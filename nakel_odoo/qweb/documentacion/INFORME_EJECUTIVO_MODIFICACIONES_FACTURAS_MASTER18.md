# Informe Ejecutivo - Modificaciones de Facturas Nakel en `master_18`

## Resumen Ejecutivo

Se realizó una intervención integral sobre los reportes de factura de Nakel en Odoo `master_18` con el objetivo de corregir errores funcionales, normalizar la descarga del PDF y mejorar la calidad visual del comprobante para impresión real y cumplimiento fiscal argentino.

El trabajo permitió estabilizar el template activo de facturación, corregir la identificación del tipo de comprobante, incorporar datos fiscales reales de AFIP/ARCA, ordenar el layout de impresión y dejar una estructura documental/técnica limpia para replicar el resultado en `master_dev`.

## Objetivos del Trabajo

- Corregir inconsistencias entre Factura A y Factura B.
- Mejorar el diseño visual del PDF para uso operativo e impresión.
- Normalizar el nombre del archivo descargado.
- Incorporar datos fiscales obligatorios o relevantes para Argentina.
- Reducir el riesgo técnico antes de replicar el cambio en `master_dev`.

## Problemas Detectados

### 1. Inconsistencia funcional del comprobante

- Facturas tipo A podían mostrarse o descargarse con referencias visuales de Factura B.
- El flujo de impresión y el flujo de vista web no se comportaban igual.

### 2. Nombre de archivo incorrecto o confuso

- El PDF se descargaba con nombres del tipo `Factura B Nakel - FA-A ...`, aun cuando el comprobante era Factura A.
- Persistían diferencias entre idioma base y `es_AR`, generando resultados inconsistentes.

### 3. Problemas de layout e impresión

- Exceso de espacio en blanco superior.
- Encabezado con alineaciones irregulares.
- Elementos fiscales mal balanceados visualmente.
- QR demasiado invasivo.
- Tabla y pie con presentación poco profesional.

### 4. Diferencia entre HTML web y PDF

- La vista web del comprobante se veía correcta y prolija.
- El PDF generado por el backend salía con otra composición visual.

### 5. Riesgo de confusión en el repositorio local

- Existían templates históricos, wrappers, pruebas, scripts one-off y un repositorio duplicado dentro de `nakel/qweb/`.
- Esto aumentaba el riesgo de aplicar en `master_dev` un archivo incorrecto.

## Decisiones Técnicas Tomadas

### Template activo de factura

Se consolidó como template vigente:

- `account.report_invoice_document_nakel_2024`

Archivo fuente canónico:

- `nakel/qweb/templates/account.report_invoice_document_nakel_2024_FACTURA_B_MEJORADO.xml`

### Layout

- Se migró el reporte a `web.basic_layout`.
- Se evitó depender de `web.external_layout` para no heredar header/footer automáticos de Odoo que deformaban la impresión.

### Paperformat

Se creó y asignó un `paperformat` específico:

- `A4 Nakel Factura Ajustado`

Objetivo:

- reducir el blanco superior,
- mejorar centrado,
- y obtener una impresión más precisa.

### Nombre del archivo PDF

Se normalizó `print_report_name` para que el archivo descargado salga como:

- `Factura NAKEL - <numero de factura>.pdf`

Además, se corrigieron variantes en idioma:

- base,
- `en_US`,
- `es_AR`.

### Campos fiscales reales

Se validó en `master_18` que los campos operativos correctos para CAE/AFIP son:

- `l10n_ar_afip_auth_code`
- `l10n_ar_afip_auth_code_due`

Y no los campos históricos/alternativos que inicialmente se habían supuesto.

## Mejoras Aplicadas al Comprobante

### Encabezado

- Se corrigió la jerarquía visual del encabezado.
- Se integró logo, razón social, domicilio y bloque fiscal.
- Se amplió y centró mejor la letra del comprobante.
- Se realineó `RESPONSABLE INSCRIPTO` con el eje visual de la letra fiscal.

### Bloque fiscal

Se incorporaron o corrigieron:

- número de factura,
- fecha,
- CUIT,
- IVA Responsable Inscripto,
- IIBB,
- inicio de actividades.

### Datos del cliente

- Se mejoró la alineación del bloque de domicilio y datos del receptor.

### Detalle de productos

- Se corrigió el render de líneas `account.move.line` con `display_type = 'product'`.
- Se recuperó correctamente la visualización de productos en la tabla.
- **Líneas de Nota y Sección (2025)**: Se corrigió el template QWeb para que las líneas agregadas con "Agregar nota" (`display_type = 'line_note'`) y "Agregar sección" (`display_type = 'line_section'`) se impriman en el PDF. Antes solo se mostraban en pantalla. Templates afectados: `account.report_invoice_document_nakel_2024_FACTURA_B_MEJORADO.xml` y `account.report_invoice_document_nakel_2024_NOTA_CREDITO_MEJORADO.xml`.

**Verificación vía XML-RPC (2025-03)**: El script `analizar_reportes_facturas_en_uso.py` confirmó que en master_18 y master_dev todos los reportes de factura (IDs 223, 224, 225, 1002) usan el template `account.report_invoice_document_nakel_2024`. Las facturas de proveedor usan el mismo template.

