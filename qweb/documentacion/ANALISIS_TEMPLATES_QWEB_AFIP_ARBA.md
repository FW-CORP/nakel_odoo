# Análisis de Templates QWeb - Cumplimiento AFIP/ARBA/ARCA

**Fecha de análisis**: 2025-12-27  
**Base de datos**: master_dev  
**Objetivo**: Verificar cumplimiento de templates QWeb con requisitos AFIP/ARBA/ARCA para Argentina

---

## 📋 Resumen Ejecutivo

### Estado Actual

- **Reportes de Facturas**: 4 reportes configurados
  - ✅ **"Factura B Nakel 2024"** (account.report_invoice_document_nakel_2024) - ⚠️ **SIN TEMPLATE ASOCIADO**
  - ✅ "PDF" (account.report_invoice_with_payments) - Template genérico Odoo
  - ✅ "PDF without Payment" (account.report_invoice) - Template genérico Odoo
  - ✅ "Original Bills" (account.report_original_vendor_bill) - Template genérico Odoo

- **Reportes de Remitos**: 6 reportes configurados
  - ✅ **"Remito Nakel 2024"** (stock.report_delivery_document_nakel_2024) - ⚠️ **SIN TEMPLATE ASOCIADO**
  - ✅ "Delivery Slip" (stock.report_deliveryslip) - Template genérico Odoo
  - ✅ "Picking Operations" (stock.report_picking) - Template genérico Odoo
  - ✅ Otros templates genéricos de Odoo

### ⚠️ PROBLEMA IDENTIFICADO

Los reportes personalizados de Nakel **no tienen templates QWeb asociados**, lo que significa que:
1. Los templates nunca se crearon en master_dev
2. Los templates fueron eliminados
3. Los reportes están configurados pero no funcionan correctamente

---

## 📊 Requisitos AFIP/ARBA/ARCA para Facturas

### Campos Obligatorios (Resolución General AFIP)

#### Información del Emisor
- ✅ CUIT del emisor (`company_id.vat`)
- ✅ Razón social (`company_id.name`)
- ✅ Domicilio fiscal (`company_id.street`, `city`, `state_id`, `zip`)
- ✅ Condición fiscal (`company_id.l10n_ar_afip_responsibility_type_id`)
- ✅ IIBB (`company_id.l10n_ar_gross_income_number`)
- ✅ Inicio de actividades (`company_id.l10n_ar_afip_start_date`)

#### Información del Receptor
- ✅ CUIT/DNI del receptor (`partner_id.vat`)
- ✅ Razón social (`partner_id.name`)
- ✅ Condición fiscal (`partner_id.l10n_ar_afip_responsibility_type_id`)

#### Información del Comprobante
- ✅ Número de factura (`o.name`)
- ✅ Fecha de emisión (`o.invoice_date`)
- ✅ Tipo de comprobante (Factura A, B, C, etc.)

#### Detalle de Productos/Servicios
- ✅ Código del producto (`product_id.default_code`)
- ✅ Descripción (`product_id.name`)
- ✅ Cantidad (`quantity`)
- ✅ Precio unitario (`price_unit`)
- ✅ Subtotal (`price_subtotal`)
- ✅ Alicuota de IVA (`tax_ids`)
- ✅ Total del comprobante (`amount_total`)

#### Información Fiscal
- ✅ CAE/CAI (`l10n_ar_cae`)
- ✅ Vencimiento CAE (`l10n_ar_cae_due_date`)
- ✅ Código de barras (CBU/CUIT + datos fiscales)
- ✅ **QR Code con información fiscal** (Obligatorio desde 2024, RG AFIP 4294/2024)
- ✅ Leyenda "Consumidor Final" (para Factura B)

#### Requisitos Adicionales 2024
- ✅ Información de percepciones (`l10n_ar_perception_ids`)
- ✅ Datos de transporte (si aplica)
- ✅ Leyendas específicas según tipo de operación

---

## 📦 Requisitos AFIP para Remitos (RG AFIP 4294/2024)

### Campos Obligatorios

#### Información del Emisor
- ✅ Datos de la empresa (nombre, CUIT, dirección)
- ✅ Condición fiscal
- ✅ IIBB

#### Información del Destinatario
- ✅ Nombre/razón social
- ✅ CUIT/DNI
- ✅ Domicilio

#### Información del Remito
- ✅ Número de remito (`o.name`)
- ✅ Fecha (`o.date_done`)
- ✅ Número de pedido (`o.origin`)

#### Detalle de Mercadería
- ✅ Código del producto (`product_id.default_code`)
- ✅ Descripción (`product_id.name`)
- ✅ Cantidad (`product_uom_qty`)
- ✅ Lotes (si aplica) (`lot_ids`)

#### Información Fiscal y Legal
- ✅ **QR Code con información fiscal** (Obligatorio desde 2024)
- ✅ Espacio para firma y conformidad
- ✅ Leyenda legal cumpliendo RG AFIP 4294/2024
- ✅ Datos de transporte (si aplica)

---

## 🔍 Análisis de Templates Actuales

### Templates de Odoo Genéricos

Los templates genéricos de Odoo (`account.report_invoice`, `stock.report_deliveryslip`, etc.) **NO cumplen** con los requisitos argentinos porque:

