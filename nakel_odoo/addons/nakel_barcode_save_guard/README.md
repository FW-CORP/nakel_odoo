# nakel_barcode_save_guard

**Propósito:** cuando el cliente **Barcode** (olas / batch) conserva **IDs viejos** de `stock.move.line` ya **eliminados** en el servidor, el RPC `save_barcode_data` puede lanzar **`MissingError`** y dejar pantalla bloqueada o 500.

Este módulo **hereda** el controlador de `stock_barcode_picking_batch` y envuelve `save_barcode_data`:

- Si ocurre **`MissingError`**, registra un warning en log.
- Si el **`model` / `res_id`** del pedido sigue existiendo y el registro expone **`_get_stock_barcode_data`**, devuelve ese payload para que el cliente **resincronice** sin crashear.
- Si no hay recuperación posible, **re-lanza** la excepción.

## Dependencias

- `stock_barcode`
- `stock_barcode_picking_batch`

## Relación con `nakel_fix_pick`

- **`nakel_fix_pick`**: servidor (`write` en `stock.move.line`) + assets JS (sesión / errores).
- **`nakel_barcode_save_guard`**: **HTTP** en la ruta de guardado Barcode.

Son **complementarios**; conviene tener ambos actualizados y Odoo **reiniciado** tras `-u`.

## Despliegue

```bash
./odoo-bin -u nakel_barcode_save_guard -d master_dev
# reiniciar servicio Odoo
```
