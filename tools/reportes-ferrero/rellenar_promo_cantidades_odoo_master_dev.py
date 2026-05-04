#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rellena **Ctd. Vendida** del informe Promo Ferrero (Hoja1) con ventas de Odoo **master_dev**
(`config_nakel.ODOO_CONFIG_MASTER_DEV`).

Criterios (revisar con negocio):
- **Cliente / comprador:** columna *Codigo Cliente* (numérico) y *Razón Social*.
  1) `res.partner.ref` = código (como en muchos clientes).
  2) Si no: texto `RAZÓN (SUCURSAL)` → contacto hijo con `parent_id` y `name` ~ sucursal,
     `parent_id.name` ~ parte de la razón (mismo criterio que pedidos: partner de entrega).
- **Promo:** columna *Descripcion*; se buscan `product.product` cuyo `name` cumple varias
  palabras clave derivadas del texto PROMO (AND `ilike`).
- **Cantidad:** suma **neta facturada** (`account.move.line`): `out_invoice` − `out_refund`,
  por `invoice_date` en el mes   (`--year`, `--month`) y movimientos `posted` (no cuenta
  NC como venta). Partner en factura = **mismo** `res.partner` resuelto para la fila (exacto).

Entrada/salida por defecto (carpeta OUT/):
  Lee:  OUT/Promo Ferrero Abril.xls
  Escribe: OUT/Promo Ferrero Abril_odoo.xls

Uso:
  cd reportes-ferrero
  ./.venv/bin/python rellenar_promo_cantidades_odoo_master_dev.py
  ./.venv/bin/python rellenar_promo_cantidades_odoo_master_dev.py --dry-run
  Por defecto Hoja1 solo incluye filas con Ctd. Vendida > 0 (sin ruido de ceros).
  Grid completo (todas las filas marzo→abril): --todas-las-filas

La hoja **Accionados** incluye columna de **ventas Odoo agregadas** por linea accionada;
la columna de **tope** es el acuerdo comercial (no es venta).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import xmlrpc.client
from datetime import date
from typing import Any, Callable

import xlrd
import xlwt

DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(DIR, "OUT")
sys.path.insert(0, DIR)
sys.path.insert(0, "/media/klap/raid5/cursor_files")

from ferrero_odoo_net_sales import aml_net_qty_by_product_partner

try:
    from config_nakel import ODOO_CONFIG_MASTER_DEV
except ImportError as e:
    raise SystemExit(f"Falta config_nakel en /media/klap/raid5/cursor_files: {e}")


def connect(cfg: dict) -> tuple[Any, int, str, str]:
    url = cfg["url"].rstrip("/")
    db = cfg["db"]
    user = cfg["username"]
    pwd = cfg["password"]
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)
    uid = common.authenticate(db, user, pwd, {})
    if not uid:
        raise SystemExit(f"Auth fallida: {url} db={db}")
    return models, int(uid), db, pwd


def month_range(year: int, month: int) -> tuple[str, str]:
    d0 = date(year, month, 1)
    if month == 12:
        d1 = date(year + 1, 1, 1)
    else:
        d1 = date(year, month + 1, 1)
    return (d0.strftime("%Y-%m-%d"), d1.strftime("%Y-%m-%d"))


