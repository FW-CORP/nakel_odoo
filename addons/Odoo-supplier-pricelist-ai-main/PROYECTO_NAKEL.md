# Proyecto Nakel — Agente IA de Actualización de Costos

> **Estado actual (2026-05-08):** Sprint 3 completado con Gemini 2.5 Flash. Pendiente deploy del módulo Odoo actualizado con interpretación comercial de precios.

## Contexto
Cliente: **Nakel** — distribuidor mayorista/minorista de golosinas, bebidas, alfajores, ferretería y productos de limpieza.

| Recurso | Valor |
|---|---|
| Instancia Odoo dev | `https://dev.nakel.net.ar/` |
| Base de datos | `prueba` |
| VM AI service | `<AI_SERVICE_HOST>` (aiadmin-subagent) |
| VM MCP server | `<MCP_HOST>` (aiadmin) |
| MCP modo | `YOLO=read` (solo lectura) |

---

## Objetivo del proyecto

Permitir que Nakel suba listas de precios de proveedores (PDF, Excel, imagen) y que la plataforma:

1. **Extraiga** los productos y sus nuevos costos sin esfuerzo manual
2. **Cruce** cada ítem con el catálogo Odoo, incluso con presentaciones distintas
3. **Interprete comercialmente** el precio (qué es 1 estuche vs 1 unidad)
4. **Compare** contra el costo actual (`standard_price`) con la métrica correcta
5. **Actualice** el `standard_price` (recálculo automático de listas de precio)

---

## Arquitectura (visión general)

```
┌──────────────────────────┐
│ Odoo dev.nakel.net.ar    │
│ Módulo nakel_supplier_   │
│        pricelist          │
│  ┌─────────────────────┐ │
│  │ supplier.pricelist. │ │      HTTP POST /api/match
│  │ import (form view)  │ ├─────────────────────────────┐
│  └─────────────────────┘ │                              │
└──────────────────────────┘                              │
                                                          ▼
                                          ┌────────────────────────────┐
                                          │ AI Service (FastAPI)       │
                                          │ VM <AI_SERVICE_HOST>:8001  │
                                          │                            │
                                          │  1. Parsea PDF/Excel       │
                                          │  2. Extracción tabular     │
                                          │     o LLM fallback         │
                                          │  3. Matching multicapa     │
                                          │  4. Smart match con LLM    │
                                          └─────┬─────────────┬────────┘
                                                │             │
                                          ┌─────▼───┐    ┌────▼─────────┐
                                          │ Ollama  │    │ Gemini 2.5   │
                                          │ local   │    │ Flash (API)  │
                                          │         │    │              │
                                          │ embed   │    │ smart match  │
                                          │ qwen2.5 │    │ + interpret  │
                                          └─────────┘    └──────────────┘
```

---

## Componentes implementados

### 1. Módulo Odoo `nakel_supplier_pricelist`
**Ubicación:** `odoo_module/nakel_supplier_pricelist/`
**Doc específica:** [`odoo_module/nakel_supplier_pricelist/README.md`](odoo_module/nakel_supplier_pricelist/README.md)

Modelos:
- `supplier.pricelist.import` — cabecera de importación
- `supplier.pricelist.import.line` — una línea por producto detectado, con campos:
  - `supplier_product_name`, `supplier_presentation`
  - `price_with_vat`, `price_without_vat`
  - **`unit_count`** — cuántas unidades Odoo hay en el precio del proveedor
  - **`unit_price_with_vat`**, **`unit_price_without_vat`** — precio normalizado por unidad
  - **`price_interpretation`** — texto explicando el cálculo (Gemini)
  - `current_cost`, `cost_delta_pct`, `cost_delta_display` (`Δ%` o `—`)
  - `delta_color` (muted/danger/warning/success según umbrales de negocio)
  - `match_status`: auto / review / no_match / rejected / confirmed
  - `confidence_score`, `match_notes`, `alternative_ids`
- `supplier.product.mapping` — memoria de matches confirmados (active learning)

### 2. Servicio AI FastAPI
**Ubicación:** `ai_service/`
**Doc específica:** [`ai_service/README.md`](ai_service/README.md)

