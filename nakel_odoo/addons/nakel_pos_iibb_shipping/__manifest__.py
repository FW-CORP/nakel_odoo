{
    "name": "Nakel — Entrega IIBB desde PV (POS)",
    "version": "18.0.1.0.0",
    "category": "Accounting/Localizations",
    "summary": "Prueba: en facturas POS, provincia de entrega = dirección del PV AFIP del diario",
    "description": """
En el flujo estándar de Odoo POS, la factura se crea con
``partner_shipping_id = domicilio de entrega del cliente``, lo que desvía el
informe IIBB por jurisdicción (agrupa por provincia de entrega).

Este módulo (si está activado vía parámetro del sistema) reemplaza en las
facturas generadas desde **Punto de venta** el ``partner_shipping_id`` por el
contacto configurado en el diario como **Dirección Punto de venta**
(``l10n_ar_afip_pos_partner_id``), típico de la localización argentina.

**Prueba / staging:** activar ``nakel_pos_iibb_shipping.enable`` (ver datos).
En producción dejar en ``False`` salvo decisión explícita.
    """,
    "author": "FwCorp / Nakel",
    "license": "LGPL-3",
    "depends": [
        "point_of_sale",
        "account",
    ],
    "data": [
        "data/ir_config_parameter.xml",
    ],
    "installable": True,
    "application": False,
}
