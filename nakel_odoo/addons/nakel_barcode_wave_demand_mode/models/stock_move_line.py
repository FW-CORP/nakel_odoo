# -*- coding: utf-8 -*-

from odoo import api, models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def _nakel_demand_mode_set_quantity_picked(self, quantity, picked):
        """
        Odoo 18: stock.move.line.write({'quantity': X}) re-reserva quants y capa X
        al stock disponible. En modo demanda OV necesitamos quantity = demanda aunque
        no haya reserva real (puente inventario desfasado).
        """
        self.ensure_one()
        quantity_product_uom = self.product_uom_id._compute_quantity(
            quantity,
            self.product_id.uom_id,
            rounding_method="HALF-UP",
        )
        self.env.cr.execute(
            """
            UPDATE stock_move_line
               SET quantity = %s,
                   picked = %s,
                   quantity_product_uom = %s
             WHERE id = %s
            """,
            (quantity, picked, quantity_product_uom, self.id),
        )
        self.invalidate_recordset(["quantity", "quantity_product_uom", "picked"])

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("nakel_demand_mode_bump"):
            return super().create(vals_list)

        records = self.env["stock.move.line"]
        for vals in vals_list:
            vals = dict(vals)
            qty = vals.pop("quantity", 0.0)
            picked = vals.pop("picked", False)
            vals.pop("qty_done", None)
            line = super(StockMoveLine, self).create(vals)
            line._nakel_demand_mode_set_quantity_picked(qty, picked)
            records |= line
        return records

    def write(self, vals):
        if not self.env.context.get("nakel_demand_mode_bump") or not (
            "quantity" in vals or "picked" in vals
        ):
            return super().write(vals)

        remaining = dict(vals)
        qty = remaining.pop("quantity", None)
        picked = remaining.pop("picked", None)
        remaining.pop("qty_done", None)
        if remaining:
            super(StockMoveLine, self).write(remaining)
        for line in self:
            new_qty = qty if qty is not None else line.quantity
            new_picked = picked if picked is not None else line.picked
            line._nakel_demand_mode_set_quantity_picked(new_qty, new_picked)
        return True