Stack:
- FastAPI + uvicorn
- pdfplumber (parser estructurado de tablas + fallback regex de líneas de texto)
- rapidfuzz (fuzzy matching)
- httpx (Gemini API + Ollama local)
- python-dotenv (configuración)

Endpoint principal: `POST /api/match` (recibe PDF base64 + catálogo Odoo, devuelve matches con interpretación comercial).

---

## Estrategia de matching (Sprint 3)

### Capas (de más a menos confiable)

| Capa | Señal | Acción |
|------|-------|--------|
| **0. Barcode** | EAN-13 exacto | auto 100% |
| **1. Código de proveedor** | `product.supplierinfo.product_code` exacto | auto 100% |
| **2. Nombre conocido** | match en `supplier.product.mapping` | auto 98% |
| **2.5. Fuzzy fuerte** | `token_sort_ratio ≥ 85%` en subset del partner | auto |
| **3. Smart match (LLM)** | Gemini 2.5 Flash razona sobre subset del partner | auto/review/no_match |

### Filtro por proveedor
El catálogo se filtra a productos vinculados a ese proveedor vía `product.supplierinfo`. Si no hay match en ese subset, **no se cae al catálogo general** (los embeddings genéricos producían falsos positivos absurdos: BEEFEATER → BUTTER CREAM, BLANCO X 12 → RAID ESPIRALES, etc.).

### Smart match con Gemini

Ver detalle completo en [`ai_service/README.md`](ai_service/README.md). Resumen:
- Cada candidato se le presenta al LLM como `VARIANTE | PACK | costo $X | nombre`
- El `costo` de Odoo es el **ancla numérica**: `unit_count = round(precio_proveedor / costo_odoo)`
- Devuelve match_id + confidence + reasoning + **unit_count + unit_price + price_interpretation**

---

## Interpretación comercial (clave del Sprint 3)

**Problema descubierto:** Odoo guarda costo por unidad atómica (1 alfajor de 60g, 1 frasco de 450g, 1 estuche de 12 conitos), pero los proveedores cobran por pack (1 estuche de 12 alfajores). Comparar los precios crudos da Δ% absurdos (ej: +132.220%).

**Solución:** Gemini interpreta el contexto comercial y devuelve `unit_count`. El módulo Odoo calcula `unit_price = price / unit_count` y compara contra `standard_price` con la métrica correcta.

| Caso | Precio Cachafaz | Costo Odoo | Análisis | unit_count | unit_price | Δ% |
|---|---|---|---|---|---|---|
| BLANCO X 12 FLOWPACK | $14.190 | $1.123 (BLANCO X60G) | 14190/1123≈12 | **12** | $1.182 | +5.2% |
| BLANCO X 6 FLOWPACK | $7.281 | $5.470 (BLANCO ESTUCHE X6U) | 7281/5470≈1 | **1** | $7.281 | +33% |
| CONITO X 12 | $12.255 | $11.727 (CONITOS X12U) | 12255/11727≈1 | **1** | $12.255 | +4.5% |
| AVENA & MIEL | $1.322 | $1.253 (X170G) | 1322/1253≈1 | **1** | $1.322 | +5.5% |

---

## Soporte de formatos de PDF (Sprint 1)

El parser detecta tres arquetipos comunes y los procesa sin LLM:

| Arquetipo | Ejemplo | Estrategia |
|---|---|---|
| **A: Tabla rica con barcode** | Pernod Ricard | Parser tabular + regex de líneas de texto fallback. Captura: nombre, código proveedor, EAN-13, categoría, presentación, precio. |
| **B: Tabla simple sin barcode** | Tunki Pop | Parser tabular con detección de headers (PRODUCTO, PRESENTACION, PRECIO FINAL). |
| **C: Tabla con headers de sección** | Cachafaz/Patagonia | Parser tabular detecta filas-categoría (CAJAS EXHIBIDORAS, BOMBONES, etc.) y las asocia a las filas siguientes. Primer columna sin clasificar = nombre. |

Si ninguna estrategia funciona → fallback a LLM (Ollama qwen2.5:7b-instruct).

### Extracción de presentación y formato

