# -*- coding: utf-8 -*-
{
    "name": "Nakel - CC por vendedor (Contacto)",
    "summary": "CC por vendedor: botón en contacto + menú pivote Ventas.",
    "version": "18.0.1.0.7",
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
        "security/ir.model.access.csv",
        "security/account_move_rules.xml",
        "views/clientes_cc_menu.xml",
        "views/res_partner_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}

