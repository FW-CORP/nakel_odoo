# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/).

---

## [18.0.1.18.5] - 2026-04-22

### Cambiado

- **Columna PLU (productos consolidados):** se muestra **imagen Code128** generada con `_generate_barcode_image` (valor `product_plu`, típicamente EAN en `barcode`) para escaneo con picker; **no** se añade código de barras en el pie de página (el pie sigue solo con texto Wave + paginación).

---

## [18.0.1.18.4] - 2026-04-22

### Cambiado

- **PLU en PDF (productos consolidados):** el valor mostrado pasa a **`product.barcode`** (EAN / código escaneable). En `master_dev`, la referencia interna (`default_code`, p. ej. `472.00`) **no coincide** con el EAN; Nakel usa `default_code` como código interno. Si no hay `barcode`, se usa **`default_code`** como respaldo. Clave nueva en el dict del reporte: `product_plu` (además se mantiene `product_code` = ref. interna).

---

## [18.0.1.18.3] - 2026-04-22

### Cambiado

- **Productos consolidados (PDF):** la columna que mostraba los nombres de picking en **Trasladar** pasa a **PLU** (tipografía **16 pt en negrita**). En **18.0.1.18.3** se usaba por error `default_code`; corregido en **18.0.1.18.4** a `barcode` con fallback.

---

## [18.0.1.18.2] - 2026-04-22

### Añadido

- **PDF del lote:** en el pie de cada hoja se muestra la **referencia de la wave** (`batch.name`, p. ej. `WAVE/00077`) junto a **Página n/m**, para identificar el lote si se mezclan impresiones.

---

## [18.0.1.18.1] - 2026-04-01

### Corregido

- **PDF del lote (ola / wave):** wkhtmltopdf/WebKit suele **ignorar** `page-break-inside: avoid` en filas (`tr`) de una tabla grande. Las secciones **Traslados en el Lote** y **Productos consolidados** pasan a usar **una tabla HTML por fila de datos** con `page-break-inside: avoid` en esa tabla, de modo que la fila (texto + código de barras) salta entera a la página siguiente si no cabe.
- **Secciones por ruta:** se quitó `page-break-inside: avoid` del contenedor que envolvía cabecera + tabla completa (con muchas filas forzaba saltos raros); la barra gris de ruta usa `page-break-after: avoid` para reducir cabeceras huérfanas.

---

## [18.0.1.18.0] - 2026-03-30

### Corregido

- **Persistía el error SQL con `factor_inv`:** incluso con `search(..., order='id')` algunas instalaciones EE siguen pasando por rutas que intentan ordenar por campos no almacenados. `_uom_largest_bulto_in_category` ahora obtiene IDs con **`SELECT id FROM uom_uom WHERE category_id = %s`** y **`browse`** + filtro en Python (sin `search` del ORM para ese caso).

---

## [18.0.1.17.0] - 2026-03-30

### Corregido

- **Mismo error `factor_inv` en SQL:** aun sin `order=` explícito, `uom.uom.search()` aplica el **`_order` del modelo** (en algunas ediciones puede apuntar a campos no almacenados). La búsqueda por categoría usa ahora **`order='id'`** y el criterio “mayor bulto” sigue resolviéndose en Python con `filtered` + `max`.

---

## [18.0.1.16.0] - 2026-03-30

### Corregido

- **Odoo 18 / EE:** `uom.uom.factor_inv` no es campo almacenado; `search(..., order='factor_inv desc')` y dominios sobre `factor_inv` pueden lanzar `ValueError: Cannot convert ... to SQL`. Se busca por categoría y se filtra/ordena en Python (`_uom_largest_bulto_in_category`).

---

## [18.0.1.15.0] - 2026-03-30

### Corregido

- **TOTAL solo mostraba unidades:** el QWeb usaba un respaldo `cantidad + UdM` cuando no veía `total_display` en el dict (p. ej. evaluación de `in line` o deploy desalineado). La columna vuelve a usar **`batch._format_total_display_for_line(line)`**, que aplica toda la lógica de bultos/embalaje (incl. variante en Odoo 18) sin depender de esa clave.

### Eliminado

- `_consolidated_line_total_text` (redundante).

---

## [18.0.1.14.0] - 2026-03-30

### Corregido

- **AttributeError: `_consolidated_line_total_text`:** el QWeb del servidor puede actualizarse antes que el `.py` (o al revés). La columna TOTAL vuelve a calcularse solo con expresión QWeb + claves estándar del dict; el método en Python se mantiene por si se usa desde código pero **ya no es obligatorio** para imprimir.

---

## [18.0.1.13.0] - 2026-03-30

### Corregido

- **KeyError: `total_display`** al imprimir PDF: el QWeb usaba `line['total_display']` pero alguna fila llegaba sin esa clave (p. ej. personalización / herencia de vista). El texto TOTAL pasa por `batch._consolidated_line_total_text(line)`, que recalcula si hace falta.

