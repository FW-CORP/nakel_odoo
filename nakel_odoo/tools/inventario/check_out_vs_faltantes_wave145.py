#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cotejo **solo lectura** entre OUT en Odoo (`master_dev`) y el cuadro Markdown
`FALTANTES_HOJA_PICKEO_WAVE145.md` (WAVE/00145).

La columna **Cant. hoja** del MD **no** tiene una sola semántica (a veces es faltante total,
a veces impreso ± **F(−n)**, a veces reparto entre OV). Por eso:

- **Por defecto** (`--mode reporte`): genera un **TSV** con OUT + producto + `qty_done` / `quantity`
  en Odoo y la fila del MD (OV, cant_raw, marca, notas) para que **vos** cotejés con el PDF.
- **Opcional** (`--mode fmenos`): solo en filas con marca **F (−n)** y *Cant. hoja* con **impreso**,
  compara `qty_done` con **impreso − n** (misma convención que varias filas del doc).

Conexión: `config_nakel.ODOO_CONFIG_MASTER_DEV`.

Uso:

  cd /media/klap/raid5/cursor_files/nakel
  python3 nakel_odoo/tools/inventario/check_out_vs_faltantes_wave145.py \\
    --out-tsv /media/klap/raid5/cursor_files/backups/out_vs_faltantes_wave145.tsv

  python3 nakel_odoo/tools/inventario/check_out_vs_faltantes_wave145.py --mode fmenos
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Any

import xmlrpc.client

_WORKSPACE_NAKEL = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from config_nakel import ODOO_CONFIG_MASTER_DEV  # noqa: E402

DEFAULT_MD = (
    _WORKSPACE_NAKEL
    / "nakel_odoo"
    / "docs"
    / "inventario"
    / "incidencias"
    / "logistica"
    / "wave145"
    / "FALTANTES_HOJA_PICKEO_WAVE145.md"
)


def connect():
    cfg = ODOO_CONFIG_MASTER_DEV
    url = cfg["url"].rstrip("/")
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)
    uid = common.authenticate(cfg["db"], cfg["username"], cfg["password"], {})
    if not uid:
        raise SystemExit("Autenticación Odoo fallida.")
    return models, int(uid), cfg["db"], cfg["password"]


