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


def _resolve_crm_tag_id(models, db: int, uid: int, password: str, *, name: str) -> int | None:
    """
    Resuelve el ID de crm.tag por nombre exacto (case sensitive como en Odoo).
    Devuelve None si no existe.
    """
    rows = models.execute_kw(
        db,
        uid,
        password,
        "crm.tag",
        "search_read",
        [[("name", "=", name)]],
        {"fields": ["id", "name"], "limit": 2},
    )
    if not rows:
        return None
    if len(rows) > 1:
        raise RuntimeError(f"crm.tag ambiguo para name={name!r}: {rows}")
    return int(rows[0]["id"])


def _ensure_crm_tag_id(models, db: int, uid: int, password: str, *, name: str, color: int = 3) -> int:
    tid = _resolve_crm_tag_id(models, db, uid, password, name=name)
    if tid:
        return tid
    return int(
        models.execute_kw(
            db,
            uid,
            password,
            "crm.tag",
            "create",
            [{"name": name, "color": int(color)}],
        )
    )


def _select_orders_by_tag(
    models,
    db: int,
    uid: int,
    password: str,
    *,
    company_nak_id: int,
    only_draft: bool,
    must_have_tag_id: int,
    skip_tag_id: int | None,
    limit: int | None = None,
) -> List[str]:
    dom = [("company_id", "=", int(company_nak_id))]
    if only_draft:
        dom.append(("state", "=", "draft"))
    dom.append(("tag_ids", "in", [int(must_have_tag_id)]))
    if skip_tag_id is not None:
        dom.append(("tag_ids", "not in", [int(skip_tag_id)]))

    opts = {"fields": ["name"], "order": "id asc"}
    if limit:
        opts["limit"] = int(limit)
    rows = models.execute_kw(db, uid, password, "sale.order", "search_read", [dom], opts)
    return [r["name"] for r in rows if r.get("name")]


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


def _ensure_move_lines_for_unreserved_moves(
    models,
    db: int,
    uid: int,
    password: str,
    picking_id: int,
) -> int:
    """
    Si algún stock.move tiene demanda > 0 pero sin líneas de detalle (Odoo no reservó),
    crea una stock.move.line con qty_done = demanda para poder validar.
    Devuelve cantidad de líneas creadas.
    """
    p = models.execute_kw(db, uid, password, "stock.picking", "read", [[picking_id]], {"fields": ["move_ids"]})[0]
    created = 0
    for mid in p.get("move_ids") or []:
        mv = models.execute_kw(
            db,
            uid,
            password,
            "stock.move",
            "read",
            [[mid]],
            {
                "fields": [
                    "product_id",
                    "product_uom",
                    "product_uom_qty",
                    "quantity",
                    "move_line_ids",
                    "location_id",
                    "location_dest_id",
                    "state",
                ]
            },
        )[0]
        qty_need = float(mv.get("product_uom_qty") or 0.0)
        if qty_need <= 0:
            continue
        if mv.get("move_line_ids"):
            continue
        loc_src = mv["location_id"][0]
        loc_dst = mv["location_dest_id"][0]
        prod_id = mv["product_id"][0]
        uom_id = mv["product_uom"][0] if mv.get("product_uom") else None
        if not uom_id:
            pr = models.execute_kw(db, uid, password, "product.product", "read", [[prod_id]], {"fields": ["uom_id"]})[0]
            uom_id = pr["uom_id"][0]
        models.execute_kw(
            db,
            uid,
            password,
            "stock.move.line",
            "create",
            [
                {
                    "move_id": mid,
                    "picking_id": picking_id,
                    "product_id": prod_id,
                    "location_id": loc_src,
                    "location_dest_id": loc_dst,
                    "product_uom_id": uom_id,
                    "qty_done": qty_need,
                }
            ],
        )
        created += 1
    return created


