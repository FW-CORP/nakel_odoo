# nakel_sync_ola

Addon **aparte** de `nakel_fix_pick`: no modifica el botón SYNC existente (solo `picked` y dominio `batch_id`).

## Botón **SYNC Ola+OUT** (formulario de ola)

- Busca pickings pendientes con `batch_id = ola` **o** `nakel_wave_batch_id = ola` (incluye OUT sin `batch_id`).
- Por cada uno llama a `action_sync_qty_done_from_quantity` de `nakel_stock_sync_qty_done` (misma regla: solo `qty_done == 0` y `quantity > 0`).
- Luego marca `picked=True` en líneas con `quantity > 0` y `picked=False`.

No ejecuta validación.

## Dependencias

- `stock_picking_batch`, `nakel_wave_picking_link`, `nakel_stock_sync_qty_done`

## Instalación

Activar el módulo en Apps tras actualizar lista de aplicaciones.
