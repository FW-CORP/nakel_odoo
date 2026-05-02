# -*- coding: utf-8 -*-
{
    'name': 'Nakel — Informe fiscal carga diferida (PoC)',
    'version': '18.0.1.0.1',
    'category': 'Accounting/Accounting',
    'summary': 'Reduce el primer payload del informe fiscal genérico (solo nivel superior; el resto al desplegar).',
    'description': """
PoC para entornos con respuestas JSON muy grandes (p. ej. WAN + informe fiscal).

- El primer RPC devuelve solo las líneas de nivel superior (p. ej. Ventas / Compras).
- Los impuestos y niveles inferiores se cargan al desplegar vía get_expanded_lines.

Nota: la agregación SQL sigue ejecutándose en la carga inicial para calcular totales
del nivel superior; este módulo recorta sobre todo el tamaño de la respuesta HTTP.

Parámetro del sistema ``nakel_tax_report_lazy.disable`` (se crea al instalar/actualizar el módulo):
``False`` = carga diferida activa; ``True`` o ``1`` = informe fiscal estándar.
    """,
    'author': 'FWCORP',
    'license': 'LGPL-3',
    'depends': ['account_reports'],
    'data': [
        'data/system_parameters.xml',
    ],
    'installable': True,
    'application': False,
}
