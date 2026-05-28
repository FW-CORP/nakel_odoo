# -*- coding: utf-8 -*-
"""
Lógica de valoración PICK → SO → factura.

Copiada y adaptada desde addons/nakel_picking (stock.picking.batch) para
reutilizar el comportamiento probado en olas sin modificar ese módulo.
"""

from odoo import fields, models
import re


class StockPickingNakelValuation(models.Model):
    """Extensión de stock.picking: valoración SO/factura (métodos compartidos)."""
    _inherit = 'stock.picking'

    def _nakel_extract_sale_name_from_origin(self, origin):
        origin = (origin or '').strip()
        if not origin:
            return ''
        m = re.search(r'\bS\d+\b', origin, flags=re.IGNORECASE)
        if m:
            return m.group(0).upper()
        return origin.split()[0].strip()

    def _nakel_picking_short_number(self, picking_name):
        name = (picking_name or '').strip()
        if not name:
            return ''
        m = re.search(r'(\d+)(?!.*\d)', name)
        if not m:
            return name
        return str(int(m.group(1)))

    def _nakel_build_valuation_lines(self, pickings):
        """
        Arma líneas para sección VALORACIÓN: Picking → SO → factura(s).

        :param pickings: recordset stock.picking
        :return: list[dict] (misma forma que nakel_picking en batch)
        """
        try:
            Sale = self.env['sale.order']
            Move = self.env['account.move']
        except KeyError:
            return []

        lines = []
        for picking in pickings:
            sale = False
            try:
                sale = getattr(picking, 'sale_id', False) or False
            except Exception:
                sale = False

            if not sale:
                try:
                    so_from_moves = picking.move_ids.mapped('sale_line_id').mapped('order_id')
                    sale = so_from_moves[:1] if so_from_moves else False
                except Exception:
                    sale = False

            if not sale and getattr(picking, 'origin', False):
                so_name = self._nakel_extract_sale_name_from_origin(picking.origin)
                if so_name:
                    sale = Sale.search([('name', '=', so_name)], limit=1)
                if not sale:
                    sale = Sale.search(
                        [('name', 'ilike', so_name or picking.origin)],
                        limit=1,
                    )

            invoices = self.env['account.move']

            if sale:
                invoices = sale.invoice_ids

            if not invoices:
                sale_lines = picking.move_ids.mapped('sale_line_id')
                if sale_lines:
                    inv_lines = sale_lines.mapped('invoice_lines')
                    invoices = inv_lines.mapped('move_id')

            if not invoices:
                origins = []
                if sale and sale.name:
                    origins.append(sale.name)
                if getattr(picking, 'origin', False):
                    origins.append(
                        self._nakel_extract_sale_name_from_origin(picking.origin)
                        or picking.origin
                    )
                if picking.name:
                    origins.append(picking.name)
                for origin in origins:
                    invoices |= Move.search([
                        ('state', '!=', 'cancel'),
                        ('move_type', 'in', ('out_invoice', 'out_refund')),
                        '|', '|',
                        ('invoice_origin', '=', origin),
                        ('invoice_origin', 'ilike', origin),
                        ('ref', 'ilike', origin),
                    ])

            invoices = invoices.filtered(
                lambda m: m.state != 'cancel'
                and m.move_type in ('out_invoice', 'out_refund')
            )
            invoices = (
                invoices.sorted(
                    lambda m: (m.invoice_date or m.date or fields.Date.today(), m.id)
                )
                if invoices
                else self.env['account.move']
            )

            partner_name = ''
            sale_total = 0.0
            sale_currency = None
            payment_term_label = ''
            if sale:
                try:
                    partner_name = (
                        sale.partner_shipping_id.display_name
                        or sale.partner_id.display_name
                        or ''
                    )
                except Exception:
                    partner_name = sale.partner_id.display_name if sale.partner_id else ''
                sale_total = float(getattr(sale, 'amount_total', 0.0) or 0.0)
                sale_currency = getattr(sale, 'currency_id', None)
                try:
                    payment_term_label = (
                        (sale.payment_term_id.name or '').strip()
                        if sale.payment_term_id
                        else ''
                    )
                except Exception:
                    payment_term_label = ''
            else:
                try:
                    partner_name = (picking.partner_id.display_name if picking.partner_id else '') or ''
                except Exception:
                    partner_name = ''

            origin_raw = ''
            try:
                origin_raw = getattr(picking, 'origin', '') or ''
            except Exception:
                origin_raw = ''
            so_name_from_origin = (
                self._nakel_extract_sale_name_from_origin(origin_raw) if origin_raw else ''
            )
            sale_name_display = sale.name if sale else (so_name_from_origin or origin_raw)

            if not invoices:
                lines.append({
                    'picking': picking,
                    'picking_short': self._nakel_picking_short_number(picking.name),
                    'sale_name': sale_name_display,
                    'partner_name': partner_name,
                    'sale_total': sale_total,
                    'sale_currency': sale_currency,
                    'payment_term': payment_term_label,
                    'origin_raw': origin_raw,
                    'invoice': False,
                    'invoice_name': '',
                    'amount_total': 0.0,
                    'currency': (sale.currency_id if sale else None),
                    'has_invoice': False,
                })
                continue

            for inv in invoices:
                currency = inv.currency_id or (sale.currency_id if sale else None)
                amount = inv.amount_total
                try:
                    amount = (
                        inv.amount_total_signed
                        if inv.move_type == 'out_refund'
                        else inv.amount_total
                    )
                except Exception:
                    pass
                lines.append({
                    'picking': picking,
                    'picking_short': self._nakel_picking_short_number(picking.name),
                    'sale_name': sale_name_display,
                    'partner_name': partner_name,
                    'sale_total': sale_total,
                    'sale_currency': sale_currency,
                    'payment_term': payment_term_label,
                    'origin_raw': origin_raw,
                    'invoice': inv,
                    'invoice_name': inv.name or inv.payment_reference or inv.ref or '',
                    'amount_total': amount,
                    'currency': currency,
                    'has_invoice': True,
                })

        def _key(x):
            return (x.get('picking_short') or '', x.get('invoice_name') or '')

        return sorted(lines, key=_key)