El parser extrae automáticamente:
- **Pack del proveedor** (`12X80G`, `30X15G`, `X1KG`, `X6U`, etc.) desde la presentación cruda y desde el nombre Odoo
- **Variante** (TUTUCA, BOLITAS, CHIZITOS, MAICENA, BLANCO, etc.) desde keywords conocidas

---

## Backends LLM

Configurables vía `.env` en la VM:

```env
# Backend principal (smart matcher)
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-2.5-flash      # alternativa: gemini-2.5-pro

# Backend de fallback (Ollama local)
OLLAMA_URL=http://localhost:11434
EXTRACT_MODEL=qwen2.5:7b-instruct
DISAMBIG_MODEL=qwen2.5:14b
EMBED_MODEL=nomic-embed-text
```

El `smart_match` intenta Gemini primero, si falla cae a Ollama local.

---

## Resultados medidos

### Pernod Ricard (167 productos, lista bebidas con barcode)

| Métrica | Antes (LLM-only) | Después (Sprint 1+3) |
|---|---|---|
| Líneas extraídas | 29/158 (18%) | **167** (100%+ por duplicados de "Productos Prestige") |
| Auto matches correctos | ~2 (1.3%) | **~93** (capa 0 barcode al 100%) |
| Resto vía Gemini | — | ~40 review/auto correctos |
| **Tasa global** | ~1.3% | **~85%** |

### Cachafaz (41 productos, sin barcode)

| Iteración | Auto | Review | No match | Falsos positivos auto |
|---|---|---|---|---|
| Sprint 1 (qwen2.5:14b prompt rígido) | 22 | 15 | 4 | **22 (todos basura)** |
| Sprint 2 (cross-confirm + filtro partner) | 0 | 12 | 29 | 0 |
| Sprint 3 (Gemini Flash + prompt con costo) | **13** | **6** | 22 | **0** |

Calidad final: 13 auto (todos correctos) + 6 review (calibración honesta) + 22 no_match (mayoría correctos). 4 errores marginales (CHOCO X 6 sin matchear, MIXTO X 12 sin matchear, BLANCO suelto, ESTUCHE EXHIBIDOR).

### Tunki Pop (38 productos, snacks sin barcode)

13/13 auto correctos en última iteración con Gemini, calibrado por costo Odoo. ~25/38 productos del PDF tienen equivalente en Odoo; el resto va a no_match honesto.

---

## Historial de sprints

### Sprint 1 — Extracción tabular (no más LLM ciego)
**Problema:** El LLM extraía 29/158 productos de Pernod (18% recall) y matcheaba al 1.3%.
**Solución:** Parser tabular en `pdfplumber` con detección de headers + fallback regex de líneas de texto. Soporte para 3 arquetipos de PDF.
**Resultado:** 167 productos extraídos con barcode + código de proveedor.

### Sprint 2 — Filtro por partner + cross-confirmación
**Problema:** Embeddings genéricos producían falsos positivos absurdos (BEEFEATER → BUTTER CREAM al 95%).
**Solución:**
- Filtrar catálogo a productos vinculados al partner vía `product.supplierinfo`
- Cross-confirmación obligatoria fuzzy + embedding para auto
- No caer al catálogo general si hay subset del partner
- Umbrales más estrictos
**Resultado:** 0 falsos positivos auto; muchos no_match honestos.

### Sprint 3 — Smart match con Gemini + interpretación comercial
**Problema:** Sin presentación ni código, el matching dependía de embedding/fuzzy. Y el `cost_delta_pct` mostraba valores absurdos (+132220%) porque comparaba precio crudo del proveedor (por estuche) vs costo Odoo (por unidad).
**Solución:**
- Gemini 2.5 Flash como matcher principal (en vez de embedding)
- Prompt enriquecido con:
  - Convención de naming Odoo (formato al final del nombre)
  - Errores comunes del dominio (ARROZ ≠ MAÍZ, CHOCO ≡ NEGRO, etc.)
  - **`standard_price` de cada candidato como ancla numérica**
- Gemini calcula `unit_count = round(precio_proveedor / costo_odoo)` por aritmética
- Devuelve `unit_count + unit_price + price_interpretation`
**Resultado:**
- Matches inteligentes con razonamiento explícito en español
- Δ% calculado contra precio unitario correcto
- Calibración honesta de confianza (auto/review/no_match)

