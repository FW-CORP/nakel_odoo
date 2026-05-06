#!/usr/bin/env python3
"""
Export SOLO LECTURA de comisiones 40/60 a CSV (abrible en Excel).

Período objetivo:
- Facturas/NC: por invoice_date dentro del rango.
- Cobranza: pagos conciliados dentro del rango (invoice_payments_widget).

Salidas (por defecto en /media/klap/raid5/cursor_files/reportes):
- comisiones_resumen_<from>_<to>.csv
- comisiones_detalle_facturas_<from>_<to>.csv
- comisiones_detalle_ncs_<from>_<to>.csv

Nota:
- No requiere dependencias extra (sin .xlsx).
- Para NCs: se exportan como documento separado (move_type=out_refund) y su comisión se calcula igual
  sobre líneas (price_subtotal) con signo propio del documento.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import xmlrpc.client
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable

sys.path.insert(0, "/media/klap/raid5/cursor_files")

try:
    from config_nakel import ODOO_CONFIG_MASTER_DEV
except Exception as e:  # pragma: no cover
    raise SystemExit(f"No se pudo importar config_nakel / ODOO_CONFIG_MASTER_DEV: {e}")


def parse_ymd(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def m2o_id(v: Any) -> int | None:
    if not v:
        return None
    if isinstance(v, (list, tuple)):
        return int(v[0]) if v else None
    if isinstance(v, int):
        return int(v)
    return None


def connect():
    cfg = ODOO_CONFIG_MASTER_DEV
    url = cfg["url"].rstrip("/")
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    uid = common.authenticate(cfg["db"], cfg["username"], cfg["password"], {})
    if not uid:
        raise SystemExit("Autenticación Odoo fallida (master_dev)")
    return models, int(uid), cfg["db"], cfg["password"], cfg


def search(models, db, uid, pwd, model: str, domain: list, *, limit: int | None = None, order: str | None = None):
    kwargs: dict[str, Any] = {}
    if limit is not None:
        kwargs["limit"] = int(limit)
    if order:
        kwargs["order"] = order
    return models.execute_kw(db, uid, pwd, model, "search", [domain], kwargs)


def read(models, db, uid, pwd, model: str, ids: list[int], fields: list[str]):
    if not ids:
        return []
    return models.execute_kw(db, uid, pwd, model, "read", [ids], {"fields": fields})


def chunked(seq: list[int], size: int) -> Iterable[list[int]]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def read_batched(models, db, uid, pwd, model: str, ids: list[int], fields: list[str], *, batch_size: int = 400):
    out: list[dict[str, Any]] = []
    for part in chunked(ids, batch_size):
        out.extend(read(models, db, uid, pwd, model, part, fields))
    return out


@dataclass(frozen=True)
class Rule:
    type: str
    rate: float
    product_categ_id: int | None  # None = regla general


def load_plan_rules(models, db, uid, pwd, plan_id: int) -> list[Rule]:
    rows = models.execute_kw(
        db,
        uid,
        pwd,
        "sale.commission.plan.achievement",
        "search_read",
        [[("plan_id", "=", plan_id)]],
        {"fields": ["type", "rate", "product_categ_id"], "limit": 500, "order": "id asc"},
    )
    out: list[Rule] = []
    for r in rows:
        out.append(
            Rule(
                type=r.get("type"),
                rate=float(r.get("rate") or 0.0),
                product_categ_id=m2o_id(r.get("product_categ_id")),
            )
        )
    return out


def pick_rate(rules: list[Rule], categ_id: int | None) -> float:
    for r in rules:
        if r.product_categ_id and categ_id and r.product_categ_id == categ_id:
            return r.rate
    for r in rules:
        if not r.product_categ_id:
            return r.rate
    return 0.0


def payments_in_period_from_widget(inv: dict, dfrom: date, dto: date) -> tuple[float, list[dict[str, Any]]]:
    """
    Devuelve (monto_pagado_en_periodo, items_filtrados).
    items_filtrados: [{'date': 'YYYY-MM-DD', 'amount': 123.0, ...}]
    """
    w = inv.get("invoice_payments_widget")
    if not w or not isinstance(w, dict):
        return 0.0, []
    content = w.get("content")
    if not isinstance(content, list):
        return 0.0, []
    total = 0.0
    picked: list[dict[str, Any]] = []
    for item in content:
        try:
            ds = item.get("date")
            amt = float(item.get("amount") or 0.0)
            if not ds:
                continue
            dd = parse_ymd(ds)
            if dfrom <= dd <= dto:
                total += amt
                picked.append(item)
        except Exception:
            continue
    return total, picked


def safe_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    return str(v)


def fmt_rate(r: float) -> str:
    return f"{r*100:.4f}%"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan-id", type=int, default=1)
    ap.add_argument("--from", dest="date_from", required=True, help="YYYY-MM-DD")
    ap.add_argument("--to", dest="date_to", required=True, help="YYYY-MM-DD")
    ap.add_argument("--out-dir", type=str, default="/media/klap/raid5/cursor_files/reportes")
    ap.add_argument(
        "--fixed-rate",
        type=float,
        default=0.40,
        help="Porcentaje fijo a pagar (ej: 0.40 para 40%).",
    )
    ap.add_argument(
        "--variable-rate",
        type=float,
        default=0.60,
        help="Porcentaje variable a pagar según cobranza (ej: 0.60 para 60%).",
    )
    ap.add_argument("--limit-moves", type=int, default=0, help="Límite de documentos (facturas+NC) por seguridad")
    ap.add_argument(
        "--only-users",
        type=str,
        default="",
        help="CSV de res.users IDs para filtrar (ej: '90,91,88,108'). Vacío = todos.",
    )
    ap.add_argument(
        "--split-by-user",
        action="store_true",
        help="Genera 1 set de CSV (resumen+detalle) por vendedor (reduce payload).",
    )
    ap.add_argument("--debug-json", action="store_true", help="Guarda un JSON auxiliar con contadores.")
    args = ap.parse_args()

    dfrom = parse_ymd(args.date_from)
    dto = parse_ymd(args.date_to)
    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)

    fixed_rate = float(args.fixed_rate)
    variable_rate = float(args.variable_rate)
    if fixed_rate < 0 or variable_rate < 0:
        raise SystemExit("fixed-rate/variable-rate no pueden ser negativos.")
    if fixed_rate + variable_rate > 1.0000001:
        raise SystemExit("fixed-rate + variable-rate no puede superar 1.0 (100%).")

    only_users: set[int] = set()
    if args.only_users.strip():
        only_users = {int(x.strip()) for x in args.only_users.split(",") if x.strip()}

    models, uid, db, pwd, cfg = connect()
    print(f"✅ Conexión OK: {cfg['url']} | db={db} | uid={uid}")
    print(f"Periodo: {dfrom.isoformat()} → {dto.isoformat()}")
    print(f"Plan ID: {args.plan_id}")

    rules = [r for r in load_plan_rules(models, db, uid, pwd, args.plan_id) if r.type == "amount_invoiced"]
    if not rules:
        raise SystemExit("No encontré reglas type=amount_invoiced para el plan. Revisar plan-id.")

    base_domain = [
        ("move_type", "in", ["out_invoice", "out_refund"]),
        ("state", "=", "posted"),
        ("invoice_date", ">=", dfrom.isoformat()),
        ("invoice_date", "<=", dto.isoformat()),
    ]
    limit = int(args.limit_moves) if int(args.limit_moves) > 0 else None

    # Determinar users objetivo:
    # - si only_users está vacío: exporta todos los vendedores que tengan docs en el período (1 solo lote)
    # - si only_users está seteado:
    #   - split-by-user: 1 lote por user (recomendado)
    #   - sin split: filtra en el search con invoice_user_id in only_users
    target_user_ids: list[int]
    if only_users:
        target_user_ids = sorted(list(only_users))
    else:
        # Detectar users con movimientos en el período (rápido y de bajo payload)
        uids = search(
            models,
            db,
            uid,
            pwd,
            "account.move",
            base_domain,
            limit=limit,
            order="id asc",
        )
        if not uids:
            print("Documentos (facturas + NC) posteados en período: 0")
            return 0
        tmp_moves = read_batched(models, db, uid, pwd, "account.move", uids, ["invoice_user_id"], batch_size=400)
        target_user_ids = sorted({m2o_id(m.get("invoice_user_id")) for m in tmp_moves if m2o_id(m.get("invoice_user_id"))})

    user_rows = read_batched(models, db, uid, pwd, "res.users", target_user_ids, ["name", "login"], batch_size=400)
    user_by_id = {u["id"]: u for u in user_rows}

    def slug(s: str) -> str:
        s = (s or "").strip().lower()
        out = []
        for ch in s:
            if ch.isalnum():
                out.append(ch)
            elif ch in {" ", "-", "_"}:
                out.append("_")
        x = "".join(out).strip("_")
        while "__" in x:
            x = x.replace("__", "_")
        return x or "sin_nombre"

    def export_one_user(user_id: int | None) -> dict[str, Any]:
        dom = list(base_domain)
        if user_id is not None:
            dom.append(("invoice_user_id", "=", int(user_id)))
        elif only_users and not args.split_by_user:
            dom.append(("invoice_user_id", "in", sorted(list(only_users))))

        move_ids = search(models, db, uid, pwd, "account.move", dom, limit=limit, order="id asc")
        label = f"user_id={user_id}" if user_id is not None else "users=varios"
        print(f"Documentos ({label}) en período: {len(move_ids)}")
        if not move_ids:
            return {"move_ids": 0, "move_lines": 0, "products": 0, "categories": 0}

        move_rows = read_batched(
            models,
            db,
            uid,
            pwd,
            "account.move",
            move_ids,
            [
                "name",
                "move_type",
                "invoice_date",
                "invoice_user_id",
                "partner_id",
                "amount_total",
                "amount_residual",
                "payment_state",
                "invoice_origin",
                "invoice_payments_widget",
            ],
            batch_size=350,
        )
        move_by_id = {m["id"]: m for m in move_rows}

        line_ids = search(
            models,
            db,
            uid,
            pwd,
            "account.move.line",
            [("move_id", "in", move_ids), ("display_type", "=", "product")],
            limit=None,
            order="id asc",
        )
        line_rows = read_batched(
            models,
            db,
            uid,
            pwd,
            "account.move.line",
            line_ids,
            ["move_id", "product_id", "price_subtotal", "quantity", "name", "display_type"],
            batch_size=800,
        )

        prod_ids = sorted({m2o_id(l.get("product_id")) for l in line_rows if m2o_id(l.get("product_id"))})
        prod_rows = read_batched(models, db, uid, pwd, "product.product", prod_ids, ["categ_id"], batch_size=800)
        prod_to_categ = {p["id"]: m2o_id(p.get("categ_id")) for p in prod_rows}

        categ_ids = sorted({cid for cid in prod_to_categ.values() if cid})
        categ_rows = read_batched(
            models, db, uid, pwd, "product.category", categ_ids, ["complete_name", "name"], batch_size=800
        )
        categ_name_by_id = {c["id"]: safe_text(c.get("complete_name") or c.get("name")) for c in categ_rows}

        lines_by_move: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for l in line_rows:
            mid = m2o_id(l.get("move_id"))
            if mid:
                lines_by_move[mid].append(l)

        partner_ids = sorted({m2o_id(m.get("partner_id")) for m in move_rows if m2o_id(m.get("partner_id"))})
        partner_rows = read_batched(
            models, db, uid, pwd, "res.partner", partner_ids, ["name", "ref", "vat"], batch_size=400
        )
        partner_by_id = {p["id"]: p for p in partner_rows}

        stamp = f"{dfrom.isoformat()}_{dto.isoformat()}"
        suffix = ""
        if user_id is not None:
            u = user_by_id.get(user_id, {})
            suffix = f"_{user_id}_{slug(safe_text(u.get('name')))}"
        resumen_path = os.path.join(out_dir, f"comisiones_resumen_{stamp}{suffix}.csv")
        fact_path = os.path.join(out_dir, f"comisiones_detalle_facturas_{stamp}{suffix}.csv")
        nc_path = os.path.join(out_dir, f"comisiones_detalle_ncs_{stamp}{suffix}.csv")
        resumen_fields = [
            "user_id",
            "vendedor",
            "login",
            "docs_facturas",
            "docs_ncs",
            "comision_total_neta",
            "tasa_fija",
            "tasa_variable",
            "pagar_fijo",
            "pagar_variable_prorrateado",
            "pagar_40",
            "pagar_60_prorrateado",
            "total_a_pagar",
        ]
        detalle_fields = [
            "move_id",
            "move_type",
            "documento",
            "invoice_date",
            "invoice_origin",
            "payment_state",
            "partner_id",
            "cliente",
            "cliente_ref",
            "cliente_vat",
            "invoice_user_id",
            "vendedor",
            "base_sin_impuestos",
            "comision_total",
            "tasa_fija",
            "tasa_variable",
            "pagar_fijo",
            "pagar_variable_prorrateado",
            "pagar_40",
            "pagar_60_prorrateado",
            "pagado_en_periodo",
            "total_documento",
            "ratio_cobrado_en_periodo",
            "detalle_lineas_json",
        ]

        per_user = defaultdict(lambda: {"docs_fact": 0, "docs_nc": 0, "comm": 0.0, "pay40": 0.0, "pay60": 0.0})

        def compute_move(move: dict) -> tuple[float, float, list[dict[str, Any]], float, float]:
            mid = int(move["id"])
            details: list[dict[str, Any]] = []
            base_total = 0.0
            comm_total = 0.0
            for l in lines_by_move.get(mid, []):
                base = float(l.get("price_subtotal") or 0.0)
                base_total += base
                prod_id = m2o_id(l.get("product_id"))
                categ_id = prod_to_categ.get(prod_id) if prod_id else None
                rate = pick_rate(rules, categ_id)
                comm = base * rate
                comm_total += comm
                details.append(
                    {
                        "product_id": prod_id,
                        "categ_id": categ_id,
                        "categ_name": categ_name_by_id.get(categ_id or 0, ""),
                        "base": base,
                        "rate": rate,
                        "rate_fmt": fmt_rate(rate),
                        "commission": comm,
                        "line_name": safe_text(l.get("name")),
                        "qty": float(l.get("quantity") or 0.0),
                    }
                )

            paid_in_period, _items = payments_in_period_from_widget(move, dfrom, dto)
            total_doc = float(move.get("amount_total") or 0.0)
            ratio = (paid_in_period / total_doc) if total_doc else 0.0
            if ratio < 0:
                ratio = 0.0
            if ratio > 1.0:
                ratio = 1.0
            return base_total, comm_total, details, float(paid_in_period), float(ratio)

        with open(fact_path, "w", newline="", encoding="utf-8") as f_fact, open(
            nc_path, "w", newline="", encoding="utf-8"
        ) as f_nc:
            w_fact = csv.DictWriter(f_fact, fieldnames=detalle_fields)
            w_nc = csv.DictWriter(f_nc, fieldnames=detalle_fields)
            w_fact.writeheader()
            w_nc.writeheader()

            for mid in move_ids:
                move = move_by_id.get(mid)
                if not move:
                    continue
                inv_user_id = m2o_id(move.get("invoice_user_id"))
                if not inv_user_id:
                    continue

                base_total, comm_total, details, paid_in_period, ratio = compute_move(move)
                pay_fixed = comm_total * fixed_rate
                pay_variable = comm_total * variable_rate * ratio

                u = user_by_id.get(inv_user_id, {})
                partner_id = m2o_id(move.get("partner_id"))
                partner = partner_by_id.get(partner_id or 0, {})

                row = {
                    "move_id": mid,
                    "move_type": safe_text(move.get("move_type")),
                    "documento": safe_text(move.get("name")),
                    "invoice_date": safe_text(move.get("invoice_date")),
                    "invoice_origin": safe_text(move.get("invoice_origin")),
                    "payment_state": safe_text(move.get("payment_state")),
                    "partner_id": partner_id or "",
                    "cliente": safe_text(partner.get("name")),
                    "cliente_ref": safe_text(partner.get("ref")),
                    "cliente_vat": safe_text(partner.get("vat")),
                    "invoice_user_id": inv_user_id,
                    "vendedor": safe_text(u.get("name")),
                    "base_sin_impuestos": f"{base_total:.2f}",
                    "comision_total": f"{comm_total:.2f}",
                    "tasa_fija": f"{fixed_rate:.6f}",
                    "tasa_variable": f"{variable_rate:.6f}",
                    "pagar_fijo": f"{pay_fixed:.2f}",
                    "pagar_variable_prorrateado": f"{pay_variable:.2f}",
                    # Compat legacy:
                    "pagar_40": f"{pay_fixed:.2f}",
                    "pagar_60_prorrateado": f"{pay_variable:.2f}",
                    "pagado_en_periodo": f"{paid_in_period:.2f}",
                    "total_documento": f"{float(move.get('amount_total') or 0.0):.2f}",
                    "ratio_cobrado_en_periodo": f"{ratio:.6f}",
                    "detalle_lineas_json": json.dumps(details, ensure_ascii=False),
                }

                if safe_text(move.get("move_type")) == "out_refund":
                    w_nc.writerow(row)
                    per_user[inv_user_id]["docs_nc"] += 1
                else:
                    w_fact.writerow(row)
                    per_user[inv_user_id]["docs_fact"] += 1

                per_user[inv_user_id]["comm"] += comm_total
                per_user[inv_user_id]["pay40"] += pay_fixed
                per_user[inv_user_id]["pay60"] += pay_variable

        with open(resumen_path, "w", newline="", encoding="utf-8") as f_res:
            w_res = csv.DictWriter(f_res, fieldnames=resumen_fields)
            w_res.writeheader()
            for uid_ in sorted(per_user.keys()):
                u = user_by_id.get(uid_, {})
                comm = per_user[uid_]["comm"]
                pay40 = per_user[uid_]["pay40"]
                pay60 = per_user[uid_]["pay60"]
                w_res.writerow(
                    {
                        "user_id": uid_,
                        "vendedor": safe_text(u.get("name")),
                        "login": safe_text(u.get("login")),
                        "docs_facturas": per_user[uid_]["docs_fact"],
                        "docs_ncs": per_user[uid_]["docs_nc"],
                        "comision_total_neta": f"{comm:.2f}",
                        "tasa_fija": f"{fixed_rate:.6f}",
                        "tasa_variable": f"{variable_rate:.6f}",
                        "pagar_fijo": f"{pay40:.2f}",
                        "pagar_variable_prorrateado": f"{pay60:.2f}",
                        # Compat legacy:
                        "pagar_40": f"{pay40:.2f}",
                        "pagar_60_prorrateado": f"{pay60:.2f}",
                        "total_a_pagar": f"{(pay40 + pay60):.2f}",
                    }
                )

        print("\n✅ CSV generados:")
        print(f"- {resumen_path}")
        print(f"- {fact_path}")
        print(f"- {nc_path}")

        return {"move_ids": len(move_ids), "move_lines": len(line_ids), "products": len(prod_ids), "categories": len(categ_ids)}

    debug_all: dict[str, Any] = {"only_users": sorted(list(only_users)), "runs": []}

    if args.split_by_user and target_user_ids:
        for uid_ in target_user_ids:
            stats = export_one_user(uid_)
            debug_all["runs"].append({"user_id": uid_, **(stats or {})})
    else:
        stats = export_one_user(None)
        debug_all["runs"].append({"user_id": None, **(stats or {})})

    if args.debug_json:
        stamp = f"{dfrom.isoformat()}_{dto.isoformat()}"
        debug_path = os.path.join(out_dir, f"comisiones_debug_{stamp}.json")
        with open(debug_path, "w", encoding="utf-8") as f:
            json.dump(debug_all, f, ensure_ascii=False, indent=2)
        print(f"- {debug_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

