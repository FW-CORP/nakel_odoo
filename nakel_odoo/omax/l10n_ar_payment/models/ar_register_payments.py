# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
from datetime import datetime
from datetime import timedelta


class ArRegisterPayment(models.Model):
    _name = "ar.register.payments"
    _description = "AR Register Payments"
    _rec_name = 'payment_order_number'
    #_order = "payment_order_number desc"

    @api.depends('payment_order_number', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.payment_order_number or "AR Register Payments"

    payment_order_number = fields.Char(string="Payment Order Number", readonly=True, copy=False)
    name = fields.Char(string="Name", default="AR Register Payments", readonly=True)
    partner_id = fields.Many2one('res.partner', string='Partner', readonly=True)#TODO partner dynamic lable
    payment_date = fields.Date(string='Payment Date', default=fields.Date.context_today, required=True)

    payment_type = fields.Selection([('outbound', 'Send Money'), ('inbound', 'Receive Money')], string='Payment Type', readonly=True, required=True)
    partner_type = fields.Selection([('customer', 'Customer'), ('supplier', 'Vendor')], readonly=True)

    company_id = fields.Many2one('res.company', store=True, readonly=True, copy=False)#compute='_compute_from_lines'
    company_currency_id = fields.Many2one('res.currency', string="Company Currency",
        related='company_id.currency_id')#default=lambda self: self.env.user.company_id.currency_id

    payment_lines = fields.One2many('ar.register.payments.line', 'payment_id', string='Payment Lines')
    line_ids = fields.Many2many(comodel_name='account.move.line', relation='ar_payment_register_move_line_new_rel', column1='wizard_id', column2='line_id',
        string="Journal items", readonly=True, copy=False,)
    move_ids = fields.Many2many('account.move', string="Selected Moves", readonly=True)
    #Total Amount to Pay (gross)
    is_executed = fields.Boolean(string="Is Executed", default=False, readonly=True)
    created_account_payment_ids = fields.Many2many(comodel_name='account.payment', relation='ar_register_multi_payments_account_payment_rel', 
         column1='ar_register_payments_id', column2='account_payment_id', string="Created Payments", readonly=True, copy=False)
    payment_count = fields.Integer(compute="_compute_payment_count", string="Payments")


    def create_payment(self):
        self.ensure_one()

        RegisterPayment = self.env['account.payment.register']
        payments = self.env['account.payment']

        for line in self.payment_lines:
            if not line.amount:
                continue

            if line.l10n_ar_net_amount < 0:
                raise ValidationError("Withholding exceeds payment amount.")

            # 1. Create wizard (skip compute via context override)
            wizard = RegisterPayment.with_context(
                active_model='account.move',
                active_ids=[line.invoice_id.id],
                from_ar_custom_payment=True,  # 🔒 lock mode
            ).create({
                'payment_date': line.payment_date or self.payment_date,
                'journal_id': line.journal_id.id,
                'payment_method_line_id': line.payment_method_line_id.id,
                'amount': line.amount,
                'currency_id': line.currency_id.id,
                'communication': line.communication,
            })
            #print("\nline.currency_id.id:", line.currency_id.name)
            #print("wizard.currency_id:",wizard.currency_id.name)
            #Stop
            #Auto manage fieldsin the create()
            #company_id, currency_id, partner_id, partner_type, payment_type, l10n_ar_net_amount, 
            #print("Created Wizard:",wizard)

            # 2. Inject withholding, existing checks/new checks INTO wizard (CRITICAL)
            wizard.write({
                # Withholdings
                'l10n_ar_withholding_ids': [
                    (0, 0, {
                        'tax_id': wth.tax_id.id,
                        'base_amount': wth.base_amount,
                        'amount': wth.amount,
                        #'l10n_ar_net_amount': it will auto calculate based on the base_amount and tax_id, no need to set it here.
                    })
                    for wth in line.l10n_ar_withholding_ids if wth.tax_id
                ],

                # Existing checks (M2M)
                'l10n_latam_move_check_ids': [ (6, 0, line.l10n_latam_move_check_ids.ids) ] if line.l10n_latam_move_check_ids else False,

                # New checks (O2M with mapping)
                'l10n_latam_new_check_ids': [
                    (0, 0, {
                        'name': check_line.name,
                        'bank_id': check_line.bank_id.id,
                        'issuer_vat': check_line.issuer_vat,
                        'payment_date': check_line.payment_date,
                        'amount': check_line.amount,
                    })
                    for check_line in line.l10n_latam_new_check_ids
                ],
            })
            #before
            #for wth_line in line.l10n_ar_withholding_ids:
            #    print("source wth_line:",wth_line, "base_amount:", wth_line.base_amount, "amount:", wth_line.amount)
            #for withholding in wizard.l10n_ar_withholding_ids:
            #    print("new Withholding line:", withholding, "base_amount:", withholding.base_amount, "amount:", withholding.amount)

            # 3. Create payment
            new_payment = wizard._create_payments()
            #print("\nNew Payment:",new_payment)
            # Copy withholding number back to my custom lines

            # ✅ Assign withholding number custom withholding lines
            if new_payment.l10n_ar_withholding_ids:
                for line_wth in line.l10n_ar_withholding_ids:
                    matched = new_payment.l10n_ar_withholding_ids.filtered(lambda aml: aml.tax_line_id == line_wth.tax_id and 
                        abs(aml.tax_base_amount) == abs(line_wth.base_amount))
                    if matched:
                        line_wth.name = matched[0].name

            # Tracking purpose
            line.created_account_payment_id = new_payment.id
            new_payment.write({
                'ar_register_payment_id': self.id,
                'ar_register_payment_line_id': line.id,
            })

            payments |= new_payment

        # 🔥 GENERATE PAYMENT ORDER NUMBER HERE
        if payments and not self.payment_order_number:
            self.payment_order_number = self.env['ir.sequence'].next_by_code('ar.payment.order')

            # OPTIONAL: link to payments
            #payments.write({
            #    'ar_register_payment_id': self.id,
            #    'ar_register_payment_line_id': line.id,
            #})
        self.is_executed = True
        # ✅ STORE ALL PAYMENTS
        if payments:
            self.created_account_payment_ids = [(6, 0, payments.ids)]

        # -----------------------------------
        # 5. Return created payments
        # -----------------------------------
        return {
            'type': 'ir.actions.act_window',
            'name': 'Payments',
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('account.view_account_payment_tree').id, 'list'),
                (self.env.ref('account.view_account_payment_form').id, 'form'),
            ],
            'domain': [('id', 'in', payments.ids)],
            'context': {'create': False},
        }

    def _compute_payment_count(self):
        for rec in self:
            rec.payment_count = len(rec.created_account_payment_ids)

    def action_view_payments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Payments',
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('account.view_account_payment_tree').id, 'list'),
                (self.env.ref('account.view_account_payment_form').id, 'form'),
            ],
            'domain': [('id', 'in', self.created_account_payment_ids.ids)],
            'context': {'create': False},
        }

    # Optional: scheduled cleanup of unused payment records (if any)
    def _cron_cleanup_unused_ar_payments(self):
        #print("\n_cron_cleanup_unused_ar_payments()...", self)
        # 2 days old threshold
        limit_date = fields.Datetime.now() - timedelta(days=2)
        #print("limit_date:",limit_date)

        """records = self.search([
            ('is_executed', '=', False),
            ('payment_order_number', '=', False),
            ('created_account_payment_ids', '=', False),
            ('create_date', '<=', limit_date),
            ('write_date', '<=', limit_date)
        ])
        print("ORM Records to cleanup:", records)"""

        rel_table = self._fields['created_account_payment_ids'].relation
        #print("rel_table:", rel_table)
        query = f"""
            SELECT arp.id
            FROM ar_register_payments arp
            LEFT JOIN {rel_table} rel
                ON rel.ar_register_payments_id = arp.id
            WHERE arp.is_executed = FALSE
            AND arp.payment_order_number IS NULL
            AND rel.account_payment_id IS NULL
            AND arp.create_date <= %s
            AND arp.write_date <= %s
        """
        #print("SQL Query:", query)
        self.env.cr.execute(query, (limit_date, limit_date))
        ids = [row[0] for row in self.env.cr.fetchall()]
        if not ids:
            return
        records = self.browse(ids)
        #print("Records to cleanup after SQL check:", records)
        records.unlink()

    def unlink(self):
        for rec in self:
            if rec.is_executed:
                raise UserError("You cannot delete executed AR Payments.")
        return super().unlink()

