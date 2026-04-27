#!/usr/bin/env python3
"""
Mueve stock físico en Nakel SA desde CEN/Existencias hacia CEN/Roturas 2
basándose en líneas de pedidos/cotizaciones (sale.order) listados por nombre.

Política: mueve min(pedido, disponible) por producto en CEN/Existencias.

Uso (desde la raíz del vault nakel):
  python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py --dry-run --orden S02202
  python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py --apply --orden S02202 --orden S02203

Requiere config_nakel.py en PYTHONPATH (mismo patrón que otros scripts del vault).
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

import xmlrpc.client


def _chunked(ids: List[int], size: int) -> Iterable[List[int]]:
    for i in range(0, len(ids), size):
        yield ids[i : i + size]


def _sum_quant_qty(models, db: int, uid: int, password: str, location_id: int, product_id: int) -> float:
    dom = [("location_id", "=", location_id), ("product_id", "=", product_id), ("quantity", ">", 0)]
    qids = models.execute_kw(db, uid, password, "stock.quant", "search", [dom])
    if not qids:
        return 0.0
    total = 0.0
    for part in _chunked(qids, 500):
        rows = models.execute_kw(db, uid, password, "stock.quant", "read", [part], {"fields": ["quantity"]})
        total += sum(float(r.get("quantity") or 0.0) for r in rows)
    return total


def _get_xmlrpc_models(cfg: dict):
    url = cfg["url"].rstrip("/")
    db = cfg["db"]
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, cfg["username"], cfg["password"], {})
    if not uid:
        raise RuntimeError("Autenticación XML-RPC fallida (revisar credenciales).")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    return db, uid, models


def _resolve_locations(models, db: int, uid: int, password: str, company_id: int) -> Tuple[int, int]:
    def _loc(complete_name: str) -> int:
        recs = models.execute_kw(
            db,
            uid,
            password,
            "stock.location",
            "search_read",
            [[("complete_name", "=", complete_name), ("company_id", "=", company_id)]],
            {"fields": ["id"], "limit": 1},
        )
        if not recs:
            raise RuntimeError(f"No se encontró ubicación {complete_name!r} para company_id={company_id}")
        return recs[0]["id"]

    src = _loc("CEN/Existencias")
    dst = _loc("CEN/Roturas 2")
    return src, dst


def _resolve_internal_picking_type(models, db: int, uid: int, password: str, warehouse_code: str) -> int:
    wh = models.execute_kw(
        db,
        uid,
        password,
        "stock.warehouse",
        "search_read",
        [[("code", "=", warehouse_code)]],
        {"fields": ["id", "name", "company_id"], "limit": 1},
    )
    if not wh:
        raise RuntimeError(f"No se encontró almacén con code={warehouse_code!r}")
    wh_id = wh[0]["id"]

    pts = models.execute_kw(
        db,
        uid,
        password,
        "stock.picking.type",
        "search_read",
        [[("warehouse_id", "=", wh_id), ("code", "=", "internal")]],
        {"fields": ["id", "name", "warehouse_id", "company_id", "default_location_src_id", "default_location_dest_id"], "limit": 20},
    )
    if not pts:
        raise RuntimeError(f"No se encontró picking type internal para warehouse_id={wh_id}")
    # Preferir el internal “genérico” del almacén (normalmente hay 1).
    return pts[0]["id"]


def _needs_by_orders(models, db: int, uid: int, password: str, order_names: List[str]) -> Dict[str, Dict[int, float]]:
    per_order: Dict[str, Dict[int, float]] = {}
    for name in order_names:
        sos = models.execute_kw(
            db,
            uid,
            password,
            "sale.order",
            "search_read",
            [[("name", "=", name)]],
            {"fields": ["id", "name", "company_id", "state"], "limit": 5},
        )
        if not sos:
            raise RuntimeError(f"No existe sale.order con name={name!r}")
        if len(sos) > 1:
            raise RuntimeError(f"Hay más de un sale.order con name={name!r} (ambiguo).")

        so_id = sos[0]["id"]
        line_ids = models.execute_kw(
            db,
            uid,
            password,
            "sale.order.line",
            "search",
            [[("order_id", "=", so_id), ("display_type", "=", False)]],
        )
        if not line_ids:
            per_order[name] = {}
            continue

        need: Dict[int, float] = defaultdict(float)
        for part in _chunked(line_ids, 500):
            lines = models.execute_kw(db, uid, password, "sale.order.line", "read", [part], {"fields": ["product_id", "product_uom_qty"]})
            for l in lines:
                pid = l["product_id"][0]
                need[pid] += float(l.get("product_uom_qty") or 0.0)
        per_order[name] = dict(need)
    return per_order


def main() -> int:
    p = argparse.ArgumentParser(description="Mueve disponible CEN/Existencias -> CEN/Roturas 2 basado en sale.order names.")
    p.add_argument("--orden", action="append", default=[], help="Nombre exacto de sale.order (repetible), ej: S02202")
    p.add_argument(
        "--ordenes",
        default="",
        help="Lista separada por comas de nombres de órdenes, ej: S02202,S02203",
    )
    p.add_argument(
        "--archivo-ordenes",
        default="",
        help="Ruta a un archivo de texto: una orden por línea (se ignoran líneas vacías y #comentarios).",
    )
    p.add_argument("--warehouse-code", default="CEN", help="Código de almacén para resolver picking type internal (default: CEN)")
    p.add_argument("--company-nakel", type=int, default=1, help="Company_id de Nakel SA (default: 1)")
    p.add_argument("--dry-run", action="store_true", help="No crea pickings; solo reporta.")
    p.add_argument("--apply", action="store_true", help="Crea y valida pickings (traslados internos).")

    args = p.parse_args()
    if args.dry_run == args.apply:
        p.error("Elegí exactamente uno: --dry-run o --apply")

    order_names = [o.strip() for o in (args.orden or []) if o and o.strip()]
    if args.ordenes.strip():
        order_names.extend([x.strip() for x in args.ordenes.split(",") if x.strip()])
    if args.archivo_ordenes.strip():
        path = args.archivo_ordenes.strip()
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                order_names.append(line)
    # unique preserve order
    seen = set()
    uniq: List[str] = []
    for o in order_names:
        if o not in seen:
            uniq.append(o)
            seen.add(o)
    order_names = uniq
    if not order_names:
        p.error("Pasá órdenes con --orden (repetible) o --ordenes CSV")

    # import config
    cfg_root = os.environ.get("NAKEL_CONFIG_ROOT", "/media/klap/raid5/cursor_files")
    if cfg_root not in sys.path:
        sys.path.insert(0, cfg_root)
    from config_nakel import ODOO_CONFIG_MASTER_DEV  # type: ignore

    cfg = ODOO_CONFIG_MASTER_DEV
    db, uid, models = _get_xmlrpc_models(cfg)
    password = cfg["password"]

    company_id = int(args.company_nakel)
    src_loc, dst_loc = _resolve_locations(models, db, uid, password, company_id)
    picking_type_id = _resolve_internal_picking_type(models, db, uid, password, args.warehouse_code)

    per_order = _needs_by_orders(models, db, uid, password, order_names)

    print(f"Nakel company_id={company_id} | src={src_loc} dst={dst_loc} | picking_type_id={picking_type_id}")
    print("Modo:", "DRY-RUN" if args.dry_run else "APPLY")

    for oname in order_names:
        need = per_order.get(oname, {})
        print(f"\n=== Orden {oname} ===")
        print("Productos distintos en líneas:", len(need))

        moves: List[dict] = []
        moved_lines = 0
        skipped_zero_need = 0
        skipped_zero_avail = 0

        # estable para salida
        for pid, q_need in sorted(need.items(), key=lambda kv: kv[0]):
            if q_need <= 0:
                skipped_zero_need += 1
                continue
            avail = _sum_quant_qty(models, db, uid, password, src_loc, pid)
            qty = min(q_need, avail)
            if qty <= 0:
                skipped_zero_avail += 1
                continue

            uom = models.execute_kw(db, uid, password, "product.product", "read", [[pid]], {"fields": ["uom_id"]})[0]["uom_id"]
            moves.append(
                {
                    "name": oname,
                    "product_id": pid,
                    "product_uom": uom[0],
                    "product_uom_qty": qty,
                    "location_id": src_loc,
                    "location_dest_id": dst_loc,
                    "company_id": company_id,
                }
            )
            moved_lines += 1

        print("Líneas a mover (productos con qty>0):", moved_lines)
        print("Saltados por pedido<=0:", skipped_zero_need)
        print("Saltados por disponible<=0:", skipped_zero_avail)

        if args.dry_run:
            continue

        if not moves:
            print("APPLY: nada para crear (sin líneas).")
            continue

        picking_vals = {
            "picking_type_id": picking_type_id,
            "location_id": src_loc,
            "location_dest_id": dst_loc,
            "origin": f"{oname} -> Roturas2 (mover disponible)",
            "company_id": company_id,
            "move_ids": [[0, 0, v] for v in moves],
        }
        pid_pick = models.execute_kw(db, uid, password, "stock.picking", "create", [picking_vals])
        models.execute_kw(db, uid, password, "stock.picking", "action_confirm", [[pid_pick]])

        # Asignar reservas (si aplica)
        try:
            models.execute_kw(db, uid, password, "stock.picking", "action_assign", [[pid_pick]])
        except xmlrpc.client.Fault:
            # Algunas bases/configs pueden no exponerlo igual; el validate igual puede pedir cantidades.
            pass

        res = models.execute_kw(db, uid, password, "stock.picking", "button_validate", [[pid_pick]])
        # En Odoo recientes button_validate puede devolver un wizard dict; si pasa, no asumimos éxito.
        if isinstance(res, dict) and res.get("res_model"):
            raise RuntimeError(
                f"button_validate devolvió un wizard ({res.get('res_model')}). "
                f"Picking id={pid_pick}. Revisar reservas/lotes/ubicaciones."
            )

        print("APPLY: picking creado y validado:", pid_pick)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
