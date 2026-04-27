#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Read-only: rastrear Orden(es) de Compra (purchase.order) desde una factura de proveedor (account.move).

Uso:
  NAKEL_TARGET=staging_sg_dev1 python3 rastrear_oc_desde_factura.py --move-id 21474 --move-id 97028
"""

from __future__ import annotations

import argparse
import sys
import xmlrpc.client
from dataclasses import dataclass
from typing import Any


sys.path.insert(0, "/media/klap/raid5/cursor_files")

try:
    from config_nakel import ODOO_CONFIG_MASTER_DEV
except Exception as e:  # pragma: no cover
    raise SystemExit(f"No se pudo importar config_nakel / ODOO_CONFIG_MASTER_DEV: {e}")


@dataclass(frozen=True)
class OdooConn:
    url: str
    db: str
    uid: int
    password: str
    models: Any


def connect(cfg: dict) -> OdooConn:
    url = cfg["url"].rstrip("/")
    db = cfg["db"]
    username = cfg["username"]
    password = cfg["password"]
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(db, username, password, {})
    if not uid:
        raise SystemExit(f"Autenticacion Odoo fallida: url={url} db={db} user={username}")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)
    return OdooConn(url=url, db=db, uid=int(uid), password=password, models=models)


def fields_get(c: OdooConn, model: str) -> set[str]:
    meta = c.models.execute_kw(c.db, c.uid, c.password, model, "fields_get", [], {"attributes": ["type"]})
    return set(meta.keys())


def read(c: OdooConn, model: str, ids: list[int], fields: list[str]) -> list[dict[str, Any]]:
    if not ids:
        return []
    return c.models.execute_kw(c.db, c.uid, c.password, model, "read", [ids], {"fields": fields})


def search_read(
    c: OdooConn,
    model: str,
    domain: list,
    *,
    fields: list[str],
    limit: int = 0,
    order: str | None = None,
) -> list[dict[str, Any]]:
    kwargs: dict[str, Any] = {"fields": fields}
    if limit:
        kwargs["limit"] = int(limit)
    if order:
        kwargs["order"] = order
    return c.models.execute_kw(c.db, c.uid, c.password, model, "search_read", [domain], kwargs)


def m2o(v: Any) -> tuple[int, str] | None:
    if not v:
        return None
    if isinstance(v, (list, tuple)) and v:
        return int(v[0]), str(v[1])
    if isinstance(v, int):
        return int(v), ""
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--move-id", action="append", type=int, default=[], help="account.move id (se puede repetir)")
    args = ap.parse_args()
    move_ids = [int(x) for x in (args.move_id or [])]
    if not move_ids:
        raise SystemExit("Falta --move-id")

    cfg = ODOO_CONFIG_MASTER_DEV.copy()
    c = connect(cfg)
    print(f"OK: {c.url} | db={c.db} | uid={c.uid}")

    move_exist = fields_get(c, "account.move")
    line_exist = fields_get(c, "account.move.line")
    pol_exist = fields_get(c, "purchase.order.line")
    po_exist = fields_get(c, "purchase.order")

    move_fields = [f for f in ["id", "name", "ref", "state", "move_type", "invoice_origin", "purchase_id", "partner_id"] if f in move_exist]
    line_fields = [f for f in ["id", "move_id", "purchase_line_id", "name"] if f in line_exist]
    pol_fields = [f for f in ["id", "order_id", "name"] if f in pol_exist]
    po_fields = [f for f in ["id", "name", "state", "partner_id", "date_order", "origin"] if f in po_exist]

    moves = read(c, "account.move", move_ids, move_fields)
    moves_by_id = {m["id"]: m for m in moves}

    for mid in move_ids:
        mv = moves_by_id.get(mid)
        if not mv:
            print(f"\nmove_id={mid}: NO ENCONTRADO")
            continue

        print("\n---")
        print(f"move_id={mid} name={mv.get('name')} ref={mv.get('ref') or '-'} state={mv.get('state')} type={mv.get('move_type')}")
        if "invoice_origin" in mv:
            print(f"invoice_origin={mv.get('invoice_origin') or '-'}")
        if "partner_id" in mv:
            p = m2o(mv.get("partner_id"))
            print(f"proveedor={p[0]}:{p[1]}" if p else "proveedor=-")

        po_ids: set[int] = set()

        # A) campo directo purchase_id (si existe)
        if "purchase_id" in mv:
            po = m2o(mv.get("purchase_id"))
            if po:
                po_ids.add(po[0])

        # B) por lineas -> purchase_line_id -> order_id
        if "purchase_line_id" in line_fields:
            inv_lines = search_read(
                c,
                "account.move.line",
                [("move_id", "=", mid)],
                fields=line_fields,
                limit=0,
                order="id asc",
            )
            pol_ids = [m2o(l.get("purchase_line_id"))[0] for l in inv_lines if m2o(l.get("purchase_line_id"))]
            if pol_ids and "order_id" in pol_fields:
                pol_rows = read(c, "purchase.order.line", sorted(set(pol_ids)), pol_fields)
                for pol in pol_rows:
                    po = m2o(pol.get("order_id"))
                    if po:
                        po_ids.add(po[0])

        if not po_ids:
            print("purchase_orders: - (no se pudo derivar desde purchase_id ni desde lineas)")
            continue

        po_rows = read(c, "purchase.order", sorted(po_ids), po_fields)
        print(f"purchase_orders: {len(po_rows)}")
        for po in po_rows:
            partner = m2o(po.get("partner_id"))
            print(
                f"- po_id={po.get('id')} name={po.get('name')} state={po.get('state')} "
                f"proveedor={partner[0]}:{partner[1] if partner else ''} date_order={po.get('date_order') or '-'} origin={po.get('origin') or '-'}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

