# Análisis (solo consulta) — picks “atorados” en CEN/Salida y CEN/OUT (master_dev)

Fecha: 2026-04-27  
Entorno: `master_dev` (vía MCP `user-odoo-master_dev`, **solo lectura**)  

## Qué se buscó

- Pickings no finalizados (estado distinto de `done`/`cancel`) asociados a:
  - **Ubicación** `CEN/Salida` (id **105**).
  - Pickings con prefijo **`CEN/OUT/`** (operación de salida del almacén central).

> Mapeo de IDs (almacén/ubicaciones/tipos de operación) para indexar en MCP-Klap:
> `nakel/MCP-Klap/docs/Inventario_IDs_CEN_Salida_OUT_master_dev_2026-04-27.md`

## Hallazgos principales

- **Backlog hacia `CEN/Salida`**: se detectaron **361** pickings con `location_dest_id = CEN/Salida (105)` en estado no finalizado.
  - Los más antiguos en la muestra ordenada por `scheduled_date` comienzan el **2026-04-02** (muchos en estado `assigned`), lo que sugiere acumulación operativa (reservados pero sin validar).
- **CEN/OUT atorados**: se detectaron **2** pickings con prefijo `CEN/OUT/` no finalizados.
  - Uno en estado `waiting` con destino **“Physical Locations/Traslado entre almacenes”**, con múltiples movimientos `waiting` y cantidad hecha `0`.
  - Otro en estado `assigned` (aparenta estar listo para validar).

## Ejemplos destacados (para inspección operativa)

- `CEN/OUT/00895` (estado `waiting`): movimientos en `waiting` hacia “Traslado entre almacenes” (suele indicar dependencia con movimientos previos/reglas push/pull o falta de disponibilidad/reserva).
- `CEN/OUT/01009` (estado `assigned`): salida estándar a cliente; revisar por qué quedó pendiente de validación.
- `CEN/PICK/00223` (estado `assigned`, 2026-04-02): ejemplo de picking “Recolectar” que llega a `CEN/Salida` pero no se valida.

## Consultas (MCP) usadas para reproducir

1) Ubicación `CEN/Salida`:

- Modelo: `stock.location`
- Dominio: `complete_name ilike "CEN/Salida"`

2) Pickings hacia `CEN/Salida` (no finalizados):

- Modelo: `stock.picking`
- Dominio: `location_dest_id = 105` AND `state not in ("done","cancel")`
- Orden: `scheduled_date asc`

3) Pickings `CEN/OUT/*` (no finalizados):

- Modelo: `stock.picking`
- Dominio: `picking_type_id in (119,126)` AND `state not in ("done","cancel")`
- Orden: `scheduled_date asc`

4) Movimientos de un picking (diagnóstico rápido de estado `waiting/confirmed/assigned`):

- Modelo: `stock.move`
- Dominio: `picking_id = <ID_PICKING>`
- Campos útiles: `state`, `product_id`, `product_uom_qty`, `quantity`, `location_id`, `location_dest_id`

