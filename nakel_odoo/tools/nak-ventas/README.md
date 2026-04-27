# NAK / ventas (Nak + stock en Nakel SA)

Ubicación en el repo: `nakel_odoo/tools/nak-ventas/`.

Material de trabajo para flujos donde la **cotización/pedido** está en compañía **Nak** pero el **stock físico** y los movimientos de almacén se hacen en **Nakel SA** (Central).

## Contenido

| Archivo | Descripción |
|--------|-------------|
| [MOVER_DISPONIBLE_PEDIDOS_A_ROTURAS2_MASTER_DEV.md](MOVER_DISPONIBLE_PEDIDOS_A_ROTURAS2_MASTER_DEV.md) | Traslado interno **CEN/Existencias → CEN/Roturas 2** según nombres de `sale.order`; política: mover **lo disponible**. |
| [scripts/mover_disponible_pedidos_a_roturas2_master_dev.py](scripts/mover_disponible_pedidos_a_roturas2_master_dev.py) | Script XML-RPC (dry-run / apply). |
| [CRON_DESECHO_ROTURAS2_MASTER_DEV.md](CRON_DESECHO_ROTURAS2_MASTER_DEV.md) | Acción planificada para **desechar** lo acumulado en Roturas 2 (CEN + B3) vía `stock.scrap`. |

**Requisito:** `config_nakel.py` (por defecto bajo `NAKEL_CONFIG_ROOT` o `/media/klap/raid5/cursor_files`).
