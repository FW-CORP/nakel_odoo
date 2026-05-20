# -*- coding: utf-8 -*-
{
    "name": "Nakel — Confirmación al validar ola (Barcode)",
    "summary": "Muestra un diálogo Aceptar/Cancelar antes de validar una ola en la app Código de barras.",
    "version": "18.0.1.0.0",
    "category": "Inventory/Inventory",
    "author": "Nakel",
    "license": "LGPL-3",
    "depends": [
        "web",
        "stock_barcode",
        "stock_barcode_picking_batch",
    ],
    "data": [
        "data/ir_config_parameter.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "nakel_barcode_wave_validate_confirm/static/src/js/barcode_wave_validate_confirm.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
