#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compara dos respaldos CSV de move_lines (backup_wave_progress_master_dev.py)
y genera un diferencial: qué líneas cambiaron qty_done / descuento entre corridas.

Uso (auto: últimos 2 archivos move_lines en el directorio):
  python3 nakel_odoo/tools/inventario/diff_wave_move_lines_backups.py \\
    --dir /media/klap/raid5/cursor_files/nakel/Prod-Incidencias/wave156/backups

Uso (manual):
  python3 nakel_odoo/tools/inventario/diff_wave_move_lines_backups.py \\
    --before backups/wave_00156_batch163_move_lines_20260520_104313.csv \\
    --after  backups/wave_00156_batch163_move_lines_20260520_180000.csv

Salida:
  <prefijo>_diff_<ts_after>_vs_<ts_before>.csv
  <prefijo>_diff_<ts_after>_vs_<ts_before>_summary.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


def _ts_from_name(path: Path) -> str:
    m = re.search(r"_(\d{8}_\d{6})\.csv$", path.name)
    return m.group(1) if m else path.stem


def _prefix_from_name(path: Path) -> str:
    m = re.match(r"(.+)_move_lines_\d{8}_\d{6}\.csv$", path.name)
    return m.group(1) if m else path.stem.rsplit("_move_lines", 1)[0]


def load_move_lines(path: Path) -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ml_id = int(row["move_line_id"])
            rows[ml_id] = {
                "move_line_id": ml_id,
                "picking": row.get("picking") or "",
                "sale_ov": row.get("sale_ov") or "",
                "product": row.get("product") or "",
                "quantity": float(row.get("quantity") or 0),
                "qty_done": float(row.get("qty_done") or 0),
                "descuento": float(row.get("descuento") or 0),
                "picked": row.get("picked") or "",
                "ml_state": row.get("ml_state") or "",
            }
    return rows


def find_latest_pair(directory: Path, glob_prefix: str | None) -> tuple[Path, Path]:
    pattern = "*_move_lines_*.csv"
    if glob_prefix:
        pattern = f"{glob_prefix}*_move_lines_*.csv"
    files = sorted(directory.glob(pattern), key=lambda p: _ts_from_name(p))
    if len(files) < 2:
        raise SystemExit(
            f"Se necesitan al menos 2 CSV move_lines en {directory} (hay {len(files)}). "
            "Corré backup_wave_progress_master_dev.py dos veces o pasá --before/--after."
        )
    return files[-2], files[-1]


