# Botón SYNC (quantity → qty_done) para traslados internos

## Objetivo

En traslados internos (`CEN/INT/...`) se detectó un patrón donde el operario completa “Cantidad” en UI,
pero el sistema deja `stock.move.line.qty_done = 0`. Como la validación impacta stock por `qty_done`,
termina sucediendo “parece cargado pero no mueve”.

## Solución

Se implementa el addon **`nakel_stock_sync_qty_done`**.

- Agrega un botón **SYNC** al lado de **Validar** en traslados internos.
- Acción: copia **`quantity → qty_done`** en líneas (`stock.move.line`) que cumplan:
  - `qty_done = 0`
  - `quantity > 0`

## Procedimiento operativo recomendado

1. Operario completa cantidades según el flujo habitual.
2. Supervisor presiona **SYNC**.
3. Supervisor presiona **Validar**.
4. Si aparece wizard de backorder:
   - **Crear backorder** si querés conservar el pendiente (recomendado cuando hay faltantes).

## Alcance y seguridad

- El botón está restringido a usuarios con permisos de inventario (`stock.group_stock_user`).
- No modifica líneas ya hechas (`qty_done > 0`).

