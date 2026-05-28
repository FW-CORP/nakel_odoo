# Pegar TODO este archivo en Odoo: Acción planificada → Ejecutar código Python
# NO es un script ejecutable fuera de Odoo (no tiene import; usa env, log, datetime de Odoo).
#
# Antes de pegar en Odoo:
#   1. Borrar TODO el texto default del cuadro de código en Odoo.
#   2. Copiar desde ESTE archivo (Ctrl+A aquí), NO desde el README Markdown.
#   3. Verificar que la 1ª línea ejecutable sea exactamente: COMPANY_STOCK = 1
#      (si queda OMPANY_STOCK = 1 → se cortó la C al pegar → NameError)
#   4. Verificar que la última línea sea: level="info",)  del log final
#   5. Para probar un día cualquiera: RUN_WEEKDAYS = (0, 1, 2, 3, 4, 5, 6)
#
# Sandbox Odoo: sin import, sin lambda, sin def internas, sin record.campo = x (usar write)

COMPANY_STOCK = 1
TAG_PROCESAR_NAME = "procesar"
TAG_PROCESADA_NAME = "ProcesadaNN"
ORIGIN_SUFFIX = "mover demanda"
RUN_WEEKDAYS = (6, 2, 4)

PROFILES = [
    {"label": "CEN/NAK", "order_company_id": 2, "warehouse_id": 0, "src_name": "CEN/Existencias", "dst_name": "CEN/Roturas 2", "wh_code": "CEN"},
    {"label": "B3", "order_company_id": 1, "warehouse_id": 17, "src_name": "B3/Existencias", "dst_name": "B3/Roturas 2", "wh_code": "B3"},
]

if datetime.date.today().weekday() not in RUN_WEEKDAYS:
    log("CRON mover Roturas2: omitido (hoy no es dom/mie/vie; weekday=%s)" % datetime.date.today().weekday(), level="info")
