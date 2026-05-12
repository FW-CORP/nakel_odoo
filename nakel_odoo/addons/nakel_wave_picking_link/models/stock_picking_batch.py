# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.osv import expression


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    # Inversos para recomputar salud de ola cuando cambian OUT/OV vía `nakel_wave_batch_id`
    # (no están en `picking_ids` del batch estándar).
    nakel_wave_all_pick_ids = fields.One2many(
        comodel_name="stock.picking",
        inverse_name="nakel_wave_batch_id",
        string="Albaranes vinculados (Nakel)",
        help="PICKs y OUT con nakel_wave_batch_id = esta ola.",
    )
    nakel_wave_sale_ids = fields.One2many(
        comodel_name="sale.order",
        inverse_name="nakel_wave_batch_id",
        string="Órdenes vinculadas (Nakel)",
    )

    nakel_sale_order_count = fields.Integer(
        string="OV en ola",
        compute="_compute_nakel_ola_counts",
    )
    nakel_out_picking_count = fields.Integer(
        string="OUT en ola",
        compute="_compute_nakel_ola_counts",
    )

    nakel_out_pending_count = fields.Integer(
        string="OUT pendientes (ola)",
        compute="_compute_nakel_wave_health",
        help="Entregas OUT con nakel_wave_batch_id = esta ola y estado distinto de hecho/cancelado.",
    )
    nakel_out_open_line_count = fields.Integer(
        string="Líneas operación sin cerrar (OUT ola)",
        compute="_compute_nakel_wave_health",
        help="Líneas de OUT pendientes con quantity > 0 y (qty_done = 0 o picked falso).",
    )
    nakel_so_to_invoice_count = fields.Integer(
        string="OV sin facturar (ola)",
        compute="_compute_nakel_wave_health",
        help="Órdenes con nakel_wave_batch_id = esta ola e invoice_status = no.",
    )
    nakel_wave_logistics_alert = fields.Boolean(
        string="Alerta logística ola",
        compute="_compute_nakel_wave_health",
        help="Verdadero si hay OUT pendientes o líneas de OUT sin cantidad hecha coherente.",
    )
    nakel_wave_issue_caption = fields.Char(
        string="Resumen alerta entregas",
        compute="_compute_nakel_wave_health",
    )

    def _nakel_wave_sale_order_ids(self):
        """OV ligadas a la ola: `nakel_wave_batch_id` en la OV **o** `sale_id` en pickings del batch.

        No basta con `picking_ids.mapped('sale_id')`: si se sacan pickings del batch pero las OV
        siguen con `nakel_wave_batch_id` (recompute no limpia), o hay mezcla OUT/PICK, el contador
        «OV (ola)» y el smartbutton quedaban en **1** aunque la ola involucre más OV.
        """
        self.ensure_one()
        from_pickings = self.picking_ids.mapped("sale_id").filtered(lambda s: s)
        return (self.nakel_wave_sale_ids | from_pickings)

    def _nakel_out_picking_types_for_batch(self):
        self.ensure_one()
        Ptype = self.env["stock.picking.type"]
        wh = self.picking_type_id.warehouse_id
        ptypes = Ptype.search(
            [("sequence_code", "=", "OUT"), ("warehouse_id", "=", wh.id)]
            if wh
            else [("sequence_code", "=", "OUT")]
        )
        if wh and not ptypes:
            ptypes = Ptype.search([("sequence_code", "=", "OUT")])
        return ptypes

    @api.depends(
        "picking_ids",
        "picking_ids.sale_id",
        "nakel_wave_sale_ids",
        "picking_type_id",
        "picking_type_id.warehouse_id",
    )
    def _compute_nakel_ola_counts(self):
        Picking = self.env["stock.picking"]
        for batch in self:
            # `sale_id` en stock.picking proviene de `sale_stock`.
            # En entornos donde no exista (o durante upgrades parciales), evitamos depender de ese campo.
            if "sale_id" in Picking._fields:
                sales = batch._nakel_wave_sale_order_ids()
                so_ids = sales.ids
            else:
                so_ids = batch.nakel_wave_sale_ids.ids
            batch.nakel_sale_order_count = len(so_ids)
            ptypes = batch._nakel_out_picking_types_for_batch()
            if so_ids and ptypes:
                batch.nakel_out_picking_count = Picking.search_count(
                    [
                        ("picking_type_id", "in", ptypes.ids),
                        ("sale_id", "in", so_ids),
                    ]
                )
            else:
                batch.nakel_out_picking_count = 0

    def action_nakel_open_sale_orders(self):
        """Todas las OV ligadas a la ola (campo en OV y/o `sale_id` en pickings del batch)."""
        self.ensure_one()
        so_ids = self._nakel_wave_sale_order_ids().ids
        return {
            "name": "Órdenes de venta (ola)",
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("id", "in", so_ids)] if so_ids else [(0, "=", 1)],
            "context": {
                "create": False,
            },
        }

    def action_nakel_open_out_pickings(self):
        """Entregas OUT a validar: mismas OV que componen la ola (unión OV enlace + pickings)."""
        self.ensure_one()
        so_ids = self._nakel_wave_sale_order_ids().ids
        ptypes = self._nakel_out_picking_types_for_batch()
        dom = [
            ("picking_type_id", "in", ptypes.ids),
            ("sale_id", "in", so_ids),
        ] if (so_ids and ptypes) else [(0, "=", 1)]
        return {
            "name": "Entregas OUT (ola)",
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": dom,
            "context": {
                "create": False,
            },
        }

    @api.depends(
        "nakel_wave_all_pick_ids.state",
        "nakel_wave_all_pick_ids.picking_type_id",
        "nakel_wave_all_pick_ids.move_line_ids.qty_done",
        "nakel_wave_all_pick_ids.move_line_ids.quantity",
        "nakel_wave_all_pick_ids.move_line_ids.picked",
        "nakel_wave_sale_ids.invoice_status",
    )
    def _compute_nakel_wave_health(self):
        SaleOrder = self.env["sale.order"]
        Picking = self.env["stock.picking"]
        for batch in self:
            if not batch.ids:
                batch.nakel_out_pending_count = 0
                batch.nakel_out_open_line_count = 0
                batch.nakel_so_to_invoice_count = 0
                batch.nakel_wave_logistics_alert = False
                batch.nakel_wave_issue_caption = ""
                continue
            ptypes = batch._nakel_out_picking_types_for_batch()
            pending_dom = [
                ("nakel_wave_batch_id", "=", batch.id),
                ("state", "not in", ("done", "cancel")),
            ]
            if ptypes:
                pending_dom = expression.AND(
                    [pending_dom, [("picking_type_id", "in", ptypes.ids)]]
                )
            else:
                pending_dom = expression.AND(
                    [
                        pending_dom,
                        [
                            "|",
                            ("picking_type_id.sequence_code", "=", "OUT"),
                            ("name", "ilike", "CEN/OUT/%"),
                        ],
                    ]
                )
            pending_outs = Picking.search(pending_dom)
            open_line_count = 0
            for picking in pending_outs:
                for line in picking.move_line_ids:
                    qty = float(line.quantity or 0.0)
                    if qty <= 0.0:
                        continue
                    done = float(line.qty_done or 0.0)
                    picked = bool(getattr(line, "picked", True))
                    if done < qty or not picked:
                        open_line_count += 1
            batch.nakel_out_pending_count = len(pending_outs)
            batch.nakel_out_open_line_count = open_line_count
            batch.nakel_so_to_invoice_count = SaleOrder.search_count(
                [
                    ("nakel_wave_batch_id", "=", batch.id),
                    ("invoice_status", "=", "no"),
                ]
            )
            batch.nakel_wave_logistics_alert = bool(
                batch.nakel_out_pending_count or batch.nakel_out_open_line_count
            )
            if batch.nakel_wave_logistics_alert:
                batch.nakel_wave_issue_caption = "%s OUT · %s líneas" % (
                    batch.nakel_out_pending_count,
                    batch.nakel_out_open_line_count,
                )
            else:
                batch.nakel_wave_issue_caption = ""

    def action_nakel_open_out_pending_wave(self):
        """OUT vinculados a esta ola (`nakel_wave_batch_id`) aún no finalizados."""
        self.ensure_one()
        ptypes = self._nakel_out_picking_types_for_batch()
        dom = [
            ("nakel_wave_batch_id", "=", self.id),
            ("state", "not in", ("done", "cancel")),
        ]
        if ptypes:
            dom = expression.AND([dom, [("picking_type_id", "in", ptypes.ids)]])
        else:
            dom = expression.AND(
                [
                    dom,
                    [
                        "|",
                        ("picking_type_id.sequence_code", "=", "OUT"),
                        ("name", "ilike", "CEN/OUT/%"),
                    ],
                ]
            )
        return {
            "name": "OUT pendientes (ola Nakel)",
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": dom,
            "context": {"create": False},
        }

    def action_nakel_open_so_to_invoice_wave(self):
        """OV con `nakel_wave_batch_id` = esta ola y sin facturar (`invoice_status` = no)."""
        self.ensure_one()
        return {
            "name": "OV sin facturar (ola Nakel)",
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [
                ("nakel_wave_batch_id", "=", self.id),
                ("invoice_status", "=", "no"),
            ],
            "context": {"create": False},
        }

    @api.model_create_multi
    def create(self, vals_list):
        batches = super().create(vals_list)
        batches._nakel_recompute_wave_links()
        return batches

    def write(self, vals):
        res = super().write(vals)
        if "picking_ids" in vals:
            self._nakel_recompute_wave_links()
        return res

    def _nakel_out_domain_for_wave_pickings(self, wave_pickings):
        """Dominio para OUT hermanos de los PICK (u otros) ya metidos en la ola."""
        origins = set()
        gids = set()
        sids = set()
        for p in wave_pickings:
            o = (p.origin or "").strip()
            if o:
                origins.add(o)
            if p.group_id:
                gids.add(p.group_id.id)
            if p.sale_id:
                sids.add(p.sale_id.id)
        parts = []
        if gids:
            parts.append([("group_id", "in", list(gids))])
        if sids:
            parts.append([("sale_id", "in", list(sids))])
        if origins:
            parts.append([("origin", "in", list(origins))])
        if not parts:
            return [(0, "=", 1)]
        or_part = expression.OR(parts)
        out_type = [
            "|",
            ("picking_type_id.sequence_code", "=", "OUT"),
            ("name", "ilike", "CEN/OUT/%"),
        ]
        return expression.AND([out_type, or_part])

    def _nakel_recompute_wave_links(self):
        """PICK en ola: mirror batch_id; OUT hermanos: misma ola; OV: mismo enlace a la ola."""
        Picking = self.env["stock.picking"]
        for batch in self:
            wave_pickings = batch.picking_ids
            if wave_pickings:
                wave_pickings._nakel_sync_wave_batch()
            sales = wave_pickings.mapped("sale_id").filtered(lambda s: s)
            if sales:
                sales.write({"nakel_wave_batch_id": batch.id})
            dom = batch._nakel_out_domain_for_wave_pickings(wave_pickings)
            if dom == [(0, "=", 1)]:
                continue
            outs = Picking.search(dom)
            if outs:
                outs.write({"nakel_wave_batch_id": batch.id})
