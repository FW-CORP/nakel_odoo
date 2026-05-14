# nakel_sync_ola

Addon **aparte** de `nakel_fix_pick`: no modifica el botón SYNC existente (solo `picked` y dominio `batch_id`).

## Botón **SYNC Ola+OUT** (formulario de ola)

- El botón se muestra **también si la ola está en `done`/`cancel`**, para poder sincronizar PICK que siguen `assigned` con `nakel_wave_batch_id` apuntando a esa ola (caso típico: ola validada en Barcode sin cerrar todos los recolectores).
- Busca pickings pendientes con `batch_id = ola` **o** `nakel_wave_batch_id = ola`, **excluyendo OUT** (`picking_type_id.sequence_code == 'OUT'` o nombre `CEN/OUT/…`): el OUT comparte ola por trazabilidad pero **no** debe forzarse `quantity → qty_done` / `picked` en bloque con el recolectar (rompe cadena operativa y validaciones).
- Por cada picking restante llama a `action_sync_qty_done_from_quantity` de `nakel_stock_sync_qty_done` (solo `qty_done == 0` y `quantity > 0`).
- Luego marca `picked=True` en líneas de esos pickings con `quantity > 0` y `picked=False`.

No ejecuta validación.

## Dependencias

- `stock_picking_batch`, `nakel_wave_picking_link`, `nakel_stock_sync_qty_done`

## Instalación

Activar el módulo en Apps tras actualizar lista de aplicaciones.
