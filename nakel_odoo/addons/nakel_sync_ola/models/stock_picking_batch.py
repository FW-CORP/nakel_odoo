# -*- coding: utf-8 -*-

from odoo import models


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    def _nakel_sync_ola_pickings(self):
        """PICK (y traslados no-OUT) pendientes ligados a esta ola.

        Los **OUT** (`sequence_code` = OUT / `CEN/OUT/…`) se **excluyen**: comparten
        `nakel_wave_batch_id` con la ola pero no son el mismo paso operativo que el
        recolectar; forzar `quantity → qty_done` y `picked` ahí suele dejar entregas
        incoherentes con PICK/PACK o con la validación en Barcode.
        """
        self.ensure_one()
        pickings = self.env["stock.picking"].search(
            [
                "|",
                ("batch_id", "=", self.id),
                ("nakel_wave_batch_id", "=", self.id),
                ("state", "not in", ("done", "cancel")),
            ]
        )
        return pickings.filtered(lambda p: not p._nakel_is_out_picking(p))

    def action_nakel_sync_ola_full(self):
        """
        Supervisor: para la ola actual,
        1) en cada picking vinculado **que no sea OUT**, copia quantity -> qty_done donde qty_done sigue en 0
           (misma lógica que nakel_stock_sync_qty_done);
        2) marca picked=True en líneas con quantity>0 y picked=False.

        No valida traslados. No reemplaza el botón SYNC de nakel_fix_pick (solo picked + batch_id).
        """
        self.ensure_one()
        pickings = self._nakel_sync_ola_pickings()
        if not pickings:
            return self._nakel_sync_ola_notification(
                "SYNC Ola+OUT",
                "No hay transferencias pendientes vinculadas a esta ola (batch_id o nakel_wave_batch_id).",
                "warning",
            )

        qty_done_updates = 0
        for picking in pickings:
            pending = picking.move_line_ids.filtered(
                lambda ml: (ml.qty_done or 0.0) == 0.0 and (ml.quantity or 0.0) > 0.0
            )
            if not pending:
                continue
            n_pending = len(pending)
            # Reutiliza implementación probada de nakel_stock_sync_qty_done
            picking.action_sync_qty_done_from_quantity()
            still = picking.move_line_ids.filtered(
                lambda ml: (ml.qty_done or 0.0) == 0.0 and (ml.quantity or 0.0) > 0.0
            )
            qty_done_updates += n_pending - len(still)

        line_domain = [
            ("picking_id", "in", pickings.ids),
            ("quantity", ">", 0),
            ("picked", "=", False),
        ]
        to_pick = self.env["stock.move.line"].search(line_domain)
        picked_n = len(to_pick)
        if to_pick:
            to_pick.write({"picked": True})

        msg = (
            f"Transferencias tocadas: {len(pickings)}. "
            f"Líneas ajustadas quantity→qty_done: {qty_done_updates}. "
            f"Líneas marcadas picked: {picked_n}."
        )
        return self._nakel_sync_ola_notification(
            "SYNC Ola+OUT",
            msg,
            "success" if (qty_done_updates or picked_n) else "info",
        )

    def _nakel_sync_ola_notification(self, title, message, notif_type):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": notif_type,
                "sticky": False,
            },
        }
