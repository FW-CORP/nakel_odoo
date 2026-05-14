# -*- coding: utf-8 -*-
{
    "name": "Nakel Fix Picked Flag",
    "summary": "Keep stock.move.line.picked consistent with quantity for Barcode waves.",
    "version": "18.0.1.1.4",
    "category": "Inventory/Inventory",
    "author": "Nakel",
    "license": "LGPL-3",
    "depends": [
        "web",
        "stock",
        "stock_barcode",
    ],
    "data": [
        "data/ir_config_parameter.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "nakel_fix_pick/static/src/js/barcode_soft_missing_error_handler.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}

