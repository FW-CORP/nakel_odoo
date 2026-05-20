# NAK / ventas (cotizaciones + stock Roturas 2)

**Fuente de verdad:** repositorio **`nakel_odoo`**, ruta **`tools/nak-ventas/`**.

Scripts manuales (`--dry-run` / `--apply`) para mover stock disponible a **Roturas 2** según cotizaciones etiquetadas con **`procesar`**, y marcar **`ProcesadaNN`** al terminar (incluso si no hubo stock que mover).

**Plan A:** ejecución manual; el cron de desecho es opcional y aparte.

## Contenido

| Archivo | Descripción |
|--------|-------------|
| [MOVER_DISPONIBLE_PEDIDOS_A_ROTURAS2_MASTER_DEV.md](MOVER_DISPONIBLE_PEDIDOS_A_ROTURAS2_MASTER_DEV.md) | **Dos perfiles:** CEN (cotizaciones **NAK** → `CEN/Roturas 2`) y **B3** (cotizaciones **Nakel SA** Belgrano 3 → `B3/Roturas 2`). Etiquetas, comandos, alias y referencia `master_dev`. |
| [scripts/mover_disponible_pedidos_a_roturas2_master_dev.py](scripts/mover_disponible_pedidos_a_roturas2_master_dev.py) | Script XML-RPC (dry-run / apply). |
| [CRON_DESECHO_ROTURAS2_MASTER_DEV.md](CRON_DESECHO_ROTURAS2_MASTER_DEV.md) | Acción planificada para **desechar** stock en Roturas 2 (CEN + B3) vía `stock.scrap`. |

## Comandos rápidos

**CEN (NAK):**

```bash
python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py --dry-run
python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py --apply
```

**B3 (Belgrano 3 / Nakel SA):**

```bash
python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py \
  --dry-run --company-nak 1 --company-nakel 1 --warehouse-code B3 --filtrar-warehouse-id 17

python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py \
  --apply --company-nak 1 --company-nakel 1 --warehouse-code B3 --filtrar-warehouse-id 17
```

**Requisito:** `config_nakel.py` (por defecto bajo `NAKEL_CONFIG_ROOT` o `/media/klap/raid5/cursor_files`).
