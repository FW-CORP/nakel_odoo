# Nakel AI Service

Microservicio FastAPI que procesa listas de precios de proveedores y las matchea con el catálogo Odoo de Nakel.

## Endpoint principal

```http
POST /api/match
Content-Type: application/json

{
  "file_content": "<base64 PDF/Excel/imagen>",
  "file_name": "lista.pdf",
  "partner_id": 5428,
  "partner_name": "ENSINCRO SRL",
  "catalog": [
    {
      "id": 5180,
      "name": "ALF.CACHAFAZ BLANCO X60G.-505- (12)",
      "standard_price": 1123.93,
      "categ_name": "ALFAJORES",
      "barcode": null,
      "supplier_product_code": null,
      "supplier_product_name": null,
      "known_supplier_names": [],
      "is_known_supplier": true
    }
  ],
  "auto_threshold": 88
}
```

Response:
```json
{
  "partner_id": 5428,
  "partner_name": "ENSINCRO SRL",
  "file_name": "lista.pdf",
  "total_extracted": 41,
  "vat_included": true,
  "matches": [
    {
      "supplier_name": "BLANCO X 12 FLOWPACK",
      "presentation": "6 Estuches x 12 u.",
      "price_with_vat": 14190.85,
      "vat_included": true,
      "product_tmpl_id": 5180,
      "product_name": "[2815.20] ALF.CACHAFAZ BLANCO X60G.-505- (12)",
      "confidence": 98,
      "match_status": "auto",
      "notes": "LLM (98%): CHOCO≡NEGRO, formato X60G(12) = un alfajor. Cachafaz cobra por estuche de 12.",
      "alternative_product_ids": [5181, 5184],
      "unit_count": 12,
      "unit_price": 1182.57,
      "price_interpretation": "El precio del estuche dividido por 12 alfajores da $1.182, similar al costo unitario Odoo de $1.123."
    }
  ],
  "warnings": []
}
```

## Estructura de archivos

```
ai_service/
├── main.py                          # FastAPI app, endpoint /api/match
├── requirements.txt
├── .env                             # GEMINI_API_KEY, OLLAMA_URL, etc.
│
├── parsers/
│   ├── pdf_parser.py                # Extracción tabular + fallback regex
│   ├── excel_parser.py              # openpyxl/csv → texto
│   └── image_parser.py              # Ollama vision → texto (raro)
│
└── matcher/
    ├── product_matcher.py           # Orquestador de capas de matching
    ├── llm_smart_matcher.py         # Smart match con Gemini API
    ├── embeddings.py                # nomic-embed-text + similitud coseno
    ├── llm_extractor.py             # Fallback LLM para extraer items (cuando parser tabular falla)
    └── llm_disambiguator.py         # LLM auxiliar para empates entre candidatos
```

## Flujo del endpoint

```
POST /api/match
    │
    ▼
[1] Parser de archivo
    ├─ PDF: extract_structured_rows()                ← intenta tabla con headers
    │   ├─ pdfplumber con múltiples estrategias      ← lines, text, lines_strict
    │   ├─ Detección de header por keywords          ← "articulo", "precio", "ean", "codigo"
    │   ├─ Mapeo de columnas a campos semánticos     ← name, barcode, supplier_code, price_*
    │   ├─ Detección de filas-categoría              ← cuando 1-2 celdas con texto, resto vacío
    │   ├─ Si filas truncadas → text-line regex      ← Pernod-style fallback
    │   └─ Si nada funciona → LLM extractor          ← último recurso
    │
    ├─ Excel: openpyxl                               ← items directos
    └─ Imagen: Ollama vision                         ← OCR (raro)
    │
    ▼
[2] Para cada ítem extraído
    ├─ Capa 0: barcode exacto                        ← lookup directo
    ├─ Capa 1: supplier_product_code exacto          ← lookup directo
    ├─ Capa 2: known_supplier_names                  ← memoria de matches confirmados
    ├─ Capa 2.5: fuzzy_partner ≥ 0.85                ← rapidfuzz token_sort_ratio
    └─ Capa 3: smart_match con Gemini                ← LLM razona sobre subset partner
        ├─ Pre-filtra top 15 candidatos (fuzzy + embedding)
        ├─ Pasa cada candidato como "VARIANTE | PACK | costo $X | nombre"
        ├─ Gemini elige + interpreta unit_count
        └─ Si Gemini falla → fallback Ollama qwen2.5:14b
    │
    ▼
[3] Resultado por ítem
    ├─ match_status: auto | review | no_match
    ├─ unit_count: cuántas unidades Odoo en el precio del proveedor
    ├─ unit_price: precio normalizado por unidad
    └─ price_interpretation: explicación humana del cálculo
```

