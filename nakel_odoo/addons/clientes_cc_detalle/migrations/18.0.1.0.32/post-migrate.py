# -*- coding: utf-8 -*-
"""Al actualizar: post_init_hook no corre con -u."""

from odoo import api, SUPERUSER_ID

from odoo.addons.clientes_cc_detalle.hooks import sync_cc_payment_restricted_groups


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    sync_cc_payment_restricted_groups(env)