else:
    Tag = env["crm.tag"].sudo()
    SO = env["sale.order"].sudo()
    Location = env["stock.location"].sudo()
    Warehouse = env["stock.warehouse"].sudo()
    PickingType = env["stock.picking.type"].sudo()
    Picking = env["stock.picking"].sudo()
    MoveLine = env["stock.move.line"].sudo()
    Product = env["product.product"].sudo()

    tag_procesar = Tag.search([("name", "=", TAG_PROCESAR_NAME)], limit=1)
    tag_procesada = Tag.search([("name", "=", TAG_PROCESADA_NAME)], limit=1)
    if not tag_procesar:
        log("CRON mover Roturas2: falta crm.tag %r" % TAG_PROCESAR_NAME, level="warning")
    elif not tag_procesada:
        log("CRON mover Roturas2: falta crm.tag %r" % TAG_PROCESADA_NAME, level="warning")
    else:
        total_orders = 0
        total_pickings = 0

        for prof in PROFILES:
            dom = [
                ("company_id", "=", prof["order_company_id"]),
                ("state", "=", "draft"),
                ("tag_ids", "in", tag_procesar.ids),
                ("tag_ids", "not in", tag_procesada.ids),
            ]
            if prof["warehouse_id"]:
                dom.append(("warehouse_id", "=", prof["warehouse_id"]))
            orders = SO.search(dom, order="id asc")
            log("CRON mover Roturas2 [%s]: %s cotizacion(es)" % (prof["label"], len(orders)), level="info")

            src = Location.search([("complete_name", "=", prof["src_name"]), ("company_id", "=", COMPANY_STOCK)], limit=1)
            dst = Location.search([("complete_name", "=", prof["dst_name"]), ("company_id", "=", COMPANY_STOCK)], limit=1)
            pt = False
            wh = Warehouse.search([("code", "=", prof["wh_code"])], limit=1)
            if wh:
                pts = PickingType.search([("warehouse_id", "=", wh.id), ("code", "=", "internal")])
                for prefer in ("Traslados internos", "Almacenamiento", "Internal Transfers", "Storage"):
                    for pt_candidate in pts:
                        if (pt_candidate.name or "").strip() == prefer:
                            pt = pt_candidate
                if not pt and pts:
                    pt = pts[0]

            if not src or not dst or not pt:
                log("CRON mover Roturas2 [%s]: ubicaciones o picking type no encontrados" % prof["label"], level="warning")
            else:
                for so in orders:
                    total_orders += 1
                    need = {}
                    for line in so.order_line:
                        if line.display_type:
                            pass
                        else:
                            pid = line.product_id.id
                            need[pid] = need.get(pid, 0.0) + line.product_uom_qty

                    moves_vals = []
                    for pid in need:
                        q_need = need[pid]
                        if q_need > 0:
                            product = Product.browse(pid)
                            moves_vals.append((0, 0, {
                                "name": so.name,
                                "product_id": product.id,
                                "product_uom": product.uom_id.id,
                                "product_uom_qty": q_need,
                                "location_id": src.id,
                                "location_dest_id": dst.id,
                                "company_id": COMPANY_STOCK,
                            }))

                    if not moves_vals:
                        so.write({"tag_ids": [(4, tag_procesada.id), (3, tag_procesar.id)]})
                        log("CRON mover Roturas2 [%s]: %s sin lineas; marcada procesada" % (prof["label"], so.name), level="info")
                    else:
                        origin = "%s -> Roturas2 (%s)" % (so.name, ORIGIN_SUFFIX)
                        picking = Picking.create({
                            "picking_type_id": pt.id,
                            "location_id": src.id,
                            "location_dest_id": dst.id,
                            "origin": origin,
                            "company_id": COMPANY_STOCK,
                            "move_ids": moves_vals,
                        })
                        picking.action_confirm()
                        try:
                            picking.action_assign()
                        except Exception:
                            pass

                        for move in picking.move_ids:
                            qty_need = move.product_uom_qty
                            if qty_need > 0:
                                if move.move_line_ids:
                                    done = sum(move.move_line_ids.mapped("qty_done"))
                                    if done + 0.000001 < qty_need and len(move.move_line_ids) == 1:
                                        line = move.move_line_ids[0]
                                        if not line.lot_id and not line.lot_name:
                                            line.write({"qty_done": qty_need})
                                else:
                                    MoveLine.create({
                                        "move_id": move.id,
                                        "picking_id": picking.id,
                                        "product_id": move.product_id.id,
                                        "location_id": move.location_id.id,
                                        "location_dest_id": move.location_dest_id.id,
                                        "product_uom_id": move.product_uom.id,
                                        "qty_done": qty_need,
                                    })

                        res = picking.with_context(skip_backorder=True).button_validate()
                        if isinstance(res, dict) and res.get("res_model"):
                            log("CRON mover Roturas2 [%s]: wizard en %s: %s" % (prof["label"], so.name, res.get("res_model")), level="warning")
                        else:
                            extras = Picking.search([
                                ("origin", "=", origin),
                                ("company_id", "=", COMPANY_STOCK),
                                ("state", "not in", ("done", "cancel")),
                            ])
                            for p in extras:
                                if p.state == "draft":
                                    p.action_confirm()
                                try:
                                    p.action_assign()
                                except Exception:
                                    pass
                                for move in p.move_ids:
                                    qty_need = move.product_uom_qty
                                    if qty_need > 0 and not move.move_line_ids:
                                        MoveLine.create({
                                            "move_id": move.id,
                                            "picking_id": p.id,
                                            "product_id": move.product_id.id,
                                            "location_id": move.location_id.id,
                                            "location_dest_id": move.location_dest_id.id,
                                            "product_uom_id": move.product_uom.id,
                                            "qty_done": qty_need,
                                        })
                                res2 = p.with_context(skip_backorder=True).button_validate()
                                if isinstance(res2, dict) and res2.get("res_model"):
                                    log("CRON mover Roturas2: wizard extra %s en %s" % (res2.get("res_model"), p.name), level="warning")

                            so.write({"tag_ids": [(4, tag_procesada.id), (3, tag_procesar.id)]})
                            total_pickings += 1
                            log("CRON mover Roturas2 [%s]: OK %s picking=%s" % (prof["label"], so.name, picking.name), level="info")

        log("CRON mover Roturas2: fin ordenes=%s pickings=%s" % (total_orders, total_pickings), level="info")
