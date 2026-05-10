# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import _, api, fields, models
from odoo.tools import float_is_zero


class ResPartner(models.Model):
    _inherit = "res.partner"

    cc_my_sales_invoice_count = fields.Integer(
        string="Mis facturas (CC)",
        compute="_compute_cc_my_sales_totals",
        groups="sales_team.group_sale_salesman,sales_team.group_sale_manager,clientes_cc_detalle.group_cc_my_sales",
    )
    cc_my_sales_residual = fields.Monetary(
        string="Adeudado (mis ventas)",
        compute="_compute_cc_my_sales_totals",
        currency_field="cc_my_sales_currency_id",
        groups="sales_team.group_sale_salesman,sales_team.group_sale_manager,clientes_cc_detalle.group_cc_my_sales",
        help="Suma de amount_residual_signed en FC/NC publicadas donde vos sos el comercial "
        "(invoice_user_id). No incluye deuda por ventas de otros vendedores/PDV.",
    )
    cc_my_sales_currency_id = fields.Many2one(
        comodel_name="res.currency",
        compute="_compute_cc_my_sales_totals",
        groups="sales_team.group_sale_salesman,sales_team.group_sale_manager,clientes_cc_detalle.group_cc_my_sales",
    )
    cc_my_sales_state = fields.Selection(
        selection=[
            ("none", "Sin operaciones"),
            ("ok", "Al día"),
            ("due", "Con saldo"),
            ("overdue", "Con vencido"),
            ("credit", "Crédito a favor"),
        ],
        string="Estado CC (mis ventas)",
        compute="_compute_cc_my_sales_totals",
        groups="sales_team.group_sale_salesman,sales_team.group_sale_manager,clientes_cc_detalle.group_cc_my_sales",
        help="Derivado solo de facturas/notas donde sos el comercial; no refleja la cuenta corriente global del contacto.",
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
        """Una sola pasada sobre account.move por lote de contactos (lista / búsqueda)."""
        Move = self.env["account.move"]
        currency = self.env.company.currency_id
        user = self.env.user
        today = fields.Date.context_today(self)

        if not self:
            return

        # Nuevos / sin id: todo en cero
        for p in self:
            if not p.id:
                p.cc_my_sales_currency_id = currency
                p.cc_my_sales_invoice_count = 0
                p.cc_my_sales_residual = 0.0
                p.cc_my_sales_state = "none"

        with_id = self.filtered(lambda r: r.id)
        if not with_id:
            return

        commercial_ids = list({p.commercial_partner_id.id for p in with_id})
        base_domain = [
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("invoice_user_id", "=", user.id),
            ("commercial_partner_id", "in", commercial_ids),
        ]
        moves = Move.search(base_domain)

        sums = defaultdict(float)
        counts = defaultdict(int)
        overdue_by_commercial = defaultdict(bool)

        for m in moves:
            cid = m.commercial_partner_id.id
            sums[cid] += m.amount_residual_signed
            counts[cid] += 1
            if (
                m.payment_state in ("not_paid", "partial")
                and m.invoice_date_due
                and m.invoice_date_due < today
            ):
                overdue_by_commercial[cid] = True

        prec = currency.rounding

        for partner in with_id:
            partner.cc_my_sales_currency_id = currency
            cid = partner.commercial_partner_id.id
            cnt = counts.get(cid, 0)
            total = sums.get(cid, 0.0)
            partner.cc_my_sales_invoice_count = cnt
            partner.cc_my_sales_residual = total

            if cnt == 0:
                partner.cc_my_sales_state = "none"
                continue

            if float_is_zero(total, precision_rounding=prec):
                partner.cc_my_sales_state = (
                    "overdue" if overdue_by_commercial.get(cid, False) else "ok"
                )
            elif total < 0.0:
                partner.cc_my_sales_state = "credit"
            elif overdue_by_commercial.get(cid, False):
                partner.cc_my_sales_state = "overdue"
            else:
                partner.cc_my_sales_state = "due"

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
