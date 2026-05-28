# Tablero Ventas + POS en `master_dev`

Documento de diseño y operación del tablero profesional unificado para Ventas y Punto de Venta.

## Módulo base

Addon: `nakel_sales_dashboard`

Ruta: `nakel_odoo/addons/nakel_sales_dashboard`

Menú previsto: **Ventas → Órdenes → Ventas Nakel - Análisis**

El módulo crea el modelo analítico readonly `nakel.sales.dashboard.report`, pensado como fuente estable para vistas Odoo (`list`, `pivot`, `graph`) y para dashboards de Odoo Spreadsheet.

## Fuentes de datos

### Ventas estándar

- Modelos: `sale.order` / `sale.order.line`
- Estados incluidos: `sale`, `done`
- Fecha: `sale.order.date_order`
- Vendedor: `sale.order.user_id`
- Sucursal / almacén: `sale.order.warehouse_id`
- Total: `sale.order.line.price_total`
- Base imponible: `sale.order.line.price_subtotal`
- Impuestos: `price_total - price_subtotal`
- Cantidad: `sale.order.line.product_uom_qty`
- Margen: `sale.order.line.margin`

Nota técnica: originalmente se validó contra `sale.report`, pero la vista SQL del módulo usa tablas base de pedidos y líneas para no depender de la relación PostgreSQL `sale_report` durante la instalación del addon.

### Punto de Venta

- Modelo: `pos.order`
- Estados incluidos: `paid`, `done`, `invoiced`
- Fecha: `date_order`
- Vendedor / empleado Odoo: `user_id`
- Caja/POS: `config_id`
- Sucursal real: `config_id.picking_type_id.warehouse_id`
- Total: `amount_total`
- Impuestos: `amount_tax`
- Base imponible: `amount_total - amount_tax`
- Cantidad: suma de `pos.order.line.qty`

Nota Nakel: en `master_dev`, `pos.config.warehouse_id` apunta a **Nakel Central** para las cajas, por eso el tablero usa `pos.config.picking_type_id.warehouse_id` para identificar la sucursal.

## Campos comunes del modelo

- `source_type`: canal (`sale` o `pos`)
- `date_order`: fecha normalizada
- `salesperson_id`: vendedor/usuario
- `warehouse_id`: sucursal o almacén
- `pos_config_id`: caja POS, solo para canal POS
- `partner_id`: cliente
- `amount_total`, `amount_untaxed`, `amount_tax`
- `qty`, `line_count`, `document_count`

## Dashboard Spreadsheet

No modificar los dashboards estándar `Sales` ni `Point of Sale`. La documentación oficial de Odoo recomienda crear copia o dashboard nuevo porque los dashboards estándar pueden reinstalarse en upgrades.

Procedimiento recomendado:

1. Instalar o actualizar el módulo `nakel_sales_dashboard`.
2. Abrir **Ventas → Órdenes → Ventas Nakel - Análisis**.
3. En vista pivote, configurar una primera lectura:
   - Filas: `Canal`, `Sucursal / almacén`, `Vendedor`
   - Columnas: `Fecha` por mes
   - Medidas: `Total`, `Documentos`, `Cantidad`
4. Insertar el pivote en Spreadsheet desde la vista Odoo.
5. Insertar al menos un gráfico:
   - Total mensual por canal
   - Total por vendedor
   - Total por caja POS o sucursal
6. Crear un dashboard nuevo, por ejemplo **Ventas Nakel**.
7. Publicarlo en el grupo de dashboards **Sales** o en un grupo Nakel si se crea uno.
8. Configurar filtros globales:
   - Fecha / rango de fechas sobre `date_order`
   - Vendedor sobre `salesperson_id`
   - Sucursal sobre `warehouse_id`
   - Caja POS sobre `pos_config_id`
9. Validar con gerencia qué usuarios deben tener acceso al grupo `Nakel: tablero ventas gerencia`.

## Validación inicial `master_dev`

Consulta realizada contra la base por MCP en modo readonly.

### Totales esperados por fuente

Ventas estándar (referencia `sale.report`, estados `sale` + `done`):

- Total: `2.154.143.000,18`
- Base imponible: `1.759.265.707,14`
- Impuestos calculados: `394.877.293,04`
- Cantidad: `639.187`
- Líneas (`nbr`): `74.162`
- Margen: `488.494.470,3152188`

Punto de Venta (`pos.order`, estados `paid` + `done` + `invoiced`):

- Total: `1.893.470.137,92`
- Impuestos: `373.672.998,54`
- Base imponible calculada: `1.519.797.139,38`
- Documentos: `11.019`

Total unificado esperado:

- Total: `4.047.613.138,10`
- Impuestos: `768.550.291,58`

### Checklist post-instalación

- [ ] El menú **Ventas Nakel - Análisis** abre sin errores.
- [ ] La vista pivote muestra dos canales: **Ventas estándar** y **Punto de venta**.
- [ ] El total del canal `sale` coincide con la suma de líneas de pedidos confirmados/hechos y con la referencia `sale.report.price_total`.
- [ ] El total del canal `pos` coincide con `pos.order.amount_total` para estados `paid`, `done` e `invoiced`.
- [ ] Las cajas POS se agrupan por sucursal usando `picking_type_id.warehouse_id`.
- [ ] Los dashboards estándar de Odoo quedan intactos.
- [ ] El dashboard Spreadsheet nuevo tiene filtros globales por fecha, vendedor, sucursal y POS.

## Riesgos conocidos

- El canal de ventas estándar mide pedidos confirmados/hechos; no equivale necesariamente a facturación contable por `account.move`.
- POS no siempre tiene la misma semántica de vendedor que ventas estándar.
- Si se necesita facturación fiscal por punto AFIP, usar una segunda etapa basada en `account.move` y `account.journal.l10n_ar_afip_pos_number`.
- El margen depende de que `sale_margin` esté instalado y poblado.
