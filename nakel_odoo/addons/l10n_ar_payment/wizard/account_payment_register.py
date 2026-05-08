# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api

class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    #🛑 STOP withholding recompute #l10n_ar_withholding/wizards/account_payment_register.py
    @api.depends('amount', 'payment_date', 'partner_id')
    def _compute_l10n_ar_withholding_ids(self):
        #print("\n _compute_l10n_ar_withholding_ids() called with context:", self.env.context)
        """ Override to skip automatic withholding creation for custom AR payment flow. """
        # 🔥 If coming from your custom wizard → skip
        if self.env.context.get('from_ar_custom_payment'):
            #print("IF.....")
            for wizard in self:
                wizard.l10n_ar_withholding_ids = False
            #print("self.l10n_ar_withholding_ids:", self.mapped('l10n_ar_withholding_ids'))
            return
        #print("Else.....")

        # ✅ Otherwise → normal behavior
        return super()._compute_l10n_ar_withholding_ids()

    #🛑 STOP amount recompute
    @api.depends('line_ids')
    def _compute_amount(self):
        #print("\n_compute_amount() called with context:", self.env.context)
        if self.env.context.get('from_ar_custom_payment'):
            #print("IF.....")
            return
        #print("Else.....")
        return super()._compute_amount()

    #🛑 STOP journal computation
    @api.depends('available_journal_ids')
    def _compute_journal_id(self):
        if self.env.context.get('from_ar_custom_payment'):
            # 🔒 Do NOT recompute → keep user-selected journal
            return
        return super()._compute_journal_id()

    #🛑 Prevent recompute during create
    def _create_payments(self):
        if self.env.context.get('from_ar_custom_payment'):
            self = self.with_context(
                skip_account_move_synchronization=True,
                skip_invoice_sync=True,
            )
        return super()._create_payments()


class l10nArPaymentRegisterWithholding(models.TransientModel):
    _inherit = 'l10n_ar.payment.register.withholding'

    #odoo-18.0/addons/l10n_ar_withholding/wizards/l10n_ar_payment_register_withholding.py
    #🛑 STOP recompute for witholding line's amount in the Wizard
    @api.depends('base_amount', 'tax_id')
    def _compute_amount(self):
        if self.env.context.get('from_ar_custom_payment'):
            return
        return super()._compute_amount()

    @api.depends('payment_register_id.amount', 'tax_id')
    def _compute_base_amount(self):
        if self.env.context.get('from_ar_custom_payment'):
            return
        return super()._compute_base_amount()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
