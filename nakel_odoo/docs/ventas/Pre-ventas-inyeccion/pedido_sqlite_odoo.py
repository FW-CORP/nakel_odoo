#!/usr/bin/env python3
"""
Columnas Odoo en SQLite de pedidos + resolución vía XML-RPC (master_18).

Reutiliza conexión y búsquedas de inyectar_pedidos_csv_master18.py (importlib).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent

ODOO_COLUMNS: list[tuple[str, str]] = [
    ("date_order_odoo", "TEXT"),
    ("user_id_odoo", "INTEGER"),
    ("user_name_odoo", "TEXT"),
    ("partner_id_odoo", "INTEGER"),
    ("partner_name_odoo", "TEXT"),
    ("partner_ref_odoo", "TEXT"),
    ("product_id_odoo", "INTEGER"),
    ("product_name_odoo", "TEXT"),
    ("product_default_code_resuelto", "TEXT"),
    ("estado_linea_odoo", "TEXT"),
]


def _load_inyectar_module():
    path = SCRIPT_DIR / "inyectar_pedidos_csv_master18.py"
    if not path.is_file():
        raise SystemExit(f"No se encuentra: {path}")
    spec = importlib.util.spec_from_file_location("inyectar_pedidos_csv", path)
    if spec is None or spec.loader is None:
        raise SystemExit("No se pudo cargar inyectar_pedidos_csv_master18.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["inyectar_pedidos_csv"] = mod
    spec.loader.exec_module(mod)
    return mod


def ensure_odoo_columns(conn) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(pedido_lineas)")}
    for name, typ in ODOO_COLUMNS:
        if name not in cols:
            conn.execute(f"ALTER TABLE pedido_lineas ADD COLUMN {name} {typ}")
    conn.commit()


def ensure_meta_odoo_resuelto(conn) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(meta_carga)")}
    if "odoo_resuelto_en" not in cols:
        conn.execute("ALTER TABLE meta_carga ADD COLUMN odoo_resuelto_en TEXT")
    conn.commit()


def parse_fecha_pedido_a_odoo(fecha_p: str | None, hora_p: str | None) -> str | None:
    """DD/MM/YYYY (+ hora legible opcional) → 'YYYY-MM-DD HH:MM:SS' para date_order."""
    s = (fecha_p or "").strip().strip('"')
    if not s:
        return None
    dt = None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            dt = datetime.strptime(s, fmt)
            break
        except ValueError:
            continue
    if dt is None:
        return None
    h = (hora_p or "").strip()
    if h:
        hn = h.lower().replace("a.m.", "AM").replace("p.m.", "PM")
        for fmt in ("%I:%M:%S %p", "%H:%M:%S", "%H:%M"):
            try:
                t = datetime.strptime(hn, fmt).time()
                dt = datetime.combine(dt.date(), t)
                break
            except ValueError:
                continue
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _mapeo_vendedores_clientes(mapeo: dict[str, Any]) -> tuple[dict[str, int], dict[str, int], str | None]:
    vend: dict[str, int] = {}
    for k, v in mapeo.get("vendedores_mssql_a_user_id_odoo", {}).items():
        if v is not None:
            vend[str(k)] = int(v)
    cli: dict[str, int] = {}
    for k, v in mapeo.get("clientes_mssql_a_partner_id", {}).items():
        if v is not None:
            cli[str(k)] = int(v)
    campo = mapeo.get("res_partner_campo_id_mssql")
    if campo is not None and str(campo).strip() == "":
        campo = None
    return vend, cli, campo


def _valor_partner_domain(campo: str, id_mssql: int) -> Any:
    if campo == "ref":
        return str(id_mssql)
    return id_mssql


def resolver_pedido_sqlite_odoo(conn, mapeo_path: Path) -> dict[str, int]:
    """
    Rellena columnas *odoo en pedido_lineas. Devuelve contadores.
    """
    ensure_odoo_columns(conn)
    ensure_meta_odoo_resuelto(conn)
    iny = _load_inyectar_module()
    mapeo = json.loads(mapeo_path.read_text(encoding="utf-8"))
    vend_map, cli_map, campo_mssql = _mapeo_vendedores_clientes(mapeo)

    models, uid, db, password = iny.conectar_odoo()

    mapa_plu: Any | None = None
    try:
        from mssql_plu_pedidos import cargar_mapa_cod_articulo_a_plu

        mapa_plu = cargar_mapa_cod_articulo_a_plu()
    except Exception:
        mapa_plu = None

    partner_cache: dict[int, tuple[int | None, str | None, str | None, str | None]] = {}
    product_cache: dict[str, tuple[int | None, str | None, str | None, str | None]] = {}

    def resolve_partner(cid: int | None) -> tuple[int | None, str | None, str | None, str | None]:
        if cid is None:
            return None, None, None, "sin_id_cliente"
        if cid in partner_cache:
            return partner_cache[cid]
        pid = cli_map.get(str(cid))
        pname = None
        pref = None
        err = None
        if pid is not None:
            rows = models.execute_kw(
                db,
                uid,
                password,
                "res.partner",
                "search_read",
                [[("id", "=", pid)]],
                {"fields": ["id", "name", "ref"], "limit": 1},
            )
            if rows:
                pname = rows[0].get("name")
                pref = rows[0].get("ref")
        elif campo_mssql:
            dom = [(campo_mssql, "=", _valor_partner_domain(campo_mssql, cid))]
            found = models.execute_kw(
                db,
                uid,
                password,
                "res.partner",
                "search_read",
                [dom],
                {"fields": ["id", "name", "ref"], "limit": 5},
            )
            if len(found) == 1:
                pid = found[0]["id"]
                pname = found[0].get("name")
                pref = found[0].get("ref")
            elif not found:
                err = "partner_no_encontrado"
            else:
                err = "partner_ambiguo"
        else:
            err = "partner_sin_mapeo_ni_campo"
        partner_cache[cid] = (pid, pname, pref, err)
        return partner_cache[cid]

    def resolve_product(
        code: str, cod_mssql: str | None
    ) -> tuple[int | None, str | None, str | None, str | None]:
        key = (code or "").strip()
        if not key:
            return None, None, None, "sin_codigo_producto"
        if key in product_cache:
            return product_cache[key]

        prods = iny.buscar_producto_por_default_code(
            models, uid, db, password, key
        )

        plu: str | None = None
        if mapa_plu is not None:
            plu = mapa_plu.plu_para_linea(
                (cod_mssql or "").strip() or None,
                key or None,
            )

        if len(prods) > 1 and plu:
            pnorm = iny.limpiar_codigo_barras(plu)
            if pnorm:
                narrowed = [
                    p
                    for p in prods
                    if iny.limpiar_codigo_barras(p.get("barcode")) == pnorm
                ]
                if len(narrowed) == 1:
                    p = narrowed[0]
                    product_cache[key] = (
                        int(p["id"]),
                        p.get("name"),
                        (p.get("default_code") or "").strip() or None,
                        None,
                    )
                    return product_cache[key]

        if len(prods) == 1:
            p = prods[0]
            product_cache[key] = (
                int(p["id"]),
                p.get("name"),
                (p.get("default_code") or "").strip() or None,
                None,
            )
            return product_cache[key]

        if plu:
            by_plu = iny.buscar_producto_por_barcode(
                models, uid, db, password, plu
            )
            if len(by_plu) == 1:
                p = by_plu[0]
                product_cache[key] = (
                    int(p["id"]),
                    p.get("name"),
                    (p.get("default_code") or "").strip() or None,
                    None,
                )
                return product_cache[key]
            if len(by_plu) > 1:
                product_cache[key] = (
                    None,
                    None,
                    None,
                    "producto_ambiguo_plu",
                )
                return product_cache[key]

        if not prods:
            product_cache[key] = (None, None, None, "producto_no_encontrado")
        else:
            product_cache[key] = (None, None, None, "producto_ambiguo")
        return product_cache[key]

    cur = conn.execute(
        """
        SELECT id, id_vendedor_mssql, id_cliente_mssql, codigo_articulo_odoo,
               cod_articulo_mssql, fecha_pedido, hora_pedido
        FROM pedido_lineas
        ORDER BY id
        """
    )
    rows = cur.fetchall()
    stats = {
        "filas": 0,
        "linea_ok": 0,
        "con_algun_fallo": 0,
    }

    for row in rows:
        rid, id_v, id_c, cod_odoo, cod_ms, fecha_p, hora_p = row
        stats["filas"] += 1

        uid_o = vend_map.get(str(id_v)) if id_v is not None else None
        uname = None
        if uid_o is not None:
            users = models.execute_kw(
                db,
                uid,
                password,
                "res.users",
                "search_read",
                [[("id", "=", uid_o)]],
                {"fields": ["id", "name", "login"], "limit": 1},
            )
            if users:
                uname = users[0].get("name")

        pid_o, pname_o, pref_o, p_err = resolve_partner(id_c)
        cms = str(cod_ms).strip() if cod_ms is not None else None
        prod_id, prod_name, prod_dc, pr_err = resolve_product(
            cod_odoo or "", cms
        )
        date_o = parse_fecha_pedido_a_odoo(fecha_p, hora_p)

        partes: list[str] = []
        if uid_o is None:
            partes.append("falta_vendedor")
        if p_err:
            partes.append(p_err)
        if pr_err:
            partes.append(pr_err)
        if date_o is None and (fecha_p or "").strip():
            partes.append("fecha_invalida")
        elif date_o is None:
            partes.append("falta_fecha")

        estado = "ok" if not partes else "+".join(partes)
        if estado == "ok":
            stats["linea_ok"] += 1
        else:
            stats["con_algun_fallo"] += 1

        conn.execute(
            """
            UPDATE pedido_lineas SET
              date_order_odoo = ?,
              user_id_odoo = ?,
              user_name_odoo = ?,
              partner_id_odoo = ?,
              partner_name_odoo = ?,
              partner_ref_odoo = ?,
              product_id_odoo = ?,
              product_name_odoo = ?,
              product_default_code_resuelto = ?,
              estado_linea_odoo = ?
            WHERE id = ?
            """,
            (
                date_o,
                uid_o,
                uname,
                pid_o,
                pname_o,
                pref_o,
                prod_id,
                prod_name,
                prod_dc,
                estado,
                rid,
            ),
        )

    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "UPDATE meta_carga SET odoo_resuelto_en = ? WHERE id = 1", (now,)
    )
    conn.commit()
    return stats