def parse_faltantes_table(md_text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in md_text.splitlines():
        line = line.rstrip()
        if not line.startswith("|") or line.startswith("|-----") or "Pág. | Marca" in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 10:
            continue
        codigo_cell = parts[3]
        cant_cell = parts[5]
        notas = parts[6]
        ov_cell = parts[7]
        out_cell = parts[9]
        pag = parts[1]
        marca = parts[2]

        mcode = re.search(r"\*\*([^*]+)\*\*", codigo_cell)
        if not mcode:
            continue
        code = mcode.group(1).strip()

        ovs = re.findall(r"\*\*(S\d+)\*\*", ov_cell)
        out_nums: list[str] = []
        for m in re.finditer(r"CEN/OUT/(\d{5})\b", out_cell):
            out_nums.append(m.group(1))
        for m in re.finditer(r"`(\d{5})`", out_cell):
            if m.group(1) not in out_nums:
                out_nums.append(m.group(1))

        skip_reason = ""
        if "sin OUT" in out_cell.lower():
            skip_reason = "sin OUT (texto en celda)"
        elif not out_nums:
            skip_reason = "sin número OUT en celda"
        elif len(ovs) != 1 or len(out_nums) != 1:
            skip_reason = f"multi OV/OUT (OV={len(ovs)} OUT={len(out_nums)})"

        rows.append(
            {
                "pag": pag,
                "marca": marca,
                "code": code,
                "cant_raw": cant_cell,
                "notas": notas.replace("\t", " ")[:500],
                "ovs": ovs,
                "out_nums": out_nums,
                "skip_reason": skip_reason,
            }
        )
    return rows


def expected_fmenos_impreso(marca: str, cant_raw: str) -> float | None:
    """Si aplica F(−n) + 'impreso' en cant_raw → impreso − n."""
    cant_raw = cant_raw.replace(",", ".")
    if "impreso" not in cant_raw.lower():
        return None
    m_f = re.search(r"F\s*\(\s*[\u2212\-]\s*(\d+)\s*\)", marca)
    if not m_f:
        return None
    nums = [float(x) for x in re.findall(r"[\d]+(?:\.[\d]+)?", cant_raw)]
    if not nums:
        return None
    n = int(m_f.group(1))
    impr = max(nums)
    return max(0.0, impr - n)


def main() -> None:
    ap = argparse.ArgumentParser(description="Cotejo OUT vs FALTANTES (solo lectura).")
    ap.add_argument("--md-path", type=Path, default=DEFAULT_MD)
    ap.add_argument(
        "--mode",
        choices=("reporte", "fmenos"),
        default="reporte",
        help="reporte=TSV para cotejo manual; fmenos=solo filas F(−n)+impreso",
    )
    ap.add_argument(
        "--out-tsv",
        type=Path,
        default=None,
        help="Ruta TSV salida (solo mode=reporte). Default: backups/out_vs_faltantes_wave145.tsv",
    )
    args = ap.parse_args()

    md_path = args.md_path
    if not md_path.is_file():
        raise SystemExit(f"No existe {md_path}")

    frows = parse_faltantes_table(md_path.read_text(encoding="utf-8"))
    models, uid, db, pwd = connect()

    out_tsv = args.out_tsv
    if args.mode == "reporte" and out_tsv is None:
        out_tsv = Path("/media/klap/raid5/cursor_files/backups/out_vs_faltantes_wave145.tsv")
        out_tsv.parent.mkdir(parents=True, exist_ok=True)

    if args.mode == "reporte":
        assert out_tsv is not None
        n = 0
        with out_tsv.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter="\t")
            w.writerow(
                [
                    "pag_md",
                    "marca_md",
                    "codigo_md",
                    "cant_hoja_raw",
                    "notas_md_resumen",
                    "ov",
                    "out_picking",
                    "out_state",
                    "product_odoo",
                    "qty_done_out",
                    "quantity_out_ml",
                ]
            )
            for fr in frows:
                if fr["skip_reason"]:
                    continue
                ov = fr["ovs"][0]
                out_name = f"CEN/OUT/{fr['out_nums'][0]}"
                code = fr["code"]

                pick_ids = models.execute_kw(
                    db,
                    uid,
                    pwd,
                    "stock.picking",
                    "search",
                    [[("name", "=", out_name), ("sale_id.name", "=", ov)]],
                    {"limit": 2},
                )
                if len(pick_ids) != 1:
                    w.writerow(
                        [
                            fr["pag"],
                            fr["marca"],
                            code,
                            fr["cant_raw"],
                            fr["notas"][:120],
                            ov,
                            out_name,
                            "NO_SINGLE_PICKING" if not pick_ids else "MULTI",
                            "",
                            "",
                            "",
                            "",
                        ]
                    )
                    n += 1
                    continue

                pid = pick_ids[0]
                [pkr] = models.execute_kw(
                    db, uid, pwd, "stock.picking", "read", [[pid]], {"fields": ["state"]}
                )
                st_pick = pkr.get("state") or ""

                prod_ids = models.execute_kw(
                    db,
                    uid,
                    pwd,
                    "product.product",
                    "search",
                    [[("default_code", "=", code)]],
                    {"limit": 2},
                )
                if not prod_ids:
                    prod_ids = models.execute_kw(
                        db,
                        uid,
                        pwd,
                        "product.product",
                        "search",
                        [[("default_code", "ilike", code)]],
                        {"limit": 2},
                    )
                if len(prod_ids) != 1:
                    w.writerow(
                        [
                            fr["pag"],
                            fr["marca"],
                            code,
                            fr["cant_raw"],
                            fr["notas"][:120],
                            ov,
                            out_name,
                            st_pick,
                            "NO_SINGLE_PRODUCT",
                            "",
                            "",
                        ]
                    )
                    n += 1
                    continue

                mls = models.execute_kw(
                    db,
                    uid,
                    pwd,
                    "stock.move.line",
                    "search_read",
                    [[("picking_id", "=", pid), ("product_id", "=", prod_ids[0])]],
                    {"fields": ["product_id", "quantity", "qty_done"]},
                )
                if not mls:
                    w.writerow(
                        [
                            fr["pag"],
                            fr["marca"],
                            code,
                            fr["cant_raw"],
                            fr["notas"][:120],
                            ov,
                            out_name,
                            st_pick,
                            "SIN_LINEA_EN_OUT",
                            "",
                            "",
                        ]
                    )
                    n += 1
                    continue

                pname = mls[0]["product_id"][1] if mls[0].get("product_id") else code
                q_done = sum(float(m.get("qty_done") or 0) for m in mls)
                q_res = sum(float(m.get("quantity") or 0) for m in mls)
                w.writerow(
                    [
                        fr["pag"],
                        fr["marca"],
                        code,
                        fr["cant_raw"],
                        fr["notas"][:120],
                        ov,
                        out_name,
                        st_pick,
                        pname,
                        f"{q_done:g}",
                        f"{q_res:g}",
                    ]
                )
                n += 1

        print("=== reporte TSV (cotejo manual vs PDF) ===")
        print("Filas MD parseadas:", len(frows))
        print("Filas escritas (OV+OUT+código resolvible):", n)
        print("Salida:", out_tsv.resolve())
        print("Abrí el TSV y compará qty_done_out con tu hoja; la columna cant_hoja_raw es la del MD.")

    elif args.mode == "fmenos":
        ok = 0
        bad = 0
        skip = 0
        for fr in frows:
            if fr["skip_reason"]:
                skip += 1
                continue
            exp = expected_fmenos_impreso(fr["marca"], fr["cant_raw"])
            if exp is None:
                skip += 1
                continue

            ov = fr["ovs"][0]
            out_name = f"CEN/OUT/{fr['out_nums'][0]}"
            code = fr["code"]

            pick_ids = models.execute_kw(
                db,
                uid,
                pwd,
                "stock.picking",
                "search",
                [[("name", "=", out_name), ("sale_id.name", "=", ov)]],
                {"limit": 1},
            )
            if not pick_ids:
                print("NO_PICK", out_name, ov, code, fr["pag"])
                bad += 1
                continue
            prod_ids = models.execute_kw(
                db, uid, pwd, "product.product", "search", [[("default_code", "=", code)]], {"limit": 1}
            )
            if not prod_ids:
                prod_ids = models.execute_kw(
                    db, uid, pwd, "product.product", "search", [[("default_code", "ilike", code)]], {"limit": 1}
                )
            if not prod_ids:
                print("NO_PROD", out_name, ov, code, fr["pag"])
                bad += 1
                continue
            mls = models.execute_kw(
                db,
                uid,
                pwd,
                "stock.move.line",
                "search_read",
                [[("picking_id", "=", pick_ids[0]), ("product_id", "=", prod_ids[0])]],
                {"fields": ["qty_done"]},
            )
            q_done = sum(float(m.get("qty_done") or 0) for m in mls)
            if abs(q_done - exp) <= 0.01:
                ok += 1
            else:
                bad += 1
                print(
                    f"DIF {out_name} {ov} [{code}] pág {fr['pag']}: qty_done={q_done:g} "
                    f"vs F(−*) impreso−n={exp:g}"
                )

        print("=== mode fmenos ===")
        print("OK:", ok, "DIF/ERR:", bad, "skip (sin F−+impreso o multi):", skip)


if __name__ == "__main__":
    main()
