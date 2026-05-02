# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.osv import expression


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    nakel_sale_order_count = fields.Integer(
        string="OV en ola",
        compute="_compute_nakel_ola_counts",
    )
    nakel_out_picking_count = fields.Integer(
        string="OUT en ola",
        compute="_compute_nakel_ola_counts",
    )

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

    @api.depends("picking_ids", "picking_type_id", "picking_type_id.warehouse_id")
    def _compute_nakel_ola_counts(self):
        Picking = self.env["stock.picking"]
        for batch in self:
            # `sale_id` en stock.picking proviene de `sale_stock`.
            # En entornos donde no exista (o durante upgrades parciales), evitamos depender de ese campo.
            if "sale_id" in Picking._fields:
                sales = batch.picking_ids.mapped("sale_id").filtered(lambda s: s)
                so_ids = sales.ids
            else:
                so_ids = []
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
        """Solo OV cuyo PICK está en esta ola (mismo criterio que el armado de la ola)."""
        self.ensure_one()
        so_ids = list(
            {sid for sid in self.picking_ids.mapped("sale_id").ids if sid}
        )
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
        """Entregas OUT a validar: mismas OV que componen la ola (sale_id vía PICKs de la ola)."""
        self.ensure_one()
        so_ids = list(
            {sid for sid in self.picking_ids.mapped("sale_id").ids if sid}
        )
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
