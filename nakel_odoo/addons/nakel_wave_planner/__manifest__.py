# -*- coding: utf-8 -*-
{
    "name": "Nakel — Planificador de olas por zona",
    "summary": (
        "Arma olas WAVE desde OV filtradas por etiqueta de cliente (zona) y fecha, "
        "con checklist de PICKs y control de OV sin ola."
    ),
    "version": "18.0.1.0.2",
    "category": "Inventory/Inventory",
    "author": "Nakel",
    "license": "LGPL-3",
    "depends": [
        "sale_stock",
        "stock_picking_batch",
        "nakel_wave_picking_link",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizard/wave_planner_wizard_views.xml",
        "views/sale_order_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
