"""
Nakel AI Supplier Pricelist Service
=====================================
FastAPI microservicio para matching inteligente de listas de precios de proveedores
con el catálogo de productos de Odoo.

Endpoints:
  POST /api/match          - Procesa un archivo y matchea con el catálogo
  GET  /api/health         - Health check con estado de Ollama
  GET  /api/models         - Modelos disponibles en Ollama
"""
import base64
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from parsers.pdf_parser import (
    extract_text_from_pdf_b64,
    extract_structured_rows_b64,
    detect_vat_included,
)
from parsers.excel_parser import extract_text_from_excel_b64
from parsers.image_parser import extract_text_from_image_b64
from matcher.llm_extractor import extract_products_from_text
from matcher.product_matcher import match_products

# ── Configuración ──────────────────────────────────────────────────────────────

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
logger = logging.getLogger('nakel_ai')

OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434')
EXTRACT_MODEL = os.getenv('EXTRACT_MODEL', 'qwen2.5:3b')    # Para extracción rápida
DISAMBIG_MODEL = os.getenv('DISAMBIG_MODEL', 'qwen2.5:7b')  # Para desambiguación
EMBED_MODEL = os.getenv('EMBED_MODEL', 'nomic-embed-text')   # Para embeddings
VISION_MODEL = os.getenv('VISION_MODEL', 'llama3.2-vision')  # Para imágenes

AUTO_THRESHOLD = int(os.getenv('AUTO_THRESHOLD', '88'))  # % mínimo para auto-match

# ── Modelos Pydantic ──────────────────────────────────────────────────────────

class ProductPackaging(BaseModel):
    name: str
    qty: float
    barcode: Optional[str] = None


class CatalogProduct(BaseModel):
    id: int
    name: str
    standard_price: float = 0.0
    categ_name: Optional[str] = None
    barcode: Optional[str] = None
    supplier_product_code: Optional[str] = None
    supplier_product_name: Optional[str] = None
    known_supplier_names: list[str] = Field(default_factory=list)
    is_known_supplier: bool = False
    # ── Datos de empaque (Sprint 4) ─────────────────────────────────────
    # uom_name: la unidad atómica (ej: "Units")
    # uom_po_name: unidad de compra (ej: "Pack of 12")
    # packagings: configuraciones de pack/bulto del producto
    uom_name: Optional[str] = None
    uom_po_name: Optional[str] = None
    packagings: list[ProductPackaging] = Field(default_factory=list)


class MatchRequest(BaseModel):
    file_content: str           # Base64-encoded file
    file_name: str              # Para detectar tipo (extensión)
    partner_id: int
    partner_name: str
    catalog: list[CatalogProduct]
    auto_threshold: Optional[int] = None  # Override de umbral global


class MatchResultItem(BaseModel):
    supplier_name: str
    presentation: Optional[str] = None
    price_with_vat: float
    vat_included: bool = True
    product_tmpl_id: Optional[int] = None
    product_name: Optional[str] = None
    confidence: int = 0
    match_status: str           # auto / review / no_match / rejected
    notes: str = ''
    alternative_product_ids: list[int] = Field(default_factory=list)
    # Interpretación comercial del LLM
    # unit_count = cuántas "unidades Odoo" hay en el precio del proveedor
    # unit_price = price_with_vat / unit_count (precio normalizado por unidad Odoo)
    unit_count: int = 1
    unit_price: Optional[float] = None
    price_interpretation: str = ''


class MatchResponse(BaseModel):
    partner_id: int
    partner_name: str
    file_name: str
    total_extracted: int
    vat_included: bool
    matches: list[MatchResultItem]
    warnings: list[str] = Field(default_factory=list)


