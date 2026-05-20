# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class AccountPayment(models.Model):
    _inherit = "account.payment"

    #AR Register Payment
    ar_register_payment_id = fields.Many2one('ar.register.payments', string="AR Payment Order", readonly=True, copy=False)
    #AR Register Payment Line
    ar_register_payment_line_id = fields.Many2one('ar.register.payments.line', string="AR Payment Order Line", readonly=True, copy=False)
    ar_move_id = fields.Many2one('account.move', related='ar_register_payment_line_id.invoice_id', string="AR: Move", store=True, readonly=True)#only for search view purpose.

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
