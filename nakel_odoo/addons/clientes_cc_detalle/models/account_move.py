# -*- coding: utf-8 -*-

import csv
import io
from collections import defaultdict
from datetime import date, datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv.expression import AND
from odoo.tools.misc import formatLang

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model
    def _clientes_cc_journal_ids_for_afip_pos_filter(
        self, company_id, pos_number, include_migration=True
    ):
        """Diarios de venta cuyo PDV AFIP coincide + opcional diario de migración de deudores.

        Si la localización no expone ``l10n_ar_afip_pos_number`` en ``account.journal``,
        devuelve ``None`` (sin filtrar). ``pos_number`` vacío o <= 0 → ``None``.
        """
        if pos_number is None or pos_number is False:
            return None
        try:
            pos_int = int(pos_number)
        except (TypeError, ValueError):
            return None
        if pos_int <= 0:
            return None
        Journal = self.env["account.journal"]
        if "l10n_ar_afip_pos_number" not in Journal._fields:
            return None
        company = self.env["res.company"].browse(company_id)
        if not company:
            return None
        journals = Journal.search(
            [
                ("company_id", "=", company.id),
                ("l10n_ar_afip_pos_number", "=", pos_int),
            ]
        )
        ids = list(journals.ids)
        if include_migration:
            mig = Journal.search(
                [
                    ("company_id", "=", company.id),
                    ("type", "=", "sale"),
                    "|",
                    ("name", "ilike", "migración"),
                    ("name", "ilike", "migracion"),
                ]
            )
            ids = list(set(ids + mig.ids))
        return ids or None

    @api.model
    def _clientes_cc_my_sales_journal_domain_extra(self):
        """Trozos de dominio por PDV AFIP (parámetros sistema) para «mis ventas»."""
        icp = self.env["ir.config_parameter"].sudo()
        if icp.get_param("clientes_cc_detalle.my_sales_filter_afip_pos") != "1":
            return []
        raw_pos = icp.get_param("clientes_cc_detalle.my_sales_afip_pos_number") or ""
        inc = icp.get_param("clientes_cc_detalle.my_sales_include_migracion", "1") != "0"
        jids = self._clientes_cc_journal_ids_for_afip_pos_filter(
            self.env.company.id, raw_pos.strip() or None, include_migration=inc
        )
        if jids:
            return [("journal_id", "in", jids)]
        return []

    @api.model
    def _clientes_cc_my_sales_balance_from_date_icp(self):
        """Fecha de corte opcional (Ajustes → Parámetros): ``YYYY-MM-DD``.

        Usada en contactos para mostrar saldo «anterior al corte» y como referencia;
        la exportación suma saldo inicial cuando la lista tiene filtro por fecha.
        """
        raw = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("clientes_cc_detalle.my_sales_balance_from_date", "")
            .strip()
        )
        if not raw or len(raw) < 10:
            return None
        try:
            return date(int(raw[0:4]), int(raw[5:7]), int(raw[8:10]))
        except (TypeError, ValueError):
            return None

    @api.model
    def _clientes_cc_domain_strip_invoice_date(self, domain):
        if not domain:
            return []
        out = []
        for item in domain:
            if isinstance(item, (list, tuple)) and len(item) == 3 and item[0] == "invoice_date":
                continue
            out.append(item)
        return out

    @api.model
    def _clientes_cc_invoice_date_lower_bound_from_domain(self, domain):
        """Si el dominio fuerza ``invoice_date >= T`` (o ``>``), devuelve T (máximo de tales)."""
        if not domain:
            return None
        candidates = []
        for item in domain:
            if not isinstance(item, (list, tuple)) or len(item) != 3:
                continue
            fname, op, val = item
            if fname != "invoice_date":
                continue
            if op == ">=" and isinstance(val, date):
                candidates.append(val)
            elif op == ">" and isinstance(val, date):
                candidates.append(val + timedelta(days=1))
        return max(candidates) if candidates else None

    @api.model
    def _clientes_cc_opening_moves_for_export(self, cut_date, active_domain):
        """FC/NC mis ventas con factura estrictamente anterior a ``cut_date`` (mismo alcance que export)."""
        if not cut_date:
            return self.env["account.move"]
        base = list(self._clientes_cc_my_sales_base_domain())
        base.append(("invoice_date", "<", cut_date))
        stripped = self._clientes_cc_domain_strip_invoice_date(active_domain or [])
        if stripped:
            try:
                domain = AND([base, stripped])
            except Exception:
                domain = base
        else:
            domain = base
        return self.search(domain, limit=100000)

    cc_paid_amount = fields.Monetary(
        string="Cobrado",
        currency_field="currency_id",
        compute="_compute_cc_paid_amount",
        groups="clientes_cc_detalle.group_cc_my_sales,sales_team.group_sale_salesman,sales_team.group_sale_manager",
        help="Importe cobrado/aplicado sobre el documento: total firmado - saldo pendiente.",
    )

    # Por defecto mail.thread exige permiso de *escritura* para seguidores/chatter;
    # con solo lectura en account.move Odoo muestra "no puede modificar". Lectura
    # alcanza para abrir facturas/listas sin dar perm_write masivo.
    _mail_post_access = "read"

    @api.depends("amount_total_signed", "amount_residual")
    def _compute_cc_paid_amount(self):
        for m in self:
            m.cc_paid_amount = (m.amount_total_signed or 0.0) - (m.amount_residual or 0.0)

    def action_clientes_cc_open_applied_payments(self):
        """Lista los cobros (`account.payment`) reconciliados con la FC/NC.

        Reutiliza el mismo criterio que el botón estándar *Payments* de la factura
        (`reconciled_payment_ids`). Si no hay pagos vinculados (p. ej. solo extracto),
        se informa con un mensaje claro.
        """
        self.ensure_one()
        if self.move_type not in ("out_invoice", "out_refund") or self.state != "posted":
            raise UserError(
                _("Solo aplica a facturas y notas de crédito de cliente publicadas.")
            )
        payments = self.reconciled_payment_ids
        if not payments:
            raise UserError(
                _(
                    "No hay pagos (cobros) registrados reconciliados con este comprobante. "
                    "Si el cobro figura solo en extracto bancario u otro asiento sin "
                    "`account.payment`, consulte con administración o use contabilidad."
                )
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Pagos aplicados"),
            "res_model": "account.payment",
            "view_mode": "list,form",
            "views": [
                (self.env.ref("account.view_account_payment_tree").id, "list"),
                (self.env.ref("account.view_account_payment_form").id, "form"),
            ],
            "domain": [("id", "in", payments.ids)],
            "context": {"create": False},
        }

    @api.model
    def action_clientes_cc_open_my_sales_pivot(self):
        """Facturas/NC de cliente posteadas con comercial = usuario actual.

        Delega en la acción persistida (vistas pivote/gráfico/lista + contexto pivot_*).
        """
        return self.env["ir.actions.actions"]._for_xml_id(
            "clientes_cc_detalle.action_act_window_clientes_cc_my_sales"
        )

    @api.model
    def _clientes_cc_my_sales_base_domain(self):
        """Dominio fijo CC «mis ventas» (seguridad + semántica menú)."""
        domain = [
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("invoice_user_id", "=", self.env.uid),
            ("company_id", "in", self.env.companies.ids),
        ]
        domain.extend(self._clientes_cc_my_sales_journal_domain_extra())
        return domain

    @api.model
    def _clientes_cc_my_sales_export_domain(self):
        """Dominio base AND filtros de la lista (active_domain) si el cliente lo envía."""
        domain = list(self._clientes_cc_my_sales_base_domain())
        active_domain = self.env.context.get("active_domain")
        if active_domain:
            try:
                domain = AND([domain, active_domain])
            except Exception:
                pass
        return domain

    @api.model
    def _clientes_cc_selection_labels(self, model_name, field_name):
        Model = self.env[model_name]
        field = Model._fields[field_name]
        sel = field.selection
        if callable(sel):
            sel = sel(Model)
        return dict(sel)

    @api.model
    def _clientes_cc_export_rows(self, moves):
        pay_labels = self._clientes_cc_selection_labels("account.move", "payment_state")
        move_labels = self._clientes_cc_selection_labels("account.move", "move_type")
        rows = []
        for m in moves:
            total = m.amount_total_signed or 0.0
            residual = m.amount_residual or 0.0
            rows.append(
                {
                    "documento": m.name or "",
                    "fecha": m.invoice_date or "",
                    "vencimiento": m.invoice_date_due or "",
                    "cliente": m.commercial_partner_id.display_name or "",
                    "diario": m.journal_id.display_name or "",
                    "tipo": move_labels.get(m.move_type, m.move_type),
                    "total_firmado": total,
                    "cobrado": total - residual,
                    "saldo": residual,
                    "estado_pago": pay_labels.get(m.payment_state, m.payment_state),
                }
            )
        return rows

    @api.model
    def _clientes_cc_pdf_global_from_moves(self, moves, opening_residual=0.0, cut_date=None):
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
        base["opening_residual"] = opening_residual
        base["has_opening_footer"] = bool(cut_date)
        base["sum_residual_with_opening"] = opening_residual + base["sum_residual"]
        base["cut_date"] = cut_date
        return base

    @api.model
    def _clientes_cc_pdf_sections_from_moves(self, moves, opening_by_partner=None):
        opening_by_partner = opening_by_partner or {}
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
            sum_open = opening_by_partner.get(pid, 0.0) if pid else 0.0
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

    @api.model
    def _clientes_cc_xlsx_build_formats(self, wb):
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

    @api.model
    def _clientes_cc_xlsx_write_pdf_sheet(
        self,
        ws,
        moves,
        fmts,
        opening_residual=0.0,
        cut_date=None,
        opening_by_partner=None,
        icp_date=None,
        opening_icp_reference=0.0,
    ):
        """Misma estructura que el PDF del informe (sin columna vendedor: solo mis ventas)."""
        opening_by_partner = opening_by_partner or {}
        cur = fmts
        headers = [
            _("Documento"),
            _("Fecha"),
            _("Tipo"),
            _("Total"),
            _("Saldo"),
            _("Cobro"),
        ]
        last_col = len(headers) - 1
        company = self.env.company
        currency = company.currency_id
        n_docs = len(moves)
        partners = len({m.commercial_partner_id.id for m in moves if m.commercial_partner_id})
        row = 0
        ws.merge_range(
            row,
            0,
            row,
            last_col,
            _("Cuentas corrientes — mis ventas (exportación)"),
            cur["fmt_title"],
        )
        row += 1
        meta = [
            (_("Compañía"), company.name or ""),
            (_("Usuario"), self.env.user.display_name),
            (
                _("Generado"),
                fields.Datetime.context_timestamp(
                    self, fields.Datetime.now()
                ).strftime("%Y-%m-%d %H:%M"),
            ),
            (_("Registros exportados"), str(n_docs)),
            (_("Clientes distintos"), str(partners)),
        ]
        if icp_date and not cut_date and opening_icp_reference:
            meta.append(
                (
                    _("Saldo FC/NC anteriores al corte ICP (referencia)"),
                    "%s — %s"
                    % (
                        icp_date,
                        formatLang(
                            self.env,
                            opening_icp_reference,
                            currency_obj=currency,
                        ),
                    ),
                )
            )
        for key, val in meta:
            ws.write(row, 0, key, cur["fmt_meta_key"])
            ws.merge_range(row, 1, row, last_col, val, cur["fmt_meta_val"])
            row += 1
        row += 1

        g = self._clientes_cc_pdf_global_from_moves(moves, opening_residual, cut_date)
        if g.get("has_opening_footer"):
            resumen_txt = _(
                "Clientes con movimientos: %(pc)s — Documentos: %(dc)s — "
                "Total importes (firmado): %(tf)s — Adeudado (tabla): %(sr)s — "
                "Saldo inicial (FC/NC con factura anterior al %(cut)s): %(so)s — "
                "Adeudado total (inicial + tabla): %(st)s"
            ) % {
                "pc": g["partner_count"],
                "dc": g["document_count"],
                "tf": formatLang(self.env, g["sum_total_signed"], currency_obj=currency),
                "sr": formatLang(self.env, g["sum_residual"], currency_obj=currency),
                "cut": cut_date,
                "so": formatLang(self.env, g["opening_residual"], currency_obj=currency),
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

        selection_pay = self._clientes_cc_selection_labels("account.move", "payment_state")
        selection_move = self._clientes_cc_selection_labels("account.move", "move_type")
        sections = self._clientes_cc_pdf_sections_from_moves(moves, opening_by_partner)

        for sec in sections:
            ws.merge_range(
                row, 0, row, last_col, sec["partner_label"], cur["fmt_group_title"]
            )
            row += 1
            if cut_date:
                bloque_txt = _(
                    "%(n)s documento(s) — Total firmado: %(tf)s — Adeudado (tabla): %(sr)s — "
                    "Saldo inicial: %(so)s — Adeudado total: %(tt)s"
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
                ws.write(
                    row,
                    2,
                    selection_move.get(m.move_type, m.move_type),
                    cur["fmt_text"],
                )
                ws.write_number(row, 3, float(m.amount_total_signed), cur["fmt_money"])
                ws.write_number(row, 4, float(m.amount_residual), cur["fmt_money"])
                ws.write(
                    row,
                    5,
                    selection_pay.get(m.payment_state, m.payment_state),
                    cur["fmt_text"],
                )
                row += 1
            row += 1

        total_firmado = sum(moves.mapped("amount_total_signed"))
        total_saldo = sum(moves.mapped("amount_residual"))
        total_cobrado = total_firmado - total_saldo
        row += 1
        ws.merge_range(row, 0, row, last_col, _("Resumen (totales)"), cur["fmt_section"])
        row += 1
        if cut_date:
            ws.write(row, 0, _("SALDO INICIAL (FC/NC antes del corte)"), cur["fmt_tot_label"])
            ws.write_number(row, 1, float(opening_residual), cur["fmt_tot_num"])
            row += 1
        ws.write(row, 0, _("TOTAL FIRMADO (tabla)"), cur["fmt_tot_label"])
        ws.write_number(row, 1, float(total_firmado), cur["fmt_tot_num"])
        row += 1
        ws.write(row, 0, _("TOTAL COBRADO / APLICADO (tabla)"), cur["fmt_tot_label"])
        ws.write_number(row, 1, float(total_cobrado), cur["fmt_tot_num"])
        row += 1
        ws.write(row, 0, _("TOTAL ADEUDADO (tabla)"), cur["fmt_tot_label"])
        ws.write_number(row, 1, float(total_saldo), cur["fmt_tot_num"])
        row += 1
        if cut_date:
            ws.write(row, 0, _("ADEUDADO TOTAL (inicial + tabla)"), cur["fmt_tot_label"])
            ws.write_number(
                row, 1, float(opening_residual + total_saldo), cur["fmt_tot_num"]
            )
            row += 1
        ws.write(row, 0, _("Comprobantes"), cur["fmt_tot_label"])
        ws.write_number(row, 1, n_docs, cur["fmt_tot_int"])

        ws.set_column(0, 0, 22)
        ws.set_column(1, 1, 12)
        ws.set_column(2, 2, 28)
        ws.set_column(3, 4, 16)
        ws.set_column(5, 5, 22)

    @api.model
    def _clientes_cc_xlsx_write_flat_sheet(
        self, ws, moves, fmts, opening_residual=0.0, cut_date=None
    ):
        """Tabla plana con columnas operativas (vencimiento, diario) + «Cobro»."""
        cur = fmts
        rows = self._clientes_cc_export_rows(moves)
        total_firmado = sum(moves.mapped("amount_total_signed"))
        total_saldo = sum(moves.mapped("amount_residual"))
        total_cobrado = total_firmado - total_saldo
        n_docs = len(moves)
        headers = [
            _("Documento"),
            _("Fecha factura"),
            _("Vencimiento"),
            _("Cliente"),
            _("Diario"),
            _("Tipo"),
            _("Total firmado"),
            _("Cobrado"),
            _("Saldo"),
            _("Cobro (estado)"),
        ]
        last_col = len(headers) - 1
        row = 0
        ws.merge_range(row, 0, row, last_col, _("Detalle plano (tabla única)"), cur["fmt_title"])
        row += 1
        company = self.env.company
        meta = [
            (_("Compañía"), company.name or ""),
            (_("Usuario"), self.env.user.display_name),
            (
                _("Generado"),
                fields.Datetime.context_timestamp(
                    self, fields.Datetime.now()
                ).strftime("%Y-%m-%d %H:%M"),
            ),
        ]
        for key, val in meta:
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
            for col, key in ((1, "fecha"), (2, "vencimiento")):
                fdv = r[key]
                if isinstance(fdv, date):
                    ws.write_datetime(
                        row,
                        col,
                        datetime.combine(fdv, datetime.min.time()),
                        cur["fmt_date"],
                    )
                else:
                    ws.write(row, col, str(fdv or ""), cur["fmt_text"])
            ws.write(row, 3, r["cliente"], cur["fmt_text"])
            ws.write(row, 4, r["diario"], cur["fmt_text"])
            ws.write(row, 5, r["tipo"], cur["fmt_text"])
            ws.write_number(row, 6, float(r["total_firmado"]), cur["fmt_money"])
            ws.write_number(row, 7, float(r["cobrado"]), cur["fmt_money"])
            ws.write_number(row, 8, float(r["saldo"]), cur["fmt_money"])
            ws.write(row, 9, r["estado_pago"], cur["fmt_text"])
            row += 1
        row += 1
        ws.merge_range(row, 0, row, last_col, _("Resumen (totales)"), cur["fmt_section"])
        row += 1
        if cut_date:
            ws.write(row, 0, _("SALDO INICIAL (FC/NC antes del corte)"), cur["fmt_tot_label"])
            ws.write_number(row, 1, float(opening_residual), cur["fmt_tot_num"])
            row += 1
        ws.write(row, 0, _("TOTAL FIRMADO (tabla)"), cur["fmt_tot_label"])
        ws.write_number(row, 1, float(total_firmado), cur["fmt_tot_num"])
        row += 1
        ws.write(row, 0, _("TOTAL COBRADO / APLICADO (tabla)"), cur["fmt_tot_label"])
        ws.write_number(row, 1, float(total_cobrado), cur["fmt_tot_num"])
        row += 1
        ws.write(row, 0, _("TOTAL ADEUDADO (tabla)"), cur["fmt_tot_label"])
        ws.write_number(row, 1, float(total_saldo), cur["fmt_tot_num"])
        row += 1
        if cut_date:
            ws.write(row, 0, _("ADEUDADO TOTAL (inicial + tabla)"), cur["fmt_tot_label"])
            ws.write_number(
                row, 1, float(opening_residual + total_saldo), cur["fmt_tot_num"]
            )
            row += 1
        ws.write(row, 0, _("Comprobantes"), cur["fmt_tot_label"])
        ws.write_number(row, 1, n_docs, cur["fmt_tot_int"])
        ws.set_column(0, 0, 22)
        ws.set_column(1, 2, 12)
        ws.set_column(3, 3, 38)
        ws.set_column(4, 4, 22)
        ws.set_column(5, 5, 28)
        ws.set_column(6, 8, 16)
        ws.set_column(9, 9, 22)
        ws.freeze_panes(header_row + 1, 0)

    @api.model
    def _clientes_cc_export_xlsx_bytes(
        self,
        moves,
        opening_residual=0.0,
        cut_date=None,
        opening_by_partner=None,
        icp_date=None,
        opening_icp_reference=0.0,
    ):
        """Hoja 1 = layout tipo PDF informe; hoja 2 = tabla plana."""
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {"in_memory": True})
        fmts = self._clientes_cc_xlsx_build_formats(wb)
        ws1 = wb.add_worksheet(_("Informe (PDF)")[:31])
        self._clientes_cc_xlsx_write_pdf_sheet(
            ws1,
            moves,
            fmts,
            opening_residual=opening_residual,
            cut_date=cut_date,
            opening_by_partner=opening_by_partner,
            icp_date=icp_date,
            opening_icp_reference=opening_icp_reference,
        )
        ws2 = wb.add_worksheet(_("Detalle plano")[:31])
        self._clientes_cc_xlsx_write_flat_sheet(
            ws2, moves, fmts, opening_residual=opening_residual, cut_date=cut_date
        )
        wb.close()
        return buf.getvalue()

    @api.model
    def _clientes_cc_export_csv_bytes(
        self,
        moves,
        opening_residual=0.0,
        cut_date=None,
        icp_date=None,
        opening_icp_reference=0.0,
    ):
        rows = self._clientes_cc_export_rows(moves)
        total_firmado = sum(moves.mapped("amount_total_signed"))
        total_saldo = sum(moves.mapped("amount_residual"))
        total_cobrado = total_firmado - total_saldo
        n_docs = len(moves)
        currency = self.env.company.currency_id
        g = self._clientes_cc_pdf_global_from_moves(moves, opening_residual, cut_date)

        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=";", lineterminator="\n")
        writer.writerow([_("Cuentas corrientes — mis ventas (exportación)")])
        writer.writerow([_("Compañía"), self.env.company.name or ""])
        writer.writerow([_("Usuario"), self.env.user.display_name])
        writer.writerow([])
        if g.get("has_opening_footer"):
            resumen_csv = _(
                "Clientes con movimientos: %(pc)s — Documentos: %(dc)s — "
                "Total importes (firmado): %(tf)s — Adeudado (tabla): %(sr)s — "
                "Saldo inicial (FC/NC anteriores al %(cut)s): %(so)s — Adeudado total: %(st)s"
            ) % {
                "pc": g["partner_count"],
                "dc": g["document_count"],
                "tf": formatLang(self.env, g["sum_total_signed"], currency_obj=currency),
                "sr": formatLang(self.env, g["sum_residual"], currency_obj=currency),
                "cut": cut_date,
                "so": formatLang(self.env, g["opening_residual"], currency_obj=currency),
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
        if icp_date and not cut_date and opening_icp_reference:
            writer.writerow(
                [
                    _("Saldo FC/NC anteriores al corte ICP (referencia)"),
                    f"{opening_icp_reference:.2f}".replace(".", ","),
                ]
            )
        writer.writerow([])
        writer.writerow(
            [
                _("Documento"),
                _("Fecha factura"),
                _("Vencimiento"),
                _("Cliente"),
                _("Diario"),
                _("Tipo"),
                _("Total firmado"),
                _("Cobrado"),
                _("Saldo"),
                _("Cobro (estado)"),
            ]
        )

        def _fd_s(fd):
            return fd.strftime("%d/%m/%Y") if isinstance(fd, date) else str(fd or "")

        for r in rows:
            writer.writerow(
                [
                    r["documento"],
                    _fd_s(r["fecha"]),
                    _fd_s(r["vencimiento"]),
                    r["cliente"],
                    r["diario"],
                    r["tipo"],
                    f"{r['total_firmado']:.2f}".replace(".", ","),
                    f"{r['cobrado']:.2f}".replace(".", ","),
                    f"{r['saldo']:.2f}".replace(".", ","),
                    r["estado_pago"],
                ]
            )
        writer.writerow([])
        if cut_date:
            writer.writerow(
                [
                    _("SALDO INICIAL (FC/NC antes del corte)"),
                    f"{opening_residual:.2f}".replace(".", ","),
                ]
            )
        writer.writerow(
            [_("TOTAL FIRMADO (tabla)"), f"{total_firmado:.2f}".replace(".", ",")]
        )
        writer.writerow(
            [_("TOTAL COBRADO (tabla)"), f"{total_cobrado:.2f}".replace(".", ",")]
        )
        writer.writerow(
            [_("TOTAL ADEUDADO (tabla)"), f"{total_saldo:.2f}".replace(".", ",")]
        )
        if cut_date:
            writer.writerow(
                [
                    _("ADEUDADO TOTAL (inicial + tabla)"),
                    f"{(opening_residual + total_saldo):.2f}".replace(".", ","),
                ]
            )
        writer.writerow([_("Comprobantes"), str(n_docs)])
        return buf.getvalue().encode("utf-8-sig")

    def action_clientes_cc_export_my_sales_spreadsheet(self):
        """Descarga Excel/CSV con el mismo alcance que la lista (dominio + filtros de búsqueda).

        Respeta `active_domain` del cliente web cuando está disponible; si no,
        exporta todo el conjunto CC del usuario en la compañía.

        No usar ``@api.model``: el botón de cabecera del listado invoca el método sobre
        un recordset (puede estar vacío) y ``call_kw`` no es compatible con esa firma.
        """
        Move = self.env["account.move"]
        active_domain = self.env.context.get("active_domain") or []
        cut_date = Move._clientes_cc_invoice_date_lower_bound_from_domain(active_domain)
        icp_date = Move._clientes_cc_my_sales_balance_from_date_icp()

        opening_residual = 0.0
        opening_by_partner = {}
        if cut_date:
            opening_moves = Move._clientes_cc_opening_moves_for_export(
                cut_date, active_domain
            )
            opening_residual = sum(opening_moves.mapped("amount_residual"))
            ob = defaultdict(float)
            for om in opening_moves:
                if om.commercial_partner_id:
                    ob[om.commercial_partner_id.id] += om.amount_residual
            opening_by_partner = dict(ob)

        opening_icp_reference = 0.0
        if icp_date and not cut_date:
            om_icp = Move._clientes_cc_opening_moves_for_export(icp_date, active_domain)
            opening_icp_reference = sum(om_icp.mapped("amount_residual"))

        domain = self._clientes_cc_my_sales_export_domain()
        moves = self.search(
            domain, order="invoice_date desc, name desc, id desc", limit=100000
        )
        if not moves and not (cut_date and opening_residual) and not (
            icp_date and not cut_date and opening_icp_reference
        ):
            raise UserError(_("No hay documentos para exportar con los filtros actuales."))
        if xlsxwriter:
            content = Move._clientes_cc_export_xlsx_bytes(
                moves,
                opening_residual=opening_residual,
                cut_date=cut_date,
                opening_by_partner=opening_by_partner,
                icp_date=icp_date,
                opening_icp_reference=opening_icp_reference,
            )
            filename = "cuentas_corrientes_mis_ventas.xlsx"
            mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            content = Move._clientes_cc_export_csv_bytes(
                moves,
                opening_residual=opening_residual,
                cut_date=cut_date,
                icp_date=icp_date,
                opening_icp_reference=opening_icp_reference,
            )
            filename = "cuentas_corrientes_mis_ventas.csv"
            mimetype = "text/csv; charset=utf-8"
        attachment = self.env["ir.attachment"].create(
            {
                "name": filename,
                "type": "binary",
                "raw": content,
                "mimetype": mimetype,
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "new",
        }
