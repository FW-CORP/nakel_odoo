# -*- coding: utf-8 -*-

from odoo import models


class StockPickingNakelReport(models.Model):
    _inherit = 'stock.picking'

    def _get_valuation_lines(self):
        """Líneas SO/factura para el PDF de operaciones de recolección."""
        self.ensure_one()
        return self._nakel_build_valuation_lines(self)

    def nakel_report_demand_qty(self, move_line):
        """
        Demanda para columna del reporte: prioriza cantidad pedida en la OV.
        (nombre público: invocable desde QWeb del reporte)
        """
        move = move_line.move_id
        if not move:
            return 0.0
        if move.sale_line_id:
            return move.sale_line_id.product_uom_qty
        return move.product_uom_qty
