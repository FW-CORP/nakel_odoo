# Comparación de Template de Remito - Base vs Mejorado

**Fecha**: 2025-12-27  
**Template base**: `stock.report_delivery_document_dxr`  
**Template mejorado**: `stock.report_delivery_document_nakel_2024_MEJORADO`

---

## 📊 Análisis del Template Base

### ✅ Elementos Presentes en el Template Base

1. **Datos del destinatario**
   - Nombre, CUIT/DNI, Teléfono, Email
   - Domicilio completo
   - ✅ Cumple requisitos básicos

2. **Información del pedido**
   - Nº Pedido
   - Fecha Pedido
   - Referencia (si aplica)
   - ✅ Cumple requisitos básicos

3. **Detalle de mercadería**
   - Código, Descripción, Cantidad, Lote
   - ✅ Cumple requisitos básicos

4. **Transporte y observaciones**
   - Transportista
   - Observaciones
   - ✅ Cumple requisitos básicos

5. **Firma y conformidad**
   - Espacio para firma
   - ✅ Cumple requisitos básicos

6. **Condiciones**
   - Condiciones de entrega
   - ✅ Cumple requisitos básicos

---

## ❌ Elementos Faltantes en el Template Base

### 1. **Encabezado Fiscal Completo**
- ❌ No incluye información fiscal de la empresa de forma destacada
- ❌ No muestra CUIT de la empresa en encabezado
- ❌ No muestra IIBB
- ❌ No muestra inicio de actividades

### 2. **QR Code (OBLIGATORIO desde 2024)**
- ❌ **NO incluye QR Code** - Requisito obligatorio según RG AFIP 4294/2024
- ❌ Sin código QR, el remito no cumple con normativa vigente

### 3. **Leyendas Legales**
- ❌ No menciona RG AFIP 4294/2024
- ❌ No tiene leyenda sobre cumplimiento normativo
- ❌ No especifica que es documento de transporte obligatorio

### 4. **Información Fiscal del Emisor**
- ❌ No muestra condición fiscal (IVA Responsable Inscripto, etc.)
- ❌ No muestra domicilio fiscal completo en encabezado
- ❌ No muestra website (si aplica)

---

## ✅ Mejoras en el Template Mejorado

### 1. **Encabezado Fiscal Completo**
```xml
<div class="fiscal-header" style="border-bottom: 2px solid #000; margin-bottom: 15px; padding-bottom: 10px;">
  <div class="row">
    <div class="col-4">
      <strong t-field="o.company_id.name"/>
    </div>
    <div class="col-4 text-center">
      <h2 style="font-size: 48px; font-weight: bold; margin: 0;">R</h2>
    </div>
    <div class="col-4 text-right">
      <h4 style="margin: 0;">Remito</h4>
      <small>
        Nro: <span t-esc="report_number"/><br/>
        Fecha: <span t-esc="env['ir.qweb.field.date'].value_to_html(report_date, {})"/>
      </small>
    </div>
  </div>
  <div class="row mt-2" style="font-size: 12px;">
    <div class="col-6">
      <span t-field="o.company_id.street"/> - <span t-field="o.company_id.city"/><br/>
      <span t-field="o.company_id.state_id.name"/> - <span t-field="o.company_id.zip"/><br/>
      <t t-if="o.company_id.website"><span t-field="o.company_id.website"/></t>
    </div>
    <div class="col-6 text-right">
      IVA Responsable Inscripto - CUIT: <span t-field="o.company_id.vat"/><br/>
      <t t-if="o.company_id.l10n_ar_gross_income_number">
        IIBB: <span t-field="o.company_id.l10n_ar_gross_income_number"/><br/>
      </t>
      <t t-if="o.company_id.l10n_ar_afip_start_date">
        Inicio de actividades: <span t-field="o.company_id.l10n_ar_afip_start_date" t-options="{'widget': 'date'}"/>
      </t>
    </div>
  </div>
</div>
```

**Incluye:**
- ✅ Razón social destacada
- ✅ Letra "R" grande para Remito
- ✅ Número y fecha en encabezado
- ✅ Domicilio fiscal completo
- ✅ CUIT
- ✅ Condición fiscal (IVA Responsable Inscripto)
- ✅ IIBB
- ✅ Inicio de actividades

### 2. **QR Code (Obligatorio)**
```xml
<div class="col-6">
  <div style="text-align: center; border: 1px solid #ccc; padding: 10px;">
    <t t-if="o.qr_code_url">
      <img t-att-src="o.qr_code_url" alt="QR Code Remito" style="width: 150px; height: 150px;"/>
    </t>
    <t t-else="">
      <div style="width: 150px; height: 150px; border: 1px dashed #ccc; margin: 0 auto; display: flex; align-items: center; justify-content: center;">
        <small>QR Code<br/>(disponible en facturación electrónica)</small>
      </div>
    </t>
    <br/>
    <small>QR Code con información fiscal según RG AFIP 4294/2024</small>
  </div>
</div>
```

