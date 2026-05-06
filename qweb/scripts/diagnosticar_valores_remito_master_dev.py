#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Diagnóstico: Remito Nakel 2024 — por qué falta "Valor" en líneas.

Conecta a Odoo (master_dev por defecto) vía XML-RPC y:
- lee un stock.picking (remito)
- inspecciona sus stock.move (move_ids_without_package)
- identifica moves sin sale_line_id
- si hay sale.order asociada, intenta matchear por producto para proponer fallback de precio.
"""

from __future__ import annotations

import argparse
import os
import sys
import xmlrpc.client
from collections import defaultdict


def _add_repo_root_to_syspath() -> None:
    # Este script vive en .../nakel/qweb/scripts/
    # config_nakel.py vive en .../cursor_files/config_nakel.py
    here = os.path.dirname(os.path.abspath(__file__))
    cursor_files_root = os.path.normpath(os.path.join(here, "..", "..", ".."))
    if cursor_files_root not in sys.path:
        sys.path.insert(0, cursor_files_root)


def _connect(cfg: dict) -> tuple[str, str, int, str, xmlrpc.client.ServerProxy]:
    url = cfg["url"].rstrip("/")
    db = cfg["db"]
    username = cfg["username"]
    password = cfg["password"]

    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, username, password, {})
    if not uid:
        raise SystemExit("No se pudo autenticar contra Odoo (uid falsy).")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    return url, db, uid, password, models


def _read(models, db, uid, password, model: str, ids: list[int], fields: list[str]):
    return models.execute_kw(db, uid, password, model, "read", [ids], {"fields": fields})


def _browse_first(models, db, uid, password, model: str, domain, fields: list[str]):
    rows = models.execute_kw(
        db, uid, password, model, "search_read", [domain], {"fields": fields, "limit": 1}
    )
    return rows[0] if rows else None


def _safe_m2o_id(val):
    # Odoo xmlrpc read: many2one suele ser [id, display_name] o False
    if not val:
        return None
    if isinstance(val, (list, tuple)) and val:
        return int(val[0])
    if isinstance(val, int):
        return int(val)
    return None


def _safe_float(x) -> float:
    try:
        return float(x or 0.0)
    except Exception:
        return 0.0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--picking-id", type=int, required=True, help="ID de stock.picking")
    p.add_argument(
        "--target",
        default=os.environ.get("NAKEL_TARGET", "").strip() or "master_dev",
        help="master_dev (default) o master_test (si NAKEL_TARGET=master_test)",
    )
    args = p.parse_args()

    _add_repo_root_to_syspath()
    from config_nakel import ODOO_CONFIG_MASTER_DEV  # noqa: E402

    # El selector NAKEL_TARGET ya está implementado en config_nakel.py
    cfg = ODOO_CONFIG_MASTER_DEV.copy()

    url, db, uid, password, models = _connect(cfg)

    picking_fields = [
        "name",
        "origin",
        "state",
        "scheduled_date",
        "date_done",
        "partner_id",
        "sale_id",
        "move_ids_without_package",
        "picking_type_id",
    ]
    pick = _read(models, db, uid, password, "stock.picking", [args.picking_id], picking_fields)
    if not pick:
        raise SystemExit(f"No se encontró stock.picking id={args.picking_id}")
    pick = pick[0]

    sale_id = _safe_m2o_id(pick.get("sale_id"))
    origin = pick.get("origin") or ""

    print("== Remito / Picking ==")
    print(f"- url: {url}")
    print(f"- db: {db}")
    print(f"- picking_id: {args.picking_id}")
    print(f"- name: {pick.get('name')}")
    print(f"- state: {pick.get('state')}")
    print(f"- origin: {origin!r}")
    print(f"- sale_id: {sale_id}")
    print(f"- move_ids_without_package: {len(pick.get('move_ids_without_package') or [])}")

    move_ids = pick.get("move_ids_without_package") or []
    if not move_ids:
        print("\nNo hay moves en move_ids_without_package.")
        return 0

    move_fields = [
        "id",
        "product_id",
        "product_uom_qty",
        "quantity",
        "sale_line_id",
        "move_line_ids",
        "state",
        "name",
    ]
    moves = _read(models, db, uid, password, "stock.move", move_ids, move_fields)

    # Leer move lines para poder replicar qty_ml = sum(move_line.quantity)
    all_ml_ids = []
    for m in moves:
        all_ml_ids.extend(m.get("move_line_ids") or [])
    ml_qty_by_id = {}
    if all_ml_ids:
        mls = _read(models, db, uid, password, "stock.move.line", all_ml_ids, ["id", "quantity", "qty_done"])
        for ml in mls:
            mlid = ml.get("id")
            # Odoo 18 suele usar 'quantity' (reservado) y qty_done; priorizamos 'quantity' como el template.
            ml_qty_by_id[mlid] = _safe_float(ml.get("quantity") or ml.get("qty_done"))

    # Preparar info de OV (si existe)
    so = None
    so_lines = []
    so_lines_by_product = defaultdict(list)
    if sale_id:
        so = _read(models, db, uid, password, "sale.order", [sale_id], ["name", "order_line", "currency_id"])
        so = so[0] if so else None
    elif origin:
        # Fallback: por nombre exacto (origin suele ser SOxxxx)
        so = _browse_first(models, db, uid, password, "sale.order", [("name", "=", origin)], ["name", "order_line", "currency_id"])

    if so and so.get("order_line"):
        sol_ids = so["order_line"]
        sol_fields = ["id", "product_id", "product_uom_qty", "price_unit", "price_subtotal", "discount", "name"]
        so_lines = _read(models, db, uid, password, "sale.order.line", sol_ids, sol_fields)
        for l in so_lines:
            pid = _safe_m2o_id(l.get("product_id"))
            if pid:
                so_lines_by_product[pid].append(l)

    # Para replicar el template, necesitamos leer algunos campos de sale.order.line apuntados por sale_line_id
    sol_by_id = {}
    sol_ids_from_moves = []
    for m in moves:
        sid = _safe_m2o_id(m.get("sale_line_id"))
        if sid:
            sol_ids_from_moves.append(sid)
    sol_ids_from_moves = sorted(set(sol_ids_from_moves))
    if sol_ids_from_moves:
        sol_fields = ["id", "product_id", "product_uom_qty", "price_subtotal", "currency_id", "price_unit", "discount", "name"]
        sols = _read(models, db, uid, password, "sale.order.line", sol_ids_from_moves, sol_fields)
        sol_by_id = {int(x["id"]): x for x in sols if x and x.get("id")}

    if so:
        print("\n== Orden de venta detectada ==")
        print(f"- so_id: {sale_id or '(por origin)'}")
        print(f"- so_name: {so.get('name')}")
        print(f"- order_line: {len(so_lines)}")
    else:
        print("\n== Orden de venta detectada ==")
        print("- No se detectó sale.order (ni por sale_id ni por origin).")

    # Analizar moves
    total = len(moves)
    with_sale_line = 0
    without_sale_line = 0
    without_sale_line_but_match = 0
    ambiguous_matches = 0
    sample_missing = []
    would_print_dash = 0
    would_print_amount = 0
    sample_dash_by_template = []

    for m in moves:
        pid = _safe_m2o_id(m.get("product_id"))
        sale_line_id = _safe_m2o_id(m.get("sale_line_id"))
        if sale_line_id:
            with_sale_line += 1
        else:
            without_sale_line += 1

        # Replicar qty_show del template:
        # qty_ml = sum(move_line.quantity); qty_show = qty_ml si existe, sino quantity/product_uom_qty
        ml_ids = m.get("move_line_ids") or []
        qty_ml = sum(ml_qty_by_id.get(int(x), 0.0) for x in ml_ids) if ml_ids else 0.0
        qty_show = qty_ml if qty_ml else (_safe_float(m.get("quantity")) or _safe_float(m.get("product_uom_qty")))

        # Regla actual del template para imprimir valor:
        # imprime solo si l.sale_line_id y l.sale_line_id.product_uom_qty (no cero)
        sol = sol_by_id.get(int(sale_line_id)) if sale_line_id else None
        sol_uom_qty = _safe_float(sol.get("product_uom_qty")) if sol else 0.0
        if sale_line_id and sol_uom_qty:
            would_print_amount += 1
        else:
            would_print_dash += 1
            if len(sample_dash_by_template) < 12:
                sample_dash_by_template.append(
                    {
                        "move_id": m.get("id"),
                        "product_id": pid,
                        "product_name": (m.get("product_id")[1] if isinstance(m.get("product_id"), (list, tuple)) else None),
                        "qty_show": qty_show,
                        "sale_line_id": sale_line_id,
                        "sol_product_uom_qty": sol_uom_qty,
                        "sol_price_subtotal": _safe_float(sol.get("price_subtotal")) if sol else None,
                    }
                )

        # Si no hay sale_line_id, evaluar fallback por producto en OV
        if not sale_line_id:
            matches = so_lines_by_product.get(pid, []) if pid else []
            if matches:
                without_sale_line_but_match += 1
                if len(matches) > 1:
                    ambiguous_matches += 1
            if len(sample_missing) < 12:
                sample_missing.append(
                    {
                        "move_id": m.get("id"),
                        "product_id": pid,
                        "product_name": (m.get("product_id")[1] if isinstance(m.get("product_id"), (list, tuple)) else None),
                        "qty": qty_show,
                        "matches": len(matches),
                        "match_prices": [(_safe_float(x.get("price_unit")), _safe_float(x.get("price_subtotal"))) for x in matches[:3]],
                    }
                )

    print("\n== Resumen por línea (stock.move) ==")
    print(f"- total_moves: {total}")
    print(f"- con sale_line_id: {with_sale_line}")
    print(f"- sin sale_line_id: {without_sale_line}")
    if so:
        print(f"- sin sale_line_id pero con match por producto en OV: {without_sale_line_but_match}")
        print(f"- matches ambiguos (múltiples líneas OV mismo producto): {ambiguous_matches}")
    print("\n== Resultado replicando lógica del template actual (columna 'Valor') ==")
    print(f"- imprimiría importe: {would_print_amount}")
    print(f"- imprimiría '—': {would_print_dash}")

    if sample_dash_by_template:
        print("\n== Muestra de líneas que el template imprimiría como '—' ==")
        for s in sample_dash_by_template:
            print(
                f"- move_id={s['move_id']} product_id={s['product_id']} "
                f"qty_show≈{_safe_float(s['qty_show'])} "
                f"sale_line_id={s['sale_line_id']} sol.product_uom_qty={s['sol_product_uom_qty']} "
                f"sol.price_subtotal={s['sol_price_subtotal']}"
            )

    if sample_missing:
        print("\n== Muestra de moves sin sale_line_id ==")
        for s in sample_missing:
            print(
                f"- move_id={s['move_id']} product_id={s['product_id']} "
                f"qty≈{s['qty']} matches_en_OV={s['matches']} "
                f"precios={s['match_prices']}"
            )

    # Diagnóstico final orientado al template
    print("\n== Diagnóstico orientado al template Remito Nakel 2024 ==")
    if would_print_dash:
        print(
            "- En este picking hay líneas que el template imprime como '—'. "
            "La condición que dispara esto es: sale_line_id inexistente o sale_line_id.product_uom_qty=0."
        )
        if without_sale_line:
            print(
                "- Parte del problema es ausencia de sale_line_id en algunos moves: se arregla con fallback desde la OV."
            )
        else:
            print(
                "- Aquí TODOS los moves tienen sale_line_id: si igualmente hay '—', el foco es sale_line_id.product_uom_qty=0 "
                "o un prorrateo inválido (división por cero)."
            )
    elif without_sale_line:
        print(
            "- El template actual toma 'Valor' desde move.sale_line_id; "
            "por eso estas líneas imprimen '—' aunque la OV tenga precios."
        )
        if so and without_sale_line_but_match:
            print(
                "- En este picking hay evidencia de que se puede tomar el precio desde la OV "
                "haciendo fallback por producto (con manejo de ambigüedad)."
            )
        elif so:
            print(
                "- Hay OV detectada, pero no se encontró match por producto para algunas líneas: "
                "requiere heurística más fina (p.ej. descripción/cantidad)."
            )
        else:
            print(
                "- No hay OV detectable: no existe una fuente de 'precio real de venta' en stock "
                "sin una referencia a venta (habría que definir otra fuente: tarifa/costo/campo custom)."
            )
    else:
        print("- Todos los moves tienen sale_line_id: el problema no sería el vínculo move->venta.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

