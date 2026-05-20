#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Respaldo de progreso de una ola (stock.picking.batch) en master_dev — solo lectura.

Genera CSV con pickings, OV y detalle de stock.move.line (quantity, qty_done, picked).
Pensado para pickeo largo (varios días) y barcode inverso: al inicio suele haber
qty_done == quantity en todas las líneas; el avance real es cuando bajan qty_done
(descuentan lo que no va).

Uso:
  cd /media/klap/raid5/cursor_files/nakel
  python3 nakel_odoo/tools/inventario/backup_wave_progress_master_dev.py \\
    --batch-id 163 \\
    --output-dir /media/klap/raid5/cursor_files/nakel/Prod-Incidencias/wave156/backups

  python3 nakel_odoo/tools/inventario/backup_wave_progress_master_dev.py --name WAVE/00156

Requiere config_nakel.ODOO_CONFIG_MASTER_DEV.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import xmlrpc.client

sys.path.insert(0, "/media/klap/raid5/cursor_files")
from config_nakel import ODOO_CONFIG_MASTER_DEV  # noqa: E402

CHUNK = 200


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
    st_pick = Counter(p["state"] for p in picks)

    ml_ids = models.execute_kw(
        db,
        uid,
        pwd,
        "stock.move.line",
        "search",
        [[("picking_id.batch_id", "=", bid), ("quantity", ">", 0)]],
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
        ],
    )

    descuento_lines: list[dict[str, Any]] = []
    qty_done_positive = 0
    picked_true = 0
    for ml in ml_rows:
        q = float(ml.get("quantity") or 0)
        d = float(ml.get("qty_done") or 0)
        if d > 1e-9:
            qty_done_positive += 1
        if ml.get("picked"):
            picked_true += 1
        desc = max(0.0, q - d)
        if desc > 1e-6:
            pick = pick_by_id.get(m2o_id(ml.get("picking_id")) or 0, {})
            descuento_lines.append(
                {
                    "move_line_id": ml["id"],
                    "picking": m2o_name(ml.get("picking_id")),
                    "sale_ov": m2o_name(pick.get("sale_id")) if pick else "",
                    "product": m2o_name(ml.get("product_id")),
                    "quantity": q,
                    "qty_done": d,
                    "descuento": desc,
                    "picked": bool(ml.get("picked")),
                    "ml_state": ml.get("state") or "",
                }
            )

    move_ids = models.execute_kw(
        db, uid, pwd, "stock.move", "search", [[("picking_id.batch_id", "=", bid)]]
    )
    move_states = Counter()
    if move_ids:
        for i in range(0, len(move_ids), CHUNK):
            chunk = move_ids[i : i + CHUNK]
            moves = models.execute_kw(
                db, uid, pwd, "stock.move", "read", [chunk], {"fields": ["state"]}
            )
            move_states.update(m.get("state") or "" for m in moves)

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
        "pickings_by_state": dict(st_pick),
        "move_lines_with_quantity": len(ml_rows),
        "move_lines_qty_done_gt_0": qty_done_positive,
        "move_lines_picked_true": picked_true,
        "move_lines_descuento_gt_0": len(descuento_lines),
        "stock_move_total": len(move_ids),
        "stock_move_by_state": dict(move_states),
        "sale_orders": len(so_ids),
        "nota_barcode_inverso": (
            "Progreso de descuento = líneas con quantity > qty_done. "
            "Al inicio del flujo inverso suele haber 0 descuentos (todo 'contado')."
        ),
    }

    sf = args.output_dir / f"{prefix}_summary_{ts}.json"
    sf.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

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

    mlf = args.output_dir / f"{prefix}_move_lines_{ts}.csv"
    with mlf.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "move_line_id",
                "picking",
                "sale_ov",
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
        for ml in sorted(ml_rows, key=lambda x: (m2o_name(x.get("picking_id")), m2o_name(x.get("product_id")))):
            pick = pick_by_id.get(m2o_id(ml.get("picking_id")) or 0, {})
            q = float(ml.get("quantity") or 0)
            d = float(ml.get("qty_done") or 0)
            w.writerow(
                {
                    "move_line_id": ml["id"],
                    "picking": m2o_name(ml.get("picking_id")),
                    "sale_ov": m2o_name(pick.get("sale_id")) if pick else "",
                    "product": m2o_name(ml.get("product_id")),
                    "quantity": q,
                    "qty_done": d,
                    "descuento": max(0.0, q - d),
                    "picked": bool(ml.get("picked")),
                    "ml_state": ml.get("state") or "",
                    "location": m2o_name(ml.get("location_id")),
                }
            )
    print("Wrote", mlf)

    if descuento_lines:
        df = args.output_dir / f"{prefix}_descuentos_{ts}.csv"
        with df.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(descuento_lines[0].keys()))
            w.writeheader()
            for row in sorted(descuento_lines, key=lambda x: (x["picking"], x["product"])):
                w.writerow(row)
        print("Wrote", df, f"({len(descuento_lines)} líneas con descuento)")


if __name__ == "__main__":
    main()
