# -*- coding: utf-8 -*-

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_is_zero


class SaleOrder(models.Model):
    _inherit = "sale.order"

    nakel_wave_batch_id = fields.Many2one(
        "stock.picking.batch",
        string="Ola/Wave (Nakel)",
        index=True,
        copy=False,
        help="Orden vinculada a una ola: se rellena desde pickings (PICK) de esa ola.",
    )

    def action_nakel_open_wave(self):
        """Abrir la ola vinculada a esta OV (si existe)."""
        self.ensure_one()
        if not self.nakel_wave_batch_id:
            return {"type": "ir.actions.act_window_close"}
        return {
            "name": "Ola/Wave (Nakel)",
            "type": "ir.actions.act_window",
            "res_model": "stock.picking.batch",
            "view_mode": "form",
            "res_id": self.nakel_wave_batch_id.id,
            "target": "current",
            "context": {"create": False},
        }

    def action_nakel_open_out_pickings(self):
        """Abrir OUT (entregas) de esta OV."""
        self.ensure_one()
        dom = [
            ("sale_id", "=", self.id),
            "|",
            ("picking_type_id.sequence_code", "=", "OUT"),
            ("name", "ilike", "CEN/OUT/%"),
        ]
        return {
            "name": "Entregas OUT (OV)",
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": dom,
            "context": {"create": False},
        }
