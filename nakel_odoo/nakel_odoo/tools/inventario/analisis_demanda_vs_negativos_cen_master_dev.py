#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análisis (solo lectura): productos con demanda reciente en ventas vs existencias NEGATIVAS
en la ubicación de stock de Nakel Central (CEN).

En master_dev, el almacén CEN tiene `lot_stock_id` = **CEN/Existencias** (id 102).
Si en tu UI ves "CEN/STOCK", suele referirse a ese stock físico; podés pasar otra ubicación con
`--location-id` o `--location-complete-name`.

Demanda (por defecto): suma de `sale.order.line.product_uom_qty` donde:
  - `state` = sale (pedido confirmado)
  - `company_id` = Nakel SA (1) por defecto
  - `order_id.date_order` >= hoy - N días

Salida: CSV con columnas: product_id, display_name, qty_stock (en ubicación), demanda (opcional), score.

Modos de cantidad (`--qty-mode`):
  - `negative`: solo `stock.quant.quantity < 0` (comportamiento original).
  - `zero_or_negative`: `quantity <= 0` (incluye ceros explícitos en quants).

`--top 0` = sin límite (exporta todos los productos que matcheen el modo).

Salida por defecto (si no pasás ``--out``): ``inventario/correcciones/OUT/`` en la raíz del repo,
con nombre ``cen_existencias_master_dev_<timestamp>.csv``.

Uso:
  python3 nakel_odoo/tools/inventario/analisis_demanda_vs_negativos_cen_master_dev.py \\
    --qty-mode zero_or_negative --top 0

  python3 ... --dias 90 --top 80 --sort score

  python3 ... --qty-mode negative --top 0 --no-demanda

  # Destino explícito:
  python3 ... --out /tmp/otro_nombre.csv
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import xmlrpc.client

sys.path.insert(0, "/media/klap/raid5/cursor_files")

from config_nakel import ODOO_CONFIG_MASTER_DEV  # noqa: E402


