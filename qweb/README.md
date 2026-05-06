# Templates QWeb - Facturas, Remitos y Notas de Crédito

Este directorio contiene templates QWeb, scripts y documentación para la gestión de reportes fiscales en Odoo, específicamente adaptados para cumplir con los requisitos de AFIP/ARBA/ARCA en Argentina.

---

## 📁 Estructura del Directorio

```
nakel/qweb/
├── README.md                          # Este archivo
├── documentacion/                     # Documentación técnica
│   ├── QWEB_REPORTS_ODOO_OFICIAL.md  # 📚 Documentación oficial de Odoo QWeb Reports
│   ├── ANALISIS_TEMPLATES_QWEB_AFIP_ARBA.md
│   ├── MEJORES_PRACTICAS_XMLRPC_TEMPLATES.md  # ⭐ Mejores prácticas XML-RPC
│   ├── COMPARACION_TEMPLATE_REMITO.md
│   └── COMO_PROBAR_TEMPLATE_REMITO.md
├── templates/                         # Templates QWeb finales / canónicos
│   ├── account.report_invoice_document_nakel_2024_FACTURA_B_MEJORADO.xml
│   ├── account.report_invoice_document_nakel_2024_NOTA_CREDITO_MEJORADO.xml
│   ├── stock.report_delivery_document_nakel_2024_MEJORADO.xml
│   └── sale.report_saleorder_pro_forma_NAKEL_MEJORADO_V2.xml
├── backups/                           # Backups antes de aplicar cambios (rollback)
├── scripts/                           # Scripts canónicos
│   ├── nakel_qweb_sync_lib.py        # ⭐ Registro canónico (archivo → key QWeb) + XML-RPC compartido
│   ├── backup_templates_master18.py  # Backup de templates antes de aplicar
│   ├── instalar_templates_todos_master18.py
│   ├── aplicar_templates_master_dev_desde_master18.py
│   ├── analizar_reportes_facturas_en_uso.py  # Diagnóstico XML-RPC de reportes en uso
│   ├── analizar_templates_qweb_afip_arba.py
│   └── extraer_y_analizar_templates_qweb.py
└── trash/                             # Histórico / experimental / generado
    ├── templates/
    ├── scripts/
    ├── docs/
    ├── data/
    └── legacy_repo/
```

---

## 🎯 Objetivo

Analizar, verificar y mantener los templates QWeb de:
- **Facturas** (Factura A, B, C, etc.)
- **Remitos** (Documentos de transporte)
- **Notas de Crédito**
- **Notas de Débito**

Para garantizar el cumplimiento con:
- **AFIP** (Administración Federal de Ingresos Públicos)
- **ARBA** (Agencia de Recaudación de la Provincia de Buenos Aires)
- **ARCA** (Agencia de Recaudación y Control Aduanero)

---

## ⚠️ Estado Actual

### Ajuste aplicado en `master_18` - 2026-03-18

- El template activo de factura es `account.report_invoice_document_nakel_2024`.
- Se normalizó el nombre descargado del PDF a `Factura NAKEL - <numero de factura>`.
- La factura fue migrada a `web.basic_layout` para evitar el header/footer automático de Odoo y alinear el PDF con la vista web/portal.
- El reporte usa el `paperformat` propio `A4 Nakel Factura Ajustado` (`format` A4, **`orientation` Portrait**, márgenes en mm) para reducir blanco superior y evitar PDF **apaisado** al imprimir en A4 vertical. El script `qweb/scripts/aplicar_templates_master_dev_desde_master18.py` sincroniza ese paperformat; en instancias ya creadas, corregir manualmente el registro si quedó en Landscape.
- En esta base, los campos AFIP/ARCA reales detectados en `account.move` para CAE son:
  - `l10n_ar_afip_auth_code`
  - `l10n_ar_afip_auth_code_due`
- El bloque visual de factura fue refinado para:
  - alinear `IVA Responsable Inscripto`,
  - reducir el placeholder del QR,
  - corregir el render de líneas de producto con `display_type = 'product'`,
  - y mostrar CAE/paginado en el pie cuando el dato exista.