class ArRegisterPaymentsLines(models.Model):
    _name = "ar.register.payments.line"
    _description = "Multiple Register Payment Line"
    _rec_name = 'invoice_id'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if not rec.payment_method_line_id and rec.journal_id:
                if rec.payment_type == 'inbound':
                    methods = rec.journal_id.inbound_payment_method_line_ids
                else:
                    methods = rec.journal_id.outbound_payment_method_line_ids

                rec.payment_method_line_id = methods[0] if methods else False
        return records

    payment_id = fields.Many2one('ar.register.payments', string='Payment', ondelete='cascade')#O2M
    created_account_payment_id = fields.Many2one('account.payment', string="Created Payment", readonly=True, copy=False)
    company_id = fields.Many2one(related='payment_id.company_id', store=True, copy=False, readonly=True)#compute='_compute_from_lines'
    partner_id = fields.Many2one('res.partner', string='Partner', readonly=True)
    partner_type = fields.Selection(related='payment_id.partner_type', store=True, readonly=True)
    payment_type = fields.Selection(related='payment_id.payment_type', store=True, readonly=True)

    invoice_id = fields.Many2one('account.move', string='Number', required=True)
    move_currency_id = fields.Many2one(related='invoice_id.currency_id', comodel_name='res.currency', string='Document Currency', required=True, help="The currency of the invoice/bill. Used to know in which currency the payment should be registered.")
    currency_id = fields.Many2one(related='invoice_id.currency_id',  comodel_name='res.currency', string='Payment Currency', store=True, help="The currency of the payment.")
    invoice_date = fields.Date(string="Date", readonly=True)
    date_due = fields.Date(string="Due Date", readonly=True)
    payment_date = fields.Date(string='Payment Date', default=fields.Date.context_today, required=True)

    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        compute='_compute_journal_id',
        store=True,
        readonly=False,
        #precompute=True,
        check_company=True,
        domain="[('id', 'in', available_journal_ids)]",
    )#required=True managed in the view side same as default account.register.payment wizard
    available_journal_ids = fields.Many2many(
        comodel_name='account.journal',
        compute='_compute_available_journal_ids'
    )
    @api.depends('company_id', 'payment_type', 'invoice_id')
    def _compute_journal_id(self):
        #print("\n_compute_journal_id()...",self)
        for rec in self:
            journals = self.env['account.journal'].search([
                ('company_id', '=', rec.company_id.id),
                ('type', 'in', ('bank', 'cash'))
            ])
            if rec.payment_type == 'inbound':
                journals = journals.filtered(lambda j: j.inbound_payment_method_line_ids)
            else:
                journals = journals.filtered(lambda j: j.outbound_payment_method_line_ids)

            # Try invoice preferred journal (if exists)
            preferred = rec.invoice_id.preferred_payment_method_line_id.journal_id
            #print("preferred journal from invoice:", preferred)
            if preferred and preferred in journals:
                rec.journal_id = preferred
            else:
                rec.journal_id = journals[:1] if journals else False
            #print("final journal_id:", rec.journal_id)

    @api.depends('company_id', 'payment_type', 'invoice_id')
    def _compute_available_journal_ids(self):
        #print("\n_compute_available_journal_ids()...",self)
        for rec in self:
            domain = [
                ('company_id', '=', rec.company_id.id),
                ('type', 'in', ('bank', 'cash'))
            ]
            # Optional: filter by inbound/outbound
            if rec.payment_type == 'inbound':
                domain.append(('inbound_payment_method_line_ids', '!=', False))
            elif rec.payment_type == 'outbound':
                domain.append(('outbound_payment_method_line_ids', '!=', False))
            #print("domain:",domain)
            rec.available_journal_ids = self.env['account.journal'].search(domain)
            #print("available_journal_ids:", rec.available_journal_ids)


    # == Payment methods fields ==
    payment_method_line_id = fields.Many2one(
        'account.payment.method.line',
        string='Payment Method',
        #store=True,
        readonly=False,
        domain="[('journal_id', '=', journal_id)]",
    )# _onchange_payment_method added.
    #required=True managed in the view side same as default account.register.payment wizard. 
    #compute='_compute_payment_method_line_id',
    #domain="[('id', 'in', available_payment_method_line_ids)]",
    #available_payment_method_line_ids = fields.Many2many('account.payment.method.line', compute='_compute_available_payment_method_line_ids')
    payment_method_code = fields.Char(
        related='payment_method_line_id.code')

    @api.onchange('journal_id', 'payment_type')
    def _onchange_payment_method(self):
        for rec in self:
            if not rec.journal_id:
                rec.payment_method_line_id = False
                continue
            if rec.payment_type == 'inbound':
                methods = rec.journal_id.inbound_payment_method_line_ids
            else:
                methods = rec.journal_id.outbound_payment_method_line_ids

            rec.payment_method_line_id = methods[0] if methods else False


    amount_total = fields.Monetary(string='Total', currency_field='currency_id',readonly=True)
    amount_due = fields.Monetary(string='Amount Due', currency_field='currency_id', readonly=True)
    amount = fields.Monetary(currency_field='currency_id', string='Amount', required=True)
    communication = fields.Char(string='Memo')
    ref = fields.Char(string='Reference')#

    l10n_ar_withholding_ids = fields.One2many(
        'ar.payment.register.withholding', 'payment_line_id', string="Withholdings",
        compute="_compute_l10n_ar_withholding_ids_copy", readonly=False, store=True)
    l10n_ar_withholding_amount_total = fields.Monetary(
        string="Withholdings Amount",
        currency_field='currency_id',
        compute='_compute_l10n_ar_amounts',
        store=True,
        readonly=True,
        help="Total withholdings amount"
    )
    l10n_ar_net_amount = fields.Monetary(
        string="Net Amount",
        currency_field='currency_id',
        compute='_compute_l10n_ar_amounts',
        store=True,
        readonly=True,
        help="Net amount after withholdings"
    )
    is_executed = fields.Boolean(
        related='payment_id.is_executed',
        store=True,
        readonly=True
    )

    @api.depends('partner_id', 'payment_date')
    def _compute_l10n_ar_withholding_ids_copy(self):
        #print("\n\n Custom _compute_l10n_ar_withholding_ids()...from l10n_ar_withholding",self)
        for payment_line in self:
            #print("payment_line.partner_id.commercial_partner_id.id:",payment_line.partner_id.commercial_partner_id.id)
            #print("payment_line.partner_type:",payment_line.partner_type)
            #print("payment_line.company_id:",payment_line.company_id)

            date = payment_line.payment_date or fields.Date.context_today(self)
            partner_taxes = self.env['l10n_ar.partner.tax'].search([
                *self.env['l10n_ar.partner.tax']._check_company_domain(payment_line.company_id),
                '|', ('from_date', '>=', date), ('from_date', '=', False),
                '|', ('to_date', '<=', date), ('to_date', '=', False),
                ('partner_id', '=', payment_line.partner_id.commercial_partner_id.id),
                ('tax_id.l10n_ar_withholding_payment_type', '=', payment_line.partner_type)#payment_line.payment_id.partner_type
            ])
            #print("partner_taxes:",partner_taxes)
            #Stop
            payment_line.l10n_ar_withholding_ids = [Command.clear()] + [Command.create({'tax_id': x.tax_id.id}) for x in partner_taxes]
            print("payment_line.l10n_ar_withholding_ids:", payment_line.l10n_ar_withholding_ids)

    @api.depends('amount', 'l10n_ar_withholding_ids.amount', 'l10n_ar_withholding_ids.base_amount', 'l10n_ar_withholding_ids.is_manual')
    def _compute_l10n_ar_amounts(self):
        for line in self:
            total_withholding = sum(line.l10n_ar_withholding_ids.mapped('amount'))
            #print(f"\n _compute_l10n_ar_amounts() from AR - line: {line}, total_withholding: {total_withholding}")
            line.l10n_ar_net_amount = line.amount - total_withholding
            line.l10n_ar_withholding_amount_total = total_withholding
            #print(f"line: {line}, net_amount: {line.l10n_ar_net_amount}, withholding_amount_total: {line.l10n_ar_withholding_amount_total}")
            #if line.l10n_ar_net_amount < 0:
            #    raise ValidationError("Total Withholding exceeds payment amount.")


    """@api.onchange('amount')# old logic
    def _onchange_payment_amount(self):
        print("\n_onchange_payment_amount()...from AR",self)
        for line in self:
            for wth in line.l10n_ar_withholding_ids:
                # recompute base first (already computed via depends, but safe)
                wth._compute_base_amount()
                # recompute withholding amount
                amount, _, _ = wth._tax_compute_all_helper()
                print("Recomputed withholding amount:", amount)
                wth.amount = amount
                print("Updated withholding line:", wth, "with amount:", wth.amount)"""

    @api.onchange('amount')
    def _onchange_payment_amount(self):#3.1 #new logic
        for line in self:
            for wth in line.l10n_ar_withholding_ids:
                wth.is_manual = False

    @api.onchange('invoice_id',)
    def _onchange_invoice_id(self):
        #print("\n\n_onchange_invoice_id:",self)
        for rec in self:
            rec.partner_id = rec.invoice_id.partner_id
            rec.invoice_date = rec.invoice_id.invoice_date
            rec.date_due = rec.invoice_id.invoice_date_due or False
            rec.amount_total = rec.invoice_id.amount_total

            # 🔥 Compute already used amount in this wizard
            other_lines = rec.payment_id.payment_lines.filtered(
                lambda l: l.invoice_id == rec.invoice_id and l != rec
            )
            already_used = sum(other_lines.mapped('amount'))

            # 🔥 Remaining amount
            remaining = rec.invoice_id.amount_residual - already_used

            if remaining < 0:
                remaining = 0.0

            rec.amount_due = remaining
            rec.amount = remaining

            rec.move_currency_id = rec.invoice_id.currency_id
            rec.ref = rec.invoice_id.ref
            rec.communication = (
                rec.invoice_id.name
                if rec.invoice_id.move_type in ('out_invoice','out_refund','out_receipt')
                else rec.invoice_id.ref or rec.invoice_id.name
            )

    #when i add constrains, auto withholding auto calculation is not working so comment the code.
    """@api.constrains('amount', 'l10n_ar_withholding_ids', 'l10n_ar_withholding_ids.amount')
    def _check_withholding_amount(self):
        for line in self:
            total_withholding = sum(line.l10n_ar_withholding_ids.mapped('amount'))
            if total_withholding > line.amount:
                raise ValidationError(_(
                    "Total Withholding (%.2f) exceeds Payment Amount (%.2f)."
                ) % (total_withholding, line.amount))"""

    @api.onchange('amount', 'l10n_ar_withholding_ids', 'l10n_ar_withholding_ids.amount')#TODO not valid: ['l10n_ar_withholding_ids.amount'] 
    def _onchange_withholding_validation(self):
        for line in self:
            total_withholding = sum(line.l10n_ar_withholding_ids.mapped('amount'))
            if total_withholding > line.amount:
                return#TODO
                #return {
                #    'warning': {
                #        'title': "Warning",
                #        'message': "Total Withholding exceeds Payment Amount."
                #    }
                #}

    def action_open_withholding(self):
        #print("\naction_open_withholding()...from l10n_ar_withholding",self, self.id)
        self.ensure_one()
        if not self.id:
            raise UserError(_("Please save the record before opening Withholding."))#not calling. check and remove the code.
        return {
            'type': 'ir.actions.act_window',
            'name': 'Withholdings',
            'res_model': 'ar.register.payments.line',
            'view_mode': 'form',
            'target': 'new',  # open in popup
            'res_id': self.id, 
        }

    l10n_latam_new_check_ids = fields.One2many('latam.payment.register.check', 'payment_line_id', string="New Checks")
    l10n_latam_move_check_ids = fields.Many2many(
        comodel_name='l10n_latam.check', relation='ar_register_multi_payments_latam_check_rel', column1='ar_register_payments_line_id', column2='check_id',
        string='Checks',
    )

    @api.onchange('l10n_latam_move_check_ids', 'l10n_latam_move_check_ids.amount', 'l10n_latam_new_check_ids', 'l10n_latam_new_check_ids.amount', 'payment_method_code')
    def _onchange_set_amounts(self):
        #print("\n\n_onchange_set_amounts()...from AR Payment Lines", self)
        for wizard in self.filtered(lambda x: x._is_latam_check_payment(check_subtype='new_check')):
            #print("Updating amount based on new checks... wizard: ",wizard)
            wizard.amount = sum(wizard.l10n_latam_new_check_ids.mapped('amount'))
            #print("New check amount total:", wizard.amount)
        for wizard in self.filtered(lambda x: x._is_latam_check_payment(check_subtype='move_check')):
            #print("Updating amount based on move checks... wizard: ", wizard)
            wizard.amount = sum(wizard.l10n_latam_move_check_ids.mapped('amount'))
            #print("Move check amount total:", wizard.amount)

    def _is_latam_check_payment(self, check_subtype=False):
        if check_subtype == 'move_check':
            codes = ['in_third_party_checks', 'out_third_party_checks', 'return_third_party_checks']
        elif check_subtype == 'new_check':
            codes = ['new_third_party_checks', 'own_checks']
        else:
            codes = ['in_third_party_checks', 'out_third_party_checks', 'return_third_party_checks', 'new_third_party_checks', 'own_checks']
        return self.payment_method_code in codes


