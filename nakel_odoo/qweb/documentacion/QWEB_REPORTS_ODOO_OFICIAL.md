# QWeb Reports - Documentación Oficial de Odoo

**Fuente**: https://odoo-master.readthedocs.io/en/master/reference/reports.html  
**Versión**: Odoo Master  
**Última actualización**: 2025-12-28

---

## Report Action

### Definición Básica

Para crear un reporte, necesitas definir una **report action**. Por simplicidad, existe un elemento `<report>` como atajo para definir un reporte, en lugar de tener que configurar la acción manualmente.

### Atributos del Elemento `<report>`

El elemento `<report>` puede tomar los siguientes atributos:

- **`id`**: El ID externo del registro generado
- **`name`** (obligatorio): Útil como mnemónico/descripción del reporte
- **`model`** (obligatorio): El modelo sobre el cual será el reporte
- **`report_type`** (obligatorio): `qweb-pdf` para PDF o `qweb-html` para HTML
- **`report_name`**: El nombre del reporte (será el nombre del PDF de salida)
- **`groups`**: Campo Many2many a los grupos permitidos para ver/usar el reporte actual
- **`attachment_use`**: Si se establece en `True`, el reporte se almacenará como adjunto del registro usando el nombre generado por la expresión de adjunto
- **`attachment`**: Expresión Python que define el nombre del reporte; el registro es accesible como la variable `object`

### ⚠️ Advertencia: Paper Format

El formato de papel **no puede** declararse actualmente mediante el atajo `<report>`, debe agregarse después usando una extensión `<record>` en la acción del reporte:

```xml
<record id="<report_id>" model="ir.actions.report.xml">
    <field name="paperformat_id" ref="<paperformat>"/>
</record>
```

### Ejemplo

```xml
<report
    id="account_invoices"
    model="account.invoice"
    string="Invoices"
    report_type="qweb-pdf"
    name="account.report_invoice"
    file="account.report_invoice"
    attachment_use="True"
    attachment="(object.state in ('open','paid')) and
        ('INV'+(object.number or '').replace('/','')+'.pdf')"
/>
```

---

## Template del Reporte

### Template Mínimo Viable

Un template mínimo se vería así:

```xml
<template id="report_invoice">
    <t t-call="report.html_container">
        <t t-foreach="docs" t-as="o">
            <t t-call="report.external_layout">
                <div class="page">
                    <h2>Report title</h2>
                    <p>This object's name is <span t-field="o.name"/></p>
                </div>
            </t>
        </t>
    </t>
</template>
```

**Notas importantes:**
- Llamar a `external_layout` agregará el encabezado y pie de página predeterminados en tu reporte
- El cuerpo del PDF será el contenido dentro del `<div class="page">`
- El `id` del template debe ser el nombre especificado en la declaración del reporte (por ejemplo, `account.report_invoice` para el reporte anterior)
- Como es un template QWeb, puedes acceder a todos los campos de los objetos `docs` recibidos por el template

### Variables Específicas en Reportes

Hay algunas variables específicas accesibles en reportes:

- **`docs`**: Registros para el reporte actual
- **`doc_ids`**: Lista de IDs para los registros docs
- **`doc_model`**: Modelo para los registros docs
- **`time`**: Referencia a `time` de la biblioteca estándar de Python
- **`user`**: Registro `res.user` para el usuario que imprime el reporte
- **`res_company`**: Registro para la compañía del usuario actual

Si deseas acceder a otros registros/modelos en el template, necesitarás un **custom report**.

---

## Templates Traducibles

Si deseas traducir reportes (al idioma de un partner, por ejemplo), necesitas definir dos templates:

1. El template principal del reporte
2. El documento traducible

Luego puedes llamar al documento traducible desde tu template principal con el atributo `t-lang` establecido en un código de idioma (por ejemplo, `fr` o `en_US`) o a un campo de registro. También necesitarás volver a buscar los registros relacionados con el contexto adecuado si usas campos que son traducibles (como nombres de países, condiciones de venta, etc.)

### ⚠️ Advertencia

