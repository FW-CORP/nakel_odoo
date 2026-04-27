#!/usr/bin/env python3
"""
Inyección de pedidos desde CSV hacia Odoo (``master_18`` o ``master_dev`` con ``--master-dev``).

Formato CSV esperado (cabecera en fila 1), igual que ``Pedidos.csv`` del ensayo:
  A: Numero de Operacion
  B: Vendedor (ID_VENDEDOR MSSQL)
  C: Cliente (ID_CLIENTE MSSQL)
  D: Ruta (ignorado)
  E: Código artículo (si viene sin coma: últimos 2 dígitos = decimales → 103920 → 1039.20)
  F: Cantidad
  G: ignorado
  H: Fecha pedido (DD/MM/YYYY)
  I: Hora opcional (ej. ``02:40:18 p.m.``) — con ``--sin-hora`` o ``--agrupar-por-cliente`` no se usa (00:00)

Exportes **sin cabecera** (solo filas de datos): ``--sin-cabecera`` (mismo orden de columnas).

``--agrupar-por-cliente``: una cotización por cliente (C); la columna A no agrupa.
``--mapeo-archivo-vendedor``: JSON con patrones en el **nombre del archivo** → ``vendedor_mssql``.
En el JSON, ``codigo_csv_a_default_code_odoo`` mapea el código normalizado desde la columna E al ``default_code`` real en Odoo cuando difieren (ej. Gestion 8372.10 → Odoo 587).

Siempre usar primero --dry-run. --apply crea sale.order en borrador.

Mapeo MSSQL→Odoo: archivo JSON (ver mapeo_preventas_master18.example.json).
Documentación vendedores principales: modulos/contactos/documentacion/RESUMEN_VENDEDORES_PRINCIPALES.md
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import xmlrpc.client

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, "/media/klap/raid5/cursor_files")

try:
    from config_nakel import ODOO_CONFIG_MASTER18, ODOO_CONFIG_MASTER_DEV
except ImportError as e:
    raise SystemExit("Falta config_nakel.py en /media/klap/raid5/cursor_files") from e


def aplicar_mapeo_codigo_producto(
    code_csv: str, mapeo: dict[str, Any]
) -> tuple[str, str | None]:
    """
    codigo_csv_a_default_code_odoo en JSON: clave = código normalizado desde CSV (p. ej. 8372.10),
    valor = default_code real en Odoo (p. ej. 587) cuando Gestion y Odoo no coinciden.
    """
    raw_map = mapeo.get("codigo_csv_a_default_code_odoo")
    if not isinstance(raw_map, dict) or not code_csv:
        return code_csv, None
    dest = raw_map.get(code_csv)
    if dest is None:
        return code_csv, None
    dest_s = str(dest).strip()
    if not dest_s:
        return code_csv, None
    return dest_s, code_csv


def articulo_csv_a_default_code(raw: Any) -> str:
    """Convierte código numérico 'comido' por CSV a default_code tipo XXXX.XX."""
    if raw is None or raw == "":
        return ""
    s = str(raw).strip().replace(",", ".")
    if not s:
        return ""
    if "." in s:
        try:
            d = Decimal(s)
            return format(d.normalize(), "f")
        except InvalidOperation:
            return s
    try:
        n = int(Decimal(s))
    except (InvalidOperation, ValueError):
        return s
    entero = n // 100
    frac = n % 100
    return f"{entero}.{frac:02d}"


def parse_fecha_dd_mm_yyyy(s: str) -> str | None:
    s = (s or "").strip().strip('"')
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return None


def _parse_hora_ampm(hora_raw: str) -> tuple[int, int, int] | None:
    """Devuelve (h,m,s) 24h desde '02:40:18 p.m.' o '12:22:23 a.m.'."""
    h = (hora_raw or "").strip().strip('"')
    if not h:
        return None
    is_pm = bool(re.search(r"p\.?\s*m\.?", h, re.I))
    is_am = bool(re.search(r"a\.?\s*m\.?", h, re.I))
    core = re.sub(r"\s*[ap]\.?\s*m\.?\s*$", "", h, flags=re.I).strip()
    m = re.match(r"^(\d{1,2})[:.](\d{2})[:.](\d{2})$", core)
    if not m:
        m = re.match(r"^(\d{1,2})[:.](\d{2})$", core)
        if not m:
            return None
        hh, mm = int(m.group(1)), int(m.group(2))
        ss = 0
    else:
        hh, mm, ss = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if is_pm and hh != 12:
        hh += 12
    if is_am and hh == 12:
        hh = 0
    return hh, mm, ss


def combinar_fecha_y_hora(fecha_s: str, hora_s: str | None) -> str | None:
    """``date_order`` Odoo: fecha DD/MM/YYYY + hora opcional (columna I)."""
    fecha_s = (fecha_s or "").strip().strip('"')
    if not fecha_s:
        return None
    d: datetime | None = None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            d = datetime.strptime(fecha_s, fmt)
            break
        except ValueError:
            continue
    if d is None:
        return None
    tpart = _parse_hora_ampm(str(hora_s or "").strip())
    if tpart:
        d = d.replace(hour=tpart[0], minute=tpart[1], second=tpart[2])
    return d.strftime("%Y-%m-%d %H:%M:%S")


_CABECERA_PEDIDOS = [
    "Numero de Operacion",
    "Vendedor",
    "Cliente",
    "Ruta",
    "Cod Aritculo",
    "Cantidad",
    "?",
    "Fecha",
    "hora",
]


def leer_pedidos_csv(path: Path, sin_cabecera: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        if sin_cabecera:
            reader = csv.reader(f)
            for parts in reader:
                if not parts or all(not str(c).strip() for c in parts):
                    continue
                d: dict[str, Any] = {}
                for i, key in enumerate(_CABECERA_PEDIDOS):
                    d[key] = parts[i].strip() if i < len(parts) else ""
                rows.append(d)
            return rows
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(dict(r))
    return rows


def cargar_mapeo(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"No existe archivo de mapeo: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def conectar_odoo(*, master_dev: bool = False):
    cfg = ODOO_CONFIG_MASTER_DEV if master_dev else ODOO_CONFIG_MASTER18
    url = cfg["url"].rstrip("/")
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(cfg["db"], cfg["username"], cfg["password"], {})
    if not uid:
        raise SystemExit(
            f"Autenticación Odoo fallida ({cfg.get('db', '')} / {'master_dev' if master_dev else 'master_18'})."
        )
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    return models, uid, cfg["db"], cfg["password"]


def buscar_partner_por_campo_mssql(
    models, uid: int, db: str, password: str, campo: str, id_mssql: int
) -> list[dict]:
    val: str | int = str(id_mssql) if campo == "ref" else id_mssql
    dom = [(campo, "=", val)]
    return models.execute_kw(
        db,
        uid,
        password,
        "res.partner",
        "search_read",
        [dom],
        {"fields": ["id", "name", campo], "limit": 5},
    )


def _solo_digitos_identificacion(s: str) -> str:
    return "".join(c for c in (s or "") if c.isdigit())


def buscar_partners_por_vat_normalizado(
    models, uid: int, db: str, password: str, vat_raw: str
) -> list[dict]:
    """Odoo suele guardar CUIT sin guiones (ej. ``20162002091``)."""
    d = _solo_digitos_identificacion(vat_raw.replace("CUIT", "").replace("cuit", ""))
    if not d:
        return []
    return models.execute_kw(
        db,
        uid,
        password,
        "res.partner",
        "search_read",
        [[("vat", "=", d)]],
        {"fields": ["id", "name", "vat"], "limit": 24},
    )


def filtrar_partners_por_nombre_contiene(
    partners: list[dict], subcadena: str | None
) -> list[dict]:
    if len(partners) <= 1 or not (subcadena or "").strip():
        return partners
    h = subcadena.strip().upper()
    hit = [p for p in partners if h in ((p.get("name") or "").upper())]
    return hit if hit else partners


def resolver_partner_cliente(
    models,
    uid: int,
    db: str,
    password: str,
    cid: int,
    *,
    partner_id_json: int | None,
    campo_mssql: str | None,
    vat_raw: str | None,
    nombre_contiene: str | None,
) -> tuple[int | None, list[str]]:
    """
    1) ``clientes_mssql_a_partner_id`` en JSON
    2) ``clientes_mssql_a_vat`` + opcional ``clientes_mssql_vat_nombre_contiene``
    3) ``res_partner_campo_id_mssql`` (p. ej. ref = id MSSQL como texto)
    """
    errores: list[str] = []
    if partner_id_json is not None:
        return int(partner_id_json), errores

    if vat_raw:
        found = buscar_partners_por_vat_normalizado(
            models, uid, db, password, vat_raw
        )
        found = filtrar_partners_por_nombre_contiene(found, nombre_contiene)
        if len(found) == 1:
            return int(found[0]["id"]), errores
        if len(found) > 1:
            nombres = ", ".join(f"{p['id']}:{p.get('name')}" for p in found[:8])
            errores.append(
                f"Cliente MSSQL {cid}: varios partners con mismo vat ({len(found)}). "
                f"Ajustar clientes_mssql_vat_nombre_contiene o clientes_mssql_a_partner_id. Ej.: {nombres}"
            )
            return None, errores
        # 0 resultados: seguir con ref / error genérico

    if campo_mssql:
        found = buscar_partner_por_campo_mssql(
            models, uid, db, password, campo_mssql, cid
        )
        if len(found) == 1:
            return int(found[0]["id"]), errores
        if not found:
            errores.append(
                f"Cliente MSSQL {cid}: sin partner con {campo_mssql}={cid!r}"
            )
        else:
            errores.append(
                f"Cliente MSSQL {cid}: múltiples partners ({len(found)}) para {campo_mssql}"
            )
        return None, errores

    suf = f" o campo {campo_mssql!r}" if campo_mssql else ""
    errores.append(
        f"Cliente MSSQL {cid}: definir partner en JSON "
        f"(clientes_mssql_a_partner_id, clientes_mssql_a_vat{suf})"
    )
    return None, errores


def _variantes_codigo_producto(code: str) -> list[str]:
    """Variantes de default_code para matchear Odoo (espacios, .00 = entero, 698.5 vs 698.50)."""
    code = (code or "").strip()
    if not code:
        return []
    out: list[str] = []
    seen: set[str] = set()

    def add_raw(c: str) -> None:
        if c and c not in seen:
            seen.add(c)
            out.append(c)

    add_raw(code)
    add_raw(f" {code}")  # Odoo a veces guarda default_code con espacio inicial
    try:
        d = Decimal(code.replace(",", "."))
        if d == d.to_integral_value():
            s_int = str(int(d))
            add_raw(s_int)
            add_raw(f" {s_int}")
        else:
            # Misma magnitud con distintos decimales visibles (698.5 / 698.50)
            n = format(d.normalize(), "f")
            add_raw(n)
            add_raw(n.rstrip("0").rstrip("."))
            q2 = f"{d:.2f}"
            add_raw(q2)
            add_raw(q2.rstrip("0").rstrip("."))
    except (InvalidOperation, ValueError):
        pass
    return out


def _default_code_cmp(dc: object) -> str:
    return (str(dc) if dc is not None else "").strip().replace(",", ".")


def reducir_ambiguedad_default_code(
    prods: list[dict], code: str, variantes: list[str]
) -> list[dict]:
    """
    Odoo puede tener variantes con el mismo valor numérico pero distinto texto
    (p. ej. `1243.9` vs `1243.90`). El dominio `in` variantes devuelve ambas;
    priorizamos la coincidencia **literal** con el código pedido y luego con cada variante.
    """
    if len(prods) <= 1:
        return prods
    c0 = _default_code_cmp(code)
    if c0:
        exact0 = [p for p in prods if _default_code_cmp(p.get("default_code")) == c0]
        if len(exact0) == 1:
            return exact0
    for v in variantes:
        vv = _default_code_cmp(v)
        if not vv:
            continue
        hit = [p for p in prods if _default_code_cmp(p.get("default_code")) == vv]
        if len(hit) == 1:
            return hit
    return prods


def buscar_producto_por_default_code(
    models, uid: int, db: str, password: str, code: str
) -> list[dict]:
    variantes = _variantes_codigo_producto(code)
    if not variantes:
        return []
    dom: list[Any] = [("default_code", "in", variantes)]
    prods = models.execute_kw(
        db,
        uid,
        password,
        "product.product",
        "search_read",
        [dom],
        {"fields": ["id", "name", "default_code", "uom_id", "barcode"], "limit": 16},
    )
    return reducir_ambiguedad_default_code(prods, code, variantes)


def _limpiar_barcode_plu(val: object) -> str:
    if val is None:
        return ""
    t = str(val).replace("\ufeff", "").replace("\u00a0", " ")
    return "".join(ch for ch in t if not ch.isspace())


def limpiar_codigo_barras(val: object) -> str:
    """PLU/EAN sin espacios (útil para cruzar con MSSQL)."""
    return _limpiar_barcode_plu(val)


def variantes_barcode_plu(barcode: str) -> list[str]:
    """PLU numérico: probar tal cual y sin ceros a la izquierda (Odoo vs MSSQL)."""
    bc = _limpiar_barcode_plu(barcode)
    if not bc:
        return []
    out: list[str] = []
    seen: set[str] = set()

    def add(x: str) -> None:
        if x and x not in seen:
            seen.add(x)
            out.append(x)

    add(bc)
    if bc.isdigit():
        t = bc.lstrip("0")
        add(t or "0")
    return out


def buscar_producto_por_barcode(
    models, uid: int, db: str, password: str, barcode: str
) -> list[dict]:
    """Código de barras en variante (PLU / EAN); prueba PLU tal cual y sin ceros iniciales."""
    for bc in variantes_barcode_plu(barcode):
        rows = models.execute_kw(
            db,
            uid,
            password,
            "product.product",
            "search_read",
            [[("barcode", "=", bc)]],
            {"fields": ["id", "name", "default_code", "barcode", "uom_id"], "limit": 8},
        )
        if rows:
            return rows
    return []


def agrupar_por_operacion(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grupos: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        op = (r.get("Numero de Operacion") or r.get("Numero de Operacion".lower()) or "").strip()
        if not op:
            op = str(r.get(list(r.keys())[0], "")).strip()
        grupos[op].append(r)
    return dict(grupos)


def agrupar_por_cliente(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Una cotización por cliente dentro del archivo (ignora nº transacción col. A)."""
    grupos: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        cid = str(r.get("Cliente", "")).strip()
        if not cid:
            cid = "_sin_cliente"
        grupos[cid].append(r)
    return dict(grupos)


