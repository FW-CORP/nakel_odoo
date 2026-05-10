# -*- coding: utf-8 -*-

import csv
import io
from datetime import date, datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError
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
        "Vacío = sin límite inferior.",
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
        help="Total firmado menos saldo pendiente, por documento (moneda de la compañía).",
    )
    sum_residual = fields.Monetary(
        string="Adeudado (vista previa)",
        currency_field="currency_id",
        compute="_compute_summary",
    )

    _FILTER_KEYS = frozenset(
        {
            "date_from",
            "date_to",
            "user_id",
            "commercial_partner_id",
            "only_open",
        }
    )

    @api.depends("user_id", "company_id")
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
            if wiz.user_id:
                moves = Move.search(
                    base_move_domain + [("invoice_user_id", "=", wiz.user_id.id)]
                )
                pids = moves.mapped("commercial_partner_id").ids
                wiz.allowed_partner_ids = Partner.browse(pids)
            else:
                moves = Move.search(base_move_domain)
                pids = list({m.commercial_partner_id.id for m in moves if m.commercial_partner_id})
                wiz.allowed_partner_ids = Partner.browse(pids)

    @api.depends("preview_move_ids", "preview_move_ids.amount_total_signed", "preview_move_ids.amount_residual")
    def _compute_summary(self):
        for wiz in self:
            moves = wiz.preview_move_ids
            total = sum(moves.mapped("amount_total_signed"))
            residual = sum(moves.mapped("amount_residual"))
            wiz.sum_total_signed = total
            wiz.sum_residual = residual
            wiz.sum_paid = total - residual

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

    def _get_report_pdf_global(self):
        """Totales globales del PDF (todos los movimientos del informe)."""
        self.ensure_one()
        moves = self._get_moves()
        if not moves:
            return {
                "partner_count": 0,
                "document_count": 0,
                "sum_total_signed": 0.0,
                "sum_residual": 0.0,
            }
        partner_ids = {m.commercial_partner_id.id for m in moves if m.commercial_partner_id}
        return {
            "partner_count": len(partner_ids),
            "document_count": len(moves),
            "sum_total_signed": sum(moves.mapped("amount_total_signed")),
            "sum_residual": sum(moves.mapped("amount_residual")),
        }

    def _get_report_pdf_sections(self):
        """Lista de dicts por cliente: partner, moves, totales (PDF agrupado)."""
        self.ensure_one()
        moves = self._get_moves()
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
            sections.append(
                {
                    "partner": partner,
                    "partner_label": partner.display_name
                    if partner
                    else _("Sin entidad comercial"),
                    "moves": pmoves,
                    "count": len(pmoves),
                    "sum_total_signed": sum(pmoves.mapped("amount_total_signed")),
                    "sum_residual": sum(pmoves.mapped("amount_residual")),
                }
            )
        sections.sort(key=lambda s: -s["sum_residual"])
        return sections

    def write(self, vals):
        res = super().write(vals)
        if self._FILTER_KEYS & vals.keys():
            self._refresh_preview()
        return res

    @api.onchange("date_from", "date_to", "user_id", "only_open", "commercial_partner_id")
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
        return [
            (_("Compañía"), comp),
            (_("Rango fechas (factura)"), rango),
            (_("Vendedor (filtro)"), vendedor),
            (_("Cliente (filtro)"), cliente),
            (_("Solo saldo pendiente"), pendiente),
        ]

    def _export_xlsx_bytes(self, moves):
        self.ensure_one()
        rows = self._build_export_rows(moves)
        total_firmado = sum(moves.mapped("amount_total_signed"))
        total_saldo = sum(moves.mapped("amount_residual"))
        n_docs = len(moves)
        hide_vendor = bool(self.user_id)

        if hide_vendor:
            headers = [
                _("Documento"),
                _("Fecha"),
                _("Cliente"),
                _("Tipo"),
                _("Total firmado"),
                _("Saldo"),
                _("Estado pago"),
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
                _("Estado pago"),
            ]
        last_col = len(headers) - 1

        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {"in_memory": True})

        fmt_title = wb.add_format(
            {"bold": True, "font_size": 14, "valign": "vcenter", "bottom": 2}
        )
        fmt_meta_key = wb.add_format({"bold": True})
        fmt_meta_val = wb.add_format({})
        fmt_header = wb.add_format(
            {
                "bold": True,
                "bg_color": "#4A4A4A",
                "font_color": "#FFFFFF",
                "border": 1,
                "text_wrap": True,
                "valign": "vcenter",
            }
        )
        fmt_text = wb.add_format({"border": 1, "valign": "vcenter"})
        fmt_date = wb.add_format({"border": 1, "num_format": "dd/mm/yyyy", "valign": "vcenter"})
        fmt_money = wb.add_format({"border": 1, "num_format": "#,##0.00", "valign": "vcenter"})
        fmt_section = wb.add_format({"bold": True, "font_size": 11, "top": 1, "valign": "vcenter"})
        fmt_tot_label = wb.add_format({"bold": True, "valign": "vcenter"})
        fmt_tot_num = wb.add_format(
            {
                "bold": True,
                "num_format": "#,##0.00",
                "bg_color": "#E8E8E8",
                "border": 1,
                "valign": "vcenter",
            }
        )
        fmt_tot_int = wb.add_format(
            {
                "bold": True,
                "num_format": "0",
                "bg_color": "#E8E8E8",
                "border": 1,
                "valign": "vcenter",
            }
        )
        fmt_group_title = wb.add_format(
            {
                "bold": True,
                "font_size": 11,
                "bg_color": "#714B67",
                "font_color": "#FFFFFF",
                "valign": "vcenter",
                "border": 1,
            }
        )
        fmt_subbar = wb.add_format(
            {
                "italic": True,
                "bg_color": "#F0EBF0",
                "border": 1,
                "valign": "vcenter",
            }
        )

        ws = wb.add_worksheet(_("Detalle")[:31])

        row = 0
        ws.merge_range(row, 0, row, last_col, _("Informe — cuentas corrientes clientes"), fmt_title)
        row += 1
        for key, val in self._export_xlsx_meta_lines():
            ws.write(row, 0, key, fmt_meta_key)
            ws.merge_range(row, 1, row, last_col, val, fmt_meta_val)
            row += 1
        row += 1

        header_row = row
        for col, h in enumerate(headers):
            ws.write(header_row, col, h, fmt_header)
        row = header_row + 1

        for r in rows:
            ws.write(row, 0, r["documento"], fmt_text)
            fd = r["fecha"]
            if isinstance(fd, date):
                ws.write_datetime(
                    row,
                    1,
                    datetime.combine(fd, datetime.min.time()),
                    fmt_date,
                )
            else:
                ws.write(row, 1, str(fd or ""), fmt_text)
            c = 2
            if not hide_vendor:
                ws.write(row, c, r["vendedor"], fmt_text)
                c += 1
            ws.write(row, c, r["cliente"], fmt_text)
            c += 1
            ws.write(row, c, r["tipo"], fmt_text)
            c += 1
            ws.write_number(row, c, float(r["total_firmado"]), fmt_money)
            c += 1
            ws.write_number(row, c, float(r["saldo"]), fmt_money)
            c += 1
            ws.write(row, c, r["estado_pago"], fmt_text)
            row += 1

        row += 1
        ws.merge_range(row, 0, row, last_col, _("Resumen (totales del informe)"), fmt_section)
        row += 1
        ws.write(row, 0, _("TOTAL FIRMADO"), fmt_tot_label)
        ws.write_number(row, 1, float(total_firmado), fmt_tot_num)
        row += 1
        ws.write(row, 0, _("TOTAL ADEUDADO (saldo pendiente)"), fmt_tot_label)
        ws.write_number(row, 1, float(total_saldo), fmt_tot_num)
        row += 1
        ws.write(row, 0, _("Cantidad de comprobantes (FC / NC)"), fmt_tot_label)
        ws.write_number(row, 1, n_docs, fmt_tot_int)

        ws.set_column(0, 0, 22)
        ws.set_column(1, 1, 12)
        if not hide_vendor:
            ws.set_column(2, 2, 22)
            ws.set_column(3, 3, 36)
            ws.set_column(4, 4, 28)
            ws.set_column(5, 6, 16)
            ws.set_column(7, 7, 18)
        else:
            ws.set_column(2, 2, 38)
            ws.set_column(3, 3, 28)
            ws.set_column(4, 5, 16)
            ws.set_column(6, 6, 18)
        ws.freeze_panes(header_row + 1, 0)

        # --- Hoja 2: mismo agrupamiento que el PDF (cliente → líneas + subtotales)
        if hide_vendor:
            headers_g = [
                _("Documento"),
                _("Fecha"),
                _("Tipo"),
                _("Total firmado"),
                _("Saldo"),
                _("Estado pago"),
            ]
        else:
            headers_g = [
                _("Documento"),
                _("Fecha"),
                _("Vendedor"),
                _("Tipo"),
                _("Total firmado"),
                _("Saldo"),
                _("Estado pago"),
            ]
        last_col_g = len(headers_g) - 1
        ws2 = wb.add_worksheet(_("Por cliente")[:31])
        row2 = 0
        ws2.merge_range(
            row2,
            0,
            row2,
            last_col_g,
            _("Agrupado por cliente (orden: mayor saldo primero)"),
            fmt_title,
        )
        row2 += 1
        for key, val in self._export_xlsx_meta_lines():
            ws2.write(row2, 0, key, fmt_meta_key)
            ws2.merge_range(row2, 1, row2, last_col_g, val, fmt_meta_val)
            row2 += 1
        row2 += 1

        selection_pay = self._selection_dict("account.move", "payment_state")
        selection_move = self._selection_dict("account.move", "move_type")

        for sec in self._get_report_pdf_sections():
            ws2.merge_range(
                row2, 0, row2, last_col_g, sec["partner_label"], fmt_group_title
            )
            row2 += 1
            ws2.write(row2, 0, _("Comprobantes"), fmt_subbar)
            ws2.write_number(row2, 1, sec["count"], fmt_tot_int)
            ws2.write(row2, 2, _("Total firmado (cliente)"), fmt_subbar)
            ws2.write_number(row2, 3, float(sec["sum_total_signed"]), fmt_money)
            ws2.write(row2, 4, _("Saldo (cliente)"), fmt_subbar)
            ws2.write_number(row2, 5, float(sec["sum_residual"]), fmt_money)
            row2 += 1
            for col, h in enumerate(headers_g):
                ws2.write(row2, col, h, fmt_header)
            row2 += 1
            for m in sec["moves"]:
                ws2.write(row2, 0, m.name or "", fmt_text)
                if m.invoice_date:
                    ws2.write_datetime(
                        row2,
                        1,
                        datetime.combine(m.invoice_date, datetime.min.time()),
                        fmt_date,
                    )
                else:
                    ws2.write(row2, 1, "", fmt_text)
                c = 2
                if not hide_vendor:
                    ws2.write(row2, c, m.invoice_user_id.name or "", fmt_text)
                    c += 1
                ws2.write(
                    row2,
                    c,
                    selection_move.get(m.move_type, m.move_type),
                    fmt_text,
                )
                c += 1
                ws2.write_number(row2, c, float(m.amount_total_signed), fmt_money)
                c += 1
                ws2.write_number(row2, c, float(m.amount_residual), fmt_money)
                c += 1
                ws2.write(
                    row2,
                    c,
                    selection_pay.get(m.payment_state, m.payment_state),
                    fmt_text,
                )
                row2 += 1
            row2 += 1

        row2 += 1
        ws2.merge_range(row2, 0, row2, last_col_g, _("Resumen (totales del informe)"), fmt_section)
        row2 += 1
        ws2.write(row2, 0, _("TOTAL FIRMADO"), fmt_tot_label)
        ws2.write_number(row2, 1, float(total_firmado), fmt_tot_num)
        row2 += 1
        ws2.write(row2, 0, _("TOTAL ADEUDADO (saldo pendiente)"), fmt_tot_label)
        ws2.write_number(row2, 1, float(total_saldo), fmt_tot_num)
        row2 += 1
        ws2.write(row2, 0, _("Cantidad de comprobantes (FC / NC)"), fmt_tot_label)
        ws2.write_number(row2, 1, n_docs, fmt_tot_int)

        ws2.set_column(0, 0, 22)
        ws2.set_column(1, 1, 12)
        if not hide_vendor:
            ws2.set_column(2, 2, 22)
            ws2.set_column(3, 3, 28)
            ws2.set_column(4, 5, 16)
            ws2.set_column(6, 6, 18)
        else:
            ws2.set_column(2, 2, 28)
            ws2.set_column(3, 4, 16)
            ws2.set_column(5, 5, 18)

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
        if hide_vendor:
            writer.writerow(
                [
                    _("Documento"),
                    _("Fecha"),
                    _("Cliente"),
                    _("Tipo"),
                    _("Total firmado"),
                    _("Saldo"),
                    _("Estado pago"),
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
                    _("Estado pago"),
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
        writer.writerow([_("TOTAL FIRMADO"), f"{total_firmado:.2f}".replace(".", ",")])
        writer.writerow([_("TOTAL ADEUDADO (saldo)"), f"{total_saldo:.2f}".replace(".", ",")])
        writer.writerow([_("Cantidad de comprobantes"), str(n_docs)])
        return buf.getvalue().encode("utf-8-sig")

    def action_export_excel(self):
        self.ensure_one()
        moves = self._search_moves()
        if not moves:
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
