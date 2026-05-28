# -*- coding: utf-8 -*-

from odoo import models, fields, api
from collections import defaultdict
import base64
import io
import math
import re


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    def _extract_sale_name_from_origin(self, origin):
        """
        Intenta extraer el nombre de la SO desde `origin`.
        Ej.: 'S02331' o 'S02331 - Nakel SA' -> 'S02331'
        """
        origin = (origin or '').strip()
        if not origin:
            return ''
        m = re.search(r'\bS\d+\b', origin, flags=re.IGNORECASE)
        if m:
            return m.group(0).upper()
        # fallback: primer token
        return origin.split()[0].strip()

    def _picking_short_number(self, picking_name):
        """
        Devuelve un "número corto" para el picking.
        Ej.: 'WH/OUT/000123' -> '123', 'PICK/0456' -> '456'.
        """
        name = (picking_name or '').strip()
        if not name:
            return ''
        m = re.search(r'(\d+)(?!.*\d)', name)
        if not m:
            return name
        return str(int(m.group(1)))

    def _get_valuation_lines(self):
        """
        Arma líneas para sección VALORACIÓN:
        Picking -> Factura -> Monto.

        Estrategia:
        - Si existe `picking.sale_id`, usarlo.
        - Si no, intentar por `picking.origin` (nombre de SO).
        - Facturas desde `sale.invoice_ids` (out_invoice/out_refund), excluye canceladas.
        - Si no hay sale/invoices, devuelve vacío sin romper.
        """
        self.ensure_one()

        # Entornos donde sale/account no están instalados: no romper el PDF
        try:
            Sale = self.env['sale.order']
            Move = self.env['account.move']
        except KeyError:
            return []

        lines = []
        for picking in self.picking_ids:
            sale = None
            try:
                sale = getattr(picking, 'sale_id', False) or False
            except Exception:
                sale = False

            # Fallback 0: derivar SO desde las líneas de venta de los movimientos (más confiable que origin)
            if not sale:
                try:
                    so_from_moves = picking.move_ids.mapped('sale_line_id').mapped('order_id')
                    sale = so_from_moves[:1] if so_from_moves else False
                except Exception:
                    sale = False

            if not sale and getattr(picking, 'origin', False):
                so_name = self._extract_sale_name_from_origin(picking.origin)
                if so_name:
                    sale = Sale.search([('name', '=', so_name)], limit=1)
                if not sale:
                    # fallback laxo: por si el origin trae variantes/espacios
                    sale = Sale.search([('name', 'ilike', so_name or picking.origin)], limit=1)

            invoices = self.env['account.move']

            # 1) Mejor caso: sale.order.invoice_ids
            if sale:
                invoices = sale.invoice_ids

            # 2) Fallback robusto: desde líneas de venta de los movimientos del picking
            #    stock.move.sale_line_id -> sale.order.line -> invoice_lines -> account.move
            if not invoices:
                sale_lines = picking.move_ids.mapped('sale_line_id')
                if sale_lines:
                    inv_lines = sale_lines.mapped('invoice_lines')
                    invoices = inv_lines.mapped('move_id')

            # 3) Fallback: buscar por invoice_origin / refs (SO o picking)
            if not invoices:
                origins = []
                if sale and sale.name:
                    origins.append(sale.name)
                if getattr(picking, 'origin', False):
                    origins.append(self._extract_sale_name_from_origin(picking.origin) or picking.origin)
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

            invoices = invoices.filtered(lambda m: m.state != 'cancel' and m.move_type in ('out_invoice', 'out_refund'))
            invoices = invoices.sorted(lambda m: (m.invoice_date or m.date or fields.Date.today(), m.id)) if invoices else self.env['account.move']

            # Datos base para cobranza (transportista): preferimos SO si existe
            partner_name = ''
            sale_total = 0.0
            sale_currency = None
            payment_term_label = ''
            if sale:
                try:
                    partner_name = sale.partner_shipping_id.display_name or sale.partner_id.display_name or ''
                except Exception:
                    partner_name = sale.partner_id.display_name if sale.partner_id else ''
                sale_total = float(getattr(sale, 'amount_total', 0.0) or 0.0)
                sale_currency = getattr(sale, 'currency_id', None)
                try:
                    payment_term_label = (sale.payment_term_id.name or '').strip() if sale.payment_term_id else ''
                except Exception:
                    payment_term_label = ''
            else:
                # fallback: partner del picking (por si no hay SO)
                try:
                    partner_name = (picking.partner_id.display_name if picking.partner_id else '') or ''
                except Exception:
                    partner_name = ''

            origin_raw = ''
            try:
                origin_raw = getattr(picking, 'origin', '') or ''
            except Exception:
                origin_raw = ''
            so_name_from_origin = self._extract_sale_name_from_origin(origin_raw) if origin_raw else ''
            sale_name_display = sale.name if sale else (so_name_from_origin or origin_raw)

            # Si no hay facturas, igual devolvemos una línea por picking (muestra SO/origen)
            if not invoices:
                lines.append({
                    'picking': picking,
                    'picking_short': self._picking_short_number(picking.name),
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
                # En devoluciones, suele ser útil ver el signo real
                try:
                    amount = inv.amount_total_signed if inv.move_type == 'out_refund' else inv.amount_total
                except Exception:
                    pass
                lines.append({
                    'picking': picking,
                    'picking_short': self._picking_short_number(picking.name),
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

        # Orden: por picking (número), luego por factura
        def _key(x):
            return (x.get('picking_short') or '', x.get('invoice_name') or '')
        return sorted(lines, key=_key)

    def _get_cobranza_data(self):
        """
        Datos para el "RESUMEN DE COBRANZA" del transportista.

        Devuelve:
          {
            'lines': [ ... ],          # líneas por picking + factura (si existe)
            'totals': {
                'sale_total': float,    # suma de SO únicas
                'inv_total': float,     # suma facturas (out_invoice)
                'refund_total': float,  # suma notas de crédito (out_refund, valores negativos)
                'net_total': float,     # inv_total + refund_total
                'currency': res.currency,
            },
            'by_term': [
                {'label': 'CONTADO', 'amount': 123.0, 'currency': ...},
                {'label': '15 días', 'amount': 456.0, 'currency': ...},
                ...
            ]
          }
        """
        self.ensure_one()

        lines = self._get_valuation_lines()

        # Sumar SO únicas (evita duplicar cuando hay múltiples facturas por picking)
        sale_seen = set()
        sale_total_sum = 0.0
        currency = None
        term_buckets = {}  # label -> amount

        for l in lines:
            sale_name = (l.get('sale_name') or '').strip()
            if sale_name and sale_name not in sale_seen:
                sale_seen.add(sale_name)
                sale_total_sum += float(l.get('sale_total') or 0.0)
                currency = currency or l.get('sale_currency') or l.get('currency')

                # Plazo de pago: si tenemos sale, usamos payment_term_id; si no, caemos a CONTADO
                label = 'CONTADO'
                try:
                    picking = l.get('picking')
                    sale = getattr(picking, 'sale_id', False) or False
                    if not sale and getattr(picking, 'origin', False):
                        so_name = self._extract_sale_name_from_origin(picking.origin)
                        if so_name:
                            sale = self.env['sale.order'].search([('name', '=', so_name)], limit=1)
                    if sale and getattr(sale, 'payment_term_id', False):
                        pt = sale.payment_term_id
                        # Preferimos el nombre del término (ej. "15 días", "30 días", "Contado", etc.)
                        if getattr(pt, 'name', False):
                            label = pt.name
                        days = 0
                        try:
                            days = max(pt.line_ids.mapped('days') or [0])
                        except Exception:
                            days = 0
                        # Si no hay nombre usable, caemos a días máximos
                        if not label or label == 'CONTADO':
                            if days and days > 0:
                                label = f'{days} días'
                            else:
                                label = 'CONTADO'
                except Exception:
                    label = 'CONTADO'

                term_buckets[label] = term_buckets.get(label, 0.0) + float(l.get('sale_total') or 0.0)

        inv_total = 0.0
        refund_total = 0.0
        for l in lines:
            inv = l.get('invoice')
            if not inv:
                continue
            # inv es recordset en servidor; si viniera como False no entra.
            try:
                mt = inv.move_type
            except Exception:
                mt = ''
            amt = float(l.get('amount_total') or 0.0)
            if mt == 'out_refund':
                refund_total += amt  # suele venir negativo (signed)
            else:
                inv_total += amt

        by_term = [{'label': k, 'amount': v, 'currency': currency} for k, v in sorted(term_buckets.items(), key=lambda kv: kv[0])]
        totals = {
            'sale_total': sale_total_sum,
            'inv_total': inv_total,
            'refund_total': refund_total,
            'net_total': inv_total + refund_total,
            'currency': currency,
        }
        return {'lines': lines, 'totals': totals, 'by_term': by_term}

    def _pretty_qty_for_display(self, n):
        """Cantidad legible: entero sin .0; si no, hasta 4 decimales sin ceros finales."""
        n = float(n)
        if abs(n - round(n)) < 1e-6:
            return str(int(round(n)))
        s = f'{n:.4f}'.rstrip('0').rstrip('.')
        return s

    def _best_packaging_from_recordset(self, packaging_rs):
        """
        Elige embalaje: mayor qty (bulto típico), desempate por sequence menor.
        Devuelve (unidades_por_bulto, registro product.packaging o None).
        """
        if not packaging_rs:
            return 0.0, None
        packs = sorted(
            packaging_rs,
            key=lambda p: ((p.qty or 0), -(getattr(p, 'sequence', None) or 0)),
            reverse=True,
        )
        for p in packs:
            q = p.qty or 0
            if q > 0:
                return float(q), p
        return 0.0, None

    def _best_packaging_for_product(self, product):
        """
        Embalaje para cálculo de bultos.

        En Odoo 18, ``product.template.packaging_ids`` solo se rellena si la plantilla
        tiene **una sola variante**; si hay varias, queda vacío aunque las variantes
        tengan embalajes. Por eso se prioriza ``product.product.packaging_ids``.
        """
        if not product:
            return 0.0, None
        pq, pkg = self._best_packaging_from_recordset(product.packaging_ids)
        if pq > 0:
            return pq, pkg
        pt = product.product_tmpl_id
        if pt:
            pq, pkg = self._best_packaging_from_recordset(pt.packaging_ids)
            if pq > 0:
                return pq, pkg
        return 0.0, None

    def _uom_largest_bulto_in_category(self, uom_category):
        """
        UdM de la misma categoría con mayor factor_inv (>1), típico 'bulto'.

        No usar ``uom.uom.search()`` aquí: en Odoo 18 EE el modelo puede tener
        ``_order`` con ``factor_inv`` (no almacenado) y el ORM revienta al armar SQL.
        Se leen solo IDs por SQL y se hace ``browse`` + filtro en Python.
        """
        if not uom_category:
            return self.env['uom.uom']
        Uom = self.env['uom.uom']
        self.env.cr.execute(
            "SELECT id FROM uom_uom WHERE category_id = %s AND active",
            (uom_category.id,),
        )
        ids = [row[0] for row in self.env.cr.fetchall()]
        if not ids:
            return Uom
        cands = Uom.browse(ids)
        cands = cands.filtered(lambda u: (u.factor_inv or 0) > 1)
        if not cands:
            return Uom
        return max(cands, key=lambda u: u.factor_inv or 0)

    def _product_units_per_bulto_package(self, product):
        """Unidades por bulto/embalaje (misma lógica que la consolidación) para texto TOTAL."""
        if not product or not product.product_tmpl_id:
            return 0.0
        pq, _pkg = self._best_packaging_for_product(product)
        if pq > 0:
            return pq
        pt = product.product_tmpl_id
        if pt.uom_po_id and pt.uom_po_id != pt.uom_id:
            fi = getattr(pt.uom_po_id, 'factor_inv', 0) or 0
            if fi > 1:
                return float(fi)
        if pt.uom_id:
            fi = getattr(pt.uom_id, 'factor_inv', 0) or 0
            if fi > 1:
                return float(fi)
        if pt.uom_id and pt.uom_id.category_id:
            bulto_uom_cat = self._uom_largest_bulto_in_category(pt.uom_id.category_id)
            if bulto_uom_cat:
                return float(bulto_uom_cat.factor_inv or 0)
        return 0.0

    def _format_bulto_uom_display(self, qty_bultos, label):
        """Cuando la línea ya va en UdM bulto y no hay factor a unidades: bultos enteros + fracción."""
        label = (label or '').strip() or 'bultos'
        q = float(qty_bultos)
        full = int(math.floor(q + 1e-9))
        rem = round(q - full, 6)
        if abs(rem) < 1e-5:
            rem = 0.0

        def wb(n):
            return 'bulto' if n == 1 else 'bultos'

        if full == 0 and rem == 0:
            return '-'
        if rem == 0:
            return f'{full} {wb(full)} ({label})'
        rs = self._pretty_qty_for_display(rem)
        return f'{full} {wb(full)} + {rs} {label}'

    def _format_total_display_for_line(self, line):
        """
        Texto para columna TOTAL: bultos enteros + unidades sueltas según demanda OV.
        Ej.: 30 uds, bulto x20 -> '1 bulto + 10 Unidades (x20)'.
        """
        if not isinstance(line, dict):
            try:
                line = dict(line)
            except (TypeError, ValueError, AttributeError):
                return '-'
        product = line.get('product')
        uom_name = (line.get('uom_name') or '').strip() or 'unidades'
        bulto_label = (line.get('bulto_name') or '').strip()
        qty_line = float(line.get('demand_qty') or 0)

        if qty_line <= 0:
            return '-'

        upb = float(line.get('units_per_bulto') or 0)
        qty_units = qty_line

        if line.get('qty_already_in_bultos'):
            upb_pkg = self._product_units_per_bulto_package(product)
            if upb_pkg > 0:
                qty_units = qty_line * upb_pkg
                upb = upb_pkg
            else:
                return self._format_bulto_uom_display(qty_line, bulto_label)

        if upb <= 0 and product:
            upb = float(self._product_units_per_bulto_package(product) or 0)

        if upb <= 0:
            # Sin embalaje/UdM de bulto en ficha: el operario igual necesita ver qué llevarse
            return f'{self._pretty_qty_for_display(qty_line)} {uom_name}'

        full = int(math.floor(qty_units / upb + 1e-9))
        remainder = qty_units - full * upb
        remainder = round(remainder, 6)
        if abs(remainder) < 1e-5:
            remainder = 0.0

        x_hint = ''
        if abs(upb - int(upb)) < 1e-6:
            x_hint = f' (x{int(upb)})'
        else:
            x_hint = f' (x{self._pretty_qty_for_display(upb)})'

        def wb(n):
            return 'bulto' if n == 1 else 'bultos'

        if full == 0:
            if remainder == 0:
                return '-'
            u_part = self._pretty_qty_for_display(remainder)
            return f'0 bultos + {u_part} {uom_name}{x_hint}'

        if remainder == 0:
            return f'{full} {wb(full)}{x_hint}'

        u_part = self._pretty_qty_for_display(remainder)
        return f'{full} {wb(full)} + {u_part} {uom_name}{x_hint}'

    def _nakel_move_demand_qty(self, move):
        """Demanda OV del move (misma lógica que nakel_report_picking en PICK)."""
        if not move:
            return 0.0
        sale_line = getattr(move, 'sale_line_id', False) or False
        if sale_line:
            return float(sale_line.product_uom_qty or 0.0)
        return float(move.product_uom_qty or 0.0)

    def _get_consolidated_lines(self):
        """
        Consolidates move lines from all pickings in the batch.
        Groups by product, lot, package, source location and destination location.
        Returns a list of consolidated line dictionaries.

        Uses move_line_ids when available (detailed operations).
        Falls back to move_ids when move_line_ids is empty (e.g. pickings not yet checked).
        """
        self.ensure_one()

        # Dictionary to accumulate quantities
        # Key: (product_id, lot_id, package_id, location_id, location_dest_id)
        consolidated = defaultdict(lambda: {
            'product': None,
            'product_name': '',
            'product_code': '',
            # PLU para picking / escáner: EAN en `barcode` (en Nakel `default_code` es ref. interna)
            'product_plu': '',
            'categ_id': None,
            'categ_name': '',
            'lot': None,
            'lot_name': '',
            'package': None,
            'package_name': '',
            'result_package': None,
            'result_package_name': '',
            'bulto_name': '',  # Nombre del embalaje/bulto del producto (ej. "Caja x 12")
            'bulto_qty': 0.0,  # Cantidad por bulto
            'location': None,
            'location_name': '',
            'location_dest': None,
            'location_dest_name': '',
            'quantity': 0.0,
            'demand_qty': 0.0,
            'move_demand_seen': set(),
            'uom': None,
            'uom_name': '',
            'picking_ids': [],
            'picking_names': [],
        })

        # Iterate through all pickings in the batch
        for picking in self.picking_ids:
            # Prefer move_line_ids (detailed operations); fallback to move_ids if empty
            lines_to_process = list(picking.move_line_ids) if picking.move_line_ids else []

            if not lines_to_process:
                # Fallback: use move_ids when move_line_ids is empty (pickings not yet checked)
                for move in picking.move_ids:
                    if not move.product_uom_qty:
                        continue
                    # Build pseudo move_line from move (no lot/package info until operations exist)
                    pseudo = type('PseudoMoveLine', (), {
                        'product_id': move.product_id,
                        'move_id': move,
                        'lot_id': None,
                        'package_id': None,
                        'result_package_id': None,
                        'location_id': move.location_id,
                        'location_dest_id': move.location_dest_id,
                        'quantity': move.product_uom_qty,
                        'product_uom_id': move.product_uom,
                        'product_packaging_id': getattr(move, 'product_packaging_id', None),
                    })()
                    lines_to_process.append(pseudo)

            for move_line in lines_to_process:
                # NO ignorar quantity=0: si una ola/lote tiene faltante de stock,
                # queremos que la línea figure en el PDF para hacer visible el problema.
                # (Antes: quantity=0 hacía que el producto "desaparezca" del consolidado.)
                if move_line.quantity is None:
                    continue

                # Create the grouping key
                key = (
                    move_line.product_id.id,
                    move_line.lot_id.id if move_line.lot_id else False,
                    move_line.package_id.id if move_line.package_id else False,
                    move_line.location_id.id,
                    move_line.location_dest_id.id,
                )

                # Initialize or update the consolidated data
                if consolidated[key]['product'] is None:
                    product = move_line.product_id
                    line_uom = move_line.product_uom_id
                    categ = product.categ_id if product else None
                    categ_name = ''
                    try:
                        # complete_name suele ser más útil (Jerarquía: "Almacén / Bebidas / Gaseosas")
                        categ_name = (categ.complete_name or categ.display_name or categ.name) if categ else ''
                    except Exception:
                        categ_name = (categ.display_name or categ.name) if categ else ''
                    # Calcular bultos: cantidad en UdM de bulto (ej. "Bulto x40") para que el recolector
                    # sepa cuántas cajas/bultos cerrados tomar sin contar unidades sueltas
                    bulto_name = ''
                    bulto_qty = 0.0

                    # Buscar UdM de bulto: uom_po_id (compra) o packaging - para que recolector
                    # sepa cuántas cajas cerradas tomar sin abrirlas para contar unidades
                    bulto_uom = None
                    units_per_bulto = 0.0
                    qty_already_in_bultos = False  # True si quantity está en bultos (no en unidades)
                    if product.product_tmpl_id:
                        pt = product.product_tmpl_id
                        line_uom = move_line.product_uom_id
                        # Si la línea ya está en UdM de bulto (ej. Bulto x40), quantity ya son bultos
                        try:
                            uom_factor = getattr(line_uom, 'factor_inv', 1) or 1
                            if uom_factor > 1:
                                bulto_name = line_uom.name or ''
                                qty_already_in_bultos = True
                                units_per_bulto = 1  # Para que bulto_qty = quantity en post-proc
                        except Exception:
                            pass
                        # Embalaje explícito en la línea de movimiento (Odoo estándar)
                        if not bulto_name:
                            pkg_line = getattr(move_line, 'product_packaging_id', None)
                            if pkg_line:
                                pq = pkg_line.qty or 0
                                if pq > 0:
                                    bulto_name = pkg_line.name or ('x %.0f' % pq)
                                    units_per_bulto = float(pq)
                        # Si no: buscar uom_po_id (UdM compra, ej. "Bulto x40")
                        if not bulto_name and pt.uom_po_id and pt.uom_po_id != pt.uom_id:
                            try:
                                units_per_bulto = getattr(pt.uom_po_id, 'factor_inv', 0) or 0
                                if units_per_bulto > 1:
                                    bulto_uom = pt.uom_po_id
                                    bulto_name = bulto_uom.name or ''
                            except Exception:
                                pass
                        # Fallback: uom_id del producto si ya es bulto (ej. producto vendido por bulto)
                        if not bulto_name and pt.uom_id:
                            try:
                                uom_factor = getattr(pt.uom_id, 'factor_inv', 0) or 0
                                if uom_factor > 1:
                                    bulto_name = pt.uom_id.name or ''
                                    units_per_bulto = uom_factor
                            except Exception:
                                pass
                        # Fallback: embalajes (variante primero; plantilla sola falla con >1 variante en Odoo 18)
                        if not bulto_name:
                            pq, pkg = self._best_packaging_for_product(product)
                            if pq > 0:
                                units_per_bulto = pq
                                bulto_name = (pkg.name if pkg else '') or ('x %.0f' % pq)
                        # Fallback: buscar UdM tipo bulto en la categoría del producto
                        if not bulto_name and pt.uom_id and pt.uom_id.category_id:
                            try:
                                bulto_uom_cat = self._uom_largest_bulto_in_category(pt.uom_id.category_id)
                                if bulto_uom_cat:
                                    bulto_name = bulto_uom_cat.name or ''
                                    units_per_bulto = bulto_uom_cat.factor_inv or 0
                            except Exception:
                                pass

                    _bar = (getattr(product, 'barcode', None) or '').strip()
                    _ref = (product.default_code or '').strip()
                    consolidated[key].update({
                        'product': product,
                        'product_name': product.display_name,
                        'product_code': product.default_code or '',
                        'product_plu': _bar or _ref,
                        'categ_id': categ,
                        'categ_name': categ_name or '',
                        'lot': move_line.lot_id,
                        'lot_name': move_line.lot_id.name if move_line.lot_id else '',
                        'package': move_line.package_id,
                        'package_name': move_line.package_id.name if move_line.package_id else '',
                        'result_package': move_line.result_package_id,
                        'result_package_name': move_line.result_package_id.name if move_line.result_package_id else '',
                        'bulto_name': bulto_name,
                        'bulto_qty': bulto_qty,
                        'units_per_bulto': units_per_bulto,
                        'qty_already_in_bultos': qty_already_in_bultos,
                        'bulto_uom': bulto_uom,
                        'location': move_line.location_id,
                        'location_name': move_line.location_id.display_name,
                        'location_dest': move_line.location_dest_id,
                        'location_dest_name': move_line.location_dest_id.display_name,
                        'uom': move_line.product_uom_id,
                        'uom_name': move_line.product_uom_id.name,
                    })

                # Accumulate quantity
                consolidated[key]['quantity'] += move_line.quantity

                move = getattr(move_line, 'move_id', False) or False
                move_id = move.id if move else False
                if move_id and move_id not in consolidated[key]['move_demand_seen']:
                    consolidated[key]['move_demand_seen'].add(move_id)
                    consolidated[key]['demand_qty'] += self._nakel_move_demand_qty(move)

                # Track which pickings contributed to this line
                if picking.id not in consolidated[key]['picking_ids']:
                    consolidated[key]['picking_ids'].append(picking.id)
                    consolidated[key]['picking_names'].append(picking.name)

        # Convert to sorted list y asegurar que todas las líneas tengan bulto_name/bulto_qty
        result = sorted(
            consolidated.values(),
            key=lambda x: (
                x['location_name'],
                x['location_dest_name'],
                (x.get('categ_name') or ''),
                x['product_name'],
                x['lot_name'],
            )
        )
        for line in result:
            line.pop('move_demand_seen', None)
            line.setdefault('demand_qty', 0.0)
            line.setdefault('bulto_name', '')
            line.setdefault('bulto_qty', 0.0)
            line.setdefault('units_per_bulto', 0.0)
            line.setdefault('qty_already_in_bultos', False)
            line.setdefault('categ_name', '')
            if not line.get('product_plu') and line.get('product'):
                p = line['product']
                line['product_plu'] = (
                    (getattr(p, 'barcode', None) or '').strip() or (p.default_code or '').strip()
                )
            # Calcular cuántos bultos representa la demanda OV (para el recolector)
            qty = line.get('demand_qty', 0)
            if line.get('qty_already_in_bultos'):
                line['bulto_qty'] = round(qty, 2)  # demanda ya está en bultos
            else:
                units_per_bulto = line.get('units_per_bulto') or 0
                if units_per_bulto > 0 and qty > 0:
                    line['bulto_qty'] = round(qty / units_per_bulto, 2)
                else:
                    line['bulto_qty'] = 0.0
            td = self._format_total_display_for_line(line)
            qty = float(line.get('demand_qty') or 0)
            if qty > 0 and td == '-':
                td = f'{self._pretty_qty_for_display(qty)} {line.get("uom_name") or "unidades"}'
            line['total_display'] = td

        return result

    def _get_consolidated_lines_by_product(self):
        """
        Alternative consolidation: only by product (no lot/package/location detail).
        This is useful for a simple summary view.
        """
        self.ensure_one()

        consolidated = defaultdict(lambda: {
            'product': None,
            'product_name': '',
            'product_code': '',
            'product_plu': '',
            'quantity': 0.0,
            'uom': None,
            'uom_name': '',
        })

        for picking in self.picking_ids:
            for move_line in picking.move_line_ids:
                # Ver comentario en _get_consolidated_lines(): mantener líneas con quantity=0
                if move_line.quantity is None:
                    continue

                key = move_line.product_id.id

                if consolidated[key]['product'] is None:
                    p = move_line.product_id
                    _b = (getattr(p, 'barcode', None) or '').strip()
                    _r = (p.default_code or '').strip()
                    consolidated[key].update({
                        'product': p,
                        'product_name': p.display_name,
                        'product_code': p.default_code or '',
                        'product_plu': _b or _r,
                        'uom': move_line.product_uom_id,
                        'uom_name': move_line.product_uom_id.name,
                    })

                consolidated[key]['quantity'] += move_line.quantity

        result = sorted(
            consolidated.values(),
            key=lambda x: x['product_name']
        )

        return result

    def _generate_barcode_image(self, value, barcode_type='Code128', width=600, height=100):
        """
        Generate a barcode image as base64 string for embedding in PDF reports.

        :param value: The value to encode in the barcode
        :param barcode_type: Type of barcode (default: Code128)
        :param width: Width in pixels
        :param height: Height in pixels
        :return: base64 encoded image string with data URI prefix
        """
        if not value:
            return ''

        try:
            # Try using python-barcode library
            import barcode
            from barcode.writer import ImageWriter

            # Create barcode instance
            barcode_class = barcode.get_barcode_class(barcode_type.lower())
            barcode_instance = barcode_class(str(value), writer=ImageWriter())

            # Generate barcode to BytesIO buffer (sin texto debajo para evitar deformación en PDF)
            buffer = io.BytesIO()
            opts = {
                'module_width': 0.3,
                'module_height': 10.0,
                'quiet_zone': 2.0,
                'font_size': 0,  # Suprime texto debajo (documentación python-barcode)
                'write_text': False,  # Sin número debajo - evita solapamiento
            }
            try:
                barcode_instance.write(buffer, options=opts)
            except (TypeError, KeyError):
                buffer = io.BytesIO()
                opts.pop('write_text', None)
                barcode_instance.write(buffer, options=opts)

            # Get image data and encode to base64
            buffer.seek(0)
            barcode_image = buffer.read()

            if barcode_image:
                # Convert to base64 with data URI
                return 'data:image/png;base64,' + base64.b64encode(barcode_image).decode('utf-8')

        except ImportError:
            # If python-barcode is not available, try reportlab
            try:
                from reportlab.graphics.barcode import code128
                from reportlab.lib.units import mm
                from reportlab.graphics import renderPM

                # Create barcode
                barcode_obj = code128.Code128(str(value), barHeight=15*mm, barWidth=0.8)

                # Render to image
                barcode_image = renderPM.drawToString(barcode_obj, fmt='PNG')

                if barcode_image:
                    return 'data:image/png;base64,' + base64.b64encode(barcode_image).decode('utf-8')

            except Exception as e:
                import logging
                _logger = logging.getLogger(__name__)
                _logger.warning(f'Error generating barcode with reportlab for value {value}: {str(e)}')

        except Exception as e:
            # Log the error but don't break the report
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning(f'Error generating barcode for value {value}: {str(e)}')

        return ''
