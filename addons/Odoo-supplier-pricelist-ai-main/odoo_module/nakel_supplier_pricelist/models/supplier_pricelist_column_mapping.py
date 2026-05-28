from odoo import models, fields


class SupplierPricelistColumnMapping(models.Model):
    """Memoria del mapeo de columnas confirmado para un (proveedor, formato).

    Cuando un proveedor envía su lista de precios siempre con la misma
    estructura de columnas, el usuario solo configura una vez cuál columna es
    el "precio final" (y cuál es nombre, código, etc.). Esa elección se guarda
    acá indexada por (partner_id, column_signature).

    `column_signature` es un hash de los nombres+orden de las columnas del
    archivo. Si el proveedor cambia el formato (nueva columna, orden distinto,
    rename), la signature no matchea y el sistema fuerza re-confirmación.

    NOTA: la generación de la signature y el wizard de selección manual son
    fase 2. Este modelo queda preparado para esa funcionalidad y al mismo
    tiempo se usa hoy para detectar cambios de formato vs la última lista
    cargada (si el AI service devuelve la signature).
    """
    _name = 'supplier.pricelist.column.mapping'
    _description = 'Mapeo de columnas por proveedor + formato'
    _order = 'partner_id, create_date desc'

    partner_id = fields.Many2one(
        'res.partner',
        string='Proveedor',
        required=True,
        ondelete='cascade',
        index=True,
    )
    column_signature = fields.Char(
        string='Signature del formato',
        required=True,
        index=True,
        help='Hash de los nombres y orden de las columnas del archivo. Permite '
             'detectar cuándo el proveedor cambia el formato de la lista.',
    )
    detected_columns = fields.Text(
        string='Columnas detectadas',
        help='JSON con la lista de nombres de columnas tal como vinieron en '
             'el archivo. Útil para mostrar al usuario qué cambió.',
    )

    # Roles por columna (mapeo confirmado por el usuario)
    # Guardamos como JSON simple: { "col_label": "field_role", ... }
    mapping_json = fields.Text(
        string='Mapeo de roles',
        help='JSON con la asignación de columna → campo lógico '
             '(price_final / name / barcode / supplier_code / unit_count / ignore).',
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
        default=0,
        help='Cuántas listas se procesaron con este mapeo.',
    )
    notes = fields.Text(string='Notas')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            'unique_partner_signature',
            'UNIQUE(partner_id, column_signature)',
            'Ya existe un mapeo guardado para este proveedor y formato.',
        )
    ]
