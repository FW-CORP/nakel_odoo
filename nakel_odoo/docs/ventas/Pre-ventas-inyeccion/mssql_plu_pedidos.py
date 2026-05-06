#!/usr/bin/env python3
"""
Índice COD_ARTICULO (MSSQL) → PLU limpio desde ARTICULOPLU, para desambiguar productos en Odoo.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

sys.path.insert(0, "/media/klap/raid5/cursor_files")

try:
    import pyodbc  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Instala pyodbc para usar MSSQL.") from exc

try:
    from config_nakel import MSSQL_CONFIG  # type: ignore
except ImportError as e:
    raise SystemExit("Falta config_nakel.py") from e


def limpiar_plu(val: object) -> str:
    if val is None:
        return ""
    t = str(val).replace("\ufeff", "").replace("\u00a0", " ")
    return "".join(ch for ch in t if not ch.isspace())


def _conectar():
    c = MSSQL_CONFIG
    return pyodbc.connect(
        f"DRIVER={{{c['driver']}}};SERVER={c['server']};DATABASE={c['database']};"
        f"UID={c['username']};PWD={c['password']};TrustServerCertificate=yes;",
        timeout=c.get("timeout", 60),
    )


def _claves_numericas_cod_mssql(cod: str) -> set[str]:
    """Claves string para cruzar con codigo_articulo_odoo."""
    out: set[str] = set()
    c = (cod or "").strip().replace(",", ".")
    if not c:
        return out
    out.add(c)
    try:
        d = Decimal(c)
        out.add(format(d.normalize(), "f"))
        out.add(f"{d:.2f}".rstrip("0").rstrip("."))
    except (InvalidOperation, ValueError):
        pass
    return out


@dataclass
class MapaPluArticulo:
    """COD_ARTICULO MSSQL → PLU; índice numérico para equivalencias con Odoo."""

    por_cod_mssql: dict[str, str] = field(default_factory=dict)
    por_clave_num: dict[str, str] = field(default_factory=dict)

    def plu_para_linea(
        self,
        cod_articulo_mssql: str | None,
        codigo_articulo_odoo: str | None,
    ) -> str | None:
        cm = (cod_articulo_mssql or "").strip()
        if cm in self.por_cod_mssql:
            return self.por_cod_mssql[cm]
        co = (codigo_articulo_odoo or "").strip().replace(",", ".")
        if co in self.por_cod_mssql:
            return self.por_cod_mssql[co]
        for key in _claves_numericas_cod_mssql(co):
            if key in self.por_clave_num:
                return self.por_clave_num[key]
        return None


def cargar_mapa_cod_articulo_a_plu() -> MapaPluArticulo:
    """
    COD_ARTICULO tal como en MSSQL → PLU preferido (heurística ROW_NUMBER).
    """
    sql = """
    WITH plu_norm AS (
        SELECT
            ap.ID_ARTICULO,
            ap.PLU,
            REPLACE(REPLACE(REPLACE(REPLACE(LTRIM(RTRIM(CAST(ap.PLU AS NVARCHAR(80)))),
                NCHAR(160), ''), CHAR(9), ''), CHAR(10), ''), CHAR(13), '') AS plu_sin_nbsp_tabs,
            ROW_NUMBER() OVER (
                PARTITION BY ap.ID_ARTICULO
                ORDER BY
                    CASE
                        WHEN LEN(REPLACE(REPLACE(REPLACE(REPLACE(LTRIM(RTRIM(CAST(ap.PLU AS NVARCHAR(80)))),
                            NCHAR(160), ''), CHAR(9), ''), CHAR(10), ''), CHAR(13), '')) >= 8
                        THEN 0 ELSE 1 END,
                    LEN(REPLACE(REPLACE(REPLACE(REPLACE(LTRIM(RTRIM(CAST(ap.PLU AS NVARCHAR(80)))),
                        NCHAR(160), ''), CHAR(9), ''), CHAR(10), ''), CHAR(13), '')) DESC,
                    LTRIM(RTRIM(CAST(ap.PLU AS NVARCHAR(80))))
            ) AS rn
        FROM ARTICULOPLU ap
        WHERE ap.PLU IS NOT NULL
          AND LTRIM(RTRIM(CAST(ap.PLU AS NVARCHAR(80)))) <> ''
          AND LTRIM(RTRIM(CAST(ap.PLU AS NVARCHAR(80)))) <> '0'
    ),
    plu_one AS (
        SELECT ID_ARTICULO, PLU
        FROM plu_norm
        WHERE LEN(plu_sin_nbsp_tabs) > 0
          AND rn = 1
    )
    SELECT LTRIM(RTRIM(a.COD_ARTICULO)) AS cod, p.PLU
    FROM ARTICULOS a
    INNER JOIN plu_one p ON p.ID_ARTICULO = a.ID_ARTICULO
    WHERE a.COD_ARTICULO IS NOT NULL
      AND LTRIM(RTRIM(a.COD_ARTICULO)) <> ''
    """
    conn = _conectar()
    mapa = MapaPluArticulo()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        for cod_raw, plu_raw in cur.fetchall():
            cod = str(cod_raw or "").strip()
            plu = limpiar_plu(plu_raw)
            if not cod or not plu:
                continue
            mapa.por_cod_mssql[cod] = plu
            for nk in _claves_numericas_cod_mssql(cod):
                mapa.por_clave_num.setdefault(nk, plu)
        return mapa
    finally:
        conn.close()