def _finalize_pickings_same_origin(
    models,
    db: int,
    uid: int,
    password: str,
    *,
    origin: str,
    company_id: int,
) -> None:
    """
    Odoo a veces parte un traslado en varios pickings con el mismo `origin`.
    Cierra los que queden en draft/waiting/confirmed/assigned (misma compañía).
    """
    dom = [
        ("origin", "=", origin),
        ("company_id", "=", company_id),
        ("state", "not in", ("done", "cancel")),
    ]
    extra_ids = models.execute_kw(db, uid, password, "stock.picking", "search", [dom], {"order": "id asc"})
    if not extra_ids:
        return
    print(f"APPLY: detectados {len(extra_ids)} albarán(es) pendiente(s) mismo origin={origin!r} → finalizando…")
    for oid in extra_ids:
        st = models.execute_kw(db, uid, password, "stock.picking", "read", [[oid]], {"fields": ["name", "state"]})[0]
        state = st["state"]
        if state == "draft":
            models.execute_kw(db, uid, password, "stock.picking", "action_confirm", [[oid]])
        try:
            models.execute_kw(db, uid, password, "stock.picking", "action_assign", [[oid]])
        except xmlrpc.client.Fault:
            pass
        n = _ensure_move_lines_for_unreserved_moves(models, db, uid, password, oid)
        if n:
            print(f"  picking {oid} ({st.get('name')}): creadas {n} línea(s) move_line (sin reserva previa)")
        res = models.execute_kw(
            db,
            uid,
            password,
            "stock.picking",
            "button_validate",
            [[oid]],
            {"context": {"skip_backorder": True}},
        )
        if isinstance(res, dict) and res.get("res_model"):
            raise RuntimeError(
                f"No se pudo validar picking relacionado id={oid} ({st.get('name')}): "
                f"wizard {res.get('res_model')}. Revisar en Odoo."
            )
        print(f"  picking {oid} ({st.get('name')}): validado")


