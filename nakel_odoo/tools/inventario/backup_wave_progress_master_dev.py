#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Respaldo de progreso de una ola (stock.picking.batch) en master_dev — solo lectura.

Genera CSV con pickings, OV, stock.move.line (todas las del batch, incl. quantity=0)
y stock.move (demanda vs reserva).

Barcode inverso Nakel: al pickear suelen igualar qty_done=quantity; al corregir
muchas veces ANULAN la línea (quantity=0, qty_done=0), no bajan solo qty_done.
Por eso el progreso se mide también con líneas zeradas y reserva en stock.move.

Uso:
  python3 nakel_odoo/tools/inventario/backup_wave_progress_master_dev.py --batch-id 163
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import xmlrpc.client

sys.path.insert(0, "/media/klap/raid5/cursor_files")
from config_nakel import ODOO_CONFIG_MASTER_DEV  # noqa: E402

CHUNK = 200
EPS = 1e-6


def connect():
    cfg = ODOO_CONFIG_MASTER_DEV
    url = cfg["url"].rstrip("/")
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)
    uid = common.authenticate(cfg["db"], cfg["username"], cfg["password"], {})
    if not uid:
        raise SystemExit("Autenticación Odoo fallida (revisá config_nakel / credenciales).")
    return models, int(uid), cfg["db"], cfg["password"]


def m2o_id(val) -> int | None:
    if not val:
        return None
    if isinstance(val, (list, tuple)) and val:
        return int(val[0])
    return None


def m2o_name(val) -> str:
    if not val:
        return ""
    if isinstance(val, (list, tuple)) and len(val) >= 2:
        return str(val[1] or "")
    return ""


def resolve_batch_id(
    models, db: str, uid: int, pwd: str, batch_id: int | None, name: str | None
) -> tuple[int, dict[str, Any]]:
    if batch_id is not None:
        rows = models.execute_kw(
            db,
            uid,
            pwd,
            "stock.picking.batch",
            "read",
            [[batch_id]],
            {"fields": ["name", "state", "warehouse_id", "picking_ids"]},
        )
        if not rows:
            raise SystemExit(f"No existe stock.picking.batch id={batch_id}")
        return batch_id, rows[0]
    if not name:
        raise SystemExit("Indicá --batch-id o --name")
    found = models.execute_kw(
        db,
        uid,
        pwd,
        "stock.picking.batch",
        "search_read",
        [[("name", "=", name)]],
        {"fields": ["id", "name", "state", "warehouse_id", "picking_ids"], "limit": 2},
    )
    if not found:
        raise SystemExit(f"No hay batch con name={name!r}")
    if len(found) > 1:
        raise SystemExit(f"Varios batches con name={name!r}: {[r['id'] for r in found]}")
    return int(found[0]["id"]), found[0]


def chunked_read(models, db, uid, pwd, model: str, ids: list[int], fields: list[str]) -> list[dict]:
    out: list[dict] = []
    for i in range(0, len(ids), CHUNK):
        out += models.execute_kw(db, uid, pwd, model, "read", [ids[i : i + CHUNK]], {"fields": fields})
    return out


def load_product_cache(
    models, db: str, uid: int, pwd: str, ml_rows: list[dict]
) -> dict[int, dict[str, str]]:
    pids = sorted({m2o_id(ml.get("product_id")) for ml in ml_rows if m2o_id(ml.get("product_id"))})
    cache: dict[int, dict[str, str]] = {}
    for i in range(0, len(pids), CHUNK):
        chunk = pids[i : i + CHUNK]
        for p in models.execute_kw(
            db,
            uid,
            pwd,
            "product.product",
            "read",
            [chunk],
            {"fields": ["default_code", "barcode", "display_name"]},
        ):
            cache[int(p["id"])] = {
                "default_code": p.get("default_code") or "",
                "barcode": p.get("barcode") or "",
                "product": p.get("display_name") or m2o_name([p["id"], ""]),
            }
    return cache


