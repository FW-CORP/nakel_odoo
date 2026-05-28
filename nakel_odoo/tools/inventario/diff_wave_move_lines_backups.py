#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compara dos respaldos CSV move_lines y detecta:
- cambios en quantity / qty_done en líneas presentes en ambos
- líneas solo en anterior (suelen ser anulaciones: salieron del activo o qty→0)
- líneas solo en nuevo

Compatible con CSV viejos (solo activas, columna descuento) y nuevos (todas las líneas).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

EPS = 1e-6


def _ts_from_name(path: Path) -> str:
    m = re.search(r"_(\d{8}_\d{6})\.csv$", path.name)
    return m.group(1) if m else path.stem


def _prefix_from_name(path: Path) -> str:
    for pat in (
        r"(.+)_move_lines_\d{8}_\d{6}\.csv$",
        r"(.+)_move_lines_activas_\d{8}_\d{6}\.csv$",
    ):
        m = re.match(pat, path.name)
        if m:
            return m.group(1)
    return path.stem.rsplit("_move_lines", 1)[0]


def load_move_lines(path: Path) -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ml_id = int(row["move_line_id"])
            q = float(row.get("quantity") or 0)
            d = float(row.get("qty_done") or 0)
            desc = row.get("descuento_qty_done") or row.get("descuento") or ""
            rows[ml_id] = {
                "move_line_id": ml_id,
                "picking": row.get("picking") or "",
                "sale_ov": row.get("sale_ov") or "",
                "default_code": row.get("default_code") or "",
                "barcode": row.get("barcode") or "",
                "product": row.get("product") or "",
                "quantity": q,
                "qty_done": d,
                "descuento_qty_done": float(desc) if desc != "" else max(0.0, q - d),
                "activa": (row.get("activa") or "").lower() in ("true", "1", "yes") or q > EPS,
                "picked": row.get("picked") or "",
                "ml_state": row.get("ml_state") or "",
                "write_date": row.get("write_date") or "",
            }
    return rows


def find_move_line_files(directory: Path, glob_prefix: str | None) -> list[Path]:
    patterns = ["*_move_lines_*.csv"]
    if glob_prefix:
        patterns = [f"{glob_prefix}*_move_lines_*.csv", f"{glob_prefix}*_move_lines_activas_*.csv"]
    files: list[Path] = []
    for pat in patterns:
        for p in directory.glob(pat):
            if "_activas_" in p.name and "_move_lines_activas_" not in p.name:
                continue
            if "_diff_" in p.name or "_anuladas_" in p.name:
                continue
            files.append(p)
    # prefer full move_lines over activas only when same timestamp
    by_ts: dict[str, Path] = {}
    for p in files:
        ts = _ts_from_name(p)
        is_full = "_move_lines_activas_" not in p.name
        prev = by_ts.get(ts)
        if prev is None or (is_full and "_move_lines_activas_" in prev.name):
            by_ts[ts] = p
    return sorted(by_ts.values(), key=_ts_from_name)


def find_latest_pair(directory: Path, glob_prefix: str | None) -> tuple[Path, Path]:
    files = find_move_line_files(directory, glob_prefix)
    if len(files) < 2:
        raise SystemExit(
            f"Se necesitan al menos 2 CSV move_lines en {directory} (hay {len(files)})."
        )
    return files[-2], files[-1]


def find_baseline(directory: Path, glob_prefix: str | None) -> Path | None:
    files = find_move_line_files(directory, glob_prefix)
    return files[0] if files else None


def compare_snapshots(
    before: dict[int, dict[str, Any]],
    after_map: dict[int, dict[str, Any]],
    epsilon: float,
) -> tuple[list[dict], list[dict], list[dict]]:
    changed: list[dict[str, Any]] = []
    only_before: list[dict[str, Any]] = []
    only_after: list[dict[str, Any]] = []

    all_ids = set(before) | set(after_map)
    for ml_id in sorted(all_ids):
        b = before.get(ml_id)
        a = after_map.get(ml_id)
        if b and not a:
            only_before.append({**b, "change_kind": "solo_en_anterior"})
            continue
        if a and not b:
            only_after.append({**a, "change_kind": "solo_en_nuevo"})
            continue
        assert b and a
        qb, qa = float(b["quantity"]), float(a["quantity"])
        db, da = float(b["qty_done"]), float(a["qty_done"])
        if (
            abs(qb - qa) <= epsilon
            and abs(db - da) <= epsilon
        ):
            continue
        kind = "ajuste_cantidad"
        if qb > EPS and qa <= EPS:
            kind = "anulada_quantity_a_0"
        elif qb <= EPS and qa > EPS:
            kind = "reactivada"
        changed.append(
            {
                "change_kind": kind,
                "move_line_id": ml_id,
                "picking": a.get("picking") or b.get("picking"),
                "sale_ov": a.get("sale_ov") or b.get("sale_ov"),
                "default_code": a.get("default_code") or b.get("default_code"),
                "barcode": a.get("barcode") or b.get("barcode"),
                "product": a.get("product") or b.get("product"),
                "quantity_before": qb,
                "quantity_after": qa,
                "delta_quantity": qa - qb,
                "qty_done_before": db,
                "qty_done_after": da,
                "delta_qty_done": da - db,
                "descuento_before": float(b.get("descuento_qty_done") or 0),
                "descuento_after": float(a.get("descuento_qty_done") or 0),
                "picked": a.get("picked") or b.get("picked"),
                "write_date_after": a.get("write_date") or "",
            }
        )
    return changed, only_before, only_after