---

## [18.0.1.12.0] - 2026-03-30

### Corregido

- **Embalajes con plantillas multi-variante (Odoo 18):** `product.template.packaging_ids` viene **vacío** si hay más de una variante; los embalajes viven en **`product.product.packaging_ids`**. La lógica ahora prioriza la variante del movimiento y recién después la plantilla (si aplica).
- **Columna TOTAL siempre en `-`:** el QWeb del reporte usaba `line.get('total_display')`, poco fiable en el motor de plantillas; se reemplazó por **`line['total_display']`**.
- **Respaldo:** si con cantidad &gt; 0 el texto calculado fuera `-`, se fuerza mostrar cantidad + UdM.

---

## [18.0.1.11.0] - 2026-03-30

### Corregido

- **Columna TOTAL en `-`**: si el producto no tenía inferible `units_per_bulto` (sin embalaje/UdM bulto en ficha), ahora se muestra al menos **`{cantidad} {UdM}`** en lugar de `-`.
- **Embalaje en la línea**: se usa `product_packaging_id` de `stock.move` / `stock.move.line` cuando viene informado (prioridad alta).
- **Embalajes en plantilla**: se elige el de **mayor `qty`** (antes solo el primero de la lista, a veces un pack chico sin cantidad útil).

---

## [18.0.1.10.0] - 2026-03-30

### Cambiado

- **Columna BULTO → TOTAL**: el texto operativo ya no usa fracciones de bulto (ej. `0.17 Bulto x12`). Muestra **bultos enteros + unidades sueltas** y el tamaño de bulto entre paréntesis, p. ej. `1 bulto + 10 Unidades (x20)` o `0 bultos + 2 Unidades (x12)`.
- Si la línea va en UdM bulto y no se puede inferir unidades por bulto desde embalaje/UdM, se mantiene desglose **bultos enteros + fracción en la misma UdM** (sin pasar a “0.xx bulto” opaco).

---

## [18.0.1.9.0] - 2025-03-19

### Corregido

- **Salto de página**: Evita encabezados huérfanos al final de página. Cada sección de ruta (cabecera + tabla) se mantiene junta; si no cabe, toda la sección pasa a la siguiente página.

---

## [18.0.1.8.0] - 2025-03-19

### Añadido

- **Logo y nombre de empresa** en la primera hoja del reporte (encima de "Resumen: WAVE/xxx").

### Cambiado

- **Columna Producto**: El código interno se muestra una sola vez (antes aparecía duplicado).
- **Columna Código de barras**: Renombrada a "Codigo Prod." y reducido su ancho (12%) para dar más espacio a BULTO (18%).

---

## [18.0.1.7.0] - 2025-03

### Añadido

- **Columna BULTO**: Muestra cantidad en bultos (ej. "1.5 Bulto x40") para que el recolector sepa cuántas cajas tomar. Usa `uom_po_id`, `packaging_ids` o UdM de bulto en la categoría del producto.

### Corregido

- `KeyError: 'bulto_name'` mediante `setdefault` en el modelo y `line.get()` en el template.
- Fallback a `move_ids` cuando `move_line_ids` está vacío (pickings sin "Comprobar disponibilidad").

---

## [18.0.1.2.0] - 2025-03

### Corregido

- Secuencia en tabla de traslados (1, 2, 3... en lugar de 0, 1, 2...).
- Fallback a `move_ids` para generar "Productos Consolidados" cuando no hay operaciones detalladas.

---

## [18.0.1.1.0] - 2025-03

### Añadido

- Códigos de barras embebidos como imágenes base64 para correcta renderización en PDF.

### Cambiado

- Dependencia: `python-barcode[images]` para generación de códigos de barras.

---

## [18.0.1.0.0] - 2025-03

### Añadido

- Reporte consolidado de lotes de transferencias (stock.picking.batch).
- Agrupación por producto, lote, paquete y ubicaciones.
- Compatibilidad con waves, lotes y picking multi-ubicación.

---

[18.0.1.9.0]: https://github.com/FW-CORP/nakel_picking/compare/v18.0.1.8.0...v18.0.1.9.0
[18.0.1.8.0]: https://github.com/FW-CORP/nakel_picking/compare/v18.0.1.7.0...v18.0.1.8.0
[18.0.1.7.0]: https://github.com/FW-CORP/nakel_picking/compare/v18.0.1.2.0...v18.0.1.7.0
[18.0.1.2.0]: https://github.com/FW-CORP/nakel_picking/compare/v18.0.1.1.0...v18.0.1.2.0
[18.0.1.1.0]: https://github.com/FW-CORP/nakel_picking/compare/v18.0.1.0.0...v18.0.1.1.0
[18.0.1.0.0]: https://github.com/FW-CORP/nakel_picking/releases/tag/v18.0.1.0.0
