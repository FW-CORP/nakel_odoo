#!/usr/bin/env python3
"""
Dry-run (y opcionalmente --apply): snapshot de precios efectivos de una lista de referencia
como líneas fijas (product_tmpl_id) en una lista nueva.

Usa cotizaciones en lotes para obtener price_unit (mismo motor que ventas), sin llamar
métodos privados por XML-RPC.

Ejemplo (solo informe, master_dev):
  python3 dry_run_snapshot_lista_desde_referencia.py \\
    --lista-referencia "Lista 2 Consumidor Final Autoservicios CR" \\
    --nombre-nueva "Belgrano Final Comodoro"

Aplicar (crear lista + ítems): añadir --apply

Si la lista de referencia devuelve precio 0 (PDV / reglas no cubren el artículo), por defecto se usa
lst_price del producto como respaldo. Desactivar: --no-lst-price-fallback
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import xmlrpc.client
from collections import defaultdict

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/media/klap/raid5/cursor_files")

try:
    from config_nakel import ODOO_CONFIG_MASTER_DEV
except ImportError:
    print("❌ No se pudo importar config_nakel.py")
    sys.exit(1)

ODOO_CONFIG = {
    "url": ODOO_CONFIG_MASTER_DEV["url"],
    "db": ODOO_CONFIG_MASTER_DEV["db"],
    "user": ODOO_CONFIG_MASTER_DEV["username"],
    "pass": ODOO_CONFIG_MASTER_DEV["password"],
}


def conectar_odoo():
    common = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/common')
    uid = common.authenticate(
        ODOO_CONFIG["db"], ODOO_CONFIG["user"], ODOO_CONFIG["pass"], {}
    )
    if not uid:
        return None, None
    models = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/object')
    return models, uid


def obtener_lista_por_nombre(models, uid, password, nombre: str) -> dict | None:
    listas = models.execute_kw(
        ODOO_CONFIG["db"],
        uid,
        password,
        "product.pricelist",
        "search_read",
        [[("name", "=", nombre)]],
        {"fields": ["id", "name", "currency_id"]},
    )
    if listas:
        return listas[0]
    listas = models.execute_kw(
        ODOO_CONFIG["db"],
        uid,
        password,
        "product.pricelist",
        "search_read",
        [[("name", "ilike", nombre)]],
        {"fields": ["id", "name", "currency_id"]},
    )
    for lista in listas or []:
        if lista["name"].lower() == nombre.lower():
            return lista
    return listas[0] if listas else None


def partner_demo(models, uid, password) -> int:
    ids = models.execute_kw(
        ODOO_CONFIG["db"],
        uid,
        password,
        "res.partner",
        "search",
        [[("customer_rank", ">", 0)]],
        {"limit": 1},
    )
    if ids:
        return ids[0]
    ids = models.execute_kw(
        ODOO_CONFIG["db"], uid, password, "res.partner", "search", [[]], {"limit": 1}
    )
    return ids[0]


def precios_por_variante_en_lotes(
    models, uid, password, pricelist_id: int, variant_ids: list[int], batch: int
) -> dict[int, float]:
    """Devuelve {product_id: price_unit} usando sale.order en lotes."""
    partner_id = partner_demo(models, uid, password)
    out: dict[int, float] = {}
    for i in range(0, len(variant_ids), batch):
        chunk = variant_ids[i : i + batch]
        lines = [(0, 0, {"product_id": pid, "product_uom_qty": 1}) for pid in chunk]
        so_id = models.execute_kw(
            ODOO_CONFIG["db"],
            uid,
            password,
            "sale.order",
            "create",
            [{"partner_id": partner_id, "pricelist_id": pricelist_id, "order_line": lines}],
        )
        try:
            so = models.execute_kw(
                ODOO_CONFIG["db"],
                uid,
                password,
                "sale.order",
                "read",
                [so_id],
                {"fields": ["order_line"]},
            )[0]
            line_data = models.execute_kw(
                ODOO_CONFIG["db"],
                uid,
                password,
                "sale.order.line",
                "read",
                [so["order_line"]],
                {"fields": ["product_id", "price_unit"]},
            )
            for row in line_data:
                pid = row["product_id"][0] if row.get("product_id") else None
                if pid is not None:
                    out[pid] = float(row.get("price_unit") or 0.0)
        finally:
            models.execute_kw(
                ODOO_CONFIG["db"], uid, password, "sale.order", "unlink", [[so_id]]
            )
    return out


def aplicar_fallback_lst_price(
    models, uid, password, variant_ids: list[int], precios: dict[int, float], batch: int = 250
) -> int:
    """Si precios[vid] <= 0, rellena con lst_price del product.product si es > 0."""
    need = [vid for vid in variant_ids if precios.get(vid, 0) <= 0]
    usados = 0
    for i in range(0, len(need), batch):
        chunk = need[i : i + batch]
        rows = models.execute_kw(
            ODOO_CONFIG["db"],
            uid,
            password,
            "product.product",
            "read",
            [chunk],
            {"fields": ["id", "lst_price"]},
        )
        for r in rows:
            lp = float(r.get("lst_price") or 0.0)
            if lp > 0:
                precios[r["id"]] = lp
                usados += 1
    return usados


def main():
    parser = argparse.ArgumentParser(
        description="Dry-run snapshot de lista de precios desde una lista de referencia (master_dev)"
    )
    parser.add_argument(
        "--lista-referencia",
        default="Lista 2 Consumidor Final Autoservicios CR",
        help="Nombre de la lista en Odoo cuyo precio efectivo se congela",
    )
    parser.add_argument(
        "--nombre-nueva",
        default="Belgrano Final Comodoro",
        help="Nombre de la lista nueva (solo con --apply)",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=35,
        help="Variantes por cotización temporal (XML-RPC)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Solo las primeras N variantes (0 = todas)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Crear lista e ítems fijos (sin esto solo informe)",
    )
    parser.add_argument(
        "--no-lst-price-fallback",
        action="store_true",
        help="No usar lst_price cuando el precio de la lista referencia sea ≤ 0",
    )
    args = parser.parse_args()

    print("=" * 72)
    print("SNAPSHOT LISTA DESDE REFERENCIA —", "APPLY" if args.apply else "DRY-RUN")
    print("=" * 72)
    print(f"Base: {ODOO_CONFIG['db']}")
    print(f"Lista referencia: {args.lista_referencia!r}")
    print(f"Lista nueva: {args.nombre_nueva!r}")
    print(f"Batch SO: {args.batch} | Límite variantes: {args.limit or 'sin límite'}")
    print("=" * 72)

    models, uid = conectar_odoo()
    if not models or not uid:
        print("❌ Autenticación fallida")
        sys.exit(1)
    pwd = ODOO_CONFIG["pass"]

    ref = obtener_lista_por_nombre(models, uid, pwd, args.lista_referencia)
    if not ref:
        print(f"❌ No se encontró la lista de referencia: {args.lista_referencia!r}")
        sys.exit(1)
    ref_id = ref["id"]
    print(f"✅ Lista referencia: id={ref_id} nombre={ref['name']!r}")

    variantes = models.execute_kw(
        ODOO_CONFIG["db"],
        uid,
        pwd,
        "product.product",
        "search_read",
        [[("sale_ok", "=", True)]],
        {"fields": ["id", "product_tmpl_id", "default_code", "active"]},
    )
    variantes = [v for v in variantes if v.get("active", True)]
    if args.limit and args.limit > 0:
        variantes = variantes[: args.limit]
    vids = [v["id"] for v in variantes]
    print(f"📦 Variantes sale_ok a procesar: {len(vids)}")

    t0 = time.perf_counter()
    precios_var = precios_por_variante_en_lotes(models, uid, pwd, ref_id, vids, args.batch)
    elapsed = time.perf_counter() - t0
    print(f"⏱️  Precios resueltos en {elapsed:.1f}s ({len(precios_var)} variantes)")

    if not args.no_lst_price_fallback:
        n_fb = aplicar_fallback_lst_price(models, uid, pwd, vids, precios_var)
        print(f"📌 Fallback lst_price aplicado en {n_fb} variantes (precio lista ref. era ≤ 0)")

    # Agregar por template: una línea de lista por template (como migrar_lista1)
    tmpl_to_prices: dict[int, list[tuple[int, float, str]]] = defaultdict(list)
    for v in variantes:
        vid = v["id"]
        tmpl = v["product_tmpl_id"][0] if v.get("product_tmpl_id") else None
        if tmpl is None:
            continue
        code = (v.get("default_code") or "").strip() or "(sin código)"
        p = precios_var.get(vid, 0.0)
        tmpl_to_prices[tmpl].append((vid, p, code))

    conflictos = 0
    items_plan: list[tuple[int, float, int | None, str]] = []
    for tmpl_id, filas in tmpl_to_prices.items():
        precios = {round(x[1], 6) for x in filas}
        if len(precios) > 1:
            conflictos += 1
        # Regla fija por template: usar precio máximo del template (conservador para no subfacturar)
        best = max(filas, key=lambda x: x[1])
        items_plan.append((tmpl_id, best[1], best[0], best[2]))

    cero = sum(1 for _, pr, _, _ in items_plan if pr <= 0)
    items_plan.sort(key=lambda x: -x[1])

    print()
    print("📊 RESUMEN DRY-RUN")
    print("-" * 72)
    print(f"   Plantillas distintas (líneas a crear): {len(items_plan)}")
    print(f"   Variantes procesadas:                    {len(vids)}")
    print(f"   Plantillas con variantes a distinto precio: {conflictos}")
    print(f"   Líneas con precio ≤ 0 (tras fallback):    {cero}")
    print("-" * 72)
    print("   Muestra 12 líneas (template_id, precio, código variante elegida):")
    for row in items_plan[:12]:
        print(f"      tmpl={row[0]}  precio={row[1]:.4f}  var={row[2]}  {row[3]!r}")
    if len(items_plan) > 12:
        print(f"      … ({len(items_plan) - 12} más)")
    print("-" * 72)

    if args.apply:
        exist = models.execute_kw(
            ODOO_CONFIG["db"],
            uid,
            pwd,
            "product.pricelist",
            "search",
            [[("name", "=", args.nombre_nueva)]],
            {"limit": 1},
        )
        if exist:
            print(f"❌ Ya existe lista con nombre exacto {args.nombre_nueva!r} (id={exist[0]})")
            sys.exit(1)
        cur = ref.get("currency_id")
        cur_id = cur[0] if cur else False
        vals = {"name": args.nombre_nueva, "currency_id": cur_id}
        nueva_id = models.execute_kw(
            ODOO_CONFIG["db"], uid, pwd, "product.pricelist", "create", [vals]
        )
        print(f"✅ Lista creada id={nueva_id}")
        creados = 0
        err = 0
        t_apply = time.perf_counter()
        for n, row in enumerate(items_plan, 1):
            tmpl_id, precio, _, _ = row
            if precio <= 0:
                continue
            try:
                models.execute_kw(
                    ODOO_CONFIG["db"],
                    uid,
                    pwd,
                    "product.pricelist.item",
                    "create",
                    [
                        {
                            "pricelist_id": nueva_id,
                            "applied_on": "1_product",
                            "product_tmpl_id": tmpl_id,
                            "compute_price": "fixed",
                            "fixed_price": precio,
                        }
                    ],
                )
                creados += 1
            except Exception as e:
                err += 1
                print(f"⚠️  tmpl {tmpl_id}: {e}")
            if n % 500 == 0:
                print(f"   … ítems creados {creados} / {n} plantillas procesadas")
        print(
            f"✅ Ítems creados: {creados} | errores: {err} | omitidos precio≤0: {cero} "
            f"| tiempo creación {time.perf_counter() - t_apply:.1f}s"
        )
    else:
        print()
        print("💡 Modo solo lectura. Para crear la lista e ítems: añadir --apply")
        print("   (hacer backup y validar en horario conveniente).")

    print("=" * 72)


if __name__ == "__main__":
    main()
