# Análisis: Error al facturar / descontar stock (Encargados)

**Fecha:** 2025-01-23  
**Base:** master_18  
**Síntoma:** El error "no tiene acceso crear a: Trasladar (stock.picking)" aparece cuando el encargado intenta **facturar** una venta (al descontar stock del inventario).

---

## Flujo donde ocurre el error

1. **Encargado** crea una **venta** (presupuesto / orden de venta) desde su sucursal.
2. Confirma la venta o va a **Facturar**.
3. Al facturar, Odoo:
   - Crea o actualiza la **entrega** (`stock.picking`) asociada a la venta.
   - Crea o actualiza **movimientos de stock** (`stock.move`) para descontar inventario.
4. Si el usuario **no tiene permiso de crear/escribir** en `stock.picking` (o en `stock.move`), aparece el error de acceso.

Por tanto el problema **no es solo** “pedir mercadería” (traslado interno), sino también **facturar una venta** que implica crear/escribir el albarán de entrega y los movimientos de stock.

---

## Plantilla de permisos actual (Encargados de sucursal)

### Lo que está configurado

1. **Grupos por sucursal:** "Encargados Belgrano 1", "Encargados Belgrano 2", etc.
2. **Reglas de registro (ir.rule)** para:
   - `stock.picking`
   - `stock.move`
   - `stock.quant`
   - `stock.picking.type`  
   Con dominio por ubicación (solo ven/modifican registros de su sucursal).

3. **Permisos de operación en la regla:**  
   En Odoo 18 las reglas tienen `perm_read`, `perm_write`, `perm_create`, `perm_unlink`.  
   Si **no** se marcan `perm_create` y `perm_write` = True, la regla **no aplica** a las operaciones de crear/escribir, y el usuario del grupo puede quedarse **sin permiso** para crear `stock.picking` al facturar.

### Corrección aplicada en el diseño

- En **nuevas** configuraciones: el script `configurar_permisos_inventario_por_sucursal_master18.py` ahora crea/actualiza las reglas con:
  - `perm_read` = True  
  - `perm_write` = True  
  - `perm_create` = True  
  - `perm_unlink` = True  

- Para **bases ya configuradas** (reglas creadas sin estos flags):  
  Ejecutar:
  ```bash
  python3 corregir_reglas_encargados_perm_create_master18.py
  ```
  (Con `--dry-run` solo se muestra qué se actualizaría.)

---

## Otras causas posibles si el error sigue

1. **Warehouse de la venta**  
   Si la orden de venta (o la compañía/usuario) usa un almacén que no es el de la sucursal del encargado, el `stock.picking` que se crea al facturar puede tener `location_id`/`location_dest_id` que **no cumplen** el dominio de la regla del encargado (p. ej. almacén Central).  
   → Revisar que las ventas del encargado se creen con el almacén de **su** sucursal (B1, B2, B3, B4).

2. **Permisos de facturación**  
   Para poder “Facturar” desde la venta, el usuario debe tener permisos sobre:
   - `sale.order` (confirmar, etc.)
   - `account.move` (crear factura de cliente).  
   Si falta el grupo de **Facturación** (o equivalente), puede fallar en un paso anterior o en un mensaje distinto; si el mensaje es explícitamente sobre `stock.picking`, lo anterior sigue siendo lo más relevante.

3. **Caché de sesión**  
   Después de cambiar reglas o grupos, el encargado debe **cerrar sesión** y volver a **iniciar sesión** para que se recalculen permisos.

---

## Resumen de scripts

| Script | Uso |
|--------|-----|
| `configurar_permisos_inventario_por_sucursal_master18.py` | Crear/actualizar grupos y reglas por sucursal (ya con perm_create/perm_write). |
| `corregir_reglas_encargados_perm_create_master18.py` | Poner perm_create/perm_write (y read/unlink) en True en reglas ya existentes de Encargados. |
| `corregir_permisos_encargado_master18.py 96` | Asegurar grupo de sucursal + Inventory/User; **retira** Product Creation en logins encargados Belgrano (política 2026-04). |
| `diagnosticar_permisos_crear_traslado_master18.py` | Revisar permisos y reglas para crear `stock.picking`. |

---

**Última actualización:** 2025-01-23
