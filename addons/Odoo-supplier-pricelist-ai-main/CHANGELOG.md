# CHANGELOG — Proyecto Nakel

Cronología técnica del proyecto. Cada sprint resolvió un bloqueo concreto.

---

## Sprint 3.5 — Interpretación comercial de precios (2026-05-08)

### Problema
Aún con matches correctos, el `cost_delta_pct` en Odoo mostraba números absurdos como `+132.220%`, `+78.890%`, `+34.440%`. Caso emblemático:

- **BLANCO X 12 FLOWPACK** del proveedor Cachafaz: $14.190 (un estuche de 12 alfajores)
- **ALF.CACHAFAZ BLANCO X60G (12)** en Odoo: `standard_price` = $1.123 (por **1 alfajor individual**)
- Comparación cruda: 14190 vs 1123 → +1163%? El precio del proveedor no subió 1163%.

La realidad: 14190/12 = $1.182 por alfajor, comparado con $1.123 → +5.2% (variación normal).

**El problema no era de matching — era de unidades.** Odoo guarda costo por unidad atómica vendible, los proveedores cobran por pack. Ambos válidos pero hay que normalizar antes de comparar.

### Solución
Hacer que **Gemini interprete la realidad comercial** además de matchear:

1. Pasar al LLM el `standard_price` de cada candidato Odoo como **ancla numérica**
2. Pedirle que calcule `unit_count = round(precio_proveedor / costo_odoo)` por aritmética
3. Devolver `unit_count`, `unit_price`, `price_interpretation` en la respuesta

Esto convierte la convención inconsistente de Odoo (algunos productos con costo por unidad, otros por estuche) en algo determinable matemáticamente.

### Cambios técnicos
**AI Service:**
- `matcher/llm_smart_matcher.py`:
  - Prompt reescrito con tabla de 7 ejemplos resueltos mostrando la división `precio/costo`
  - Schema JSON ampliado: `unit_count`, `unit_price`, `price_interpretation`
  - `_summarize_candidate()` ahora incluye el `standard_price` en el formato `VARIANTE | PACK | costo $X | nombre`
- `matcher/product_matcher.py`:
  - Pasa `unit_count`, `unit_price`, `price_interpretation` al resultado
  - Default `unit_count=1` para preservar compatibilidad
- `main.py`:
  - `MatchResultItem` con campos `unit_count`, `unit_price`, `price_interpretation`

**Módulo Odoo:**
- `models/supplier_pricelist_import_line.py`:
  - Nuevos campos: `unit_count`, `unit_price_with_vat`, `unit_price_without_vat`, `price_interpretation`, `has_comparable_cost`
  - `_compute_current_cost` ahora usa `unit_price_without_vat` (no `price_without_vat` directo)
  - Umbrales nuevos: ≥30 danger, ≥10 warning, ≤-10 success, resto muted
  - `cost_delta_display` muestra "—" cuando no hay costo comparable
- `models/supplier_pricelist_import.py`:
  - `_create_lines_from_matches` recibe los nuevos campos
- Vistas (`supplier_pricelist_import_views.xml`, `confirm_wizard_views.xml`, etc.) actualizadas para usar `cost_delta_display` con decoraciones por color

### Smoke test (10/10)
| Caso | Match | unit | unit_price | Estado |
|---|---|---|---|---|
| BLANCO X 12 FLOWPACK | BLANCO X60G (12) | 12 | $1.182 | ✅ |
| BLANCO X 6 FLOWPACK | BLANCO ESTUCHE X6U | 1 | $7.281 | ✅ |
| MAICENA X 12 | MAICENA X76G | 12 | $1.182 | ✅ |
| CONITO X 12 | CONITOS X12U | 1 | $12.255 | ✅ |
| AVENA & MIEL | ORGANICA AVENA&MIEL | 1 | $1.322 | ✅ |
| BOCADITOS MARROC | MARROC X54U | 1 | $28.085 | ✅ |
| ... y 4 más | | | | ✅ |

### Resultado import #23 (Cachafaz, 41 ítems)
- 13 auto (todos correctos)
- 6 review (calibración honesta)
- 22 no_match (mayoría correctos, 3 falsos no_match marginales)

---

## Sprint 3 — Smart match con LLM (2026-05-07/08)

### Problema
Después del Sprint 2, Cachafaz seguía sin auto-matches útiles. Embeddings en subset chico (22 productos) daban 95% confianza spurious a casi cualquier producto. La cross-confirmación bloqueaba los falsos positivos pero terminaba en 0/12/29 (nada en auto).

### Solución
Reemplazar la combinación "fuzzy + embedding + cross-confirmación" por un LLM que razone holísticamente:

1. Pre-filtrar top 15 candidatos del subset partner (fuzzy + embedding)
2. Mandar al LLM con prompt rico:
   - Item del proveedor (nombre, presentación, sección PDF, precio)
   - Candidatos como `VARIANTE | PACK | nombre completo`
   - Errores comunes a evitar (ARROZ ≠ MAÍZ, BOLITAS ≠ TUTUCA, CHIZITOS ≠ PALITOS, etc.)
   - Sinónimos útiles (CHOCO ≡ NEGRO, CONITO ≡ CONITOS)
