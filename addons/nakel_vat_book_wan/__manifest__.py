# -*- coding: utf-8 -*-
{
    'name': 'Nakel — Libro IVA: límite vista previa (WAN)',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Localizations/Account Reports',
    'summary': 'Reduce líneas en vista previa del Libro de IVA AR para evitar timeouts/payload enorme por WAN.',
    'description': """
El informe estándar trae ``load_more_limit`` = 4000 líneas en pantalla.
Cada fila incluye muchas columnas → JSON-RPC muy grande → problemas por WAN
(timeout del proxy, transferencia lenta, ERR_CONTENT_LENGTH_MISMATCH).

Este módulo baja el límite de vista previa (export PDF/XLSX/ZIP sigue completo).

Ajustar: editar ``data/vat_book_limits.xml`` o el registro ``account.report``
del Libro de IVA en modo desarrollador.
    """,
    'author': 'FWCORP',
    'license': 'LGPL-3',
    'depends': ['l10n_ar_reports'],
    'data': [
        'data/vat_book_limits.xml',
    ],
    'installable': True,
    'application': False,
}
