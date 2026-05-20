# nakel_barcode_wave_validate_confirm

Confirmación en **Código de barras → Ola** (`stock.picking.batch`) al pulsar **Validar**.

## Comportamiento

- Si está activo, antes de ejecutar la validación estándar de Odoo aparece un diálogo:
  - **Título:** Validar ola
  - **Mensaje:** configurable (por defecto: *¿Realmente querés validar la OLA?*)
  - **Aceptar** → continúa la validación (backorders, firma, etc. de Odoo siguen igual).
  - **Cancelar** → no valida.

- Solo afecta **olas** en Barcode (`BarcodePickingBatchModel`), no pickings sueltos ni inventario.

## Activar / desactivar sin desinstalar

Ajustes técnicos → Parámetros del sistema:

| Clave | Valor |
|--------|--------|
| `nakel_barcode_wave_validate_confirm.enable` | `1` / `0` (o `true` / `false`) |
| `nakel_barcode_wave_validate_confirm.message` | Texto del cartel |

Tras cambiar parámetros, **recargar el navegador** (la sesión lee los flags en `session_info`).

## Dependencias

- `stock_barcode`
- `stock_barcode_picking_batch` (Enterprise)

## Instalación

```bash
./odoo-bin -u nakel_barcode_wave_validate_confirm -d staging_mayo
# reiniciar Odoo
```

En **Apps** → actualizar lista → instalar **Nakel — Confirmación al validar ola (Barcode)**.

## Relación con otros módulos Nakel

| Módulo | Rol |
|--------|-----|
| `nakel_fix_pick` | `picked` / MissingError en Barcode |
| `nakel_barcode_save_guard` | HTTP `save_barcode_data` |
| **Este módulo** | UX confirmación al validar **ola** |

Son independientes: podés instalar solo este o combinarlos.

## Despliegue

Copiar la carpeta a la ruta de addons custom del servidor (misma que el resto de `nakel_odoo/addons`), reiniciar Odoo e instalar/actualizar el módulo.
