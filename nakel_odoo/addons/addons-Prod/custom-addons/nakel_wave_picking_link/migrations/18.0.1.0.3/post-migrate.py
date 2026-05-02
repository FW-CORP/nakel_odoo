# -*- coding: utf-8 -*-
"""Relacionar OUT hermanos con cada ola (histórico + PICK mirror)."""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    batches = env["stock.picking.batch"].search([])
    batches._nakel_recompute_wave_links()
    _logger.info(
        "nakel_wave_picking_link: _nakel_recompute_wave_links en %s olas",
        len(batches),
    )