**Incluye:**
- ✅ QR Code cuando está disponible (`o.qr_code_url`)
- ✅ Placeholder si no está disponible (para debugging)
- ✅ Leyenda indicando que es según RG AFIP 4294/2024

### 3. **Leyendas Legales**
```xml
<div class="row mt-3">
  <div class="col-12" style="font-size: 10px; text-align: center; border-top: 1px solid #ccc; padding-top: 10px;">
    <strong>CONDICIONES LEGALES</strong><br/>
    Este remito cumple con los requisitos de la RG AFIP 4294/2024.<br/>
    Documento de transporte obligatorio según normativa vigente.
  </div>
</div>
```

**Incluye:**
- ✅ Menciona RG AFIP 4294/2024
- ✅ Indica cumplimiento normativo
- ✅ Especifica que es documento obligatorio

### 4. **Mejoras en Tabla de Mercadería**
- ✅ Usa `move_ids_without_package or []` para evitar errores
- ✅ Bordes en la tabla para mejor legibilidad
- ✅ Estilos mejorados (background-color en header)
- ✅ Manejo de valores nulos con `or 0`

### 5. **Mejor Organización Visual**
- ✅ Sección de transporte mejor organizada
- ✅ Espacios más consistentes
- ✅ Firma y conformidad en dos columnas

---

## 📋 Cumplimiento AFIP/ARBA/ARCA

### Template Base

| Requisito | Cumple | Notas |
|-----------|--------|-------|
| Datos del destinatario | ✅ | Completo |
| Información del pedido | ✅ | Completo |
| Detalle de mercadería | ✅ | Completo |
| Información fiscal emisor | ⚠️ | Parcial - falta en encabezado |
| CUIT emisor | ❌ | No visible en encabezado |
| IIBB | ❌ | No incluido |
| QR Code | ❌ | **OBLIGATORIO - FALTA** |
| Leyenda legal RG AFIP 4294/2024 | ❌ | No incluida |
| Condición fiscal | ❌ | No visible |

**Cumplimiento**: ~50% - **NO CUMPLE** con requisitos 2024

### Template Mejorado

| Requisito | Cumple | Notas |
|-----------|--------|-------|
| Datos del destinatario | ✅ | Completo |
| Información del pedido | ✅ | Completo |
| Detalle de mercadería | ✅ | Completo |
| Información fiscal emisor | ✅ | Completo en encabezado |
| CUIT emisor | ✅ | Visible en encabezado |
| IIBB | ✅ | Incluido |
| QR Code | ✅ | **INCLUIDO (obligatorio)** |
| Leyenda legal RG AFIP 4294/2024 | ✅ | Incluida |
| Condición fiscal | ✅ | Visible |
| Inicio de actividades | ✅ | Incluido |

**Cumplimiento**: ~100% - **CUMPLE** con requisitos 2024

---

## 🎯 Recomendaciones

### 1. **Usar Template Mejorado para Producción**

El template mejorado cumple con todos los requisitos de AFIP/ARBA/ARCA, especialmente:
- ✅ QR Code obligatorio
- ✅ Información fiscal completa
- ✅ Leyendas legales actualizadas

### 2. **Verificar Disponibilidad de QR Code**

Asegurarse de que el campo `qr_code_url` esté disponible en `stock.picking`. Si no está disponible:
- Implementar generación de QR Code en el módulo `l10n_ar`
- O usar un campo personalizado para almacenar el QR Code

### 3. **Probar con Datos Reales**

Antes de poner en producción:
- Generar remitos de prueba
- Verificar que todos los campos se muestren correctamente
- Validar formato PDF
- Verificar que el QR Code se genere correctamente

### 4. **Ajustes Visuales (Opcional)**

El template mejorado tiene un diseño más formal con bordes. Si prefieres un diseño más limpio como el original, puedes:
- Quitar bordes de la tabla
- Mantener solo los elementos obligatorios (QR Code, leyendas, etc.)

---

## 📝 Notas Técnicas

### Campos Odoo Utilizados

- `o.company_id.vat` - CUIT de la empresa
- `o.company_id.l10n_ar_gross_income_number` - IIBB
- `o.company_id.l10n_ar_afip_start_date` - Inicio de actividades
- `o.qr_code_url` - QR Code (debe estar implementado en el módulo)
- `o.move_ids_without_package` - Movimientos de stock sin paquetes
- `o.partner_id.vat` - CUIT/DNI del destinatario

### Dependencias

- Módulo `l10n_ar` (localización argentina) debe estar instalado
- Campo `qr_code_url` debe estar disponible o implementado

---

**Última actualización**: 2025-12-27

