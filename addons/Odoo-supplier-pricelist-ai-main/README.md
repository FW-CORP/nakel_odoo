# Nakel — Agente IA de Listas de Precios de Proveedores

Plataforma para que Nakel suba listas de precios (PDF/Excel/imagen) y la IA extraiga, matchee con el catálogo Odoo, interprete los precios comercialmente, y prepare los costos para actualizar.

## Componentes

| Componente | Ruta | Descripción |
|---|---|---|
| **Módulo Odoo** | `odoo_module/nakel_supplier_pricelist/` | Modelo + UI en Odoo 18 |
| **AI Service** | `ai_service/` | Microservicio FastAPI que procesa los archivos |
| **Doc principal** | `PROYECTO_NAKEL.md` | Visión general del proyecto |
| **Changelog** | `CHANGELOG.md` | Historia técnica de sprints |

## Quick start

### Para desarrollar / testear localmente
```bash
# AI service (modo dev)
cd ai_service/
cp .env.example .env
# editar .env: GEMINI_API_KEY=...
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### Para deployar a la VM
Ver instrucciones en [`ai_service/README.md`](ai_service/README.md#deploy-a-la-vm).

### Para instalar el módulo en Odoo
Ver [`odoo_module/nakel_supplier_pricelist/README.md`](odoo_module/nakel_supplier_pricelist/README.md#instalación).

## Arquitectura en 30 segundos

```
Usuario en Odoo dev.nakel.net.ar
        │
        │ Sube PDF/Excel + click "Procesar con IA"
        ▼
┌──────────────────────────────────────────────────┐
│ Módulo Odoo nakel_supplier_pricelist             │
│ → Construye catálogo del proveedor               │
│ → POST http://<AI_SERVICE_HOST>:8001/api/match   │
└────────────────────┬─────────────────────────────┘
                     │ (catálogo + archivo b64)
                     ▼
┌──────────────────────────────────────────────────┐
│ AI Service (VM <AI_SERVICE_HOST> puerto 8001)    │
│                                                  │
│ 1. Parser tabular del PDF (sin LLM)              │
│    → 167 productos con barcode + código          │
│                                                  │
│ 2. Para cada producto:                           │
│    a. Capa 0: barcode exacto       → auto 100%   │
│    b. Capa 1: código proveedor     → auto 100%   │
│    c. Capa 2: nombre conocido      → auto  98%   │
│    d. Capa 3: smart match (Gemini) → auto/review │
│       │                                          │
│       └─→ Gemini interpreta:                     │
│           - Variante (CHOCO ≡ NEGRO)             │
│           - Pack (X 12 → 12 unidades)            │
│           - unit_count = precio/costo_odoo       │
│                                                  │
│ 3. Devuelve matches + unit_count + reasoning     │
└────────────────────┬─────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────┐
│ Módulo Odoo recibe matches                       │
│ → Crea líneas con auto/review/no_match           │
│ → Usuario revisa → Aplica costos                 │
│ → Update standard_price y product.supplierinfo   │
└──────────────────────────────────────────────────┘
```

## Estado actual (2026-05-08)

| Aspecto | Estado |
|---|---|
| Parser tabular de PDFs | ✅ funcional con 3 arquetipos (Pernod, Tunki, Cachafaz) |
| Capa 0 (barcode) | ✅ 100% accuracy cuando barcode está en Odoo |
| Capa 1 (código proveedor) | ✅ funcional |
| Capa 2 (nombre conocido) | ✅ funcional, alimentada por confirmaciones del usuario |
| Capa 3 (smart match LLM) | ✅ Gemini 2.5 Flash con interpretación comercial |
| Filtro por partner | ✅ catálogo se filtra a productos del proveedor |
| Δ% (cost_delta_pct) | ✅ usa `unit_price_without_vat` (pendiente deploy módulo) |
| Active learning | ⚠️ tabla existe, falta loop al confirmar match |
| Perfiles de proveedor | ⏳ futuro Sprint 4 |

### Métricas reales (Cachafaz, 41 productos)

- **13 auto correctos** (sin falsos positivos)
- **6 review** con calibración honesta
- **22 no_match** mayoritariamente correctos

## Stack técnico

- **Odoo 18** (módulo)
- **Python 3.10+** (FastAPI)
- **pdfplumber 0.11** (parser PDF)
- **rapidfuzz 3.10** (fuzzy matching)
- **Gemini 2.5 Flash** (LLM principal, vía API)
- **Ollama** (fallback local: qwen2.5:14b, nomic-embed-text)
- **httpx** (clientes HTTP async)

## Documentación adicional

- [`PROYECTO_NAKEL.md`](PROYECTO_NAKEL.md) — visión general del proyecto, contexto de Nakel, decisiones arquitectónicas
- [`CHANGELOG.md`](CHANGELOG.md) — historia técnica detallada de cada sprint
- [`ai_service/README.md`](ai_service/README.md) — doc técnica del microservicio
- [`odoo_module/nakel_supplier_pricelist/README.md`](odoo_module/nakel_supplier_pricelist/README.md) — doc del módulo Odoo
