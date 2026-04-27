---
title: Runbook — aplicar fix FACOM en productivo
updated: 2026-04-25
---

## Objetivo

Normalizar `account.move.name` de **Facturas de Proveedor** (compras) del diario `FACOM` para que no figure mas `FACOM/...` y pase a formato:

- `00010-00100648` (PV(5) + `-` + NRO(8))

Derivado desde `account.move.ref` segun la regla de Paula.

## Alcance / restricciones

- Modelo: `account.move`
- Dominio: `move_type=in_invoice` (factura proveedor), `journal_id.code=FACOM`, opcional `state=posted`
- El script **NO inventa** nombres cuando `ref` no se puede parsear:
  - esos registros quedan como `SKIP_NO_PARSE` para correccion manual previa.
- Colisiones (`name_new` ya existente) se saltan como `SKIP_COLLISION`.
- **Restriccion importante (liquidacion impuestos AR)**: la localizacion AR (p.ej. IIBB sufrido) espera que el numero de documento tenga **un solo guion** y sea `PV-NRO`. Si el `name` contiene prefijos con guiones (ej. `FA-A 00010-...`) se rompe con `ValueError: too many values to unpack`.

## Pre-requisitos

- Acceso por XML-RPC (credenciales configuradas fuera del repo).
- Tener este repo clonado y Python 3 disponible.
- Identificar lista de **IDs a omitir**:
  - correcciones manuales (Paula)
  - colisiones (si se resuelven a mano)

Referencias:
- `docs/ANALISIS_CAMPOS_Y_PROCESOS.md`
- `docs/CORRECCIONES_MANUALES_PAULA.md`

## 0) Checklist previo

- Confirmar que estas en el entorno correcto (prod).
- Coordinar una ventana para ejecutar (ideal fuera de horario).
- Tener a mano un path para guardar backups CSV (fuera del repo).

## 1) Dry-run en productivo (sin escribir)

Genera un CSV con antes/despues y la accion que tomaria el script.

```bash
NAKEL_TARGET=master_dev python3 scripts/aplicar_fix_facom.py \
  --only-posted \
  --skip-move-ids 21474,97028,25631,38203,50143,79042 \
  --out-csv /media/klap/raid5/cursor_files/reportes/fix_facom_prod_DRYRUN.csv
```

Revisar en el CSV:
- filas `SKIP_NO_PARSE` (hay que completar `ref` manualmente)
- filas `SKIP_COLLISION` (resolver antes o decidir otro criterio)

## 2) Batch chico (10–20) con escritura

```bash
NAKEL_TARGET=master_dev python3 scripts/aplicar_fix_facom.py \
  --only-posted --limit 20 \
  --skip-move-ids 21474,97028,25631,38203,50143,79042 \
  --out-csv /media/klap/raid5/cursor_files/reportes/fix_facom_prod_APPLY_batch20.csv \
  --apply --i-know-what-im-doing
```

Validacion manual en UI (contabilidad/compras):
- buscar por los `move_id` del CSV
- confirmar que el `name` ya no contiene `FACOM`
- confirmar que el `name` respeta `PV-NRO` (un solo `-`)
- confirmar que no rompe reportes ni conciliaciones visibles
- probar **liquidacion de impuesto** en staging antes de productivo (caso de exito)

## 3) Ejecucion completa

Cuando el batch chico fue OK:

```bash
NAKEL_TARGET=master_dev python3 scripts/aplicar_fix_facom.py \
  --only-posted \
  --skip-move-ids 21474,97028,25631,38203,50143,79042 \
  --out-csv /media/klap/raid5/cursor_files/reportes/fix_facom_prod_APPLY_full.csv \
  --apply --i-know-what-im-doing
```

## 4) Rollback (si hiciera falta)

El script guarda `name_old` y `move_id` en el CSV.
Para revertir, se puede armar un script corto que lea el CSV y haga `write` de `name_old` para los `action=WROTE`.

Recomendacion: antes de revertir, identificar el problema exacto (colisiones, impacto contable, etc.).

## Notas sobre IDs a omitir

- `21474,97028`: casos donde `ref` estuvo incompleta / correccion manual.
- `25631,38203,50143,79042`: colisiones detectadas en staging (si se corrigen a mano, omitirlas del batch).