def fecha_minima_grupo(lineas: list[dict[str, Any]], sin_hora: bool) -> str | None:
    best: str | None = None
    for ln in lineas:
        fr = str(ln.get("Fecha", "")).strip()
        if sin_hora:
            d = parse_fecha_dd_mm_yyyy(fr)
        else:
            hr = ln.get("hora", "") or ln.get("Hora", "")
            d = combinar_fecha_y_hora(fr, str(hr) if hr else None) or parse_fecha_dd_mm_yyyy(fr)
        if not d:
            continue
        if best is None or d < best:
            best = d
    return best


def vendedor_mssql_desde_nombre_archivo(csv_path: Path, mapeo_path: Path | None) -> int | None:
    if mapeo_path is None or not mapeo_path.is_file():
        return None
    with open(mapeo_path, encoding="utf-8") as f:
        data = json.load(f)
    stem = csv_path.stem.lower()
    for p in data.get("patrones", []):
        needle = (p.get("contiene") or "").lower()
        if needle and needle in stem:
            try:
                return int(p["vendedor_mssql"])
            except (KeyError, TypeError, ValueError):
                continue
    return None


def slug_archivo_para_ref(path: Path) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", path.stem).strip("-").upper()
    return s[:60] or "IMPORT"


def main() -> None:
    ap = argparse.ArgumentParser(description="Inyectar Pedidos CSV en Odoo (master_18 o master_dev)")
    ap.add_argument(
        "--csv",
        type=Path,
        default=SCRIPT_DIR / "Pedidos.csv",
        help="Ruta al CSV",
    )
    ap.add_argument(
        "--mapeo",
        type=Path,
        default=SCRIPT_DIR / "mapeo_preventas_master18.json",
        help="JSON con vendedores_mssql_a_user_id_odoo y clientes_mssql_a_partner_id",
    )
    ap.add_argument(
        "--mapeo-archivo-vendedor",
        type=Path,
        default=None,
        help="JSON con lista 'patrones': [{contiene, vendedor_mssql}] — el nombre del CSV debe contener 'contiene'",
    )
    ap.add_argument(
        "--master-dev",
        action="store_true",
        help="Conectar a master_dev (config_nakel.ODOO_CONFIG_MASTER_DEV)",
    )
    ap.add_argument(
        "--agrupar-por-cliente",
        action="store_true",
        help="Ignorar col. A (transacción): una cotización por cliente dentro del archivo",
    )
    ap.add_argument(
        "--sin-hora",
        action="store_true",
        help="date_order solo con fecha (00:00); sin combinar columna I",
    )
    ap.add_argument(
        "--sin-cabecera",
        action="store_true",
        help="CSV sin fila de títulos (mismo orden que Pedidos.csv del ensayo)",
    )
    ap.add_argument(
        "--client-order-ref-prefix",
        type=str,
        default="MSSQL-OP-",
        help="Prefijo client_order_ref (evitar choque entre lotes)",
    )
    ap.add_argument("--dry-run", action="store_true", help="Solo analizar y reportar (recomendado)")
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Crear sale.order en borrador (requiere mapeo completo y productos resueltos)",
    )
    ap.add_argument(
        "--omitir-lineas-sin-producto",
        action="store_true",
        help="No fallar por default_code inexistente: omitir esa línea (avisos en reporte)",
    )
    args = ap.parse_args()

    if args.apply and args.dry_run:
        raise SystemExit("Usar solo uno de --dry-run o --apply")
    if not args.apply and not args.dry_run:
        args.dry_run = True

    if not args.csv.is_file():
        raise SystemExit(f"No existe CSV: {args.csv}")

    mapeo = cargar_mapeo(args.mapeo)
    vend_map: dict[str, int] = {}
    for k, v in mapeo.get("vendedores_mssql_a_user_id_odoo", {}).items():
        if v is None:
            continue
        vend_map[str(k)] = int(v)
    cli_map_raw = mapeo.get("clientes_mssql_a_partner_id", {})
    cli_map: dict[str, Any] = {}
    for k, v in cli_map_raw.items():
        if v is None:
            continue
        cli_map[str(k)] = int(v)
    vat_por_cliente: dict[str, str] = {
        str(k): str(v).strip()
        for k, v in mapeo.get("clientes_mssql_a_vat", {}).items()
        if v is not None and str(v).strip()
    }
    vat_nombre_hint: dict[str, str] = {
        str(k): str(v).strip()
        for k, v in mapeo.get("clientes_mssql_vat_nombre_contiene", {}).items()
        if v is not None and str(v).strip()
    }
    campo_mssql = mapeo.get("res_partner_campo_id_mssql")

    rows = leer_pedidos_csv(args.csv, sin_cabecera=args.sin_cabecera)
    if args.agrupar_por_cliente:
        grupos = agrupar_por_cliente(rows)
    else:
        grupos = agrupar_por_operacion(rows)

    vid_desde_archivo: int | None = None
    if args.mapeo_archivo_vendedor is not None:
        vid_desde_archivo = vendedor_mssql_desde_nombre_archivo(
            args.csv.resolve(), args.mapeo_archivo_vendedor.resolve()
        )
        if vid_desde_archivo is None:
            raise SystemExit(
                f"Ningún patrón de --mapeo-archivo-vendedor coincide con el nombre del archivo: {args.csv.name}"
            )

    models, uid, db, password = conectar_odoo(master_dev=args.master_dev)
    entorno = "master_dev" if args.master_dev else "master_18"
    print(f"✅ Conectado a Odoo ({entorno}) db={db}\n")

    reporte: dict[str, Any] = {
        "csv": str(args.csv),
        "entorno_odoo": entorno,
        "agrupar_por_cliente": args.agrupar_por_cliente,
        "grupos": len(grupos),
        "detalle": [],
    }

    slug_ref = slug_archivo_para_ref(args.csv.resolve())

    for gkey, lineas in sorted(grupos.items(), key=lambda x: x[0]):
        primera = lineas[0]

        if vid_desde_archivo is not None:
            vid = vid_desde_archivo
        else:
            try:
                vid = int(str(primera.get("Vendedor", "")).strip())
            except ValueError:
                vid = -1

        if args.agrupar_por_cliente:
            if gkey == "_sin_cliente":
                cid = -1
            else:
                try:
                    cid = int(str(gkey).strip())
                except ValueError:
                    cid = -1
            grupo_label = f"CLI-{gkey}"
            ref_suffix = f"{slug_ref}-CLI-{gkey}"
        else:
            try:
                cid = int(str(primera.get("Cliente", "")).strip())
            except ValueError:
                cid = -1
            grupo_label = str(gkey)
            ref_suffix = str(gkey)

        if args.agrupar_por_cliente or args.sin_hora:
            date_order = fecha_minima_grupo(lineas, sin_hora=True)
        else:
            fecha_raw = primera.get("Fecha", "")
            hora_raw = primera.get("hora", "") or primera.get("Hora", "")
            date_order = combinar_fecha_y_hora(str(fecha_raw), str(hora_raw) if hora_raw else None)
            if not date_order:
                date_order = parse_fecha_dd_mm_yyyy(str(fecha_raw))

        user_id = vend_map.get(str(vid))
        partner_id_json = cli_map.get(str(cid))
        if partner_id_json is not None:
            try:
                partner_id_json = int(partner_id_json)
            except (TypeError, ValueError):
                partner_id_json = None

        bloque: dict[str, Any] = {
            "grupo": grupo_label,
            "operacion": grupo_label,
            "ref_suffix": ref_suffix,
            "vendedor_mssql": vid,
            "vendedor_desde_archivo": vid_desde_archivo is not None,
            "user_id_odoo": user_id,
            "cliente_mssql": cid,
            "partner_id_odoo": None,
            "date_order": date_order,
            "lineas": [],
            "errores": [],
            "avisos": [],
        }

        if user_id is None:
            bloque["errores"].append(
                f"Vendedor MSSQL {vid} sin mapeo en JSON (los 6 principales en doc son 2,5,6,9,16,17; el 3 no está en esa lista)."
            )

        vat_raw = vat_por_cliente.get(str(cid))
        nombre_vat_hint = vat_nombre_hint.get(str(cid))
        partner_id, perrs = resolver_partner_cliente(
            models,
            uid,
            db,
            password,
            cid,
            partner_id_json=partner_id_json,
            campo_mssql=campo_mssql if isinstance(campo_mssql, str) else None,
            vat_raw=vat_raw,
            nombre_contiene=nombre_vat_hint,
        )
        bloque["partner_id_odoo"] = partner_id
        bloque["errores"].extend(perrs)

        if not date_order:
            bloque["errores"].append("Fecha inválida en el grupo (revisar columna H)")

        for ln in lineas:
            raw_cod = ln.get("Cod Aritculo") or ln.get("Cod Articulo")
            code_csv = articulo_csv_a_default_code(raw_cod)
            code_odoo, _ = aplicar_mapeo_codigo_producto(code_csv, mapeo)
            try:
                qty = float(str(ln.get("Cantidad", "0")).replace(",", "."))
            except ValueError:
                qty = 0.0
            prod = buscar_producto_por_default_code(models, uid, db, password, code_odoo)
            entry = {
                "raw_codigo_csv": raw_cod,
                "codigo_csv_normalizado": code_csv,
                "default_code": code_odoo,
                "cantidad": qty,
                "productos_odoo": [{"id": p["id"], "name": p["name"]} for p in prod],
                "omitida": False,
            }
            if len(prod) == 0:
                if args.omitir_lineas_sin_producto:
                    entry["omitida"] = True
                    entry["motivo_omitida"] = "sin_producto"
                    bloque["avisos"].append(
                        f"Omitida línea sin producto Odoo default_code={code_odoo!r}"
                        + (f" (CSV {code_csv!r})" if code_csv != code_odoo else "")
                    )
                else:
                    bloque["errores"].append(
                        f"Sin producto default_code={code_odoo!r}"
                        + (f" (código CSV normalizado {code_csv!r})" if code_csv != code_odoo else "")
                    )
            elif len(prod) > 1:
                bloque["errores"].append(
                    f"Varias variantes para default_code={code_odoo!r}: ids {[p['id'] for p in prod]}"
                )
            bloque["lineas"].append(entry)

        if args.omitir_lineas_sin_producto and bloque["lineas"]:
            if all(li.get("omitida") for li in bloque["lineas"]):
                bloque["errores"].append(
                    "Todas las líneas quedaron omitidas (ningún producto resuelto en Odoo)"
                )

        reporte["detalle"].append(bloque)

    # Imprimir resumen
    for b in reporte["detalle"]:
        print(f"--- Grupo {b['grupo']} ---")
        src_v = " (desde nombre archivo)" if b.get("vendedor_desde_archivo") else ""
        print(f"  Vendedor MSSQL: {b['vendedor_mssql']}{src_v} → user_id Odoo: {b['user_id_odoo']}")
        print(f"  Cliente MSSQL: {b['cliente_mssql']} → partner_id: {b['partner_id_odoo']}")
        print(f"  date_order: {b['date_order']}")
        for li in b["lineas"]:
            ps = li["productos_odoo"]
            pid = ps[0]["id"] if len(ps) == 1 else None
            suf = " [omitida]" if li.get("omitida") else ""
            csv_n = li.get("codigo_csv_normalizado", li["default_code"])
            suf_csv = (
                f" [CSV {csv_n}]" if csv_n != li["default_code"] else ""
            )
            print(
                f"  • {li['default_code']} x {li['cantidad']} → product_id={pid} ({len(ps)} matches){suf_csv}{suf}"
            )
        for a in b.get("avisos") or []:
            print(f"  ⚠ {a}")
        if b["errores"]:
            print("  ERRORES:")
            for e in b["errores"]:
                print(f"    - {e}")
        print()

    out_json = SCRIPT_DIR / f"reporte_preventas_dryrun_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2)
    print(f"📄 Reporte JSON: {out_json}")

    if args.apply:
        def _grupo_aplicable(b: dict[str, Any]) -> bool:
            if b["errores"] or not b["user_id_odoo"] or not b["partner_id_odoo"] or not b["date_order"]:
                return False
            return any(
                not li.get("omitida") and len(li.get("productos_odoo") or []) == 1
                for li in b["lineas"]
            )

        aplicables = [b for b in reporte["detalle"] if _grupo_aplicable(b)]
        omitidos = [b for b in reporte["detalle"] if not _grupo_aplicable(b)]
        if not aplicables:
            raise SystemExit(
                "No se crearon órdenes: ningún grupo aplicable (revisar errores del dry-run)."
            )
        for b in omitidos:
            errs = b.get("errores") or []
            msg = errs[0] if errs else "sin líneas válidas"
            print(f"⚠ Omitido grupo {b['grupo']}: {msg}")

        for b in aplicables:
            line_cmds = []
            for li in b["lineas"]:
                if li.get("omitida"):
                    continue
                pid = li["productos_odoo"][0]["id"]
                line_cmds.append(
                    (
                        0,
                        0,
                        {
                            "product_id": pid,
                            "product_uom_qty": li["cantidad"],
                        },
                    )
                )
            vals = {
                "partner_id": b["partner_id_odoo"],
                "user_id": b["user_id_odoo"],
                "date_order": b["date_order"],
                "client_order_ref": f"{args.client_order_ref_prefix}{b['ref_suffix']}",
                "order_line": line_cmds,
            }
            new_id = models.execute_kw(db, uid, password, "sale.order", "create", [vals])
            print(f"✅ Creado sale.order id={new_id} grupo={b['grupo']}")


if __name__ == "__main__":
    main()
