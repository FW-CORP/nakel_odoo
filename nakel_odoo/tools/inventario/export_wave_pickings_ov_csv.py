#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exporta CSV de pickings y órdenes de venta vinculadas a un `stock.picking.batch`
(wave), más conteos de `stock.move` / `stock.move.line` y brechas Barcode
(`qty_done`, `picked`).

Solo lectura (no modifica Odoo).

Uso:
  cd /media/klap/raid5/cursor_files/nakel
  python3 nakel_odoo/tools/inventario/export_wave_pickings_ov_csv.py --batch-id 151

  python3 nakel_odoo/tools/inventario/export_wave_pickings_ov_csv.py --name WAVE/00145

Requiere `config_nakel.ODOO_CONFIG_MASTER_DEV`.

Salida por defecto: `/media/klap/raid5/cursor_files/backups/`
  wave<N>_batch<id>_pickings_<timestamp>.csv
  wave<N>_batch<id>_sale_orders_<timestamp>.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import xmlrpc.client

sys.path.insert(0, "/media/klap/raid5/cursor_files")
from config_nakel import ODOO_CONFIG_MASTER_DEV  # noqa: E402


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


def resolve_batch_id(models, db: str, uid: int, pwd: str, batch_id: int | None, name: str | None) -> tuple[int, dict[str, Any]]:
    if batch_id is not None:
        rows = models.execute_kw(
            db, uid, pwd, "stock.picking.batch", "read", [[batch_id]], {"fields": ["name", "state", "warehouse_id", "picking_ids"]}
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


def main() -> None:
    ap = argparse.ArgumentParser(description="Export pickings + OV CSV para un batch (wave).")
    ap.add_argument("--batch-id", type=int, default=None, help="ID de stock.picking.batch")
    ap.add_argument("--name", default=None, help="Nombre exacto del batch, ej. WAVE/00145")
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/media/klap/raid5/cursor_files/backups"),
        help="Directorio de salida CSV",
    )
    args = ap.parse_args()

    models, uid, db, pwd = connect()
    bid, batch = resolve_batch_id(models, db, uid, pwd, args.batch_id, args.name)
    pick_ids = batch.get("picking_ids") or []
    wave_slug = re.sub(r"[^\w]+", "_", (batch.get("name") or f"batch{bid}")).strip("_").lower()[:40]

    picks = models.execute_kw(
        db,
        uid,
        pwd,
        "stock.picking",
        "read",
        [pick_ids],
        {"fields": ["id", "name", "state", "origin", "sale_id", "picking_type_id", "date_done"]},
    )
    st_pick = Counter(p["state"] for p in picks)
    print("BATCH", batch.get("name"), "id=", bid, "state=", batch.get("state"), "pickings", len(picks), "states", dict(st_pick))

    base_m: list = [("picking_id.batch_id", "=", bid)]
    mc = models.execute_kw(db, uid, pwd, "stock.move", "search_count", [base_m])
    print("stock.move total", mc)
    for stn in ("assigned", "partially_available", "waiting", "confirmed", "done", "cancel"):
        c = models.execute_kw(db, uid, pwd, "stock.move", "search_count", [base_m + [("state", "=", stn)]])
        if c:
            print(f"  move {stn}", c)

    ml_base: list = [("picking_id.batch_id", "=", bid)]
    mlc = models.execute_kw(db, uid, pwd, "stock.move.line", "search_count", [ml_base])
    print("stock.move.line total", mlc)
    for stn in ("assigned", "partially_available", "waiting", "confirmed", "done", "cancel"):
        c = models.execute_kw(db, uid, pwd, "stock.move.line", "search_count", [ml_base + [("state", "=", stn)]])
        if c:
            print(f"  ml {stn}", c)

    gap_done = models.execute_kw(
        db, uid, pwd, "stock.move.line", "search_count", [ml_base + [("quantity", ">", 0), ("qty_done", "=", 0)]]
    )
    gap_picked = models.execute_kw(
        db, uid, pwd, "stock.move.line", "search_count", [ml_base + [("quantity", ">", 0), ("picked", "=", False)]]
    )
    print("ML qty_done gap (qty>0, qty_done=0)", gap_done)
    print("ML picked gap (qty>0, picked=False)", gap_picked)

    so_ids = sorted({m2o_id(p.get("sale_id")) for p in picks if m2o_id(p.get("sale_id"))})
    print("sale.orders linked", len(so_ids))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"{wave_slug}_batch{bid}"

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
                    "sale_ov": m2o_name(p.get("sale_id")) if p.get("sale_id") else "",
                    "picking_type": m2o_name(p.get("picking_type_id")),
                    "date_done": p.get("date_done") or "",
                }
            )
    print("Wrote", pf)

    sof = args.output_dir / f"{prefix}_sale_orders_{ts}.csv"
    so_rows: list[dict[str, Any]] = []
    for i in range(0, len(so_ids), 200):
        chunk = so_ids[i : i + 200]
        so_rows += models.execute_kw(
            db,
            uid,
            pwd,
            "sale.order",
            "read",
            [chunk],
            {"fields": ["id", "name", "state", "invoice_status", "nakel_wave_batch_id", "amount_total"]},
        )
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


if __name__ == "__main__":
    main()
