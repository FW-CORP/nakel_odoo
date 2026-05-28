from odoo import models, fields


class SupplierProductMapping(models.Model):
    """Memoria de matches confirmados por el usuario.

    Cada vez que el usuario confirma que el producto X del proveedor Y
    corresponde al producto Z en Odoo, se guarda aquí.
    La próxima vez que llegue una lista del mismo proveedor, el agente
    consulta esta tabla primero (matching exacto antes de usar embeddings).
    """
    _name = 'supplier.product.mapping'
    _description = 'Memoria de matches proveedor ↔ producto'
    _order = 'partner_id, times_used desc'
    _rec_name = 'supplier_product_name'

    partner_id = fields.Many2one(
        'res.partner',
        string='Proveedor',
        required=True,
        ondelete='cascade',
        index=True,
    )
    supplier_product_name = fields.Char(
        string='Nombre en lista proveedor',
        required=True,
        index=True,
    )
    supplier_product_code = fields.Char(
        string='Código del proveedor',
        help='Si la lista del proveedor incluye un código de producto',
    )
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Producto en Odoo',
        required=True,
        ondelete='cascade',
    )
    confirmed_by = fields.Many2one(
        'res.users',
        string='Confirmado por',
        default=lambda self: self.env.uid,
    )
    confirmed_date = fields.Datetime(
        string='Fecha de confirmación',
        default=fields.Datetime.now,
    )
    times_used = fields.Integer(
        string='Veces usado',
        default=1,
        help='Cuántas listas se procesaron usando este match',
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            'unique_partner_supplier_name',
            'UNIQUE(partner_id, supplier_product_name)',
            'Ya existe un mapping para este nombre de producto y proveedor.',
        )
    ]
