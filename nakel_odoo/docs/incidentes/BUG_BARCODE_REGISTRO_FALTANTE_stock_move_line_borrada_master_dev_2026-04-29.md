## Bug — Barcode “Registro faltante” por `stock.move.line` borrada (master_dev)

**Fecha:** 2026-04-29  
**Entorno:** `master_dev`  
**Módulo/área:** Inventario → Código de barras (Barcode) / Olas (Waves)  

### Síntoma

En la pantalla **Escanear producto** (Barcode), al operar dentro de una ola/wave, aparece el popup:

- **“Registro faltante”**
- “El registro no existe o fue eliminado.”
- Referencia: `stock.move.line(<id>)` (ejemplo observado: `stock.move.line(156163)`)

### Evidencia (master_dev)

- OLA afectada: `WAVE/00104` (`stock.picking.batch` id **109**), estado `in_progress`
- Usuario en la ola: id **110**
- El registro indicado por el popup **no existe** en base:
  - `stock.move.line(156163)` → **Record not found**

### Causa probable

**Concurrencia / regeneración de reservas**: mientras un dispositivo tiene abierta la sesión Barcode con IDs de `stock.move.line` cargados, otra acción (p. ej. desreserva/reasignación o cambios de disponibilidad) puede **eliminar y recrear** `stock.move.line` con IDs nuevos. La UI queda apuntando a un ID viejo y al intentar abrirlo dispara “Registro faltante”.

### Mitigación operativa (rápida)

1. En el dispositivo afectado, **salir** de la ola (volver al menú principal de Barcode).
2. **Re-entrar** a la ola desde el listado (evitar volver con “Atrás” del navegador).
3. Si persiste, hacer **recarga dura** del navegador (limpia caché de la app):
   - Chrome/Edge: `Ctrl+Shift+R`
4. Si aún persiste, borrar **almacenamiento del sitio** para el dominio de Odoo (localStorage/session/caché) y volver a entrar.

### Nota

Si el problema se repite, conviene evaluar un fix a nivel backend (controlador/JS) para que ante “record missing” la app **re-sincronice** y recargue la ola en vez de quedar bloqueada.

---

## Variante (misma familia): `stock.move(<id>)` al salir / retroceder

### Síntoma

Mensaje equivalente, pero el registro citado es **`stock.move(170390)`** (ejemplo), no `stock.move.line`.

### Qué es `stock.move`

En inventario, cada **línea de producto/cantidad** dentro de un albarán (`stock.picking`) es un **`stock.move`**. Los detalles por ubicación/lote suelen ir en **`stock.move.line`**. Barcode y el formulario web guardan en memoria **IDs** de esos modelos; si el servidor **borró o reemplazó** el `stock.move` (re-reserva, cancelación, fusión de líneas, picking viejo saneado, etc.), el cliente sigue intentando **leer o refrescar** ese ID al **salir, retroceder o recargar** → *“El registro no existe o fue eliminado”*.

### Por qué se nota más en picks / OV viejos

- Historial de **re-reservas** o correcciones que **recrean** movimientos (IDs nuevos).
- Picking **cancelado** o **dividido** dejando movimientos viejos eliminados.
- Sesión del navegador con **URL o estado** (breadcrumb) que aún apunta al movimiento viejo.

No implica necesariamente que lo que marcaste no se haya guardado: muchas veces el **write** ya se aplicó y el cartel aparece en un **read** posterior sobre un ID obsoleto.

### Mitigación operativa (igual que arriba, reforzada)

1. Salir al **menú** de Barcode (no depender del botón “Atrás” del navegador).
2. Volver a abrir el **picking/ola desde el listado** (ruta “limpia”).
3. **Recarga dura** (`Ctrl+Shift+R`) o borrar **datos del sitio** para ese dominio si el aviso reaparece siempre al navegar.

### Comprobación rápida (técnico)

En modo desarrollador o shell Odoo, ver si el ID sigue existiendo:

- `stock.move` id **170390**: si no existe, el mensaje es **coherente** (cliente con estado viejo).
- Si existe, revisar `picking_id`, `state` y si el picking sigue siendo el que tenías abierto en Barcode.

### Subsanar a futuro (producto)

- **Implementado en `nakel_fix_pick` (18.0.1.0.2+):** parámetro `nakel_fix_pick.barcode_soft_missing` → handler JS que ante `MissingError` en `stock.move` / `stock.move.line` muestra aviso y **recarga** el cliente (evita el bucle del diálogo). Ver README del módulo.
- Reducir operaciones que **eliminen** líneas con la pantalla abierta (procesos batch concurrentes sobre la misma ola).


