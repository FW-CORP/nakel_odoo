# -*- coding: utf-8 -*-

from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def split_uncompleted_moves(self):
        """
        `stock_barcode` hace `move.move_line_ids.unlink()` y líneas sueltas con quantity==0
        dentro de este método. Nuestro `stock.move.line.unlink` no debe bloquear olas
        `in_progress` en ese contexto (validar / post_barcode_process).
        """
        return super(
            StockMove, self.with_context(nakel_barcode_split_uncompleted=True)
        ).split_uncompleted_moves()