# ── App ───────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Verifica disponibilidad de Ollama al arrancar."""
    logger.info(f'🚀 Nakel AI Service iniciando...')
    logger.info(f'   Ollama URL: {OLLAMA_URL}')
    logger.info(f'   Modelos: extract={EXTRACT_MODEL}, embed={EMBED_MODEL}, disambig={DISAMBIG_MODEL}')
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f'{OLLAMA_URL}/api/tags')
            models = [m['name'] for m in resp.json().get('models', [])]
            logger.info(f'   Modelos disponibles: {models}')
    except Exception as e:
        logger.warning(f'   ⚠️  Ollama no disponible: {e}')
    yield
    logger.info('Servicio detenido.')


app = FastAPI(
    title='Nakel AI Supplier Pricelist',
    description='Matching inteligente de listas de precios de proveedores con Odoo',
    version='1.0.0',
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f'❌ Validation error en {request.url}: {exc.errors()}')
    return JSONResponse(status_code=422, content={'detail': exc.errors()})

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get('/api/health')
async def health_check():
    """Health check — verifica Ollama y modelos."""
    status = {'service': 'ok', 'ollama': 'unknown', 'models': []}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f'{OLLAMA_URL}/api/tags')
            status['ollama'] = 'ok'
            status['models'] = [m['name'] for m in resp.json().get('models', [])]
    except Exception as e:
        status['ollama'] = f'error: {e}'
    return status