- En cotizaciones/pedidos (`sale.report_saleorder_document_nakel_2024`) el paginado también se mueve al **pie** (wkhtmltopdf `div.footer`) para evitar superposición con el contenido y se imprime en **negro**.
- Se limpió el directorio `nakel/qweb` y se movió a `trash/` todo lo duplicado, histórico, extraído o experimental para evitar confusión antes de aplicar en `master_dev`.

### Actualización (abril 2026): impresión por lote + PDF Quote / Cotización/orden

- **Facturas por lote (PDF “continuo”)**:
  - **Síntoma**: al imprimir varias facturas juntas, wkhtmltopdf “pegaba” el final de una con el comienzo de la siguiente (sin corte por documento).
  - **Causa probable**: el template de factura Nakel llamaba `web.basic_layout` sin `web.html_container` (en algunos casos `.page` no fuerza el salto entre documentos).
  - **Fix aplicado en template**: `account.report_invoice_document_nakel_2024` pasó a usar el patrón estándar:
    - `web.html_container` → `t-foreach="docs"` → `web.basic_layout` → `<div class="page">...`

- **Factura: Direcciones “fiscal” vs “envío”**:
  - **Mejora**: se etiquetaron explícitamente:
    - **Dirección fiscal**: `partner_invoice_id` (fallback `partner_id`)
    - **Dirección de envío**: `partner_shipping_id` solo si existe y es distinta de la fiscal
  - **Objetivo**: evitar duplicar la misma dirección con el mismo criterio y dar claridad operativa.

- **Cotización en PDF (PDF Quote) en `master_dev`**:
  - La acción `sale.action_report_saleorder` (menú “Cotización en PDF” / *PDF Quote*, id típico `424`) se apuntó a:
    - `report_name = sale.report_saleorder_nakel_2024`
    - `report_file = sale.report_saleorder_nakel_2024`
  - **Nota**: si el navegador cachea assets/acciones, hacer recarga dura (Ctrl+F5 / Shift+Reload) para evitar que siga llamando al reporte viejo.

- **Cotización/orden (módulo `sale_pdf_quote_builder`) en `master_dev`**:
  - En algunas bases existe el reporte `Quotation / Order` (xmlid `sale_pdf_quote_builder.action_report_saleorder_raw`, id típico `661`) que imprime con `sale.report_saleorder_raw`.
  - Para unificar el diseño Nakel, se debe apuntar también a:
    - `report_name = sale.report_saleorder_nakel_2024`
    - `report_file = sale.report_saleorder_nakel_2024`

### Estado del Directorio

1. **Canónico**:
   - `templates/` contiene solo los XML finales vigentes.
   - `scripts/nakel_qweb_sync_lib.py` define **`TEMPLATES_CANONICOS`** (path relativo a `qweb/` → `key` de `ir.ui.view`, modelo, prioridad). Cualquier script de despliegue debe alinearse con esa lista.
   - `scripts/` contiene los scripts operativos que llaman a la librería.
2. **Archivado**:
   - `trash/templates/` contiene variantes legacy, numeradas o de referencia.
   - `trash/scripts/` contiene scripts one-off, de corrección puntual, reversión o diagnóstico histórico.
   - `trash/data/` contiene backups y reportes generados.
   - `trash/legacy_repo/` contiene la copia histórica `QWeb-Modelos-templates`.

### Próximos Pasos

1. ✅ `master_18` estabilizado y ordenado.
2. ⏳ Aplicar templates probados a `master_dev`.
3. ⏳ Validar PDFs en `master_dev` con documentos reales.
4. ⏳ Ajustar solo si aparece una diferencia específica entre bases.

---

## 🔧 Scripts Disponibles

### `extraer_y_analizar_templates_qweb.py`

Extrae templates QWeb desde Odoo y los guarda localmente para análisis.

**Uso:**
```bash
cd /media/klap/raid5/cursor_files/nakel/qweb/scripts
python3 extraer_y_analizar_templates_qweb.py
```

