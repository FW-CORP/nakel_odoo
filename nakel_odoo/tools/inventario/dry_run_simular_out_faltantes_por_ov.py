#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Solo lectura (dry-run): simula qué implicaría **generar** albaranes OUT faltantes
por lista de OV (`sale.order.name`), sin crear ni modificar nada en Odoo.

Para cada OV:
- Detecta si ya hay `stock.picking` tipo OUT (no cancelados).
- Si no hay OUT: lista líneas de venta con producto almacenable y cantidad
  pendiente de entrega al cliente (`product_uom_qty - qty_delivered`), como
  movimientos que un OUT manual tendría (origen típico: Salida del almacén →
  ubicación stock del cliente).

No ejecuta `create`, `write`, `button_validate` ni métodos de abastecimiento.

Uso:
  cd /media/klap/raid5/cursor_files/nakel
  python3 nakel_odoo/tools/inventario/dry_run_simular_out_faltantes_por_ov.py \\
    --archivo-ov nakel_odoo/docs/inventario/incidencias/logistica/wave143/lista_ov_wave143.txt

  python3 nakel_odoo/tools/inventario/dry_run_simular_out_faltantes_por_ov.py --ov S04297 --ov S04370

Requiere `config_nakel.ODOO_CONFIG_MASTER_DEV` (misma convención que `out_por_ov_master_dev.py`).