def ml_row_dict(ml: dict, pick_by_id: dict, product_cache: dict[int, dict[str, str]]) -> dict[str, Any]:
    pick = pick_by_id.get(m2o_id(ml.get("picking_id")) or 0, {})
    pid = m2o_id(ml.get("product_id")) or 0
    prod = product_cache.get(pid, {})
    q = float(ml.get("quantity") or 0)
    d = float(ml.get("qty_done") or 0)
    return {
        "move_line_id": ml["id"],
        "picking": m2o_name(ml.get("picking_id")),
        "sale_ov": m2o_name(pick.get("sale_id")) if pick else "",
        "default_code": prod.get("default_code", ""),
        "barcode": prod.get("barcode", ""),
        "product": prod.get("product") or m2o_name(ml.get("product_id")),
        "quantity": q,
        "qty_done": d,
        "descuento_qty_done": max(0.0, q - d),
        "activa": q > EPS,
        "anulada": q <= EPS and d <= EPS,
        "picked": bool(ml.get("picked")),
        "ml_state": ml.get("state") or "",
        "location": m2o_name(ml.get("location_id")),
        "write_date": ml.get("write_date") or "",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Backup progreso ola (wave) master_dev — solo lectura.")
    ap.add_argument("--batch-id", type=int, default=None)
    ap.add_argument("--name", default=None, help="Ej. WAVE/00156")
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/media/klap/raid5/cursor_files/nakel/Prod-Incidencias/wave156/backups"),
    )
    args = ap.parse_args()

    models, uid, db, pwd = connect()
    bid, batch = resolve_batch_id(models, db, uid, pwd, args.batch_id, args.name)
    pick_ids = batch.get("picking_ids") or []
    wave_slug = re.sub(r"[^\w]+", "_", (batch.get("name") or f"batch{bid}")).strip("_").lower()[:40]

    picks = chunked_read(
        models,
        db,
        uid,
        pwd,
        "stock.picking",
        pick_ids,
        ["id", "name", "state", "origin", "sale_id", "picking_type_id", "date_done"],
    )
    pick_by_id = {p["id"]: p for p in picks}

    ml_ids = models.execute_kw(
        db, uid, pwd, "stock.move.line", "search", [[("picking_id.batch_id", "=", bid)]]
    )
    ml_rows = chunked_read(
        models,
        db,
        uid,
        pwd,
        "stock.move.line",
        ml_ids,
        [
            "id",
            "product_id",
            "quantity",
            "qty_done",
            "picked",
            "state",
            "picking_id",
            "location_id",
            "write_date",
        ],
    )

    product_cache = load_product_cache(models, db, uid, pwd, ml_rows)
    ml_export = [ml_row_dict(ml, pick_by_id, product_cache) for ml in ml_rows]
    activas = [r for r in ml_export if r["activa"]]
    anuladas = [r for r in ml_export if r["anulada"]]
    descuento_clasico = [r for r in ml_export if r["descuento_qty_done"] > EPS]

    move_ids = models.execute_kw(
        db, uid, pwd, "stock.move", "search", [[("picking_id.batch_id", "=", bid)]]
    )
    move_export: list[dict[str, Any]] = []
    move_states: Counter = Counter()
    reserva_lt_demanda = 0
    if move_ids:
        for i in range(0, len(move_ids), CHUNK):
            chunk = move_ids[i : i + CHUNK]
            moves = models.execute_kw(
                db,
                uid,
                pwd,
                "stock.move",
                "read",
                [chunk],
                {
                    "fields": [
                        "id",
                        "state",
                        "product_id",
                        "product_uom_qty",
                        "quantity",
                        "picking_id",
                        "write_date",
                    ]
                },
            )
            for m in moves:
                move_states.update([m.get("state") or ""])
                dem = float(m.get("product_uom_qty") or 0)
                res = float(m.get("quantity") or 0)
                gap = max(0.0, dem - res)
                if gap > EPS:
                    reserva_lt_demanda += 1
                pick = pick_by_id.get(m2o_id(m.get("picking_id")) or 0, {})
                move_export.append(
                    {
                        "move_id": m["id"],
                        "picking": m2o_name(m.get("picking_id")),
                        "sale_ov": m2o_name(pick.get("sale_id")) if pick else "",
                        "product": m2o_name(m.get("product_id")),
                        "demanda": dem,
                        "reserva": res,
                        "faltante_reserva": gap,
                        "state": m.get("state") or "",
                        "write_date": m.get("write_date") or "",
                    }
                )

    so_ids = sorted({m2o_id(p.get("sale_id")) for p in picks if m2o_id(p.get("sale_id"))})
    so_rows = chunked_read(
        models,
        db,
        uid,
        pwd,
        "sale.order",
        so_ids,
        ["id", "name", "state", "invoice_status", "nakel_wave_batch_id", "amount_total"],
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"{wave_slug}_batch{bid}"

    summary = {
        "timestamp_local": ts,
        "batch_id": bid,
        "batch_name": batch.get("name"),
        "batch_state": batch.get("state"),
        "warehouse": m2o_name(batch.get("warehouse_id")),
        "pickings_total": len(picks),
        "pickings_by_state": dict(Counter(p["state"] for p in picks)),
        "move_lines_total_en_ola": len(ml_export),
        "move_lines_activas_quantity_gt_0": len(activas),
        "move_lines_anuladas_qty_y_done_0": len(anuladas),
        "move_lines_descuento_qty_done": len(descuento_clasico),
        "stock_move_total": len(move_ids),
        "stock_move_by_state": dict(move_states),
        "stock_moves_reserva_lt_demanda": reserva_lt_demanda,
        "sale_orders": len(so_ids),
        "nota_barcode_inverso": (
            "Progreso típico: líneas que pasan a quantity=0 (anuladas) o stock.move con "
            "reserva < demanda. descuento_qty_done (quantity-qty_done) suele quedar en 0."
        ),
    }

    sf = args.output_dir / f"{prefix}_summary_{ts}.json"
    sf.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    # pickings + OV (igual que antes)
    pf = args.output_dir / f"{prefix}_pickings_{ts}.csv"
    with pf.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["picking_id", "name", "state", "origin", "sale_ov", "picking_type", "date_done"],
        )
        w.writeheader()
        for p in sorted(picks, key=lambda x: (x.get("name") or "")):
            w.writerow(
                {
                    "picking_id": p["id"],
                    "name": p.get("name"),
                    "state": p.get("state"),
                    "origin": (p.get("origin") or "")[:120],
                    "sale_ov": m2o_name(p.get("sale_id")),
                    "picking_type": m2o_name(p.get("picking_type_id")),
                    "date_done": p.get("date_done") or "",
                }
            )
    print("Wrote", pf)

    sof = args.output_dir / f"{prefix}_sale_orders_{ts}.csv"
    with sof.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["sale_id", "name", "state", "invoice_status", "nakel_wave_batch_id", "amount_total"],
        )
        w.writeheader()
        for r in sorted(so_rows, key=lambda x: (x.get("name") or "")):
            w.writerow(
                {
                    "sale_id": r["id"],
                    "name": r.get("name"),
                    "state": r.get("state"),
                    "invoice_status": r.get("invoice_status"),
                    "nakel_wave_batch_id": m2o_name(r.get("nakel_wave_batch_id")),
                    "amount_total": r.get("amount_total"),
                }
            )
    print("Wrote", sof)

    ml_fields = [
        "move_line_id",
        "picking",
        "sale_ov",
        "default_code",
        "barcode",
        "product",
        "quantity",
        "qty_done",
        "descuento_qty_done",
        "activa",
        "anulada",
        "picked",
        "ml_state",
        "location",
        "write_date",
    ]
    mlf = args.output_dir / f"{prefix}_move_lines_{ts}.csv"
    with mlf.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ml_fields, extrasaction="ignore")
        w.writeheader()
        for row in sorted(ml_export, key=lambda x: (x["picking"], x["product"])):
            w.writerow(row)
    print("Wrote", mlf, f"({len(ml_export)} líneas, {len(activas)} activas)")

    # Compat: solo activas (mismo nombre viejo descuento)
    mla = args.output_dir / f"{prefix}_move_lines_activas_{ts}.csv"
    with mla.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "move_line_id",
                "picking",
                "sale_ov",
                "default_code",
                "barcode",
                "product",
                "quantity",
                "qty_done",
                "descuento",
                "picked",
                "ml_state",
                "location",
            ],
        )
        w.writeheader()
        for row in sorted(activas, key=lambda x: (x["picking"], x["product"])):
            w.writerow(
                {
                    "move_line_id": row["move_line_id"],
                    "picking": row["picking"],
                    "sale_ov": row["sale_ov"],
                    "default_code": row["default_code"],
                    "barcode": row["barcode"],
                    "product": row["product"],
                    "quantity": row["quantity"],
                    "qty_done": row["qty_done"],
                    "descuento": row["descuento_qty_done"],
                    "picked": row["picked"],
                    "ml_state": row["ml_state"],
                    "location": row["location"],
                }
            )
    print("Wrote", mla, f"({len(activas)} activas)")

    if anuladas:
        azf = args.output_dir / f"{prefix}_anuladas_{ts}.csv"
        with azf.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=ml_fields, extrasaction="ignore")
            w.writeheader()
            for row in sorted(anuladas, key=lambda x: (x["picking"], x["product"])):
                w.writerow(row)
        print("Wrote", azf, f"({len(anuladas)} anuladas)")

    if move_export:
        mvf = args.output_dir / f"{prefix}_stock_moves_{ts}.csv"
        with mvf.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(move_export[0].keys()))
            w.writeheader()
            for row in sorted(move_export, key=lambda x: (-x["faltante_reserva"], x["picking"])):
                w.writerow(row)
        print("Wrote", mvf)


if __name__ == "__main__":
    main()
