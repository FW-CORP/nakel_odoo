import base64
import hashlib
import json
import logging
import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Umbrales de detección de anomalías. Configurables vía ir.config_parameter.
_DEFAULT_ANOMALY_LINE_THRESHOLD_PCT = 50.0  # Δ% por línea para flag individual
_DEFAULT_ANOMALY_BULK_THRESHOLD_PCT = 25.0  # % de líneas anómalas sobre total
                                             # para warning crítico
_DEFAULT_ROWS_MISSING_THRESHOLD_PCT = 40.0  # % de drop de filas vs última lista


class SupplierPricelistImport(models.Model):
    _name = 'supplier.pricelist.import'
    _description = 'Importación de Lista de Precios de Proveedor'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Referencia',
        required=True,
        copy=False,
        default=lambda self: _('Nueva importación'),
        tracking=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Proveedor',
        required=True,
        domain=[('supplier_rank', '>', 0)],
        tracking=True,
    )
    date = fields.Date(
        string='Fecha de lista',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    file = fields.Binary(
        string='Archivo de lista',
        required=True,
        attachment=True,
    )
    file_name = fields.Char(string='Nombre de archivo')
    file_type = fields.Selection([
        ('pdf', 'PDF'),
        ('excel', 'Excel (.xlsx / .xls)'),
        ('csv', 'CSV'),
        ('image', 'Imagen (JPG/PNG)'),
    ], string='Tipo de archivo', compute='_compute_file_type', store=True)

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('processing', 'Procesando IA...'),
        ('review', 'Revisión pendiente'),
        ('done', 'Aplicado'),
        ('cancelled', 'Cancelado'),
    ], string='Estado', default='draft', required=True, tracking=True)

    line_ids = fields.One2many(
        'supplier.pricelist.import.line',
        'import_id',
        string='Líneas',
    )

    # Estadísticas
    total_lines = fields.Integer(
        string='Total líneas', compute='_compute_stats', store=True)
    matched_auto = fields.Integer(
        string='Match automático', compute='_compute_stats', store=True)
    matched_review = fields.Integer(
        string='Requieren revisión', compute='_compute_stats', store=True)
    unmatched = fields.Integer(
        string='Sin match', compute='_compute_stats', store=True)
    applied_lines = fields.Integer(
        string='Aplicadas', compute='_compute_stats', store=True)

    # ── Signature del formato del archivo + mapeo de columnas ────────────────
    column_signature = fields.Char(
        string='Signature del formato',
        readonly=True,
        help='Hash de la estructura de columnas detectada en el archivo. '
             'Si cambia entre listas del mismo proveedor, indica cambio de '
             'formato y dispara un aviso.',
    )
    detected_columns_json = fields.Text(
        string='Columnas detectadas (JSON)',
        readonly=True,
    )
    column_mapping_id = fields.Many2one(
        'supplier.pricelist.column.mapping',
        string='Mapeo de columnas usado',
        readonly=True,
    )

    # ── Warnings ─────────────────────────────────────────────────────────────
    warning_ids = fields.One2many(
        'supplier.pricelist.warning',
        'import_id',
        string='Avisos',
    )
    warning_count = fields.Integer(
        string='Cantidad de avisos',
        compute='_compute_warning_stats',
        store=True,
    )
    critical_warning_count = fields.Integer(
        string='Avisos críticos',
        compute='_compute_warning_stats',
        store=True,
    )
    unacknowledged_critical_count = fields.Integer(
        string='Avisos críticos sin reconocer',
        compute='_compute_warning_stats',
        store=True,
    )
    has_blocking_warnings = fields.Boolean(
        string='Tiene avisos que bloquean',
        compute='_compute_warning_stats',
        store=True,
        help='True si hay avisos críticos sin reconocer. Bloquea "Aplicar costos".',
    )

    # ── Estadísticas de anomalías de precio ──────────────────────────────────
    anomaly_line_count = fields.Integer(
        string='Líneas con anomalía',
        compute='_compute_anomaly_stats',
        store=True,
        help='Líneas con variación absoluta > umbral configurado (default 50%).',
    )
    anomaly_pct = fields.Float(
        string='% líneas con anomalía',
        compute='_compute_anomaly_stats',
        store=True,
        digits=(5, 1),
    )
    comparable_line_count = fields.Integer(
        string='Líneas comparables',
        compute='_compute_anomaly_stats',
        store=True,
        help='Líneas que tienen costo previo del mismo proveedor (base para el %).',
    )

    notes = fields.Text(string='Notas')

    # ── Compute ──────────────────────────────────────────────────────────────

    @api.depends('file_name')
    def _compute_file_type(self):
        for rec in self:
            name = (rec.file_name or '').lower()
            if name.endswith('.pdf'):
                rec.file_type = 'pdf'
            elif name.endswith(('.xlsx', '.xls')):
                rec.file_type = 'excel'
            elif name.endswith('.csv'):
                rec.file_type = 'csv'
            elif name.endswith(('.jpg', '.jpeg', '.png')):
                rec.file_type = 'image'
            else:
                rec.file_type = 'pdf'

    @api.depends('line_ids', 'line_ids.match_status', 'line_ids.applied')
    def _compute_stats(self):
        for rec in self:
            lines = rec.line_ids
            rec.total_lines = len(lines)
            rec.matched_auto = len(
                lines.filtered(lambda l: l.match_status == 'auto'))
            rec.matched_review = len(
                lines.filtered(lambda l: l.match_status == 'review'))
            rec.unmatched = len(
                lines.filtered(lambda l: l.match_status == 'no_match'))
            rec.applied_lines = len(lines.filtered('applied'))

    @api.depends('warning_ids', 'warning_ids.severity',
                 'warning_ids.acknowledged')
    def _compute_warning_stats(self):
        for rec in self:
            warnings = rec.warning_ids
            rec.warning_count = len(warnings)
            critical = warnings.filtered(lambda w: w.severity == 'critical')
            rec.critical_warning_count = len(critical)
            unack = critical.filtered(lambda w: not w.acknowledged)
            rec.unacknowledged_critical_count = len(unack)
            rec.has_blocking_warnings = bool(unack)

    @api.depends('line_ids', 'line_ids.cost_delta_pct',
                 'line_ids.has_comparable_cost', 'line_ids.match_status')
    def _compute_anomaly_stats(self):
        # Umbral configurable
        ICP = self.env['ir.config_parameter'].sudo()
        line_threshold = float(ICP.get_param(
            'nakel_supplier_pricelist.anomaly_line_threshold_pct',
            default=_DEFAULT_ANOMALY_LINE_THRESHOLD_PCT))
        for rec in self:
            comparable = rec.line_ids.filtered(
                lambda l: l.has_comparable_cost
                and l.match_status in ('auto', 'confirmed', 'review')
            )
            rec.comparable_line_count = len(comparable)
            if not comparable:
                rec.anomaly_line_count = 0
                rec.anomaly_pct = 0.0
                continue
            anomalous = comparable.filtered(
                lambda l: abs(l.cost_delta_pct) >= line_threshold
            )
            rec.anomaly_line_count = len(anomalous)
            rec.anomaly_pct = (len(anomalous) / len(comparable)) * 100.0

    # ── Acciones ─────────────────────────────────────────────────────────────

    def action_process_ai(self):
        """Envía el archivo al servicio IA y crea las líneas con los matches."""
        self.ensure_one()
        if not self.file:
            raise UserError(_('Debe subir un archivo antes de procesar.'))

        ai_url = self.env['ir.config_parameter'].sudo().get_param(
            'nakel_supplier_pricelist.ai_service_url',
            default='http://localhost:8001'
        )

        # Prepara el catálogo de productos del proveedor desde supplierinfo
        catalog = self._get_product_catalog()

        # Llama al servicio IA
        self.write({'state': 'processing'})
        self.env.cr.commit()  # Guarda el estado para que el usuario lo vea

        try:
            payload = {
                'file_content': self.file.decode('utf-8') if isinstance(self.file, bytes) else self.file,
                'file_name': self.file_name,
                'partner_id': self.partner_id.id,
                'partner_name': self.partner_id.name,
                'catalog': catalog,
            }
            response = requests.post(
                f'{ai_url}/api/match',
                json=payload,
                timeout=600,
            )
            response.raise_for_status()
            result = response.json()
        except requests.exceptions.ConnectionError:
            self.write({'state': 'draft'})
            raise UserError(_(
                'No se pudo conectar al servicio IA en %s.\n'
                'Verifique que el servicio esté corriendo.'
            ) % ai_url)
        except requests.exceptions.Timeout:
            self.write({'state': 'draft'})
            raise UserError(_('El servicio IA tardó demasiado. Intente de nuevo.'))
        except Exception as e:
            self.write({'state': 'draft'})
            raise UserError(_('Error al procesar: %s') % str(e))

        # Borra líneas y warnings anteriores antes de crear los nuevos
        self.line_ids.unlink()
        self.warning_ids.unlink()

        # Signature del formato si el AI service la mandó. Si no, calcular
        # desde detected_columns si vinieron. Si tampoco, queda vacía y se
        # omite la detección de cambio de formato.
        sig = result.get('column_signature')
        detected_cols = result.get('detected_columns') or []
        if not sig and detected_cols:
            sig = self._compute_column_signature(detected_cols)
        if sig or detected_cols:
            self.write({
                'column_signature': sig or False,
                'detected_columns_json': json.dumps(detected_cols) if detected_cols else False,
            })

        for item in result.get('matches', []):
            unit_count = item.get('unit_count') or 1
            unit_price = item.get('unit_price')
            self.env['supplier.pricelist.import.line'].create({
                'import_id': self.id,
                'supplier_product_name': item.get('supplier_name', ''),
                'supplier_presentation': item.get('presentation', ''),
                'price_with_vat': item.get('price_with_vat', 0.0),
                'vat_included': item.get('vat_included', True),
                'product_tmpl_id': item.get('product_tmpl_id'),
                'confidence_score': item.get('confidence', 0),
                'match_status': item.get('match_status', 'no_match'),
                'match_notes': item.get('notes', ''),
                'alternative_ids': [(6, 0, item.get('alternative_product_ids', []))],
                # Interpretación comercial del LLM
                'unit_count': unit_count,
                'unit_price_with_vat': unit_price if unit_price is not None else item.get('price_with_vat', 0.0),
                'price_interpretation': item.get('price_interpretation', ''),
            })

        self.write({'state': 'review'})

        # Después de crear líneas y signature, correr el análisis de avisos
        self._analyze_and_generate_warnings()

        # Resumen para la notificación
        warn_msg = ''
        if self.critical_warning_count:
            warn_msg = _(
                '\n⚠ %d aviso(s) crítico(s). Revisar antes de aplicar costos.'
            ) % self.critical_warning_count
        elif self.warning_count:
            warn_msg = _('\nℹ %d aviso(s) generados.') % self.warning_count

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Procesamiento completado'),
                'message': _(
                    '%d productos encontrados. %d con match automático, '
                    '%d requieren revisión, %d sin match.'
                ) % (
                    self.total_lines,
                    self.matched_auto,
                    self.matched_review,
                    self.unmatched,
                ) + warn_msg,
                'type': 'warning' if self.critical_warning_count else 'success',
                'sticky': True,
            }
        }

    def action_apply_confirmed(self):
        """Aplica los costos de las líneas confirmadas."""
        self.ensure_one()

        # Bloqueo si hay avisos críticos sin reconocer
        if self.has_blocking_warnings:
            blocking = self.warning_ids.filtered(
                lambda w: w.severity == 'critical' and not w.acknowledged)
            titles = '\n  • '.join(blocking.mapped('title'))
            raise UserError(_(
                'No se pueden aplicar costos: hay %d aviso(s) crítico(s) '
                'sin reconocer.\n\n  • %s\n\n'
                'Abrí la pestaña "Avisos", revisalos y marcalos como reconocidos '
                'para continuar (o cancelá la importación si el formato del '
                'archivo cambió y prefiero reconfigurar).'
            ) % (self.unacknowledged_critical_count, titles))

        lines_to_apply = self.line_ids.filtered(
            lambda l: l.match_status in ('auto', 'confirmed')
            and l.product_tmpl_id
            and not l.applied
        )
        if not lines_to_apply:
            raise UserError(_('No hay líneas confirmadas para aplicar.'))

        applied = 0
        for line in lines_to_apply:
            line._apply_cost()
            applied += 1

        if all(self.line_ids.filtered(
                lambda l: l.match_status not in ('no_match',)).mapped('applied')):
            self.write({'state': 'done'})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Costos actualizados'),
                'message': _('%d productos actualizados correctamente.') % applied,
                'type': 'success',
            }
        }

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})
        self.line_ids.unlink()

    # ── Acciones de stat buttons (navegación a líneas filtradas) ──────────────

    def _action_open_lines(self, status_filter, title):
        """Abre las líneas filtradas por estado de match."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': 'supplier.pricelist.import.line',
            'view_mode': 'list',
            'domain': [('import_id', '=', self.id),
                       ('match_status', 'in', status_filter)],
            'context': {'default_import_id': self.id},
        }

    def action_view_auto(self):
        return self._action_open_lines(['auto'], _('Matches automáticos'))

    def action_view_review(self):
        return self._action_open_lines(['review'], _('Requieren revisión'))

    def action_view_no_match(self):
        return self._action_open_lines(['no_match'], _('Sin match'))

    def action_view_applied(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Costos aplicados'),
            'res_model': 'supplier.pricelist.import.line',
            'view_mode': 'list',
            'domain': [('import_id', '=', self.id), ('applied', '=', True)],
        }

    def action_reanalyze_warnings(self):
        """Re-corre el análisis de avisos sin re-procesar la IA.

        Útil cuando el usuario cambió manualmente algún match o cuando se
        ajustó el umbral de anomalías.
        """
        self.ensure_one()
        self.warning_ids.unlink()
        self._analyze_and_generate_warnings()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Análisis re-corrido'),
                'message': _('%d aviso(s) detectado(s).') % self.warning_count,
                'type': 'info',
            }
        }

    def action_view_warnings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Avisos de la importación'),
            'res_model': 'supplier.pricelist.warning',
            'view_mode': 'list,form',
            'domain': [('import_id', '=', self.id)],
            'context': {'default_import_id': self.id},
        }

    # ── Análisis y detección de problemas ────────────────────────────────────

    def _analyze_and_generate_warnings(self):
        """Corre todos los detectores y crea los warnings correspondientes.

        Llamar después de crear las líneas y poblar la signature.
        """
        self.ensure_one()
        self._detect_format_change()
        self._detect_price_anomalies()
        self._detect_rows_missing()
        self._detect_parser_noise()

    def _detect_format_change(self):
        """Si la column_signature actual no matchea con la última lista del
        mismo proveedor, genera un warning crítico.
        """
        self.ensure_one()
        if not self.column_signature:
            return  # AI service no mandó signature, no podemos chequear

        # Buscamos la última importación previa del mismo proveedor
        previous = self.search([
            ('partner_id', '=', self.partner_id.id),
            ('id', '!=', self.id),
            ('state', 'in', ('review', 'done')),
            ('column_signature', '!=', False),
        ], order='date desc, id desc', limit=1)

        if not previous:
            # Primera lista de este proveedor con signature: registramos
            # info pero no warning
            return

        if previous.column_signature == self.column_signature:
            return  # Mismo formato, todo OK

        # Diff legible: qué columnas se agregaron/quitaron/reordenaron
        prev_cols = []
        new_cols = []
        try:
            prev_cols = json.loads(previous.detected_columns_json or '[]')
        except Exception:
            pass
        try:
            new_cols = json.loads(self.detected_columns_json or '[]')
        except Exception:
            pass

        added = [c for c in new_cols if c not in prev_cols]
        removed = [c for c in prev_cols if c not in new_cols]
        diff_lines = []
        if added:
            diff_lines.append(_('Columnas nuevas: ') + ', '.join(added))
        if removed:
            diff_lines.append(_('Columnas que desaparecieron: ') + ', '.join(removed))
        if not diff_lines and prev_cols and new_cols:
            diff_lines.append(_('Mismas columnas pero en orden distinto.'))

        self.env['supplier.pricelist.warning'].create({
            'import_id': self.id,
            'type': 'format_changed',
            'severity': 'critical',
            'title': _('El formato del archivo cambió'),
            'message': _(
                'La estructura de columnas de este archivo es distinta a la '
                'de la última lista cargada de %(partner)s (fecha %(date)s).\n'
                '%(diff)s\n\n'
                'Esto puede causar que el sistema esté leyendo la columna '
                'de precios equivocada.'
            ) % {
                'partner': self.partner_id.name,
                'date': previous.date,
                'diff': '\n'.join(diff_lines) or _('(sin detalle)'),
            },
            'suggested_action': _(
                'Antes de aplicar costos: verificá manualmente que algunos '
                'precios coincidan con lo que esperás. Si están mal, cancelá '
                'la importación y avisá a soporte para reconfigurar el mapeo '
                'de columnas para este proveedor.'
            ),
        })

    def _detect_price_anomalies(self):
        """Genera warning si % de líneas con variación > umbral es alto."""
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        bulk_threshold = float(ICP.get_param(
            'nakel_supplier_pricelist.anomaly_bulk_threshold_pct',
            default=_DEFAULT_ANOMALY_BULK_THRESHOLD_PCT))

        if not self.comparable_line_count:
            return  # No hay base de comparación, no podemos detectar nada

        if self.anomaly_pct < bulk_threshold:
            # Pocas anomalías → no warning (cada línea ya tiene su Δ% visible)
            return

        # Ejemplos top: las 5 líneas con mayor delta absoluto
        anomalous_lines = self.line_ids.filtered(
            lambda l: l.has_comparable_cost
            and abs(l.cost_delta_pct) >= float(ICP.get_param(
                'nakel_supplier_pricelist.anomaly_line_threshold_pct',
                default=_DEFAULT_ANOMALY_LINE_THRESHOLD_PCT))
        ).sorted(key=lambda l: abs(l.cost_delta_pct), reverse=True)[:5]

        examples = '\n'.join([
            f'  • {l.product_tmpl_id.name}: ${l.current_cost:,.2f} → '
            f'${l.unit_price_without_vat:,.2f} ({l.cost_delta_display})'
            for l in anomalous_lines
        ])

        # Severidad: critical si >50% anómalas, warning si entre umbral y 50%
        severity = 'critical' if self.anomaly_pct >= 50.0 else 'warning'

        self.env['supplier.pricelist.warning'].create({
            'import_id': self.id,
            'type': 'price_anomaly',
            'severity': severity,
            'title': _('%(n)d de %(t)d líneas con variación >%(thr)s%%') % {
                'n': self.anomaly_line_count,
                't': self.comparable_line_count,
                'thr': int(ICP.get_param(
                    'nakel_supplier_pricelist.anomaly_line_threshold_pct',
                    default=_DEFAULT_ANOMALY_LINE_THRESHOLD_PCT)),
            },
            'message': _(
                '%(pct).1f%% de las líneas comparables muestran un cambio de '
                'precio significativo respecto a la última lista cargada de '
                'este proveedor.\n\n'
                'Ejemplos (top 5 por variación):\n%(examples)s'
            ) % {
                'pct': self.anomaly_pct,
                'examples': examples or _('(sin ejemplos disponibles)'),
            },
            'suggested_action': _(
                'Si es por aumento real de precios, reconocé este aviso y '
                'continuá.\n'
                'Si NO esperabas un cambio así, lo más probable es que la '
                'columna de precios leída sea la equivocada (típico: el '
                'proveedor cambió el formato del PDF y ahora se está leyendo '
                '"precio sin descuento" en vez de "precio final"). En ese '
                'caso, cancelá la importación.'
            ),
        })

    def _detect_rows_missing(self):
        """Warning si la cantidad de líneas bajó mucho respecto a la última lista."""
        self.ensure_one()
        if not self.total_lines:
            return

        previous = self.search([
            ('partner_id', '=', self.partner_id.id),
            ('id', '!=', self.id),
            ('state', 'in', ('review', 'done')),
            ('total_lines', '>', 0),
        ], order='date desc, id desc', limit=1)
        if not previous:
            return

        ICP = self.env['ir.config_parameter'].sudo()
        threshold = float(ICP.get_param(
            'nakel_supplier_pricelist.rows_missing_threshold_pct',
            default=_DEFAULT_ROWS_MISSING_THRESHOLD_PCT))

        drop_pct = (1 - (self.total_lines / previous.total_lines)) * 100.0
        if drop_pct < threshold:
            return

        self.env['supplier.pricelist.warning'].create({
            'import_id': self.id,
            'type': 'rows_missing',
            'severity': 'warning',
            'title': _('Se cargaron %(drop).0f%% menos productos que la lista anterior') % {
                'drop': drop_pct,
            },
            'message': _(
                'Lista anterior (%(date)s): %(prev)d productos.\n'
                'Esta lista: %(now)d productos.\n\n'
                'Posibles causas: el proveedor recortó su catálogo, o el '
                'parser perdió filas por cambio de formato.'
            ) % {
                'date': previous.date,
                'prev': previous.total_lines,
                'now': self.total_lines,
            },
            'suggested_action': _(
                'Comparar visualmente el PDF con la cantidad detectada. Si el '
                'archivo del proveedor tiene más productos de los que detectó '
                'el parser, hay un problema de extracción.'
            ),
        })

    def _detect_parser_noise(self):
        """Detecta líneas-basura (fechas, totales, códigos sin nombre)."""
        self.ensure_one()
        import re
        date_re = re.compile(r'^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}')
        code_only_re = re.compile(r'^[A-Z]?\d{4,8}\s*$')

        noise_lines = []
        for line in self.line_ids:
            name = (line.supplier_product_name or '').strip()
            if not name:
                continue
            if date_re.match(name):
                noise_lines.append(line)
            elif code_only_re.match(name):
                noise_lines.append(line)

        if not noise_lines:
            return

        # Solo creamos warning si la cantidad es relevante (>=2)
        if len(noise_lines) < 2:
            return

        self.env['supplier.pricelist.warning'].create({
            'import_id': self.id,
            'type': 'parser_noise',
            'severity': 'info',
            'title': _('%d líneas-basura detectadas') % len(noise_lines),
            'message': _(
                'El parser extrajo %(n)d líneas que parecen ruido (fechas, '
                'códigos sin descripción legible). Estas líneas no se van a '
                'matchear nunca y se pueden ignorar.\n\n'
                'Ejemplos: %(examples)s'
            ) % {
                'n': len(noise_lines),
                'examples': ', '.join(
                    f'"{l.supplier_product_name[:30]}"'
                    for l in noise_lines[:5]
                ),
            },
            'suggested_action': _(
                'Estas líneas se pueden ignorar — no van a afectar los costos '
                'aplicados. Si son muchas (más del 10% del total), puede ser '
                'señal de que el PDF tiene un formato raro que conviene revisar.'
            ),
        })

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _compute_column_signature(columns):
        """Hash determinístico de una lista de nombres de columna.

        Normaliza los nombres (lowercase, strip, espacios colapsados) para que
        diferencias triviales no cambien la signature.
        """
        if not columns:
            return False
        norm = []
        for c in columns:
            s = (c or '').lower().strip()
            s = ' '.join(s.split())  # colapsar espacios
            norm.append(s)
        joined = '|'.join(norm)
        return hashlib.sha256(joined.encode('utf-8')).hexdigest()[:16]

    def _get_product_catalog(self):
        """Devuelve el catálogo de productos relevante para el proveedor."""
        # Primero: productos que ya tienen supplierinfo con este proveedor
        supplierinfo = self.env['product.supplierinfo'].search([
            ('partner_id', '=', self.partner_id.id)
        ])
        known_products = supplierinfo.mapped('product_tmpl_id')

        # También el mapping confirmado de veces anteriores
        mappings = self.env['supplier.product.mapping'].search([
            ('partner_id', '=', self.partner_id.id)
        ])

        # Catálogo completo (todos los productos activos)
        all_products = self.env['product.template'].search([
            ('type', '!=', 'service'),
            ('active', '=', True),
        ], limit=5000)

        # Pre-fetch de UoM y packagings de todos los productos para evitar N+1
        all_variants = all_products.mapped('product_variant_ids')
        packagings = self.env['product.packaging'].search([
            ('product_id', 'in', all_variants.ids),
        ])
        # Index: product_tmpl_id → list of packagings
        pkg_by_tmpl = {}
        for pkg in packagings:
            tmpl_id = pkg.product_id.product_tmpl_id.id
            pkg_by_tmpl.setdefault(tmpl_id, []).append({
                'name': pkg.name or '',
                'qty': float(pkg.qty or 0),
                'barcode': pkg.barcode or None,
            })

        catalog = []
        for p in all_products:
            si = supplierinfo.filtered(lambda s: s.product_tmpl_id == p)
            mp = mappings.filtered(lambda m: m.product_tmpl_id == p)
            catalog.append({
                'id': p.id,
                'name': p.name or '',
                'standard_price': float(p.standard_price or 0.0),
                'categ_name': p.categ_id.name or None,
                'barcode': p.barcode or None,
                'supplier_product_code': (si[0].product_code or None) if si else None,
                'supplier_product_name': (si[0].product_name or None) if si else None,
                'known_supplier_names': [n for n in mp.mapped('supplier_product_name') if n],
                'is_known_supplier': bool(p in known_products),
                # ── Datos de empaque/UoM (Sprint 4) ────────────────────────
                # Permiten al smart matcher saber cuántas unidades tiene cada
                # packaging configurado (ej: "Pack de 12 unidades" → qty=12).
                # Esto da una ancla DETERMINÍSTICA para el unit_count, además
                # del costo que ya se usa.
                'uom_name': p.uom_id.name if p.uom_id else None,
                'uom_po_name': p.uom_po_id.name if p.uom_po_id else None,
                'packagings': pkg_by_tmpl.get(p.id, []),
            })
        return catalog
