# IIBB sufrido — liquidación / `get_pos_and_number` (withholding / certificado)

## Resumen ejecutivo

- **Entorno:** `master_dev` en `nakel.net.ar` (Odoo 18 EE, productivo).
- **Síntoma:** `RPC_ERROR` / `AttributeError: 'bool' object has no attribute 'split'` al generar archivo de liquidación (acción servidor **1065** *Download File*, modelo `account.move.line`, código `action = records.get_tax_settlement_file()`).
- **Causa:** en EE `l10n_ar_account_tax_settlement`, `get_pos_and_number(full_number)` hace `full_number.split("-")` sin normalizar `False`/`None` (típico de `Char` vacío en Odoo, p. ej. `line.withholding_id.name`).
- **Parche Nakel:** addon `nakel_fix_iibb_settlement_name` (monkeypatch defensivo de la misma función global). Revisar tras cada upgrade del EE.

---

## 1) RPC / traza (completar desde el cliente si hace falta el ticket formal)

En sesiones de análisis por API no siempre queda la traza del navegador. Para un informe de cambio formal, conviene adjuntar desde el entorno del usuario:

- Línea de log werkzeug / traza Odoo del **500** / `AttributeError` en el momento del fallo.
- Si aplica: método (`iibb_sufrido_files_values`, etc.) y **id de asiento / pago** si el mensaje lo trae.

La traza típica ya citada apunta a `get_pos_and_number(line.withholding_id.name)` en `iibb_sufrido_files_values`.

---

## 2) IDs de líneas / movimiento y SQL (informe servidor)

**Importante:** en este stack, `account.move.line.withholding_id` es **campo calculado** (`compute="_compute_withholding"` en `l10n_ar_tax`), **no** columna en PostgreSQL. Por eso **no** aplica un `JOIN` directo `aml.withholding_id` en SQL.

### Equivalente SQL (replica lógica compute: mismo `payment_id` y `tax_line_id` = `tax_id` del withholding)

```sql
SELECT aml.id AS aml_id, aml.move_id, aml.payment_id, w.id AS withholding_id, w.name, w.tax_id
FROM account_move_line aml
JOIN account_payment p ON p.id = aml.payment_id
JOIN l10n_ar_payment_withholding w
  ON w.payment_id = p.id AND w.tax_id = aml.tax_line_id
WHERE aml.tax_line_id IS NOT NULL
  AND aml.payment_id IS NOT NULL
  AND (w.name IS NULL OR trim(COALESCE(w.name, '')) = '')
LIMIT 50;
```

**Resultado auditado en `master_dev` (muestra del servidor):**

| Métrica | Valor |
|--------|-------|
| Retenciones `l10n_ar_payment_withholding` con `name` NULL o vacío | **43** |
| Líneas `account_move_line` que encajan en el join anterior y retención sin nombre | **0** |

**Interpretación:** hay 43 retenciones sin nombre usable; hoy ninguna línea de asiento cumple el join `tax_line_id` + `payment_id` con esas retenciones (histórico, pagos sin esas líneas, u otra ruta que en Python sí pasa `False` a `get_pos_and_number`). **El parche defensivo sigue siendo válido:** normalizar `w.name` / argumento antes de `.split()`.

### Conteo y listado solo tabla retenciones

```sql
SELECT COUNT(*) AS withholding_sin_nombre
FROM l10n_ar_payment_withholding w
WHERE w.name IS NULL OR trim(COALESCE(w.name, '')) = '';
```

```sql
SELECT w.id, w.payment_id, w.tax_id, w.name, w.amount
FROM l10n_ar_payment_withholding w
WHERE w.name IS NULL OR trim(COALESCE(w.name, '')) = ''
ORDER BY w.id DESC
LIMIT 50;
```

---

## 3) Código en servidor (alinear el diff al disco del host)

| Dato | Valor |
|------|--------|
| Ruta archivo | `/opt/odoo/custom-addons/odoo-argentina-ee/l10n_ar_account_tax_settlement/models/account_journal.py` |
| Versión módulo EE (`__manifest__.py`) | **18.0.1.14.0** |
| Git repo EE en host | `HEAD` corto **94e6f75** |
| `get_pos_and_number` | definición **~L34–46** |
| Uso con comprobante factura/ND/NC | **~L273–282** (`move.l10n_latam_document_number`) |
| Uso IIBB sufrido | **~L1105–1114** (`line.withholding_id.name`) |

### Función `get_pos_and_number` (riesgo)

- Si `full_number` es `None`, falla en `.split`.
- Si es `False`, mismo error.
- Si es `""`, el flujo original puede devolver tuplas con segmentos vacíos; el `f"{number:>016s}"` downstream puede ser frágil según caso (menor que el crash con `bool`).

### Bloque `iibb_sufrido_files_values` (candidato típico)

```python
pos, number = get_pos_and_number(line.withholding_id.name)
```

Aquí `name` puede ser `False`/`None`/`""` según datos.

**Idea de parche (upstream o Nakel):** normalizar a `str` antes de `split`, o `ValidationError` explícito con ids de `payment`/`withholding` si se prefiere fallar controlado.

---

## 4) Dependencias del módulo (API)

`l10n_ar_account_tax_settlement` declara en BD (y están **installed** en `master_dev`): `account_tax_settlement`, `account_ux`, `l10n_ar`, `l10n_ar_account_reports`, `l10n_ar_ux`, `l10n_ar_tax`, `account_payment_pro_receiptbook`.

Script: `tools/tax_settlement_diagnostico/analizar_dependencias_modulo_api.py`.

---

## 5) Entregables en repo `nakel_odoo`

| Entregable | Ubicación |
|------------|-----------|
| Diagnóstico AML / acción 1065 (RPC) | `tools/tax_settlement_diagnostico/diagnostico_iibb_sufrido_aml.py` |
| Dependencias por API | `tools/tax_settlement_diagnostico/analizar_dependencias_modulo_api.py` |
| Parche defensivo instalable | `addons/nakel_fix_iibb_settlement_name/` |

---

## Checklist cierre ticket

- [ ] (Opcional) Pegar traza RPC/log cliente en el ticket.
- [ ] Decidir: **solo datos** (completar `name` en retenciones) vs **instalar** `nakel_fix_iibb_settlement_name` vs **PR upstream** a ADHOC.
- [ ] Tras upgrade EE: `git log -1 --follow -- l10n_ar_account_tax_settlement/models/account_journal.py` y revalidar el monkeypatch.

*Este documento incorpora el informe de solo consulta ejecutado en el servidor indicado por operaciones; si otro host tiene otro `HEAD` o manifiesto, alinear el diff allí.*
