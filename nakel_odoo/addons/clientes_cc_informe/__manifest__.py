# -*- coding: utf-8 -*-
{
    "name": "Nakel - Detalle CC clientes (gerencia)",
    "summary": "Informe y lista de FC/NC por vendedor para gerencia y administración.",
    "version": "18.0.1.0.13",
    "category": "Sales/Sales",
    "author": "Nakel",
    "license": "LGPL-3",
    "depends": [
        "base",
        "account",
        "sale",
        "clientes_cc_detalle",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "security/account_move_access.xml",
        "security/account_move_informe_rules.xml",
        "views/clientes_cc_informe_wizard_views.xml",
        "views/clientes_cc_informe_menu.xml",
        "report/clientes_cc_informe_report_templates.xml",
        "report/clientes_cc_informe_report.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
