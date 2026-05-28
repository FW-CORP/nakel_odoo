# -*- coding: utf-8 -*-
{
    "name": "Nakel — Tablero Ventas + POS",
    "summary": "Fuente analítica unificada para tableros profesionales de Ventas y Punto de Venta.",
    "version": "18.0.1.0.0",
    "category": "Sales/Sales",
    "author": "Nakel",
    "license": "LGPL-3",
    "depends": [
        "pos_sale",
        "sale_margin",
        "sale_stock",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/sales_dashboard_report_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
