# -*- coding: utf-8 -*-
"""Recuperación suave ante líneas de operación borradas mientras el cliente barcode conserva ids viejos."""

import logging

from odoo import http
from odoo.exceptions import MissingError
from odoo.http import request

from odoo.addons.stock_barcode_picking_batch.controllers.main import StockBarcodePickingBatchController

_logger = logging.getLogger(__name__)


class NakelStockBarcodeSaveGuardController(StockBarcodePickingBatchController):
    @http.route("/stock_barcode/save_barcode_data", type="json", auth="user")
    def save_barcode_data(self, model, res_id, write_field, write_vals):
        try:
            return super().save_barcode_data(model, res_id, write_field, write_vals)
        except MissingError as err:
            _logger.warning(
                "nakel_barcode_save_guard: MissingError en save_barcode_data "
                "(típico: línea borrada / concurrencia). model=%s res_id=%s field=%s err=%s",
                model,
                res_id,
                write_field,
                err,
            )
            if not res_id or not model:
                raise
            if model not in request.env:
                raise
            target = request.env[model].browse(res_id)
            if target.exists() and hasattr(target, "_get_stock_barcode_data"):
                return target._get_stock_barcode_data()
            raise
