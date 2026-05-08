# Análisis técnico (Odoo) — Etiquetas PDF 2×7 en `master_test`

**Ambiente**: `dev.nakel.net.ar` / **`master_test`**  
**Objetivo**: reunir evidencia técnica y decisiones necesarias para crear una nueva etiqueta **PDF 2×7** “Nakel Consumidor Final” cumpliendo **Resolución 4/2025 (Exhibición de Precios)** sin sobrescribir los formatos existentes.

---

## 1) Qué imprime hoy Odoo (base 2×7)

En `master_test`, el formato estándar “2×7” está implementado como **reporte QWeb PDF**:

- **Acción de reporte** (`ir.actions.report`):
  - **ID**: `186`
  - **Nombre**: `Product Label 2x7 (PDF)`
  - **Modelo**: `product.template`
  - **Tipo**: `qweb-pdf`
  - **Report name**: `product.report_producttemplatelabel2x7`
  - **Paperformat**: `A4 Label Sheet` (A4 Portrait, márgenes 0, DPI 96)

- **Template “wrapper”** (`ir.ui.view`):
  - **key**: `product.report_producttemplatelabel2x7`
  - Setea `columns=2`, `rows=7` y delega a `product.report_productlabel`.

- **Template de “plancha”**:
  - **key**: `product.report_productlabel`
  - Según `columns/rows` llama a `product.report_simple_label2x7` (la “celda” de cada etiqueta).

- **Template de celda 2×7 (donde se dibuja la etiqueta)**:
  - **key**: `product.report_simple_label2x7`
  - Muestra `product.display_name`, `product.default_code`, barcode (si hay) y un **precio** calculado desde la lista:
    - `pricelist._get_product_price(product, 1, currency=...)`

**Implicación**: para “Nakel Consumidor Final” conviene **clonar** la acción + los templates (wrapper/celda) y editar solo el nuevo template, sin tocar los originales.

---

## 2) Impuestos en `master_test` (impacto sobre “precio final” y “precio sin impuestos nacionales”)

### 2.1 Hallazgo clave: los impuestos de venta NO están incluidos en el precio base

En `account.tax` (ventas) se observa:

- **`price_include = False`** en todos los impuestos de venta relevados.
- **`include_base_amount = False`** en todos los impuestos de venta relevados.

**Interpretación**: el “precio base” que sale de la lista (`pricelist._get_product_price(...)`) es **sin impuestos incluidos**, y para llegar al “importe total y final” (Resolución 4/2025) hay que **sumar** impuestos aplicables.

### 2.2 Impuestos típicos detectados en productos

En una muestra de productos vendibles (`product.template.sale_ok=True`) se detectó:

- Impuesto habitual: **IVA 21% Ventas** (`account.tax` id **110**, `amount_type=percent`, `amount=21`, `price_include=False`, grupo `VAT 21%`).
- En algunos productos (ej. bebidas alcohólicas): impuestos **fijos** asociados a “Imp Int.” (impuesto interno), por ejemplo:
  - `3965 - ... Imp Int. 894.38` (`account.tax` id **494**, `amount_type=fixed`, `amount=894.38`, grupo `Other Taxes`, `l10n_ar_tribute_afip_code='99'`).

Además existen en la base muchos impuestos de percepción (municipales/provinciales) en grupos específicos (p. ej. `Municipal Taxes Perceptions`). Estos suelen depender del cliente/condición fiscal y **no** son adecuados para una etiqueta general de góndola (consumidor final).

---

## 3) Cómo cumplir Resolución 4/2025 con datos actuales (reglas de cálculo)

La normativa exige:

1) **Precio final** (importe total y final a abonar), en ARS  
2) **Importe neto** con leyenda **“PRECIO SIN IMPUESTOS NACIONALES”** (tipografía menor)  
3) **Precio por unidad de medida** (tipografía menor; regla 10 g/ml si ≤ 50 g/ml)

### 3.1 Precio final (recomendado)

En QWeb (en servidor, con recordsets reales), la forma robusta es usar el motor de impuestos:

