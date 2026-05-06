# -*- coding: utf-8 -*-
from odoo import models


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _nakel_pos_iibb_shipping_is_enabled(self):
        v = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("nakel_pos_iibb_shipping.enable", "False")
        )
        return str(v).lower() in ("1", "true", "yes")

    def _prepare_invoice_vals(self):
        vals = super()._prepare_invoice_vals()
        if not self._nakel_pos_iibb_shipping_is_enabled():
            return vals
        journal = self.session_id.config_id.invoice_journal_id
        addr = getattr(journal, "l10n_ar_afip_pos_partner_id", False)
        if addr:
            vals["partner_shipping_id"] = addr.id
        return vals
