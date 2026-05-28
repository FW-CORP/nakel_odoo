# WAVE/00156 — respaldos de pickeo (master_dev, solo lectura)

**Ola:** `WAVE/00156` · **ID batch:** `163` · **Almacén:** Nakel Central  
**Estado (inicio documentación):** `in_progress`  
**Fecha:** 2026-05-20

## Contexto operativo

- Pickeo estimado: **~2 días**.
- **Barcode inverso:** al entrar, el flujo marca todo como contado (`qty_done` suele igualar `quantity` y `picked=True`). Los operarios **descontan** lo que no hay o no va → el avance real en BD es **`qty_done` menor que `quantity`** (columna `descuento` en los CSV).
- **No validar** la ola por error hasta tener un respaldo reciente; los CSV son evidencia con timestamp.

> **ID vs nombre:** en URLs de Odoo suele aparecer el id del registro (`163`), no el `156` del nombre `WAVE/00156`.

## Estructura de archivos

```
Prod-Incidencias/wave156/
├── README.md          ← este archivo
└── backups/           ← CSV + JSON (no commitear secretos; solo datos de negocio)
    ├── wave_00156_batch163_summary_<timestamp>.json
    ├── wave_00156_batch163_pickings_<timestamp>.csv
    ├── wave_00156_batch163_sale_orders_<timestamp>.csv
    ├── wave_00156_batch163_move_lines_<timestamp>.csv   ← listado completo de productos
    └── wave_00156_batch163_descuentos_<timestamp>.csv   ← solo si ya hay líneas descontadas
    └── wave_00156_batch163_diff_<nuevo>_vs_<anterior>.csv  ← cambios entre 2 corridas
    └── wave_00156_batch163_diff_<nuevo>_vs_<anterior>_summary.json
```

### Cómo leer el diferencial

`run_backup.sh` genera **dos diffs**:

1. **`_*_intervalo`** — última corrida vs la anterior (cambios recientes, ej. turno).
2. **`_*_baseline`** — última corrida vs el **primer** snapshot del día (progreso total).

| Señal en diff | Significado |
|---------------|-------------|
| `solo_en_anterior` (extras) | Línea que **desapareció** del activo (típico: anulada `quantity→0`) |
| `change_kind=anulada_quantity_a_0` | Misma línea, pasó de `quantity>0` a `0` (CSV nuevo con todas las líneas) |
| `move_lines_anuladas` en summary | Cuántas líneas están en cero ahora |
| `descuento_qty_done` | Casi siempre 0 en barcode inverso; no usar solo esto |

Si `130036` vs `130243` da **0 cambios**, es normal: ambos ya tienen 901 activas. Mirá **`_*_baseline`** (922→901 = 21 anulaciones).

## Comando recomendado (cada 4–6 h o al cierre de turno)

**Un solo comando** (respaldo + diferencial automático si ya hay un snapshot previo):

```bash
/media/klap/raid5/cursor_files/nakel/Prod-Incidencias/wave156/run_backup.sh
```

**Cada 15 min durante 3 horas** (en segundo plano; log en `backups/scheduled_3h_*.log`):

```bash
cd /media/klap/raid5/cursor_files/nakel/Prod-Incidencias/wave156
nohup ./run_backup_3h_every_15m.sh &
# Ver progreso: tail -f backups/scheduled_3h_*.log
# Detener: pkill -f run_backup_3h_every_15m
```

Solo backup (sin diff):

```bash
cd /media/klap/raid5/cursor_files/nakel
python3 nakel_odoo/tools/inventario/backup_wave_progress_master_dev.py \
  --batch-id 163 \
  --output-dir /media/klap/raid5/cursor_files/nakel/Prod-Incidencias/wave156/backups
```

Solo diff manual (últimos 2 `move_lines` en la carpeta):

```bash
python3 nakel_odoo/tools/inventario/diff_wave_move_lines_backups.py \
  --dir /media/klap/raid5/cursor_files/nakel/Prod-Incidencias/wave156/backups \
  --prefix wave_00156_batch163
```

Alternativa por nombre:

```bash
python3 nakel_odoo/tools/inventario/backup_wave_progress_master_dev.py --name WAVE/00156
```

Export liviano (solo pickings + OV, sin detalle de líneas):

```bash
python3 nakel_odoo/tools/inventario/export_wave_pickings_ov_csv.py \
  --batch-id 163 \
  --output-dir /media/klap/raid5/cursor_files/nakel/Prod-Incidencias/wave156/backups
```

## Instantánea inicial (2026-05-20 ~10:42)

| Métrica | Valor |
|---------|------:|
| Pickings | 58 (`assigned`) |
| `stock.move` | 921 (909 `assigned`, 12 `partially_available`) |
| `stock.move.line` | 922 |
| Líneas con descuento (`qty_done` &lt; `quantity`) | **0** (aún no descontaron en BD) |
| OV distintas | 35 |
| `picked=True` en líneas con cantidad | 922 |

Archivos generados en el primer respaldo: ver `backups/wave_00156_batch163_*_20260520_104224.csv`.

## Qué mirar si hay incidente

1. **Último `move_lines_*.csv`** antes del error → producto, OV, picking, `quantity`, `qty_done`, `descuento`.
2. Comparar dos timestamps: las líneas que **aparecen** en `descuentos_*.csv` o suben `descuento` son lo que el piso ya ajustó.
3. **`partially_available` (12 moves):** pueden bloquear validación aunque el piso diga “listo” — revisar stock en origen del PICK (misma lógica que [wave145](../../nakel_odoo/docs/inventario/incidencias/logistica/wave145/README.md)).
4. Si Odoo “miente” en Barcode pero BD tiene `qty_done` en cero en muchas líneas: ver [Diagnostico.md](../../nakel_odoo/docs/inventario/Diagnostico.md) y botón **SYNC Ola+OUT** (solo PICK, no valida).

## Referencias en el repo

- Procedimiento similar: [wave145 RESPALDO](../../nakel_odoo/docs/inventario/incidencias/logistica/wave145/RESPALDO_PRE_VALIDACION_WAVE145_2026-05-13.md)
- Caída de conexión / `qty_done`: [wave146](../../nakel_odoo/docs/inventario/incidencias/logistica/wave146/README.md)
