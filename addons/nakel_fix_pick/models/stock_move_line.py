# -*- coding: utf-8 -*-

from odoo import api, models


def _nakel_float_from_vals(vals: dict, key: str):
    if key not in vals:
        return None
    try:
        return float(vals.get(key) or 0.0)
    except Exception:
        return 0.0


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    @api.model
    def _nakel_fix_pick_enabled(self):
        # Default OFF: only active if explicitly enabled in System Parameters.
        val = self.env["ir.config_parameter"].sudo().get_param("nakel_fix_pick.enable", "0")
        return str(val).strip().lower() in ("1", "true", "yes", "y", "on")

    def write(self, vals):
        """
        If enabled, keep `picked` (and often `qty_done`) consistent when Barcode writes quantities.

        Rationale (observed in Nakel):
        - Barcode puede mandar `picked: False` junto con cantidad > 0; la guarda antigua
          (`if "picked" not in vals`) saltaba y dejaba datos incoherentes.
        - A veces solo llega `quantity`; si queda `qty_done` en 0, la UI puede mostrar 0 / … tras refresh.

        Nota: `quantity` es la reserva operativa; `qty_done` es lo hecho. Solo copiamos
        `quantity` -> `qty_done` cuando hay cantidad > 0 y `qty_done` no viene positivo en `vals`.
        """
        if not self._nakel_fix_pick_enabled():
            return super().write(vals)

        keys = ("qty_done", "quantity", "picked")
        if not any(k in vals for k in keys):
            return super().write(vals)

        vals = dict(vals)
        qd = _nakel_float_from_vals(vals, "qty_done") if "qty_done" in vals else None
        qt = _nakel_float_from_vals(vals, "quantity") if "quantity" in vals else None

        # Cantidad "hecha" implícita: el máximo positivo entre lo que venga en qty_done y quantity.
        # Cubre el caso Barcode: qty_done=0 y quantity=5 en el mismo write.
        positives = [v for v in (qd, qt) if v is not None and v > 0.0]
        max_positive = max(positives) if positives else None

        if max_positive is not None and max_positive > 0.0:
            vals["picked"] = True
            if qt is not None and qt > 0.0 and (qd is None or qd <= 0.0):
                vals["qty_done"] = qt
        elif qd is not None and qd <= 0.0 and (qt is None or qt <= 0.0):
            if "picked" not in vals:
                vals["picked"] = False
        elif qt is not None and qt <= 0.0 and qd is None:
            if "picked" not in vals:
                vals["picked"] = False

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
