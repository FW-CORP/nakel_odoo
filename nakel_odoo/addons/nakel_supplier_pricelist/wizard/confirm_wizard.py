import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SupplierPricelistConfirmWizard(models.TransientModel):
    """Wizard para confirmar (o corregir) el match de un producto de proveedor.

    Se abre cuando el usuario hace clic en "Confirmar" sobre una línea en
    estado 'review' o 'no_match'. Permite ver la comparativa de precios y
    seleccionar/cambiar el producto Odoo antes de guardar en la memoria de
    matches.
    """
    _name = 'supplier.pricelist.confirm.wizard'
    _description = 'Confirmar match proveedor ↔ producto'

    line_id = fields.Many2one(
        'supplier.pricelist.import.line',
        string='Línea',
        required=True,
        ondelete='cascade',
    )

    # ── Info del proveedor (solo lectura) ────────────────────────────────────
    supplier_product_name = fields.Char(
        related='line_id.supplier_product_name',
        string='Producto (proveedor)',
        readonly=True,
    )
    supplier_presentation = fields.Char(
        related='line_id.supplier_presentation',
        string='Presentación',
        readonly=True,
    )
    price_with_vat = fields.Float(
        related='line_id.price_with_vat',
        string='Precio c/IVA',
        readonly=True,
        digits=(12, 2),
    )
    price_without_vat = fields.Float(
        related='line_id.price_without_vat',
        string='Costo nuevo (s/IVA)',
        readonly=True,
        digits=(12, 2),
    )
    current_cost = fields.Float(
        related='line_id.current_cost',
        string='Costo actual en Odoo',
        readonly=True,
        digits=(12, 2),
    )
    cost_delta_pct = fields.Float(
        related='line_id.cost_delta_pct',
        string='Variación %',
        readonly=True,
        digits=(8, 1),
    )
    cost_delta_display = fields.Char(
        related='line_id.cost_delta_display',
        string='Δ%',
        readonly=True,
    )
    has_comparable_cost = fields.Boolean(
        related='line_id.has_comparable_cost',
        string='Tiene costo comparable',
        readonly=True,
    )
    match_status = fields.Selection(
        related='line_id.match_status',
        string='Estado actual',
        readonly=True,
    )
    alternative_ids = fields.Many2many(
        related='line_id.alternative_ids',
        string='Alternativas sugeridas',
        readonly=True,
    )

    # ── Selección del producto Odoo (editable) ───────────────────────────────
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Producto Odoo confirmado',
        required=True,
        domain=[('type', '!=', 'service')],
        help='Podés mantener la sugerencia o elegir otro producto.',
    )
    match_notes = fields.Char(
        string='Notas (opcional)',
        help='Observaciones sobre este match para referencia futura.',
    )

    # ── Default: precargar el producto sugerido ──────────────────────────────
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        line_id = res.get('line_id')
        if line_id:
            line = self.env['supplier.pricelist.import.line'].browse(line_id)
            if line.product_tmpl_id:
                res['product_tmpl_id'] = line.product_tmpl_id.id
        return res

    # ── Acciones ─────────────────────────────────────────────────────────────

    def action_confirm(self):
        """Confirma el match, guarda en memoria y cierra el wizard."""
        self.ensure_one()
        if not self.product_tmpl_id:
            raise UserError(_('Seleccioná un producto antes de confirmar.'))

        self.line_id.write({
            'product_tmpl_id': self.product_tmpl_id.id,
            'match_status': 'confirmed',
            'match_notes': self.match_notes or self.line_id.match_notes,
        })
        self.line_id._save_mapping()

        _logger.info(
            'Match confirmado vía wizard: "%s" → %s (import #%s)',
            self.line_id.supplier_product_name,
            self.product_tmpl_id.name,
            self.line_id.import_id.id,
        )
        return {'type': 'ir.actions.act_window_close'}

    def action_confirm_and_apply(self):
        """Confirma el match Y aplica el costo al producto de inmediato."""
        self.ensure_one()
        self.action_confirm()
        self.line_id._apply_cost()
        return {'type': 'ir.actions.act_window_close'}