Salida: CSV en backups/ con prefijo `dry_run_out_faltantes_sim_`.
"""

from __future__ import annotations

import argparse
import csv
import sys
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
    return models, int(uid), cfg["db"], cfg["password"], cfg


def search(models, db, uid, pwd, model: str, domain: list, **kwargs) -> list[int]:
    return models.execute_kw(db, uid, pwd, model, "search", [domain], kwargs)


def search_read(
    models, db, uid, pwd, model: str, domain: list, *, fields: list[str], **kwargs
) -> list[dict[str, Any]]:
    kw = {"fields": fields}
    kw.update(kwargs)
    return models.execute_kw(db, uid, pwd, model, "search_read", [domain], kw)


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


def parse_ov_names(args: argparse.Namespace) -> list[str]:
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
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            out.append(n)
            seen.add(n)
    return out


def _float_gt(a: float, b: float, eps: float = 1e-6) -> bool:
    return (a - b) > eps


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ov", action="append", default=[], help="OV repetible (sale.order.name)")
    ap.add_argument("--ovs", default="", help="Lista CSV de OVs")
    ap.add_argument(
        "--archivo-ov",
        default="",
        help="Archivo una OV por línea (default vacío: hay que pasar --ov/--ovs/--archivo-ov)",
    )
    ap.add_argument(
        "--outdir",
        type=Path,
        default=Path("/media/klap/raid5/cursor_files/backups"),
        help="Directorio del CSV de salida",
    )
    args = ap.parse_args()

    ov_names = parse_ov_names(args)
    if not ov_names:
        raise SystemExit("Pasá OVs con --ov / --ovs / --archivo-ov")

    models, uid, db, pwd, _cfg = connect()

    meta_sol = models.execute_kw(db, uid, pwd, "sale.order.line", "fields_get", [], {"attributes": ["type"]})
    sol_fields = ["order_id", "product_id", "product_uom", "product_uom_qty", "qty_delivered", "display_name"]
    if "is_storable" in meta_sol:
        sol_fields.append("is_storable")

    rows_out: list[dict[str, Any]] = []
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    for ov in ov_names:
        so_ids = search(models, db, uid, pwd, "sale.order", [("name", "=", ov)], limit=2)
        if not so_ids:
            rows_out.append(
                {
                    "ov": ov,
                    "so_id": "",
                    "so_state": "NO_ENCONTRADA",
                    "simular_out": "no",
                    "motivo": "OV no existe en la base",
                    "outs_existentes": "",
                    "lineas_out_simuladas": "0",
                    "qty_total_simulada": "0",
                    "wh_salida": "",
                    "ubic_cliente": "",
                    "detalle_lineas_sim": "",
                }
            )
            continue
        if len(so_ids) > 1:
            rows_out.append(
                {
                    "ov": ov,
                    "so_id": ",".join(str(x) for x in so_ids),
                    "so_state": "DUPLICADO_NAME",
                    "simular_out": "no",
                    "motivo": "Más de un sale.order con mismo name",
                    "outs_existentes": "",
                    "lineas_out_simuladas": "0",
                    "qty_total_simulada": "0",
                    "wh_salida": "",
                    "ubic_cliente": "",
                    "detalle_lineas_sim": "",
                }
            )
            continue

        so_id = so_ids[0]
        so = search_read(
            models,
            db,
            uid,
            pwd,
            "sale.order",
            [("id", "=", so_id)],
            fields=["id", "name", "state", "warehouse_id", "partner_shipping_id", "company_id"],
            limit=1,
        )[0]
        state = so.get("state") or ""

        out_dom = [
            ("sale_id", "=", so_id),
            ("state", "!=", "cancel"),
            "|",
            ("picking_type_id.sequence_code", "=", "OUT"),
            ("name", "ilike", "CEN/OUT/%"),
        ]
        out_pick_ids = search(models, db, uid, pwd, "stock.picking", out_dom, limit=20, order="id asc")
        outs_desc = ""
        if out_pick_ids:
            outs = search_read(
                models,
                db,
                uid,
                pwd,
                "stock.picking",
                [("id", "in", out_pick_ids)],
                fields=["id", "name", "state"],
                limit=20,
            )
            outs_desc = "; ".join(f"{r.get('name')}({r.get('state')})" for r in outs)

        wh_id = m2o_id(so.get("warehouse_id"))
        wh_salida = ""
        if wh_id:
            wh_rows = search_read(
                models,
                db,
                uid,
                pwd,
                "stock.warehouse",
                [("id", "=", wh_id)],
                fields=["name", "wh_output_stock_loc_id", "out_type_id", "delivery_steps"],
                limit=1,
            )
            if wh_rows:
                w = wh_rows[0]
                wh_salida = m2o_name(w.get("wh_output_stock_loc_id")) or ""
                _ = w.get("delivery_steps") or ""

        partner_id = m2o_id(so.get("partner_shipping_id"))
        ubic_cliente = ""
        if partner_id:
            pr = search_read(
                models,
                db,
                uid,
                pwd,
                "res.partner",
                [("id", "=", partner_id)],
                fields=["property_stock_customer"],
                limit=1,
            )
            if pr:
                ubic_cliente = m2o_name(pr[0].get("property_stock_customer")) or ""

        if out_pick_ids:
            rows_out.append(
                {
                    "ov": ov,
                    "so_id": str(so_id),
                    "so_state": state,
                    "simular_out": "no",
                    "motivo": "Ya hay al menos un picking OUT no cancelado",
                    "outs_existentes": outs_desc,
                    "lineas_out_simuladas": "0",
                    "qty_total_simulada": "0",
                    "wh_salida": wh_salida,
                    "ubic_cliente": ubic_cliente,
                    "detalle_lineas_sim": "",
                }
            )
            continue

        if state != "sale":
            rows_out.append(
                {
                    "ov": ov,
                    "so_id": str(so_id),
                    "so_state": state,
                    "simular_out": "no",
                    "motivo": "OV no está en estado sale (no simulamos create)",
                    "outs_existentes": "",
                    "lineas_out_simuladas": "0",
                    "qty_total_simulada": "0",
                    "wh_salida": wh_salida,
                    "ubic_cliente": ubic_cliente,
                    "detalle_lineas_sim": "",
                }
            )
            continue

        line_ids = search(models, db, uid, pwd, "sale.order.line", [("order_id", "=", so_id)], limit=500, order="id asc")
        lines = (
            search_read(models, db, uid, pwd, "sale.order.line", [("id", "in", line_ids)], fields=sol_fields, limit=500)
            if line_ids
            else []
        )

        sim_lines: list[str] = []
        qty_total = 0.0
        for ln in lines:
            pid = m2o_id(ln.get("product_id"))
            if not pid:
                continue
            storable = True
            if "is_storable" in ln:
                storable = bool(ln.get("is_storable"))
            else:
                prods = search_read(
                    models, db, uid, pwd, "product.product", [("id", "=", pid)], fields=["is_storable"], limit=1
                )
                if prods:
                    storable = bool(prods[0].get("is_storable"))

            if not storable:
                continue

            pqty = float(ln.get("product_uom_qty") or 0.0)
            qdel = float(ln.get("qty_delivered") or 0.0)
            need = pqty - qdel
            if not _float_gt(need, 0.0):
                continue

            uom_name = m2o_name(ln.get("product_uom"))
            disp = (ln.get("display_name") or ln.get("name") or "")[:80]
            sim_lines.append(f"{need:g} {uom_name} | {disp}")
            qty_total += need

        if not sim_lines:
            rows_out.append(
                {
                    "ov": ov,
                    "so_id": str(so_id),
                    "so_state": state,
                    "simular_out": "ambiguo",
                    "motivo": "Sin OUT pero sin líneas almacenables con cantidad pendiente (revisar líneas/servicios)",
                    "outs_existentes": "",
                    "lineas_out_simuladas": "0",
                    "qty_total_simulada": "0",
                    "wh_salida": wh_salida,
                    "ubic_cliente": ubic_cliente,
                    "detalle_lineas_sim": "",
                }
            )
            continue

        detalle = " | ".join(sim_lines[:12])
        if len(sim_lines) > 12:
            detalle += f" | …(+{len(sim_lines) - 12} líneas)"

        rows_out.append(
            {
                "ov": ov,
                "so_id": str(so_id),
                "so_state": state,
                "simular_out": "si",
                "motivo": (
                    "Simulación: 1 picking OUT con movimientos Salida→Cliente por líneas listadas; "
                    "requiere stock en ubicación Salida del almacén tras PICK; NO ejecutado."
                ),
                "outs_existentes": "",
                "lineas_out_simuladas": str(len(sim_lines)),
                "qty_total_simulada": str(round(qty_total, 6)).rstrip("0").rstrip("."),
                "wh_salida": wh_salida,
                "ubic_cliente": ubic_cliente,
                "detalle_lineas_sim": detalle,
            }
        )

    args.outdir.mkdir(parents=True, exist_ok=True)
    csv_path = args.outdir / f"dry_run_out_faltantes_sim_{ts}.csv"
    fieldnames = [
        "ov",
        "so_id",
        "so_state",
        "simular_out",
        "motivo",
        "outs_existentes",
        "lineas_out_simuladas",
        "qty_total_simulada",
        "wh_salida",
        "ubic_cliente",
        "detalle_lineas_sim",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows_out:
            row = {k: r.get(k, "") for k in fieldnames}
            w.writerow(row)

    print(f"OK dry-run: {len(rows_out)} OV procesadas. CSV: {csv_path}")
    for r in rows_out:
        flag = r.get("simular_out", "")
        print(f"  {r.get('ov')}: simular_out={flag}  {r.get('motivo', '')[:100]}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
