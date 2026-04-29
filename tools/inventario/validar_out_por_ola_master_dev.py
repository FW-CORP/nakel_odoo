#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dry-run / apply: validar masivamente OUT (Customer Delivery) asociados a una OLA/WAVE en master_dev,
SIN depender del listado de pickings dentro del batch (picking_ids), que puede estar incompleto.

Estrategia:
1) Resolver batch (stock.picking.batch) por --batch-id o --name (ej: WAVE/00104)
2) Tomar OV desde sale.order.nakel_wave_batch_id = batch_id (si el campo existe)
3) Buscar OUT (stock.picking) por sale_id in OV y picking_type_id.sequence_code='OUT'
   - opcionalmente acotado por warehouse de la ola
4) DRY-RUN: exporta CSV con estados y candidatos a validar
5) APPLY: intenta button_validate en los OUT en estado != done/cancel
   - si devuelve wizard (dict con res_model), se registra y se saltea (no asume confirmaciones)

Uso:
  python3 nakel_odoo/tools/inventario/validar_out_por_ola_master_dev.py --name "WAVE/00104" --dry-run
  python3 nakel_odoo/tools/inventario/validar_out_por_ola_master_dev.py --batch-id 109 --dry-run

  # Solo si querés ejecutar (escritura):
  python3 ... --name "WAVE/00104" --apply --i-know-what-im-doing

Salida:
  /media/klap/raid5/cursor_files/backups/out_validate_wave_<batch_id>_<ts>.csv
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path
from typing import Any

import xmlrpc.client

import sys

sys.path.insert(0, "/media/klap/raid5/cursor_files")

from config_nakel import ODOO_CONFIG_MASTER_DEV  # noqa: E402


def connect():
    cfg = ODOO_CONFIG_MASTER_DEV
    url = cfg["url"].rstrip("/")
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)
    uid = common.authenticate(cfg["db"], cfg["username"], cfg["password"], {})
    if not uid:
        raise SystemExit("Autenticación Odoo fallida (master_dev)")
    return models, int(uid), cfg["db"], cfg["password"], cfg


def fields_get(models, db, uid, pwd, model: str) -> dict[str, Any]:
    return models.execute_kw(db, uid, pwd, model, "fields_get", [], {"attributes": ["type", "relation"]})


def search(models, db, uid, pwd, model: str, domain: list, *, limit: int | None = None, order: str | None = None) -> list[int]:
    kwargs: dict[str, Any] = {}
    if limit is not None:
        kwargs["limit"] = int(limit)
    if order:
        kwargs["order"] = order
    return models.execute_kw(db, uid, pwd, model, "search", [domain], kwargs)


def read(models, db, uid, pwd, model: str, ids: list[int], fields: list[str]) -> list[dict[str, Any]]:
    if not ids:
        return []
    return models.execute_kw(db, uid, pwd, model, "read", [ids], {"fields": fields})


def search_read(
    models, db, uid, pwd, model: str, domain: list, *, fields: list[str], limit: int | None = None, order: str | None = None
) -> list[dict[str, Any]]:
    kwargs: dict[str, Any] = {"fields": fields}
    if limit is not None:
        kwargs["limit"] = int(limit)
    if order:
        kwargs["order"] = order
    return models.execute_kw(db, uid, pwd, model, "search_read", [domain], kwargs)


def chunked(seq: list[int], size: int) -> list[list[int]]:
    return [seq[i : i + size] for i in range(0, len(seq), size)]


def m2o_id(val) -> int | None:
    if not val:
        return None
    if isinstance(val, (list, tuple)) and val:
        return int(val[0])
    if isinstance(val, int):
        return int(val)
    return None