3. LLM devuelve match_id + confidence + reasoning en JSON estructurado

### Iteraciones del prompt
**v1 (rígido, 4 pasos)**: dio 9/10/22, pero con varios falsos positivos auto del catálogo general.

**v2 (sin fallback general)**: 0/12/29. No falsos positivos pero muchos no_match incorrectos.

**v3 (conversacional, "trust Gemini")**: 13/5/23, 12/13 auto correctos, 1 alucinación (CON LECHE → CONITOS). Mucho mejor.

**v4 (Sprint 3.5 con costo Odoo como ancla)**: 13/6/22, 13/13 auto correctos, 0 alucinaciones.

### Cambios técnicos
- `matcher/llm_smart_matcher.py` (nuevo):
  - Soporta backends Gemini (preferido) y Ollama (fallback)
  - `responseSchema` de Gemini para JSON estructurado garantizado
  - `maxOutputTokens=3000` para no truncar respuestas
  - Prompt con few-shot examples del dominio Nakel
- `matcher/product_matcher.py`:
  - Capa 3 ahora llama a `smart_match` en vez de embedding directo
  - Fallback a fuzzy review si LLM falla
- `.env`:
  - `GEMINI_API_KEY=AIzaSy...`
  - `GEMINI_MODEL=gemini-2.5-flash`

### Resultados medidos
| Iteración | Auto | Review | No match | Falsos auto |
|---|---|---|---|---|
| Sprint 2 (sin LLM) | 0 | 12 | 29 | 0 |
| Sprint 3 v1 (Gemini rígido) | 9 | 10 | 22 | 1+ |
| Sprint 3 v3 (Gemini libre) | 13 | 5 | 23 | 1 (CON LECHE) |
| Sprint 3 v4 (con costo) | 13 | 6 | 22 | 0 |

---

## Sprint 2 — Filtro por partner + cross-confirmación (2026-05-07)

### Problema
Embeddings genéricos (`nomic-embed-text`) producían matches absurdos al 95% confianza:
- BEEFEATER PINK → BUTTER CREAM
- BEEFEATER → Combustible
- THE GLENLIVET → BUDIN FANTOCHE
- MIXTO X 12 FLOWPACK → RAID ESPIRALES

El modelo no entiende dominio (alimentos vs limpieza vs bebidas).

### Solución (3 capas)

**1. Filtrar catálogo por proveedor**
- Función `_is_partner_product()` detecta productos vinculados al partner vía `is_known_supplier`, `supplier_product_code`, `supplier_product_name`, o `known_supplier_names`
- Si hay ≥5 productos en el subset, se usa **prioritariamente**
- Si nada matchea ahí, **NO se cae al catálogo general** (los embeddings genéricos siguen siendo basura)

**2. Cross-confirmación obligatoria**
- Para auto en subset partner: requerir fuzzy ≥ 0.55 **Y** embedding ≥ 0.85 **del mismo producto**
- El embedding solo no puede dar auto (en subsets chicos da scores inflados)

**3. Umbrales por contexto**
- General: `EMBED_AUTO=0.95`, `FUZZY_AUTO=0.85`
- Partner: `EMBED_AUTO=0.85`, `FUZZY_AUTO=0.75` (más permisivo porque subset es semánticamente homogéneo)
- Mínimo fuzzy del mismo producto del embedding: 0.45 (era 0.30)

### Cambios técnicos
- `matcher/product_matcher.py`:
  - Split del catálogo en `partner_catalog` vs general
  - Doble pasada: subset partner primero, luego (opcionalmente) general
  - Constantes `EMBED_AUTO_PARTNER`, `FUZZY_AUTO_PARTNER`, etc.

### Resultados
- Pernod #10: 100 auto (93 correctos por barcode), 21 review, 46 no_match → ~63% accuracy real
- Cachafaz: 0 falsos positivos auto pero también 0 auto reales (necesitaba LLM → Sprint 3)

---

## Sprint 1 — Extracción tabular sin LLM (2026-05-07)

### Problema
LLM extractor (qwen2.5:3b) extraía solo 29/158 productos del PDF de Pernod (18% recall). Confundía columnas de precio (tomaba "Precio Base" en vez de "Precio Final BOTELLA"). No extraía barcodes ni códigos de proveedor.

### Solución

**1. Parser tabular nativo con pdfplumber**
- Múltiples estrategias (`default`, `text/lines`, `lines/lines`, `text/text`) — toma la que captura más columnas
- Detección de headers por keywords (`articulo`, `producto`, `precio`, `codigo`, `ean`, `presentacion`)
- Mapeo de columnas a campos semánticos:
  - `barcode`, `barcode_box`, `supplier_code`, `name`, `presentation`, `category`
  - `price_final_bottle`, `price_distrib_unit`, `price_final`, `price_pack`, `price_unit`, `price_base_*`
