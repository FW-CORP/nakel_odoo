# Informe — Coherencia RGAN_CPA / retenciones Ganancias (SICORE)

## Resumen ejecutivo

| Campo | Valor |
|-------|-------|
| **Entorno** | Odoo `master_dev` (solo lectura XML-RPC) |
| **Período analizado** | 2026-05-01 a 2026-05-15 (quincena) |
| **Archivo** | `ARCA-RETENCIONES/SICORE/out/RGAN_CPA_2026-05-01_a_2026-05-15.TXT` |
| **Registros** | 45 líneas (40 pagos con retención; prorrateo por factura reconciliada) |
| **Conclusión** | Los importes del TXT coinciden con Odoo. La retención total del período es **~$ 5,15 M**. Si el estudio suma **~$ 327 M**, está agregando el campo **importe total de factura**, no la retención. |

---

## 1) Tres totales distintos (no mezclar columnas)

El layout RGAN_CPA (145 caracteres, SIAP) distingue tres importes por línea:

| Concepto | Posición en línea | Campo | Suma quincena | ¿Es retención? |
|----------|-------------------|-------|---------------|----------------|
| Importe retenido | 79–93 | `retenido` | **$ 5.154.625,92** | **Sí** — lo que corresponde a Ganancias |
| Base imponible | 53–66 | `base` | $ 263.002.563,96 | No — base sobre la que se calcula |
| Importe total factura | 33–45 | `importe_total` | $ 327.723.480,22 | No — `amount_total` de la FC (con IVA) |

**Interpretación para el contador:** en SIAP/Excel debe sumarse la columna **retenido**. Si se suma **importe_total** o **base**, el total parece “millones de retención” pero en realidad son montos de facturación.

---

## 2) Coherencia matemática (archivo vs Odoo)

| Control | Resultado |
|---------|-----------|
| Suma `retenido` en TXT | $ 5.154.625,92 |
| Suma `credit` retenciones Ganancias en Odoo | $ 5.154.625,92 |
| Diferencia | $ 0,00 |
| Líneas RGAN (prorrateadas por FC) | 45 |
| Líneas impuesto en pagos (sin prorrateo) | 40 |
| Mediana por línea (retenido) | ~$ 36.582 |
| Alícuota efectiva promedio | ~1,96 % (rango 0,66 % – 2,36 %) |

**Validaciones:**

- En general: `retenido ≈ base × alícuota` (p. ej. 2 % sobre régimen 830 bienes).
- No se detectaron casos con `base` > total de factura reconciliada.
- El prorrateo por factura no duplica: la suma de líneas prorrateadas = total del pago en Odoo.

**Fuente en Odoo (script `generar_rgan_cpa_master_dev.py`):**

- Pagos proveedor con `l10n_ar_withholding_ids`.
- Impuestos con `account.tax.l10n_ar_tax_type = 'earnings'`.
- Por línea de retención: `tax_base_amount` → base; `credit` / `balance` → retenido.
- Si hay facturas reconciliadas: prorrateo de base y retención según `amount_total` de cada FC.

---

## 3) Caso outlier — NEW RITA S.A. - PANINI

Operación que más impacta el total de la quincena (~38 % del retenido acumulado).

| Dato | Valor |
|------|-------|
| Proveedor | NEW RITA S.A. - PANINI (CUIT 30-71474007-1) |
| Factura | FA-A 00001-00032455 (`account.move` id 164218) |
| Fecha factura | 2026-04-30 |
| Pago | OP-X 0001-00000068 — 2026-05-06 |
| Total FC (`importe_total` en TXT) | $ 119.644.800,00 |
| Neto / base retención (`amount_untaxed`) | $ 98.880.000,00 |
| IVA factura | $ 20.764.800,00 |
| Retención en TXT / Odoo | $ 1.977.600,00 |
| Alícuota | 2,00 % exacto |
| Impuesto Odoo | Retención gcias 830 sobre Bienes (`earnings`, 2 %) |
| Monto pago | $ 112.918.291,20 |

**Línea 9 del TXT (extracto de campos):**

| Campo | Valor |
|-------|-------|
| `nro_orden` | 000100032455 |
| `importe_total` | 119644800,00 |
| `base` | 98880000,00 |
| `retenido` | 1977600,00 |

**Qué revisar en Odoo (negocio, no del export):**

1. Confirmar que la FC **00001-00032455** por **$ 119,6 M** es correcta (compras / proveedor).
2. Pago **$ 112,9 M** vs FC **$ 119,6 M** — posible pago parcial u otras retenciones en el mismo OP (en Ganancias solo figura $ 1,98 M).

