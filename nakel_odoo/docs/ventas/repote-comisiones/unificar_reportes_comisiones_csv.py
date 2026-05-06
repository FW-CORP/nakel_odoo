#!/usr/bin/env python3
"""
Unifica CSVs por vendedor (resumen/detalles) en un único CSV por tipo.

Entrada:
- Carpeta: nakel/ventas/repote-comisiones/reportes/
- Archivos: comisiones_{resumen|detalle_facturas|detalle_ncs}_<from>_<to>_<user>_<nombre>.csv

Salida (en la misma carpeta):
- comisiones_resumen_<from>_<to>_UNIFICADO.csv
- comisiones_detalle_facturas_<from>_<to>_UNIFICADO.csv
- comisiones_detalle_ncs_<from>_<to>_UNIFICADO.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from typing import Iterable


def iter_files(report_dir: str, prefix: str, stamp: str) -> list[str]:
    rx = re.compile(rf"^{re.escape(prefix)}_{re.escape(stamp)}_.+\.csv$")
    out: list[str] = []
    for name in os.listdir(report_dir):
        if rx.match(name):
            out.append(os.path.join(report_dir, name))
    return sorted(out)


def read_rows(path: str) -> tuple[list[str], list[dict]]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        fields = list(r.fieldnames or [])
        rows = list(r)
    return fields, rows


def write_rows(path: str, fields: list[str], rows: Iterable[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def unify(report_dir: str, prefix: str, stamp: str) -> str | None:
    files = iter_files(report_dir, prefix, stamp)
    if not files:
        return None

    base_fields: list[str] | None = None
    all_rows: list[dict] = []
    for fp in files:
        fields, rows = read_rows(fp)
        if base_fields is None:
            base_fields = fields
        elif fields != base_fields:
            # Si cambia el esquema, unificamos a "superset" preservando orden original + extras al final
            extras = [f for f in fields if f not in base_fields]
            if extras:
                base_fields = base_fields + extras
        all_rows.extend(rows)

    out_path = os.path.join(report_dir, f"{prefix}_{stamp}_UNIFICADO.csv")
    assert base_fields is not None

    # Normalizar filas al superset (si corresponde)
    norm_rows = []
    for r in all_rows:
        norm = {k: r.get(k, "") for k in base_fields}
        norm_rows.append(norm)

    write_rows(out_path, base_fields, norm_rows)
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--report-dir",
        default="/media/klap/raid5/cursor_files/nakel/ventas/repote-comisiones/reportes",
    )
    ap.add_argument("--stamp", required=True, help="YYYY-MM-DD_YYYY-MM-DD (ej: 2026-04-01_2026-04-25)")
    args = ap.parse_args()

    report_dir = args.report_dir
    stamp = args.stamp

    outputs = []
    for prefix in [
        "comisiones_resumen",
        "comisiones_detalle_facturas",
        "comisiones_detalle_ncs",
    ]:
        out = unify(report_dir, prefix, stamp)
        if out:
            outputs.append(out)

    if outputs:
        print("✅ Unificados generados:")
        for o in outputs:
            print(f"- {o}")
    else:
        print("No encontré archivos por vendedor para ese stamp.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

