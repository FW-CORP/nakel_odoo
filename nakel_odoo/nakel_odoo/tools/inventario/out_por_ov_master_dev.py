#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dry-run / apply: analizar y (opcionalmente) validar OUT (Customer Delivery) por lista de OV (sale.order.name)
en master_dev, sin depender de la ola/WAVE.

Objetivo:
- Dado un set de OV tipo S03111, S03260, etc.
- Encontrar la OV en Odoo (sale.order)
- Buscar sus pickings OUT (stock.picking) por sale_id + picking_type.sequence_code='OUT'
- Exportar CSV con OUTs y estados

Uso:
  python3 nakel_odoo/tools/inventario/out_por_ov_master_dev.py --dry-run --ov S03111 --ov S03260
  python3 nakel_odoo/tools/inventario/out_por_ov_master_dev.py --dry-run --ovs "S03111,S03260,S03262"
  python3 nakel_odoo/tools/inventario/out_por_ov_master_dev.py --dry-run --archivo-ov /ruta/ovs.txt

Salida:
  /media/klap/raid5/cursor_files/backups/out_por_ov_master_dev_<ts>.csv

Nota:
- En --apply, si button_validate devuelve wizard (dict con res_model), se registra y se saltea.
- No asume lotes/series ni confirma wizards automáticamente.
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


def search(models, db, uid, pwd, model: str, domain: list, *, limit: int | None = None, order: str | None = None) -> list[int]:
    kwargs: dict[str, Any] = {}
    if limit is not None:
        kwargs["limit"] = int(limit)
    if order:
        kwargs["order"] = order
    return models.execute_kw(db, uid, pwd, model, "search", [domain], kwargs)


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


def m2o_name(val) -> str:
    if not val:
        return ""
    if isinstance(val, (list, tuple)) and len(val) >= 2:
        return str(val[1] or "")
    return ""


def parse_ov_list(args) -> list[str]:
    names: list[str] = []
    for o in args.ov or []:
        o = (o or "").strip()
        if o:
            names.append(o)
    if (args.ovs or "").strip():
        names.extend([x.strip() for x in args.ovs.split(",") if x.strip()])
    if (args.archivo_ov or "").strip():
        p = Path(args.archivo_ov)
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            names.append(line)
    # unique preserve order
    seen = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            out.append(n)
            seen.add(n)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ov", action="append", default=[], help="OV (sale.order.name) repetible, ej: --ov S03111")
    ap.add_argument("--ovs", default="", help='CSV de OVs, ej: "S03111,S03260"')
    ap.add_argument("--archivo-ov", default="", help="Archivo: una OV por línea")
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

    ov_names = parse_ov_list(args)
    if not ov_names:
        raise SystemExit("Pasá OVs con --ov / --ovs / --archivo-ov")

    models, uid, db, pwd, cfg = connect()
    outdir: Path = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_csv = outdir / f"out_por_ov_master_dev_{ts}.csv"

    # Resolve OUT picking types (all warehouses)
    out_pt_ids = search(models, db, uid, pwd, "stock.picking.type", [("sequence_code", "=", "OUT")], limit=200)
    if not out_pt_ids:
        raise SystemExit("No encontré stock.picking.type con sequence_code='OUT'.")

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "ov",
                "sale_order_id",
                "sale_order_state",
                "out_id",
                "out_name",
                "out_state",
                "origin",
                "scheduled_date",
                "date_done",
                "action",
                "result",
            ],
        )
        w.writeheader()

        for ov in ov_names:
            so = search_read(
                models,
                db,
                uid,
                pwd,
                "sale.order",
                [("name", "=", ov)],
                fields=["id", "name", "state"],
                limit=2,
                order="id desc",
            )
            if not so:
                w.writerow(
                    {
                        "ov": ov,
                        "sale_order_id": "",
                        "sale_order_state": "",
                        "out_id": "",
                        "out_name": "",
                        "out_state": "",
                        "origin": "",
                        "scheduled_date": "",
                        "date_done": "",
                        "action": "dry-run",
                        "result": "sale.order_not_found",
                    }
                )
                continue
            if len(so) > 1:
                # Ambiguo (no debería pasar)
                w.writerow(
                    {
                        "ov": ov,
                        "sale_order_id": "",
                        "sale_order_state": "",
                        "out_id": "",
                        "out_name": "",
                        "out_state": "",
                        "origin": "",
                        "scheduled_date": "",
                        "date_done": "",
                        "action": "dry-run",
                        "result": f"sale.order_ambiguous({[r['id'] for r in so]})",
                    }
                )
                continue

            so_id = int(so[0]["id"])
            so_state = str(so[0].get("state") or "")

            out_ids = search(
                models,
                db,
                uid,
                pwd,
                "stock.picking",
                [("sale_id", "=", so_id), ("picking_type_id", "in", out_pt_ids)],
                limit=5000,
                order="id asc",
            )

            if not out_ids:
                w.writerow(
                    {
                        "ov": ov,
                        "sale_order_id": so_id,
                        "sale_order_state": so_state,
                        "out_id": "",
                        "out_name": "",
                        "out_state": "",
                        "origin": "",
                        "scheduled_date": "",
                        "date_done": "",
                        "action": "dry-run",
                        "result": "no_out_pickings_found",
                    }
                )
                continue

            out_rows = []
            for part in chunked([int(x) for x in out_ids], 200):
                out_rows += models.execute_kw(
                    db,
                    uid,
                    pwd,
                    "stock.picking",
                    "read",
                    [part],
                    {
                        "fields": [
                            "id",
                            "name",
                            "state",
                            "origin",
                            "scheduled_date",
                            "date_done",
                        ]
                    },
                )

            for out in out_rows:
                action = "dry-run"
                result = ""
                if args.apply and out.get("state") not in ("done", "cancel"):
                    action = "button_validate"
                    try:
                        res = models.execute_kw(
                            db,
                            uid,
                            pwd,
                            "stock.picking",
                            "button_validate",
                            [[int(out["id"])]],
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
                        "ov": ov,
                        "sale_order_id": so_id,
                        "sale_order_state": so_state,
                        "out_id": out.get("id"),
                        "out_name": out.get("name"),
                        "out_state": out.get("state"),
                        "origin": out.get("origin"),
                        "scheduled_date": out.get("scheduled_date"),
                        "date_done": out.get("date_done"),
                        "action": action,
                        "result": result,
                    }
                )

    print("OK")
    print("ov_count:", len(ov_names))
    print("csv:", str(out_csv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

