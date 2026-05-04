#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rellena columnas VENTAS y STOCK del XLS Ferrero consultando Odoo **master_dev**
en https://nakel.net.ar (config: config_nakel.ODOO_CONFIG_MASTER_DEV).

Criterios (revisar con negocio si hace falta afinar):
- Producto: primero `product.product.default_code` = codigo art. proveedor (col B del XLS);
  si no hay match, `product.supplierinfo.product_code` = ese codigo (codigo Ferrero en ficha proveedor);
  si sigue sin match, **nombre**: descripcion col C (sin sufijo tipo `.-899-`), busqueda `ilike` + desempate por tokens.
- STOCK: `qty_available` del producto (stock global Odoo; no filtra por deposito).
- VENTAS (mes): **cantidad neta facturada** (`account.move.line`): facturas `out_invoice`
  menos notas de crédito `out_refund`, por `invoice_date` en el rango (`--year` / mes abril
  por defecto) y movimientos `posted` (devoluciones no cuentan como venta).

Entrada/salida por defecto (carpeta OUT/):
- Lee:  OUT/FERRERO VENTAS Y STOCK 2026-04.xls
- Escribe: OUT/FERRERO VENTAS Y STOCK 2026-04_odoo.xls (no pisa el original)

Uso:
  cd reportes-ferrero
  ./.venv/bin/pip install 'xlrd<2' xlwt   # si falta
  NAKEL_TARGET=master_dev python3 rellenar_ventas_stock_odoo_master_dev.py
  # (NAKEL_TARGET opcional: por defecto config_nakel ya apunta a master_dev / nakel.net.ar)

Opciones:
  --year 2026 --in PATH.xls --out OUT.xls
  --dry-run  (solo imprime mapeo, no escribe XLS)
  --exclude-codes 77235547,…  (omite esas filas de producto en el XLS de salida)
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import xmlrpc.client
from typing import Any

import xlrd
import xlwt

DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(DIR, "OUT")
sys.path.insert(0, DIR)
sys.path.insert(0, "/media/klap/raid5/cursor_files")

from ferrero_odoo_net_sales import aml_net_qty_by_product_global

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


def norm_code(v: Any) -> str | None:
    if v is None or v == "":
        return None
    try:
        f = float(v)
        if f != f:  # nan
            return None
        i = int(f)
        if abs(f - i) < 1e-9:
            return str(i)
        return str(f).rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        s = str(v).strip()
        return s or None


def parse_exclude_codes(raw: str) -> set[str]:
    if not raw or not str(raw).strip():
        return set()
    out: set[str] = set()
    for part in str(raw).split(","):
        part = part.strip()
        if not part:
            continue
        nc = norm_code(part)
        if nc:
            out.add(nc)
        else:
            out.add(part)
    return out


