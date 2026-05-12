# NAK / ventas (Nak + stock en Nakel SA)

**Fuente de verdad:** solo el repositorio **`nakel_odoo`** (`FW-CORP/nakel_odoo`), ruta **`tools/nak-ventas/`**. Cualquier copia en otro workspace sin ese remoto queda **fuera del esquema** de versionado y despliegue; los cambios se hacen **aquí** y se publican con `git push` desde la raíz de `nakel_odoo`.

Material de trabajo para flujos donde la **cotización/pedido** está en compañía **Nak** (solo **borradores** / `draft`) pero el **stock físico** y los movimientos de almacén se hacen en **Nakel SA**. **No** usar órdenes de venta de Nakel SA como origen de cantidades.

**Plan A:** script manual (`--dry-run` / `--apply`), sin cron obligatorio.

## Contenido

| Archivo | Descripción |
|--------|-------------|
| [MOVER_DISPONIBLE_PEDIDOS_A_ROTURAS2_MASTER_DEV.md](MOVER_DISPONIBLE_PEDIDOS_A_ROTURAS2_MASTER_DEV.md) | Traslado interno **CEN/Existencias → CEN/Roturas 2** según `sale.order` NAK; por defecto solo cotizaciones con etiqueta **`procesar`**; con **`--apply`** marca **`ProcesadaNN`** y quita **`procesar`**. Incluye **referencia `master_dev`** (`crm.tag` por `id`, compañías). |
| [scripts/mover_disponible_pedidos_a_roturas2_master_dev.py](scripts/mover_disponible_pedidos_a_roturas2_master_dev.py) | Script XML-RPC (dry-run / apply). |
| [CRON_DESECHO_ROTURAS2_MASTER_DEV.md](CRON_DESECHO_ROTURAS2_MASTER_DEV.md) | Acción planificada para **desechar** lo acumulado en Roturas 2 (CEN + B3) vía `stock.scrap`. |

**Requisito:** `config_nakel.py` (por defecto bajo `NAKEL_CONFIG_ROOT` o `/media/klap/raid5/cursor_files`).