def norm_client_code(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        f = float(v)
        if f != f:
            return None
        return int(f)
    except (TypeError, ValueError):
        return None


def parse_promo_data_row(rs: Any, r: int) -> tuple[int | None, str, str, bool]:
    """
    Devuelve (codigo_cliente, razon_social, descripcion_promo, fila_desfasada_una_columna).
    Algunas planillas traen filas con col A vacía y el código en col B.
    """
    v0 = rs.cell_value(r, 0)
    v1 = rs.cell_value(r, 1)
    cc = norm_client_code(v0)
    if cc is not None:
        razon = str(rs.cell_value(r, 1)).strip()
        desc = str(rs.cell_value(r, 3)).strip()
        return cc, razon, desc, False
    cc = norm_client_code(v1)
    if cc is not None:
        desc = str(rs.cell_value(r, 3)).strip()
        return cc, "", desc, True
    return None, "", "", False


def mes_etiqueta(month: int, year: int) -> str:
    meses = ("", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
    return f"{meses[month]} {year}"


# Misma tabla comercial que generar_promo_ferrero_abril / ventas-stock (tope cajas + fila resumen ventas)
ACCIONADOS_PARAM: list[tuple[str, float, Callable[[str], bool]]] = [
    ("Kinder Maxi 10% descuento", 14, lambda u: "MAXI" in u and "KINDER" in u),
    ("Kinder Chocolate T4 10% descuento", 6, lambda u: "CHOCOLATE" in u and "T4" in u),
    ("Nutella B-Ready 20% descuento", 161, lambda u: "NUTELLA" in u and "READY" in u.replace(" ", "")),
    ("Nutella 140 15% descuento", 47, lambda u: "NUTELLA" in u and "140" in u),
    ("Nutella 350 15% descuento", 16, lambda u: "NUTELLA" in u and "350" in u),
    ("Rocher T24 15% descuento", 31, lambda u: "ROCHER" in u and "T24" in u),
    (
        "Rocher T3 15% descuento",
        48,
        lambda u: "ROCHER" in u and bool(re.search(r"\bT3\b", u)) and "T24" not in u,
    ),
    (
        "Tic Tac Chico (3x2; 1 si o si Citrus Mix) o los 3 con 33% dto., siempre 1 citrus mix",
        15,
        lambda u: "TIC" in u and "TAC" in u,
    ),
]


def accionados_totales_odoo(
    rows: list[tuple[int, int, str, str, bool]],
    qty_by_row: dict[int, float],
) -> list[tuple[str, float, float]]:
    """Lista (texto dinámica, tope cajas acuerdo, suma uds Odoo Hoja1)."""
    out: list[tuple[str, float, float]] = []
    for label, tope, pred in ACCIONADOS_PARAM:
        s = 0.0
        for r, _cc, _razon, desc, _sh in rows:
            if pred(desc.upper()):
                s += float(qty_by_row.get(r, 0.0))
        out.append((label, float(tope), s))
    return out


def escribir_hoja_accionados(
    wb: xlwt.Workbook,
    totales: list[tuple[str, float, float]],
    etiqueta_mes: str,
) -> None:
    w = wb.add_sheet("Accionados_16abr2026")
    w.write(0, 0, "Articulos accionados desde 16/04/2026 — NAKEL S.A.")
    w.write(
        1,
        0,
        "Col. B = tope de cajas (acuerdo comercial). Col. C = unidades vendidas periodo (Odoo, suma Hoja1).",
    )
    w.write(2, 0, "Dinamica / Cliente")
    w.write(2, 1, "Tope cajas (acuerdo)")
    w.write(2, 2, f"Ventas {etiqueta_mes} (Odoo uds)")
    for i, (txt, tope, vta) in enumerate(totales, start=3):
        w.write(i, 0, txt)
        w.write(i, 1, float(tope))
        w.write(i, 2, float(vta))


def promo_search_tokens(desc: str) -> tuple[list[str], list[str]]:
    """
    Palabras clave para acotar productos Ferrero según texto PROMO del Excel.
    Devuelve (tokens para AND ilike, subcadenas a excluir en el nombre del producto leído de Odoo).
    """
    d = str(desc).strip().upper()
    if "KINDER MAXI" in d:
        return (["KINDER", "MAXI"], [])
    if "HUEVO KINDER" in d or ("HUEVO" in d and "KINDER" in d and "MAXI" not in d and "JOY" not in d):
        return (["HUEVO", "KINDER"], [])
    if "KINDER JOY" in d or "JOY" in d and "KINDER" in d:
        return (["KINDER", "JOY"], [])
    if "KINDER CHOCOLATE" in d or ("CHOCOLATE" in d and "KINDER" in d and "HUEVO" not in d):
        return (["KINDER", "CHOCOLATE"], [])
    # En catálogo no suele figurar "T24" literal; bomboneras / estuches Rocher sin huevo.
    if "ROCHER T24" in d or ("ROCHER" in d and "T24" in d):
        return (["ROCHER", "BOMBONERA"], ["HUEVO", "BOX", "X225", "X365", "DARK"])
    if "ROCHER T3" in d or (
        "ROCHER" in d and "T24" not in d and re.search(r"\bT3\b", d) and "T30" not in d
    ):
        return (["ROCHER", "X3U"], ["HUEVO", "BOX", "X225", "X365", "DARK"])
    if "ROCHER T12" in d or "T12" in d:
        return (["ROCHER", "BOMBONERA"], ["HUEVO", "BOX", "X225", "X365", "DARK"])
    if "ROCHER T8" in d or ("ROCHER" in d and "T8" in d):
        return (["ROCHER", "BOMBONERA"], ["HUEVO", "BOX", "X225", "X365", "DARK"])
    if "RAFAELLO" in d or "RAFFAELLO" in d:
        return (["RAFFAELLO"], [])
    if "BUENO WHITE" in d or ("BUENO" in d and "WHITE" in d):
        return (["BUENO", "WHITE"], [])
    if "BUENO" in d and "WHITE" not in d:
        return (["KINDER", "BUENO"], [])
    if "NUTELLA" in d and "B-READY" in d.replace(" ", ""):
        return (["NUTELLA", "READY"], [])
    if "NUTELLA" in d and "350" in d:
        return (["NUTELLA", "350"], [])
    if "NUTELLA" in d and ("140" in d or "X140" in d):
        return (["NUTELLA", "140"], [])
    if "TIC TAC" in d or "TICTAC" in d.replace(" ", ""):
        return (["TIC", "TAC"], [])
    # fallback: tokens significativos
    parts = re.findall(r"[A-Za-zÁÉÍÓÚÑÜ0-9]+", d)
    skip = {"PROMO", "OFF", "DESCUENTO", "DE", "LA", "EL", "X", "U"}
    out = [p for p in parts if len(p) >= 3 and p.upper() not in skip]
    out.sort(key=len, reverse=True)
    return (out[:4], [])


def product_ids_for_tokens(
    models: Any,
    uid: int,
    db: str,
    pwd: str,
    tokens: list[str],
    exclude_name: list[str],
    cache: dict[tuple[tuple[str, ...], tuple[str, ...]], list[int]],
) -> list[int]:
    if not tokens:
        return []
    key = (tuple(tokens), tuple(exclude_name))
    if key in cache:
        return cache[key]
    # Dominio Odoo: un solo triplete en lista, o ['&', triplete, triplete, ...] (sin listas de 1 hoja).
    if len(tokens) == 1:
        domain: list[Any] = [("name", "ilike", tokens[0])]
    else:
        domain = ["&", ("name", "ilike", tokens[0]), ("name", "ilike", tokens[1])]
        for t in tokens[2:]:
            domain = ["&", domain, ("name", "ilike", t)]
    ids = models.execute_kw(
        db,
        uid,
        pwd,
        "product.product",
        "search",
        [domain],
        {"limit": 400},
    )
    if ids and exclude_name:
        prows = models.execute_kw(
            db,
            uid,
            pwd,
            "product.product",
            "read",
            [ids],
            {"fields": ["id", "name"]},
        )
        keep: list[int] = []
        for p in prows:
            nm = str(p.get("name") or "").upper()
            if any(ex.upper() in nm for ex in exclude_name):
                continue
            keep.append(int(p["id"]))
        ids = keep
    cache[key] = ids
    return ids


def resolve_partner_id(
    models: Any,
    uid: int,
    db: str,
    pwd: str,
    codigo: int,
    razon: str,
    cache: dict[tuple[int, str], int | None],
) -> int | None:
    razon_s = str(razon).strip()
    ck = (codigo, razon_s)
    if ck in cache:
        return cache[ck]

    ref = str(codigo)
    ids = models.execute_kw(
        db,
        uid,
        pwd,
        "res.partner",
        "search",
        [[("ref", "=", ref)]],
        {"limit": 8},
    )
    if len(ids) >= 1:
        pid = ids[0]
        mbr = re.match(r"^(.+?)\s*\(\s*([^)]+)\s*\)\s*$", razon_s)
        if mbr and len(ids) == 1:
            branch = mbr.group(2).strip()
            prow = models.execute_kw(
                db,
                uid,
                pwd,
                "res.partner",
                "read",
                [[pid]],
                {"fields": ["name", "parent_id"]},
            )
            if prow:
                p0 = prow[0]
                par = p0.get("parent_id")
                is_child = bool(par)
                nm = str(p0.get("name") or "")
                if not is_child:
                    ch = models.execute_kw(
                        db,
                        uid,
                        pwd,
                        "res.partner",
                        "search",
                        [
                            [
                                ("parent_id", "=", pid),
                                ("name", "ilike", branch[:40]),
                            ]
                        ],
                        {"limit": 4},
                    )
                    if len(ch) == 1:
                        pid = ch[0]
                elif branch.lower() not in nm.lower():
                    par_id = int(par[0]) if isinstance(par, (list, tuple)) else int(par)
                    ch = models.execute_kw(
                        db,
                        uid,
                        pwd,
                        "res.partner",
                        "search",
                        [
                            [
                                ("parent_id", "=", par_id),
                                ("name", "ilike", branch[:40]),
                            ]
                        ],
                        {"limit": 4},
                    )
                    if len(ch) == 1:
                        pid = ch[0]
        cache[ck] = pid
        return pid

    m = re.match(r"^(.+?)\s*\(\s*([^)]+)\s*\)\s*$", razon_s)
    if m:
        base = re.sub(r"\.\s*$", "", m.group(1).strip())
        branch = m.group(2).strip()
        dom: list[Any] = [
            "&",
            ("parent_id", "!=", False),
            ("name", "ilike", branch[:40]),
            ("parent_id.name", "ilike", base[:50]),
        ]
        ids = models.execute_kw(
            db,
            uid,
            pwd,
            "res.partner",
            "search",
            [dom],
            {"limit": 5},
        )
        if len(ids) == 1:
            cache[ck] = ids[0]
            return ids[0]
        if len(ids) > 1:
            cache[ck] = ids[0]
            return ids[0]

    # Nombre plano: palabra más larga + ilike nombre completo acotado
    words = [w for w in re.split(r"\W+", razon_s) if len(w) >= 4]
    words.sort(key=len, reverse=True)
    if not words:
        cache[ck] = None
        return None
    needle = words[0][:20]
    ids = models.execute_kw(
        db,
        uid,
        pwd,
        "res.partner",
        "search",
        [[("name", "ilike", needle)]],
        {"limit": 15},
    )
    if len(ids) == 1:
        cache[ck] = ids[0]
        return ids[0]
    cache[ck] = None
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--month", type=int, default=4, help="Mes 1-12 (default abril)")
    ap.add_argument(
        "--in",
        dest="in_path",
        default=os.path.join(OUT_DIR, "Promo Ferrero Abril.xls"),
    )
    ap.add_argument(
        "--out",
        dest="out_path",
        default=os.path.join(OUT_DIR, "Promo Ferrero Abril_odoo.xls"),
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--todas-las-filas",
        action="store_true",
        help="En Hoja1 incluir todas las filas de detalle aunque Ctd. Vendida <= 0 (grid completo).",
    )
    args = ap.parse_args()

    year, month = int(args.year), int(args.month)
    if not 1 <= month <= 12:
        raise SystemExit("--month debe estar entre 1 y 12")
    d0, d1 = month_range(year, month)

    cfg = ODOO_CONFIG_MASTER_DEV.copy()
    models, uid, db, pwd = connect(cfg)
    print(f"OK Odoo: {cfg.get('url')} db={db} | ventas {d0} .. <{d1}")

    if not os.path.isfile(args.in_path):
        raise SystemExit(f"No existe: {args.in_path}")

    rb = xlrd.open_workbook(args.in_path, formatting_info=False)
    rs = rb.sheet_by_index(0)

    partner_cache: dict[tuple[int, str], int | None] = {}
    prod_cache: dict[tuple[tuple[str, ...], tuple[str, ...]], list[int]] = {}
    aml_cache: dict[tuple[int, str, str], dict[int, float]] = {}

    # Pre-scan filas datos (incluye filas con codigo cliente en col B por desalineacion en planilla)
    rows: list[tuple[int, int, str, str, bool]] = []
    n_shifted = 0
    for r in range(3, rs.nrows):
        cc, razon, desc, shifted = parse_promo_data_row(rs, r)
        if cc is None or not desc or desc.lower() == "descripcion":
            continue
        if shifted:
            n_shifted += 1
        rows.append((r, cc, razon, desc, shifted))

    # Precompute product ids por descripcion promo unica
    desc_uniq = sorted({d for _, _, _, d, _ in rows})
    desc_to_pids: dict[str, list[int]] = {}
    for d in desc_uniq:
        toks, excl = promo_search_tokens(d)
        desc_to_pids[d] = product_ids_for_tokens(models, uid, db, pwd, toks, excl, prod_cache)

    stats = {"no_partner": 0, "no_product": 0, "qty_pos": 0, "rows": 0, "desalineadas": n_shifted}

    qty_by_row: dict[int, float] = {}
    for r, cc, razon, desc, _shifted in rows:
        stats["rows"] += 1
        pid = resolve_partner_id(models, uid, db, pwd, cc, razon, partner_cache)
        if pid is None:
            stats["no_partner"] += 1
            qty_by_row[r] = 0.0
            continue
        pids = desc_to_pids.get(desc) or []
        if not pids:
            stats["no_product"] += 1
            qty_by_row[r] = 0.0
            continue
        pset = set(pids)
        pq = aml_net_qty_by_product_partner(models, uid, db, pwd, pid, d0, d1, aml_cache)
        q = sum(qty for pr, qty in pq.items() if pr in pset)
        qty_by_row[r] = q
        if q > 0:
            stats["qty_pos"] += 1

    totales_acc = accionados_totales_odoo(rows, qty_by_row)
    mes_lbl = mes_etiqueta(month, year)

    print(
        f"Filas con datos: {stats['rows']} | "
        f"filas planilla desalineadas (codigo en col B): {stats['desalineadas']} | "
        f"sin partner: {stats['no_partner']} | "
        f"sin productos promo: {stats['no_product']} | "
        f"filas con cantidad > 0: {stats['qty_pos']}"
    )

    if args.dry_run:
        print("Dry-run (primeras 12 filas con detalle):")
        for r, cc, razon, desc, sh in rows[:12]:
            q = qty_by_row.get(r, 0.0)
            p = partner_cache.get((cc, str(razon).strip()))
            np = len(desc_to_pids.get(desc) or [])
            shs = " desalineada" if sh else ""
            print(
                f"  row={r+1} cliente={cc} partner_id={p} prod_cands={np} qty={q}{shs} | {desc[:50]}"
            )
        print("Resumen accionados — tope (acuerdo) vs uds Odoo (suma detalle Hoja1):")
        for txt, tope, v in totales_acc:
            print(f"  tope {tope:>4.0f} | Odoo {v:>10.1f} | {txt[:55]}")
        if not args.todas_las_filas:
            n_kept = sum(1 for r, *_ in rows if qty_by_row.get(r, 0.0) > 0)
            print(
                f"Hoja1 (por defecto sin ceros): quedarian {n_kept} filas de detalle (mas cabecera). "
                f"Grid completo: --todas-las-filas"
            )
        return 0

    wb = xlwt.Workbook(encoding="utf-8")
    ws = wb.add_sheet("Hoja1")

    for r in range(3):
        for c in range(rs.ncols):
            v = rs.cell_value(r, c)
            t = rs.cell_type(r, c)
            if isinstance(v, str):
                ws.write(r, c, v)
            elif t == xlrd.XL_CELL_NUMBER:
                fv = float(v)
                ws.write(r, c, int(fv) if fv == int(fv) else fv)
            elif t == xlrd.XL_CELL_BOOLEAN:
                ws.write(r, c, bool(v))
            else:
                ws.write(r, c, v)

    wr = 3
    for r in range(3, rs.nrows):
        cc, razon, desc, shifted = parse_promo_data_row(rs, r)
        if cc is None or not desc or desc.lower() == "descripcion":
            continue
        q = float(qty_by_row.get(r, 0.0))
        if not args.todas_las_filas and q <= 0:
            continue
        for c in range(rs.ncols):
            v = rs.cell_value(r, c)
            t = rs.cell_type(r, c)
            if c == 4:
                v = q
            elif t == xlrd.XL_CELL_NUMBER and float(v) == int(float(v)) and c != 4:
                v = int(float(v))
            if isinstance(v, str):
                ws.write(wr, c, v)
            elif isinstance(v, (int, float)):
                ws.write(wr, c, float(v))
            elif t == xlrd.XL_CELL_BOOLEAN:
                ws.write(wr, c, bool(v))
            else:
                ws.write(wr, c, v)
        wr += 1

    escribir_hoja_accionados(wb, totales_acc, mes_lbl)

    out_parent = os.path.dirname(os.path.abspath(args.out_path))
    if out_parent:
        os.makedirs(out_parent, exist_ok=True)
    wb.save(args.out_path)
    print(f"OK: escrito {args.out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