**Despliegue (2026-03-24)**: Fix de notas/secciones aplicado en master_18 (con backup previo). Mismo conjunto aplicado a master_dev con backup en `nakel/qweb/backups/*_master_dev_*.xml` y script `aplicar_templates_master_dev_desde_master18.py`.

### Totales e impuestos

- Se mantuvo el uso de `tax_totals`.
- Se filtraron percepciones de IIBB en Factura B cuando corresponde.
- Se dejó un bloque de totales más legible para operación e impresión.

### QR y pie legal

- Se redujo el peso visual del QR.
- Se dejó el pie con mejor legibilidad.
- Se agregó o estabilizó la visualización de:
  - CAE,
  - vencimiento del CAE,
  - número de página.

## Resultado Alcanzado

### Estado funcional

- El PDF de factura en `master_18` quedó estable.
- El comprobante descarga con nombre normalizado.
- Los productos ya se imprimen correctamente.
- Los datos fiscales relevantes ya aparecen.

### Estado visual

- El comprobante quedó con una presentación profesional, clara y apta para impresión.
- La composición general quedó alineada con lo esperado por operación.
- La factura quedó visualmente mucho más cercana a la calidad de la vista web correcta.

## Limpieza y Preparación para `master_dev`

Se realizó una limpieza del directorio `nakel/qweb` para reducir ruido y riesgo operativo.

### Estructura canónica conservada

- `templates/`
- `scripts/`
- `documentacion/`
- `README.md`

### Archivado en `trash/`

Se movieron a `trash/`:

- templates legacy o extraídos,
- scripts de diagnóstico/corrección puntual,
- backups y reportes generados,
- documentación histórica de reversión,
- repositorio duplicado `QWeb-Modelos-templates`.

## Riesgos o Consideraciones Pendientes

- `master_dev` debe validarse por separado porque puede diferir en datos, vistas o configuración.
- Aunque el diseño ya quedó estabilizado en `master_18`, podrían aparecer diferencias menores de layout al aplicar en otra base.
- Conviene probar al menos:
  - Factura A,
  - Factura B,
  - una factura con múltiples líneas,
  - una factura con percepciones,
  - y descarga real de PDF.

## Próximo Paso Recomendado

Aplicar los templates canónicos ya estabilizados de `master_18` a `master_dev` y ejecutar una validación comparativa visual y funcional.

Script previsto para ese paso:

- `nakel/qweb/scripts/aplicar_templates_master_dev_desde_master18.py`

---

## Actualización (abril 2026): QR AFIP en PDF con Odoo 18

### Síntoma

Al imprimir factura en `master_dev`, el PDF salía **sin imagen de QR** (o con error de red en wkhtmltopdf). En el log del servidor aparecía:

- `TypeError: ReportController.report_barcode() missing 1 required positional argument: 'barcode_type'`
- Petición fallida: `GET /report/barcode/?type=QR&value=...` → **HTTP 500**

### Causa

En **Odoo 18**, el controlador `report_barcode` (`addons/web/controllers/report.py`) ya no usa el parámetro de query `type`, sino **`barcode_type`**. La URL antigua `?type=QR&value=...` hace coincidir la ruta `/report/barcode` pero **no** rellena el argumento `barcode_type`, lo que dispara el `TypeError`.

Además, el valor de `l10n_ar_afip_qr_code` es una **URL AFIP** con `?`, `&`, etc.; si no se codifica, el query string puede partirse mal. En QWeb está disponible **`quote_plus`** (werkzeug) para codificar el valor.

### Corrección en el repositorio

En el template canónico de factura (`FACTURA_B_MEJORADO`), la imagen del QR debe generarse así (resumen):

- Query: `barcode_type=QR` (no `type=QR`).
- Valor: `quote_plus(o.l10n_ar_afip_qr_code)` concatenado al resto de la URL.

Archivos actualizados en el vault/repo:

- `templates/account.report_invoice_document_nakel_2024_FACTURA_B_MEJORADO.xml`
- `templatesv2/account.report_invoice_document_nakel_2024_FACTURA_B_MEJORADO.xml`

### ¿Está aplicado en `master_dev`?

**Solo en la base Odoo `master_dev` si** se volvió a **publicar la vista** desde este repo (por ejemplo con `nakel_qweb_sync_lib` / script de aplicación de templates contra esa instancia). El cambio en **archivos del vault** no actualiza solo el servidor: hay que **ejecutar el sync** y comprobar en Odoo que la vista `ir.ui.view` del reporte coincide con el XML del repo.

Tras desplegar, validar: imprimir una factura con CAE/QR y confirmar en log que `/report/barcode/?barcode_type=QR&value=...` responde **200**.

---

## Estado Final

Trabajo completado en `master_18` con resultado satisfactorio para:

- corrección funcional,
- corrección de nombre de archivo,
- mejora de layout,
- incorporación de datos fiscales,
- y preparación ordenada para migración a `master_dev`.
