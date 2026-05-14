#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Crea **un** albarán OUT (`stock.picking` tipo entrega del almacén) para una OV
(`sale.order.name`) cuando **no** existe ya un OUT no cancelado, con movimientos
**Salida del almacén → ubicación stock del cliente** por cantidad pendiente
`product_uom_qty - qty_delivered` en líneas almacenables.

Requiere `config_nakel.ODOO_CONFIG_MASTER_DEV` (igual que `out_por_ov_master_dev.py`).

Por defecto **solo dry-run** (imprime lo que haría). Escritura:

  python3 .../crear_out_faltante_por_ov_xmlrpc.py --ov S04368 --apply --i-know-what-im-doing

Riesgos: stock debe estar en **Salida** (PICK validado); si no, `action_assign` puede
fallar o quedar parcial. Revisar en Odoo tras ejecutar.

Importante: **no** incluir `sale_id` en el `create` del picking. Si el picking se crea
ya vinculado a la OV, `action_confirm` en `sale_stock` puede **añadir otra vez**
los movimientos de entrega por líneas de venta y **duplicar** cantidades (mismo
producto dos veces). Tras confirmar/asignar se hace `write` de `sale_id` para
mantener el vínculo con la OV sin disparar esa duplicación en el alta.
"""

from __future__ import annotations

import argparse
import sys
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
        raise SystemExit("Autenticación Odoo fallida.")
    return models, int(uid), cfg["db"], cfg["password"]


def m2o_id(val) -> int | None:
    if not val:
        return None
    if isinstance(val, (list, tuple)) and val:
        return int(val[0])
    return None


def _float_gt(a: float, b: float, eps: float = 1e-6) -> bool:
    return (a - b) > eps


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ov", required=True, help="Número de OV, ej. S04368")
    ap.add_argument("--apply", action="store_true", help="Crear picking y confirmar/asignar")
    ap.add_argument("--i-know-what-im-doing", action="store_true", help="Obligatorio con --apply")
    args = ap.parse_args()

    if args.apply and not args.i_know_what_im_doing:
        raise SystemExit("Con --apply pasá también --i-know-what-im-doing")

    ov = (args.ov or "").strip()
    if not ov:
        raise SystemExit("Pasá --ov")

    models, uid, db, pwd = connect()

    meta_sol = models.execute_kw(db, uid, pwd, "sale.order.line", "fields_get", [], {"attributes": ["type"]})
    sol_fields = ["order_id", "product_id", "product_uom", "product_uom_qty", "qty_delivered", "display_name", "name"]
    if "is_storable" in meta_sol:
        sol_fields.append("is_storable")

    so_ids = models.execute_kw(db, uid, pwd, "sale.order", "search", [[("name", "=", ov)]], {"limit": 2})
    if not so_ids:
        raise SystemExit(f"No se encontró sale.order con name={ov!r}")
    if len(so_ids) > 1:
        raise SystemExit(f"Varias OV con name={ov!r}: ids={so_ids}")
    so_id = so_ids[0]

    so = models.execute_kw(
        db,
        uid,
        pwd,
        "sale.order",
        "read",
        [so_id],
        {"fields": ["name", "state", "warehouse_id", "partner_shipping_id", "procurement_group_id", "company_id"]},
    )[0]
    if so.get("state") != "sale":
        raise SystemExit(f"OV {ov} state={so.get('state')!r}; solo se crea OUT en estado 'sale'.")

    out_dom = [
        ("sale_id", "=", so_id),
        ("state", "!=", "cancel"),
        "|",
        ("picking_type_id.sequence_code", "=", "OUT"),
        ("name", "ilike", "CEN/OUT/%"),
    ]
    existing = models.execute_kw(db, uid, pwd, "stock.picking", "search", [out_dom], {"limit": 1})
    if existing:
        raise SystemExit(f"Ya existe OUT no cancelado para {ov}: picking ids={existing}")

    wh_id = m2o_id(so.get("warehouse_id"))
    if not wh_id:
        raise SystemExit("La OV no tiene warehouse_id.")
    wh = models.execute_kw(
        db,
        uid,
        pwd,
        "stock.warehouse",
        "read",
        [[wh_id]],
        {"fields": ["out_type_id", "wh_output_stock_loc_id", "name"]},
    )[0]
    out_type_id = m2o_id(wh.get("out_type_id"))
    loc_out_id = m2o_id(wh.get("wh_output_stock_loc_id"))
    if not out_type_id or not loc_out_id:
        raise SystemExit("Almacén sin out_type_id o wh_output_stock_loc_id.")

    partner_id = m2o_id(so.get("partner_shipping_id"))
    if not partner_id:
        raise SystemExit("OV sin partner_shipping_id.")
    pr = models.execute_kw(
        db,
        uid,
        pwd,
        "res.partner",
        "read",
        [[partner_id]],
        {"fields": ["property_stock_customer"]},
    )[0]
    loc_cust_id = m2o_id(pr.get("property_stock_customer"))
    if not loc_cust_id:
        raise SystemExit("Partner sin property_stock_customer.")

    company_id = m2o_id(so.get("company_id"))
    group_id = m2o_id(so.get("procurement_group_id"))

    line_ids = models.execute_kw(
        db, uid, pwd, "sale.order.line", "search", [[("order_id", "=", so_id)]], {"limit": 500, "order": "id asc"}
    )
    lines = (
        models.execute_kw(db, uid, pwd, "sale.order.line", "read", [line_ids], {"fields": sol_fields})
        if line_ids
        else []
    )

    move_cmds: list[tuple] = []
    for ln in lines:
        lid = int(ln["id"])
        pid = m2o_id(ln.get("product_id"))
        if not pid:
            continue
        storable = bool(ln.get("is_storable")) if "is_storable" in ln else None
        if storable is None:
            prd = models.execute_kw(db, uid, pwd, "product.product", "read", [[pid]], {"fields": ["is_storable"]})
            storable = bool(prd[0].get("is_storable")) if prd else False
        if not storable:
            continue
        pqty = float(ln.get("product_uom_qty") or 0.0)
        qdel = float(ln.get("qty_delivered") or 0.0)
        need = pqty - qdel
        if not _float_gt(need, 0.0):
            continue
        uom_id = m2o_id(ln.get("product_uom"))
        if not uom_id:
            raise SystemExit(f"Línea {lid} sin product_uom.")
        disp = (ln.get("display_name") or ln.get("name") or f"Line {lid}")[:200]
        move_vals: dict[str, Any] = {
            "name": disp,
            "product_id": pid,
            "product_uom": uom_id,
            "product_uom_qty": need,
            "location_id": loc_out_id,
            "location_dest_id": loc_cust_id,
            "sale_line_id": lid,
            "company_id": company_id,
            "picking_type_id": out_type_id,
            "origin": ov,
            "procure_method": "make_to_stock",
        }
        if group_id:
            move_vals["group_id"] = group_id
        move_cmds.append((0, 0, move_vals))

    if not move_cmds:
        raise SystemExit("No hay líneas almacenables con cantidad pendiente; no se crea OUT.")

    picking_vals: dict[str, Any] = {
        "picking_type_id": out_type_id,
        "partner_id": partner_id,
        "location_id": loc_out_id,
        "location_dest_id": loc_cust_id,
        "origin": ov,
        # NO poner sale_id aquí: ver docstring (duplicación en action_confirm).
        "company_id": company_id,
        "move_ids": move_cmds,
    }
    if group_id:
        picking_vals["group_id"] = group_id

    print(f"OV {ov} (sale.order id={so_id}): crear picking OUT con {len(move_cmds)} movimiento(s).")
    print(f"  locations: {loc_out_id} -> {loc_cust_id}  type={out_type_id}")

    if not args.apply:
        print("Dry-run: no se escribió nada. Usá --apply --i-know-what-im-doing para crear.")
        return 0

    pid_new = models.execute_kw(db, uid, pwd, "stock.picking", "create", [picking_vals])
    print(f"Creado stock.picking id={pid_new}")

    models.execute_kw(db, uid, pwd, "stock.picking", "action_confirm", [[pid_new]])
    print("action_confirm OK.")

    try:
        models.execute_kw(db, uid, pwd, "stock.picking", "action_assign", [[pid_new]])
        print("action_assign OK.")
    except xmlrpc.client.Fault as e:
        print(f"action_assign Fault (revisar stock en Salida): {e.faultString[:500]}")

    models.execute_kw(db, uid, pwd, "stock.picking", "write", [[pid_new], {"sale_id": so_id}])
    print("write sale_id en picking (post-confirm) OK.")

    pick = models.execute_kw(
        db, uid, pwd, "stock.picking", "read", [[pid_new]], {"fields": ["name", "state", "scheduled_date"]}
    )[0]
    print(f"Resultado: {pick.get('name')} state={pick.get('state')}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