1. ❌ No incluyen campos específicos de Argentina (`l10n_ar_*`)
2. ❌ No tienen QR Code
3. ❌ No tienen leyendas legales en español
4. ❌ No incluyen información de percepciones
5. ❌ No tienen formato adecuado para AFIP/ARBA

### Templates Personalizados de Nakel (FALTANTES)

Los reportes personalizados **"Factura B Nakel 2024"** y **"Remito Nakel 2024"** están configurados pero **no tienen templates asociados**.

Según el script `instalar_templates_remitos_facturas.py` encontrado en el proyecto, estos templates deberían incluir:

**Factura B Nakel 2024:**
- ✅ Encabezado fiscal con información completa
- ✅ Datos del cliente (Consumidor Final)
- ✅ Detalle de productos
- ✅ Totales con IVA
- ✅ QR Code
- ✅ Información AFIP (CAE)
- ✅ Leyenda "Consumidor Final"

**Remito Nakel 2024:**
- ✅ Encabezado fiscal
- ✅ Datos del destinatario
- ✅ Información del pedido
- ✅ Detalle de mercadería
- ✅ QR Code
- ✅ Información de transporte
- ✅ Espacio para firma y conformidad
- ✅ Leyendas legales (RG AFIP 4294/2024)

---

## ✅ Plan de Acción

### 1. Crear/Recuperar Templates Faltantes

#### Opción A: Crear templates desde el script existente

El proyecto tiene un script `modulos/contabilidad/scripts/instalar_templates_remitos_facturas.py` que contiene los templates completos. Este script puede ejecutarse para crear los templates faltantes.

#### Opción B: Crear templates manualmente

Basarse en el contenido del script mencionado y crear los templates directamente en Odoo.

### 2. Verificar Cumplimiento AFIP/ARBA/ARCA

Una vez creados los templates, verificar que incluyan:

#### Para Facturas:
- [ ] CUIT emisor y receptor
- [ ] Condición fiscal
- [ ] Fecha y número
- [ ] Detalle de productos con precios y IVA
- [ ] Totales
- [ ] CAE/CAI
- [ ] QR Code (obligatorio 2024)
- [ ] Leyenda "Consumidor Final"
- [ ] IIBB
- [ ] Inicio de actividades
- [ ] Información de percepciones (si aplica)

#### Para Remitos:
- [ ] Datos del emisor y destinatario
- [ ] Número y fecha
- [ ] Detalle de mercadería
- [ ] QR Code (obligatorio 2024)
- [ ] Espacio para firma
- [ ] Leyenda legal RG AFIP 4294/2024

### 3. Probar Templates

- Generar facturas de prueba
- Generar remitos de prueba
- Verificar que todos los campos se muestren correctamente
- Validar formato PDF
- Verificar QR Code

### 4. Documentación

- Documentar estructura de templates
- Crear guía de uso
- Documentar requisitos específicos de Argentina

---

## 📁 Estructura de Archivos

```
/media/klap/raid5/cursor_files/nakel/qweb/
├── documentacion/
│   └── ANALISIS_TEMPLATES_QWEB_AFIP_ARBA.md (este archivo)
├── templates/
│   ├── account.report_invoice_777.xml (template genérico)
│   ├── stock.report_deliveryslip_2374.xml (template genérico)
│   └── [templates personalizados faltantes]
├── scripts/
│   ├── analizar_templates_qweb_afip_arba.py
│   └── extraer_y_analizar_templates_qweb.py
└── reportes/
    └── extraccion_templates_YYYYMMDD_HHMMSS.json
```

---

## 🔗 Referencias

### Normativas AFIP
- **RG AFIP 4294/2024**: Requisitos para remitos y facturas electrónicas
- **RG AFIP 5309/2023**: Código QR obligatorio en comprobantes fiscales

### Scripts de Referencia
- `/media/klap/raid5/cursor_files/modulos/contabilidad/scripts/instalar_templates_remitos_facturas.py`
- `/media/klap/raid5/cursor_files/modulos/contabilidad/documentacion/RESUMEN_FACTURA_B_ANALISIS.md`

### Campos Odoo Argentina (l10n_ar)
- `l10n_ar_cae`: CAE (Código de Autorización Electrónico)
- `l10n_ar_cae_due_date`: Vencimiento del CAE
- `l10n_ar_afip_responsibility_type_id`: Condición fiscal (Responsable Inscripto, etc.)
- `l10n_ar_gross_income_number`: Número de IIBB
- `l10n_ar_afip_start_date`: Inicio de actividades
- `l10n_ar_perception_ids`: Percepciones aplicadas

---

## 📝 Notas Importantes

1. **QR Code**: Desde 2024, el código QR es **obligatorio** en todos los comprobantes fiscales (facturas y remitos).

2. **Almacenamiento**: Los comprobantes deben almacenarse en formato digital por al menos 10 años según normativa vigente.

3. **Validación**: Los templates deben validarse con datos reales antes de ponerlos en producción.

4. **Actualizaciones**: Las normativas fiscales cambian frecuentemente. Revisar actualizaciones de AFIP/ARBA regularmente.

---

**Última actualización**: 2025-12-27  
**Próximos pasos**: Crear templates faltantes y verificar cumplimiento

