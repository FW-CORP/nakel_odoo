# -*- coding: utf-8 -*-
{
    "name": "Nakel - CC por vendedor (Contacto)",
    "summary": "CC por vendedor: botón en contacto + menú pivote Ventas.",
    "version": "18.0.1.0.12",
    "category": "Sales/Sales",
    "author": "Nakel",
    "license": "LGPL-3",
    "depends": [
        "base",
        "account",
        "sale",
    ],
    "data": [
        "security/security.xml",
        "security/account_move_access.xml",
        "security/account_move_rules.xml",
        "views/account_move_clientes_cc_views.xml",
        "views/clientes_cc_menu.xml",
        "views/res_partner_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}

