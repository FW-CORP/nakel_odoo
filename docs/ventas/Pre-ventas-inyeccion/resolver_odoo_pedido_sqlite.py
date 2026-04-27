#!/usr/bin/env python3
"""
Rellena columnas Odoo en una SQLite ya generada (sin volver a pasar CSV/MSSQL).

  python3 resolver_odoo_pedido_sqlite.py --db /ruta/pedido.sqlite

Requiere el mismo JSON que inyectar_pedidos_csv_master18 (vendedores, clientes,
opcional res_partner_campo_id_mssql = \"ref\" para buscar por ID MSSQL).
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pedido_sqlite_odoo import resolver_pedido_sqlite_odoo  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Resolver ids Odoo en pedido_lineas (SQLite)")
    ap.add_argument("--db", type=Path, required=True, help="Ruta al .sqlite")
    ap.add_argument(
        "--mapeo",
        type=Path,
        default=SCRIPT_DIR / "mapeo_preventas_master18.json",
        help="JSON de mapeo preventas",
    )
    args = ap.parse_args()
    if not args.db.is_file():
        raise SystemExit(f"No existe: {args.db}")
    if not args.mapeo.is_file():
        raise SystemExit(f"No existe mapeo: {args.mapeo}")

    conn = sqlite3.connect(args.db)
    try:
        st = resolver_pedido_sqlite_odoo(conn, args.mapeo)
    finally:
        conn.close()
    print(f"Listo. líneas ok={st['linea_ok']}, con incidencias={st['con_algun_fallo']}, total={st['filas']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
