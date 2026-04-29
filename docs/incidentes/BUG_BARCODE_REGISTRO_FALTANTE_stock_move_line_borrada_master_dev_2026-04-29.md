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

