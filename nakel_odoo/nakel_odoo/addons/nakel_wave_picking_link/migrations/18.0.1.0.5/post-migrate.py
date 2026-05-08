# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    batches = env["stock.picking.batch"].search([])
    batches._nakel_recompute_wave_links()
    _logger.info(
        "nakel_wave_picking_link 18.0.1.0.5: recompute en %s olas (fix depends + sale_stock)",
        len(batches),
    )

