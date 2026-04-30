# -*- coding: utf-8 -*-
{
    "name": "Nakel Fix Picked Flag",
    "summary": "Barcode: picked consistency + optional soft recovery on missing stock.move(line).",
    "version": "18.0.1.0.2",
    "category": "Inventory/Inventory",
    "author": "Nakel",
    "license": "LGPL-3",
    "depends": [
        "web",
        "stock",
        "stock_barcode",
    ],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "nakel_fix_pick/static/src/js/barcode_soft_missing_error_handler.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}

