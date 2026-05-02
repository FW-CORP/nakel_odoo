# -*- coding: utf-8 -*-

from odoo import api, models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    @api.model
    def _nakel_fix_pick_enabled(self):
        # Default OFF: only active if explicitly enabled in System Parameters.
        val = self.env["ir.config_parameter"].sudo().get_param("nakel_fix_pick.enable", "0")
        return str(val).strip().lower() in ("1", "true", "yes", "y", "on")

    def write(self, vals):
        """
        If enabled, keep `picked` consistent when done quantity is set.

        Rationale (observed in Nakel):
        - In Barcode, users effectively "do" lines by setting done quantities.
        - If `picked` is left False while done quantities are set, Barcode can display 0/… and block operation.

        Important: `quantity` on stock.move.line is NOT the done quantity; it's typically the reserved/initial
        quantity for the operation. We therefore prefer `qty_done` when available.
        """
        enabled = self._nakel_fix_pick_enabled()
        if enabled and "picked" not in vals:
            # Prefer real done qty when it's being written.
            if "qty_done" in vals:
                try:
                    done = float(vals.get("qty_done") or 0.0)
                except Exception:
                    done = 0.0
                vals = dict(vals)
                vals["picked"] = done > 0
            # Fallback for installations/custom flows that write `quantity` as done quantity.
            elif "quantity" in vals:
                try:
                    qty = float(vals.get("quantity") or 0.0)
                except Exception:
                    qty = 0.0
                vals = dict(vals)
                vals["picked"] = qty > 0
        return super().write(vals)

    @api.model
    def nakel_backfill_picked_for_wave(self, batch_id, limit=None):
        """
        Backfill helper (manual use only): set picked=True where qty_done>0 for a given wave.

        - batch_id: stock.picking.batch id (Wave/WAVE/xxxxx)
        - limit: optional int to process in chunks
        """
        if not self._nakel_fix_pick_enabled():
            return {
                "ok": False,
                "reason": "nakel_fix_pick.enable is disabled",
                "updated": 0,
            }

        domain = [
            ("picking_id.batch_id", "=", batch_id),
            ("qty_done", ">", 0),
            ("picked", "=", False),
        ]
        lines = self.search(domain, limit=limit)
        lines.write({"picked": True})
        return {
            "ok": True,
            "batch_id": batch_id,
            "updated": len(lines),
            "limited": bool(limit),
        }