Si tu template de reporte **no usa campos de registro traducibles**, volver a buscar el registro en otro idioma **no es necesario** y afectará el rendimiento.

### Ejemplo: Sale Order Report

```xml
<!-- Template principal -->
<template id="report_saleorder">
    <t t-call="report.html_container">
        <t t-foreach="docs" t-as="doc">
            <t t-call="sale.report_saleorder_document" t-lang="doc.partner_id.lang"/>
        </t>
    </t>
</template>

<!-- Template traducible -->
<template id="report_saleorder_document">
    <!-- Re-buscar el registro con el idioma del partner -->
    <t t-set="doc" t-value="doc.with_context({'lang':doc.partner_id.lang})" />
    <t t-call="report.external_layout">
        <div class="page">
            <div class="oe_structure"/>
            <div class="row">
                <div class="col-xs-6">
                    <strong t-if="doc.partner_shipping_id == doc.partner_invoice_id">Invoice and shipping address:</strong>
                    <strong t-if="doc.partner_shipping_id != doc.partner_invoice_id">Invoice address:</strong>
                    <div t-field="doc.partner_invoice_id" t-field-options="{&quot;no_marker&quot;: true}"/>
                </div>
                <!-- ... más contenido ... -->
            </div>
            <div class="oe_structure"/>
        </div>
    </t>
</template>
```

**Nota**: Esto funciona **solo cuando se llama a templates externos**. No podrás traducir parte de un documento estableciendo un atributo `t-lang` en un nodo XML que no sea `t-call`.

---

## Códigos de Barras

Los códigos de barras son imágenes devueltas por un controlador y pueden incrustarse fácilmente en reportes gracias a la sintaxis QWeb:

```xml
<!-- Código QR simple (ruta con tipo en el path) -->
<img t-att-src="'/report/barcode/QR/%s' % 'My text in qr code'"/>

<!-- Odoo 18+: query string usa barcode_type (no "type"; si no, falla report_barcode) -->
<img t-att-src="'/report/barcode/?barcode_type=%s&amp;value=%s&amp;width=%s&amp;height=%s' % ('QR', 'text', 200, 200)"/>

<!-- Valores con URL o caracteres especiales: codificar value en QWeb con quote_plus(...) -->
```

En **Odoo 18**, el parámetro de query `type=` quedó obsoleto frente a `barcode_type=`. Para URLs largas (p. ej. QR AFIP), concatenar `value=` con `quote_plus(campo)`.

---

## Observaciones Útiles

1. **Twitter Bootstrap y FontAwesome**: Las clases de Twitter Bootstrap y FontAwesome pueden usarse en tu template de reporte

2. **CSS Local**: El CSS local puede ponerse directamente en el template

3. **CSS Global**: El CSS global puede insertarse en el layout principal del reporte heredando su template e insertando tu CSS:

```xml
<template id="report_saleorder_style" inherit_id="report.layout">
    <xpath expr="//style" position="after">
        <style type="text/css">
            .example-css-class {
                background-color: red;
            }
        </style>
    </xpath>
</template>
```

---

## Paper Format (Formato de Papel)

Los formatos de papel son registros de `report.paperformat` y pueden contener los siguientes atributos:

- **`name`** (obligatorio): Útil como mnemónico/descripción
- **`description`**: Una pequeña descripción de tu formato
- **`format`**: Un formato predefinido (A0 a A9, B0 a B10, Legal, Letter, Tabloid, ...) o `custom`; A4 por defecto. No puedes usar un formato no personalizado si defines las dimensiones de la página.
- **`dpi`**: DPI de salida; 90 por defecto
- **`margin_top`, `margin_bottom`, `margin_left`, `margin_right`**: Tamaños de márgenes en mm
- **`page_height`, `page_width`**: Dimensiones de la página en mm
- **`orientation`**: `Landscape` o `Portrait`
- **`header_line`**: Booleano para mostrar una línea de encabezado
- **`header_spacing`**: Espaciado del encabezado en mm

### Ejemplo

