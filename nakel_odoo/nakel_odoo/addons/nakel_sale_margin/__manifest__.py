# -*- coding: utf-8 -*-
{
    "name": "Nakel — Margen de Venta (acceso restringido)",
    "version": "18.0.1.0.4",
    "summary": "Oculta margen al pie de la OV a vendedores; solo visible para quienes estén en el grupo (p. ej. gerentes).",
    "description": """
Margen en pedidos de venta (OV)
================================

- Por defecto **no** ven el bloque de margen (importe y %) al final del formulario
  ni las columnas de margen en líneas quienes solo tengan acceso comercial habitual.
- Solo quienes estén en el grupo **Ver Margen de Ventas** (Ajustes → Usuarios y
  compañías → Grupos) ven esos datos. Pensado para asignarlo **solo** a quienes
  deben ver rentabilidad (p. ej. dos gerentes), no al resto del equipo de ventas.

Requiere la app **sale_margin** (márgenes activados en Ventas).
""",
    "author": "GliderIT",
    "category": "Sales",
    "depends": ["sale_margin"],
    "data": [
        "security/security.xml",
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
