# -*- coding: utf-8 -*-
{
    'name': 'Nakel Picking - Consolidated Batch Report',
    'version': '18.0.1.18.5',
    'category': 'Inventory/Inventory',
    'summary': 'Consolidated quantities in batch picking reports',
    'description': """
        This module modifies the stock.picking.batch print report to consolidate
        quantities by product, lot, package and location.

        Features:
        - Consolidates quantities when printing batch transfers
        - Barcodes embedded as base64 images for proper PDF rendering
        - Supports lot tracking
        - Supports packages
        - Supports waves
        - Compatible with multi-location picking

        Requirements:
        - python-barcode[images] (pip install python-barcode[images])
    """,
    'author': 'FWCORP',
    'website': '',
    'depends': [
        'stock',
        'stock_picking_batch',
    ],
    'data': [
        'reports/stock_picking_batch_report.xml',
        'reports/paperformat.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