**Qué hace:**
- Obtiene todos los reportes de facturas y remitos de Odoo
- Busca templates asociados
- Extrae el contenido XML de los templates
- Guarda templates en `templates/`
- Genera reporte JSON en `reportes/`

### `analizar_templates_qweb_afip_arba.py`

Analiza templates QWeb y verifica cumplimiento con requisitos AFIP/ARBA/ARCA.

**Uso:**
```bash
cd /media/klap/raid5/cursor_files/nakel/qweb/scripts
python3 analizar_templates_qweb_afip_arba.py
```

**Qué hace:**
- Busca templates de facturas y remitos
- Analiza qué campos AFIP están presentes
- Verifica cumplimiento porcentual
- Genera reporte de análisis

---

## 📊 Requisitos AFIP/ARBA/ARCA

### Facturas

#### Campos Obligatorios
- ✅ CUIT emisor y receptor
- ✅ Condición fiscal
- ✅ Fecha y número de factura
- ✅ Detalle de productos con precios y IVA
- ✅ Totales
- ✅ CAE/CAI
- ✅ **QR Code** (obligatorio desde 2024)
- ✅ Leyenda "Consumidor Final" (Factura B)
- ✅ IIBB
- ✅ Inicio de actividades
- ✅ Información de percepciones (si aplica)

#### Requisitos 2024
- ✅ QR Code con información fiscal (RG AFIP 4294/2024)
- ✅ Información de percepciones
- ✅ Datos de transporte (si aplica)
- ✅ Leyendas específicas según tipo

### Remitos

#### Campos Obligatorios
- ✅ Datos del emisor y destinatario
- ✅ Número y fecha
- ✅ Detalle de mercadería
- ✅ **QR Code** (obligatorio desde 2024, RG AFIP 4294/2024)
- ✅ Espacio para firma y conformidad
- ✅ Leyenda legal RG AFIP 4294/2024
- ✅ Información de transporte (si aplica)

---

## 📚 Documentación

### Documentos Principales

1. **ANALISIS_TEMPLATES_QWEB_AFIP_ARBA.md**
   - Análisis completo de templates actuales
   - Requisitos AFIP/ARBA/ARCA detallados
   - Plan de acción
   - Referencias normativas

2. **INFORME_EJECUTIVO_MODIFICACIONES_FACTURAS_MASTER18.md**
   - Resumen ejecutivo del trabajo realizado sobre facturas en `master_18`
   - Decisiones técnicas adoptadas
   - Estado final alcanzado
   - Base de preparación para `master_dev`

### Referencias Externas

- **RG AFIP 4294/2024**: Requisitos para remitos y facturas electrónicas
- **RG AFIP 5309/2023**: Código QR obligatorio
- Script de instalación: `/media/klap/raid5/cursor_files/modulos/contabilidad/scripts/instalar_templates_remitos_facturas.py`

---

## 🔍 Campos Odoo Argentina (l10n_ar)

Los templates deben usar los siguientes campos específicos de Argentina:

### Campos de Factura (`account.move`)
- `l10n_ar_afip_auth_code`: CAE / código de autorización electrónico
- `l10n_ar_afip_auth_code_due`: Vencimiento del CAE
- `l10n_ar_afip_qr_code`: texto/URL del QR fiscal AFIP (para imagen en PDF)
- `l10n_ar_afip_responsibility_type_id`: Condición fiscal
- `l10n_ar_perception_ids`: Percepciones aplicadas

### Campos de Empresa (`res.company`)
- `vat`: CUIT
- `l10n_ar_gross_income_number`: Número de IIBB
- `l10n_ar_afip_start_date`: Inicio de actividades
- `l10n_ar_afip_responsibility_type_id`: Condición fiscal

### Campos de Remito (`stock.picking`)
- `qr_code_url`: URL del QR Code (si está disponible)

---

## 📝 Notas Importantes

