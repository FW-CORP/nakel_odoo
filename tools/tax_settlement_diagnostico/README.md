# Diagnóstico liquidación IIBB sufrido (`withholding_id.name`)

## Contexto

Al generar el archivo de **IIBB sufrido** desde liquidación de impuestos, el código de `odoo-argentina-ee` (`l10n_ar_account_tax_settlement`) asume que `account.move.line.withholding_id.name` es siempre un **string** con guiones (`pos-número`). Si `name` es **False** (campo `Char` vacío en Odoo), aparece:

`AttributeError: 'bool' object has no attribute 'split'`

## Dependencias del módulo (API)

`encontrar_apuntes_iibb_retencion_sin_certificado.py` — con una lista de **`account.move.line` ids** (los apuntes seleccionados al generar el TXT), marca cuáles entran en la rama **retención** (`payment_id` + `balance` ≠ 0) y tienen **`withholding_id` vacío** o **`name` vacío** (misma condición que rompe `get_pos_and_number` en el EE).

```bash
python3 encontrar_apuntes_iibb_retencion_sin_certificado.py --ids 510875,510876,...
```

`analizar_dependencias_modulo_api.py` lee **`ir.module.module`** y **`ir.module.module.dependency`**: estado (`installed`, etc.) de `l10n_ar_account_tax_settlement` y de cada dependencia registrada en la BD para esa base.

```bash
python3 analizar_dependencias_modulo_api.py
python3 analizar_dependencias_modulo_api.py -m l10n_ar_tax
```

*(Es lo que Odoo guardó al actualizar la lista de aplicaciones; si el árbol en disco del EE cambió y no se actualizó el módulo, puede haber pequeñas diferencias con el `__manifest__.py` del repo.)*

**SQL / Postgres:** `withholding_id` en `account.move.line` puede ser **solo ORM** (`compute` en `l10n_ar_tax`); no asumir columna `aml.withholding_id` en SQL. Ver incidente y SQL con `payment_id` + `tax_line_id` en `docs/incidentes/IIBB_SUFRIDO_LIQUIDACION_WITHHOLDING_NAME_master_dev.md`.

## Herramienta (solo API de consulta)

`diagnostico_iibb_sufrido_aml.py`:

- Conecta con `config_nakel.ODOO_CONFIG_MASTER_DEV` (por defecto `nakel.net.ar` / `master_dev`).
- `fields_get` sobre `account.move.line` para resolver el modelo de `withholding_id`.
- `search` + `read` en ese modelo: registros con `name` en `False` o `''`.
- Muestreo de `account.move.line` con `withholding_id` y cruce para listar AML cuya retención tiene nombre vacío.

**No** usa `create` / `write` / `unlink`.

```bash
cd /media/klap/raid5/cursor_files/nakel/nakel_odoo/tools/tax_settlement_diagnostico
python3 diagnostico_iibb_sufrido_aml.py
python3 diagnostico_iibb_sufrido_aml.py --limite-aml 800 --server-action-id 1065
```

Credenciales: mismas que el resto de scripts (`config_nakel` + opcional `nakel/.env`).

## Resultado típico en `master_dev` (muestra)

- Modelo destino: `l10n_ar.payment.withholding`.
- Decenas de retenciones con `name` vacío; la liquidación que incluye una línea AML con una de esas retenciones revienta al exportar.
- Detalle y opciones de remedio: `docs/incidentes/IIBB_SUFRIDO_LIQUIDACION_WITHHOLDING_NAME_master_dev.md`.

## Próximos pasos (fuera de este script)

1. **Datos:** completar `name` en los registros de retención afectados o corregir el origen que los creó sin certificado.
2. **Código:** parche defensivo en el servidor en `get_pos_and_number` (addon EE) o módulo puente en `nakel_odoo/addons/` si se acuerda política de upgrade.
