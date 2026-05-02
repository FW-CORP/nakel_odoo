from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    x_flete_percent = fields.Float(
        string="Recargo flete (%)",
        help="Porcentaje de recargo por flete a aplicar sobre el precio unitario de las líneas de producto."
    )

    def action_apply_freight_markup(self):
        for order in self:
            pct = order.x_flete_percent or 0.0
            if pct < 0.0:
                raise ValidationError(_("El porcentaje de flete no puede ser negativo."))
            factor = 1.0 + (pct / 100.0)
            lines = order.order_line.filtered(lambda l: not l.display_type and l.product_id and l.price_unit >= 0.0)
            for line in lines:
                base = line.x_price_unit_base or line.price_unit
                # Guardamos el precio base la primera vez
                if not line.x_price_unit_base:
                    line.x_price_unit_base = base
                # Recalcular siempre desde el base para que sea idempotente
                line.price_unit = line.x_price_unit_base * factor

    def action_reset_freight_markup(self):
        for order in self:
            lines = order.order_line.filtered(lambda l: l.x_price_unit_base and not l.display_type)
            for line in lines:
                line.price_unit = line.x_price_unit_base
                line.x_price_unit_base = 0.0

class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    x_price_unit_base = fields.Float(
        string="Precio base (sin flete)",
        help="Precio unitario antes de aplicar el recargo de flete. Permite recalcular o revertir el recargo.",
        default=0.0
    )