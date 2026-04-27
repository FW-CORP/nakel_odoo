# -*- coding: utf-8 -*-
{
    "name": "Nakel - Wave link on pickings (OUT filterable)",
    "summary": "Propaga/permite filtrar OUT por ola (stock.picking.batch) vía campo almacenado.",
    "version": "18.0.1.0.5",
    "category": "Inventory/Inventory",
    "license": "LGPL-3",
    "depends": [
        "sale",
        "sale_stock",
        "stock",
        "stock_picking_batch",
    ],
    "data": [
        "views/stock_picking_views.xml",
        "views/stock_picking_batch_views.xml",
        "views/sale_order_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