## Capas de matching detalladas

### Capa 0: Barcode (EAN-13)
- Lookup directo en `barcode_index` (productos del catálogo con `barcode` no vacío)
- Normaliza barcodes con/sin ceros a la izquierda
- **Confianza 100%, status auto**

### Capa 1: Código de proveedor
- 1.a Si el item tiene `supplier_code` explícito (parser estructurado)
- 1.b Si el supplier_name contiene `[código]` entre corchetes
- 1.c Si el supplier_name completo coincide con un código del índice
- Lookup en `code_index` (productos con `supplier_product_code` para ese partner)
- **Confianza 100%, status auto**

### Capa 2: Nombre conocido
- Lookup exacto en `known_name_index` (productos con `known_supplier_names` o `supplier_product_name` que matchean)
- Match parcial: si supplier_name ⊂ known_name o viceversa (>4 chars)
- **Confianza 90-98%, status auto**

### Capa 2.5: Fuzzy matching
- `rapidfuzz.fuzz.token_sort_ratio` entre nombre limpio del item y catálogo del partner
- Threshold `FUZZY_AUTO_GENERAL = 0.85` (subset partner) o más estricto en general
- **Si ≥ 85%, auto**

### Capa 3: Smart match (LLM)

Pre-filtrado:
- Top 10 candidatos por fuzzy_partner
- Top 10 por embedding (Ollama nomic-embed-text)
- Combina y deduplica → top 15 al LLM

Llamada al LLM:
- Si `GEMINI_API_KEY` está set → Gemini 2.5 Flash
- Sino → Ollama qwen2.5:14b (fallback)

Cada candidato pasa al prompt como:
```
1. TUTUCA          | 12X80G    | $    5,573.65 | TUTUCA TUNKI POP 12X80G.-117-
2. BOLITAS         | 12X80G    | $    5,573.65 | BOLITAS CEREAL COLORES TUNKI 12X80G.
3. CHIZITOS        | 1KG       | $    3,879.49 | CHIZITOS SABOR QUESO TUNKI X1KG.
```

El **costo en pesos** ($X) es la **ancla numérica clave** que permite a Gemini calcular `unit_count = round(precio_proveedor / costo_odoo)` por aritmética simple.

Decisión:
- `confidence ≥ 90` → auto
- `60 ≤ confidence < 90` → review
- `confidence < 60` → no_match (con sugerencia)

## Configuración (.env)

```env
# AI service
HOST=0.0.0.0
PORT=8001
API_KEY=nakel-ai-2026

# Backend principal: Gemini API
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-2.5-flash      # alternativa: gemini-2.5-pro

# Backend fallback: Ollama local
OLLAMA_URL=http://localhost:11434
EXTRACT_MODEL=qwen2.5:7b-instruct
DISAMBIG_MODEL=qwen2.5:14b
EMBED_MODEL=nomic-embed-text
VISION_MODEL=llama3.2-vision

# Umbral global
AUTO_THRESHOLD_PCT=88
```

## Prompt engineering (Gemini)

El prompt en `matcher/llm_smart_matcher.py` incluye:

1. **Contexto del rol**: experto en distribuidoras argentinas, procesa lista de Nakel
2. **Tarea dual**: (A) match + (B) interpretación comercial de unit_count
3. **Convención Odoo**: formato al final del nombre (`X60G`, `12X80G`, `X1KG`, etc.)
4. **Errores comunes**: ARROZ ≠ MAÍZ, BOLITAS ≠ TUTUCA, CHOCO ≡ NEGRO, CHIZITOS DE MAÍZ ≠ CHIZITOS QUESO, etc.
5. **Tabla de 7 ejemplos resueltos** con la división `precio/costo` explícita
6. **Calibración de confianza**: 95-100 = exacto, 85-94 = duda menor, 70-84 = review, 0-49 = no_match

JSON schema (con responseSchema de Gemini):
```json
{
  "variante_item": "string",
  "match_id": "integer",
  "confidence": "integer 0-100",
  "reasoning": "string",
  "unit_count": "integer",
  "unit_price": "number",
  "price_interpretation": "string"
}
```

## Soporte de PDFs (parser tabular)

`parsers/pdf_parser.py` implementa:

### `extract_structured_rows(file_bytes)`
1. Itera múltiples estrategias de pdfplumber: default, text/lines, lines/lines, text/text
2. Para cada tabla: busca header row con `_is_header_row()` (≥2 keywords como "articulo", "precio", "ean")
3. Mapea cada columna a campo semántico vía `_classify_column()`:
   - `barcode` (EAN, código botella, código de barras)
   - `supplier_code` (N°, nro, código)
   - `name` (artículo, producto, descripción)
   - `presentation` (presentación, envase, tipo)
   - `price_final_bottle`, `price_final`, `price_distrib_unit`, `price_pack`, `price_unit`, `price_base`
   - `category` (subcategoría, rubro, familia)
