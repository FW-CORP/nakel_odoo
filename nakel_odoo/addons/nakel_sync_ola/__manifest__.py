# -*- coding: utf-8 -*-
{
    "name": "Nakel Sync Ola + OUT",
    "summary": "Botón en la ola: sincroniza qty_done (reutiliza Nakel Sync Qty Done) y picked en PICK/OUT vinculados por batch_id o nakel_wave_batch_id.",
    "version": "18.0.1.0.2",
    "category": "Inventory/Inventory",
    "author": "Nakel",
    "license": "LGPL-3",
    "depends": [
        "stock_picking_batch",
        "nakel_wave_picking_link",
        "nakel_stock_sync_qty_done",
    ],
    "data": [
        "views/stock_picking_batch_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