- Detección de filas-categoría (Cachafaz: "CAJAS EXHIBIDORAS", "BOMBONES", etc.)
- Fallback de "primera columna sin clasificar = nombre" (caso Cachafaz "PATAGONIA II")

**2. Parser de líneas de texto con regex**
- Para PDFs como Pernod cuyas tablas se fragmentan en pdfplumber
- Regex captura `<categoría> <código> <nombre> <Bot|Est|Kit> ... <bc_caja> <bc_botella>`
- Repara números cortados (`$ 1 09.641,93` → `$ 109.641,93`)

**3. Detector heurístico de truncamiento**
- Si los nombres extraídos por tabular empiezan con dígito o minúscula → reemplazar por text-line parser

### Cambios técnicos
- `parsers/pdf_parser.py`:
  - `extract_structured_rows()` (nuevo)
  - `_classify_column()` (mapeo header → campo)
  - `_extract_rows_from_text_lines()` (regex Pernod-style)
  - `_parse_pack_size()`, `_extract_variant_word()` (helpers)
  - `_parse_price()` con detección de formato argentino vs US
  - `detect_vat_included()` lee notas al pie del PDF
- `main.py`:
  - Intenta extracción tabular antes del LLM
  - Si extrae ≥5 filas, **salta el LLM completo**
- `matcher/product_matcher.py`:
  - Capa 1.a nueva: match exacto por `supplier_code` del item (parser estructurado)

### Smoke test final (3 PDFs reales)
| PDF | Filas extraídas | Con barcode | Con código | Sin LLM |
|---|---|---|---|---|
| Pernod (DISTR Abril) | 167 | 167 (100%) | 167 (100%) | ✅ |
| Tunki Pop | 38 | 0 (no tiene) | 0 (no tiene) | ✅ |
| Cachafaz | 41 | 0 (no tiene) | 0 (no tiene) | ✅ |

---

## Pre-Sprint 1 — Diagnóstico inicial

### Problema observado en el primer import (#7) de Pernod
- Solo 29 de 158 productos extraídos por el LLM
- TODOS matcheaban via "embedding alta confianza" al 95-98% — pero a productos absurdos
- Ejemplos:
  - BEEFEATER PINK → BUTTER CREAM (95%)
  - GLENLIVET 18YO → BUDIN FANTOCHE MARMOLADO (97%)
  - CHIVAS BLENDING KIT → BUDIN FANTOCHE
  - WYBOROWA WATERMELON → BODEGA PRIVADA CHARDONNAY
- Matches realmente correctos: ~2/29 (~7%)
- **Tasa global: ~1.3%** (2 correctos sobre 158 productos del PDF)

### Causas raíz identificadas
1. **LLM extractor pierde contexto** en chunks de PDF — no extrae todo
2. **`nomic-embed-text` es genérico** — no sabe nada del dominio bebidas/snacks
3. **Embedding sobre catálogo completo** (~10000 productos) — falsos positivos garantizados
4. **Sin uso de barcodes** aunque están en el PDF

### Plan de remediación → Sprints 1, 2, 3.

---

## Estructura del proyecto al inicio (~2026-04-28)

- Módulo Odoo básico funcionando
- AI service en VM 226 con Ollama (qwen2.5:3b extract, nomic-embed-text)
- Endpoint `/api/match` recibiendo PDFs, extrayendo con LLM, matcheando con embeddings
- Sin filtro por partner, sin cross-confirmación, sin LLM disambiguador efectivo
- Resultado: catastrófico (~1% accuracy real)

---

## Lecciones aprendidas

1. **No confiar ciegamente en LLMs para extracción** cuando el dato es tabular. pdfplumber + regex es 10x más rápido y 100x más preciso para PDFs estructurados.

2. **Los embeddings genéricos no entienden dominio**. `nomic-embed-text` da 95% similarity entre productos completamente distintos si comparten palabras genéricas. Solo sirven como **pre-filtro** para reducir candidatos, nunca como matcher principal.

3. **El filtro por partner es no-negociable**. Productos no relacionados con el proveedor no deben aparecer como candidatos. Cualquier match contra el catálogo general es probablemente basura.

4. **Pasar contexto numérico al LLM lo cambia todo**. Decirle a Gemini "el costo Odoo es $1.123" + "el proveedor cobra $14.190" le permite calcular `unit_count=12` por aritmética simple. Sin esa ancla, depende de inferencia textual frágil.

5. **Los nombres de productos en Odoo son inconsistentes**. Algunos tienen formato al final, otros no. El "(12)" final aparece a veces. La única forma robusta de inferir cuál es la "unidad atómica de costo" es comparar contra el `standard_price`.

6. **Confidence calibrada honestamente > forzar matches**. Es mejor `no_match` con sugerencia que `auto al 95%` que el usuario tiene que detectar y corregir. Gemini con prompt bien diseñado calibra bien (75% review para sabor distinto, 95% para variante exacta).

7. **No todo lo que parece igual lo es**: BOLITAS vs TUTUCA vs CHIZITOS son productos distintos aunque sean snacks de la misma marca. Hay que enseñarle al LLM las distinciones del dominio explícitamente.