```xml
<record id="paperformat_frenchcheck" model="report.paperformat">
    <field name="name">French Bank Check</field>
    <field name="default" eval="True"/>
    <field name="format">custom</field>
    <field name="page_height">80</field>
    <field name="page_width">175</field>
    <field name="orientation">Portrait</field>
    <field name="margin_top">3</field>
    <field name="margin_bottom">3</field>
    <field name="margin_left">3</field>
    <field name="margin_right">3</field>
    <field name="header_line" eval="False"/>
    <field name="header_spacing">3</field>
    <field name="dpi">80</field>
</record>
```

---

## Custom Reports (Reportes Personalizados)

El modelo de reporte tiene una función `get_html` predeterminada que busca un modelo llamado `report._module.report_name`. Si existe, lo usará para llamar al motor QWeb; de lo contrario, se usará una función genérica.

Si deseas personalizar tus reportes incluyendo más cosas en el template (como registros de otros modelos, por ejemplo), puedes definir este modelo, sobrescribir la función `render_html` y pasar objetos en el diccionario `docargs`:

```python
from openerp import api, models

class ParticularReport(models.AbstractModel):
    _name = 'report.module.report_name'
    
    @api.multi
    def render_html(self, data=None):
        report_obj = self.env['report']
        report = report_obj._get_report_from_name('module.report_name')
        docargs = {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': self,
        }
        return report_obj.render('module.report_name', docargs)
```

---

## Los Reportes son Páginas Web

Los reportes se generan dinámicamente por el módulo de reporte y pueden accederse directamente mediante URL:

### Ejemplos de URLs

**HTML:**
```
http://<server-address>/report/html/sale.report_saleorder/38
```

**PDF:**
```
http://<server-address>/report/pdf/sale.report_saleorder/38
```

---

## Conceptos Clave para Este Proyecto

### 1. **Relación entre `report_name` y `template id`**

- El `report_name` en `ir.actions.report` debe coincidir con el `t-name` del template
- Ejemplo: Si `report_name = 'account.report_invoice_document_nakel_2024'`, el template debe tener `<t t-name="account.report_invoice_document_nakel_2024">`

### 2. **Estructura del Template**

```xml
<t t-name="account.report_invoice_document_nakel_2024">
    <t t-call="web.html_container">
        <t t-foreach="docs" t-as="o">
            <t t-call="web.external_layout">
                <div class="page">
                    <!-- Contenido del reporte -->
                </div>
            </t>
        </t>
    </t>
</t>
```

### 3. **Variables Disponibles**

- `docs`: Los registros del modelo (`account.move`, `stock.picking`, `sale.order`, etc.)
- `o`: Cada registro individual en el loop `t-foreach`
- `user`: Usuario actual
- `res_company`: Compañía actual

### 4. **Acceso a Campos**

- **Campos simples**: `<span t-field="o.name"/>`
- **Campos con opciones**: `<span t-field="o.date" t-options="{'widget': 'date'}"/>`
- **Valores calculados**: `<span t-esc="'%.2f' % (o.amount_total or 0)"/>`

### 5. **Campos Opcionales (Lección Aprendida)**

⚠️ **PROBLEMA**: Si intentas acceder a un campo que no existe (ej: `o.qr_code_url`), Odoo lanzará un `AttributeError`.

✅ **SOLUCIÓN**: No uses `t-if="o.campo_opcional"` directamente. En su lugar:
- Elimina la referencia al campo opcional, O
- Muestra un placeholder por defecto, O
- Usa un custom report que verifique la existencia del campo antes de pasarlo al template

### 6. **Herencia de Templates**

Para heredar un template existente:

```xml
<template id="my_template_inherit" inherit_id="account.report_invoice_document">
    <xpath expr="//div[@class='page']" position="inside">
        <!-- Tu contenido adicional -->
    </xpath>
</template>
```

**Prioridad**: Los templates con mayor `priority` tienen precedencia.

---

## Referencias

- **Documentación oficial**: https://odoo-master.readthedocs.io/en/master/reference/reports.html
- **Versión**: Odoo Master
- **Fecha de consulta**: 2025-12-28

---

**Última actualización**: 2025-12-28  
**Mantenido por**: Equipo Nakel / Corolla (AI Assistant)

