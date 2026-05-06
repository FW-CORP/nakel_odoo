#!/usr/bin/env python3
"""
Mapa de correcciones para códigos de artículo en preventas (export viejo → Odoo/MSSQL).

Ver: correcciones_codigo_articulo_preventas.example.json
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CORRECCIONES_JSON = SCRIPT_DIR / "correcciones_codigo_articulo_preventas.json"


def cargar_correcciones(path: Path | None) -> dict[str, Any]:
    p = path or DEFAULT_CORRECCIONES_JSON
    if not p.is_file():
        return {"raw_a_cod_odoo": {}, "codigo_odoo_a_correcto": {}}
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    return {
        "raw_a_cod_odoo": dict(data.get("raw_a_cod_odoo") or {}),
        "codigo_odoo_a_correcto": dict(data.get("codigo_odoo_a_correcto") or {}),
    }


def _variantes_clave_raw(cod_raw: str) -> list[str]:
    s = (cod_raw or "").strip()
    if not s:
        return []
    out: list[str] = []
    seen: set[str] = set()

    def add(x: str) -> None:
        if x and x not in seen:
            seen.add(x)
            out.append(x)

    add(s)
    try:
        d = Decimal(s.replace(",", "."))
        if d == d.to_integral_value():
            add(str(int(d)))
    except (InvalidOperation, ValueError):
        pass
    return out


def aplicar_correcciones_codigo(
    cod_raw: str,
    cod_odoo_calculado: str,
    data: dict[str, Any],
) -> tuple[str, str | None, str | None]:
    """
    Devuelve (cod_odoo_final, cod_odoo_antes_correccion, detalle_correccion).

    - raw_a_cod_odoo: clave = valor crudo del CSV (ej. "124309") → default_code Odoo ("1243.90").
    - codigo_odoo_a_correcto: clave = código ya calculado mal (ej. "1243.09") → correcto ("1243.90").
    """
    rmap: dict[str, str] = data.get("raw_a_cod_odoo") or {}
    for k in _variantes_clave_raw(cod_raw):
        if k in rmap:
            dest = str(rmap[k]).strip().replace(",", ".")
            return dest, cod_odoo_calculado, f"raw_a_cod_odoo:{k}→{dest}"

    calc = (cod_odoo_calculado or "").strip().replace(",", ".")
    omap: dict[str, str] = data.get("codigo_odoo_a_correcto") or {}
    if calc in omap:
        dest = str(omap[calc]).strip().replace(",", ".")
        return dest, calc, f"codigo_odoo_a_correcto:{calc}→{dest}"

    try:
        d_calc = Decimal(calc)
        for k, v in omap.items():
            try:
                if Decimal(str(k).replace(",", ".")) == d_calc:
                    dest = str(v).strip().replace(",", ".")
                    return dest, calc, f"codigo_odoo_a_correcto(num):{k}→{dest}"
            except (InvalidOperation, ValueError):
                continue
    except (InvalidOperation, ValueError):
        pass

    return calc or cod_odoo_calculado, None, None


def alerta_por_descripcion_mssql(descripcion: str | None) -> str | None:
    """Convención Nakel: ZZZ/ZZ al inicio en descripción MSSQL."""
    if not descripcion:
        return None
    d = descripcion.strip().upper()
    if d.startswith("ZZZ"):
        return "mssql_descripcion_ZZZ_baja_logica_ERP"
    if d.startswith("ZZ"):
        return "mssql_descripcion_ZZ"
    return None
