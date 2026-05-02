# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api

class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    @api.depends('amount', 'payment_date', 'partner_id')
    def _compute_l10n_ar_withholding_ids(self):
        """
        Override to skip automatic withholding creation
        for custom AR payment flow.
        """
        # 🔥 If coming from your custom wizard → skip
        if self.env.context.get('from_ar_custom_payment'):
            for wizard in self:
                wizard.l10n_ar_withholding_ids = False
            return

        # ✅ Otherwise → normal behavior
        return super()._compute_l10n_ar_withholding_ids()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
