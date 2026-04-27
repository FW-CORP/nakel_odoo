#!/usr/bin/env python3
"""
Lee ``impuestos.sqlite`` (tabla ``productos``), consulta **Gestion** (MSSQL) y
rellena ``precio_venta_con_iva`` / ``precio_venta_sin_iva`` con la misma lógica
que el ERP viejo:

- **Con IVA:** ``PRECIOS.PRECIO_NETO`` (nombre engañoso: es el final con IVA en pantalla).
- **Sin IVA:** ``PRECIO_NETO / (1 + TASASIVA.PORC_TASA/100)`` según ``ARTICULOS.ID_IVA``.

Matching **100%** por código normalizado (coma → punto, ``Decimal.normalize``), alineado con
``db_precios_ventas/codigo_normalizar.py``. En MSSQL se usa ``LTRIM(RTRIM(CAST(COD_ARTICULO AS VARCHAR(50))))``.

Por defecto **dry-run** (solo reporte). Con ``--apply`` escribe en la SQLite.

Los importes se **redondean a 2 decimales** al comparar y al grabar (pesos).

Referencias en ``--conservar-referencias`` (por defecto ``80``): no se hace ``UPDATE`` ni se
marcan como cambio; se dejan los valores ya cargados en la SQLite.

Requiere: ``pyodbc``, ODBC Driver 18, MSSQL accesible (``config_nakel.MSSQL_CONFIG``).

Ejemplos:

  python3 actualizar_precios_venta_mssql_impuestos.py
  python3 actualizar_precios_venta_mssql_impuestos.py --id-lista 1 --salida-csv reporte.csv
  python3 actualizar_precios_venta_mssql_impuestos.py --apply
  python3 actualizar_precios_venta_mssql_impuestos.py --apply --conservar-referencias ""
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CURSOR_FILES = _REPO_ROOT.parent if _REPO_ROOT.name == "nakel" else Path("/media/klap/raid5/cursor_files")
_DV = _REPO_ROOT / "db_precios_ventas"
for p in (_CURSOR_FILES, _DV):
    if p.is_file():
        continue
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

try:
    import pyodbc  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Instalá pyodbc y ODBC Driver 18 para SQL Server.") from exc

from codigo_normalizar import normalize_code  # noqa: E402

try:
    from config_nakel import MSSQL_CONFIG  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "No se encontró config_nakel (esperado bajo cursor_files). "
        "Ajustá PYTHONPATH o la ruta en el script."
    ) from exc

_DIR = Path(__file__).resolve().parent
_DEFAULT_DB = _DIR / "impuestos.sqlite"
_REPORT_DIR = _DIR / "reportes_precios_venta_mssql"


def _connect_mssql():
    c = MSSQL_CONFIG
    cs = (
        f"DRIVER={{{c['driver']}}};"
        f"SERVER={c['server']};"
        f"DATABASE={c['database']};"
        f"UID={c['username']};"
        f"PWD={c['password']};"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(cs, timeout=c.get("timeout", 30))


def _cargar_articulos_mssql_map(cn, id_lista: int) -> dict[str, tuple[Decimal, Decimal]]:
    """
    codigo_normalizado -> (precio_con_iva, precio_sin_iva).
    Solo artículos que tienen fila en PRECIOS para id_lista.
    """
    sql = """
    SELECT
        LTRIM(RTRIM(CAST(a.COD_ARTICULO AS VARCHAR(50)))) AS codigo_mssql,
        CAST(p.PRECIO_NETO AS DECIMAL(18, 6)) AS precio_neto,
        CAST(COALESCE(t.PORC_TASA, 0) AS DECIMAL(18, 6)) AS porc_tasa
    FROM dbo.ARTICULOS a
    INNER JOIN dbo.PRECIOS p
        ON p.ID_ARTICULO = a.ID_ARTICULO
       AND p.ID_LISTA_PRECIO = ?
    INNER JOIN dbo.TASASIVA t
        ON t.ID_IVA = a.ID_IVA
    """
    cur = cn.cursor()
    cur.execute(sql, (id_lista,))
    out: dict[str, tuple[Decimal, Decimal]] = {}
    for codigo_mssql, precio_neto, porc_tasa in cur.fetchall():
        if codigo_mssql is None:
            continue
        key = normalize_code(codigo_mssql)
        if not key:
            continue
        con_iva = Decimal(str(precio_neto))
        tasa = Decimal(str(porc_tasa))
        if tasa == 0:
            sin_iva = con_iva
        else:
            factor = Decimal("1") + tasa / Decimal("100")
            sin_iva = (con_iva / factor).quantize(Decimal("0.000001"))
        out[key] = (con_iva, sin_iva)
    return out


def _redondear_moneda(x: float | Decimal) -> float:
    return round(float(x), 2)


def _valor_db_redondeado(a: object | None) -> float | None:
    if a is None:
        return None
    return round(float(a), 2)


def _parse_conservar_referencias(s: str) -> frozenset[str]:
    if not s or not str(s).strip():
        return frozenset()
    return frozenset(x.strip() for x in str(s).split(",") if x.strip())


def _ensure_columnas_venta(cur: sqlite3.Cursor) -> None:
    cols = {r[1] for r in cur.execute("PRAGMA table_info(productos)")}
    if "precio_venta_sin_iva" not in cols:
        cur.execute("ALTER TABLE productos ADD COLUMN precio_venta_sin_iva REAL")
    if "precio_venta_con_iva" not in cols:
        cur.execute("ALTER TABLE productos ADD COLUMN precio_venta_con_iva REAL")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Dry-run o apply: precios venta desde MSSQL → impuestos.sqlite"
    )
    ap.add_argument("--db", type=Path, default=_DEFAULT_DB, help="impuestos.sqlite")
    ap.add_argument(
        "--id-lista",
        type=int,
        default=1,
        help="ID_LISTA_PRECIO en PRECIOS (1 = GENERAL)",
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Escribir precio_venta_* en SQLite (sin esto, solo reporte)",
    )
    ap.add_argument(
        "--salida-csv",
        type=Path,
        default=None,
        help="CSV de auditoría (default: reportes_precios_venta_mssql/… si dry-run)",
    )
    ap.add_argument(
        "--conservar-referencias",
        type=str,
        default="80",
        help="Referencias internas (PK en SQLite) que no se tocan, separadas por coma. Vacío = ninguna.",
    )
    args = ap.parse_args()
    conservar = _parse_conservar_referencias(args.conservar_referencias)

    if not args.db.is_file():
        print(f"No existe SQLite: {args.db}", file=sys.stderr)
        return 1

    con_sql = sqlite3.connect(args.db)
    con_sql.row_factory = sqlite3.Row
    cur = con_sql.cursor()
    refs = [r["referencia_interna"] for r in cur.execute("SELECT referencia_interna FROM productos")]
    if not refs:
        print("No hay filas en productos.", file=sys.stderr)
        return 1

    targets = {normalize_code(r): r for r in refs}

    try:
        cn = _connect_mssql()
    except Exception as e:
        print(f"Error conexión MSSQL: {e}", file=sys.stderr)
        return 1

    try:
        mssql_map = _cargar_articulos_mssql_map(cn, args.id_lista)
    finally:
        cn.close()

    rows_out: list[dict[str, object]] = []
    match = 0
    sin_mssql = 0
    actualizados = 0

    if args.apply:
        _ensure_columnas_venta(cur)

    for norm, ref_pk in sorted(targets.items(), key=lambda x: x[1]):
        row_db = cur.execute(
            """
            SELECT precio_venta_sin_iva, precio_venta_con_iva, nombre
            FROM productos WHERE referencia_interna = ?
            """,
            (ref_pk,),
        ).fetchone()
        db_sin = row_db["precio_venta_sin_iva"]
        db_con = row_db["precio_venta_con_iva"]
        nombre = row_db["nombre"]

        trip = mssql_map.get(norm)
        if trip is None:
            sin_mssql += 1
            rows_out.append(
                {
                    "referencia_interna": ref_pk,
                    "codigo_norm": norm,
                    "nombre": nombre,
                    "estado": "sin_precio_mssql",
                    "precio_sin_iva_mssql": "",
                    "precio_con_iva_mssql": "",
                    "precio_sin_iva_db": db_sin,
                    "precio_con_iva_db": db_con,
                    "cambio_sin": "",
                    "cambio_con": "",
                }
            )
            continue

        match += 1
        con_m, sin_m = trip
        fsin = _redondear_moneda(sin_m)
        fcon = _redondear_moneda(con_m)

        if ref_pk in conservar:
            rows_out.append(
                {
                    "referencia_interna": ref_pk,
                    "codigo_norm": norm,
                    "nombre": nombre,
                    "estado": "ok_conservado_manual",
                    "precio_sin_iva_mssql": fsin,
                    "precio_con_iva_mssql": fcon,
                    "precio_sin_iva_db": db_sin,
                    "precio_con_iva_db": db_con,
                    "cambio_sin": False,
                    "cambio_con": False,
                }
            )
            continue

        dbs = _valor_db_redondeado(db_sin)
        dbc = _valor_db_redondeado(db_con)
        cambia_sin = dbs != fsin
        cambia_con = dbc != fcon
        igual = not cambia_sin and not cambia_con

        rows_out.append(
            {
                "referencia_interna": ref_pk,
                "codigo_norm": norm,
                "nombre": nombre,
                "estado": "ok_igual" if igual else "ok_cambia",
                "precio_sin_iva_mssql": fsin,
                "precio_con_iva_mssql": fcon,
                "precio_sin_iva_db": db_sin,
                "precio_con_iva_db": db_con,
                "cambio_sin": cambia_sin,
                "cambio_con": cambia_con,
            }
        )

        if args.apply and (cambia_sin or cambia_con):
            cur.execute(
                """
                UPDATE productos
                SET precio_venta_sin_iva = ?, precio_venta_con_iva = ?
                WHERE referencia_interna = ?
                """,
                (fsin, fcon, ref_pk),
            )
            actualizados += 1

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    csv_path = args.salida_csv
    if csv_path is None:
        _REPORT_DIR.mkdir(parents=True, exist_ok=True)
        suf = "apply" if args.apply else "dry_run"
        csv_path = _REPORT_DIR / f"precios_venta_mssql_{suf}_{ts}.csv"

    fieldnames = [
        "referencia_interna",
        "codigo_norm",
        "nombre",
        "estado",
        "precio_sin_iva_mssql",
        "precio_con_iva_mssql",
        "precio_sin_iva_db",
        "precio_con_iva_db",
        "cambio_sin",
        "cambio_con",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows_out)

    if args.apply:
        cur.execute(
            """
            INSERT INTO meta (clave, valor) VALUES (?, ?)
            ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor
            """,
            ("fuente_precios_venta_mssql", f"PRECIOS.ID_LISTA_PRECIO={args.id_lista}"),
        )
        cur.execute(
            """
            INSERT INTO meta (clave, valor) VALUES (?, ?)
            ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor
            """,
            ("precios_venta_mssql_actualizados", str(actualizados)),
        )
        cur.execute(
            """
            INSERT INTO meta (clave, valor) VALUES (?, ?)
            ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor
            """,
            ("precios_venta_mssql_sin_match", str(sin_mssql)),
        )
        cur.execute(
            """
            INSERT INTO meta (clave, valor) VALUES (?, ?)
            ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor
            """,
            (
                "precios_venta_mssql_conservar_refs",
                ",".join(sorted(conservar)) if conservar else "",
            ),
        )
        con_sql.commit()

    con_sql.close()

    print(f"SQLite: {args.db}")
    print(f"MSSQL lista: {args.id_lista} | Filas en productos: {len(refs)}")
    print(f"Match código en MSSQL (con precio en esa lista): {match}")
    print(f"Sin fila PRECIOS/MSSQL para el código: {sin_mssql}")
    n_cons = sum(1 for r in rows_out if r["estado"] == "ok_conservado_manual")
    if conservar:
        print(f"Referencias conservadas (sin UPDATE): {sorted(conservar)} ({n_cons} filas)")
    if args.apply:
        print(f"Filas UPDATE en SQLite: {actualizados}")
    else:
        cambian = sum(1 for r in rows_out if r["estado"] == "ok_cambia")
        iguales = sum(1 for r in rows_out if r["estado"] == "ok_igual")
        print(f"Dry-run — filas que cambiarían valores: {cambian} | ya iguales: {iguales}")
    print(f"CSV: {csv_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
