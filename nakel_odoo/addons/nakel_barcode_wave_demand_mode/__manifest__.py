# -*- coding: utf-8 -*-
{
    "name": "Nakel Barcode Ola — Modo demanda OV",
    "summary": (
        "Puente operativo: en olas PICK, sube stock.move.line.quantity a la demanda OV "
        "(product_uom_qty) aunque la reserva Odoo sea parcial. Activable por ICP."
    ),
    "version": "18.0.1.0.15",
    "category": "Inventory/Inventory",
    "author": "Nakel",
    "license": "LGPL-3",
    "depends": [
        "stock_picking_batch",
        "nakel_wave_picking_link",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "wizard/wave_coverage_gap_wizard_views.xml",
        "views/stock_picking_batch_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
