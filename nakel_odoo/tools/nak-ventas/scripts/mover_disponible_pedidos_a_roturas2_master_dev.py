#!/usr/bin/env python3
"""
Mueve stock físico hacia Roturas 2 basándose en líneas de cotizaciones (sale.order en borrador).

Perfiles documentados en MOVER_DISPONIBLE_PEDIDOS_A_ROTURAS2_MASTER_DEV.md:
- CEN (default): cotizaciones NAK, stock CEN/Existencias → CEN/Roturas 2 en Nakel SA.
- B3: cotizaciones Nakel SA (Belgrano 3), stock B3/Existencias → B3/Roturas 2.

Política: mueve min(pedido, disponible) por producto en el origen del perfil.

Por defecto solo cotizaciones con crm.tag **procesar**. Tras --apply se quita procesar y
se agrega **ProcesadaNN**, incluso si no hubo stock que mover (evita reprocesar por error).

Si no pasás --orden/--ordenes/--archivo-ordenes, el script lista solo cotizaciones
NAK en borrador que tengan **procesar** y no tengan aún la etiqueta de “ya procesada”.

Opcional: exportá `NAKEL_MOVER_TAG_PROCESAR_ID` y `NAKEL_MOVER_SKIP_TAG_ID` para usar esos
`crm.tag` por defecto sin repetir `--tag-procesar-id` / `--skip-tag-id` en cada comando.

Uso (desde la raíz del vault nakel):
  python3 .../mover_disponible_pedidos_a_roturas2_master_dev.py --dry-run
  python3 .../mover_disponible_pedidos_a_roturas2_master_dev.py --apply

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


def _default_crm_tag_id_from_env(var: str) -> int:
    """Entero >0 desde variable de entorno, o 0 si no está definida / inválida."""
    raw = (os.environ.get(var) or "").strip()
    if not raw:
        return 0
    try:
        v = int(raw)
        return v if v > 0 else 0
    except ValueError:
        return 0


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
    warehouse_id: int | None = None,
    limit: int | None = None,
) -> List[str]:
    dom = [("company_id", "=", int(company_nak_id))]
    if only_draft:
        dom.append(("state", "=", "draft"))
    dom.append(("tag_ids", "in", [int(must_have_tag_id)]))
    if skip_tag_id is not None:
        dom.append(("tag_ids", "not in", [int(skip_tag_id)]))
    if warehouse_id is not None:
        dom.append(("warehouse_id", "=", int(warehouse_id)))

    opts = {"fields": ["name"], "order": "id asc"}
    if limit:
        opts["limit"] = int(limit)
    rows = models.execute_kw(db, uid, password, "sale.order", "search_read", [dom], opts)
    return [r["name"] for r in rows if r.get("name")]


def _resolve_locations(
    models,
    db: int,
    uid: int,
    password: str,
    company_id: int,
    *,
    src_complete_name: str,
    dst_complete_name: str,
) -> Tuple[int, int]:
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

    return _loc(src_complete_name), _loc(dst_complete_name)


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
    # Preferir “Traslados internos” / “Almacenamiento” si hay varios internal en el almacén.
    for prefer in ("Traslados internos", "Almacenamiento", "Internal Transfers", "Storage"):
        for pt in pts:
            if (pt.get("name") or "").strip() == prefer:
                return pt["id"]
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


def _mark_sale_order_processed(
    models,
    db: int,
    uid: int,
    password: str,
    *,
    order_name: str,
    skip_tag_id: int,
    procesar_tag_id: int | None,
) -> None:
    so_id = models.execute_kw(
        db,
        uid,
        password,
        "sale.order",
        "search",
        [[("name", "=", order_name)]],
        {"limit": 2},
    )
    if not so_id:
        return
    tag_cmds: List[tuple] = [(4, int(skip_tag_id))]
    if procesar_tag_id:
        tag_cmds.append((3, int(procesar_tag_id)))
    models.execute_kw(
        db,
        uid,
        password,
        "sale.order",
        "write",
        [so_id, {"tag_ids": tag_cmds}],
    )
    if procesar_tag_id:
        print(
            f"APPLY: cotización {order_name}: tag procesada id={skip_tag_id}, "
            f"quitado «procesar» id={procesar_tag_id}"
        )
    else:
        print(f"APPLY: cotización {order_name}: solo tag procesada id={skip_tag_id} (sin quitar procesar)")


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
    warehouse_id: int | None = None,
) -> Tuple[Dict[str, Dict[int, float]], List[str]]:
    """
    Lee líneas de venta solo de cotizaciones NAK (solo lectura de sale.order aquí).
    - company_nak_id: compañía Nak (en master_dev suele ser 2; Nakel SA es 1).
    - only_draft: True = solo state 'draft' (cotización); no tocar ventas confirmadas.

    Devuelve (necesidades_por_orden, omitidas) donde omitidas son nombres de orden
    que no cumplen etiquetas requeridas / exclusiones (no se procesan).
    Las etiquetas se actualizan en el bucle principal solo con --apply (ver main).
    """
    per_order: Dict[str, Dict[int, float]] = {}
    skipped: List[str] = []
    for name in order_names:
        sos = models.execute_kw(
            db,
            uid,
            password,
            "sale.order",
            "search_read",
            [[("name", "=", name)]],
            {"fields": ["id", "name", "company_id", "state", "tag_ids", "warehouse_id"], "limit": 5},
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
                f"Solo se aceptan cotizaciones/ventas de company_id={company_nak_id}."
            )
        if only_draft and st != "draft":
            raise RuntimeError(
                f"Orden {name!r} no está en borrador (state={st!r}). "
                f"Solo se procesan cotizaciones (draft) de NAK. Confirmá o cancelá manualmente otra lógica si aplica."
            )

        if require_tag_id is not None:
            tags = so.get("tag_ids") or []
            if int(require_tag_id) not in [int(t) for t in tags]:
                print(f"SKIP: Orden {name!r} no tiene la etiqueta «procesar» (tag_id={require_tag_id}).")
                skipped.append(name)
                continue

        if skip_tag_id is not None:
            tags = so.get("tag_ids") or []
            if int(skip_tag_id) in [int(t) for t in tags]:
                print(f"SKIP: Orden {name!r} ya está marcada como procesada (tag_id={skip_tag_id}).")
                skipped.append(name)
                continue

        if warehouse_id is not None:
            wh = so.get("warehouse_id")
            wh_id = wh[0] if wh else None
            if wh_id != int(warehouse_id):
                wh_label = wh[1] if wh else "—"
                print(
                    f"SKIP: Orden {name!r} almacén={wh_label!r} (id={wh_id}); "
                    f"se exige warehouse_id={warehouse_id}."
                )
                skipped.append(name)
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
    return per_order, skipped


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
    p.add_argument("--warehouse-code", default="CEN", help="Código de almacén (default: CEN). Define picking type y, si no pasás ubicaciones, {code}/Existencias → {code}/Roturas 2.")
    p.add_argument(
        "--src-location",
        default="",
        help="Ubicación origen (complete_name). Default: {warehouse-code}/Existencias.",
    )
    p.add_argument(
        "--dst-location",
        default="",
        help="Ubicación destino (complete_name). Default: {warehouse-code}/Roturas 2.",
    )
    p.add_argument(
        "--filtrar-warehouse-id",
        type=int,
        default=0,
        help="Solo cotizaciones con este warehouse_id (ej. 17 = Belgrano 3). 0 = sin filtro.",
    )
    p.add_argument("--company-nak", type=int, default=2, help="Company_id de la compañía de las cotizaciones a leer (default: 2 = NAK). Para Belgrano 3 en Nakel SA usar 1.")
    p.add_argument(
        "--permitir-venta-confirmada",
        action="store_true",
        help="Inseguro: acepta sale.order con state distinto de draft. Por defecto solo borrador (cotización).",
    )
    p.add_argument("--company-nakel", type=int, default=1, help="Company_id de Nakel SA para el picking interno (default: 1)")
    p.add_argument("--dry-run", action="store_true", help="No crea pickings; solo reporta.")
    p.add_argument("--apply", action="store_true", help="Crea y valida pickings (traslados internos).")
    p.add_argument(
        "--permitir-sin-tag-procesar",
        action="store_true",
        help="Por defecto solo se procesan cotizaciones con etiqueta «procesar». "
        "Con este flag se aceptan también las indicadas por --orden aunque no tengan esa etiqueta.",
    )
    p.add_argument(
        "--no-mark-processed",
        action="store_true",
        help="Con --apply: no agregar la etiqueta «ProcesadaNN» ni quitar «procesar» tras mover stock.",
    )
    p.add_argument(
        "--ensure-tag-procesar",
        action="store_true",
        help="Si no existe la etiqueta crm.tag con el nombre de --tag-procesar-name, la crea en Odoo.",
    )
    p.add_argument(
        "--tag-procesar-color",
        type=int,
        default=6,
        help="Índice de color Odoo (0-11) al crear «procesar» con --ensure-tag-procesar (default 6, tono rosa/salmón).",
    )
    p.add_argument(
        "--tag-procesada-color",
        type=int,
        default=4,
        help="Índice de color al crear «ProcesadaNN» si falta al marcar post-apply (default 4, azul claro).",
    )
    p.add_argument(
        "--skip-tag-name",
        default="ProcesadaNN",
        help="Nombre exacto de crm.tag en sale.order.tag_ids para SALTEAR cotizaciones ya marcadas (default: ProcesadaNN). Usar '' para deshabilitar.",
    )
    p.add_argument(
        "--skip-tag-id",
        type=int,
        default=_default_crm_tag_id_from_env("NAKEL_MOVER_SKIP_TAG_ID"),
        help="ID de crm.tag para SALTEAR cotizaciones ya marcadas (tiene prioridad sobre --skip-tag-name). 0 = deshabilitado. "
        "Default: entorno NAKEL_MOVER_SKIP_TAG_ID si está definido (>0).",
    )
    p.add_argument(
        "--mark-processed",
        action="store_true",
        help="(Compatibilidad) Con --apply ya se marca por defecto; este flag no cambia el comportamiento.",
    )
    p.add_argument(
        "--ensure-tag",
        action="store_true",
        help="Si --skip-tag-name no existe, crear esa etiqueta (ProcesadaNN). Equivale a asegurar etiqueta procesada.",
    )
    p.add_argument(
        "--listar-omitidos",
        action="store_true",
        help="Lista productos de la cotización con pedido>0 pero stock=0 en CEN/Existencias (no se crea movimiento; es esperado).",
    )

    # Flujo por etiquetas (NAK): "procesar" -> ejecutar -> marcar "ProcesadaNN"
    p.add_argument(
        "--auto-desde-tag-procesar",
        action="store_true",
        help="Igual que no pasar órdenes: lista cotizaciones NAK con etiqueta «procesar» (sin «ProcesadaNN»). Opcional si ya es el comportamiento por defecto.",
    )
    p.add_argument(
        "--require-tag-procesar",
        action="store_true",
        help="Obsoleto: la etiqueta «procesar» ya se exige por defecto (salvo --permitir-sin-tag-procesar). Este flag no hace falta.",
    )
    p.add_argument(
        "--tag-procesar-name",
        default="procesar",
        help="Nombre exacto de crm.tag para indicar 'a procesar' (default: procesar). Usar '' para deshabilitar este criterio.",
    )
    p.add_argument(
        "--tag-procesar-id",
        type=int,
        default=_default_crm_tag_id_from_env("NAKEL_MOVER_TAG_PROCESAR_ID"),
        help="ID de crm.tag para indicar 'a procesar' (tiene prioridad sobre --tag-procesar-name). 0 = deshabilitado. "
        "Default: entorno NAKEL_MOVER_TAG_PROCESAR_ID si está definido (>0).",
    )
    p.add_argument(
        "--limit-auto",
        type=int,
        default=0,
        help="Límite de cotizaciones al listar automáticamente por «procesar» (sin órdenes en CLI o con --auto-desde-tag-procesar). 0 = sin límite.",
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

    require_procesar = not bool(args.permitir_sin_tag_procesar)
    mark_processed = bool(args.apply) and not bool(args.no_mark_processed)

    # Resolver tag «procesar» (nombre exacto, p. ej. como en la ficha de venta)
    procesar_tag_id: int | None = None
    if int(args.tag_procesar_id or 0) > 0:
        procesar_tag_id = int(args.tag_procesar_id)
    else:
        tag_name = (args.tag_procesar_name or "").strip()
        if tag_name:
            procesar_tag_id = _resolve_crm_tag_id(models, db, uid, password, name=tag_name)
            if procesar_tag_id is None and args.ensure_tag_procesar:
                procesar_tag_id = _ensure_crm_tag_id(
                    models,
                    db,
                    uid,
                    password,
                    name=tag_name,
                    color=int(args.tag_procesar_color),
                )
                print(
                    f"INFO: creada etiqueta crm.tag {tag_name!r} id={procesar_tag_id} "
                    f"(color={args.tag_procesar_color})."
                )

    # Etiqueta «ya procesada» (para no re-listar en auto y para marcar tras --apply)
    skip_tag_id: int | None = None
    skip_tag_name = (args.skip_tag_name or "").strip()
    if int(args.skip_tag_id or 0) > 0:
        skip_tag_id = int(args.skip_tag_id)
    elif skip_tag_name:
        skip_tag_id = _resolve_crm_tag_id(models, db, uid, password, name=skip_tag_name)
        if skip_tag_id is None:
            print(
                f"WARNING: etiqueta {skip_tag_name!r} no existe; no se filtrará «ya procesada» "
                f"hasta que exista (se puede crear con --ensure-tag al aplicar)."
            )

    if mark_processed:
        if not skip_tag_name and not int(args.skip_tag_id or 0):
            print("WARNING: --apply sin etiqueta procesada (--skip-tag-name vacío): no se marcarán cotizaciones.")
            mark_processed = False
        elif skip_tag_id is None and skip_tag_name:
            skip_tag_id = _ensure_crm_tag_id(
                models,
                db,
                uid,
                password,
                name=skip_tag_name,
                color=int(args.tag_procesada_color),
            )
            print(
                f"INFO: creada etiqueta {skip_tag_name!r} id={skip_tag_id} "
                f"(color={args.tag_procesada_color}) para marcar tras mover."
            )

    if require_procesar and not procesar_tag_id:
        raise RuntimeError(
            "Por defecto solo se procesan cotizaciones con la etiqueta «procesar», pero no existe ese crm.tag. "
            "Creala en Odoo (nombre exacto) o ejecutá con --ensure-tag-procesar / --tag-procesar-id. "
            "Si querés omitir este requisito: --permitir-sin-tag-procesar."
        )

    company_id = int(args.company_nakel)
    wh_code = (args.warehouse_code or "CEN").strip()
    src_name = (args.src_location or "").strip() or f"{wh_code}/Existencias"
    dst_name = (args.dst_location or "").strip() or f"{wh_code}/Roturas 2"
    filter_wh_id = int(args.filtrar_warehouse_id or 0) or None
    src_loc, dst_loc = _resolve_locations(
        models, db, uid, password, company_id, src_complete_name=src_name, dst_complete_name=dst_name
    )
    picking_type_id = _resolve_internal_picking_type(models, db, uid, password, wh_code)

    only_draft = not args.permitir_venta_confirmada

    want_auto = (not order_names) or bool(args.auto_desde_tag_procesar)
    if want_auto:
        if not procesar_tag_id:
            raise RuntimeError(
                "Listado automático por etiqueta requiere resolver «procesar» (--tag-procesar-name / --tag-procesar-id)."
            )
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
            warehouse_id=filter_wh_id,
            limit=lim if lim > 0 else None,
        )
        if not order_names:
            print(
                "No hay cotizaciones NAK en borrador con etiqueta «procesar» "
                "(o todas tienen ya la etiqueta de procesadas / filtro vacío)."
            )
            return 0
        print(
            f"Selección por etiqueta «procesar»: {len(order_names)} orden(es): "
            f"{', '.join(order_names[:20])}{'…' if len(order_names) > 20 else ''}"
        )
    elif not order_names:
        p.error("Pasá órdenes con --orden/--ordenes/--archivo-ordenes, o dejá la lista vacía para usar solo «procesar».")

    require_tag_for_scan = int(procesar_tag_id) if (require_procesar and procesar_tag_id) else None
    per_order, skipped_orders = _needs_by_orders(
        models,
        db,
        uid,
        password,
        order_names,
        company_nak_id=int(args.company_nak),
        only_draft=only_draft,
        skip_tag_id=skip_tag_id,
        require_tag_id=require_tag_for_scan,
        warehouse_id=filter_wh_id,
    )
    skipped_set = set(skipped_orders)
    order_names = [o for o in order_names if o not in skipped_set]
    if skipped_set:
        print(
            f"Omitidas {len(skipped_set)} orden(es) por etiquetas / criterios: "
            f"{', '.join(sorted(skipped_set)[:30])}{'…' if len(skipped_set) > 30 else ''}"
        )
    if not order_names:
        print("No quedan órdenes para procesar tras filtros.")
        return 0

    wh_note = f"warehouse_id={filter_wh_id}" if filter_wh_id else "warehouse_id=— (sin filtro)"
    print(
        f"Lectura ventas: company_id={args.company_nak} | solo_draft={only_draft} | {wh_note} "
        f"(sale.order solo lectura salvo etiquetas con --apply)"
    )
    print(
        f"Stock/picking: company_id={company_id} | {src_name!r} (id={src_loc}) → {dst_name!r} (id={dst_loc}) "
        f"| almacén={wh_code!r} picking_type_id={picking_type_id}"
    )
    print("Modo:", "DRY-RUN" if args.dry_run else "APPLY")
    proc_label = f"id={procesar_tag_id}" if procesar_tag_id else "—"
    skip_label = f"id={skip_tag_id}" if skip_tag_id else (skip_tag_name or "—")
    if args.dry_run:
        mark_note = "no aplica en dry-run (etiquetas solo con --apply)"
    elif mark_processed:
        mark_note = "sí"
    else:
        mark_note = "no (--no-mark-processed o --skip-tag-name vacío)"
    print(
        f"Etiquetas NAK: exigir «procesar» ({proc_label}): "
        f"{'sí' if require_procesar else 'no (--permitir-sin-tag-procesar)'} | "
        f"con --apply marcar «{skip_tag_name or skip_label}» y quitar procesar: {mark_note}"
    )

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
            "Productos con pedido>0 pero stock=0 en origen (no se mueve nada; dado por hecho):",
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
            if mark_processed and skip_tag_id:
                _mark_sale_order_processed(
                    models,
                    db,
                    uid,
                    password,
                    order_name=oname,
                    skip_tag_id=int(skip_tag_id),
                    procesar_tag_id=procesar_tag_id,
                )
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

        if mark_processed and skip_tag_id:
            _mark_sale_order_processed(
                models,
                db,
                uid,
                password,
                order_name=oname,
                skip_tag_id=int(skip_tag_id),
                procesar_tag_id=procesar_tag_id,
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