def _needs_by_orders(
    models,
    db: int,
    uid: int,
    password: str,
    order_names: List[str],
    *,
    company_nak_id: int,
    only_draft: bool = True,
    skip_tag_id: int | None = None,
    require_tag_id: int | None = None,
) -> Dict[str, Dict[int, float]]:
    """
    Lee líneas de venta solo de cotizaciones NAK: no modifica sale.order.
    - company_nak_id: compañía Nak (en master_dev suele ser 2; Nakel SA es 1).
    - only_draft: True = solo state 'draft' (cotización); no tocar ventas confirmadas.
    """
    per_order: Dict[str, Dict[int, float]] = {}
    for name in order_names:
        sos = models.execute_kw(
            db,
            uid,
            password,
            "sale.order",
            "search_read",
            [[("name", "=", name)]],
            {"fields": ["id", "name", "company_id", "state", "tag_ids"], "limit": 5},
        )
        if not sos:
            raise RuntimeError(f"No existe sale.order con name={name!r}")
        if len(sos) > 1:
            raise RuntimeError(f"Hay más de un sale.order con name={name!r} (ambiguo).")

        so = sos[0]
        cid = so["company_id"][0] if so.get("company_id") else None
        st = so.get("state")
        if cid != company_nak_id:
            raise RuntimeError(
                f"Orden {name!r} es de compañía {so.get('company_id')!r}. "
                f"Solo se aceptan cotizaciones/ventas de NAK (company_id={company_nak_id}). "
                f"No se procesan pedidos de Nakel SA ni otras compañías."
            )
        if only_draft and st != "draft":
            raise RuntimeError(
                f"Orden {name!r} no está en borrador (state={st!r}). "
                f"Solo se procesan cotizaciones (draft) de NAK. Confirmá o cancelá manualmente otra lógica si aplica."
            )

        if require_tag_id is not None:
            tags = so.get("tag_ids") or []
            if int(require_tag_id) not in [int(t) for t in tags]:
                print(f"SKIP: Orden {name!r} no tiene tag_id={require_tag_id} (etiqueta requerida).")
                per_order[name] = {}
                continue

        if skip_tag_id is not None:
            tags = so.get("tag_ids") or []
            if int(skip_tag_id) in [int(t) for t in tags]:
                print(f"SKIP: Orden {name!r} ya tiene tag_id={skip_tag_id} (marcada como procesada).")
                per_order[name] = {}
                continue

        so_id = so["id"]
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
    p.add_argument("--company-nak", type=int, default=2, help="Company_id de Nak (cotizaciones a leer; default: 2). No usar Nakel SA aquí.")
    p.add_argument(
        "--permitir-venta-confirmada",
        action="store_true",
        help="Inseguro: acepta sale.order con state distinto de draft. Por defecto solo borrador (cotización).",
    )
    p.add_argument("--company-nakel", type=int, default=1, help="Company_id de Nakel SA para el picking interno (default: 1)")
    p.add_argument("--dry-run", action="store_true", help="No crea pickings; solo reporta.")
    p.add_argument("--apply", action="store_true", help="Crea y valida pickings (traslados internos).")
    p.add_argument(
        "--skip-tag-name",
        default="ProcesadaNN",
        help="Nombre exacto de crm.tag en sale.order.tag_ids para SALTEAR cotizaciones ya marcadas (default: ProcesadaNN). Usar '' para deshabilitar.",
    )
    p.add_argument(
        "--skip-tag-id",
        type=int,
        default=0,
        help="ID de crm.tag para SALTEAR cotizaciones ya marcadas (tiene prioridad sobre --skip-tag-name). 0 = deshabilitado.",
    )
    p.add_argument(
        "--mark-processed",
        action="store_true",
        help="En modo --apply, marca la cotización NAK con el tag (evita reprocesos).",
    )
    p.add_argument(
        "--ensure-tag",
        action="store_true",
        help="Si el tag no existe, lo crea (solo si --mark-processed o si se usa para skip por nombre).",
    )
    p.add_argument(
        "--listar-omitidos",
        action="store_true",
        help="Lista productos de la cotización con pedido>0 pero stock=0 en CEN/Existencias (no se crea movimiento; es esperado).",
    )

    # Flujo por etiquetas (NAK): "Procesar" -> ejecutar -> marcar "ProcesadaNN"
    p.add_argument(
        "--auto-desde-tag-procesar",
        action="store_true",
        help="Si no se pasan --orden/--ordenes/--archivo-ordenes, selecciona automáticamente cotizaciones de NAK con el tag 'Procesar' (configurable).",
    )
    p.add_argument(
        "--require-tag-procesar",
        action="store_true",
        help="Aun si pasás órdenes por nombre, exige que tengan la etiqueta 'Procesar' (si no, se saltean).",
    )
    p.add_argument(
        "--tag-procesar-name",
        default="procesar",
        help="Nombre exacto de crm.tag para indicar 'a procesar' (default: procesar). Usar '' para deshabilitar este criterio.",
    )
    p.add_argument(
        "--tag-procesar-id",
        type=int,
        default=0,
        help="ID de crm.tag para indicar 'a procesar' (tiene prioridad sobre --tag-procesar-name). 0 = deshabilitado.",
    )
    p.add_argument(
        "--limit-auto",
        type=int,
        default=0,
        help="Límite de cotizaciones a seleccionar cuando se usa --auto-desde-tag-procesar (0 = sin límite).",
    )

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
    # Nota: si no hay órdenes, puede haber auto-selección por tag (se resuelve tras conectar).

    # import config
    cfg_root = os.environ.get("NAKEL_CONFIG_ROOT", "/media/klap/raid5/cursor_files")
    if cfg_root not in sys.path:
        sys.path.insert(0, cfg_root)
    from config_nakel import ODOO_CONFIG_MASTER_DEV  # type: ignore

    cfg = ODOO_CONFIG_MASTER_DEV
    db, uid, models = _get_xmlrpc_models(cfg)
    password = cfg["password"]

    # Resolver tag "Procesar" (opcional)
    procesar_tag_id: int | None = None
    if int(args.tag_procesar_id or 0) > 0:
        procesar_tag_id = int(args.tag_procesar_id)
    else:
        tag_name = (args.tag_procesar_name or "").strip()
        if tag_name:
            procesar_tag_id = _resolve_crm_tag_id(models, db, uid, password, name=tag_name)
            if procesar_tag_id is None and (args.auto_desde_tag_procesar or args.require_tag_procesar):
                raise RuntimeError(f"No existe crm.tag name={tag_name!r} (requerido para el modo por etiquetas).")

    skip_tag_id: int | None = None
    skip_tag_name = (args.skip_tag_name or "").strip()
    if int(args.skip_tag_id or 0) > 0:
        skip_tag_id = int(args.skip_tag_id)
    elif skip_tag_name:
        if args.ensure_tag:
            skip_tag_id = _ensure_crm_tag_id(models, db, uid, password, name=skip_tag_name)
        else:
            skip_tag_id = _resolve_crm_tag_id(models, db, uid, password, name=skip_tag_name)
            if skip_tag_id is None:
                print(f"WARNING: skip-tag-name={skip_tag_name!r} no existe; no se salteará por tag.")
                skip_tag_id = None

    company_id = int(args.company_nakel)
    src_loc, dst_loc = _resolve_locations(models, db, uid, password, company_id)
    picking_type_id = _resolve_internal_picking_type(models, db, uid, password, args.warehouse_code)

    only_draft = not args.permitir_venta_confirmada

    if not order_names:
        if args.auto_desde_tag_procesar:
            if not procesar_tag_id:
                raise RuntimeError("auto-desde-tag-procesar requiere --tag-procesar-id o --tag-procesar-name válido.")
            lim = int(args.limit_auto or 0)
            order_names = _select_orders_by_tag(
                models,
                db,
                uid,
                password,
                company_nak_id=int(args.company_nak),
                only_draft=only_draft,
                must_have_tag_id=int(procesar_tag_id),
                skip_tag_id=skip_tag_id,
                limit=lim if lim > 0 else None,
            )
            if not order_names:
                print("No hay cotizaciones con tag 'Procesar' para procesar (o ya están marcadas como procesadas).")
                return 0
            print(
                f"Auto-selección por tag: {len(order_names)} orden(es): "
                f"{', '.join(order_names[:20])}{'…' if len(order_names) > 20 else ''}"
            )
        else:
            p.error("Pasá órdenes con --orden/--ordenes/--archivo-ordenes, o usá --auto-desde-tag-procesar.")

    per_order = _needs_by_orders(
        models,
        db,
        uid,
        password,
        order_names,
        company_nak_id=int(args.company_nak),
        only_draft=only_draft,
        skip_tag_id=skip_tag_id,
        require_tag_id=int(procesar_tag_id) if (args.require_tag_procesar and procesar_tag_id) else None,
    )

    print(
        f"Lectura ventas: NAK company_id={args.company_nak} | solo_draft={only_draft} "
        f"(sale.order solo lectura; no se modifica la cotización)"
    )
    print(f"Stock/picking: Nakel SA company_id={company_id} | src={src_loc} dst={dst_loc} | picking_type_id={picking_type_id}")
    print("Modo:", "DRY-RUN" if args.dry_run else "APPLY")

    for oname in order_names:
        need = per_order.get(oname, {})
        print(f"\n=== Orden {oname} ===")
        print("Productos distintos en líneas:", len(need))

        moves: List[dict] = []
        moved_lines = 0
        skipped_zero_need = 0
        sin_stock_en_origen: List[Tuple[int, float, float]] = []  # pid, pedido, disponible
        movimiento_parcial = 0  # 0 < disp < pedido

        # Por producto: solo se crea línea si hay cantidad > 0 a mover (min(pedido, disp)).
        # Si disponible en CEN/Existencias es 0, no hay nada que mover → se omite (comportamiento esperado).
        for pid, q_need in sorted(need.items(), key=lambda kv: kv[0]):
            if q_need <= 0:
                skipped_zero_need += 1
                continue
            avail = _sum_quant_qty(models, db, uid, password, src_loc, pid)
            qty = min(q_need, avail)
            if avail <= 0 and q_need > 0:
                sin_stock_en_origen.append((pid, q_need, avail))
            elif 0 < avail < q_need:
                movimiento_parcial += 1
            if qty <= 0:
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

        print("Líneas de movimiento a crear (producto con cantidad > 0 a mover):", moved_lines)
        print("Líneas de cotización con pedido<=0 (omitidas):", skipped_zero_need)
        print(
            "Productos con pedido>0 pero stock=0 en CEN/Existencias (no se mueve nada; dado por hecho):",
            len(sin_stock_en_origen),
        )
        if movimiento_parcial:
            print(
                "Productos con movimiento parcial (se mueve min(pedido, disp), queda faltante en cotización):",
                movimiento_parcial,
            )
        if args.listar_omitidos and sin_stock_en_origen:
            pids = [t[0] for t in sin_stock_en_origen]
            names = {}
            for part in _chunked(pids, 200):
                prods = models.execute_kw(db, uid, password, "product.product", "read", [part], {"fields": ["display_name"]})
                for pr in prods:
                    names[pr["id"]] = pr.get("display_name") or str(pr["id"])
            print("  Detalle (sin stock en origen):")
            for pid, q_need, avail in sin_stock_en_origen[:80]:
                print(f"    - [{pid}] {names.get(pid, '?')!s} | pedido={q_need} disp={avail}")
            if len(sin_stock_en_origen) > 80:
                print(f"    ... y {len(sin_stock_en_origen) - 80} más")

        if args.dry_run:
            continue

        if not moves:
            print("APPLY: nada para crear (sin líneas).")
            continue

        origin_str = f"{oname} -> Roturas2 (mover disponible)"
        picking_vals = {
            "picking_type_id": picking_type_id,
            "location_id": src_loc,
            "location_dest_id": dst_loc,
            "origin": origin_str,
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

        # Evita wizard stock.backorder.confirmation en traslados internos largos (no crear backorder).
        res = models.execute_kw(
            db,
            uid,
            password,
            "stock.picking",
            "button_validate",
            [[pid_pick]],
            {"context": {"skip_backorder": True}},
        )
        if isinstance(res, dict) and res.get("res_model"):
            raise RuntimeError(
                f"button_validate devolvió un wizard ({res.get('res_model')}). "
                f"Picking id={pid_pick}. Revisar reservas/lotes/ubicaciones."
            )

        _finalize_pickings_same_origin(
            models, db, uid, password, origin=origin_str, company_id=company_id
        )
        print("APPLY: picking principal validado:", pid_pick)

        if args.mark_processed:
            if not (skip_tag_id or skip_tag_name):
                raise RuntimeError("mark-processed requiere --skip-tag-id o --skip-tag-name (no vacío).")
            tag_id_to_set = skip_tag_id
            if tag_id_to_set is None and skip_tag_name:
                # si no se resolvió antes, resolver/crear ahora
                if args.ensure_tag:
                    tag_id_to_set = _ensure_crm_tag_id(models, db, uid, password, name=skip_tag_name)
                else:
                    tag_id_to_set = _resolve_crm_tag_id(models, db, uid, password, name=skip_tag_name)
            if not tag_id_to_set:
                raise RuntimeError("No se pudo resolver el tag para mark-processed (revisar nombre/ID).")
            so_id = models.execute_kw(
                db,
                uid,
                password,
                "sale.order",
                "search",
                [[("name", "=", oname)]],
                {"limit": 2},
            )
            if so_id:
                # add "ProcesadaNN" tag without removing others
                models.execute_kw(
                    db,
                    uid,
                    password,
                    "sale.order",
                    "write",
                    [so_id, {"tag_ids": [(4, int(tag_id_to_set))]}],
                )
                # remove "procesar" tag to avoid confusion in the workflow
                if procesar_tag_id:
                    models.execute_kw(
                        db,
                        uid,
                        password,
                        "sale.order",
                        "write",
                        [so_id, {"tag_ids": [(3, int(procesar_tag_id))]}],
                    )
                    print(
                        f"APPLY: cotización {oname} marcada ProcesadaNN (tag_id={tag_id_to_set}) y quitado tag 'procesar' (tag_id={procesar_tag_id})"
                    )
                else:
                    print(f"APPLY: cotización {oname} marcada ProcesadaNN (tag_id={tag_id_to_set})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
