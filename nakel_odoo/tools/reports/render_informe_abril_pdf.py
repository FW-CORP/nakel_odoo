#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera PDF a partir del informe Markdown de actividades (abr 2026).

Requisitos (venv): pip install fpdf2 markdown
Uso:
  tools/reports/.venv_pdf/bin/python tools/reports/render_informe_abril_pdf.py
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

import markdown
from fpdf import FPDF
from fpdf.fonts import FontFace, TextStyle
from fpdf.html import DEFAULT_TAG_STYLES

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MD = REPO_ROOT / "docs/informes/INFORME_ACTIVIDADES_ABRIL_2026.md"
DEFAULT_PDF = REPO_ROOT / "docs/informes/INFORME_ACTIVIDADES_ABRIL_2026.pdf"

# Anchos en <th> (fpdf2 ignora CSS en <style> y además lo imprimía como texto plano).
_TH_WIDTHS_BY_COL: dict[int, tuple[str, ...]] = {
    2: ("32%", "68%"),
    3: ("18%", "62%", "20%"),
    4: ("12%", "40%", "30%", "18%"),
    5: ("10%", "28%", "28%", "24%", "10%"),
}


def _flatten_inline_markdown_in_table_rows(md_text: str) -> str:
    """fpdf2 no admite <code>/<strong> anidados dentro de <td>."""
    lines = []
    for line in md_text.splitlines():
        if line.strip().startswith("|"):
            line = line.replace("`", "")
            line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
            line = re.sub(r"\*(.+?)\*", r"\1", line)
        lines.append(line)
    return "\n".join(lines)


def _inject_table_th_widths(html: str) -> str:
    """Fija anchos de columnas en la primera fila de cabecera (alinea «h est.»)."""

    def process_table(table: str) -> str:
        om = re.search(
            r"<thead>\s*<tr>([\s\S]*?)</tr>\s*</thead>", table, re.IGNORECASE
        )
        if not om:
            return table
        row_inner = om.group(1)
        th_matches = list(
            re.finditer(r"<th(\b[^>]*)>([\s\S]*?)</th>", row_inner, re.IGNORECASE)
        )
        if not th_matches:
            return table
        n = len(th_matches)
        widths = _TH_WIDTHS_BY_COL.get(n) or tuple(f"{100 // n}%" for _ in range(n))
        new_cells: list[str] = []
        for i, tm in enumerate(th_matches):
            attrs, content = tm.group(1), tm.group(2)
            if re.search(r"\bwidth\s*=", attrs, re.IGNORECASE):
                new_cells.append(tm.group(0))
            else:
                w = widths[min(i, len(widths) - 1)]
                new_cells.append(f'<th{attrs} width="{w}">{content}</th>')
        new_thead = f"<thead><tr>{''.join(new_cells)}</tr></thead>"
        return re.sub(
            r"<thead>\s*<tr>[\s\S]*?</tr>\s*</thead>",
            new_thead,
            table,
            count=1,
            flags=re.IGNORECASE,
        )

    def repl(m: re.Match[str]) -> str:
        return process_table(m.group(0))

    return re.sub(r"<table\b[^>]*>[\s\S]*?</table>", repl, html, flags=re.IGNORECASE)


def md_to_html(md_text: str) -> str:
    md_text = _flatten_inline_markdown_in_table_rows(md_text)
    # fpdf2 write_html no entiende \( \) del Markdown matemático
    md_text = re.sub(r"\\\(([^)]+)\\\)", r"(\1)", md_text)
    body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "nl2br", "sane_lists"],
        output_format="html5",
    )
    body = _inject_table_th_widths(body)
    # fpdf2 v2.x vuelca el contenido de <head> como texto; solo meta + estilos vía tag_styles.
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'/></head><body>"
        + body
        + "</body></html>"
    )


def _html_tag_styles():
    """DejaVu + colores de encabezado (sin <style> en <head>, incompatible con fpdf2)."""
    styles = dict(DEFAULT_TAG_STYLES)
    styles["code"] = FontFace(family="DejaVu", size_pt=8)
    styles["pre"] = TextStyle(t_margin=4 + 7 / 30, font_family="DejaVu")
    styles["h1"] = TextStyle(
        font_family="DejaVu",
        font_style="B",
        font_size_pt=17,
        color="#1e3a5f",
        t_margin=5,
        b_margin=6,
    )
    styles["h2"] = TextStyle(
        font_family="DejaVu",
        font_style="B",
        font_size_pt=13,
        color="#2c5282",
        t_margin=5 + 453 / 900,
        b_margin=6,
    )
    styles["h3"] = TextStyle(
        font_family="DejaVu",
        font_style="B",
        font_size_pt=11,
        color="#2d3748",
        t_margin=5 + 199 / 900,
        b_margin=4,
    )
    styles["strong"] = FontFace(emphasis="BOLD", color="#1a365d")
    styles["em"] = FontFace(emphasis="ITALICS", color="#4a5568")
    return styles


def _register_dejavu(pdf: FPDF) -> None:
    base = Path("/usr/share/fonts/truetype/dejavu")
    sans = base / "DejaVuSans.ttf"
    bold = base / "DejaVuSans-Bold.ttf"
    pdf.add_font("DejaVu", "", str(sans))
    pdf.add_font("DejaVu", "B", str(bold))
    # Paquete DejaVu en Ubuntu no trae Sans-Oblique; reutilizamos regular/bold.
    pdf.add_font("DejaVu", "I", str(sans))
    pdf.add_font("DejaVu", "BI", str(bold))


def main() -> int:
    md_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_MD
    pdf_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PDF
    if not md_path.is_file():
        print("No existe:", md_path, file=sys.stderr)
        return 1

    md_text = md_path.read_text(encoding="utf-8")
    html = md_to_html(md_text)

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    _register_dejavu(pdf)
    pdf.set_creator("nakel_odoo/tools/reports/render_informe_abril_pdf.py")
    pdf.set_title("Informe de actividades — Abril 2026")
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.set_margins(16, 16, 16)
    pdf.add_page()
    pdf.set_font("DejaVu", "", 10.5)
    pdf.write_html(
        html,
        font_family="DejaVu",
        tag_styles=_html_tag_styles(),
        table_line_separators=True,
    )

    # Pie de última página
    pdf.set_y(-12)
    pdf.set_font("DejaVu", "", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(
        0,
        5,
        f"Nakel / FWCORP — generado el {date.today().isoformat()} — fuente: {md_path.name}",
        align="C",
    )

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(pdf_path))
    print("PDF:", pdf_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
