# -*- coding: utf-8 -*-

from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    nakel_shipping_zone_tag_ids = fields.Many2many(
        comodel_name="res.partner.category",
        related="partner_shipping_id.category_id",
        string="Etiquetas zona (entrega)",
        readonly=True,
    )

    def action_nakel_open_wave_planner(self):
        """Abre el planificador con las OV seleccionadas pre-cargadas (si aplica)."""
        return {
            "name": "Armar ola por zona",
            "type": "ir.actions.act_window",
            "res_model": "nakel.wave.planner.wizard",
            "view_mode": "form",
            "target": "new",
            "context": dict(self.env.context),
        }
