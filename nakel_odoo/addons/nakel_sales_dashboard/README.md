# Nakel — Tablero Ventas + POS

Módulo base para construir tableros profesionales de ventas en Odoo 18.

## Qué aporta

- Modelo analítico readonly `nakel.sales.dashboard.report`.
- Unión de ventas estándar (`sale.order` / `sale.order.line`) y Punto de Venta (`pos.order`).
- Vistas `list`, `pivot`, `graph` y búsqueda preparada para Spreadsheet Dashboard.
- Menú: **Ventas → Órdenes → Ventas Nakel - Análisis**.

## Criterios de datos

- Ventas estándar: `sale.order` / `sale.order.line` con estados `sale` y `done`.
- POS: `pos.order` con estados `paid`, `done` e `invoiced`.
- Sucursal POS: `pos.config.picking_type_id.warehouse_id`.
- Vendedor: `sale.order.user_id` y `pos.order.user_id`.
- Fecha común: `sale.order.date_order` / `pos.order.date_order`.

## Uso con Dashboard Spreadsheet

1. Abrir **Ventas Nakel - Análisis**.
2. Ajustar pivote o gráfico con filtros de vendedor, sucursal/POS y fecha.
3. Usar **Insertar en hoja de cálculo**.
4. Crear o elegir un dashboard publicado, sin modificar los dashboards estándar de Odoo.
