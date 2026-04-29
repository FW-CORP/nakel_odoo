# -*- coding: utf-8 -*-
# Copyright (C) 2024-present The Authors
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl)

from odoo import models, fields, api, _
from odoo.exceptions import UserError

MAP_INVOICE_TYPE_PARTNER_TYPE = {
    'out_invoice': 'customer',
    'out_refund': 'customer',
    'out_receipt': 'customer',
    'in_invoice': 'supplier',
    'in_refund': 'supplier',
    'in_receipt': 'supplier',
}

MAP_INVOICE_TYPE_PAYMENT_SIGN = {
    'out_invoice': 1,
    'out_refund': -1,
    'out_receipt': 1,
    'in_invoice': -1,
    'in_refund': 1,
    'in_receipt': -1,
}


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_open_ar_register_payment(self):
        vals = self._prepare_ar_payment_vals()
        #print("\n\nVALS: ", vals)
        payment = self.env['ar.register.payments'].create(vals)

        # ✅ If all validations pass → open your model
        return {
            'type': 'ir.actions.act_window',
            'name': 'AR Register Payment',
            'res_model': 'ar.register.payments',
            'view_mode': 'form',
            'res_id': payment.id,
            'target': 'current',  # or 'new' if you want popup
        }


    def _prepare_ar_payment_vals(self):

        context = dict(self._context or {})
        active_ids = context.get('active_ids') or self.ids

        #Invoice = self.env['account.move']
        #invoice_objs = Invoice.search([('id', 'in', active_ids)], order='invoice_date asc')
        invoice_objs = self.browse(active_ids).sorted('invoice_date') #it will sort by invoice_date ascending order.

        # =====================
        # VALIDATIONS (same as your default_get)
        # =====================
        if not active_ids:
            raise UserError(_("No active invoices found."))

        invalid_moves = invoice_objs.filtered(
            lambda m: m.move_type not in ('out_invoice', 'in_invoice')
        )
        if invalid_moves:
            raise UserError(_(
                "Invalid records selected:\n%s\n\nOnly Customer Invoices and Vendor Bills are allowed."
            ) % "\n".join(invalid_moves.mapped('name')))

        # ✅ Posted check
        if any(inv.state != 'posted' for inv in invoice_objs):
            raise UserError(_("You can only register payments for posted invoices."))

         # ✅ NEW: Residual (Amount Due) check
        if any(inv.currency_id.is_zero(inv.amount_residual) for inv in invoice_objs):
            raise UserError(_("You cannot register payment for fully paid invoices (Amount Due = 0)."))

        if any(inv.payment_state == 'paid' for inv in invoice_objs):
            raise UserError(_("You can not register payments for paid invoices."))

        if any(inv.currency_id != invoice_objs[0].currency_id for inv in invoice_objs):
            raise UserError(_("In order to pay multiple invoices at once, they must use the same currency."))

        partners = invoice_objs.mapped('partner_id')
        if len(partners) > 1:
            raise UserError(_("All bills must belong to same vendor."))

        companies = invoice_objs.mapped('company_id')
        if len(companies) > 1:
            raise UserError(_("All bills must belong to same company."))

        # =====================
        # PAYMENT TYPE
        # =====================
        move_type = MAP_INVOICE_TYPE_PARTNER_TYPE[invoice_objs[0].move_type]
        payment_type = 'outbound' if move_type == 'supplier' else 'inbound'

        #payment_method = self.env['account.payment.method'].search([('payment_type', '=', payment_type)], limit=1)


        # =====================
        # AVAILABLE LINES
        # =====================
        available_lines = self.env['account.move.line']
        for line in invoice_objs.line_ids:
            if line.move_id.state != 'posted':
                continue

            if line.account_type not in ('asset_receivable', 'liability_payable'):
                continue

            if line.currency_id:
                if line.currency_id.is_zero(line.amount_residual_currency):
                    continue
            else:
                if line.company_currency_id.is_zero(line.amount_residual):
                    continue

            available_lines |= line

        # =====================
        # PAYMENT LINES
        # =====================
        line_vals = []
        for invoice in invoice_objs:

            if invoice.move_type in ('out_invoice','out_refund','out_receipt'):
                memo = invoice.name
            else:
                memo = invoice.ref or invoice.name

            line_vals.append((0, 0, {
                'partner_id': invoice.partner_id.id,
                'ref': invoice.ref,
                'invoice_date': invoice.invoice_date,
                'date_due': invoice.invoice_date_due or False,
                'amount_total': invoice.amount_total,
                'amount_due': invoice.amount_residual,
                'amount': invoice.amount_residual,
                'invoice_id': invoice.id,
                #'move_currency_id': invoice.currency_id.id,# Need this here ?
                #'currency_id': invoice.currency_id.id,
                'communication': memo,
                'payment_date': fields.Date.context_today(self),
            }))

        # =====================
        # FINAL VALS
        # =====================
        return {
            'partner_id': invoice_objs[0].partner_id.id,
            'payment_lines': line_vals,
            'payment_type': payment_type,
            'partner_type': move_type,
            'line_ids': [(6, 0, available_lines.ids)],
            'move_ids': [(6, 0, invoice_objs.ids)],
            'company_id': invoice_objs[0].company_id.id,
            'payment_date': fields.Date.context_today(self),
        }