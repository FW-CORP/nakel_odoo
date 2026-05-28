# -*- coding: utf-8 -*-
{
    'name': 'Nakel Report - Picking Operations PDF',
    'version': '18.0.1.0.1',
    'category': 'Inventory/Inventory',
    'summary': 'PDF de operaciones de recolección (PICK): demanda OV, sin ubicaciones, valoración',
    'description': """
        Personaliza el reporte estándar «Operaciones de recolección» (stock.report_picking):

        - Quita columnas Desde / A (ubicaciones).
        - Mantiene Producto y Cantidad (reservada).
        - Agrega columna Demanda (línea de venta / OV).
        - Sección Valoración (SO, facturas) reutilizando la lógica probada en olas.

        No modifica el módulo nakel_picking (reportes batch/ola).
    """,
    'author': 'FWCORP',
    'website': '',
    'depends': [
        'stock',
        'sale_stock',
        'account',
    ],
    'data': [
        'reports/stock_report_picking.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
