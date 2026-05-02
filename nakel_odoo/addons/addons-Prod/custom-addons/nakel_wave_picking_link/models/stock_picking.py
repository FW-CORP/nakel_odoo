# -*- coding: utf-8 -*-

from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    nakel_wave_batch_id = fields.Many2one(
        "stock.picking.batch",
        string="Ola/Wave (Nakel)",
        index=True,
        copy=False,
        help=(
            "Campo Nakel para filtrar OUT por ola aunque el OUT no tenga batch_id. "
            "Se sincroniza desde batch_id cuando aplica, y se propaga al OUT hermano vía "
            "grupo de abastecimiento / pedido de venta (fallback: Documento origen)."
        ),
    )

    def _nakel_is_out_picking(self, picking):
        self.ensure_one()
        ptype = picking.picking_type_id
        if not ptype:
            return False
        # Prefer sequence_code (OUT) when available.
        if getattr(ptype, "sequence_code", None) == "OUT":
            return True
        # Fallback: reference naming convention used in Nakel.
        name = picking.name or ""
        return name.startswith("CEN/OUT/")

    def _nakel_find_wave_batch_for_origin(self, origin):
        origin = (origin or "").strip()
        if not origin:
            return self.env["stock.picking.batch"]
        # Pick any picking in the wave batch with same origin and a batch set.
        pick = self.search(
            [
                ("origin", "=", origin),
                ("batch_id", "!=", False),
            ],
            order="write_date desc",
            limit=1,
        )
        return pick.batch_id

    def _nakel_find_wave_batch_for_procurement_links(self, picking):
        """
        Nakel: OUT suele no estar en `batch_id`, pero comparte `procurement.group` / `sale.order`
        con el PICK batcheado de la ola.
        """
        self.ensure_one()
        Batch = self.env["stock.picking.batch"]

        if picking.group_id:
            pick = self.search(
                [
                    ("group_id", "=", picking.group_id.id),
                    ("batch_id", "!=", False),
                ],
                order="write_date desc",
                limit=1,
            )
            if pick.batch_id:
                return pick.batch_id

        if picking.sale_id:
            pick = self.search(
                [
                    ("sale_id", "=", picking.sale_id.id),
                    ("batch_id", "!=", False),
                ],
                order="write_date desc",
                limit=1,
            )
            if pick.batch_id:
                return pick.batch_id

        return Batch

    def _nakel_find_wave_batch_for_out(self, picking):
        """Prefer procurement/sale links; fallback to origin string matching."""
        self.ensure_one()
        batch = picking._nakel_find_wave_batch_for_procurement_links(picking)
        if batch:
            return batch
        return picking._nakel_find_wave_batch_for_origin(picking.origin)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._nakel_sync_wave_batch()
        return records

    def write(self, vals):
        res = super().write(vals)
        touch_keys = {
            "batch_id",
            "origin",
            "picking_type_id",
            "name",
            "state",
            "group_id",
            "sale_id",
        }
        if touch_keys.intersection(vals.keys()):
            self._nakel_sync_wave_batch()
        # If a PICK-like picking joins a wave, related OUTs may need refresh even if OUT wasn't written.
        if "batch_id" in vals:
            related = self.env["stock.picking"]
            for picking in self:
                if not picking.batch_id:
                    continue
                domain = []
                if picking.group_id:
                    domain = [("group_id", "=", picking.group_id.id)]
                elif picking.sale_id:
                    domain = [("sale_id", "=", picking.sale_id.id)]
                elif (picking.origin or "").strip():
                    domain = [("origin", "=", (picking.origin or "").strip())]
                if not domain:
                    continue
                related |= self.search(domain + [("id", "not in", picking.ids)])
            if related:
                related._nakel_sync_wave_batch()
        return res

    def _nakel_sync_wave_batch(self):
        """Best-effort sync for mixed environments (PICK in batch, OUT not in batch)."""
        for picking in self:
            # 1) If picking is in a batch, mirror it.
            if picking.batch_id:
                if picking.nakel_wave_batch_id != picking.batch_id:
                    picking.nakel_wave_batch_id = picking.batch_id
                continue

            # 2) OUT (or OUT-like) pickings: infer wave from related pickings (procurement/sale/origin).
            if picking._nakel_is_out_picking(picking):
                batch = picking._nakel_find_wave_batch_for_out(picking)
                if batch and picking.nakel_wave_batch_id != batch:
                    picking.nakel_wave_batch_id = batch
                continue

            # 3) Other pickings: if wave was inferred previously but batch_id cleared, keep last known
            # (intentionally conservative: do not auto-clear wave link here).

    @api.model
    def nakel_wave_backfill_all(self, chunk: int = 500):
        """
        Backfill masivo (post-install / mantenimiento):
        Recorre pickings en chunks y fuerza `_nakel_sync_wave_batch`.

        Nota: está pensado para ejecutarse en `post_init_hook` o manualmente desde shell Odoo.
        """
        ids = self.search([], order="id asc").ids
        for i in range(0, len(ids), chunk):
            subset = self.browse(ids[i : i + chunk])
            subset._nakel_sync_wave_batch()
