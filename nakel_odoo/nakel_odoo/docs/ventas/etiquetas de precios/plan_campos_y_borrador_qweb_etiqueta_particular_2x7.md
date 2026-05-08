# Plan de campos mínimos + borrador QWeb — “Nakel Particular” 2×7 (PDF)

**Objetivo**: crear un **nuevo** formato de etiqueta PDF 2×7 para góndola en `dev.nakel.net.ar / master_test`, sin sobrescribir los reportes estándar de Odoo, cumpliendo lo relevado de la **Resolución 4/2025**.

La referencia visual deseada (según tus capturas) es:

- bloque con **nombre del producto** a la izquierda
- a la derecha, 3 renglones:
  1) **“Precio final a Particular”** + importe grande
  2) **“Precio sin impuestos nacionales (IVA)”** + importe más chico
  3) **“Precio al Particular por cada <unidad>”** + importe más chico
- barcode debajo (si existe)

Además, se debe garantizar “**góndola = caja**” (el precio final mostrado debe coincidir con lo cobrado).

---

## 1) Campos mínimos para poder cumplir “precio por unidad de medida”

Hoy en Odoo el `uom_id` suele ser “Units” y `weight/volume` no representan de forma confiable el contenido neto (son peso/volumen logístico del ítem). Para calcular “precio por litro/kg/…”, hace falta un dato explícito.

### 1.1 Propuesta recomendada (campos explícitos en `product.template`)

- **`x_contenido_neto_valor`** (float)
  - Ejemplos: `2.0`, `0.75`, `340`, `80`
- **`x_contenido_neto_uom`** (selection)
  - Valores sugeridos: `g`, `ml`, `kg`, `l`, `unidad`

**Regla normativa de envases chicos**:
- si `x_contenido_neto_uom` es `g` o `ml` y `x_contenido_neto_valor <= 50`, el precio unitario debe expresarse por **10 g/ml** (no por 100).

### 1.2 Fallback (si no está el dato)

Si falta contenido neto explícito, se puede:
- intentar **parsear** desde el nombre (patrones típicos `X750ML`, `X1L`, `X340G`, etc.)
- y si falla, mostrar “precio por unidad” como **$/unidad** (porque la norma acepta “por una sola unidad”)

---

## 2) Qué impuestos usar para el cálculo “Particular”

En `master_test` se relevó:
- impuestos de venta con `price_include = False` (no vienen incluidos en el precio base)
- IVA 21% típico (`IVA 21% Ventas`)
- algunos productos con **impuesto interno** fijo (“Imp Int.”)

Para una etiqueta de góndola “Particular” se recomienda:
- **usar impuestos del producto** (`product.taxes_id`) para construir el **precio final**
- **no** incluir percepciones/retenciones dependientes del cliente

### 2.1 Cálculos (dentro de QWeb)

Tomando:
- `precio_base` = precio desde la lista (sin impuestos)
- `taxes = product.taxes_id` (ventas)

Entonces:
- **Precio final a Particular**: `total_included`
- **Precio sin impuestos nacionales (IVA)**: `total_excluded`

En QWeb se hace con `taxes.compute_all(...)` (funciona dentro de Odoo con `currency` como recordset).

---

## 3) Borrador QWeb (celda 2×7) — contenido principal

Este borrador es para un **template nuevo** (clonado de `product.report_simple_label2x7`) y ajustado al layout de tu ejemplo.

> Nota: acá muestro solo el bloque de “contenido”; al implementarlo se mantiene el sizing estándar 2×7 para que calce en la hoja.

