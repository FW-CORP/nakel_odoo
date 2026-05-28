from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ai_service_url = fields.Char(
        string='URL Servicio IA',
        help='URL del servicio de matching IA (ej: http://192.168.1.10:8001)',
        config_parameter='nakel_supplier_pricelist.ai_service_url',
    )
    ai_default_vat_rate = fields.Float(
        string='IVA por defecto (%)',
        default=21.0,
        config_parameter='nakel_supplier_pricelist.default_vat_rate',
    )
    ai_auto_apply_threshold = fields.Integer(
        string='Confianza mínima para auto-aplicar (%)',
        default=90,
        help='Líneas con confianza >= este valor se marcan como match automático',
        config_parameter='nakel_supplier_pricelist.auto_apply_threshold',
    )
