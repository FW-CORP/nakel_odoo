#!/usr/bin/env python3
"""
Cotizaciones (sale.order en borrador) en Odoo master_18 desde la SQLite de preventas.

- **Una cotización por número de operación** (`operacion`): mismas líneas que el export
  viejo (un pedido = una operación; suele ser un solo cliente).
- Vendedor: mapeo JSON (`vendedores_mssql_a_user_id_odoo`) o búsqueda por login/email
  con `--user-login` (p. ej. el correo del vendedor en Odoo).
- Cliente: columnas resueltas en SQLite, JSON, o `res_partner_campo_id_mssql` (típico `ref`
  = id cliente MSSQL como texto).
- Producto: `product_id_odoo` en la fila si está ok; si no por `default_code` (con variantes
  698.5 / 698.50). Con **MSSQL + PLU** (`--mssql-plu`, por defecto activo): desambigua por
  código de barras del artículo en Gestion vs Odoo.
- Cliente: si `ref` = id MSSQL no coincide, se intenta **nombre** (razón social de la SQLite)
  o **CUIT** (`vat` en Odoo).

Siempre ejecutar primero sin `--apply`. Con `--apply` crea órdenes; evita duplicar si ya
existe `client_order_ref` = PREVENTA-OP-{operacion}.

Requiere: config_nakel.ODOO_CONFIG_MASTER18, red a Odoo; MSSQL opcional para mapa PLU.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from pedido_sqlite_odoo import parse_fecha_pedido_a_odoo

import xmlrpc.client

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, "/media/klap/raid5/cursor_files")
sys.path.insert(0, str(SCRIPT_DIR))

try:
    from config_nakel import ODOO_CONFIG_MASTER18
except ImportError as e:
    raise SystemExit("Falta config_nakel.py en /media/klap/raid5/cursor_files") from e


def _load_inyectar():
    path = SCRIPT_DIR / "inyectar_pedidos_csv_master18.py"
    spec = importlib.util.spec_from_file_location("iny_ped", path)
    if spec is None or spec.loader is None:
        raise SystemExit("No se pudo cargar inyectar_pedidos_csv_master18.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cargar_mapeo(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def buscar_usuario_por_login_o_email(
    models, uid: int, db: str, password: str, login_o_email: str
) -> list[dict]:
    lg = (login_o_email or "").strip()
    if not lg:
        return []
    dom: list[Any] = [
        "|",
        ("login", "=", lg),
        ("email", "=", lg),
    ]
    return models.execute_kw(
        db,
        uid,
        password,
        "res.users",
        "search_read",
        [dom],
        {"fields": ["id", "name", "login", "email"], "limit": 5},
    )


def orden_ya_existe(
    models, uid: int, db: str, password: str, client_order_ref: str
) -> bool:
    ids = models.execute_kw(
        db,
        uid,
        password,
        "sale.order",
        "search",
        [[("client_order_ref", "=", client_order_ref)]],
        {"limit": 1},
    )
    return bool(ids)


def _solo_digitos(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def resolver_partner_odoo(
    models,
    uid: int,
    db: str,
    password: str,
    *,
    partner_id: int | None,
    cid: int,
    campo_mssql: str | None,
    cli_map: dict[str, int],
    first: sqlite3.Row,
) -> tuple[int | None, list[str]]:
    """ref / JSON / nombre SQLite / CUIT."""
    errs: list[str] = []
    fk = first.keys()

    if partner_id is not None:
        return partner_id, errs
    if cid < 0:
        errs.append("Sin id_cliente_mssql válido en la operación")
        return None, errs

    partner_id = cli_map.get(str(cid))
    if partner_id is not None:
        return int(partner_id), errs

    if campo_mssql and cid >= 0:
        val = str(cid) if campo_mssql == "ref" else cid
        found = models.execute_kw(
            db,
            uid,
            password,
            "res.partner",
            "search_read",
            [[(campo_mssql, "=", val)]],
            {"fields": ["id", "name", "ref", "vat"], "limit": 5},
        )
        if len(found) == 1:
            return int(found[0]["id"]), errs
        if len(found) > 1:
            errs.append(
                f"Cliente MSSQL {cid}: varios partners para {campo_mssql}={val!r}"
            )
            return None, errs

    razon = (
        (first["cliente_razon_social"] if "cliente_razon_social" in fk else "")
        or (first["cliente_display"] if "cliente_display" in fk else "")
        or ""
    ).strip()

    if razon and len(razon) >= 6:
        por_nombre = models.execute_kw(
            db,
            uid,
            password,
            "res.partner",
            "search_read",
            [[("customer_rank", ">", 0), ("name", "ilike", razon)]],
            {"fields": ["id", "name", "ref"], "limit": 5},
        )
        if len(por_nombre) == 1:
            return int(por_nombre[0]["id"]), errs
        if len(por_nombre) == 0:
            toks = [t for t in re.split(r"[\s,.]+", razon) if len(t) >= 4][:2]
            if toks:
                if len(toks) > 1:
                    dom = [
                        "&",
                        "&",
                        ("customer_rank", ">", 0),
                        ("name", "ilike", f"%{toks[0]}%"),
                        ("name", "ilike", f"%{toks[1]}%"),
                    ]
                else:
                    dom = [
                        "&",
                        ("customer_rank", ">", 0),
                        ("name", "ilike", f"%{toks[0]}%"),
                    ]
                por_tokens = models.execute_kw(
                    db,
                    uid,
                    password,
                    "res.partner",
                    "search_read",
                    [dom],
                    {"fields": ["id", "name", "ref"], "limit": 8},
                )
                if len(por_tokens) == 1:
                    return int(por_tokens[0]["id"]), errs

    if "cliente_cuit" in fk and first["cliente_cuit"]:
        dig = _solo_digitos(str(first["cliente_cuit"]))
        if len(dig) >= 8:
            por_vat = models.execute_kw(
                db,
                uid,
                password,
                "res.partner",
                "search_read",
                [
                    [
                        ("customer_rank", ">", 0),
                        ("vat", "ilike", f"%{dig}%"),
                    ]
                ],
                {"fields": ["id", "name", "vat"], "limit": 5},
            )
            if len(por_vat) == 1:
                return int(por_vat[0]["id"]), errs

    if partner_id is None and not errs:
        errs.append(
            f"Cliente MSSQL {cid}: no resuelto en Odoo (ref, nombre de la SQLite ni CUIT único)"
        )

    return None, errs


def resolver_producto_linea(
    ln: sqlite3.Row,
    op: str,
    iny: Any,
    models,
    uid: int,
    db: str,
    password: str,
    mapa_plu: Any | None,
) -> tuple[int | None, str | None]:
    """(product_id, error_msg)."""
    fk = ln.keys()
    code = (ln["codigo_articulo_odoo"] or "").strip()

    if "product_id_odoo" in fk and ln["product_id_odoo"]:
        est = (
            (ln["estado_linea_odoo"] or "").strip()
            if "estado_linea_odoo" in fk
            else ""
        )
        if not est or est == "ok":
            return int(ln["product_id_odoo"]), None

    prods = iny.buscar_producto_por_default_code(models, uid, db, password, code)

    plu: str | None = None
    if mapa_plu is not None:
        cm = None
        if "cod_articulo_mssql" in fk:
            cm = ln["cod_articulo_mssql"]
        plu = mapa_plu.plu_para_linea(
            str(cm).strip() if cm else None,
            code or None,
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
                return int(narrowed[0]["id"]), None

    if len(prods) == 1:
        return int(prods[0]["id"]), None

    if plu:
        by_plu = iny.buscar_producto_por_barcode(
            models, uid, db, password, plu
        )
        if len(by_plu) == 1:
            return int(by_plu[0]["id"]), None
        if len(by_plu) > 1:
            return (
                None,
                f"Varios productos con barcode=PLU {plu!r} (cod {code!r} op {op})",
            )

    if len(prods) == 0:
        return None, f"Sin producto default_code={code!r} (op {op})"
    return (
        None,
        f"Producto ambiguo {code!r} ids {[p['id'] for p in prods]} (op {op})",
    )


def leer_grupos_sqlite(db_path: Path) -> dict[str, list[sqlite3.Row]]:
    """operacion -> filas ordenadas por id."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        """
        SELECT * FROM pedido_lineas
        ORDER BY operacion, id
        """
    )
    rows = cur.fetchall()
    conn.close()
    grupos: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for r in rows:
        op = str(r["operacion"] or "").strip()
        if not op:
            continue
        grupos[op].append(r)
    return dict(grupos)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Inyectar cotizaciones master_18 desde SQLite preventas"
    )
    ap.add_argument(
        "--db",
        type=Path,
        required=True,
        help="Ruta al .sqlite (pedido_lineas)",
    )
    ap.add_argument(
        "--mapeo",
        type=Path,
        default=SCRIPT_DIR / "mapeo_preventas_master18.json",
        help="JSON mapeo vendedores / clientes / campo ref",
    )
    ap.add_argument(
        "--user-login",
        type=str,
        default="",
        help="Login o email Odoo del vendedor: fuerza user_id en todas las cotizaciones "
        "(p. ej. omar.delrincon@hotmail.com). Si se omite, se usa el mapeo por id MSSQL.",
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Crear sale.order en borrador en master_18 (sin este flag solo informe)",
    )
    ap.add_argument(
        "--sin-mssql-plu",
        action="store_true",
        help="No cargar COD_ARTICULO→PLU desde MSSQL (sin desambiguar por barcode)",
    )
    args = ap.parse_args()

    if not args.db.is_file():
        raise SystemExit(f"No existe SQLite: {args.db}")
    if not args.mapeo.is_file():
        raise SystemExit(f"No existe mapeo: {args.mapeo}")

    iny = _load_inyectar()
    mapeo = cargar_mapeo(args.mapeo)
    vend_map: dict[str, int] = {}
    for k, v in mapeo.get("vendedores_mssql_a_user_id_odoo", {}).items():
        if v is not None:
            vend_map[str(k)] = int(v)
    cli_map: dict[str, int] = {}
    for k, v in mapeo.get("clientes_mssql_a_partner_id", {}).items():
        if v is not None:
            cli_map[str(k)] = int(v)
    campo_mssql = mapeo.get("res_partner_campo_id_mssql")
    if campo_mssql is not None and str(campo_mssql).strip() == "":
        campo_mssql = None

    grupos = leer_grupos_sqlite(args.db)
    if not grupos:
        raise SystemExit("No hay filas con operacion en pedido_lineas")

    models, uid, db, password = iny.conectar_odoo()
    print(f"Conectado a Odoo db={db}\n")

    user_forzado: int | None = None
    if args.user_login.strip():
        us = buscar_usuario_por_login_o_email(
            models, uid, db, password, args.user_login.strip()
        )
        if len(us) != 1:
            raise SystemExit(
                f"--user-login {args.user_login!r}: se esperaba 1 usuario, hay {len(us)}"
            )
        user_forzado = int(us[0]["id"])
        print(
            f"Vendedor forzado: id={user_forzado} {us[0].get('name')!r} "
            f"login={us[0].get('login')!r}\n"
        )

    mapa_plu: Any | None = None
    if not args.sin_mssql_plu:
        try:
            from mssql_plu_pedidos import cargar_mapa_cod_articulo_a_plu

            print("Cargando mapa COD_ARTICULO → PLU (MSSQL Gestion)...")
            mapa_plu = cargar_mapa_cod_articulo_a_plu()
            print(
                f"  Artículos con PLU indexados: {len(mapa_plu.por_cod_mssql)}\n"
            )
        except Exception as exc:
            print(f"  Aviso: no se pudo cargar PLU desde MSSQL ({exc})\n")

    reporte: list[dict[str, Any]] = []

    def _sort_op(k: str) -> tuple[int, str]:
        return (int(k), k) if k.isdigit() else (10**9, k)

    for op in sorted(grupos.keys(), key=_sort_op):
        lineas = grupos[op]
        first = lineas[0]
        errores: list[str] = []

        id_v = first["id_vendedor_mssql"]
        id_c = first["id_cliente_mssql"]
        vid = int(id_v) if id_v is not None else -1
        cid = int(id_c) if id_c is not None else -1
        fk = first.keys()

        date_order = None
        if "date_order_odoo" in fk and first["date_order_odoo"]:
            date_order = str(first["date_order_odoo"]).strip() or None
        if not date_order:
            date_order = parse_fecha_pedido_a_odoo(
                first["fecha_pedido"], first["hora_pedido"]
            )
        if not date_order:
            errores.append("Sin fecha válida (date_order_odoo / fecha_pedido)")

        if user_forzado is not None:
            user_id_odoo = user_forzado
        elif "user_id_odoo" in fk and first["user_id_odoo"]:
            user_id_odoo = int(first["user_id_odoo"])
        else:
            user_id_odoo = vend_map.get(str(vid))
        if user_id_odoo is None:
            errores.append(
                f"Vendedor MSSQL {vid}: sin user_id (mapeo JSON o --user-login)"
            )

        partner_id = None
        if "partner_id_odoo" in fk and first["partner_id_odoo"]:
            partner_id = int(first["partner_id_odoo"])
        partner_id, e_part = resolver_partner_odoo(
            models,
            uid,
            db,
            password,
            partner_id=partner_id,
            cid=cid,
            campo_mssql=campo_mssql,
            cli_map=cli_map,
            first=first,
        )
        errores.extend(e_part)

        line_cmds: list[tuple[int, int, dict]] = []

        for ln in lineas:
            qty = ln["cantidad_pedida"]
            try:
                qty_f = float(qty) if qty is not None else 0.0
            except (TypeError, ValueError):
                qty_f = 0.0

            pid, err_p = resolver_producto_linea(
                ln,
                op,
                iny,
                models,
                uid,
                db,
                password,
                mapa_plu,
            )
            if err_p:
                errores.append(err_p)
            if pid is not None:
                line_cmds.append(
                    (0, 0, {"product_id": pid, "product_uom_qty": qty_f})
                )

        if len(line_cmds) != len(lineas):
            errores.append(
                f"Productos: solo {len(line_cmds)}/{len(lineas)} líneas resueltas"
            )

        cref = f"PREVENTA-OP-{op}"
        dup = orden_ya_existe(models, uid, db, password, cref)
        if dup:
            errores.append(f"Ya existe sale.order con client_order_ref={cref!r}")

        reporte.append(
            {
                "operacion": op,
                "client_order_ref": cref,
                "vendedor_mssql": vid,
                "user_id_odoo": user_id_odoo,
                "cliente_mssql": cid,
                "partner_id_odoo": partner_id,
                "date_order": date_order,
                "lineas": len(line_cmds),
                "errores": errores,
                "_line_cmds": line_cmds,
            }
        )

    ok_crear = [b for b in reporte if not b["errores"]]
    con_err = [b for b in reporte if b["errores"]]

    print(f"Operaciones (cotizaciones): {len(reporte)}")
    print(f"  listas para crear: {len(ok_crear)}")
    print(f"  con errores: {len(con_err)}\n")

    for b in reporte[:15]:
        st = "OK" if not b["errores"] else "FALLO"
        print(
            f"[{st}] op={b['operacion']} ref={b['client_order_ref']} "
            f"partner={b['partner_id_odoo']} user={b['user_id_odoo']} "
            f"líneas={b['lineas']} fecha={b['date_order']}"
        )
        if b["errores"]:
            for e in b["errores"]:
                print(f"       - {e}")
    if len(reporte) > 15:
        print(f"... y {len(reporte) - 15} operaciones más (ver JSON)\n")

    out_json = SCRIPT_DIR / (
        f"reporte_inyeccion_sqlite_{Path(args.db).stem}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    # serializable: drop _line_cmds from copy for json, or include
    def _ser(x: dict) -> dict:
        d = {k: v for k, v in x.items() if not k.startswith("_")}
        return d

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(
            {"db": str(args.db), "bloques": [_ser(b) for b in reporte]},
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"Reporte JSON: {out_json}")

    if args.apply:
        creadas = 0
        for b in reporte:
            if b["errores"]:
                print(
                    f"Omitida op={b['operacion']}: {'; '.join(b['errores'])}"
                )
                continue
            vals = {
                "partner_id": b["partner_id_odoo"],
                "user_id": b["user_id_odoo"],
                "date_order": b["date_order"],
                "client_order_ref": b["client_order_ref"],
                "order_line": b["_line_cmds"],
            }
            new_id = models.execute_kw(
                db, uid, password, "sale.order", "create", [vals]
            )
            creadas += 1
            print(f"Creado sale.order id={new_id} op={b['operacion']}")
        print(f"\nTotal creadas: {creadas} / {len(reporte)} operaciones")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