---

## 4) Top 10 — Mayor importe retenido

| # | Fecha | CUIT (13) | Base | Retenido | ~Alic % | Importe total FC |
|---|-------|-----------|------|----------|---------|------------------|
| 1 | 06/05/2026 | 8030714740071 | 98.880.000,00 | 1.977.600,00 | 2,00 | 119.644.800,00 |
| 2 | 07/05/2026 | 8030515658269 | 29.980.807,03 | 595.136,14 | 1,99 | 37.176.200,72 |
| 3 | 13/05/2026 | 8033521902839 | 12.218.310,00 | 244.366,20 | 2,00 | 15.150.704,40 |
| 4 | 14/05/2026 | 8030626863945 | 8.859.747,02 | 208.856,40 | 2,36 | 16.282.147,06 |
| 5 | 12/05/2026 | 8020283088341 | 9.970.511,99 | 194.930,24 | 1,96 | 12.064.319,54 |
| 6 | 04/05/2026 | 8030714740071 | 9.584.640,00 | 187.212,80 | 1,95 | 11.597.414,40 |
| 7 | 05/05/2026 | 8033521902839 | 9.503.130,00 | 185.582,60 | 1,95 | 11.783.881,20 |
| 8 | 08/05/2026 | 8030626863945 | 6.815.329,83 | 131.826,60 | 1,93 | 8.451.009,00 |
| 9 | 12/05/2026 | 8030717620212 | 6.399.664,17 | 123.513,28 | 1,93 | 7.794.197,64 |
| 10 | 15/05/2026 | 8030715733176 | 5.441.707,90 | 104.354,16 | 1,92 | 6.747.717,80 |

---

## 5) Otros picos y prorrateo

| Retenido | Proveedor | Factura (ref) | Nota |
|----------|-----------|---------------|------|
| $ 595.136 | DIELO S.A. | 00011-00133002 | FC ~ $ 37 M |
| $ 244.366 | ALEXVIAN S.A. | 00012-00075347 | |
| $ 208.856 | PRODUCTOS TRIO S.A. | 00005-00091052 | Base prorrateada < total FC → alícuota efectiva ~2,36 % |

**Mismo CUIT + mismo día con varias líneas RGAN:** 4 situaciones (pagos distintos o varias FC en un pago; no duplicación del mismo importe).

| CUIT | Fecha | Líneas | Retenido sumado | Base sumada |
|------|-------|--------|-----------------|-------------|
| 33707338119 | 2026-05-13 | 3 | $ 98.646,63 | $ 5.156.331,58 |
| 30663137375 | 2026-05-12 | 2 | $ 41.594,14 | $ 2.303.707,10 |
| 30708968648 | 2026-05-11 | 2 | $ 33.088,83 | $ 1.878.441,66 |

---

## 6) Conclusiones

| Pregunta | Respuesta |
|----------|-----------|
| ¿El export inventa millones de retención? | **No.** Retención real del período: **~$ 5,15 M**. |
| ¿Puede haber imputación rara en Odoo? | **Posible** en operaciones puntuales (validar FC de alto importe con compras). |
| ¿El script mezcla campos? | **No.** `importe_total` = monto FC; `retenido` = retención efectiva. |
| ¿Datos = mismos campos DB? | **Sí.** `tax_base_amount`, `credit`, `amount_total` de factura reconciliada. |

---

## 7) Recomendación al estudio contable

1. Confirmar qué columna del importador SIAP / planilla Excel están totalizando.
2. Usar **solo** el importe de la posición **retenido** (79–93) para el total a declarar / comparar.
3. Revisar en Odoo la FC **FA-A 00001-00032455** (NEW RITA / PANINI) si el monto de negocio no cierra.
4. Regenerar archivo si corrigen datos:

```bash
cd …/ARCA-RETENCIONES
python3 SICORE/tools/generar_rgan_cpa_master_dev.py \
  --desde 2026-05-01 --hasta 2026-05-15 \
  --out SICORE/out/RGAN_CPA_2026-05-01_a_2026-05-15.TXT
```

---

## Referencias

- Repo: `FW-CORP/arca-retenciones` → `ARCA-RETENCIONES/SICORE/tools/generar_rgan_cpa_master_dev.py`
- Manual quincena: `ARCA-RETENCIONES/Documentacion/MANUAL_ARCA_RETENCIONES_QUINCENA.md`
- Fecha informe: 2026-05-19
