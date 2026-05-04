#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera Promo Ferrero Abril.xls a partir de Promo Ferrero Marzo.xls.

Estructura marzo (Hoja1):
  Fila 2 (0-based): Codigo Cliente | Razón Social | Codigo | Descripcion | Ctd. Vendida
  Desde fila 3: una fila por (comprador, promo) con cantidades de marzo.

Abril:
  - **Comprador** (Codigo Cliente, Razón Social): se copian igual que marzo.
  - **Promo** (Codigo, Descripcion): se reemplazan según acuerdos accionados desde 16/04/2026
    (mapeo MARZO_TO_ABRIL); lo no mapeado conserva texto/código de marzo.
  - **Ctd. Vendida**: 0 en plantilla; para **ventas reales de abril** desde Odoo usar
    `rellenar_promo_cantidades_odoo_master_dev.py` (master_dev).

Hoja extra **Accionados_16abr2026**: misma referencia que el informe VENTAS/STOCK abril.

Uso:
  cd reportes-ferrero && ./.venv/bin/python generar_promo_ferrero_abril.py
"""

from __future__ import annotations

import argparse
import os
import re
from typing import Any

import xlrd
import xlwt

DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(DIR, "OUT")
SRC_DEFAULT = os.path.join(DIR, "Promo Ferrero Marzo.xls")
DST_DEFAULT = os.path.join(OUT_DIR, "Promo Ferrero Abril.xls")

# Referencia comercial abril (dinámica + tope cajas NAKEL S.A.) — misma lista que generar_ferrero_ventas_stock_abril
ACCIONADOS = [
    ("Kinder Maxi 10% descuento", 14),
    ("Kinder Chocolate T4 10% descuento", 6),
    ("Nutella B-Ready 20% descuento", 161),
    ("Nutella 140 15% descuento", 47),
    ("Nutella 350 15% descuento", 16),
    ("Rocher T24 15% descuento", 31),
    ("Rocher T3 15% descuento", 48),
    (
        "Tic Tac Chico (3x2; 1 si o si Citrus Mix) o los 3 con 33% dto., siempre 1 citrus mix",
        15,
    ),
]

# (codigo_marzo, descripcion_marzo_normalizada) -> (codigo_abril, descripcion_abril)
# Códigos abril nuevos (2.6x) solo donde el producto/pack cambia respecto al texto marzo.
MARZO_TO_ABRIL: dict[tuple[float, str], tuple[float, str]] = {
    (2.44, "PROMO KINDER MAXI (10% OFF)"): (
        2.44,
        "PROMO KINDER MAXI (10% OFF)",
    ),
    (2.4, "PROMO HUEVO KINDER (8.33% OFF)"): (
        2.4,
        "PROMO HUEVO KINDER (8.33% OFF)",
    ),
    (2.48, "PROMO ROCHER T8 (15% OFF)"): (
        2.6,
        "PROMO ROCHER T24 (15% OFF)",
    ),
    # T12 no está en accionados; se alinea a línea Rocher T24 abril (revisar con Ferrero si hace falta T3).
    (2.47, "PROMO ROCHER T12 (20% OFF)"): (
        2.6,
        "PROMO ROCHER T24 (15% OFF)",
    ),
    (2.53, "PROMO KINDER JOY (10% OFF)"): (
        2.53,
        "PROMO KINDER JOY (10% OFF)",
    ),
    (2.57, "PROMO RAFAELLO T9 (15% OFF)"): (
        2.57,
        "PROMO RAFAELLO T9 (15% OFF)",
    ),
    (2.43, "PROMO KINDER BUENO WHITE(15%OFF)"): (
        2.43,
        "PROMO KINDER BUENO WHITE (15% OFF)",
    ),
    (2.54, "PROMO KINDER BUENO (15% OFF)"): (
        2.54,
        "PROMO KINDER BUENO (15% OFF)",
    ),
    (2.5, "PROMO NUTELLA X140 (15% OFF)"): (
        2.5,
        "PROMO NUTELLA X140 (15% OFF)",
    ),
}


def norm_desc(s: str) -> str:
    s = str(s).strip()
    s = re.sub(r"\s+", " ", s)
    # Marzo: "… (10% OFF)." → quitar punto tras paréntesis
    s = re.sub(r"\)\s*\.\s*$", ")", s)
    return s


def promo_key(cod: Any, desc: str) -> tuple[float, str] | None:
    try:
        c = float(cod)
    except (TypeError, ValueError):
        return None
    d = norm_desc(desc)
    if not d or d.lower() == "descripcion":
        return None
    return (round(c, 2), d)


def main() -> int:
    ap = argparse.ArgumentParser(description="Promo Ferrero Marzo -> Abril (plantilla).")
    ap.add_argument("--in", dest="src", default=SRC_DEFAULT, help="XLS marzo")
    ap.add_argument("--out", dest="dst", default=DST_DEFAULT, help="XLS abril salida")
    ap.add_argument(
        "--mantener-cantidades",
        action="store_true",
        help="No poner Ctd. Vendida en 0 (por defecto se anulan para abril).",
    )
    args = ap.parse_args()

    if not os.path.isfile(args.src):
        raise SystemExit(f"No existe: {args.src}")

    os.makedirs(os.path.dirname(os.path.abspath(args.dst)) or ".", exist_ok=True)

    rb = xlrd.open_workbook(args.src, formatting_info=False)
    rs = rb.sheet_by_index(0)

    wb = xlwt.Workbook(encoding="utf-8")
    ws = wb.add_sheet("Hoja1")

    mapped_rows = 0
    unmapped_rows = 0
    skipped_rows = 0

    for r in range(rs.nrows):
        key: tuple[float, str] | None = None
        new_cod: Any = None
        new_desc: str | None = None
        if r >= 3:
            cod_raw = rs.cell_value(r, 2)
            desc_raw = rs.cell_value(r, 3)
            key = promo_key(cod_raw, str(desc_raw))
            if key is None:
                skipped_rows += 1
            elif key in MARZO_TO_ABRIL:
                new_cod, new_desc = MARZO_TO_ABRIL[key]
                mapped_rows += 1
            else:
                unmapped_rows += 1

        for c in range(rs.ncols):
            v = rs.cell_value(r, c)
            t = rs.cell_type(r, c)

            if r >= 3 and c == 4 and not args.mantener_cantidades:
                v = 0.0
            elif r >= 3 and c == 2 and new_cod is not None:
                v = float(new_cod)
            elif r >= 3 and c == 3 and new_desc is not None:
                v = new_desc
            elif r >= 3 and c in (2, 3) and key is not None and key not in MARZO_TO_ABRIL:
                pass  # v ya es valor marzo
            elif t == xlrd.XL_CELL_NUMBER and float(v) == int(float(v)) and c != 4:
                v = int(float(v))

            if isinstance(v, str):
                ws.write(r, c, v)
            elif isinstance(v, (int, float)):
                ws.write(r, c, float(v) if c == 4 else v)
            elif t == xlrd.XL_CELL_BOOLEAN:
                ws.write(r, c, bool(v))
            else:
                ws.write(r, c, v)

    w2 = wb.add_sheet("Accionados_16abr2026")
    w2.write(0, 0, "Articulos accionados desde 16/04/2026 — NAKEL S.A.")
    w2.write(
        1,
        0,
        "Col. B = tope cajas (acuerdo). Col. C = ventas Odoo (rellenar_promo_cantidades_odoo_master_dev.py).",
    )
    w2.write(2, 0, "Dinamica / Cliente")
    w2.write(2, 1, "Tope cajas (acuerdo)")
    w2.write(2, 2, "Ventas periodo (Odoo)")
    for i, (txt, tope) in enumerate(ACCIONADOS, start=3):
        w2.write(i, 0, txt)
        w2.write(i, 1, float(tope))
        w2.write(i, 2, 0.0)

    wb.save(args.dst)
    n_data = max(0, rs.nrows - 3)
    print(f"OK: {args.dst}  (filas datos ~{n_data})")
    print(
        f"  Promo mapeada a texto/código abril: {mapped_rows}  "
        f"sin regla (copia marzo): {unmapped_rows}  sin código promo válido: {skipped_rows}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
