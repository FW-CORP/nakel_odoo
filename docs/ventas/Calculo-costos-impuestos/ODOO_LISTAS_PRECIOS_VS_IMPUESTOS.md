# Listas de precios vs impuestos en Odoo (master_dev) — criterio Nakel

Documento de referencia para alinear el modelo mental del **ERP Gestion (MSSQL)** con **Odoo 18 / master_dev**, en particular cuando se trabaja con productos con **impuesto interno** y la base local **`impuestos.sqlite`**.

**Fecha de registro:** 2026-04-03.

---

## 1. Dos capas distintas

| Concepto | Qué define | En Gestion (referencia) |
|----------|------------|-------------------------|
| **Lista de precios / margen** | **Cuánto se cobra** (precio por canal, cliente o política) | Tabla **`PRECIOS`**: `ID_ARTICULO`, `ID_LISTA_PRECIO`, **`PRECIO_NETO`**, **`PORC_GANANCIA`**. Cada lista puede tener **otro precio** para el mismo artículo. |
| **Impuesto (IVA, II, percepciones)** | **Reglas fiscales** (% o montos) sobre la base que corresponda según normativa y configuración | **`ARTICULOS.ID_IVA`** + **`TASASIVA`**. Impuesto interno y percepciones se modelan en Odoo con **`account.tax`** / localización, no duplicando un impuesto por cada lista solo por margen. |

El **margen comercial** altera el **precio unitario**. Los **impuestos** se aplican según el producto, la posición fiscal del partner y el tipo de operación — no es obligatorio crear **un `account.tax` por cada lista de precios** cuando lo único que cambia entre listas es el **porcentaje de ganancia** o el **precio final**.

---

## 2. Nombre engañoso en Gestion: `PRECIO_NETO`

En la base **Gestion**, para la lista típica (ej. **GENERAL**, `ID_LISTA_PRECIO = 1`), el campo **`PRECIOS.PRECIO_NETO`** coincide con el **precio final con IVA** que muestra el ERP viejo en pantalla (“Precio Con IVA”), no con el neto contable sin IVA.

- **Precio con IVA (venta):** `PRECIO_NETO`.
- **Precio sin IVA:** `PRECIO_NETO / (1 + TASASIVA.PORC_TASA/100)` (para `ID_IVA` con tasa 21 → divisor 1,21).

Esta lógica está implementada para cruzar con **`impuestos.sqlite`** en:

- `ventas/Calculo-costos-impuestos/actualizar_precios_venta_mssql_impuestos.py`  
  (dry-run por defecto; `--apply` para escribir; `--conservar-referencias` por defecto `80` si se quiere no pisar un precio manual).

---

## 3. Cómo lo encaja Odoo (documentación oficial)

- **Listas, descuentos y fórmulas:** [Pricelists, discounts, and formulas](https://www.odoo.com/documentation/17.0/applications/sales/sales/products_prices/prices/pricing.html) (Odoo 17; misma idea en 18).
- **Precios B2B (sin impuestos mostrados) vs B2C (con impuestos):** [B2B and B2C pricing](https://www.odoo.com/documentation/16.0/applications/finance/accounting/taxes/B2B_B2C.html).
- **Gestión de precios (eCommerce):** [Price management](https://www.odoo.com/documentation/17.0/applications/websites/ecommerce/products/price_management.html).

**master_dev (Enterprise)** admite múltiples listas, reglas avanzadas y posiciones fiscales. Lo que suele requerirse es **definir bien** si el precio guardado en lista/catálogo va **con IVA incluido o excluido** respecto de los impuestos del producto, para que factura y AFIP cuadren.

---

## 4. Práctica ya documentada en el vault Nakel

- **Estructura real en `master_dev` (Lista 1 / Lista 2, costo vs -FIX):** snapshot por API con IDs y cadena de listas → **`ventas/Listas de precios/ESTRUCTURA_COSTOS_Y_LISTAS_1_2_MASTER_DEV.md`** (actualizado **2026-04-07**).
- **PDV y listas con fórmulas:** en muchos casos el POS **no resuelve bien** listas con reglas complejas; se usan listas **-FIX** con precio **fijo** (snapshot). Ver `ventas/pdv-listas/README.md` y `ventas/Listas de precios/scripts/dry_run_snapshot_lista_desde_referencia.py`.
- **Migración de listas desde Excel:** `ventas/Listas de precios/scripts/README.md` (precios desde planilla hacia `product.pricelist`).
- **Percepción RG 5329** (filtrado en cálculo de impuestos): `modulo_rg5329-main/.../models/account_tax.py` — **no** sustituye la lógica de margen por lista.

---

## 5. Rol de `impuestos.sqlite`

Ubicación típica: `ventas/Calculo-costos-impuestos/impuestos.sqlite`.

Sirve para **auditoría y costos** en el subconjunto de productos con **impuesto interno** (planilla Excel + stock + fórmula col. G, precios venta desde MSSQL opcional). **No impone** en Odoo un diseño de “un impuesto fiscal por lista”; el cruce a Odoo sigue siendo: **precios en listas** (o `list_price`) + **impuestos en plantilla** según `l10n_ar` y política de la empresa.

Scripts relacionados en la misma carpeta:

- `construir_impuestos_sqlite.py`
- `actualizar_precios_venta_mssql_impuestos.py`
- `exportar_impuestos_sqlite_a_excel.py`

---

## 6. Cuándo sí tendrías más impuestos en Odoo (no por margen)

- Distinta **alícuota** o **exención** (producto/partner/op).
- **Percepciones / retenciones** según régimen (p. ej. RG 5329).
- **Impuesto interno** como impuesto específico **por producto o categoría**, no una copia del mismo IVA por cada lista solo porque `PORC_GANANCIA` cambia.

Si entre listas solo cambia el **precio** en Gestion, en Odoo eso se refleja como **otra lista** o **otra regla de precio**, no como otro impuesto idéntico con otro nombre.

---

## 7. Próximos pasos sugeridos (checklist)

1. Fijar convención: precio de **lista principal** ¿con IVA incluido en pantalla o excluido?
2. Revisar en **2–3 productos** (uno con II, uno sin II, uno vendido en POS) impuestos en plantilla vs línea de pedido/factura.
3. Si el problema es solo en **POS**, priorizar lista **-FIX** o revisar lista asignada al PDV según `ventas/pdv-listas/README.md`.

---

## Referencias cruzadas

- Costos MSSQL → Odoo: `mssql/ANALISIS_ACTUALIZACION_COSTOS_NAKEL.md` (incluye enlace a este documento al final).
- Fiscalidad / facturas Argentina: `qweb/README.md`.
