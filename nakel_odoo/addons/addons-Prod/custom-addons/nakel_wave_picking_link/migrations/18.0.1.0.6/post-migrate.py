# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # 18.0.1.0.6: cambios puramente de UI (vistas). No requiere backfill/migración de datos.
    _logger.info("nakel_wave_picking_link 18.0.1.0.6: noop migrate (UI only)")