1. **QR Code**: Desde 2024 es **obligatorio** en todos los comprobantes fiscales
2. **Odoo 18 – imagen QR en PDF**: el endpoint es `/report/barcode/` con query **`barcode_type=QR`** (no usar `type=QR`; provoca error 500 y el QR no sale en el PDF). El valor suele ser una URL AFIP: codificarlo en QWeb con **`quote_plus(...)`** al armar `value=`. Ver detalle en `documentacion/INFORME_EJECUTIVO_MODIFICACIONES_FACTURAS_MASTER18.md` (sección abril 2026).
3. **Almacenamiento**: Comprobantes deben guardarse digitalmente por al menos 10 años
4. **Validación**: Probar templates con datos reales antes de producción
5. **Actualizaciones**: Revisar normativas AFIP/ARBA regularmente

---

## 📄 Templates Disponibles

### Template de Referencia

- **`stock.report_delivery_document_dxr_REFERENCIA.xml`**
  - Template funcional de remito argentino usado como base
  - ✅ Incluye datos básicos (destinatario, pedido, mercadería, firma)
  - ❌ **NO incluye QR Code** (requisito obligatorio 2024)
  - ❌ Falta información fiscal completa en encabezado
  - ⚠️ **NO cumple completamente** con RG AFIP 4294/2024

### Template Mejorado (Recomendado)

- **`stock.report_delivery_document_nakel_2024_MEJORADO.xml`**
  - Versión mejorada del template de referencia
  - ✅ Incluye **QR Code obligatorio** (RG AFIP 4294/2024)
  - ✅ Encabezado fiscal completo (CUIT, IIBB, condición fiscal)
  - ✅ Leyendas legales actualizadas
  - ✅ Mejor formato y organización visual
  - ✅ **CUMPLE** con todos los requisitos AFIP/ARBA/ARCA

### Comparación

Ver documentación detallada en: `documentacion/COMPARACION_TEMPLATE_REMITO.md`

## ⚙️ Enfoque Técnico: XML-RPC Directo

Este proyecto utiliza **instalación directa vía XML-RPC** (sin módulos Odoo) para mayor flexibilidad y rapidez.

### ✅ Ventajas

- ✅ **Rápido**: Cambios inmediatos sin reiniciar Odoo
- ✅ **Flexible**: Ideal para desarrollo y testing
- ✅ **Sin dependencias**: No requiere configurar addons path

### ⚠️ Mejoras Implementadas

1. **Manejo Robusto de PDFs**:
   - Script `generar_proforma_ejemplo_master18.py` actualizado
   - Maneja correctamente `xmlrpc.client.Binary` desde `render_qweb_pdf`
   - Evita PDFs corruptos o vacíos

2. **Versionado y Trazabilidad**:
   - Templates versionados en Git
   - Documentación de cambios
   - Backups antes de actualizaciones

### 📚 Documentación

**Documentación oficial de Odoo**: [`documentacion/QWEB_REPORTS_ODOO_OFICIAL.md`](documentacion/QWEB_REPORTS_ODOO_OFICIAL.md)
- Referencia completa de la documentación oficial de Odoo sobre QWeb Reports
- Estructura de templates, variables disponibles, herencia, etc.

**Mejores prácticas XML-RPC**: [`documentacion/MEJORES_PRACTICAS_XMLRPC_TEMPLATES.md`](documentacion/MEJORES_PRACTICAS_XMLRPC_TEMPLATES.md)

Esta guía incluye:
- ✅ Manejo correcto de `render_qweb_pdf` con `xmlrpc.client.Binary`
- ✅ Checklist pre-producción
- ✅ Mejores prácticas para mantenimiento
- ✅ Limitaciones del enfoque y mitigaciones
- ✅ Cuándo considerar crear módulo Odoo (si es necesario)

## 🚀 Próximos Pasos

1. ✅ **Templates Mejorados Instalados**
   - Remito Nakel 2024
   - Factura B Nakel 2024
   - Nota de Crédito Nakel 2024
   - Proforma Nakel (mejorado)
   - **Cotización Nakel 2024** (`sale.report_saleorder_nakel_2024` + documento): mismo criterio visual que factura (`web.basic_layout`), sin bloque AFIP/QR. El script de aplicación enlaza **`sale.action_report_saleorder`** (menú *Cotización en PDF* / PDF Quote) a ese template; use `--sin-apuntar-cotizacion-pdf` para solo subir vistas y no tocar la acción.

