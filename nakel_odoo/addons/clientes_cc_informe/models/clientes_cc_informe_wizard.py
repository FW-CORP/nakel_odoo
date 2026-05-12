# -*- coding: utf-8 -*-

import csv
import io
from datetime import date, datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang
from odoo.tools.safe_eval import safe_eval

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class ClientesCcInformeWizard(models.TransientModel):
    _name = "clientes.cc.informe.wizard"
    _description = "Informe de cuentas corrientes clientes"
    _rec_name = "name"

    name = fields.Char(
        string="Título",
        required=True,
        default=lambda self: _("Informe de cuentas corrientes clientes"),
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Compañía",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="company_id.currency_id",
        readonly=True,
    )

    date_from = fields.Date(
        string="Fecha desde (factura)",
        help="Incluye documentos con fecha de factura a partir de esta fecha (inclusive). "
        "Vacío = sin límite inferior. Si está definida, el resumen puede mostrar además el "
        "«saldo inicial» como suma de saldos pendientes de FC/NC anteriores a esa fecha "
        "(mismos filtros de vendedor, cliente y diarios; no incluye pagos sueltos ni mayor "
        "contable completo).",
    )
    date_to = fields.Date(
        string="Fecha hasta (factura)",
        help="Incluye documentos con fecha de factura hasta esta fecha (inclusive). "
        "Vacío = sin límite superior.",
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Vendedor",
        domain=[("share", "=", False)],
        help="Comercial en cabecera de la factura (invoice_user_id). Vacío = todos.",
    )
    allowed_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="clientes_cc_informe_wiz_allowed_partner_rel",
        column1="wizard_id",
        column2="partner_id",
        string="Clientes permitidos (dominio)",
        compute="_compute_allowed_partner_ids",
        store=True,
        help="Técnico: acota el desplegable de cliente según el vendedor (o todas las "
        "entidades con FC/NC publicadas si no hay vendedor).",
    )
    commercial_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Cliente",
        help="Entidad comercial. Vacío = todos. Si hay vendedor, solo clientes con "
        "facturación publicada asociada a ese comercial.",
    )
    only_open = fields.Boolean(
        string="Solo con saldo pendiente",
        default=True,
        help="Excluye documentos totalmente pagados (estado de pago: pagado).",
    )
    filtro_pdv_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="PDV / diario de ventas",
        domain="[('company_id', '=', company_id), ('type', '=', 'sale')]",
        help="Elija el diario de facturación (p. ej. FACT NAKEL CENTRAL = PDV 50). "
        "Vacío = se incluyen todos los diarios de venta. Por defecto se propone el diario "
        "con PDV AFIP 50 si existe en la compañía. No replica el «Estado del cliente» de "
        "contabilidad (mayor con pagos y saldo inicial).",
    )
    include_migracion_deudores = fields.Boolean(
        string="Incluir diario migración de deudores",
        default=True,
        help="Si eligió un diario de ventas arriba, suele mantener también las FC del "
        "diario de migración (saldo arrastrado de la plataforma anterior). Desmarque para "
        "excluirlas.",
    )
    preview_move_ids = fields.Many2many(
        comodel_name="account.move",
        relation="clientes_cc_informe_wizard_account_move_rel",
        column1="wizard_id",
        column2="move_id",
        string="Vista previa",
        help="Documentos según filtros. Se actualiza al abrir, al guardar o al cambiar filtros.",
    )

    sum_total_signed = fields.Monetary(
        string="Total documentos",
        currency_field="currency_id",
        compute="_compute_summary",
        help="Suma de importes firmados (FC y NC) en la vista previa.",
    )
    sum_paid = fields.Monetary(
        string="Cobrado / aplicado (vista previa)",
        currency_field="currency_id",
        compute="_compute_summary",
        help="Suma de importes firmados menos suma de saldos pendientes de las filas "
        "mostradas (= aplicado sobre FC/NC listadas). Las NC de cliente suman importe "
        "firmado negativo; no incluye pagos sueltos ni saldo inicial del mayor.",
    )
    sum_residual = fields.Monetary(
        string="Adeudado (vista previa)",
        currency_field="currency_id",
        compute="_compute_summary",
        help="Suma de saldos pendientes de las facturas listadas abajo (rango de fechas "
        "según filtros).",
    )
    sum_opening_residual = fields.Monetary(
        string="Saldo inicial (FC/NC antes del «desde»)",
        currency_field="currency_id",
        compute="_compute_summary",
        help="Solo si hay «Fecha desde»: suma actual de amount_residual de FC/NC publicadas "
        "con fecha de factura anterior a ese día, con los mismos filtros de vendedor, "
        "cliente, PDV/migración y solo pendiente. No es el saldo inicial del mayor contable "
        "(no incluye asientos que no sean FC/NC de cliente).",
    )
    sum_residual_with_opening = fields.Monetary(
        string="Adeudado total (inicial + listado)",
        currency_field="currency_id",
        compute="_compute_summary",
        help="Saldo inicial más adeudado de las filas listadas. Si no hay «Fecha desde», "
        "coincide con el adeudado del listado.",
    )

    _FILTER_KEYS = frozenset(
        {
            "date_from",
            "date_to",
            "user_id",
            "commercial_partner_id",
            "only_open",
            "filtro_pdv_journal_id",
            "include_migracion_deudores",
        }
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        company = self.env.company
        cid = res.get("company_id")
        if isinstance(cid, (list, tuple)):
            company = self.env["res.company"].browse(cid[0])
        elif cid:
            company = self.env["res.company"].browse(cid)
        if "filtro_pdv_journal_id" in fields_list and not res.get("filtro_pdv_journal_id"):
            Journal = self.env["account.journal"]
            if "l10n_ar_afip_pos_number" in Journal._fields:
                j = Journal.search(
                    [
                        ("company_id", "=", company.id),
                        ("type", "=", "sale"),
                        ("l10n_ar_afip_pos_number", "=", 50),
                    ],
                    limit=1,
                    order="id",
                )
                if j:
                    res["filtro_pdv_journal_id"] = j.id
        return res

    def _domain_afip_journal_filter(self):
        """Lista de términos de dominio ``journal_id`` o vacía."""
        self.ensure_one()
        if not self.filtro_pdv_journal_id:
            return []
        Journal = self.env["account.journal"]
        jids = [self.filtro_pdv_journal_id.id]
        if self.include_migracion_deudores:
            mig = Journal.search(
                [
                    ("company_id", "=", self.company_id.id),
                    ("type", "=", "sale"),
                    "|",
                    ("name", "ilike", "migración"),
                    ("name", "ilike", "migracion"),
                ]
            )
            jids = list(set(jids + mig.ids))
        return [("journal_id", "in", jids)]

    @api.depends(
        "user_id",
        "company_id",
        "filtro_pdv_journal_id",
        "include_migracion_deudores",
    )
    def _compute_allowed_partner_ids(self):
        Move = self.env["account.move"]
        Partner = self.env["res.partner"]
        for wiz in self:
            base_move_domain = [
                ("move_type", "in", ("out_invoice", "out_refund")),
                ("state", "=", "posted"),
            ]
            if wiz.company_id:
                base_move_domain.append(("company_id", "=", wiz.company_id.id))
            afip_dom = wiz._domain_afip_journal_filter()
            if wiz.user_id:
                moves = Move.search(
                    base_move_domain
                    + [("invoice_user_id", "=", wiz.user_id.id)]
                    + afip_dom
                )
                pids = moves.mapped("commercial_partner_id").ids
                wiz.allowed_partner_ids = Partner.browse(pids)
            else:
                moves = Move.search(base_move_domain + afip_dom)
                pids = list({m.commercial_partner_id.id for m in moves if m.commercial_partner_id})
                wiz.allowed_partner_ids = Partner.browse(pids)

    @api.depends(
        "preview_move_ids",
        "preview_move_ids.amount_total_signed",
        "preview_move_ids.amount_residual",
        "date_from",
        "user_id",
        "commercial_partner_id",
        "only_open",
        "filtro_pdv_journal_id",
        "include_migracion_deudores",
        "company_id",
    )
    def _compute_summary(self):
        Move = self.env["account.move"]
        for wiz in self:
            moves = wiz.preview_move_ids
            total = sum(moves.mapped("amount_total_signed"))
            residual = sum(moves.mapped("amount_residual"))
            wiz.sum_total_signed = total
            wiz.sum_residual = residual
            wiz.sum_paid = total - residual
            opening = 0.0
            if wiz.date_from:
                dom = wiz._build_domain_opening_moves()
                opening = sum(Move.search(dom).mapped("amount_residual"))
            wiz.sum_opening_residual = opening
            wiz.sum_residual_with_opening = opening + residual

    def _build_domain_opening_moves(self, commercial_partner_id=None):
        """Dominio FC/NC con fecha de factura estrictamente anterior a ``date_from``."""
        self.ensure_one()
        if not self.date_from:
            return [("id", "=", 0)]
        domain = [
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("invoice_date", "<", self.date_from),
        ]
        if commercial_partner_id is not None:
            domain.append(("commercial_partner_id", "=", commercial_partner_id))
        elif self.commercial_partner_id:
            domain.append(("commercial_partner_id", "=", self.commercial_partner_id.id))
        if self.user_id:
            domain.append(("invoice_user_id", "=", self.user_id.id))
        if self.only_open:
            domain.append(("payment_state", "in", ("not_paid", "partial")))
        domain.extend(self._domain_afip_journal_filter())
        if self.company_id:
            domain.append(("company_id", "=", self.company_id.id))
        return domain

    def _search_opening_moves(self, commercial_partner_id=None):
        self.ensure_one()
        if not self.date_from:
            return self.env["account.move"]
        return self.env["account.move"].search(
            self._build_domain_opening_moves(commercial_partner_id=commercial_partner_id),
            order="invoice_date desc, name desc",
        )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault(
                "name",
                self.env._("Informe de cuentas corrientes clientes"),
            )
        records = super().create(vals_list)
        records._refresh_preview()
        return records

    def _commercial_partner_ids_for_vendor(self, user):
        """Clientes (entidad comercial) con facturación publicada asociada al vendedor."""
        if not user:
            return []
        domain = [
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("invoice_user_id", "=", user.id),
        ]
        if self.company_id:
            domain.append(("company_id", "=", self.company_id.id))
        domain.extend(self._domain_afip_journal_filter())
        moves = self.env["account.move"].search(domain)
        return moves.mapped("commercial_partner_id").ids

    def _build_domain(self):
        self.ensure_one()
        domain = [
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
        ]
        if self.date_from:
            domain.append(("invoice_date", ">=", self.date_from))
        if self.date_to:
            domain.append(("invoice_date", "<=", self.date_to))
        if self.user_id:
            domain.append(("invoice_user_id", "=", self.user_id.id))
        if self.commercial_partner_id:
            domain.append(("commercial_partner_id", "=", self.commercial_partner_id.id))
        if self.only_open:
            domain.append(("payment_state", "in", ("not_paid", "partial")))
        domain.extend(self._domain_afip_journal_filter())
        return domain

    def _search_moves(self):
        self.ensure_one()
        return self.env["account.move"].search(
            self._build_domain(),
            order="invoice_user_id, commercial_partner_id, invoice_date desc, name desc",
        )

    def _refresh_preview(self):
        for rec in self:
            rec.preview_move_ids = rec._search_moves()

    def _get_moves(self):
        """Informe PDF: mismo dominio que los filtros actuales."""
        self.ensure_one()
        return self._search_moves()

    def format_currency_amount(self, amount):
        """Formato moneda compañía para QWeb (resúmenes del PDF)."""
        self.ensure_one()
        from odoo.tools.misc import formatLang

        return formatLang(
            self.env,
            amount,
            currency_obj=self.company_id.currency_id,
        )

    def _pdf_global_from_moves(self, moves):
        """Totales globales (mismo criterio que el PDF) a partir de un recordset."""
        if not moves:
            base = {
                "partner_count": 0,
                "document_count": 0,
                "sum_total_signed": 0.0,
                "sum_residual": 0.0,
            }
        else:
            partner_ids = {m.commercial_partner_id.id for m in moves if m.commercial_partner_id}
            base = {
                "partner_count": len(partner_ids),
                "document_count": len(moves),
                "sum_total_signed": sum(moves.mapped("amount_total_signed")),
                "sum_residual": sum(moves.mapped("amount_residual")),
            }
        base["sum_opening_residual"] = self.sum_opening_residual
        base["sum_residual_with_opening"] = self.sum_residual_with_opening
        base["has_opening"] = bool(self.date_from)
        return base

    def _pdf_sections_from_moves(self, moves):
        """Bloques por cliente, mayor saldo primero (mismo orden que el PDF)."""
        if not moves:
            return []
        mapping = {}
        for m in moves:
            pid = m.commercial_partner_id.id or 0
            mapping.setdefault(pid, self.env["account.move"])
            mapping[pid] |= m
        sections = []
        for pid, pmoves in mapping.items():
            partner = (
                self.env["res.partner"].browse(pid) if pid else self.env["res.partner"]
            )
            pmoves = pmoves.sorted(
                key=lambda mm: (mm.invoice_date or date.min, mm.name or ""),
                reverse=True,
            )
            sum_res = sum(pmoves.mapped("amount_residual"))
            sum_open = 0.0
            if self.date_from and pid:
                sum_open = sum(
                    self._search_opening_moves(commercial_partner_id=pid).mapped(
                        "amount_residual"
                    )
                )
            sections.append(
                {
                    "partner": partner,
                    "partner_label": partner.display_name
                    if partner
                    else _("Sin entidad comercial"),
                    "moves": pmoves,
                    "count": len(pmoves),
                    "sum_total_signed": sum(pmoves.mapped("amount_total_signed")),
                    "sum_residual": sum_res,
                    "sum_opening_residual": sum_open,
                    "sum_residual_with_opening": sum_open + sum_res,
                }
            )
        sections.sort(key=lambda s: -s["sum_residual_with_opening"])
        return sections

    def _get_report_pdf_global(self):
        """Totales globales del PDF (todos los movimientos del informe)."""
        self.ensure_one()
        return self._pdf_global_from_moves(self._get_moves())

    def _get_report_pdf_sections(self):
        """Lista de dicts por cliente: partner, moves, totales (PDF agrupado)."""
        self.ensure_one()
        return self._pdf_sections_from_moves(self._get_moves())

    def write(self, vals):
        res = super().write(vals)
        if self._FILTER_KEYS & vals.keys():
            self._refresh_preview()
        return res

    @api.onchange(
        "date_from",
        "date_to",
        "user_id",
        "only_open",
        "commercial_partner_id",
        "filtro_pdv_journal_id",
        "include_migracion_deudores",
    )
    def _onchange_filters_refresh_preview(self):
        if self.user_id:
            pids = self._commercial_partner_ids_for_vendor(self.user_id)
            if self.commercial_partner_id and self.commercial_partner_id.id not in pids:
                self.commercial_partner_id = False
        moves = self._search_moves()
        self.preview_move_ids = moves

    def action_refresh_preview(self):
        self._refresh_preview()
        return False

    def action_open_list(self):
        self.ensure_one()
        action = dict(
            self.env["ir.actions.actions"]._for_xml_id(
                "clientes_cc_informe.action_act_window_clientes_cc_gerencia"
            )
        )
        ctx = dict(self.env.context)
        raw = action.get("context")
        if isinstance(raw, str):
            ctx.update(
                safe_eval(
                    raw,
                    {
                        "context": ctx,
                        "uid": self.env.uid,
                        "allowed_company_ids": self.env.context.get(
                            "allowed_company_ids", [self.env.company.id]
                        ),
                    },
                )
            )
        elif isinstance(raw, dict):
            ctx.update(raw)
        ctx["search_default_posted"] = 1
        action["context"] = ctx
        action["domain"] = self._build_domain()
        return action

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref(
            "clientes_cc_informe.action_report_clientes_cc_informe"
        ).report_action(self)

    def _selection_dict(self, model_name, field_name):
        Model = self.env[model_name]
        field = Model._fields[field_name]
        sel = field.selection
        if callable(sel):
            sel = sel(Model)
        return dict(sel)

    def _build_export_rows(self, moves):
        """Lista de filas para CSV/XLSX (valores escalares)."""
        rows = []
        selection_pay = self._selection_dict("account.move", "payment_state")
        selection_move = self._selection_dict("account.move", "move_type")
        for m in moves:
            rows.append(
                {
                    "documento": m.name or "",
                    "fecha": m.invoice_date or "",
                    "vendedor": m.invoice_user_id.name or "",
                    "cliente": m.commercial_partner_id.display_name or "",
                    "tipo": selection_move.get(m.move_type, m.move_type),
                    "total_firmado": m.amount_total_signed,
                    "saldo": m.amount_residual,
                    "estado_pago": selection_pay.get(m.payment_state, m.payment_state),
                }
            )
        return rows

    def _export_xlsx_meta_lines(self):
        """Textos de cabecera del Excel (filtros del informe)."""
        self.ensure_one()
        if self.date_from and self.date_to:
            rango = _("%(desde)s a %(hasta)s") % {
                "desde": self.date_from,
                "hasta": self.date_to,
            }
        elif self.date_from:
            rango = _("Desde %s") % self.date_from
        elif self.date_to:
            rango = _("Hasta %s") % self.date_to
        else:
            rango = _("Sin filtro por fecha")
        vendedor = self.user_id.name if self.user_id else _("Todos")
        cliente = (
            self.commercial_partner_id.display_name
            if self.commercial_partner_id
            else _("Todos (según filtros)")
        )
        pendiente = _("Sí") if self.only_open else _("No (incluye pagados)")
        comp = self.company_id.name or ""
        if self.filtro_pdv_journal_id:
            pos = ""
            if "l10n_ar_afip_pos_number" in self.env["account.journal"]._fields:
                pos = self.filtro_pdv_journal_id.l10n_ar_afip_pos_number
            pos_txt = (" (AFIP %s)" % pos) if pos not in (False, None) else ""
            pdv_txt = _("%(journal)s%(pos)s — incl. migración: %(m)s") % {
                "journal": self.filtro_pdv_journal_id.display_name,
                "pos": pos_txt,
                "m": _("Sí") if self.include_migracion_deudores else _("No"),
            }
        else:
            pdv_txt = _("Todos los diarios de venta (sin filtro por PDV)")
        lines = [
            (_("Compañía"), comp),
            (_("Rango fechas (factura)"), rango),
            (_("Vendedor (filtro)"), vendedor),
            (_("Cliente (filtro)"), cliente),
            (_("Solo saldo pendiente"), pendiente),
            (_("Filtro PDV / diario"), pdv_txt),
        ]
        if self.date_from:
            lines.append(
                (
                    _("Saldo inicial (FC/NC con factura anterior al «desde»)"),
                    formatLang(
                        self.env,
                        self.sum_opening_residual,
                        currency_obj=self.company_id.currency_id,
                    ),
                )
            )
            lines.append(
                (
                    _("Adeudado total (inicial + facturas en el rango listadas)"),
                    formatLang(
                        self.env,
                        self.sum_residual_with_opening,
                        currency_obj=self.company_id.currency_id,
                    ),
                )
            )
        return lines

    def _export_xlsx_build_formats(self, wb):
        """Formatos compartidos (layout tipo PDF + hoja plana)."""
        return {
            "fmt_title": wb.add_format(
                {"bold": True, "font_size": 14, "valign": "vcenter", "bottom": 2}
            ),
            "fmt_meta_key": wb.add_format({"bold": True}),
            "fmt_meta_val": wb.add_format({}),
            "fmt_global_box": wb.add_format(
                {
                    "text_wrap": True,
                    "valign": "vcenter",
                    "border": 1,
                    "bg_color": "#F8F9FA",
                    "font_size": 10,
                }
            ),
            "fmt_header": wb.add_format(
                {
                    "bold": True,
                    "bg_color": "#4A4A4A",
                    "font_color": "#FFFFFF",
                    "border": 1,
                    "text_wrap": True,
                    "valign": "vcenter",
                }
            ),
            "fmt_text": wb.add_format({"border": 1, "valign": "vcenter"}),
            "fmt_date": wb.add_format(
                {"border": 1, "num_format": "dd/mm/yyyy", "valign": "vcenter"}
            ),
            "fmt_money": wb.add_format(
                {"border": 1, "num_format": "#,##0.00", "valign": "vcenter"}
            ),
            "fmt_section": wb.add_format(
                {"bold": True, "font_size": 11, "top": 1, "valign": "vcenter"}
            ),
            "fmt_tot_label": wb.add_format({"bold": True, "valign": "vcenter"}),
            "fmt_tot_num": wb.add_format(
                {
                    "bold": True,
                    "num_format": "#,##0.00",
                    "bg_color": "#E8E8E8",
                    "border": 1,
                    "valign": "vcenter",
                }
            ),
            "fmt_tot_int": wb.add_format(
                {
                    "bold": True,
                    "num_format": "0",
                    "bg_color": "#E8E8E8",
                    "border": 1,
                    "valign": "vcenter",
                }
            ),
            "fmt_group_title": wb.add_format(
                {
                    "bold": True,
                    "font_size": 11,
                    "bg_color": "#714B67",
                    "font_color": "#FFFFFF",
                    "valign": "vcenter",
                    "border": 1,
                }
            ),
            "fmt_subbar": wb.add_format(
                {
                    "italic": True,
                    "bg_color": "#F0EBF0",
                    "border": 1,
                    "valign": "vcenter",
                }
            ),
        }

    def _export_xlsx_headers_pdf_table(self, hide_vendor):
        """Cabeceras de tabla alineadas al PDF (última columna «Cobro» = estado de pago)."""
        if hide_vendor:
            return [
                _("Documento"),
                _("Fecha"),
                _("Tipo"),
                _("Total"),
                _("Saldo"),
                _("Cobro"),
            ]
        return [
            _("Documento"),
            _("Fecha"),
            _("Vendedor"),
            _("Tipo"),
            _("Total"),
            _("Saldo"),
            _("Cobro"),
        ]

    def _export_xlsx_write_sheet_pdf_layout(self, ws, moves, hide_vendor, fmts):
        """Primera hoja: mismo orden y bloques que el PDF (resumen global + cliente)."""
        self.ensure_one()
        cur = fmts
        headers = self._export_xlsx_headers_pdf_table(hide_vendor)
        last_col = len(headers) - 1
        row = 0
        ws.merge_range(
            row, 0, row, last_col, _("Informe — cuentas corrientes clientes"), cur["fmt_title"]
        )
        row += 1
        for key, val in self._export_xlsx_meta_lines():
            ws.write(row, 0, key, cur["fmt_meta_key"])
            ws.merge_range(row, 1, row, last_col, val, cur["fmt_meta_val"])
            row += 1
        row += 1

        g = self._pdf_global_from_moves(moves)
        currency = self.company_id.currency_id
        if g.get("has_opening"):
            resumen_txt = _(
                "Clientes con movimientos: %(pc)s — Documentos: %(dc)s — "
                "Total importes (firmado): %(tf)s — Adeudado (solo facturas en el rango): %(sr)s — "
                "Saldo inicial (FC/NC anteriores al «desde»): %(so)s — Adeudado total: %(st)s"
            ) % {
                "pc": g["partner_count"],
                "dc": g["document_count"],
                "tf": formatLang(self.env, g["sum_total_signed"], currency_obj=currency),
                "sr": formatLang(self.env, g["sum_residual"], currency_obj=currency),
                "so": formatLang(self.env, g["sum_opening_residual"], currency_obj=currency),
                "st": formatLang(
                    self.env, g["sum_residual_with_opening"], currency_obj=currency
                ),
            }
        else:
            resumen_txt = _(
                "Clientes con movimientos: %(pc)s — Documentos: %(dc)s — "
                "Total importes (firmado): %(tf)s — Saldo pendiente total: %(sr)s"
            ) % {
                "pc": g["partner_count"],
                "dc": g["document_count"],
                "tf": formatLang(self.env, g["sum_total_signed"], currency_obj=currency),
                "sr": formatLang(self.env, g["sum_residual"], currency_obj=currency),
            }
        ws.merge_range(row, 0, row, last_col, resumen_txt, cur["fmt_global_box"])
        row += 1
        row += 1

        selection_pay = self._selection_dict("account.move", "payment_state")
        selection_move = self._selection_dict("account.move", "move_type")
        sections = self._pdf_sections_from_moves(moves)

        for sec in sections:
            ws.merge_range(
                row, 0, row, last_col, sec["partner_label"], cur["fmt_group_title"]
            )
            row += 1
            if self.date_from:
                bloque_txt = _(
                    "%(n)s documento(s) — Total firmado: %(tf)s — Adeudado (en el rango): %(sr)s — "
                    "Saldo inicial (antes del «desde»): %(so)s — Adeudado total: %(tt)s"
                ) % {
                    "n": sec["count"],
                    "tf": formatLang(
                        self.env, sec["sum_total_signed"], currency_obj=currency
                    ),
                    "sr": formatLang(self.env, sec["sum_residual"], currency_obj=currency),
                    "so": formatLang(
                        self.env, sec["sum_opening_residual"], currency_obj=currency
                    ),
                    "tt": formatLang(
                        self.env,
                        sec["sum_residual_with_opening"],
                        currency_obj=currency,
                    ),
                }
            else:
                bloque_txt = _(
                    "%(n)s documento(s) — Total firmado: %(tf)s — Saldo del cliente "
                    "(en este informe): %(sr)s"
                ) % {
                    "n": sec["count"],
                    "tf": formatLang(
                        self.env, sec["sum_total_signed"], currency_obj=currency
                    ),
                    "sr": formatLang(self.env, sec["sum_residual"], currency_obj=currency),
                }
            ws.merge_range(row, 0, row, last_col, bloque_txt, cur["fmt_subbar"])
            row += 1
            header_row = row
            for col, h in enumerate(headers):
                ws.write(header_row, col, h, cur["fmt_header"])
            row = header_row + 1
            for m in sec["moves"]:
                ws.write(row, 0, m.name or "", cur["fmt_text"])
                if m.invoice_date:
                    ws.write_datetime(
                        row,
                        1,
                        datetime.combine(m.invoice_date, datetime.min.time()),
                        cur["fmt_date"],
                    )
                else:
                    ws.write(row, 1, "", cur["fmt_text"])
                c = 2
                if not hide_vendor:
                    ws.write(row, c, m.invoice_user_id.name or "", cur["fmt_text"])
                    c += 1
                ws.write(
                    row,
                    c,
                    selection_move.get(m.move_type, m.move_type),
                    cur["fmt_text"],
                )
                c += 1
                ws.write_number(row, c, float(m.amount_total_signed), cur["fmt_money"])
                c += 1
                ws.write_number(row, c, float(m.amount_residual), cur["fmt_money"])
                c += 1
                ws.write(
                    row,
                    c,
                    selection_pay.get(m.payment_state, m.payment_state),
                    cur["fmt_text"],
                )
                row += 1
            row += 1

        total_firmado = sum(moves.mapped("amount_total_signed"))
        total_saldo = sum(moves.mapped("amount_residual"))
        n_docs = len(moves)
        row += 1
        ws.merge_range(row, 0, row, last_col, _("Resumen (totales del informe)"), cur["fmt_section"])
        row += 1
        if self.date_from:
            ws.write(row, 0, _("SALDO INICIAL (FC/NC antes del «desde»)"), cur["fmt_tot_label"])
            ws.write_number(row, 1, float(self.sum_opening_residual), cur["fmt_tot_num"])
            row += 1
        ws.write(row, 0, _("TOTAL FIRMADO (documentos listados)"), cur["fmt_tot_label"])
        ws.write_number(row, 1, float(total_firmado), cur["fmt_tot_num"])
        row += 1
        ws.write(row, 0, _("ADEUDADO (solo documentos listados)"), cur["fmt_tot_label"])
        ws.write_number(row, 1, float(total_saldo), cur["fmt_tot_num"])
        row += 1
        if self.date_from:
            ws.write(row, 0, _("ADEUDADO TOTAL (inicial + listado)"), cur["fmt_tot_label"])
            ws.write_number(row, 1, float(self.sum_residual_with_opening), cur["fmt_tot_num"])
            row += 1
        ws.write(row, 0, _("Cantidad de comprobantes (FC / NC)"), cur["fmt_tot_label"])
        ws.write_number(row, 1, n_docs, cur["fmt_tot_int"])

        ws.set_column(0, 0, 22)
        ws.set_column(1, 1, 12)
        if not hide_vendor:
            ws.set_column(2, 2, 22)
            ws.set_column(3, 3, 28)
            ws.set_column(4, 5, 16)
            ws.set_column(6, 6, 22)
        else:
            ws.set_column(2, 2, 28)
            ws.set_column(3, 4, 16)
            ws.set_column(5, 5, 22)

    def _export_xlsx_write_sheet_flat(self, ws, moves, hide_vendor, fmts):
        """Segunda hoja: tabla plana (para pivot / análisis), columnas alineadas al PDF."""
        self.ensure_one()
        cur = fmts
        rows = self._build_export_rows(moves)
        total_firmado = sum(moves.mapped("amount_total_signed"))
        total_saldo = sum(moves.mapped("amount_residual"))
        n_docs = len(moves)
        if hide_vendor:
            headers = [
                _("Documento"),
                _("Fecha"),
                _("Cliente"),
                _("Tipo"),
                _("Total firmado"),
                _("Saldo"),
                _("Cobro"),
            ]
        else:
            headers = [
                _("Documento"),
                _("Fecha"),
                _("Vendedor"),
                _("Cliente"),
                _("Tipo"),
                _("Total firmado"),
                _("Saldo"),
                _("Cobro"),
            ]
        last_col = len(headers) - 1
        row = 0
        ws.merge_range(
            row, 0, row, last_col, _("Detalle plano (tabla única)"), cur["fmt_title"]
        )
        row += 1
        for key, val in self._export_xlsx_meta_lines():
            ws.write(row, 0, key, cur["fmt_meta_key"])
            ws.merge_range(row, 1, row, last_col, val, cur["fmt_meta_val"])
            row += 1
        row += 1
        header_row = row
        for col, h in enumerate(headers):
            ws.write(header_row, col, h, cur["fmt_header"])
        row = header_row + 1
        for r in rows:
            ws.write(row, 0, r["documento"], cur["fmt_text"])
            fd = r["fecha"]
            if isinstance(fd, date):
                ws.write_datetime(
                    row,
                    1,
                    datetime.combine(fd, datetime.min.time()),
                    cur["fmt_date"],
                )
            else:
                ws.write(row, 1, str(fd or ""), cur["fmt_text"])
            c = 2
            if not hide_vendor:
                ws.write(row, c, r["vendedor"], cur["fmt_text"])
                c += 1
            ws.write(row, c, r["cliente"], cur["fmt_text"])
            c += 1
            ws.write(row, c, r["tipo"], cur["fmt_text"])
            c += 1
            ws.write_number(row, c, float(r["total_firmado"]), cur["fmt_money"])
            c += 1
            ws.write_number(row, c, float(r["saldo"]), cur["fmt_money"])
            c += 1
            ws.write(row, c, r["estado_pago"], cur["fmt_text"])
            row += 1
        row += 1
        ws.merge_range(row, 0, row, last_col, _("Resumen (totales del informe)"), cur["fmt_section"])
        row += 1
        if self.date_from:
            ws.write(row, 0, _("SALDO INICIAL (FC/NC antes del «desde»)"), cur["fmt_tot_label"])
            ws.write_number(row, 1, float(self.sum_opening_residual), cur["fmt_tot_num"])
            row += 1
        ws.write(row, 0, _("TOTAL FIRMADO (documentos listados)"), cur["fmt_tot_label"])
        ws.write_number(row, 1, float(total_firmado), cur["fmt_tot_num"])
        row += 1
        ws.write(row, 0, _("ADEUDADO (solo documentos listados)"), cur["fmt_tot_label"])
        ws.write_number(row, 1, float(total_saldo), cur["fmt_tot_num"])
        row += 1
        if self.date_from:
            ws.write(row, 0, _("ADEUDADO TOTAL (inicial + listado)"), cur["fmt_tot_label"])
            ws.write_number(row, 1, float(self.sum_residual_with_opening), cur["fmt_tot_num"])
            row += 1
        ws.write(row, 0, _("Cantidad de comprobantes (FC / NC)"), cur["fmt_tot_label"])
        ws.write_number(row, 1, n_docs, cur["fmt_tot_int"])
        ws.set_column(0, 0, 22)
        ws.set_column(1, 1, 12)
        if not hide_vendor:
            ws.set_column(2, 2, 22)
            ws.set_column(3, 3, 36)
            ws.set_column(4, 4, 28)
            ws.set_column(5, 6, 16)
            ws.set_column(7, 7, 22)
        else:
            ws.set_column(2, 2, 38)
            ws.set_column(3, 3, 28)
            ws.set_column(4, 5, 16)
            ws.set_column(6, 6, 22)
        ws.freeze_panes(header_row + 1, 0)

    def _export_xlsx_bytes(self, moves):
        """Hoja 1 = layout PDF; hoja 2 = tabla plana para Excel."""
        self.ensure_one()
        hide_vendor = bool(self.user_id)
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {"in_memory": True})
        fmts = self._export_xlsx_build_formats(wb)
        ws1 = wb.add_worksheet(_("Informe (PDF)")[:31])
        self._export_xlsx_write_sheet_pdf_layout(ws1, moves, hide_vendor, fmts)
        ws2 = wb.add_worksheet(_("Detalle plano")[:31])
        self._export_xlsx_write_sheet_flat(ws2, moves, hide_vendor, fmts)
        wb.close()
        return buf.getvalue()

    def _export_csv_bytes(self, moves):
        self.ensure_one()
        rows = self._build_export_rows(moves)
        total_firmado = sum(moves.mapped("amount_total_signed"))
        total_saldo = sum(moves.mapped("amount_residual"))
        n_docs = len(moves)
        hide_vendor = bool(self.user_id)

        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=";", lineterminator="\n")
        writer.writerow([_("Informe — cuentas corrientes clientes")])
        for key, val in self._export_xlsx_meta_lines():
            writer.writerow([key, val])
        writer.writerow([])
        g = self._pdf_global_from_moves(moves)
        currency = self.company_id.currency_id
        if g.get("has_opening"):
            resumen_csv = _(
                "Clientes con movimientos: %(pc)s — Documentos: %(dc)s — "
                "Total importes (firmado): %(tf)s — Adeudado listado: %(sr)s — "
                "Saldo inicial (FC/NC antes del «desde»): %(so)s — Adeudado total: %(st)s"
            ) % {
                "pc": g["partner_count"],
                "dc": g["document_count"],
                "tf": formatLang(self.env, g["sum_total_signed"], currency_obj=currency),
                "sr": formatLang(self.env, g["sum_residual"], currency_obj=currency),
                "so": formatLang(self.env, g["sum_opening_residual"], currency_obj=currency),
                "st": formatLang(
                    self.env, g["sum_residual_with_opening"], currency_obj=currency
                ),
            }
        else:
            resumen_csv = _(
                "Clientes con movimientos: %(pc)s — Documentos: %(dc)s — "
                "Total importes (firmado): %(tf)s — Saldo pendiente total: %(sr)s"
            ) % {
                "pc": g["partner_count"],
                "dc": g["document_count"],
                "tf": formatLang(self.env, g["sum_total_signed"], currency_obj=currency),
                "sr": formatLang(self.env, g["sum_residual"], currency_obj=currency),
            }
        writer.writerow([_("Resumen general"), resumen_csv])
        writer.writerow([])
        if hide_vendor:
            writer.writerow(
                [
                    _("Documento"),
                    _("Fecha"),
                    _("Cliente"),
                    _("Tipo"),
                    _("Total firmado"),
                    _("Saldo"),
                    _("Cobro"),
                ]
            )
        else:
            writer.writerow(
                [
                    _("Documento"),
                    _("Fecha"),
                    _("Vendedor"),
                    _("Cliente"),
                    _("Tipo"),
                    _("Total firmado"),
                    _("Saldo"),
                    _("Cobro"),
                ]
            )
        for r in rows:
            fd = r["fecha"]
            fd_s = fd.strftime("%d/%m/%Y") if isinstance(fd, date) else str(fd or "")
            if hide_vendor:
                writer.writerow(
                    [
                        r["documento"],
                        fd_s,
                        r["cliente"],
                        r["tipo"],
                        f"{r['total_firmado']:.2f}".replace(".", ","),
                        f"{r['saldo']:.2f}".replace(".", ","),
                        r["estado_pago"],
                    ]
                )
            else:
                writer.writerow(
                    [
                        r["documento"],
                        fd_s,
                        r["vendedor"],
                        r["cliente"],
                        r["tipo"],
                        f"{r['total_firmado']:.2f}".replace(".", ","),
                        f"{r['saldo']:.2f}".replace(".", ","),
                        r["estado_pago"],
                    ]
                )
        writer.writerow([])
        if self.date_from:
            writer.writerow(
                [
                    _("SALDO INICIAL (FC/NC antes del «desde»)"),
                    f"{self.sum_opening_residual:.2f}".replace(".", ","),
                ]
            )
        writer.writerow(
            [_("TOTAL FIRMADO (documentos listados)"), f"{total_firmado:.2f}".replace(".", ",")]
        )
        writer.writerow(
            [
                _("ADEUDADO (solo documentos listados)"),
                f"{total_saldo:.2f}".replace(".", ","),
            ]
        )
        if self.date_from:
            writer.writerow(
                [
                    _("ADEUDADO TOTAL (inicial + listado)"),
                    f"{self.sum_residual_with_opening:.2f}".replace(".", ","),
                ]
            )
        writer.writerow([_("Cantidad de comprobantes"), str(n_docs)])
        return buf.getvalue().encode("utf-8-sig")

    def action_export_excel(self):
        self.ensure_one()
        moves = self._search_moves()
        opening = self.sum_opening_residual
        if not moves and not (self.date_from and opening):
            raise UserError(_("No hay documentos para exportar con los filtros actuales."))
        if xlsxwriter:
            content = self._export_xlsx_bytes(moves)
            filename = "informe_cc_clientes.xlsx"
            mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            content = self._export_csv_bytes(moves)
            filename = "informe_cc_clientes.csv"
            mimetype = "text/csv; charset=utf-8"
        attachment = self.env["ir.attachment"].create(
            {
                "name": filename,
                "type": "binary",
                "raw": content,
                "mimetype": mimetype,
                "res_model": self._name,
                "res_id": self.id,
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "new",
        }
