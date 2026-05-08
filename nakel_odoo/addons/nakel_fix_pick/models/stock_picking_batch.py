# -*- coding: utf-8 -*-

from odoo import api, models


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    def action_nakel_sync_picked_from_quantity(self):
        """
        Operational SYNC for Waves (Batch Transfers):
        Mark move lines as `picked=True` when operators already recorded quantity > 0.

        This fixes Barcode progress (green ticks) when `picked` gets desynchronized.
        It does NOT change quantities, only the boolean flag.
        """
        self.ensure_one()

        if not self.picking_ids:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "SYNC ola (picked)",
                    "message": "La ola no tiene transferencias asociadas. No se sincronizó nada.",
                    "type": "warning",
                    "sticky": False,
                },
            }

        lines = self.env["stock.move.line"].search(
            [
                ("picking_id.batch_id", "=", self.id),
                ("quantity", ">", 0),
                ("picked", "=", False),
            ]
        )
        updated = len(lines)
        if updated:
            lines.write({"picked": True})

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "SYNC ola (picked)",
                "message": f"Sincronizadas {updated} líneas (picked=True donde quantity>0).",
                "type": "success" if updated else "info",
                "sticky": False,
            },
        }

