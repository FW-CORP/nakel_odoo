#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera FERRERO VENTAS Y STOCK 2026-04.xls a partir del archivo de marzo.

- Titulo (fila 3 col A en Excel = indice 2,0): MARZO -> ABRIL.
- VENTAS y STOCK (cols D y E en Excel = indices 3 y 4), desde fila 7 en Excel
  (indice 6): se ponen en 0 para no enviar datos de marzo por error.
- Hoja extra Accionados_16abr2026: tabla vigente desde 16/04/2026.

Uso:
  cd reportes-ferrero && ./.venv/bin/python generar_ferrero_ventas_stock_abril.py
"""

from __future__ import annotations

import os
import re

import xlrd
import xlwt


DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(DIR, "OUT")
SRC = os.path.join(DIR, "FERRERO VENTAS Y STOCK 2026-03.xls")
DST = os.path.join(OUT_DIR, "FERRERO VENTAS Y STOCK 2026-04.xls")

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


def titulo_abril(val: str) -> str:
    s = str(val)
    s = re.sub(r"\bMARZO\b", "ABRIL", s, flags=re.I)
    s = re.sub(r"\bMarzo\b", "Abril", s)
    s = re.sub(r"2026-03", "2026-04", s)
    s = re.sub(r"03/2026", "04/2026", s)
    return s


def main() -> None:
    if not os.path.isfile(SRC):
        raise SystemExit(f"No existe: {SRC}")

    os.makedirs(OUT_DIR, exist_ok=True)

    rb = xlrd.open_workbook(SRC, formatting_info=False)
    rs = rb.sheet_by_index(0)

    wb = xlwt.Workbook(encoding="utf-8")
    ws = wb.add_sheet("Hoja1")

    for r in range(rs.nrows):
        for c in range(rs.ncols):
            v = rs.cell_value(r, c)
            t = rs.cell_type(r, c)

            if r == 2 and c == 0:
                v = titulo_abril(v) if isinstance(v, str) else v
            elif r >= 6 and c in (3, 4):
                v = 0.0
            elif t == xlrd.XL_CELL_NUMBER and v == int(v) and c not in (3, 4):
                v = int(v)

            if isinstance(v, str):
                ws.write(r, c, v)
            elif isinstance(v, (int, float)):
                ws.write(r, c, float(v) if c in (3, 4) else v)
            elif t == xlrd.XL_CELL_BOOLEAN:
                ws.write(r, c, bool(v))
            else:
                ws.write(r, c, v)

    wa = wb.add_sheet("Accionados_16abr2026")
    wa.write(0, 0, "Articulos accionados desde 16/04/2026 — NAKEL S.A.")
    wa.write(2, 0, "Dinamica / Cliente")
    wa.write(2, 1, "NAKEL S.A. (Tope cajas)")
    for i, (desc, tope) in enumerate(ACCIONADOS, start=3):
        wa.write(i, 0, desc)
        wa.write(i, 1, int(tope))

    wb.save(DST)
    print(f"OK: generado {DST}")


if __name__ == "__main__":
    main()
