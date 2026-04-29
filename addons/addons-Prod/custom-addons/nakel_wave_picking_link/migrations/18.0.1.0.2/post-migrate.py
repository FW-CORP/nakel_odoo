# -*- coding: utf-8 -*-
"""Backfill al actualizar el módulo: post_init_hook NO corre con -u."""

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    before = env["stock.picking"].search_count([("nakel_wave_batch_id", "!=", False)])
    env["stock.picking"].nakel_wave_backfill_all()
    after = env["stock.picking"].search_count([("nakel_wave_batch_id", "!=", False)])
    _logger.info(
        "nakel_wave_picking_link: backfill nakel_wave_batch_id (%s -> %s pickings con valor)",
        before,
        after,
    )