def ferrero_desc_key(s: str) -> str:
    """Texto comercial del XLS sin sufijos internos tipo '.-899-'."""
    s = str(s).strip()
    if not s:
        return ""
    s = re.sub(r"\.-\d+-\s*$", "", s)
    # Cantidad por caja en ficha (ej. " (10)") no suele estar en el name de Odoo
    s = re.sub(r"\s*\(\d+\)\s*$", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def safe_ilike_fragment(s: str, max_len: int = 100) -> str:
    """Evita comodines accidentales en dominio ilike de Odoo."""
    s = s.strip()[:max_len]
    return s.replace("%", "").replace("_", " ")


def tokenize_name(s: str) -> set[str]:
    return {m.group(0).lower() for m in re.finditer(r"[A-Za-zÁÉÍÓÚÑÜáéíóúñü0-9]{2,}", s)}


def name_overlap_score(excel_key: str, odoo_name: str) -> float:
    a = tokenize_name(excel_key)
    b = tokenize_name(odoo_name)
    if not a:
        return 0.0
    inter = len(a & b)
    return inter / max(len(a), 1)


def pick_product_by_name(
    models: Any,
    uid: int,
    db: str,
    pwd: str,
    desc: str,
) -> dict[str, Any] | None:
    """
    Un solo candidato fuerte o el de mayor solapamiento de tokens frente al segundo.
    Si hay ambiguedad clara, devuelve None.
    """
    key = ferrero_desc_key(desc)
    if len(key) < 4:
        return None

    def search_ids(domain: list) -> list[int]:
        return models.execute_kw(
            db,
            uid,
            pwd,
            "product.product",
            "search",
            [domain],
            {"limit": 40},
        )

    needle = safe_ilike_fragment(key, 100)
    ids: list[int] = []
    if needle:
        ids = search_ids([("name", "ilike", needle)])

    if not ids:
        toks = sorted(tokenize_name(key), key=len, reverse=True)
        long_toks = [t for t in toks if len(t) >= 4][:3]
        if len(long_toks) >= 2:
            ids = search_ids(
                [
                    ("name", "ilike", long_toks[0]),
                    ("name", "ilike", long_toks[1]),
                ]
            )
        elif len(long_toks) == 1:
            ids = search_ids([("name", "ilike", long_toks[0])])

    if not ids:
        return None

    prows = models.execute_kw(
        db,
        uid,
        pwd,
        "product.product",
        "read",
        [ids],
        {"fields": ["id", "default_code", "qty_available", "name"]},
    )
    if len(prows) == 1:
        return prows[0]

    scored = [(name_overlap_score(key, str(p.get("name") or "")), p) for p in prows]
    scored.sort(key=lambda x: x[0], reverse=True)
    best_s, best_p = scored[0]
    second_s = scored[1][0] if len(scored) > 1 else 0.0
    if best_s >= 0.35 and best_s - second_s >= 0.08:
        return best_p
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument(
        "--in",
        dest="in_path",
        default=os.path.join(OUT_DIR, "FERRERO VENTAS Y STOCK 2026-04.xls"),
        help="XLS base abril",
    )
    ap.add_argument(
        "--out",
        dest="out_path",
        default=os.path.join(OUT_DIR, "FERRERO VENTAS Y STOCK 2026-04_odoo.xls"),
        help="XLS salida",
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--no-name-fallback",
        action="store_true",
        help="No intentar mapear por nombre (solo codigo + supplierinfo).",
    )
    ap.add_argument(
        "--exclude-codes",
        default="",
        help="Codigos *Cod.Art. Proveedor* a NO incluir en el XLS (coma). Ej: 77235547",
    )
    args = ap.parse_args()
    exclude_codes = parse_exclude_codes(args.exclude_codes)

    year = int(args.year)
    d0 = f"{year}-04-01"
    d1 = f"{year}-05-01"

    cfg = ODOO_CONFIG_MASTER_DEV.copy()
    models, uid, db, pwd = connect(cfg)
    print(f"OK Odoo: {cfg.get('url')} db={db} uid={uid}")

    in_path = args.in_path
    if not os.path.isfile(in_path):
        raise SystemExit(f"No existe: {in_path}")

    rb = xlrd.open_workbook(in_path, formatting_info=False)
    rs = rb.sheet_by_index(0)

    # Recolectar codigo proveedor (col 1) y descripcion (col 2) para fallback por nombre
    rows_data: list[tuple[int, str, str]] = []
    for r in range(6, rs.nrows):
        code = norm_code(rs.cell_value(r, 1))
        if not code:
            continue
        d = rs.cell_value(r, 2)
        desc = str(d).strip() if d is not None else ""
        rows_data.append((r, code, desc))

    codes = sorted({c for _, c, _ in rows_data})
    prod_by_code: dict[str, dict[str, Any]] = {}

    for chunk_start in range(0, len(codes), 80):
        chunk = codes[chunk_start : chunk_start + 80]
        ids = models.execute_kw(
            db,
            uid,
            pwd,
            "product.product",
            "search",
            [[("default_code", "in", chunk)]],
            {"limit": 500},
        )
        if ids:
            prows = models.execute_kw(
                db,
                uid,
                pwd,
                "product.product",
                "read",
                [ids],
                {"fields": ["id", "default_code", "qty_available", "name"]},
            )
            for p in prows:
                dc = p.get("default_code")
                if dc:
                    prod_by_code[str(dc).strip()] = p

    missing = [c for c in codes if c not in prod_by_code]
    if missing:
        # Fallback: codigo en lineas de proveedor (Ferrero)
        for chunk_start in range(0, len(missing), 50):
            chunk = missing[chunk_start : chunk_start + 50]
            sinfos = models.execute_kw(
                db,
                uid,
                pwd,
                "product.supplierinfo",
                "search_read",
                [[("product_code", "in", chunk)]],
                {"fields": ["product_code", "product_tmpl_id", "product_id"], "limit": 200},
            )
            tmpl_ids: set[int] = set()
            for si in sinfos:
                code = str(si.get("product_code") or "").strip()
                if not code or code in prod_by_code:
                    continue
                pid = si.get("product_id")
                if isinstance(pid, (list, tuple)) and pid:
                    prows = models.execute_kw(
                        db,
                        uid,
                        pwd,
                        "product.product",
                        "read",
                        [[int(pid[0])]],
                        {"fields": ["id", "default_code", "qty_available", "name"]},
                    )
                    if prows:
                        prod_by_code[code] = prows[0]
                elif si.get("product_tmpl_id"):
                    tid = si["product_tmpl_id"][0] if isinstance(si["product_tmpl_id"], (list, tuple)) else si["product_tmpl_id"]
                    tmpl_ids.add(int(tid))
            if tmpl_ids:
                pids = models.execute_kw(
                    db,
                    uid,
                    pwd,
                    "product.product",
                    "search",
                    [[("product_tmpl_id", "in", list(tmpl_ids))]],
                    {"limit": 500},
                )
                if pids:
                    prows = models.execute_kw(
                        db,
                        uid,
                        pwd,
                        "product.product",
                        "read",
                        [pids],
                        {"fields": ["id", "default_code", "qty_available", "name", "product_tmpl_id"]},
                    )
                    tmpl_to_variant: dict[int, dict[str, Any]] = {}
                    for p in prows:
                        tid = p.get("product_tmpl_id")
                        if isinstance(tid, (list, tuple)) and tid:
                            tmpl_to_variant[int(tid[0])] = p
                    for si in sinfos:
                        code = str(si.get("product_code") or "").strip()
                        if not code or code in prod_by_code:
                            continue
                        tid = si.get("product_tmpl_id")
                        if isinstance(tid, (list, tuple)) and tid:
                            pv = tmpl_to_variant.get(int(tid[0]))
                            if pv:
                                prod_by_code[code] = pv

    matched_by_name = 0
    if not args.no_name_fallback:
        code_to_desc: dict[str, str] = {}
        for _, c, desc in rows_data:
            if c not in code_to_desc and desc:
                code_to_desc[c] = desc
        for code in [c for c in codes if c not in prod_by_code]:
            desc = code_to_desc.get(code) or ""
            p = pick_product_by_name(models, uid, db, pwd, desc)
            if p:
                prod_by_code[code] = p
                matched_by_name += 1

    ventas_by_pid: dict[int, float] = {}
    aml_global_cache: dict[tuple[Any, ...], float] = {}
    unique_pids = sorted({int(prod_by_code[c]["id"]) for _, c, _ in rows_data if c in prod_by_code})
    for pid in unique_pids:
        ventas_by_pid[pid] = aml_net_qty_by_product_global(
            models, uid, db, pwd, int(pid), d0, d1, aml_global_cache
        )

    matched_codes = sum(1 for c in codes if c in prod_by_code)
    extra = f" | por nombre: {matched_by_name}" if not args.no_name_fallback else ""
    print(f"Filas producto: {len(rows_data)} | codigos distintos: {len(codes)} | match Odoo: {matched_codes}{extra}")

    if exclude_codes:
        n_omit = sum(
            1
            for rr in range(6, rs.nrows)
            if (cc := norm_code(rs.cell_value(rr, 1))) and cc in exclude_codes
        )
        print(f"Excluidos del XLS de salida: {sorted(exclude_codes)} ({n_omit} filas en plantilla)")

    sin_match_all = [c for c in codes if c not in prod_by_code]
    sin_match = [c for c in sin_match_all if c not in exclude_codes]
    if sin_match:
        det = []
        code_desc = {c: d for _, c, d in rows_data if d}
        for c in sin_match:
            det.append(f"{c} ({code_desc.get(c, '')[:60]})")
        print(f"Sin match Odoo ({len(sin_match)}): " + "; ".join(det))
    omitted_sin_odoo = [c for c in sin_match_all if c in exclude_codes]
    if omitted_sin_odoo:
        code_desc = {c: d for _, c, d in rows_data if d}
        det2 = [f"{c} ({code_desc.get(c, '')[:50]})" for c in omitted_sin_odoo]
        print(f"Sin match Odoo pero omitidos del XLS ({len(det2)}): " + "; ".join(det2))

    if args.dry_run:
        print("Dry-run: no se escribe XLS.")
        for r, code, desc in rows_data[:15]:
            if code in exclude_codes:
                print(f"  row={r+1} code={code} — excluido del XLS (--exclude-codes)")
                continue
            p = prod_by_code.get(code)
            v = ventas_by_pid.get(int(p["id"]), 0.0) if p else 0.0
            st = float(p.get("qty_available") or 0.0) if p else 0.0
            odoo_n = p.get("name") if p else "-"
            print(f"  row={r+1} code={code} ventas_abril={v} stock={st} odoo={odoo_n!r}")
            if p and desc and ferrero_desc_key(desc):
                sc = name_overlap_score(ferrero_desc_key(desc), str(odoo_n))
                if sc < 0.2:
                    print(f"       (baja coincidencia tokens vs XLS: {desc[:70]!r}...)")
        return 0

    # Construir salida (copia Hoja1 + VENTAS/STOCK desde Odoo; filas --exclude-codes sin copiar)
    wb = xlwt.Workbook(encoding="utf-8")
    ws = wb.add_sheet("Hoja1")
    out_row = 0
    for r in range(rs.nrows):
        if r >= 6:
            code_r = norm_code(rs.cell_value(r, 1))
            if code_r and code_r in exclude_codes:
                continue
        wr = out_row
        out_row += 1
        for c in range(rs.ncols):
            v = rs.cell_value(r, c)
            t = rs.cell_type(r, c)
            if r >= 6 and c in (3, 4):
                code = norm_code(rs.cell_value(r, 1))
                p = prod_by_code.get(code) if code else None
                if c == 3:
                    v = float(ventas_by_pid.get(int(p["id"]), 0.0)) if p else 0.0
                else:
                    v = float(p.get("qty_available") or 0.0) if p else 0.0
            elif t == xlrd.XL_CELL_NUMBER and float(v) == int(float(v)) and c not in (3, 4):
                v = int(float(v))
            if isinstance(v, str):
                ws.write(wr, c, v)
            elif isinstance(v, (int, float)):
                ws.write(wr, c, float(v))
            elif t == xlrd.XL_CELL_BOOLEAN:
                ws.write(wr, c, bool(v))
            else:
                ws.write(wr, c, v)

    if rb.nsheets > 1:
        for si in range(1, rb.nsheets):
            rs2 = rb.sheet_by_index(si)
            w2 = wb.add_sheet(rs2.name[:31])
            for r in range(rs2.nrows):
                for c in range(rs2.ncols):
                    v = rs2.cell_value(r, c)
                    t = rs2.cell_type(r, c)
                    if isinstance(v, str):
                        w2.write(r, c, v)
                    elif t == xlrd.XL_CELL_NUMBER:
                        fv = float(v)
                        w2.write(r, c, int(fv) if fv == int(fv) else fv)
                    elif t == xlrd.XL_CELL_BOOLEAN:
                        w2.write(r, c, bool(v))
                    else:
                        w2.write(r, c, v)

    out_parent = os.path.dirname(os.path.abspath(args.out_path))
    if out_parent:
        os.makedirs(out_parent, exist_ok=True)
    wb.save(args.out_path)
    print(f"OK: escrito {args.out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