4. Si la primera columna no se clasificó pero tiene texto → toma como nombre (caso Cachafaz "PATAGONIA II")
5. Detecta filas-categoría (1-2 celdas con texto, resto vacío) → asocia a las filas siguientes
6. Construye dict por fila con priority de precio: `final_bottle > distrib_unit > final > pack > final_box > distrib_box > unit > base_bottle > base`

### `_extract_rows_from_text_lines(file_bytes)`
Fallback para tablas fragmentadas (Pernod-style):
- Extrae texto plano del PDF
- Regex que captura: `<categoría> <código> <nombre> <Bot|Est|Kit> ... <bc_caja> <bc_botella>`
- Repara números cortados por pdfplumber (`$ 1 09.641` → `$ 109.641`)
- Toma el penúltimo `$` como precio (Precio Final BOTELLA en Pernod)

### `_parse_pack_size(text)` y `_extract_variant_word(text)`
- Pack: `12X80G`, `30X15G`, `X1KG`, `X6U`, etc. desde texto crudo o nombre Odoo
- Variante: TUTUCA, BOLITAS, CHIZITOS, MAICENA, BLANCO, NEGRO, CHIVAS, BEEFEATER, etc.

## Deploy a la VM

> Reemplazar `<VM_PASSWORD>`, `<HOSTKEY_SHA256>` y `<VM_AI_HOST>` con los valores reales que tenés en tu entorno local. **No commitear esos valores.**

```powershell
# Subir archivos modificados
& "C:\Program Files\PuTTY\pscp.exe" -batch -pw "<VM_PASSWORD>" `
  -hostkey "<HOSTKEY_SHA256>" `
  "C:\Claude\nakel\ai_service\matcher\llm_smart_matcher.py" `
  aiadmin-subagent@<VM_AI_HOST>:/home/aiadmin-subagent/nakel-ai/matcher/

# Reiniciar uvicorn
& "C:\Program Files\PuTTY\plink.exe" -batch -pw "<VM_PASSWORD>" `
  -hostkey "<HOSTKEY_SHA256>" `
  aiadmin-subagent@<VM_AI_HOST> `
  "pgrep -f 'uvicorn main' | xargs -r kill -9; sleep 3; cd /home/aiadmin-subagent/nakel-ai; setsid nohup ~/.local/bin/uvicorn main:app --host 0.0.0.0 --port 8001 </dev/null >/tmp/nakel-ai.log 2>&1 & disown"
```

## Dependencias

```txt
# requirements.txt
fastapi==0.115.5
uvicorn[standard]==0.32.1
pdfplumber==0.11.4
openpyxl==3.1.5
python-multipart==0.0.12
httpx==0.27.2
numpy==1.26.4
pillow==11.0.0
python-dotenv==1.0.1
rapidfuzz==3.10.1
```

## Tuning y monitoreo

### Logs en tiempo real
```bash
tail -f /tmp/nakel-ai.log | grep -E 'product_matcher.*→|Procesamiento'
```

### Métricas que mirar
- Cuántas llamadas a Gemini vs Ollama (URL del log)
- Latencia por ítem (~5-15s con Gemini Flash)
- Cuántos auto / review / no_match por import
- Reasoning del LLM (visible en `match_notes` y `price_interpretation`)

### Costos Gemini
- Flash: ~$0.0002 por llamada (prompt ~2K tokens + response ~150)
- Pro: ~$0.001 por llamada
- Para Cachafaz (~30 calls): Flash $0.006, Pro $0.03
- Con $200 de crédito: 13.000+ imports en Flash, 6.500 en Pro

## Limitaciones conocidas

1. **Latencia alta**: ~5-15 seg por ítem con Gemini Flash. Para listas de 100+ items, son varios minutos.
2. **Inconsistencia ocasional**: Gemini Flash puede dar respuestas distintas para casos similares (ej: AVENA & MIEL ✅ vs CACAO & MIEL ❌). Pro reduce esto pero cuesta 5x.
3. **Falsos no_match cuando no hay variante**: si el subset del partner no tiene la variante (CHOCO X 6 → debería ser NEGRO ESTUCHE X6U), depende de que Gemini haga el sinónimo CHOCO≡NEGRO.
4. **Costos placeholder en Odoo**: si `standard_price` es 0 o muy bajo (placeholder), la división `precio/costo` da números absurdos. El módulo Odoo lo maneja mostrando `Δ% = "—"` cuando `current_cost ≤ 1`.
