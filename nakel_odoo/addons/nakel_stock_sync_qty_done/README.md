# nakel_stock_sync_qty_done

Botón **SYNC** en traslados internos (`stock.picking` con `picking_type_code = internal`) para copiar
**`stock.move.line.quantity` → `stock.move.line.qty_done`** cuando `qty_done` está en 0.

## Problema que resuelve (Nakel)

En ciertos flujos operativos, el operario completa “Cantidad” (visible en la UI) pero Odoo deja
`qty_done` en 0. Al validar, el stock no impacta porque el movimiento real se rige por `qty_done`.

## Qué hace el botón

- Solo sobre el picking actual
- Solo líneas con `qty_done = 0` y `quantity > 0`
- Es conservador: no toca líneas ya hechas

## Uso

1. Operario completa cantidades (según flujo local).
2. Supervisor presiona **SYNC**.
3. Validar (si hay wizard de backorder, elegir según política operativa).

