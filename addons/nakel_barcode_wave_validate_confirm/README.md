# nakel_barcode_wave_validate_confirm

Confirmación en **Código de barras** al pulsar **Validar**, para:

- **Ola** (`stock.picking.batch` / `BarcodePickingBatchModel`)
- **Picking suelto** (`stock.picking` / `BarcodePickingModel`)

## Por qué a veces «no pregunta nada»

1. **Módulo no instalado** o sin `-u` tras copiar el addon → Apps → instalar/actualizar.
2. **Caché del navegador**: tras instalar/actualizar, **recarga forzada** (Ctrl+Shift+R) o cerrar sesión; los flags vienen de `session_info` en `ir.http`.
3. **Parámetro desactivado**: `nakel_barcode_wave_validate_confirm.enable` = `0`.
4. **Assets viejos**: reiniciar Odoo después de `-u nakel_barcode_wave_validate_confirm`.

Comprobar en consola del navegador (F12 → consola), con sesión abierta:

```js
odoo.session_info?.nakel_barcode_wave_validate_confirm_enabled
```

Debe ser `true` (o truthy). Si es `undefined`, recargá la página.

## Parámetros del sistema

| Clave | Uso |
|--------|-----|
| `nakel_barcode_wave_validate_confirm.enable` | `1` activo / `0` apagado |
| `nakel_barcode_wave_validate_confirm.message` | Texto al validar **ola** |
| `nakel_barcode_wave_validate_confirm.message_picking` | Texto al validar **picking** |

## Instalación

```bash
sudo -u odoo odoo -c /etc/odoo/odoo.conf -d <base> -u nakel_barcode_wave_validate_confirm --stop-after-init
# reiniciar Odoo; recargar navegador
```

## Dependencias

- `stock_barcode` (Enterprise)
- `stock_barcode_picking_batch` (Enterprise, olas)