@app.get('/api/models')
async def list_models():
    """Lista los modelos disponibles en Ollama."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f'{OLLAMA_URL}/api/tags')
        resp.raise_for_status()
        return resp.json()


@app.post('/api/match', response_model=MatchResponse)
async def match_pricelist(request: MatchRequest):
    """
    Procesa una lista de precios de proveedor y la matchea con el catálogo de Odoo.

    Flujo:
      1. Parsea el archivo (PDF / Excel / CSV / imagen)
      2. Usa LLM para extraer productos y precios estructurados
      3. Matchea cada ítem con el catálogo usando embeddings + LLM
      4. Devuelve los matches con niveles de confianza
    """
    warnings = []
    threshold = request.auto_threshold or AUTO_THRESHOLD
    file_name = request.file_name or 'archivo'
    name_lower = file_name.lower()

    logger.info(
        f'📥 Procesando lista: {file_name} | '
        f'Proveedor: {request.partner_name} | '
        f'Catálogo: {len(request.catalog)} productos'
    )

    # ── Paso 1: Parsear el archivo ────────────────────────────────────────────
    try:
        if name_lower.endswith('.pdf'):
            logger.info('  → Parseando PDF...')
            raw_text = extract_text_from_pdf_b64(request.file_content)
        elif name_lower.endswith(('.xlsx', '.xls')):
            logger.info('  → Parseando Excel...')
            raw_text = extract_text_from_excel_b64(request.file_content, file_name)
        elif name_lower.endswith('.csv'):
            logger.info('  → Parseando CSV...')
            raw_text = extract_text_from_excel_b64(request.file_content, file_name)
        elif name_lower.endswith(('.jpg', '.jpeg', '.png')):
            logger.info('  → Procesando imagen con visión...')
            raw_text = await extract_text_from_image_b64(
                request.file_content, OLLAMA_URL, VISION_MODEL)
        else:
            # Intenta como PDF por defecto
            logger.warning(f'Extensión desconocida: {file_name}, intentando como PDF')
            warnings.append(f'Extensión "{file_name}" no reconocida, interpretando como PDF')
            raw_text = extract_text_from_pdf_b64(request.file_content)
    except Exception as e:
        logger.error(f'Error al parsear archivo: {e}')
        raise HTTPException(
            status_code=422,
            detail=f'No se pudo leer el archivo "{file_name}": {str(e)}'
        )

    if not raw_text.strip():
        raise HTTPException(
            status_code=422,
            detail='El archivo no contiene texto extraíble. '
                   '¿Es un PDF escaneado? Intentá con una imagen JPG/PNG.'
        )

    logger.info(f'  → Texto extraído: {len(raw_text)} caracteres')

    # ── Paso 2a: Intento de extracción tabular estructurada (sin LLM) ─────────
    extracted_items = None
    vat_included = True
    extraction_method = None

    if name_lower.endswith('.pdf'):
        try:
            logger.info('  → Intentando extracción tabular estructurada...')
            structured = extract_structured_rows_b64(request.file_content)
            if structured and len(structured) >= 5:
                extracted_items = structured
                vat_included = detect_vat_included(raw_text)
                extraction_method = 'structured_table'
                with_barcode = sum(1 for r in structured if r.get('barcode'))
                with_code = sum(1 for r in structured if r.get('supplier_code'))
                logger.info(
                    f'  ✓ Extracción tabular: {len(structured)} productos, '
                    f'{with_barcode} con barcode, {with_code} con código de proveedor, '
                    f'IVA incluido={vat_included} (sin LLM)'
                )
        except Exception as e:
            logger.warning(f'  ⚠ Extracción tabular falló: {e}, fallback a LLM')

    # ── Paso 2b: Fallback al LLM ──────────────────────────────────────────────
    if extracted_items is None:
        logger.info(f'  → Extrayendo productos con LLM ({EXTRACT_MODEL})...')
        try:
            extraction = await extract_products_from_text(
                raw_text=raw_text,
                partner_name=request.partner_name,
                ollama_url=OLLAMA_URL,
                model=EXTRACT_MODEL,
            )
            extracted_items = extraction.get('items', [])
            vat_included = extraction.get('vat_included', True)
            extraction_method = 'llm'
        except Exception as e:
            logger.error(f'Error en extracción LLM: {e}')
            raise HTTPException(
                status_code=503,
                detail=f'Error al extraer productos con LLM: {str(e)}'
            )

    if not extracted_items:
        logger.warning('El LLM no extrajo ningún producto')
        warnings.append(
            'El LLM no pudo identificar productos en el archivo. '
            'Verificá que el archivo sea una lista de precios.'
        )
        return MatchResponse(
            partner_id=request.partner_id,
            partner_name=request.partner_name,
            file_name=file_name,
            total_extracted=0,
            vat_included=True,
            matches=[],
            warnings=warnings,
        )

    logger.info(f'  → {len(extracted_items)} productos extraídos')

    # ── Paso 3: Matchear con catálogo ─────────────────────────────────────────
    logger.info(f'  → Matcheando con catálogo (umbral auto: {threshold}%)...')
    catalog_dicts = [p.model_dump() for p in request.catalog]

    try:
        matched = await match_products(
            extracted_items=extracted_items,
            catalog=catalog_dicts,
            partner_name=request.partner_name,
            auto_threshold_pct=threshold,
            ollama_url=OLLAMA_URL,
            embed_model=EMBED_MODEL,
            llm_model=DISAMBIG_MODEL,
        )
    except Exception as e:
        import traceback
        logger.error(f'Error en matching: {e}\n{traceback.format_exc()}')
        raise HTTPException(
            status_code=503,
            detail=f'Error en el proceso de matching: {str(e)}'
        )

    # Aplica vat_included global al resultado
    for m in matched:
        m['vat_included'] = vat_included

    # Estadísticas
    auto_count = sum(1 for m in matched if m['match_status'] == 'auto')
    review_count = sum(1 for m in matched if m['match_status'] == 'review')
    no_match_count = sum(1 for m in matched if m['match_status'] == 'no_match')

    logger.info(
        f'✅ Procesamiento completo: '
        f'{auto_count} auto / {review_count} revisión / {no_match_count} sin match'
    )

    return MatchResponse(
        partner_id=request.partner_id,
        partner_name=request.partner_name,
        file_name=file_name,
        total_extracted=len(extracted_items),
        vat_included=vat_included,
        matches=[MatchResultItem(**m) for m in matched],
        warnings=warnings,
    )
