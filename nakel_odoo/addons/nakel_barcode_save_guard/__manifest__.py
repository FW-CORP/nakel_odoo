# -*- coding: utf-8 -*-
{
    "name": "Nakel Barcode save guard (stale move lines)",
    "summary": "Evita crash del cliente barcode cuando stock.move.line fue eliminado (IDs obsoletos / concurrencia).",
    "version": "18.0.1.0.1",
    "category": "Inventory/Inventory",
    "author": "Nakel",
    "license": "LGPL-3",
    "depends": [
        "web",
        "stock_barcode",
        "stock_barcode_picking_batch",
    ],
    "data": [],
    "installable": True,
    "application": False,
    "auto_install": False,
}