---

## Pasos siguientes

### Inmediato
- [ ] Deploy del módulo Odoo actualizado en `dev.nakel.net.ar` (campos `unit_count`, `unit_price_with_vat`, etc. + `_compute_current_cost` reescrito)
- [ ] Validar el flujo end-to-end: usuario revisa, confirma, aplica costos, verifica que `product.supplierinfo` y `standard_price` se actualicen

### Corto plazo
- [ ] Probar con más proveedores reales (5-10) para detectar patrones nuevos
- [ ] Active learning: cuando el usuario confirma un match, guardarlo en `supplier.product.mapping` para que el próximo import sea automático
- [ ] Soporte de Excel mejorado (algunos proveedores mandan en xlsx)

### Mediano plazo
- [ ] **Perfiles de proveedor persistidos**: primera vez que llega un proveedor, el usuario confirma el column mapping del PDF; próximas importaciones aplican el perfil sin LLM
- [ ] **Procesamiento batch**: enviar 5-10 ítems a Gemini en una sola llamada para reducir latencia (actualmente ~5-15 seg/ítem)
- [ ] Permitir que el usuario edite `unit_count` manualmente cuando Gemini se equivoque (con feedback loop)

### Largo plazo
- [ ] Cambiar MCP a `YOLO=true` (escritura) y permitir que el AI service escriba directamente en Odoo
- [ ] Reportes de tendencias de costos por proveedor / categoría
- [ ] Detección automática de nuevos productos (sin match → propuesta de creación)

---

## Configuración técnica actual

### MCP Servers (`~/.claude.json`)
```json
{
  "mcpServers": {
    "nakel-odoo": {
      "command": "ssh",
      "args": [
        "-i", "C:/Users/jorge/.ssh/id_rsa_ai226",
        "-p", "22",
        "-o", "StrictHostKeyChecking=no",
        "aiadmin@<VM_MCP_HOST>",
        "ODOO_URL=https://dev.nakel.net.ar ODOO_DB=prueba ODOO_USER=odoo@nakel.ar ODOO_PASSWORD=<PASSWORD> ODOO_YOLO=read /home/aiadmin/.local/bin/uvx mcp-server-odoo"
      ]
    }
  }
}
```

> ⚠️ El archivo `.mcp.json` real con credenciales **NO está en este repo** (incluido en `.gitignore`). Mantenelo en tu máquina local.

### VM AI Service (`<AI_SERVICE_HOST>`)
- Host: `<AI_SERVICE_HOST>` puerto 22
- Usuario: `aiadmin-subagent`
- Servicio en `/home/aiadmin-subagent/nakel-ai/` corriendo en puerto 8001
- Logs en `/tmp/nakel-ai.log`
- 2× RTX 3070 (8GB cada una), 9.2 GB RAM

### Comando de deploy (desde Windows)
```powershell
& "C:\Program Files\PuTTY\pscp.exe" -batch -hostkey "<HOSTKEY_SHA256>" -pw "<VM_PASSWORD>" "C:\Claude\nakel\ai_service\<archivo>" aiadmin-subagent@<VM_AI_HOST>:/home/aiadmin-subagent/nakel-ai/<destino>
```

> Reemplazar `<VM_PASSWORD>` y `<HOSTKEY_SHA256>` con los valores reales (no commitear).

Restart uvicorn:
```bash
pkill -f 'uvicorn main' && sleep 2 && cd /home/aiadmin-subagent/nakel-ai && \
  setsid nohup ~/.local/bin/uvicorn main:app --host 0.0.0.0 --port 8001 \
    </dev/null >/tmp/nakel-ai.log 2>&1 & disown
```

---

## Documentación específica por componente

- [`ai_service/README.md`](ai_service/README.md) — Servicio FastAPI: arquitectura, parser, matcher, prompt engineering
- [`odoo_module/nakel_supplier_pricelist/README.md`](odoo_module/nakel_supplier_pricelist/README.md) — Módulo Odoo: modelos, vistas, flujo, API
- [`CHANGELOG.md`](CHANGELOG.md) — Cronología de sprints y cambios técnicos
