# -*- coding: utf-8 -*-

from odoo import api, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def action_sync_qty_done_from_quantity(self):
        """
        Copy move line `quantity` (reserved/plan) into `qty_done` (done) when `qty_done` is still 0.

        This is intentionally conservative:
        - Only touches stock.move.line in current picking
        - Only when qty_done == 0 and quantity > 0
        - Does not modify lines already marked done
        """
        self.ensure_one()

        # Only makes sense for transfers that can be validated.
        if self.state in ("done", "cancel"):
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "SYNC qty_done",
                    "message": "El traslado ya está finalizado/cancelado. No se sincronizó nada.",
                    "type": "warning",
                    "sticky": False,
                },
            }

        lines = self.move_line_ids.filtered(lambda l: (l.qty_done or 0.0) == 0.0 and (l.quantity or 0.0) > 0.0)
        updated = 0
        for ml in lines:
            ml.write({"qty_done": ml.quantity})
            updated += 1

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "SYNC qty_done",
                "message": f"Sincronizadas {updated} líneas (quantity → qty_done).",
                "type": "success" if updated else "info",
                "sticky": False,
            },
        }

