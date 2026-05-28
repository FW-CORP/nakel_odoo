import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SupplierPricelistImportLine(models.Model):
    _name = 'supplier.pricelist.import.line'
    _description = 'Línea de importación de lista de precios'
    _order = 'match_status asc, confidence_score desc'

    import_id = fields.Many2one(
        'supplier.pricelist.import',
        string='Importación',
        required=True,
        ondelete='cascade',
    )
    partner_id = fields.Many2one(
        related='import_id.partner_id',
        store=True,
        string='Proveedor',
    )

    # ── Datos del proveedor (tal cual vienen en la lista) ────────────────────
    supplier_product_name = fields.Char(
        string='Producto (proveedor)', required=True)
    supplier_presentation = fields.Char(string='Presentación')
    price_with_vat = fields.Float(string='Precio c/IVA', digits=(12, 2))
    vat_included = fields.Boolean(string='IVA incluido', default=True)
    vat_rate = fields.Float(string='% IVA', default=21.0)

    price_without_vat = fields.Float(
        string='Precio s/IVA (costo)',
        compute='_compute_price_without_vat',
        store=True,
        digits=(12, 2),
    )

    # ── Interpretación comercial del LLM ──────────────────────────────────────
    # Cuántas "unidades Odoo" hay en el price_with_vat del proveedor.
    # Ej: si el proveedor cobra $14.190 por un estuche de 12 alfajores y Odoo
    # guarda costo por 1 alfajor → unit_count=12, unit_price_with_vat=$1.182.
    unit_count = fields.Integer(
        string='Unidades por pack',
        default=1,
        help='Cuántas unidades Odoo equivalen al precio del proveedor. '
             'Ej: si el proveedor cobra por un pack de 12 alfajores y Odoo '
             'guarda costo por unidad, unit_count=12.',
    )
    unit_price_with_vat = fields.Float(
        string='Precio unitario c/IVA',
        digits=(12, 2),
        help='Precio del proveedor dividido por unit_count. Es el valor '
             'comparable directamente con el costo unitario de Odoo.',
    )
    unit_price_without_vat = fields.Float(
        string='Precio unitario s/IVA (costo)',
        compute='_compute_unit_price_without_vat',
        store=True,
        digits=(12, 2),
    )
    price_interpretation = fields.Char(
        string='Interpretación del precio',
        help='Explicación generada por el LLM de cómo se calculó unit_price '
             'a partir del precio crudo del proveedor.',
    )

    # ── Match con producto Odoo ───────────────────────────────────────────────
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Producto Odoo',
        domain=[('type', '!=', 'service')],
    )
    alternative_ids = fields.Many2many(
        'product.template',
        'pricelist_line_alt_rel',
        'line_id', 'product_id',
        string='Alternativas sugeridas',
    )
    confidence_score = fields.Integer(
        string='Confianza', default=0,
        help='0-100: porcentaje de confianza del match automático',
    )
    match_status = fields.Selection([
        ('auto', 'Match automático'),
        ('confirmed', 'Confirmado manualmente'),
        ('review', 'Requiere revisión'),
        ('no_match', 'Sin match'),
        ('rejected', 'Rechazado'),
    ], string='Estado del match', default='review', required=True)

    match_notes = fields.Char(string='Notas del agente')

    # ── Comparativa de precios ────────────────────────────────────────────────
    # `current_cost` ahora representa el supplierinfo.price del MISMO proveedor
    # de la importación (precio anterior de su última lista cargada). Si no hay
    # supplierinfo previo, fallback a standard_price.
    current_cost = fields.Float(
        string='Precio anterior del proveedor',
        compute='_compute_current_cost',
        digits=(12, 2),
        help='Precio unitario que tenía cargado este proveedor para este '
             'producto en su última lista (product.supplierinfo.price). '
             'Si es la primera vez que se carga este proveedor para este '
             'producto, muestra el standard_price como referencia.',
    )
    cost_delta_pct = fields.Float(
        string='Variación %',
        compute='_compute_current_cost',
        digits=(8, 1),  # admite valores grandes (>9999%) sin desbordar
    )
    has_comparable_cost = fields.Boolean(
        string='Tiene costo comparable',
        compute='_compute_current_cost',
        help='False si no hay costo previo confiable (producto sin compras o '
             'costo placeholder bogus). En ese caso la variación no aplica.',
    )
    cost_delta_display = fields.Char(
        string='Δ%',
        compute='_compute_current_cost',
        help='Variación porcentual lista para mostrar. "—" si no hay costo '
             'previo comparable.',
    )
    delta_color = fields.Char(
        compute='_compute_current_cost',
        string='Color variación',
    )

    # ── Estado de aplicación ─────────────────────────────────────────────────
    applied = fields.Boolean(string='Aplicado', default=False, readonly=True)
    applied_date = fields.Datetime(string='Fecha aplicación', readonly=True)

    # ── Compute ──────────────────────────────────────────────────────────────

    @api.depends('price_with_vat', 'vat_included', 'vat_rate')
    def _compute_price_without_vat(self):
        for rec in self:
            if rec.vat_included and rec.vat_rate:
                rec.price_without_vat = rec.price_with_vat / (1 + rec.vat_rate / 100)
            else:
                rec.price_without_vat = rec.price_with_vat

    @api.depends('unit_price_with_vat', 'vat_included', 'vat_rate')
    def _compute_unit_price_without_vat(self):
        for rec in self:
            if rec.vat_included and rec.vat_rate:
                rec.unit_price_without_vat = rec.unit_price_with_vat / (1 + rec.vat_rate / 100)
            else:
                rec.unit_price_without_vat = rec.unit_price_with_vat

    # Umbral mínimo de costo confiable. Valores menores se consideran
    # placeholders bogus (típico: 0, 0.01, 1) y la variación no se calcula.
    _MIN_VALID_COST = 1.0

    @api.depends('product_tmpl_id', 'partner_id', 'unit_price_without_vat',
                 'price_without_vat')
    def _compute_current_cost(self):
        """
        Calcula el costo actual del proveedor (de la última lista cargada en Odoo)
        y la variación vs el precio UNITARIO de la nueva lista.

        El `current_cost` se busca en `product.supplierinfo.price` del **mismo
        proveedor** que estamos importando. Esto da una métrica relevante:
        "cuánto subió/bajó ALEXVIAN respecto a su última lista".

        Si el producto no tiene supplierinfo para este partner (primera vez que
        se carga), hace fallback a `standard_price` con marca de
        `has_comparable_cost=False` (para mostrar "—" en lugar de un Δ% engañoso).

        Reglas de color del Δ%:
          - +30% o más  → danger  (suba grande, revisar urgente)
          - +10% a +30% → warning (suba moderada)
          - -10% a +10% → muted   (variación normal)
          - -10% o menos → success (baja, oportunidad)
        """
        for rec in self:
            if not rec.product_tmpl_id:
                rec.current_cost = 0.0
                rec.cost_delta_pct = 0.0
                rec.has_comparable_cost = False
                rec.cost_delta_display = '—'
                rec.delta_color = 'muted'
                continue

            # Buscamos supplierinfo del proveedor actual para este producto
            current = 0.0
            has_supplier_price = False
            if rec.partner_id:
                supplier = self.env['product.supplierinfo'].sudo().search([
                    ('partner_id', '=', rec.partner_id.id),
                    ('product_tmpl_id', '=', rec.product_tmpl_id.id),
                ], limit=1, order='sequence asc, min_qty desc')
                if supplier and supplier.price > self._MIN_VALID_COST:
                    current = supplier.price
                    has_supplier_price = True

            # Fallback: si no hay supplierinfo cargado, mostramos standard_price
            # como referencia (pero marcamos has_comparable_cost=False para que
            # la UI lo trate distinto).
            if not has_supplier_price:
                current = rec.product_tmpl_id.standard_price or 0.0
            rec.current_cost = current

            if current <= self._MIN_VALID_COST or not has_supplier_price:
                # Primera vez para este partner+producto, o costo placeholder:
                # no podemos calcular un Δ% significativo.
                rec.cost_delta_pct = 0.0
                rec.has_comparable_cost = False
                rec.cost_delta_display = '—' if not has_supplier_price else 'NUEVO'
                rec.delta_color = 'muted'
                continue

            # Usar el precio unitario (ya dividido por unit_count) para comparar
            # contra el supplierinfo.price del proveedor (que ya está por unidad).
            new_unit_cost = rec.unit_price_without_vat or rec.price_without_vat

            delta = ((new_unit_cost - current) / current) * 100.0
            rec.cost_delta_pct = delta
            rec.has_comparable_cost = True
            sign = '+' if delta > 0 else ''
            rec.cost_delta_display = f'{sign}{delta:.1f}%'

            if delta >= 30:
                rec.delta_color = 'danger'
            elif delta >= 10:
                rec.delta_color = 'warning'
            elif delta <= -10:
                rec.delta_color = 'success'
            else:
                rec.delta_color = 'muted'

    # ── Acciones ─────────────────────────────────────────────────────────────

    def action_confirm_match(self):
        """Abre el wizard de confirmación de match."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Confirmar match'),
            'res_model': 'supplier.pricelist.confirm.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_line_id': self.id,
            },
        }

    def action_reject(self):
        """El usuario rechaza este ítem (no se actualiza el costo)."""
        self.write({'match_status': 'rejected'})

    def action_apply_single(self):
        """Aplica el costo de esta línea individualmente."""
        self.ensure_one()
        self._apply_cost()

    def _effective_unit_cost_without_vat(self):
        """
        Devuelve el precio s/IVA que se va a aplicar como `supplierinfo.price`
        unitario en Odoo.

        Usa `unit_price_without_vat` (precio por unidad Odoo, calculado por el LLM
        a partir del precio crudo del proveedor dividido por unit_count). Si no
        está cargado, fallback al `price_without_vat` directo.

        Esto es CRÍTICO: si el proveedor cobra $14.190 por un estuche de 12
        alfajores, el `supplierinfo.price` debe ser $1.182 (el precio por alfajor),
        no $14.190 (el precio del estuche entero).
        """
        self.ensure_one()
        return self.unit_price_without_vat or self.price_without_vat

    def _apply_cost(self):
        """
        Aplica el costo importado de la lista del proveedor:

        1. Actualiza/crea `product.supplierinfo` con el precio unitario s/IVA
        2. Guarda el match en la memoria (`supplier.product.mapping`)
        3. Marca la línea como `applied=True`

        ❌ NO modifica `standard_price` (queda libre para el flujo FIFO contable).
        ❌ NO modifica `product.pricelist.item.fixed_price` directamente.

        Para que esto afecte los precios de venta automáticamente, instalar el
        módulo OCA `product_pricelist_supplierinfo` (disponible para Odoo 18) y
        configurar las pricelist con `base='supplier_price'` + markup deseado.
        Sin ese módulo OCA, este flujo solo cargará el costo del proveedor como
        referencia (sin impacto en precios de venta).
        """
        self.ensure_one()
        if not self.product_tmpl_id:
            return

        unit_cost = self._effective_unit_cost_without_vat()
        if unit_cost <= 0:
            raise UserError(
                _('El precio unitario calculado s/IVA es 0 o negativo para "%s". '
                  'Revisá el precio crudo y/o el unit_count.')
                % self.supplier_product_name)

        # 1. Actualiza o crea el supplierinfo con el precio unitario del proveedor
        previous_price = self._update_supplierinfo(unit_cost)

        # 2. Guarda match en memoria de aprendizaje
        self._save_mapping()

        # 3. Marca como aplicada
        self.write({
            'applied': True,
            'applied_date': fields.Datetime.now(),
        })

        _logger.info(
            'supplierinfo.price actualizado: %s (proveedor %s) → '
            '$%.2f/unidad (antes $%.2f, unit_count=%s, precio crudo $%.2f). '
            'standard_price NO modificado.',
            self.product_tmpl_id.name,
            self.partner_id.name,
            unit_cost,
            previous_price,
            self.unit_count or 1,
            self.price_without_vat,
        )

    def _update_supplierinfo(self, unit_cost=None):
        """
        Crea o actualiza el registro de product.supplierinfo con el precio
        UNITARIO del proveedor (no el precio crudo, ya dividido por unit_count).

        Si ya existe un supplierinfo para este (partner, producto), lo actualiza
        in-place. Si no, crea uno nuevo con sequence=10.

        Returns:
            float: el precio anterior (0 si no había), útil para logging.
        """
        if unit_cost is None:
            unit_cost = self._effective_unit_cost_without_vat()

        SupplierInfo = self.env['product.supplierinfo'].sudo()
        existing = SupplierInfo.search([
            ('partner_id', '=', self.partner_id.id),
            ('product_tmpl_id', '=', self.product_tmpl_id.id),
        ], limit=1)
        previous_price = existing.price if existing else 0.0
        vals = {
            'price': unit_cost,
            'product_name': self.supplier_product_name,
        }
        # Si el ítem del proveedor traía código (extraído por el parser
        # estructurado), también lo guardamos. Útil para próximas listas:
        # la capa 1 del matcher buscará por product_code antes que por nombre.
        if hasattr(self, 'supplier_product_code') and self.supplier_product_code:
            vals['product_code'] = self.supplier_product_code

        if existing:
            existing.write(vals)
        else:
            SupplierInfo.create({
                'partner_id': self.partner_id.id,
                'product_tmpl_id': self.product_tmpl_id.id,
                'sequence': 10,
                **vals,
            })
        return previous_price

    def _save_mapping(self):
        """Guarda el match confirmado en la tabla de memoria."""
        Mapping = self.env['supplier.product.mapping'].sudo()
        existing = Mapping.search([
            ('partner_id', '=', self.partner_id.id),
            ('supplier_product_name', '=', self.supplier_product_name),
        ], limit=1)
        if existing:
            existing.write({
                'product_tmpl_id': self.product_tmpl_id.id,
                'times_used': existing.times_used + 1,
            })
        else:
            Mapping.create({
                'partner_id': self.partner_id.id,
                'supplier_product_name': self.supplier_product_name,
                'product_tmpl_id': self.product_tmpl_id.id,
                'confirmed_by': self.env.uid,
                'times_used': 1,
            })
