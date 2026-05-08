---
title: Arreglo FACOM — Facturas de compra (vendor bills)
updated: 2026-04-25
---

## Objetivo

Eliminar el prefijo **`/FACOM`** como “número visible” en **facturas de compra** (Odoo `account.move` con `move_type='in_invoice'`) migrando/normalizando el número a un formato estándar argentino **tomado de la factura** del proveedor.

## Contexto (Odoo)

- **`account.move.name`**: numeración interna del asiento/factura (sale de la **secuencia del diario**).
- **`account.move.ref`** (y/o campos LATAM según configuración): referencia/número del comprobante del proveedor (típicamente `PPPP-NNNNNNNN` en AR).

El prefijo `FACOM` suele provenir del **diario de compras** (`account.journal.code = 'FACOM'`) y su secuencia asociada.

## Conexión (staging `sg_dev1`)

Este directorio asume operación **solo lectura** por XML-RPC.

- Target: `NAKEL_TARGET=staging_sg_dev1`
- URL: `https://staging.nakel.net.ar`
- DB: `sg_dev1`

Las credenciales por defecto se toman de las variables de `dev` (`ODOO_MASTER_DEV_USERNAME/PASSWORD`) salvo override explícito con `ODOO_STAGING_*`.

## Scripts (solo lectura)

- `scripts/inspeccionar_facom_staging.py`
  - Lista el diario `FACOM` y sus campos de secuencia.
  - Muestra ejemplos de facturas proveedor donde `name` contiene `FACOM`/`/FACOM`.
  - Compara `name` vs `ref` y detecta casos donde el número “estándar” puede derivarse de `ref`.

## Próximo entregable (cambio)

Para aplicar el cambio de forma **segura**, usar el enfoque:

- **Backup primero**: exportar CSV con `move_id`, `name_old`, `ref`, `name_new`, `fallback_reason`.
- **Validación de colisiones**: asegurar que el `name_new` no exista ya en `account.move` del mismo `journal_id`/compañía.
- **Ejecución por tandas**: empezar con 5–20 registros y revisar en UI.
- **Exclusiones**: omitir IDs ya corregidos manualmente (ej. Paula) mediante `--skip-move-ids`.
- **Escritura explícita**: el script debe ser dry-run por defecto y requerir un flag para escribir.

Scripts:

- `scripts/aplicar_fix_facom.py` (write, con dry-run por defecto)

Una vez que el análisis confirme campos y casos borde, el script de **modificación** (write) hace:

- recalcular el “nuevo número” desde `ref` (factura proveedor),
- actualizar el campo objetivo (a definir según tu criterio: **cambiar `name`** o **mover a `ref` y ajustar vistas/reportes**),
- registrar un backup/csv de antes/después.