# ar.payment.register.withholding = l10n_ar.payment.register.withholding:
class ArPaymentRegisterWithholding(models.Model):
    _name = 'ar.payment.register.withholding'
    _description = 'AR Payment register withholding lines'
    _rec_name = 'tax_id'
    _check_company_auto = True

    #ref : l10n_ar_withholding/wizards/l10n_ar_payment_register_withholding.py
    payment_line_id = fields.Many2one('ar.register.payments.line', string='Payment Line', ondelete='cascade')#O2M required=True, 

    company_id = fields.Many2one(related='payment_line_id.company_id')
    currency_id = fields.Many2one(related='payment_line_id.currency_id')#Document's currency
    name = fields.Char(string='Number')
    tax_id = fields.Many2one(
        'account.tax', check_company=True, required=True,
        domain="[('l10n_ar_withholding_payment_type', '=', parent.partner_type)]")
        #domain="[('l10n_ar_withholding_payment_type', '=', parent.payment_id.partner_type)]"
    withholding_sequence_id = fields.Many2one(related='tax_id.l10n_ar_withholding_sequence_id')
    base_amount = fields.Monetary(compute='_compute_base_amount', store=True, readonly=False)
    #amount = fields.Monetary(store=True, readonly=False)
    amount = fields.Monetary(compute='_compute_amount', store=True, readonly=False)#3.1
    is_manual = fields.Boolean(string="Manual Override", readonly=True, default=False)#3.1


    @api.depends('base_amount', 'tax_id', 'payment_line_id.amount')
    def _compute_amount(self):#3.1
        #print("\n_compute_amount()...from AR withholding amount",self)
        for line in self:
            # 🟡 Skip auto if user manually edited
            if line.is_manual:
                continue #it's called on Save.
            if not line.tax_id:
                line.amount = 0.0
            else:
                line.amount = line._tax_compute_all_helper()[0]

    @api.onchange('amount')
    def _onchange_amount_manual(self):#3.1
        for rec in self:
            if rec.tax_id:
                rec.is_manual = True

    """@api.onchange('base_amount', 'tax_id')
    def _onchange_amount(self):#old logic
        print("\n_onchange_amount()...from AR",self)
        for line in self:
            #if line.tax_id and not line.amount:
            if line.tax_id:
                #line.amount = line._tax_compute_all_helper()[0]
                amount, _, _ = line._tax_compute_all_helper()
                line.amount = amount"""

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            # Only set if not provided manually
            if rec.tax_id and not rec.amount:
                rec.amount = rec._tax_compute_all_helper()[0]
        return records

    def _tax_compute_all_helper(self):
        #print("\n@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@_tax_compute_all_helper()...from AR",self)
        self.ensure_one()
        # Computes the withholding tax amount provided a base and a tax
        # It is equivalent to: amount = self.base * self.tax_id.amount / 100

        # if it is earnings withholding, then we accumulate the tax base for the period
        if self.tax_id.l10n_ar_tax_type in ['earnings', 'earnings_scale']:
            to_date = self.payment_line_id.payment_id.payment_date or fields.Date.context_today(self)
            from_date = to_date + relativedelta(day=1)
            # We search for the payments in the same month of the same regimen and the same code.
            domain_same_period_withholdings = [
                *self.env['account.move.line']._check_company_domain(self.tax_id.company_id),
                ('parent_state', '=', 'posted'),
                ('tax_line_id.l10n_ar_code', '=', self.tax_id.l10n_ar_code),
                ('tax_line_id.l10n_ar_tax_type', 'in', ['earnings', 'earnings_scale']),
                ('partner_id', '=', self.payment_line_id.payment_id.partner_id.commercial_partner_id.id),
                ('date', '<=', to_date), ('date', '>=', from_date)]
            if same_period_partner_withholdings := self.env['account.move.line']._read_group(domain_same_period_withholdings, ['partner_id'], ['balance:sum']):
                same_period_withholdings = abs(same_period_partner_withholdings[0][1])
            else:
                same_period_withholdings = 0.0
            domain_same_period_base = [
                *self.env['account.move.line']._check_company_domain(self.tax_id.company_id),
                ('parent_state', '=', 'posted'),
                ('tax_ids.l10n_ar_code', '=', self.tax_id.l10n_ar_code),
                ('tax_ids.l10n_ar_tax_type', 'in', ['earnings', 'earnings_scale']),
                ('partner_id', '=', self.payment_line_id.payment_id.partner_id.commercial_partner_id.id),
                ('date', '<=', to_date), ('date', '>=', from_date)]
            if same_period_partner_base := self.env['account.move.line']._read_group(domain_same_period_base, ['partner_id'], ['balance:sum']):
                same_period_base = abs(same_period_partner_base[0][1])
            else:
                same_period_base = 0.0
            net_amount = self.base_amount + same_period_base
        else:
            net_amount = self.base_amount
        net_amount = max(0, net_amount - self.tax_id.l10n_ar_non_taxable_amount)
        taxes_res = self.tax_id.compute_all(
            net_amount,
            currency=self.payment_line_id.currency_id,#correct as per current logic
            quantity=1.0,
            product=False,
            partner=False,
            is_refund=False,
        )
        tax_amount = taxes_res['taxes'][0]['amount']
        tax_account_id = taxes_res['taxes'][0]['account_id']
        tax_repartition_line_id = taxes_res['taxes'][0]['tax_repartition_line_id']

        if self.tax_id.l10n_ar_tax_type in ['earnings', 'earnings_scale']:
            # if it is earnings scale we calculate according to the scale.
            if self.tax_id.l10n_ar_tax_type == 'earnings_scale':
                escala = self.env['l10n_ar.earnings.scale.line'].search([
                    ('scale_id', '=', self.tax_id.l10n_ar_scale_id.id),
                    ('excess_amount', '<=', net_amount),
                    ('to_amount', '>', net_amount),
                ], limit=1)
                tax_amount = ((net_amount - escala.excess_amount) * escala.percentage / 100) + escala.fixed_amount
            # deduct withholdings from the same period
            tax_amount -= same_period_withholdings

        l10n_ar_minimum_threshold = self.tax_id.l10n_ar_minimum_threshold
        if l10n_ar_minimum_threshold > tax_amount:
            tax_amount = 0.0
        return tax_amount, tax_account_id, tax_repartition_line_id


    @api.depends('payment_line_id.amount', 'payment_line_id.payment_id.line_ids', 'tax_id')
    def _compute_base_amount(self):
        #print("\n _compute_base_amount()...Custom", self)
        for wth in self:
            #print("wth Line:", wth, "tax_id:", wth.tax_id)
            payment_line = wth.payment_line_id
            payment = payment_line.payment_id

            # Safety checks
            if not payment_line or not payment:
                wth.base_amount = 0.0
                continue

            if wth.tax_id.l10n_ar_tax_type == 'iibb_total':
                wth.base_amount = payment_line.amount
                continue

            # Compute totals safely
            #print("payment.line_ids:",payment.line_ids)
            #expect only one move line. it's a singleton.
            #total_amount = sum(payment.line_ids.mapped('move_id.amount_total'))
            amline = payment.line_ids.filtered(lambda aml: aml.move_id == payment_line.invoice_id)
            total_amount = amline.move_id.amount_total if amline else 0.0
            #print("total_amount:", total_amount)
            
            #untaxed_amount = sum(payment.line_ids.mapped('move_id.amount_untaxed'))
            untaxed_amount = amline.move_id.amount_untaxed if amline else 0.0
            #print("untaxed_amount:", untaxed_amount)

            # 🔴 CRITICAL FIX
            if not total_amount:
                wth.base_amount = 0.0
                continue

            # ✅ Safe division
            wth.base_amount = (
                payment_line.amount * untaxed_amount / total_amount
            )
            #total_amount 11,168,769.05      payment_line.amount 11,168,469.05
            #untaxed_amount 9,007,071.96        ?  9006830.02
            #print("wth.base_amount:", wth.base_amount ,"\n---")


    """@api.depends('payment_line_id.amount', 'payment_line_id.payment_id.line_ids', 'tax_id')
    def _compute_base_amount(self):
        for wth in self:
            if wth.tax_id.l10n_ar_tax_type == 'iibb_total':
                wth.base_amount = wth.payment_line_id.amount
            else:
                #wth.base_amount = wth.payment_line_id.amount * sum(wth.payment_line_id.payment_id.line_ids.mapped('move_id.amount_untaxed')) / sum(wth.payment_line_id.payment_id.line_ids.mapped('move_id.amount_total'))
                total = sum(wth.payment_line_id.payment_id.line_ids.mapped('move_id.amount_total'))
                if not total:
                    wth.base_amount = 0.0
                else:
                    wth.base_amount = (wth.payment_line_id.amount * sum(wth.payment_line_id.payment_id.line_ids.mapped('move_id.amount_untaxed')) / total)"""

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