def main() -> None:
    ap = argparse.ArgumentParser(description="Diff entre dos respaldos move_lines de una ola.")
    ap.add_argument("--dir", type=Path, default=None, help="Carpeta con CSV move_lines")
    ap.add_argument("--before", type=Path, default=None, help="CSV anterior (más viejo)")
    ap.add_argument("--after", type=Path, default=None, help="CSV nuevo (más reciente)")
    ap.add_argument(
        "--prefix",
        default=None,
        help="Filtro de nombre, ej. wave_00156_batch163 (solo si --dir)",
    )
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directorio de salida (default: mismo que --after o --dir)",
    )
    ap.add_argument(
        "--epsilon",
        type=float,
        default=1e-6,
        help="Umbral para considerar cambio en qty_done/descuento",
    )
    args = ap.parse_args()

    if args.before and args.after:
        before_p, after_p = args.before, args.after
    elif args.dir:
        before_p, after_p = find_latest_pair(args.dir, args.prefix)
    else:
        raise SystemExit("Indicá --dir o bien --before y --after.")

    if not before_p.is_file() or not after_p.is_file():
        raise SystemExit(f"Archivo no encontrado: {before_p} / {after_p}")

    before = load_move_lines(before_p)
    after_map = load_move_lines(after_p)

    ts_before = _ts_from_name(before_p)
    ts_after = _ts_from_name(after_p)
    prefix = _prefix_from_name(after_p)

    out_dir = args.output_dir or after_p.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    changed: list[dict[str, Any]] = []
    only_after: list[dict[str, Any]] = []
    only_before: list[dict[str, Any]] = []

    all_ids = set(before) | set(after_map)
    for ml_id in sorted(all_ids):
        b = before.get(ml_id)
        a = after_map.get(ml_id)
        if b and not a:
            only_before.append(b)
            continue
        if a and not b:
            only_after.append(a)
            continue
        assert b and a
        q_after = float(a["qty_done"])
        d_after = float(a["descuento"])
        q_before = float(b["qty_done"])
        d_before = float(b["descuento"])
        delta_d = d_after - d_before
        delta_q = q_after - q_before
        if abs(delta_d) <= args.epsilon and abs(delta_q) <= args.epsilon:
            continue
        changed.append(
            {
                "move_line_id": ml_id,
                "picking": a.get("picking") or b.get("picking"),
                "sale_ov": a.get("sale_ov") or b.get("sale_ov"),
                "product": a.get("product") or b.get("product"),
                "quantity": a.get("quantity") or b.get("quantity"),
                "qty_done_before": q_before,
                "qty_done_after": q_after,
                "delta_qty_done": q_after - q_before,
                "descuento_before": d_before,
                "descuento_after": d_after,
                "delta_descuento": delta_d,
                "picked": a.get("picked") or b.get("picked"),
                "ml_state": a.get("ml_state") or b.get("ml_state"),
            }
        )

    summary = {
        "generated_at": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "before_file": str(before_p),
        "after_file": str(after_p),
        "ts_before": ts_before,
        "ts_after": ts_after,
        "lines_before": len(before),
        "lines_after": len(after_map),
        "changed": len(changed),
        "only_in_after": len(only_after),
        "only_in_before": len(only_before),
        "total_descuento_after": sum(float(r["descuento_after"]) for r in changed),
        "nota": "delta_descuento > 0 = descontaron más unidades entre el respaldo anterior y el nuevo.",
    }

    diff_csv = out_dir / f"{prefix}_diff_{ts_after}_vs_{ts_before}.csv"
    fieldnames = [
        "move_line_id",
        "picking",
        "sale_ov",
        "product",
        "quantity",
        "qty_done_before",
        "qty_done_after",
        "delta_qty_done",
        "descuento_before",
        "descuento_after",
        "delta_descuento",
        "picked",
        "ml_state",
    ]
    with diff_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in sorted(changed, key=lambda x: (-float(x["delta_descuento"]), x["picking"], x["product"])):
            w.writerow(row)
    print("Wrote", diff_csv, f"({len(changed)} cambios)")

    if only_after or only_before:
        extras = out_dir / f"{prefix}_diff_{ts_after}_vs_{ts_before}_extras.csv"
        with extras.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=["kind", "move_line_id", "picking", "sale_ov", "product", "quantity", "qty_done", "descuento"],
            )
            w.writeheader()
            for row in only_before:
                w.writerow(
                    {
                        "kind": "solo_en_anterior",
                        "move_line_id": row["move_line_id"],
                        "picking": row["picking"],
                        "sale_ov": row["sale_ov"],
                        "product": row["product"],
                        "quantity": row["quantity"],
                        "qty_done": row["qty_done"],
                        "descuento": row["descuento"],
                    }
                )
            for row in only_after:
                w.writerow(
                    {
                        "kind": "solo_en_nuevo",
                        "move_line_id": row["move_line_id"],
                        "picking": row["picking"],
                        "sale_ov": row["sale_ov"],
                        "product": row["product"],
                        "quantity": row["quantity"],
                        "qty_done": row["qty_done"],
                        "descuento": row["descuento"],
                    }
                )
        print("Wrote", extras)

    summary_path = out_dir / f"{prefix}_diff_{ts_after}_vs_{ts_before}_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("Wrote", summary_path)


if __name__ == "__main__":
    main()
