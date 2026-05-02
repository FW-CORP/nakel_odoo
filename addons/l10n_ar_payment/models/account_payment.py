# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class AccountPayment(models.Model):
    _inherit = "account.payment"

    ar_register_payment_id = fields.Many2one('ar.register.payments', readonly=True, copy=False)
    ar_register_payment_line_id = fields.Many2one('ar.register.payments.line', readonly=True, copy=False)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
