# Diagnóstico: faltantes en OLA aunque “hay stock” (stock en `CEN/Entrada`)

## Síntoma

En una OLA/wave (batch) falta(n) unidades de un producto en el picking de **Recolectar** (`CEN/PICK/...`), pero al buscar el producto aparece “hay stock”.

## Causa típica

El picking de recolección suele tomar stock desde **`CEN/Existencias`**, pero el stock “disponible” puede estar en **`CEN/Entrada`** (misma sucursal/almacén, **ubicación hermana**, no incluida en la reserva del picking).

En ese caso:

- El `stock.move` del producto queda con **availability = 0** al momento de asignación.
- Al cerrar/validar el picking/ola, la línea puede quedar **cancelada** (`state = cancel`) y ya no aparece para pickear.

## Verificación rápida (técnico)

1. Identificar el picking y el `stock.move` del producto:
   - `stock.picking` (`CEN/PICK/...`) → `stock.move` del producto → revisar `state`, `product_uom_qty`, `quantity`, `availability`.
2. Confirmar stock por ubicación:
   - `stock.quant` del producto con `quantity > 0` → revisar `location_id`.
3. Comparar ubicación fuente del picking vs ubicación del stock:
   - `stock.picking.location_id` (p. ej. `CEN/Existencias`)
   - `stock.quant.location_id` (p. ej. `CEN/Entrada`)

## Resolución operativa (cuando corresponde)

- Mover mercadería de `CEN/Entrada` a `CEN/Existencias` (traslado interno / putaway) para que el picking pueda reservar.
- Luego **re-asignar** / regenerar la demanda del pedido (según el flujo operativo de logística) para que se cree/regenere el movimiento no cancelado.

> Nota: si la OLA ya está en `done`, el faltante no se “agrega” a esa ola: se corrige generando el movimiento/picking correspondiente después de disponer stock en la ubicación correcta.