- Base (desde lista): `precio_base = pricelist._get_product_price(product, 1, currency=...)`
- Impuestos del producto: `product.taxes_id` (ventas)
- Cálculo: `taxes_res = product.taxes_id.compute_all(precio_base, currency, 1.0, product=product, partner=partner)`
  - `taxes_res['total_included']` → **precio final**
  - `taxes_res['total_excluded']` → base sin impuestos (ver 3.2)

**Nota**: este `compute_all` no pudo ejecutarse por XML-RPC en este análisis (porque allí `currency` viaja como `int`), pero **sí funciona dentro de QWeb** (porque QWeb corre dentro de Odoo con objetos `res.currency`).

### 3.2 “PRECIO SIN IMPUESTOS NACIONALES”

La resolución pide mostrar el importe neto **sin IVA** y **sin otros impuestos nacionales indirectos** que impacten en el precio.

Con los datos actuales (todos `price_include=False`), el **punto de partida** natural es:

- `neto_sin_impuestos = taxes_res['total_excluded']`

Esto cumple “sin IVA” si el IVA está en `product.taxes_id`. Para el resto de impuestos nacionales indirectos:

- Si los impuestos internos (“Imp Int.”) están en `product.taxes_id` (ej. id 494), también quedan excluidos en `total_excluded`.

**Riesgo a documentar**: en la base existen impuestos de percepción (municipales/provinciales) como `account.tax` de venta, pero no deberían formar parte de una etiqueta de góndola “genérica” de consumidor final porque dependen del cliente. Para la etiqueta se recomienda calcular con **los impuestos del producto** (IVA + internos) y **no** con percepciones configuradas por partner.

---

## 4) Precio por unidad de medida (problema de datos y opciones)

La resolución exige “precio por unidad de medida” (kg/L/m/unidad) y para envases ≤ 50 g/ml, referencia a 10 g/ml.

### 4.1 Situación actual relevada

- Los productos suelen tener `uom_id = Units` (unidad), incluso para artículos cuyo nombre indica contenido (p. ej. `X750ML`, `X350G`).
- Existen campos estándar `product.template.weight` y `product.template.volume`, pero:
  - están cargados en muchos productos,
  - **no representan necesariamente el contenido neto** (por ejemplo, botellas de 750 ml tienen `weight` ~1.16 kg, que es el peso del ítem, no litros).
- `product.packaging` existe y está cargado, pero describe **unidades por bulto/caja** (`qty`, `product_uom_id=Units`), no el contenido neto (g/ml).

### 4.2 Opciones para poder calcular el precio unitario en una etiqueta

1) **Opción recomendada (robusta)**: agregar **campos explícitos de contenido neto** en `product.template`:
   - `contenido_valor` (número)
   - `contenido_unidad` (selección: g, ml, kg, l, unidad)
   - Esto permite calcular \(precio\_unitario = precio\_final / contenido\) con la unidad correcta y aplicar la regla 10 g/ml.

2) **Opción “rápida” (menos robusta)**: parsear el contenido desde `product.name` / `display_name` (patrones `X750ML`, `X1L`, `X340G`, etc.).
   - Pros: no requiere datos nuevos.
   - Contras: depende de convención de nombres; falla con nombres inconsistentes.

3) **Opción híbrida**: usar parseo como fallback y permitir sobreescritura manual con campos explícitos.

---

## 5) Recomendación de implementación (sin sobrescribir, en `master_test`)

Para crear “**Nakel Consumidor Final 2×7 (PDF)**” sin tocar los estándares:

- Crear un nuevo `ir.actions.report` (copiando el `186`):
  - nuevo `name`
  - nuevo `report_name` y `report_file` (namespace Nakel)
  - mismo `paperformat_id = A4 Label Sheet`
  - mismo `model = product.template`

- Crear nuevos templates QWeb:
  - wrapper nuevo (similar a `product.report_producttemplatelabel2x7`) que llame a un `report_productlabel` propio o reutilice el existente.
  - celda nueva: clonar `product.report_simple_label2x7` y modificar:
    - **Precio final**: usar `compute_all(...).get('total_included')`
    - **Precio sin impuestos nacionales**: `compute_all(...).get('total_excluded')` + leyenda
    - **Precio por unidad**: según estrategia (campos explícitos o parseo)

---

## 6) Próximo documento

Ver `ventas/etiquetas de precios/informe_resolucion_4_2025_exhibicion_de_precios.md` para requisitos legales y checklist.

