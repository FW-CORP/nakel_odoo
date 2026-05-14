# WAVE/00145 — Respaldo pre-validación (error de validación / Barcode)

**Fecha de lectura `master_dev`:** 2026-05-13 (XML-RPC, `config_nakel`).  
**Batch:** `stock.picking.batch` id **151**, nombre **`WAVE/00145`**, almacén **Nakel Central** (id **14**).  
**Estado del batch al leer:** `in_progress`.

Este documento sirve de **respaldo operativo** antes de pulsar **Validar** en la ola o en masas de PICK: resume números, riesgos y enlaces a CSV generados en el repo de backups.

---

## 1. Por qué puede fallar la validación aunque “en piso esté todo contado”

En Odoo la validación mira **`qty_done`** (y el flujo Barcode / `picked`) en **`stock.move.line`**, no solo lo que el operario “vio” en pantalla.

**Instantánea A — 2026-05-13 ~11:37** (CSV `wave145_batch151_*_20260513_113739.csv` en `backups/`):

| Indicador | Valor | Interpretación |
|-----------|------:|------------------|
| `stock.move` | **1467** | Líneas de demanda en pickings del batch (el “~1513” del usuario es del mismo orden de magnitud; el total **cambia** si entran/salen pickings). |
| `stock.move.line` | **1418** | Operaciones detalladas. |
| `quantity > 0` y `qty_done = 0` | **1418** | **Todas** las líneas con reserva sin **cantidad hecha** en BD → coherente con **Barcode que no persistió** (`save_barcode_data` / concurrencia; ver [Diagnostico.md](../../../Diagnostico.md)). |
| `quantity > 0` y `picked = False` | **1414** | Casi todo sin tilde `picked` persistido. |
| `partially_available` (move) | **8** | Bloque ya listado en el README: validación / demanda completa bloqueada sin stock en origen del PICK ([DIAGNOSTICO_OLA_FALTANTES_POR_STOCK_EN_ENTRADA.md](../../DIAGNOSTICO_OLA_FALTANTES_POR_STOCK_EN_ENTRADA.md)). |
| `confirmed` (move) | **51** | Sin asignación completa. |
| Pickings en batch | **68** (66 `assigned`, 2 `confirmed`) | La ola sigue `in_progress`. |
| OV distintas | **37** | Ver CSV de OV. |

**Instantánea B — 2026-05-13 11:39:30** (`export_wave_pickings_ov_csv.py`, archivos `wave_00145_batch151_*_20260513_113930.csv`): **65** pickings, **1423** moves, **1374** move lines, brecha `qty_done` **1374/1374**, **36** OV. Demuestra que **entre minutos** el batch perdió pickings en la relación `batch_id` (alguien sacó albaranes de la ola o se rearmó parcialmente).

> Nota: una lectura anterior el mismo día (documentada en `README.md` §2) daba **1512** movimientos y **1514** líneas detalladas; los números **cambian** si se agregan o sacan pickings del batch o se reasigna stock. Para auditoría judicial usar siempre el **CSV con timestamp** de la corrida que guardes vos.

---

## 2. Archivos CSV generados (backups)

Ruta base: `/media/klap/raid5/cursor_files/backups/`

| Archivo (patrón) | Contenido |
|------------------|-----------|
| `<slug_batch>_batch151_pickings_<timestamp>.csv` | Cada picking del batch: `id`, nombre, estado, origen, OV (`sale_id`), tipo de operación, `date_done`. |
| `<slug_batch>_batch151_sale_orders_<timestamp>.csv` | Cada `sale.order` vinculada: `id`, nombre, estado, `invoice_status`, `nakel_wave_batch_id`, total. |

El prefijo `<slug_batch>` lo genera el script a partir del nombre del batch (p. ej. `wave_00145_batch151_…`).

**Ejemplos manuales del mismo día (prefijo antiguo `wave145_batch151`):**  
`/media/klap/raid5/cursor_files/backups/wave145_batch151_pickings_20260513_113739.csv`  
`/media/klap/raid5/cursor_files/backups/wave145_batch151_sale_orders_20260513_113739.csv`

Para regenerar (recomendado):

```bash
cd /media/klap/raid5/cursor_files/nakel
python3 nakel_odoo/tools/inventario/export_wave_pickings_ov_csv.py --batch-id 151
```

---

## 3. Qué hacer antes de volver a “Validar” (orden recomendado)

1. **Resolver las 8 líneas `partially_available`** (stock en **Entrada** vs **Existencias**, recomprobar disponibilidad, o decisión comercial de parcial / backorder). Sin eso, la validación **seguirá** chocando en esas líneas.
2. **Alinear Barcode con BD** para el resto: **`quantity` → `qty_done`** y **`picked`** según runbooks:
   - [NAKEL_SYNC_QTY_DONE_BOTON.md](../../NAKEL_SYNC_QTY_DONE_BOTON.md)
   - [NAKEL_SYNC_PIKCED_OLA_BOTON.md](../../NAKEL_SYNC_PIKCED_OLA_BOTON.md)
   - Botón **SYNC Ola+OUT** en la ola (**solo PICK**, no OUT) — [README.md §8.2](README.md) y módulo `nakel_sync_ola` 18.0.1.0.2+.
3. **Dry-run masivo** de simulación OUT por lista de OV (solo lectura): `nakel_odoo/tools/inventario/dry_run_simular_out_faltantes_por_ov.py` cuando la ola esté cerrada y haya que facturar (ver `wave143` §6.4).
4. **Validar** primero en **un** picking de prueba o en las **8** líneas problemáticas, luego la ola completa, con alguien monitoreando log Barcode (`save_barcode_data` vs `get_specific_barcode_data`) según [Diagnostico.md](../../../Diagnostico.md).

---

## 4. Lecturas cruzadas en inventario (vault)

| Documento | Uso |
|-----------|-----|
| [README.md](README.md) (wave145) | Resumen original 8 faltantes, IDs pickings, procedimiento §8. |
| [Diagnostico.md](../../../Diagnostico.md) | Barcode: lecturas sin guardado, concurrencia, SERIALIZATION_FAILURE. |
| [OV_SIN_FACTURAR_SIN_OUT_TRAS_OLA.md](../../OV_SIN_FACTURAR_SIN_OUT_TRAS_OLA.md) | Cadena PICK → OUT y facturación. |
| [DIAGNOSTICO_OLA_FALTANTES_POR_STOCK_EN_ENTRADA.md](../../DIAGNOSTICO_OLA_FALTANTES_POR_STOCK_EN_ENTRADA.md) | Stock en Entrada vs reserva del PICK. |

---

## 5. Regenerar este respaldo (script)

`nakel_odoo/tools/inventario/export_wave_pickings_ov_csv.py` — parámetros: `--batch-id 151` o `--name WAVE/00145`. Escribe CSV en `/media/klap/raid5/cursor_files/backups/` con prefijo tipo `wave_00145_batch151_…`.
