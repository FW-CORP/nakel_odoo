# -*- coding: utf-8 -*-
"""Sincroniza group_cc_payment_restricted según perfil (sin tocar CC mis ventas)."""

import logging

_logger = logging.getLogger(__name__)

# Usuarios con estos grupos no deben llevar filtro ir.rule en account.payment.
_PAYMENT_RULE_EXEMPT_XMLIDS = (
    "base.group_system",
    "account.group_account_user",
    "account.group_account_manager",
    "account.group_account_invoice",
)


def sync_cc_payment_restricted_groups(env):
    """Asigna o quita group_cc_payment_restricted en usuarios con CC mis ventas."""
    cc_sales = env.ref("clientes_cc_detalle.group_cc_my_sales", raise_if_not_found=False)
    cc_restrict = env.ref(
        "clientes_cc_detalle.group_cc_payment_restricted", raise_if_not_found=False
    )
    if not cc_sales or not cc_restrict:
        return

    exempt_ids = set()
    for xmlid in _PAYMENT_RULE_EXEMPT_XMLIDS:
        group = env.ref(xmlid, raise_if_not_found=False)
        if group:
            exempt_ids.add(group.id)

    users = env["res.users"].sudo().search([("groups_id", "in", cc_sales.id)])
    added = removed = 0
    for user in users:
        exempt = bool(set(user.groups_id.ids) & exempt_ids)
        has_restrict = cc_restrict.id in user.groups_id.ids
        if exempt and has_restrict:
            user.write({"groups_id": [(3, cc_restrict.id)]})
            removed += 1
        elif not exempt and not has_restrict:
            user.write({"groups_id": [(4, cc_restrict.id)]})
            added += 1

    if added or removed:
        _logger.info(
            "clientes_cc_detalle: sync cobros CC filtrados "
            "(+%s usuarios con filtro, -%s sin filtro)",
            added,
            removed,
        )


def post_init_hook(env):
    sync_cc_payment_restricted_groups(env)
