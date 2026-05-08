#!/usr/bin/env python3
"""
Genera un XLSX (sin dependencias) a partir de los CSV UNIFICADO.

Pestañas:
- RESUMEN: por vendedor para liquidación
- DETALLE_FACTURAS: detalle por documento (out_invoice)
- DETALLE_NCS: detalle por documento (out_refund)

Entrada esperada en reportes/:
- comisiones_detalle_facturas_<stamp>_UNIFICADO.csv
- comisiones_detalle_ncs_<stamp>_UNIFICADO.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import zipfile
from collections import defaultdict
from datetime import datetime
from typing import Any


def _xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _col_name(n: int) -> str:
    # 1-indexed
    name = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        name = chr(65 + rem) + name
    return name


_re_num = re.compile(r"^-?\d+(\.\d+)?$")


def _is_number(s: str) -> bool:
    s = (s or "").strip()
    return bool(_re_num.match(s))


def _sheet_xml(rows: list[list[Any]]) -> str:
    out = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
        "<sheetData>",
    ]

    for r_idx, row in enumerate(rows, start=1):
        out.append(f'<row r="{r_idx}">')
        for c_idx, v in enumerate(row, start=1):
            cell_ref = f"{_col_name(c_idx)}{r_idx}"
            if v is None:
                out.append(f'<c r="{cell_ref}" t="inlineStr"><is><t></t></is></c>')
                continue
            if isinstance(v, (int, float)):
                out.append(f'<c r="{cell_ref}"><v>{v}</v></c>')
                continue
            vs = str(v)
            if _is_number(vs):
                out.append(f'<c r="{cell_ref}"><v>{vs}</v></c>')
            else:
                out.append(f'<c r="{cell_ref}" t="inlineStr"><is><t>{_xml_escape(vs)}</t></is></c>')
        out.append("</row>")

    out += ["</sheetData>", "</worksheet>"]
    return "\n".join(out)


def _write_xlsx(path: str, sheets: list[tuple[str, list[list[Any]]]]) -> None:
    # Minimal XLSX packaging
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        # [Content_Types].xml
        overrides = "\n".join(
            [
                '  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
                '  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>',
            ]
            + [
                f'  <Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                for i in range(1, len(sheets) + 1)
            ]
        )
        z.writestr(
            "[Content_Types].xml",
            "\n".join(
                [
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
                    '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
                    '  <Default Extension="xml" ContentType="application/xml"/>',
                    overrides,
                    "</Types>",
                ]
            ),
        )

        # _rels/.rels
        z.writestr(
            "_rels/.rels",
            "\n".join(
                [
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
                    '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>',
                    "</Relationships>",
                ]
            ),
        )

        # xl/workbook.xml
        sheets_xml = "\n".join(
            [
                f'    <sheet name="{_xml_escape(name)}" sheetId="{i}" r:id="rId{i}"/>'
                for i, (name, _rows) in enumerate(sheets, start=1)
            ]
        )
        z.writestr(
            "xl/workbook.xml",
            "\n".join(
                [
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">',
                    "  <sheets>",
                    sheets_xml,
                    "  </sheets>",
                    "</workbook>",
                ]
            ),
        )

        # xl/_rels/workbook.xml.rels
        rels = "\n".join(
            [
                f'  <Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
                for i in range(1, len(sheets) + 1)
            ]
            + [
                '  <Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            ]
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            "\n".join(
                [
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
                    rels,
                    "</Relationships>",
                ]
            ),
        )

        # xl/styles.xml (minimal)
        z.writestr(
            "xl/styles.xml",
            "\n".join(
                [
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                    '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
                    "  <fonts count=\"1\"><font><sz val=\"11\"/><color theme=\"1\"/><name val=\"Calibri\"/><family val=\"2\"/></font></fonts>",
                    "  <fills count=\"1\"><fill><patternFill patternType=\"none\"/></fill></fills>",
                    "  <borders count=\"1\"><border><left/><right/><top/><bottom/><diagonal/></border></borders>",
                    "  <cellStyleXfs count=\"1\"><xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\"/></cellStyleXfs>",
                    "  <cellXfs count=\"1\"><xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\" xfId=\"0\"/></cellXfs>",
                    "</styleSheet>",
                ]
            ),
        )

        # worksheets
        for i, (_name, rows) in enumerate(sheets, start=1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", _sheet_xml(rows))


def _read_csv(path: str) -> list[dict[str, str]]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        return list(r)


def _sum_float(rows: list[dict[str, str]], key: str) -> float:
    s = 0.0
    for r in rows:
        try:
            s += float((r.get(key) or "0").strip() or 0)
        except Exception:
            continue
    return s


def _pick_pay_keys(rows: list[dict[str, str]]) -> tuple[str, str]:
    """
    Soporta esquema antiguo (pagar_40/pagar_60_prorrateado) y nuevo (pagar_fijo/pagar_variable_prorrateado).
    """
    if not rows:
        return "pagar_40", "pagar_60_prorrateado"
    keys = set(rows[0].keys())
    if "pagar_fijo" in keys and "pagar_variable_prorrateado" in keys:
        return "pagar_fijo", "pagar_variable_prorrateado"
    return "pagar_40", "pagar_60_prorrateado"


def _rate_label(rows: list[dict[str, str]], key: str) -> str:
    if not rows:
        return ""
    v = (rows[0].get(key) or "").strip()
    if not v:
        return ""
    try:
        return f"{float(v) * 100:.0f}%"
    except Exception:
        return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--report-dir",
        default="/media/klap/raid5/cursor_files/nakel/ventas/repote-comisiones/reportes",
    )
    ap.add_argument("--stamp", required=True, help="YYYY-MM-DD_YYYY-MM-DD")
    ap.add_argument("--out", default="", help="Ruta de salida .xlsx (opcional)")
    args = ap.parse_args()

    report_dir = args.report_dir
    stamp = args.stamp

    fact_path = os.path.join(report_dir, f"comisiones_detalle_facturas_{stamp}_UNIFICADO.csv")
    nc_path = os.path.join(report_dir, f"comisiones_detalle_ncs_{stamp}_UNIFICADO.csv")
    if not os.path.exists(fact_path) or not os.path.exists(nc_path):
        raise SystemExit("No encuentro los CSV UNIFICADO en reportes/.")

    out_path = args.out.strip() or os.path.join(report_dir, f"comisiones_{stamp}.xlsx")

    fact_rows = _read_csv(fact_path)
    nc_rows = _read_csv(nc_path)

    # RESUMEN por vendedor
    by_user = defaultdict(lambda: {"fact": [], "nc": []})
    for r in fact_rows:
        by_user[r.get("invoice_user_id") or "" ]["fact"].append(r)
    for r in nc_rows:
        by_user[r.get("invoice_user_id") or "" ]["nc"].append(r)

    pay_fixed_key, pay_var_key = _pick_pay_keys(fact_rows or nc_rows)
    fixed_lbl = _rate_label(fact_rows or nc_rows, "tasa_fija")
    var_lbl = _rate_label(fact_rows or nc_rows, "tasa_variable")

    resumen_header = [
        "invoice_user_id",
        "VENDEDOR",
        "VENTAS (docs)",
        "FACTURAS (docs)",
        "NCs (docs)",
        "TOTAL_FACTURADO",
        "TOTAL_NCS",
        "NETO_FACTURADO",
        "COMISION_TOTAL_NETA",
        f"COMISION_FIJA{f' ({fixed_lbl})' if fixed_lbl else ''}",
        f"COMISION_VARIABLE_PRORRATEADO{f' ({var_lbl})' if var_lbl else ''}",
        "TOTAL_A_PAGAR",
    ]
    resumen_rows: list[list[Any]] = [resumen_header]

    for user_id in sorted([k for k in by_user.keys() if k.strip()], key=lambda x: int(x) if x.isdigit() else x):
        facts = by_user[user_id]["fact"]
        ncs = by_user[user_id]["nc"]
        vendedor = (facts[0].get("vendedor") if facts else (ncs[0].get("vendedor") if ncs else "")) or ""

        cant_fact = len(facts)
        cant_nc = len(ncs)
        total_fact = _sum_float(facts, "total_documento")
        total_nc = _sum_float(ncs, "total_documento")

        comm = _sum_float(facts, "comision_total") + _sum_float(ncs, "comision_total")
        c_fixed = _sum_float(facts, pay_fixed_key) + _sum_float(ncs, pay_fixed_key)
        c_var = _sum_float(facts, pay_var_key) + _sum_float(ncs, pay_var_key)

        resumen_rows.append(
            [
                int(user_id) if user_id.isdigit() else user_id,
                vendedor,
                cant_fact,  # ventas ~ docs de factura
                cant_fact,
                cant_nc,
                round(total_fact, 2),
                round(total_nc, 2),
                round(total_fact - total_nc, 2),
                round(comm, 2),
                round(c_fixed, 2),
                round(c_var, 2),
                round(c_fixed + c_var, 2),
            ]
        )

    # DETALLES como tabla
    def table_from_rows(rows: list[dict[str, str]]) -> list[list[Any]]:
        if not rows:
            return [["(sin datos)"]]
        header = list(rows[0].keys())
        out = [header]
        for r in rows:
            out.append([r.get(k, "") for k in header])
        return out

    sheets = [
        ("RESUMEN", resumen_rows),
        ("DETALLE_FACTURAS", table_from_rows(fact_rows)),
        ("DETALLE_NCS", table_from_rows(nc_rows)),
    ]

    _write_xlsx(out_path, sheets)
    print(f"✅ XLSX generado: {out_path}")
    print(f"   Fecha: {datetime.now().isoformat(timespec='seconds')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

