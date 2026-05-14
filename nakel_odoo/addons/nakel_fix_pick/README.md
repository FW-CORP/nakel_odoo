# nakel_fix_pick

Mini-módulo para **analizar** y (opcionalmente) corregir el caso detectado en Barcode:

- En `stock.move.line`, `qty_done` (UI) se computa como `quantity` si `picked` es verdadero, si no **0**.
- Se observó data inconsistente: `quantity > 0` pero `picked = false`, lo que hace que Barcode muestre “0 / …” aun teniendo cantidades hechas.

## Despliegue (después de actualizar código)

1. Copiar addon al servidor y **`./odoo-bin -u nakel_fix_pick -d master_dev`** (o la base que corresponda).
2. **Reiniciar** el servicio Odoo (workers cargan assets JS).
3. En **Ajustes → Técnico → Parámetros del sistema**, mantener si hace falta:
   - `nakel_fix_pick.enable` = `1`
   - `nakel_fix_pick.barcode_soft_missing` = `1`
   - `nakel_fix_pick.block_unlink_open_wave_lines` = `1` (desde **18.0.1.1.0**: bloquea borrar líneas de pickings que pertenecen a una ola `in_progress`; los **Administradores de inventario** pueden borrar igualmente.)  
   (Los valores por defecto en XML son `0` con `noupdate` para las claves antiguas; en bases ya existentes un `-u` **no** pisa ICP ya creados. La clave nueva de bloqueo se inserta al actualizar el módulo.)

## Enfoque propuesto (seguro por defecto)

Este módulo **no hace nada** si no se activa explícitamente.

- **Bandera**: parámetro de sistema `nakel_fix_pick.enable`
  - `False` o no seteado: no toca nada.
  - `True`: al **crear** y **escribir** en `stock.move.line`, sincroniza **`picked`** y, si aplica, **`quantity` → `qty_done`** cuando Barcode manda cantidades positivas (incluye el caso `picked: False` + cantidad > 0, y `qty_done=0` + `quantity>0` en el mismo `write` / `create`).
- **Bandera JS**: `nakel_fix_pick.barcode_soft_missing` expuesta en `session_info` (`ir.http`); el asset `barcode_soft_missing_error_handler.js` mitiga `MissingError` en referencias a líneas/movimientos borrados (recarga suave).
- **Bloqueo unlink en olas abiertas** (desde 18.0.1.1.0): parámetro `nakel_fix_pick.block_unlink_open_wave_lines` (por defecto `1` en datos nuevos). Si está activo, no se puede **borrar** una línea de movimiento cuyo picking pertenezca a una ola **`in_progress`**, salvo **Administrador de inventario** (`stock.group_stock_manager`) o `sudo`. Desactivar con `0` solo si hay un motivo fuerte.

## Backfill (opcional, no automático)

Incluye un método utilitario `nakel_backfill_picked_for_wave` para backfill controlado por Wave (Batch Picking), pensado para ejecutarse **manualmente**; el dominio usa **`quantity > 0`** (Odoo 18 en este entorno no almacena `qty_done` en tabla). En la UI de la ola existe el botón **SYNC** (`action_nakel_sync_picked_from_quantity`) para el mismo efecto sin shell.

## Notas operativas

- Con `enable=1`, si llega `quantity > 0` y `qty_done` no viene positivo, se **escribe** `qty_done` con ese valor para alinear Barcode tras refresh.
- `nakel_barcode_save_guard` (en `nakel_odoo/addons/nakel_barcode_save_guard`) es **complementario** (ruta HTTP `save_barcode_data`); conviene `-u` y reinicio junto con este módulo.