2. ✅ **Scripts de Instalación**
   - `instalar_templates_todos_master18.py` - Instala todos los templates en master_18
   - `aplicar_templates_master_dev_desde_master18.py` - Aplica templates probados de master_18 a master_dev
   - `actualizar_proforma_mejorado_master18.py` - Actualiza template de proforma
   - `actualizar_facturas_amount_by_group_master18.py` - Actualiza templates de facturas y notas de crédito
   - `actualizar_remito_bultos_master18.py` - Actualiza template de remito
   - `generar_proforma_ejemplo_master18.py` - Genera PDFs de prueba

3. ✅ **Aplicación a Múltiples Bases de Datos**
   - Los templates probados en `master_18` pueden aplicarse a `master_dev` usando el script de aplicación
   - Ver sección "Procedimiento para Aplicar Templates" más abajo

4. ✅ **Limpieza y Archivo**
   - Todo lo no canónico fue movido a `trash/`
   - La raíz operativa quedó reducida a templates, scripts y documentación vigentes

5. ⏳ **Pruebas Continuas**
   - Verificar PDFs generados después de cambios
   - Validar cumplimiento AFIP/ARBA/ARCA
   - Probar en múltiples documentos

---

## 📋 Procedimiento para Aplicar Templates a Otra Base de Datos

### Aplicar Templates de master_18 a master_dev

Si tienes templates probados y funcionando en `master_18` y quieres aplicarlos a `master_dev`:

```bash
cd /media/klap/raid5/cursor_files/nakel/qweb/scripts
# Backup previo (recomendado; rollback desde nakel/qweb/backups/)
python3 backup_templates_master18.py --instancia master_dev
python3 aplicar_templates_master_dev_desde_master18.py
```

**Misma carpeta `templates/`, otra base (p. ej. master_18):**

```bash
python3 aplicar_templates_master_dev_desde_master18.py --instancia master18
```

Opciones útiles:

- `--solo-facturas` — solo vistas `account.move` (factura + nota de crédito).
- `--sin-acciones-report` — solo sube `ir.ui.view`, no toca `report.paperformat` ni `ir.actions.report`.

El script aplica automáticamente todos los templates listados en `nakel_qweb_sync_lib.TEMPLATES_CANONICOS`:
- ✅ Factura B (con impuestos detallados usando tax_totals)
- ✅ Nota de Crédito (con impuestos detallados)
- ✅ Remito (con Cant. Bultos en lugar de Lote)
- ✅ Factura Proforma (diseño profesional con branding NAKEL)

**Nota**: Las credenciales salen de `config_nakel.py` (`ODOO_CONFIG_MASTER_DEV` o `ODOO_CONFIG_MASTER18` según `--instancia`). El enlace de **reportes de factura** ya no usa IDs fijos: se buscan `ir.actions.report` con modelo `account.move` y tipo `qweb-pdf`, excluyendo reportes de proveedor; las notas de crédito se detectan por nombre/`report_name` (heurística). Si en tu base no aparece ninguna acción de NC, el script lo indica: puede bastar un solo reporte que cubra ambos o hay que crear/ajustar la acción en Odoo.

### Actualizar un Template Específico en master_18

Si necesitas actualizar un template específico en `master_18`:

```bash
# Proforma
python3 actualizar_proforma_mejorado_master18.py

# Facturas y Notas de Crédito (impuestos)
python3 actualizar_facturas_amount_by_group_master18.py

# Remito (bultos)
python3 actualizar_remito_bultos_master18.py
```

---

**Última actualización**: 2026-04-01  
**Base de datos**: master_18, master_dev  
**Estado**: ✅ Templates en `templates/` + despliegue unificado vía `nakel_qweb_sync_lib` y `aplicar_templates_master_dev_desde_master18.py`