```xml
<t t-name="nakel.report_simple_label2x7_particular">
    <t t-set="barcode_size" t-value="'width:33mm;height:14mm'"/>
    <t t-set="table_style" t-value="'width:97mm;height:37.1mm;' + table_style"/>

    <!-- Precio base desde la lista (sin impuestos en master_test) -->
    <t t-set="price_base"
       t-value="pricelist._get_product_price(product, 1, currency=pricelist.currency_id or product.currency_id)"/>

    <!-- Impuestos del producto (ventas) -->
    <t t-set="taxes_res"
       t-value="product.taxes_id.compute_all(price_base, currency=pricelist.currency_id or product.currency_id, quantity=1.0, product=product)"/>
    <t t-set="price_final" t-value="taxes_res.get('total_included')"/>
    <t t-set="price_net" t-value="taxes_res.get('total_excluded')"/>

    <!-- Contenido neto (campos custom) -->
    <t t-set="content_val" t-value="getattr(product, 'x_contenido_neto_valor', False)"/>
    <t t-set="content_uom" t-value="getattr(product, 'x_contenido_neto_uom', False)"/>

    <!-- Unidad para texto “por cada ...” -->
    <t t-set="unit_label"
       t-value=\"('litro' if content_uom in ('l','ml') else ('kilo' if content_uom in ('kg','g') else 'unidad'))\"/>

    <!-- Normalización a litro/kg para el cálculo unitario -->
    <t t-set="content_in_base_unit"
       t-value=\"(content_val / 1000.0 if content_uom in ('ml','g') else (content_val if content_uom in ('l','kg') else 1.0))\"/>

    <!-- Regla 10 g/ml si envase <= 50 -->
    <t t-set=\"small_pack_ref\"
       t-value=\"(10.0 if content_uom in ('ml','g') and content_val and content_val <= 50.0 else False)\"/>
    <t t-set=\"content_for_unit_price\"
       t-value=\"(small_pack_ref / 1000.0 if small_pack_ref and content_uom in ('ml','g') else content_in_base_unit)\"/>

    <t t-set=\"unit_price\"
       t-value=\"(price_final / content_for_unit_price) if (content_for_unit_price and content_for_unit_price > 0) else price_final\"/>

    <td t-att-style="make_invisible and 'visibility:hidden;'">
        <div class="o_label_full" t-att-style="table_style">
            <!-- Izquierda: nombre -->
            <div class="o_label_name" style="width: 45%; float:left;">
                <strong t-field="product.display_name"/>
            </div>

            <!-- Derecha: precios -->
            <div style="width: 55%; float:right; line-height: 1.05;">
                <div style="font-size: 9px; text-align:center; font-weight:600;">
                    Precio final a Particular
                </div>
                <div style="text-align:center; font-size: 26px; font-weight: 800;">
                    <span t-out="price_final"
                          t-options="{'widget':'monetary','display_currency': pricelist.currency_id or product.currency_id, 'label_price': True}"/>
                </div>
                <div style="font-size: 9px; text-align:center;">
                    Precio sin impuestos nacionales (IVA)
                    <span t-out="price_net"
                          t-options="{'widget':'monetary','display_currency': pricelist.currency_id or product.currency_id, 'label_price': True}"/>
                </div>
                <div style="font-size: 9px; text-align:center;">
                    Precio al Particular por cada
                    <t t-if="small_pack_ref">
                        10 <t t-out=\"'ml' if content_uom == 'ml' else 'g'\"/>
                    </t>
                    <t t-elif=\"content_uom in ('ml','l')\">litro</t>
                    <t t-elif=\"content_uom in ('g','kg')\">kilo</t>
                    <t t-else=\"\">unidad</t>
                    <span t-out=\"unit_price\"
                          t-options=\"{'widget':'monetary','display_currency': pricelist.currency_id or product.currency_id, 'label_price': True}\"/>
                </div>
            </div>

            <!-- Barcode -->
            <div style="clear: both; padding-top: 2mm;">
                <t t-if="barcode">
                    <div class="text-center" t-out="barcode"
                         t-options="{'widget': 'barcode', 'symbology': 'auto', 'img_style': barcode_size}"/>
                </t>
            </div>
        </div>
    </td>
</t>
```

---

## 4) Qué queda para “listo para implementar” (pasos técnicos)

1) **Clonar** el reporte `Product Label 2x7 (PDF)` a uno nuevo:
   - nombre: `Nakel Particular 2x7 (PDF)`
   - `report_name`: `nakel.report_producttemplatelabel2x7_particular`
   - mismo `paperformat_id`

2) Crear `ir.ui.view` wrapper nuevo:
   - `t-name="nakel.report_producttemplatelabel2x7_particular"`
   - set `columns=2`, `rows=7`
   - llamar a `product.report_productlabel` pero sustituyendo la celda 2x7 por `nakel.report_simple_label2x7_particular`
     - (alternativa: clonar `product.report_productlabel` a `nakel.report_productlabel` y cambiar ahí el `t-call`)

3) Cargar los **campos de contenido neto** en productos (al menos para un set piloto) o habilitar fallback por parseo.

---

## 5) Recomendación operativa para evitar “góndola ≠ caja”

Para sostener “góndola = caja”:
- el **precio final** de la etiqueta debe usar la **misma lista** que usa el POS/venta “Particular”
- y sumar solo los impuestos “de producto” (IVA + internos) que efectivamente se cobran en venta al consumidor final.

Ver también: `ventas/etiquetas de precios/informe_resolucion_4_2025_exhibicion_de_precios.md`.

