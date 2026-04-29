# -*- coding: utf-8 -*-

from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    nakel_wave_batch_id = fields.Many2one(
        "stock.picking.batch",
        string="Ola/Wave (Nakel)",
        index=True,
        copy=False,
        help="Orden vinculada a una ola: se rellena desde pickings (PICK) de esa ola.",
    )
