# -*- coding: utf-8 -*-

from odoo import api, models


class IrConfigParameter(models.Model):
    _inherit = "ir.config_parameter"

    @api.model
    def nakel_fix_pick_ensure_default_parameters(self):
        """
        Crear parámetros por defecto solo si no existen la fila (key única).
        Evita UniqueViolation al actualizar el módulo cuando las claves ya están en BD
        sin el xml_id del data file (instalaciones previas, copias de BD, etc.).
        """
        defaults = (
            ("nakel_fix_pick.enable", "0"),
            ("nakel_fix_pick.barcode_soft_missing", "0"),
            ("nakel_fix_pick.block_unlink_open_wave_lines", "1"),
        )
        for key, value in defaults:
            if not self.search_count([("key", "=", key)]):
                self.create({"key": key, "value": value})