def m2o_name(val) -> str:
    if not val:
        return ""
    if isinstance(val, (list, tuple)) and len(val) >= 2:
        return str(val[1] or "")
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--batch-id", type=int, help="ID de stock.picking.batch (ej: 109)")
    g.add_argument("--name", type=str, help='Nombre ilike (ej: "WAVE/00104")')
    ap.add_argument("--dry-run", action="store_true", help="Solo reporta (default)")
    ap.add_argument("--apply", action="store_true", help="Intenta validar OUT (escritura)")
    ap.add_argument("--i-know-what-im-doing", action="store_true", help="Requerido para --apply")
    ap.add_argument(
        "--outdir",
        type=Path,
        default=Path("/media/klap/raid5/cursor_files/backups"),
        help="Directorio de salida del CSV",
    )
    args = ap.parse_args()

    if args.apply and not args.i_know_what_im_doing:
        raise SystemExit("Para --apply necesitás --i-know-what-im-doing")
    if not args.apply:
        args.dry_run = True

    models, uid, db, pwd, cfg = connect()
    outdir: Path = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Resolve batch
    if args.batch_id is not None:
        batch_id = int(args.batch_id)
        batch_ids = [batch_id]
    else:
        batch_ids = search(models, db, uid, pwd, "stock.picking.batch", [("name", "ilike", args.name.strip())], limit=5, order="id desc")
        if not batch_ids:
            raise SystemExit(f"No encontré ola por name ilike {args.name!r} en {cfg['db']} ({cfg['url']})")
        batch_id = int(batch_ids[0])

    batch = read(models, db, uid, pwd, "stock.picking.batch", [batch_id], ["id", "name", "state", "picking_type_id", "warehouse_id", "user_id", "write_date"])[0]

    # Confirm wave-field exists
    so_meta = fields_get(models, db, uid, pwd, "sale.order")
    if "nakel_wave_batch_id" not in so_meta:
        raise SystemExit("sale.order no tiene campo nakel_wave_batch_id en este entorno (no se puede usar este método).")

    # Get OV
    so_rows = search_read(
        models,
        db,
        uid,
        pwd,
        "sale.order",
        [("nakel_wave_batch_id", "=", batch_id)],
        fields=["id", "name", "state", "date_order", "company_id"],
        limit=None,
        order="id asc",
    )
    so_ids = [int(r["id"]) for r in so_rows]

    # Resolve OUT picking types (warehouse-aware if possible)
    out_pt_ids: list[int] = []
    pt_wh_id = None
    if batch.get("picking_type_id"):
        pt = read(models, db, uid, pwd, "stock.picking.type", [batch["picking_type_id"][0]], ["warehouse_id"])
        if pt and pt[0].get("warehouse_id"):
            pt_wh_id = pt[0]["warehouse_id"][0]

    pt_dom = [("sequence_code", "=", "OUT")]
    if pt_wh_id:
        pt_dom.append(("warehouse_id", "=", pt_wh_id))
    out_pt_ids = search(models, db, uid, pwd, "stock.picking.type", pt_dom, limit=50)
    if not out_pt_ids:
        out_pt_ids = search(models, db, uid, pwd, "stock.picking.type", [("sequence_code", "=", "OUT")], limit=50)

    # Find OUT pickings
    picking_meta = fields_get(models, db, uid, pwd, "stock.picking")
    p_fields = [f for f in ["id", "name", "state", "sale_id", "origin", "group_id", "picking_type_id", "scheduled_date", "date_done"] if f in picking_meta]

    out_ids = []
    if so_ids and out_pt_ids:
        out_ids = search(models, db, uid, pwd, "stock.picking", [("picking_type_id", "in", out_pt_ids), ("sale_id", "in", so_ids)], limit=5000, order="id asc")
    outs: list[dict[str, Any]] = []
    for part in chunked([int(x) for x in out_ids], 200):
        outs += read(models, db, uid, pwd, "stock.picking", part, p_fields)

    # Export + optional validate
    out_csv = outdir / f"out_validate_wave_{batch_id}_{ts}.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "batch_id",
                "batch_name",
                "so_count",
                "out_id",
                "out_name",
                "out_state",
                "sale_order",
                "origin",
                "picking_type",
                "scheduled_date",
                "date_done",
                "action",
                "result",
            ],
        )
        w.writeheader()

        for o in outs:
            so_name = m2o_name(o.get("sale_id"))
            action = "dry-run"
            result = ""
            if args.apply and o.get("state") not in ("done", "cancel"):
                action = "button_validate"
                try:
                    res = models.execute_kw(
                        db,
                        uid,
                        pwd,
                        "stock.picking",
                        "button_validate",
                        [[int(o["id"])]],
                        {"context": {"skip_backorder": True}},
                    )
                    if isinstance(res, dict) and res.get("res_model"):
                        result = f"wizard:{res.get('res_model')}"
                    else:
                        result = "validated"
                except xmlrpc.client.Fault as e:
                    result = f"fault:{e.faultCode}:{e.faultString[:180]}"

            w.writerow(
                {
                    "batch_id": batch_id,
                    "batch_name": batch.get("name"),
                    "so_count": len(so_ids),
                    "out_id": o.get("id"),
                    "out_name": o.get("name"),
                    "out_state": o.get("state"),
                    "sale_order": so_name,
                    "origin": o.get("origin"),
                    "picking_type": m2o_name(o.get("picking_type_id")),
                    "scheduled_date": o.get("scheduled_date"),
                    "date_done": o.get("date_done"),
                    "action": action,
                    "result": result,
                }
            )

    print("OK")
    print("batch:", batch.get("name"), "id=", batch_id, "state=", batch.get("state"))
    print("ov_count:", len(so_ids))
    print("out_count:", len(outs))
    print("csv:", str(out_csv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
