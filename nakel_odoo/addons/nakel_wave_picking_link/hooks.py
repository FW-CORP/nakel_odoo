# -*- coding: utf-8 -*-

import logging

from odoo import SUPERUSER_ID

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """
    Odoo 18: post_init_hook(env)

    Backfill inicial:
    - PICK con batch_id -> nakel_wave_batch_id
    - OUT sin batch_id -> inferir desde PICK batcheado (preferencia: procurement.group / sale.order; fallback: origin)
    """
    # `env` es un `odoo.api.Environment`. `sudo()` existe en recordsets, no en env.
    # En Odoo 18, el Environment es callable para clonar cambiando el usuario.
    env = env(user=SUPERUSER_ID)
    before = env["stock.picking"].search_count([("nakel_wave_batch_id", "!=", False)])
    env["stock.picking"].nakel_wave_backfill_all()
    after = env["stock.picking"].search_count([("nakel_wave_batch_id", "!=", False)])
    _logger.info(
        "nakel_wave_picking_link: post_init_hook backfill (%s -> %s pickings con ola)",
        before,
        after,
    )
