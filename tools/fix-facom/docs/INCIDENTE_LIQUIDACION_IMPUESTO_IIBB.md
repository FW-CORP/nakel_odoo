---
title: Incidente — liquidacion IIBB y formato de numero de factura
updated: 2026-04-26
---

## Resumen

Al intentar **liquidar un impuesto** (IIBB sufrido) en `staging.nakel.net.ar` se produjo un error de servidor:

- `ValueError: too many values to unpack (expected 2)`

La causa fue el formato del numero de documento que la localizacion AR intenta parsear con un `split('-')`.

## Causa raiz

La localizacion AR (stack observado):

- `l10n_ar_account_tax_settlement` -> `iibb_sufrido_files_values`
- llama a `account.move._l10n_ar_get_document_number_parts(...)`
- termina en `l10n_ar/models/account_move.py` haciendo:

`pos, invoice_number = document_number.split('-')`

Eso asume que `document_number` tiene **exactamente un guion** y viene como:

- `PV-NRO` (ej. `00010-00100648`)

Luego del fix inicial, `account.move.name` quedo con un prefijo con guion:

- `FA-A 00010-00100648`

Por lo tanto `split('-')` devuelve mas de 2 partes y explota.

## Solucion aplicada (staging `sg_dev1`)

Se corrigio el criterio para que el `name` sea **solo** `PV-NRO`:

- `FA-A 00010-00100648` -> `00010-00100648`

Se aplico el script:

- `scripts/reparar_name_para_liquidacion.py`

Resultado en `sg_dev1`:

- `candidates=311`
- `WROTE=311`
- Backup CSV: `reparar_name_liquidacion_sg_dev1_APPLIED.csv` (fuera del repo)

## Caso de exito

Luego de la correccion, se pudo avanzar con la liquidacion sin el error `too many values to unpack`.

## Accion preventiva para productivo

- El script de aplicacion `scripts/aplicar_fix_facom.py` fue actualizado para escribir `name` como `PV-NRO` (un solo guion).
- El runbook productivo (`RUNBOOK_PRODUCTIVO.md`) fue actualizado para reflejar este requisito.

