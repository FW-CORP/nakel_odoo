# Factura NAKEL — Página 2 en blanco (solo pie / CAE)

## Síntoma

Con cierta cantidad de líneas de producto, el PDF genera una **hoja 2 casi vacía** donde solo aparece el pie (numeración **Hoja 2/2**, a veces **CAE** y leyendas AFIP), sin ítems ni totales.

## Template afectado

- **QWeb:** `account.report_invoice_document_nakel_2024`
- **Archivo:** `templates/account.report_invoice_document_nakel_2024_FACTURA_B_MEJORADO.xml`
- **Motor PDF:** wkhtmltopdf (vía `ir.actions.report` + `report.paperformat`)

## Causas identificadas (combinadas)

### 1. Bloque QR + totales indivisible (`page-break-inside: avoid`)

```css
.nakel-totals-qr-block {
  page-break-inside: avoid;
}
```

El bloque (QR ~90px + tabla de totales) **no puede partirse**. Si al final de la hoja 1 queda poco espacio (p. ej. 40–60 mm), wkhtmltopdf **mueve el bloque entero** a la hoja 2. La hoja 1 queda “llena” de ítems; la 2 arranca con QR/totales + pies legales.

### 2. Pie fiscal duplicado (cuerpo + banda `div.footer`)

- **`div.footer`** (wkhtml): solo `Hoja X/Y` — se repite en la **banda inferior** de cada hoja (reserva `margin_bottom` del paperformat, **20 mm**).
- **Cuerpo del documento** (líneas 311–350): bloques “INFORMACIÓN AFIP”, contacto, **CAE / Vto. CAE**.

Si los ítems + QR/totales ocupan casi toda la hoja 1, el **bloque AFIP + CAE** queda solo en hoja 2 con poco contenido → sensación de “hoja en blanco para el pie”.

### 3. Filas de ítems que no se parten

```css
table.nakel-lines-table tbody tr {
  page-break-inside: avoid;
}
```

Cada línea es un bloque indivisible. Con ~18–22 ítems por página A4, las **últimas filas** que no entran en el remanente de la hoja 1 pasan enteras a la hoja 2, reduciendo el espacio útil y empeorando el empuje del bloque de totales.

### 4. Paperformat `A4 Nakel Factura Ajustado`

- `margin_bottom: 20` mm reservados para header/footer de wkhtml.
- Esa zona se usa aunque el `div.footer` solo tenga una línea de numeración → **banda inferior vacía** visible en cada hoja.

### 5. (Menor) Clase `.page` de Odoo

En reportes por lote, `.page { page-break-after: always; }` fuerza salto entre documentos. En impresión unitaria a veces contribuye a una hoja extra; se mitiga con `page-break-after: avoid` en el documento Nakel.

## Propuesta de solución (aplicada en template)

| # | Cambio | Objetivo |
|---|--------|----------|
| 1 | Quitar `page-break-inside: avoid` del bloque QR+totales; evitar salto solo en la **fila de totales** (más chica) | Permitir que QR quede al pie de hoja 1 y totales empiecen ahí o en hoja 2 sin empujar todo el bloque |
| 2 | Permitir partir **filas de producto**; mantener `avoid` en sección/nota | Más líneas por hoja, menos “últimas filas” huérfanas |
| 3 | **CAE + numeración** en `div.footer` (compacto); quitar CAE duplicado del cuerpo | El pie fiscal va en la banda de wkhtml, no ocupa cuerpo de página 2 |
| 4 | Compactar leyendas AFIP del cuerpo (menos `margin-top`) | Menos altura del “cola” del documento |
| 5 | `page-break-after: avoid` en `.nakel-invoice-page` | Evitar hoja 3 vacía tras el comprobante |
| 6 | `margin_bottom` paperformat **14 mm** + pie AFIP compacto en `.nakel-cierre-factura` | Totales+QR+pie intentan ir juntos en la misma hoja |

### Paginación manual — **retirada** (mayo 2026, 2.ª iteración)

Dividir en varios `<div class="page">` con N líneas por bloque **empeoró** el PDF:

1. Cada `div.page` + `page-break-after` = **una hoja física** aunque el contenido ocupe poco.
2. Las filas con **Impuestos** (IVA + IIBB en varias líneas) son **altas**; wkhtml partía dentro del bloque y dejaba ~¼ de hoja usada + blanco.
3. Resultado: FA-A con **324 líneas** → **18 hojas** con patrón repetido en hoja 2, 3, …

**Solución vigente:** un solo flujo por factura:

- Encabezado Nakel **una vez**.
- Tabla única con `thead` repetido (`display: table-header-group`) en cada hoja impresa.
- `tbody tr` de producto con `page-break-inside: auto` (wkhtml reparte filas según altura real).
- QR + totales + pie fiscal **solo al final** del documento (`page-break-inside: avoid` en el bloque de cierre).
- Sin `class="page"` de Odoo en el cuerpo (evita min-height / salto forzado por bloque).

## Encabezado alineado (mayo 2026)

Reestructura del bloque superior en **3 columnas** (`display: table` para wkhtml):

| Col. izq. | Col. centro | Col. der. |
|-----------|-------------|-----------|
| Logo + Nakel SA + domicilio emisor | Letra A/B/C (solo recuadro) | Nro, fecha, CUIT emisor |
| Nombre / CUIT / contacto cliente | | Dirección de envío (si distinta) |
| Dirección fiscal (debajo del cliente) | | |

Evita filas Bootstrap con `col` vacías que desalineaban los bloques 1–5.

---

## Validación recomendada

Probar PDF con:

1. **5 líneas** (1 hoja, pie completo).
2. **18–20 líneas** (zona crítica donde aparecía hoja 2 en blanco).
3. **40+ líneas** (varias hojas; CAE y “Hoja X/Y” en la última / en cada hoja según diseño).

Comparar antes/después en `master_dev` tras actualizar la vista QWeb (`nakel_qweb_sync` o actualizar `ir.ui.view` desde el XML).

## Referencia

- Patrón pie compacto: `sale.report_saleorder_pro_forma_NAKEL_MEJORADO_V2.xml` (comentario: *evita que el pie empuje una página extra*).
- Remito: mismo `div.footer` + `nakel-totals-qr-block` — revisar si el mismo ajuste aplica.
