from odoo import models, fields


class SupplierPricelistWarning(models.Model):
    """Aviso generado automáticamente por el sistema sobre una importación.

    Se usa para alertar al usuario antes de aplicar costos cuando se detectan
    síntomas de que el PDF/Excel del proveedor cambió de formato o cuando los
    precios saltan mucho respecto al histórico.

    Tipos:
      - format_changed: la signature de columnas cambió vs la última lista
                         del mismo proveedor.
      - price_anomaly:  alto % de líneas con variación de precio sospechosa
                         vs supplierinfo histórico.
      - rows_missing:   se cargaron muchos menos productos que en la lista
                         anterior del mismo proveedor.
      - parser_noise:   se detectaron líneas-basura (fechas, totales, IDs sin
                         nombre) en proporción anormal.
    """
    _name = 'supplier.pricelist.warning'
    _description = 'Aviso sobre importación de lista de proveedor'
    _order = 'severity desc, id desc'

    import_id = fields.Many2one(
        'supplier.pricelist.import',
        string='Importación',
        required=True,
        ondelete='cascade',
        index=True,
    )
    partner_id = fields.Many2one(
        related='import_id.partner_id',
        store=True,
        string='Proveedor',
    )

    type = fields.Selection([
        ('format_changed', 'Formato del archivo cambió'),
        ('price_anomaly', 'Anomalía de precios'),
        ('rows_missing', 'Faltan filas'),
        ('parser_noise', 'Ruido del parser'),
        ('column_unknown', 'Mapeo de columnas desconocido'),
    ], string='Tipo', required=True)

    severity = fields.Selection([
        ('info', 'Informativo'),
        ('warning', 'Advertencia'),
        ('critical', 'Crítico'),
    ], string='Severidad', required=True, default='warning')

    title = fields.Char(string='Título', required=True)
    message = fields.Text(string='Mensaje', required=True)
    suggested_action = fields.Text(string='Acción sugerida')

    acknowledged = fields.Boolean(
        string='Reconocido',
        default=False,
        help='Marcar como visto. Los avisos críticos sin reconocer bloquean '
             'la aplicación de costos.',
    )
    acknowledged_by = fields.Many2one('res.users', string='Reconocido por',
                                       readonly=True)
    acknowledged_date = fields.Datetime(string='Fecha de reconocimiento',
                                         readonly=True)

    def action_acknowledge(self):
        for rec in self:
            rec.write({
                'acknowledged': True,
                'acknowledged_by': self.env.uid,
                'acknowledged_date': fields.Datetime.now(),
            })
        return True
