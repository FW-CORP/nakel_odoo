#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Libro mayor (solo lectura): entradas/salidas en CEN/Existencias para un producto.

Uso:
  python3 nakel_odoo/tools/inventario/libro_mayor_cen_producto_master_dev.py \\
    --default-code 8209.00

  python3 ... --default-code 8209.00 --desde 2026-05-12

Salida: inventario/correcciones/OUT/libro_mayor_cen_<codigo>_<timestamp>.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

import xmlrpc.client

sys.path.insert(0, "/media/klap/raid5/cursor_files")

from config_nakel import ODOO_CONFIG_MASTER_DEV  # noqa: E402

LOC_EXISTENCIAS = 102  # CEN/Existencias


def _out_dir() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "inventario"
        / "correcciones"
        / "OUT"
    )


def _connect():
    cfg = ODOO_CONFIG_MASTER_DEV
    common = xmlrpc.client.ServerProxy(f"{cfg['url']}/xmlrpc/2/common")
    uid = common.authenticate(cfg["db"], cfg["username"], cfg["password"], {})
    if not uid:
        raise RuntimeError("Autenticación Odoo fallida")
    models = xmlrpc.client.ServerProxy(f"{cfg['url']}/xmlrpc/2/object")
    return cfg["db"], uid, cfg["password"], models


def _search_read(models, db, uid, pwd, model, domain, fields, order=None, limit=0):
    kw = {"fields": fields}
    if order:
        kw["order"] = order
    if limit:
        kw["limit"] = limit
    return models.execute_kw(db, uid, pwd, model, "search_read", [domain], kw)


def _tipo_mov(ref: str, loc_from: int, loc_to: int) -> str:
    if "Cantidad de producto actualizada" in ref:
        return "AJUSTE_INVENTARIO"
    if ref.startswith("CEN/STOR"):
        return "RECEPCION_ALMACENAJE"
    if ref.startswith("CEN/INT"):
        return "TRASLADO_A_SUCURSAL"
    if ref.startswith("CEN/PICK"):
        return "PICK_A_SALIDA"
    if loc_to == LOC_EXISTENCIAS and loc_from != LOC_EXISTENCIAS:
        return "ENTRADA_OTRA"
    if loc_from == LOC_EXISTENCIAS:
        return "SALIDA_OTRA"
    return "OTRO"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--default-code", required=True)
    ap.add_argument("--desde", default=None, help="YYYY-MM-DD (opcional)")
    ap.add_argument(
        "--saldo-inicial",
        type=float,
        default=None,
        help="Saldo en Existencias antes del primer movimiento del rango",
    )
    ap.add_argument("--location-id", type=int, default=LOC_EXISTENCIAS)
    args = ap.parse_args()

    db, uid, pwd, models = _connect()
    prods = _search_read(
        models, db, uid, pwd, "product.product",
        [["default_code", "=", args.default_code]],
        ["id", "display_name"],
    )
    if not prods:
        print(f"Producto no encontrado: {args.default_code}", file=sys.stderr)
        return 1
    pid = prods[0]["id"]

    domain = [
        ["product_id", "=", pid],
        ["state", "=", "done"],
        "|",
        ["location_id", "=", args.location_id],
        ["location_dest_id", "=", args.location_id],
    ]
    if args.desde:
        domain.append(["date", ">=", f"{args.desde} 00:00:00"])

    lines = _search_read(
        models, db, uid, pwd, "stock.move.line",
        domain,
        ["id", "date", "reference", "location_id", "location_dest_id", "quantity"],
        order="date asc, id asc",
        limit=0,
    )

    rows = []
    saldo = float(args.saldo_inicial or 0.0)
    entradas = 0.0
    salidas = 0.0

    for ln in lines:
        loc_from = ln["location_id"][0]
        loc_to = ln["location_dest_id"][0]
        qty = float(ln["quantity"])
        ref = ln["reference"] or ""
        tipo = _tipo_mov(ref, loc_from, loc_to)

        delta = 0.0
        sentido = ""
        if loc_to == args.location_id and loc_from != args.location_id:
            delta = qty
            sentido = "ENTRADA"
            entradas += qty
        elif loc_from == args.location_id and loc_to != args.location_id:
            delta = -qty
            sentido = "SALIDA"
            salidas += qty
        else:
            continue

        # Ajuste inventario que SALE de Existencias: en Odoo es corrección; el saldo
        # post-ajuste no es saldo + delta sino el valor contado. Marcar y recalcular
        # saldo en la fila siguiente si es el ajuste Angel 2206.
        saldo += delta
        rows.append({
            "fecha": (ln["date"] or "")[:19].replace("T", " "),
            "tipo": tipo,
            "sentido": sentido,
            "referencia": ref,
            "cantidad": int(qty) if qty == int(qty) else qty,
            "delta": int(delta) if delta == int(delta) else delta,
            "saldo_existencias": int(saldo) if saldo == int(saldo) else round(saldo, 2),
            "ubicacion_origen": ln["location_id"][1],
            "ubicacion_destino": ln["location_dest_id"][1],
        })

    out = _out_dir()
    out.mkdir(parents=True, exist_ok=True)
    cod = args.default_code.replace("/", "_")
    path = out / f"libro_mayor_cen_{cod}_{datetime.now():%Y%m%d_%H%M%S}.csv"
    fields = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=",")
        w.writeheader()
        w.writerows(rows)
        w.writerow({})
        w.writerow({
            "fecha": "RESUMEN",
            "tipo": f"ENTRADAS_TOTAL={int(entradas) if entradas==int(entradas) else entradas}",
            "sentido": f"SALIDAS_TOTAL={int(salidas) if salidas==int(salidas) else salidas}",
            "referencia": f"SALDO_FINAL={rows[-1]['saldo_existencias'] if rows else 0}",
            "cantidad": "",
            "delta": "",
            "saldo_existencias": "",
            "ubicacion_origen": "",
            "ubicacion_destino": "",
        })

    print(path)
    print(
        f"Lineas: {len(rows)} | Entradas: {entradas} | Salidas: {salidas} | "
        f"Saldo final: {rows[-1]['saldo_existencias'] if rows else 0}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
