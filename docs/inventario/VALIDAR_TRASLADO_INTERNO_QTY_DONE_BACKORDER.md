# Validar traslado interno (stock.picking `INT`) — qué impacta stock, `qty_done` y backorder

## Regla práctica (la que importa en operación)

- Al tocar **Validar** en un traslado interno (`stock.picking` tipo `INT`), **el stock se mueve según la “Cantidad hecha” en las líneas de operación** (`stock.move.line`).
  - En Odoo estándar esa cantidad es **`qty_done`**.
  - En algunos flujos (especialmente Barcode) puede aparecer uso de `quantity`/flags como `picked`, pero **para el asiento de stock la referencia operativa es “lo hecho”** (equivalente a `qty_done`).

## Qué pasa al validar

- **Si `qty_done` está cargado**: al validar se generan los `stock.move` “done” y los `stock.valuation.layer`/quants correspondientes, moviendo stock desde `location_id` a `location_dest_id`.
- **Si `qty_done = 0` (o no hay cantidades hechas)**:
  - El picking puede disparar un wizard de **backorder** (si había cantidades solicitadas `product_uom_qty`).
  - Si se confirma backorder, el picking original se finaliza por lo hecho (cero o parcial) y se crea otro picking por lo pendiente.

## Backorder (traslado pendiente)

- Se ofrece cuando hay diferencia entre:
  - **Solicitado** (`stock.move.product_uom_qty`) vs
  - **Hecho** (líneas `stock.move.line.qty_done`).

## Checklist antes de validar (para evitar sorpresas)

- Revisar que las **líneas de operación** tengan la cantidad hecha correcta (`qty_done`).
- Si el objetivo es **mover TODO lo solicitado**, entonces `qty_done` debe **igualar** lo solicitado en cada producto.
- Si el objetivo es **mover SOLO lo contado**, entonces:
  - cargar `qty_done` solo para lo contado
  - y aceptar el comportamiento de backorder (o definir operativamente si se crea/no se crea el pendiente).

## Cómo asegurarte de que está en `qty_done` (UI)

- En el picking (`CEN/INT/...`) ir a la pestaña **Operaciones**.
- Verificar/abrir **Operaciones detalladas** (o el ícono/listado de líneas detalladas).
- En las líneas, revisar la columna **Hecho / Cantidad hecha** (eso es `qty_done`).
  - Si está en **0** y vos ya contaste, todavía **no está cargado** lo que se va a mover.
  - Si está con valores, eso es lo que Odoo intentará mover al validar.

## Caso común: cantidad visible pero `qty_done` en 0

- Puede ocurrir que las líneas tengan cantidad en **`quantity`** (reservado/planificado) pero `qty_done` quede en 0.
- En ese caso, **no impacta stock** al validar hasta que `qty_done` tenga valor (por UI, Barcode o corrección técnica controlada).

## Caso real (master_dev): `CEN/INT/00117` → backorder `CEN/INT/00153`

- **Problema observado**: `stock.move.line.quantity > 0` pero `qty_done = 0` en muchas líneas (en UI se veía “Cantidad”, pero no impactaba al validar).
- **Corrección aplicada (técnica, controlada)**: copiar `quantity → qty_done` solo donde `qty_done=0` para el picking.
- **Validación**: el picking `CEN/INT/00117` quedó en `done` y Odoo creó backorder `CEN/INT/00153` (estado `assigned`) para el remanente.
- **Chequeo post-validación**:
  - `CEN/INT/00117`: `qty_done > 0` en **todas** las `move_line` (159/159).
  - Backorder: existe como picking separado (no se “pierde” lo pendiente).

### Recomendación operativa cuando hay mucha diferencia solicitado vs hecho

- Al validar, **elegir crear backorder** (no cancelar pendientes), así:
  - impacta stock por lo hecho (`qty_done`)
  - y queda un traslado pendiente por lo faltante

## Botón operativo recomendado: `nakel_stock_sync_qty_done` (SYNC)

Para evitar depender de scripts/API y hacerlo operable por supervisión:

- Addon: `nakel_stock_sync_qty_done`
- Agrega un botón **SYNC** en el encabezado del traslado interno que hace:
  - `quantity → qty_done` en `stock.move.line` solo donde `qty_done=0` y `quantity>0`

## Nota relacionada (Barcode)

En incidentes de Barcode se observó desincronización entre cantidades y el flag `picked`. Esto puede afectar lo que la UI muestra, pero **no debe confundirse con el criterio contable/logístico de validación**: el impacto final lo define la “cantidad hecha” en las líneas.