def _reports_out_dir() -> Path:
    """Directorio estándar de informes: inventario/correcciones/OUT (raíz del repo)."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    return repo_root / "inventario" / "correcciones" / "OUT"


def _csv_num(v: float) -> str:
    """Serializa float para CSV: sin `.0` innecesario (más legible en Excel/LibreOffice)."""
    x = float(v)
    s = f"{x:.10f}".rstrip("0").rstrip(".")
    if s in ("-0", "-0."):
        return "0"
    return s if s else "0"


def _csv_numeric_int_if_whole(v: float, *, abs_tol: float = 1e-4) -> str:
    """Entero en texto si el valor es (casi) entero; si no, decimales con _csv_num."""
    x = float(v)
    ri = round(x)
    if math.isclose(x, ri, rel_tol=0.0, abs_tol=abs_tol):
        return str(int(ri))
    return _csv_num(x)


def _csv_excel_text_field(s: str) -> str:
    """
    Evita que Excel trate la celda como número (p. ej. referencia 1039.20 → 1039,2).
    Fórmula de una celda que devuelve texto; LibreOffice suele interpretarla igual.
    """
    s = (s or "").strip()
    if not s:
        return s
    inner = s.replace('"', '""')
    return f'="{inner}"'


def connect():
    cfg = ODOO_CONFIG_MASTER_DEV
    url = cfg["url"].rstrip("/")
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)
    uid = common.authenticate(cfg["db"], cfg["username"], cfg["password"], {})
    if not uid:
        raise SystemExit("Autenticación Odoo fallida (master_dev)")
    return models, int(uid), cfg["db"], cfg["password"]


def search(models, db, uid, pwd, model: str, domain: list, *, limit: int | None = None, order: str | None = None) -> list[int]:
    kwargs: dict[str, Any] = {}
    if limit is not None:
        kwargs["limit"] = int(limit)
    if order:
        kwargs["order"] = order
    return models.execute_kw(db, uid, pwd, model, "search", [domain], kwargs)


def read(models, db, uid, pwd, model: str, ids: list[int], fields: list[str]) -> list[dict[str, Any]]:
    if not ids:
        return []
    return models.execute_kw(db, uid, pwd, model, "read", [ids], {"fields": fields})


def search_read(
    models,
    db,
    uid,
    pwd,
    model: str,
    domain: list,
    *,
    fields: list[str],
    limit: int = 0,
    offset: int = 0,
    order: str | None = None,
) -> list[dict[str, Any]]:
    kwargs: dict[str, Any] = {"fields": fields, "offset": int(offset)}
    if limit:
        kwargs["limit"] = int(limit)
    if order:
        kwargs["order"] = order
    return models.execute_kw(db, uid, pwd, model, "search_read", [domain], kwargs)


def read_group(
    models,
    db,
    uid,
    pwd,
    model: str,
    domain: list,
    fields: list[str],
    groupby: list[str],
    *,
    lazy: bool = False,
) -> list[dict[str, Any]]:
    return models.execute_kw(
        db,
        uid,
        pwd,
        model,
        "read_group",
        [domain],
        {"fields": fields, "groupby": groupby, "lazy": lazy},
    )


def resolve_location_id(
    models, db, uid, pwd, *, location_id: int | None, location_name: str | None
) -> tuple[int, str]:
    if location_id:
        rows = read(models, db, uid, pwd, "stock.location", [location_id], ["id", "complete_name"])
        if not rows:
            raise SystemExit(f"No existe stock.location id={location_id}")
        r = rows[0]
        return int(r["id"]), str(r["complete_name"])

    if location_name:
        key = location_name.strip()
        if key.upper() == "CEN/STOCK":
            return resolve_location_id(models, db, uid, pwd, location_id=None, location_name="CEN/Existencias")
        dom = [["complete_name", "=", key]]
        ids = search(models, db, uid, pwd, "stock.location", dom, limit=2)
        if len(ids) == 1:
            r = read(models, db, uid, pwd, "stock.location", ids, ["id", "complete_name"])[0]
            return int(r["id"]), str(r["complete_name"])
        raise SystemExit(
            f"Ubicación no encontrada o ambigua para complete_name={location_name!r} (ids={ids})"
        )

    # Default: lot_stock del almacén CEN
    wh_ids = search(models, db, uid, pwd, "stock.warehouse", [["code", "=", "CEN"]], limit=1)
    if not wh_ids:
        raise SystemExit("No se encontró almacén code=CEN")
    wh = read(models, db, uid, pwd, "stock.warehouse", wh_ids, ["lot_stock_id"])[0]
    loc = wh.get("lot_stock_id")
    if not loc:
        raise SystemExit("Warehouse CEN sin lot_stock_id")
    lid = int(loc[0]) if isinstance(loc, (list, tuple)) else int(loc)
    name = str(loc[1]) if isinstance(loc, (list, tuple)) and len(loc) > 1 else ""
    return lid, name or f"id={lid}"


def _build_quant_domain(location_id: int, *, include_children: bool, qty_mode: str) -> list:
    loc_op = "child_of" if include_children else "="
    loc_clause: list = ["location_id", loc_op, location_id]
    if qty_mode == "negative":
        return ["&", loc_clause, ["quantity", "<", 0]]
    if qty_mode == "zero_or_negative":
        return ["&", loc_clause, "|", ["quantity", "<", 0], ["quantity", "=", 0]]
    raise ValueError(f"qty_mode inválido: {qty_mode!r}")


def aggregate_quants_by_product(
    models, db, uid, pwd, location_id: int, *, include_children: bool, qty_mode: str
) -> dict[int, float]:
    domain = _build_quant_domain(location_id, include_children=include_children, qty_mode=qty_mode)
    agg: dict[int, float] = defaultdict(float)
    offset = 0
    page = 500
    while True:
        rows = search_read(
            models,
            db,
            uid,
            pwd,
            "stock.quant",
            domain,
            fields=["product_id", "quantity"],
            limit=page,
            offset=offset,
            order="id asc",
        )
        if not rows:
            break
        for r in rows:
            pid = r["product_id"][0] if isinstance(r.get("product_id"), (list, tuple)) else r["product_id"]
            agg[int(pid)] += float(r.get("quantity") or 0.0)
        offset += len(rows)
        if len(rows) < page:
            break
    return dict(agg)


def demand_by_product(
    models,
    db,
    uid,
    pwd,
    *,
    product_ids: list[int],
    company_id: int,
    days: int,
) -> dict[int, float]:
    if not product_ids:
        return {}
    date_from = (datetime.now(timezone.utc) - timedelta(days=int(days))).strftime("%Y-%m-%d 00:00:00")
    out: dict[int, float] = defaultdict(float)
    # read_group en chunks (evita dominios enormes)
    chunk = 200
    for i in range(0, len(product_ids), chunk):
        part = product_ids[i : i + chunk]
        domain = [
            ["order_id.date_order", ">=", date_from],
            ["state", "=", "sale"],
            ["company_id", "=", int(company_id)],
            ["product_id", "in", part],
        ]
        groups = read_group(
            models,
            db,
            uid,
            pwd,
            "sale.order.line",
            domain,
            ["product_uom_qty:sum"],
            ["product_id"],
            lazy=False,
        )
        for g in groups:
            key = g.get("product_id")
            if not key:
                continue
            pid = int(key[0]) if isinstance(key, (list, tuple)) else int(key)
            out[pid] += float(g.get("product_uom_qty", 0) or 0.0)
    return dict(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--location-id", type=int, default=None, help="stock.location id (default: CEN lot_stock)")
    ap.add_argument(
        "--location-complete-name",
        type=str,
        default=None,
        help='Ej: "CEN/Existencias". Si pasás "CEN/STOCK" y no existe, se intenta CEN/Existencias.',
    )
    ap.add_argument(
        "--include-children",
        action="store_true",
        help="Usar location_id child_of (sububicaciones bajo la raíz elegida).",
    )
    ap.add_argument("--company-id", type=int, default=1, help="Compañía para demanda en ventas (default 1 Nakel SA)")
    ap.add_argument("--dias", type=int, default=90, help="Ventana de días hacia atrás para demanda (order date)")
    ap.add_argument(
        "--qty-mode",
        choices=("negative", "zero_or_negative"),
        default="negative",
        help="negative: solo quantity<0; zero_or_negative: quantity<=0 (negativos y ceros en quants).",
    )
    ap.add_argument(
        "--top",
        type=int,
        default=80,
        help="Filas máximas en el CSV; use 0 para exportar TODOS sin límite.",
    )
    ap.add_argument(
        "--no-demanda",
        action="store_true",
        help="No consultar ventas (CSV solo con qty en ubicación y datos de producto). Más rápido.",
    )
    ap.add_argument(
        "--out",
        type=str,
        default="",
        help="Ruta CSV de salida. Vacío = inventario/correcciones/OUT/cen_existencias_master_dev_<timestamp>.csv",
    )
    ap.add_argument(
        "--sort",
        choices=("score", "demand", "negative"),
        default="score",
        help="score = demanda * abs(negativo); demanda = solo por ventas; negative = más negativo primero",
    )
    args = ap.parse_args()

    models, uid, db, pwd = connect()
    loc_id, loc_name = resolve_location_id(
        models, db, uid, pwd, location_id=args.location_id, location_name=args.location_complete_name
    )

    qty_by_product = aggregate_quants_by_product(
        models,
        db,
        uid,
        pwd,
        loc_id,
        include_children=bool(args.include_children),
        qty_mode=args.qty_mode,
    )
    if not qty_by_product:
        print(f"No hay quants que cumplan qty-mode={args.qty_mode!r} en {loc_name} (id={loc_id}).")
        return 0

    pids = sorted(qty_by_product.keys())
    demand: dict[int, float] = {}
    if not args.no_demanda:
        demand = demand_by_product(
            models, db, uid, pwd, product_ids=pids, company_id=args.company_id, days=args.dias
        )

    rows_out: list[dict[str, Any]] = []
    for pid in pids:
        qn = qty_by_product[pid]
        d = float(demand.get(pid, 0.0)) if demand else 0.0
        score = d * abs(qn)
        rows_out.append(
            {
                "product_id": pid,
                "qty_stock": qn,
                "demanda_ventas": d,
                "score": score,
            }
        )

    if args.sort == "score":
        rows_out.sort(key=lambda r: (r["score"], r["demanda_ventas"], abs(r["qty_stock"])), reverse=True)
    elif args.sort == "demand":
        rows_out.sort(key=lambda r: (r["demanda_ventas"], abs(r["qty_stock"])), reverse=True)
    else:
        rows_out.sort(key=lambda r: (abs(r["qty_stock"]), r["demanda_ventas"]), reverse=True)

    topn = int(args.top)
    if topn <= 0:
        slice_rows = rows_out
    else:
        slice_rows = rows_out[: max(1, topn)]

    names = read(
        models,
        db,
        uid,
        pwd,
        "product.product",
        [r["product_id"] for r in slice_rows],
        ["display_name", "default_code", "barcode"],
    )
    name_by_id = {int(x["id"]): x for x in names}

    if args.out.strip():
        out_path = Path(args.out)
    else:
        out_dir = _reports_out_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"cen_existencias_master_dev_{datetime.now():%Y%m%d_%H%M%S}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    demand_col = f"demanda_ventas_{args.dias}d_c{args.company_id}"
    fieldnames = [
        "product_id",
        "default_code",
        "barcode",
        "display_name",
        "ubicacion",
        "qty_mode",
        "qty_stock",
    ]
    if not args.no_demanda:
        fieldnames.extend([demand_col, "score_demanda_x_abs_qty"])
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for r in slice_rows:
            pid = int(r["product_id"])
            meta = name_by_id.get(pid, {})
            code = (meta.get("default_code") or "").strip()
            bc = (meta.get("barcode") or "").strip()
            row = {
                "product_id": pid,
                # Referencias con punto: forzar texto en Excel (no son decimales de stock).
                "default_code": _csv_excel_text_field(code) if ("." in code or "," in code) else code,
                # Códigos largos solo dígitos: Excel suele pasarlos a notación científica.
                "barcode": _csv_excel_text_field(bc) if (bc.isdigit() and len(bc) >= 11) else bc,
                "display_name": (meta.get("display_name") or "").strip(),
                "ubicacion": f"{loc_name} (id={loc_id})",
                "qty_mode": args.qty_mode,
                "qty_stock": _csv_numeric_int_if_whole(r["qty_stock"]),
            }
            if not args.no_demanda:
                row[demand_col] = _csv_numeric_int_if_whole(r["demanda_ventas"])
                row["score_demanda_x_abs_qty"] = _csv_numeric_int_if_whole(r["score"])
            w.writerow(row)

    print(f"Ubicación: {loc_name} (id={loc_id})")
    print(f"qty-mode: {args.qty_mode} | productos (agregado por product_id): {len(qty_by_product)}")
    print(f"Filas exportadas: {len(slice_rows)}")
    if not args.no_demanda:
        print(f"Ventana demanda: últimos {args.dias} días | company_id={args.company_id} | orden={args.sort}")
    else:
        print("Demanda: omitida (--no-demanda)")
    print(f"CSV: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
