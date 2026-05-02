# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    cc_my_sales_invoice_count = fields.Integer(
        string="Mis facturas (CC)",
        compute="_compute_cc_my_sales_totals",
    )
    cc_my_sales_residual = fields.Monetary(
        string="Saldo pendiente (mis ventas)",
        compute="_compute_cc_my_sales_totals",
        currency_field="cc_my_sales_currency_id",
    )
    cc_my_sales_currency_id = fields.Many2one(
        comodel_name="res.currency",
        compute="_compute_cc_my_sales_totals",
    )

    def _cc_my_sales_domain(self):
        self.ensure_one()
        commercial = self.commercial_partner_id
        return [
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("commercial_partner_id", "=", commercial.id),
            ("invoice_user_id", "=", self.env.user.id),
        ]

    @api.depends("commercial_partner_id")
    def _compute_cc_my_sales_totals(self):
        Move = self.env["account.move"]
        currency = self.env.company.currency_id
        for partner in self:
            partner.cc_my_sales_currency_id = currency
            if not partner.id:
                partner.cc_my_sales_invoice_count = 0
                partner.cc_my_sales_residual = 0.0
                continue
            domain = partner._cc_my_sales_domain()
            moves = Move.search(domain)
            partner.cc_my_sales_invoice_count = len(moves)
            # Neto por cobrar del subconjunto: positivo = el cliente debe; negativo = crédito a favor del cliente
            partner.cc_my_sales_residual = sum(moves.mapped("amount_residual_signed"))

    def action_open_cc_my_sales(self):
        self.ensure_one()
        # No usar env.ref(...).read(): en staging la acción estándar puede estar restringida
        # a Administración y dispara AccessError en preventistas.
        return {
            "type": "ir.actions.act_window",
            "name": _("Cuenta corriente (mis ventas)"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": self._cc_my_sales_domain(),
            "context": {
                **self.env.context,
                "search_default_posted": 1,
            },
        }
