#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Diagnóstico XML-RPC contra Odoo 18 para validar:
stock.picking.batch -> pickings -> sale_line_id -> invoice_lines -> account.move

Uso:
  python3 analizar_odoo18_api.py dev --batch-id 45
  python3 analizar_odoo18_api.py dev --batch-name WAVE/00045
  python3 analizar_odoo18_api.py dev --batch-id 45 --limit-pickings 50

Credenciales:
  Se leen desde /media/klap/raid5/cursor_files/nakel/.env (o variables de entorno ya exportadas)
"""

from __future__ import annotations

import argparse
import os
import sys
import xmlrpc.client


ENV_FILE_DEFAULT = "/media/klap/raid5/cursor_files/nakel/.env"


def load_env_file(path: str) -> None:
    """Carga KEY=VALUE simples desde un .env (sin depender de python-dotenv)."""
    if not path or not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            # No pisar si ya existe exportado
            os.environ.setdefault(k, v)


def cfg(prefix: str) -> dict:
    url = os.environ.get(f"{prefix}_URL", "").strip()
    db = os.environ.get(f"{prefix}_DB", "").strip()
    username = os.environ.get(f"{prefix}_USERNAME", "").strip()
    password = os.environ.get(f"{prefix}_PASSWORD", "").strip()
    missing = [k for k, v in {"URL": url, "DB": db, "USERNAME": username, "PASSWORD": password}.items() if not v]
    if missing:
        raise SystemExit(f"Faltan variables {prefix}_...: {', '.join(missing)}")
    return {"url": url, "db": db, "username": username, "password": password}


def xmlrpc_login(conf: dict):
    common = xmlrpc.client.ServerProxy(f"{conf['url'].rstrip('/')}/xmlrpc/2/common")
    uid = common.authenticate(conf["db"], conf["username"], conf["password"], {})
    if not uid:
        raise SystemExit("No autenticó (credenciales inválidas o DB incorrecta).")
    models = xmlrpc.client.ServerProxy(f"{conf['url'].rstrip('/')}/xmlrpc/2/object")
    return uid, models


def exec_kw(models, db, uid, pwd, model, method, args=None, kwargs=None):
    return models.execute_kw(db, uid, pwd, model, method, args or [], kwargs or {})


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target", choices=["dev", "prod"], help="dev=dev.nakel.net.ar, prod=nakel.net.ar (según .env)")
    ap.add_argument("--env-file", default=ENV_FILE_DEFAULT, help="Ruta al .env con credenciales")
    ap.add_argument("--batch-id", type=int, default=None, help="ID de stock.picking.batch")
    ap.add_argument("--batch-name", default=None, help="Nombre del batch (ej WAVE/00045)")
    ap.add_argument("--sale-name", default=None, help="Nombre de SO (ej S02152) para ubicar pickings y su batch")
    ap.add_argument("--picking-name", default=None, help="Nombre de picking (ej CEN/PICK/00878) para ubicar su batch")
    ap.add_argument("--limit-pickings", type=int, default=200)
    args = ap.parse_args(argv)

    load_env_file(args.env_file)

    prefix = "ODOO_MASTER_DEV" if args.target == "dev" else "ODOO_MASTER18"
    conf = cfg(prefix)

    uid, models = xmlrpc_login(conf)
    db = conf["db"]
    pwd = conf["password"]

    batch_id = args.batch_id
    if not batch_id:
        if args.batch_name:
            ids = exec_kw(models, db, uid, pwd, "stock.picking.batch", "search", [[("name", "=", args.batch_name)]], {"limit": 1})
            if not ids:
                raise SystemExit(f"No se encontró batch con name={args.batch_name!r}")
            batch_id = ids[0]
        elif args.picking_name:
            pids = exec_kw(models, db, uid, pwd, "stock.picking", "search", [[("name", "=", args.picking_name)]], {"limit": 1})
            if not pids:
                raise SystemExit(f"No se encontró picking con name={args.picking_name!r}")
            pick_id = pids[0]
            bids = exec_kw(models, db, uid, pwd, "stock.picking.batch", "search", [[("picking_ids", "in", [pick_id])]], {"limit": 1})
            if not bids:
                raise SystemExit(f"No se encontró batch que contenga picking {args.picking_name!r}")
            batch_id = bids[0]
        elif args.sale_name:
            # Ubicar pickings por origin = SO o por sale_id (si existe relación)
            so_ids = exec_kw(models, db, uid, pwd, "sale.order", "search", [[("name", "=", args.sale_name)]], {"limit": 1})
            so_id = so_ids[0] if so_ids else None
            domain = [("|", ("origin", "=", args.sale_name), ("sale_id", "=", so_id or 0))]
            pids = exec_kw(models, db, uid, pwd, "stock.picking", "search", [domain], {"limit": 50})
            if not pids:
                raise SystemExit(f"No se encontraron pickings para SO {args.sale_name!r} (origin/sale_id).")
            bids = exec_kw(models, db, uid, pwd, "stock.picking.batch", "search", [[("picking_ids", "in", pids)]], {"limit": 1})
            if not bids:
                raise SystemExit(f"No se encontró batch para la SO {args.sale_name!r} (pickings: {len(pids)}).")
            batch_id = bids[0]
        else:
            raise SystemExit("Indicar --batch-id, --batch-name, --picking-name o --sale-name")

    batch = exec_kw(
        models,
        db,
        uid,
        pwd,
        "stock.picking.batch",
        "read",
        [[batch_id]],
        {"fields": ["id", "name", "picking_ids"]},
    )[0]

    print(f"BATCH {batch['id']}: {batch['name']}")
    picking_ids = batch.get("picking_ids") or []
    picking_ids = picking_ids[: args.limit_pickings]
    print(f"Pickings: {len(picking_ids)} (limit {args.limit_pickings})")

    if not picking_ids:
        return 0

    pickings = exec_kw(
        models, db, uid, pwd, "stock.picking", "read", [picking_ids],
        {"fields": ["id", "name", "origin", "sale_id", "move_ids"]},
    )

    # Traer moves y sale_line_id
    move_ids = []
    for p in pickings:
        move_ids.extend(p.get("move_ids") or [])
    move_ids = list(dict.fromkeys(move_ids))

    moves = exec_kw(
        models, db, uid, pwd, "stock.move", "read", [move_ids],
        {"fields": ["id", "picking_id", "sale_line_id"]},
    ) if move_ids else []

    sale_line_ids = [m["sale_line_id"][0] for m in moves if m.get("sale_line_id")]
    sale_line_ids = list(dict.fromkeys(sale_line_ids))

    # Desde SOL -> invoice_lines -> move_id
    invoice_ids_by_sale_line = {}
    if sale_line_ids:
        sol = exec_kw(
            models, db, uid, pwd, "sale.order.line", "read", [sale_line_ids],
            {"fields": ["id", "order_id", "invoice_lines"]},
        )
        inv_line_ids = []
        for l in sol:
            inv_line_ids.extend(l.get("invoice_lines") or [])
        inv_line_ids = list(dict.fromkeys(inv_line_ids))

        inv_lines = exec_kw(
            models, db, uid, pwd, "account.move.line", "read", [inv_line_ids],
            {"fields": ["id", "move_id", "sale_line_ids"]},
        ) if inv_line_ids else []

        for il in inv_lines:
            move = il.get("move_id")
            if not move:
                continue
            inv_id = move[0]
            for sl in il.get("sale_line_ids") or []:
                invoice_ids_by_sale_line.setdefault(sl, set()).add(inv_id)

    # Leer invoices detectadas
    all_invoice_ids = sorted({inv for s in invoice_ids_by_sale_line.values() for inv in s})
    invoices = exec_kw(
        models, db, uid, pwd, "account.move", "read", [all_invoice_ids],
        {"fields": ["id", "name", "move_type", "state", "amount_total", "currency_id", "invoice_origin"]},
    ) if all_invoice_ids else []
    inv_by_id = {i["id"]: i for i in invoices}

    # Reporte por picking
    sale_by_id_cache = {}
    for p in pickings:
        p_sale = p.get("sale_id")
        sale_name = ""
        if p_sale:
            sale_id = p_sale[0]
            if sale_id not in sale_by_id_cache:
                so = exec_kw(models, db, uid, pwd, "sale.order", "read", [[sale_id]], {"fields": ["id", "name"]})[0]
                sale_by_id_cache[sale_id] = so["name"]
            sale_name = sale_by_id_cache[sale_id]

        # moves de este picking
        p_move_ids = [m["id"] for m in moves if m.get("picking_id") and m["picking_id"][0] == p["id"]]
        p_sale_line_ids = [m["sale_line_id"][0] for m in moves if m["id"] in p_move_ids and m.get("sale_line_id")]
        p_sale_line_ids = list(dict.fromkeys(p_sale_line_ids))

        p_invoice_ids = sorted({inv for sl in p_sale_line_ids for inv in invoice_ids_by_sale_line.get(sl, set())})

        print("\n---")
        print(f"PICK {p['id']}: {p['name']} | origin={p.get('origin')!r} | sale={sale_name or '-'}")
        print(f"sale_line_ids: {len(p_sale_line_ids)} | invoices via sale_line: {len(p_invoice_ids)}")
        for inv_id in p_invoice_ids[:50]:
            inv = inv_by_id.get(inv_id, {})
            print(f"  INV {inv_id}: {inv.get('name')} | {inv.get('state')} | {inv.get('move_type')} | {inv.get('amount_total')} | origin={inv.get('invoice_origin')!r}")

    print("\nOK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