def write_diff_outputs(
    before_p: Path,
    after_p: Path,
    changed: list[dict],
    only_before: list[dict],
    only_after: list[dict],
    out_dir: Path,
    label: str,
) -> Path:
    ts_before = _ts_from_name(before_p)
    ts_after = _ts_from_name(after_p)
    prefix = _prefix_from_name(after_p)
    suffix = f"{ts_after}_vs_{ts_before}" if not label else f"{ts_after}_vs_{ts_before}_{label}"

    anuladas = [r for r in changed if r.get("change_kind") == "anulada_quantity_a_0"]
    summary = {
        "generated_at": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "label": label or "intervalo",
        "before_file": str(before_p),
        "after_file": str(after_p),
        "ts_before": ts_before,
        "ts_after": ts_after,
        "lines_before": len(load_move_lines(before_p)),
        "lines_after": len(load_move_lines(after_p)),
        "changed": len(changed),
        "anuladas_quantity_a_0": len(anuladas),
        "solo_en_anterior": len(only_before),
        "solo_en_nuevo": len(only_after),
        "nota": (
            "solo_en_anterior con CSV viejo (solo activas) = línea anulada o ausente en el nuevo. "
            "anulada_quantity_a_0 = misma línea con quantity>0 que pasó a 0."
        ),
    }

    fieldnames = [
        "change_kind",
        "move_line_id",
        "picking",
        "sale_ov",
        "default_code",
        "barcode",
        "product",
        "quantity_before",
        "quantity_after",
        "delta_quantity",
        "qty_done_before",
        "qty_done_after",
        "delta_qty_done",
        "descuento_before",
        "descuento_after",
        "picked",
        "write_date_after",
    ]
    diff_csv = out_dir / f"{prefix}_diff_{suffix}.csv"
    with diff_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in sorted(
            changed,
            key=lambda x: (
                0 if x.get("change_kind") == "anulada_quantity_a_0" else 1,
                -abs(float(x.get("delta_quantity") or 0)),
                x.get("picking") or "",
            ),
        ):
            w.writerow(row)
    print("Wrote", diff_csv, f"({len(changed)} cambios, {len(anuladas)} anuladas)")

    if only_before or only_after:
        extras = out_dir / f"{prefix}_diff_{suffix}_extras.csv"
        with extras.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "kind",
                    "move_line_id",
                    "picking",
                    "sale_ov",
                    "default_code",
                    "barcode",
                    "product",
                    "quantity",
                    "qty_done",
                    "descuento_qty_done",
                ],
            )
            w.writeheader()
            for row in only_before:
                w.writerow(
                    {
                        "kind": "solo_en_anterior",
                        "move_line_id": row["move_line_id"],
                        "picking": row["picking"],
                        "sale_ov": row["sale_ov"],
                        "default_code": row.get("default_code"),
                        "barcode": row.get("barcode"),
                        "product": row["product"],
                        "quantity": row["quantity"],
                        "qty_done": row["qty_done"],
                        "descuento_qty_done": row.get("descuento_qty_done"),
                    }
                )
            for row in only_after:
                w.writerow(
                    {
                        "kind": "solo_en_nuevo",
                        "move_line_id": row["move_line_id"],
                        "picking": row["picking"],
                        "sale_ov": row["sale_ov"],
                        "default_code": row.get("default_code"),
                        "barcode": row.get("barcode"),
                        "product": row["product"],
                        "quantity": row["quantity"],
                        "qty_done": row["qty_done"],
                        "descuento_qty_done": row.get("descuento_qty_done"),
                    }
                )
        print("Wrote", extras, f"(solo_anterior={len(only_before)}, solo_nuevo={len(only_after)})")

    summary_path = out_dir / f"{prefix}_diff_{suffix}_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Diff entre respaldos move_lines de una ola.")
    ap.add_argument("--dir", type=Path, default=None)
    ap.add_argument("--before", type=Path, default=None)
    ap.add_argument("--after", type=Path, default=None)
    ap.add_argument("--prefix", default=None)
    ap.add_argument("--output-dir", type=Path, default=None)
    ap.add_argument("--epsilon", type=float, default=EPS)
    ap.add_argument(
        "--vs-baseline",
        action="store_true",
        help="Además comparar el snapshot más nuevo contra el más antiguo del directorio.",
    )
    args = ap.parse_args()

    out_dir = args.output_dir

    if args.before and args.after:
        before_p, after_p = args.before, args.after
        out_dir = out_dir or after_p.parent
        before = load_move_lines(before_p)
        after_map = load_move_lines(after_p)
        changed, ob, oa = compare_snapshots(before, after_map, args.epsilon)
        write_diff_outputs(before_p, after_p, changed, ob, oa, out_dir, "")
        return

    if not args.dir:
        raise SystemExit("Indicá --dir o --before y --after.")

    out_dir = out_dir or args.dir

    if args.vs_baseline:
        files = find_move_line_files(args.dir, args.prefix)
        if len(files) >= 2:
            baseline_p, latest_p = files[0], files[-1]
            if baseline_p != latest_p:
                print("=== Diff vs BASELINE ===")
                changed, ob, oa = compare_snapshots(
                    load_move_lines(baseline_p), load_move_lines(latest_p), args.epsilon
                )
                write_diff_outputs(baseline_p, latest_p, changed, ob, oa, out_dir, "baseline")

    try:
        before_p, after_p = find_latest_pair(args.dir, args.prefix)
    except SystemExit as e:
        if not args.vs_baseline:
            raise
        print(e)
        return

    print("=== Diff vs corrida anterior ===")
    changed, ob, oa = compare_snapshots(
        load_move_lines(before_p), load_move_lines(after_p), args.epsilon
    )
    write_diff_outputs(before_p, after_p, changed, ob, oa, out_dir, "intervalo")


if __name__ == "__main__":
    main()
