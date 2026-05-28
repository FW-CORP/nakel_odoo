"""
LLM Smart Matcher — razonamiento explícito sobre el match de productos.

Soporta dos backends:
  1. Gemini API (preferido si hay GEMINI_API_KEY) — modelo frontier, mucho mejor
     reasoning en español y conocimiento del dominio
  2. Ollama local (qwen2.5:14b) — fallback si Gemini no está configurado o falla

A diferencia del `llm_disambiguator` que solo elige entre candidatos preseleccionados,
este matcher recibe el ítem completo del proveedor con todo su contexto (nombre,
presentación, categoría, precio, marca implícita del proveedor) y un subset de
candidatos del catálogo Odoo. Le pide al LLM que razone sobre:
  - Marca implícita (qué vende el proveedor en general)
  - Presentación (X 12 vs X 6, X 1KG vs X 80GR, FLOWPACK vs ESTUCHE)
  - Variante (sabor, color, edición)
  - Categoría/uso

Devuelve {product_id, confidence, reasoning} o no_match con justificación.
"""
import json
import logging
import os
import re
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ── Configuración Gemini ──────────────────────────────────────────────────────
# IMPORTANTE: leemos las env vars EN CADA LLAMADA, no a module-load time.
# Caso contrario, si load_dotenv() se ejecuta después de importar este módulo
# (que es lo que pasa en main.py), las vars salen vacías.
GEMINI_URL = (
    'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
)


def _gemini_config() -> tuple[str, str]:
    """Devuelve (api_key, model) leyendo desde env vars al momento de la llamada."""
    return (
        os.getenv('GEMINI_API_KEY', '').strip(),
        os.getenv('GEMINI_MODEL', 'gemini-2.5-flash'),
    )


# ── Pre-parseo de productos para el LLM ──────────────────────────────────────

def _parse_pack_size(text: str) -> Optional[str]:
    """
    Extrae el tamaño/pack normalizado de un texto.
    Ejemplos:
      "TUTUCA TUNKI POP 12X80G."          → "12X80G"
      "PALITOS SALADOS TUNKI X1KG."       → "1KG"
      "MINI HELADITOS SECOS 25X5G."       → "25X5G"
      "5 bol. x 12 unid. x 80gr."         → "12X80G"  (12 unid x 80g)
      "10 bol. x 30 unid. x 15gr."        → "30X15G"  (30 unid x 15g)
      "15 bol. x 20 unid. x 20gr."        → "20X20G"
      "18 unid. x 80gr."                  → "18X80G"
      "5 bol. X 1kg."                     → "1KG"
      "5 kg."                             → "5KG"
      "x 21 unidades"                     → "21U"
      "12 Estuches x 12 u."               → "12U"
      "ALF.CACHAFAZ BLANCO X60G.-505- (12)" → "60G"
    """
    if not text:
        return None
    t = text.upper().replace(',', '.').replace('GR', 'G').replace('GS', 'G')
    t = re.sub(r'\s+', ' ', t)

    # Patrón EXTENDIDO típico de proveedor: "N unid. x SIZE [g/kg/ml/l]"
    # Ej: "5 bol. x 12 unid. x 80gr." → 12X80G
    m = re.search(
        r'(\d+)\s*UNID(?:ADES)?\.?\s*[X×]\s*(\d+(?:\.\d+)?)\s*(KG|G|ML|L)\b',
        t
    )
    if m:
        return f'{m.group(1)}X{m.group(2)}{m.group(3)}'

    # Patrón "N unidades" o "N u." (sólo cantidad de unidades)
    m = re.search(r'[X×]\s*(\d+)\s*UNIDADES?\b', t)
    if m:
        return f'{m.group(1)}U'
    m = re.search(r'(\d+)\s*U\.\s*$', t)  # "12 u."
    if m:
        return f'{m.group(1)}U'

    # Patrón compacto Odoo: "Nx M[unidad]" tipo "12X80G", "25X5G"
    m = re.search(r'(\d+)\s*[X×]\s*(\d+(?:\.\d+)?)\s*(KG|G|ML|L)\b', t)
    if m:
        return f'{m.group(1)}X{m.group(2)}{m.group(3)}'

    # Patrón: "X1KG", "X80G", "X750ML"
    m = re.search(r'X\s*(\d+(?:\.\d+)?)\s*(KG|G|ML|L)\b', t)
    if m:
        return f'{m.group(1)}{m.group(2)}'

    # Patrón: "1KG.", "5 KG", "750ML"
    m = re.search(r'(?<![\d.])(\d+(?:\.\d+)?)\s*(KG|ML|L)\b', t)
    if m:
        return f'{m.group(1)}{m.group(2)}'

    return None


# Palabras-clave que típicamente describen una variante principal de producto
# Estas se usan para extraer la "palabra-variante" del nombre Odoo y mostrarla al LLM
_VARIANT_KEYWORDS = {
    # Snacks
    'TUTUCA', 'BOLITAS', 'CHIZITOS', 'PALITOS', 'PIZZITAS', 'TRONQUITOS',
    'NACHOS', 'ARITOS', 'HELADITOS', 'TUNKI', 'TIPSY',
    # Alfajores y derivados
    'ALFAJOR', 'CONITOS', 'CONITO', 'MAICENA', 'BLANCO', 'NEGRO', 'MOUSSE',
    'MIXTO', 'MARROC', 'CACHAFAZ',
    # Galletas
    'GALL', 'GALLETA', 'AVENA', 'CACAO', 'MIEL', 'CHIPS', 'GRANOLA',
    # Bebidas
    'WHISKY', 'WHISKEY', 'GIN', 'VODKA', 'CHAMPAGNE', 'CHAMPAÑA',
    'CHIVAS', 'BEEFEATER', 'GLENLIVET', 'BALLANTINES', 'JAMESON',
    'MUMM', 'ABSOLUT', 'WYBOROWA', 'HAVANA', 'MALIBU',
    # Otros
    'DULCE DE LECHE', 'CHOCOLATE',
}


def _extract_variant_word(text: str) -> str:
    """
    Extrae la palabra-variante principal de un nombre.
    Ej: "[2737.00] CHIZITOS SABOR QUESO TUNKI X1KG." → "CHIZITOS"
    """
    if not text:
        return ''
    # Sacar códigos entre [] y al final tipo "-797-"
    t = re.sub(r'\[[^\]]*\]', '', text)
    t = re.sub(r'-\d+-?\s*', ' ', t)
    t = re.sub(r'\([^)]*\)', '', t)
    t = t.upper()

    # Buscar primera palabra que esté en el set de variantes conocidas
    tokens = re.findall(r'[A-ZÁÉÍÓÚÑ]+', t)
    for tok in tokens:
        if tok in _VARIANT_KEYWORDS or tok.rstrip('S') in _VARIANT_KEYWORDS:
            return tok

    # Si no, devolver la primera palabra significativa (>3 chars, no genérica)
    skip = {'X', 'X1U', 'TUNKI', 'CACHAFAZ', 'GALL', 'ALF'}
    for tok in tokens:
        if len(tok) > 2 and tok not in skip:
            return tok
    return tokens[0] if tokens else ''


def _summarize_candidate(p: dict) -> str:
    """
    Devuelve un summary estructurado del producto para el LLM:
      "VARIANT | PACK | costo $X | packagings | nombre completo"

    Tres anclas determinísticas para el unit_count:
      1. costo (standard_price): permite calcular unit_count = precio_prov / costo
      2. packagings: dice explícitamente cuántas unidades hay en cada bulto
         (ej: "Pack de 12 unidades qty=12") — si el proveedor habla de "X 12",
         el packaging confirma que unit_count=12.
      3. uom_po: si la unidad de compra es "Pack of 12", da otra pista.
    """
    name = p.get('name', '')
    variant = _extract_variant_word(name)
    pack = _parse_pack_size(name) or '?'
    cost = p.get('standard_price') or 0.0
    cost_str = f'${cost:>10,.2f}' if cost else '   sin costo'

    # Packagings configurados en Odoo: lista corta de "qty:X" para que el LLM
    # vea las cantidades disponibles
    packagings = p.get('packagings') or []
    if packagings:
        pkg_parts = []
        for pkg in packagings[:4]:  # top 4 para no inflar el prompt
            qty = pkg.get('qty', 0)
            pname = (pkg.get('name') or '').strip()[:30]
            if qty:
                pkg_parts.append(f'{pname or "pkg"}={int(qty)}u')
        pkg_str = '[' + ', '.join(pkg_parts) + ']' if pkg_parts else '[—]'
    else:
        pkg_str = '[—]'

    return f'{variant or "?":15} | {pack:10} | {cost_str} | {pkg_str:40} | {name}'


SMART_MATCH_PROMPT = """Sos experto en distribuidoras, supermercados y abastecimiento mayorista en Argentina.

Estamos procesando una lista de precios del proveedor **"{partner_name}"** para el
mayorista Nakel. Para cada ítem tenés DOS tareas combinadas:

  (A) Decidir qué producto Odoo corresponde (o no_match si ninguno encaja).
  (B) Interpretar el precio comercialmente para que sea comparable con el costo
      unitario que Nakel guarda en Odoo.

# 🔑 Contexto comercial crítico (tarea B)

Odoo guarda un `standard_price` (costo actual) para cada producto. Pero la "unidad
de costo" depende del producto:
  - Algunos productos guardan costo POR UNIDAD INDIVIDUAL (ej: 1 alfajor de 60g = $1.123)
  - Otros guardan costo POR ESTUCHE (ej: 1 estuche de 6 alfajores = $5.470)
  - Otros guardan costo POR PAQUETE/PACK (ej: 1 paquete de 170g = $1.253)

**Tenés 3 anclas para deducir el `unit_count` correcto**:

### Ancla 1: Costo Odoo (standard_price)
El `unit_count` correcto es el número que hace que `precio_proveedor / unit_count`
sea numéricamente similar al `costo_odoo` del candidato.
  - Si `precio / costo ≈ 1` → unit_count=1
  - Si `precio / costo ≈ 6, 12, 24` → ese es el unit_count

### Ancla 2: Packagings configurados (columna entre `[ ]`)
Cada candidato muestra los packagings que tiene cargados en Odoo, con cantidad
de unidades. Ej:
  - `[Pack de 12 unidades=12u, Bulto x72=72u]` → el producto se compra en packs
    de 12 o 72 unidades. Si el proveedor habla de "X 12" → unit_count=12 (matchea
    el packaging de 12).
  - `[Pack de 21 unidades=21u]` → si el proveedor cobra por pack y dice "x 21
    unidades" → unit_count=21.
  - `[—]` (sin packagings) → no hay info, usá ancla 1 o 3.

### Ancla 3: Pack del nombre Odoo
El formato al final del nombre (`X1KG`, `12X80G`, `X450G`) describe la unidad
atómica. Si coincide con la presentación del proveedor → unit_count=1.

### Algoritmo mental
  1. Identificá el match correcto (variante + presentación).
  2. Si los packagings del candidato matchean con la cantidad que dice el proveedor
     (ej: "X 12" ↔ packaging qty=12) → unit_count=esa qty.
  3. Si no hay packagings claros, usá `unit_count = round(precio / costo)`.
  4. Verificá: `precio / unit_count` debería estar entre 0.5x y 1.5x del `costo_odoo`.

# Ejemplos resueltos

| Caso | Ítem | Precio prov. | Candidato Odoo | costo Odoo | División | unit_count | unit_price |
|---|---|---|---|---|---|---|---|
| 1 | BLANCO X 12 FLOWPACK     | $14.190 | BLANCO X60G (12)        | $1.123  | 14190/1123=12.6  | **12** | $1.182  |
| 2 | BLANCO X 6 FLOWPACK      | $7.281  | BLANCO ESTUCHE X6U      | $5.470  | 7281/5470=1.33   | **1**  | $7.281  |
| 3 | CONITO X 12              | $12.255 | CONITOS CACHAFAZ X12U   | $11.727 | 12255/11727=1.04 | **1**  | $12.255 |
| 4 | X 450 GR (DULCE DE LECHE)| $4.052  | DULCE DE LECHE X450G    | $3.786  | 4052/3786=1.07   | **1**  | $4.052  |
| 5 | AVENA & MIEL             | $1.322  | GALL ORG. AVENA&MIEL X170G | $1.253 | 1322/1253=1.05  | **1**  | $1.322  |
| 6 | BOCADITOS MARROC         | $28.085 | MARROC CACHAFAZ X54U    | $25.531 | 28085/25531=1.10 | **1**  | $28.085 |
| 7 | MAICENA X 12             | $14.190 | MAICENA X76G            | $1.123  | 14190/1123=12.6  | **12** | $1.182  |

Notá los casos 2 y 3: aunque el ítem dice "X 6" y "X 12", el costo Odoo del
candidato YA está por estuche, así que unit_count=1 (no dividir).

# 📋 Ítem del proveedor
- Nombre crudo:        "{supplier_name}"
- Presentación cruda:  "{presentation}"
- Sección del PDF:     "{category}"
- Precio:              ${price:,.2f}

# 📚 Candidatos del catálogo Odoo (subset del proveedor)
Cada candidato muestra "VARIANTE | PACK | nombre completo". Las dos primeras columnas
son extracción automática orientativa — leé el nombre completo si te confunde.

{candidates_list}

# ⚠️ Errores comunes a evitar
- ARROZ ≠ MAÍZ. TUTUCA es **solo** maíz inflado. Si el ítem es ARROZ inflado y no
  hay candidato explícitamente de arroz (o GHOST), es no_match.
- BOLITAS ≠ TUTUCA ≠ ARITOS ≠ CHIZITOS ≠ PALITOS ≠ PIZZITAS ≠ TRONQUITOS ≠ NACHOS.
- CHIZITOS DE MAÍZ vs CHIZITOS SABOR QUESO → la línea coincide pero el sabor difiere → REVIEW (no auto).
- POP ≠ GHOST (líneas Tunki distintas).
- "CON LECHE", "SEMIAMARGO ALMENDRAS" sin más contexto son chocolates a granel,
  NO alfajores. Si no hay producto chocolate específico en candidatos → no_match.
  **NO confundas "CON LECHE" con CONITOS** ni con alfajores.
- "BOLSAS PROPILENO", "MALETÍN", "BOLSA CARTÓN" son packaging → no_match.

# 💡 Sinónimos útiles
- CHOCO ≡ NEGRO (en alfajores).
- CONITO ≡ CONITOS.
- Sección "DULCE DE LECHE" + "X 450 GR" → DULCE DE LECHE CACHAFAZ X450G.

# 🎯 Tu respuesta (JSON estricto)
{{
  "variante_item":   "<variante que identificás del ítem>",
  "match_id":        <1..N elegido o 0 si no_match>,
  "confidence":      <0-100>,
  "reasoning":       "<máx 100 caracteres>",

  "unit_count":      <entero: cuántas 'unidades Odoo' hay en el precio del proveedor>,
  "unit_price":      <decimal: precio/unit_count, o null si no_match>,
  "price_interpretation": "<máx 120 caracteres explicando unit_count>"
}}

# Calibración de confidence
- 95-100: variante + presentación + interpretación de pack TODO claro.
- 85-94:  alta seguridad, una duda menor.
- 70-84:  variante OK, dudas en sabor/sub-tipo/presentación → REVIEW.
- 50-69:  candidato razonable con varias dudas → REVIEW.
- 0-49:   no encaja → match_id=0, unit_price=null.

NO uses 90+ si reasoning incluye "aunque..." o "ligeramente...".
NO uses 0 si hay un candidato razonable — usá 50-70 y mandalo a review.
SIEMPRE devolvé unit_count y unit_price, incluso en review (excepto no_match).
"""


async def _call_gemini(prompt: str, timeout: int = 60) -> Optional[str]:
    """Llama a la Gemini API. Devuelve el texto crudo de la respuesta o None."""
    api_key, model = _gemini_config()
    if not api_key:
        return None

    url = GEMINI_URL.format(model=model)
    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {
            'temperature': 0.1,
            'maxOutputTokens': 8000,
            'responseMimeType': 'application/json',
            'responseSchema': {
                'type': 'object',
                'properties': {
                    'variante_item': {'type': 'string'},
                    'match_id': {'type': 'integer'},
                    'confidence': {'type': 'integer'},
                    'reasoning': {'type': 'string'},
                    'unit_count': {'type': 'integer'},
                    'unit_price': {'type': 'number'},
                    'price_interpretation': {'type': 'string'},
                },
                'required': ['match_id', 'confidence', 'reasoning'],
            },
        },
    }
    headers = {'x-goog-api-key': api_key, 'Content-Type': 'application/json'}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get('candidates', [])
            if not candidates:
                logger.warning(f'Gemini: respuesta sin candidates: {data}')
                return None
            content = candidates[0].get('content', {})
            parts = content.get('parts', [])
            if not parts:
                return None
            return parts[0].get('text', '').strip()
    except Exception as e:
        logger.warning(f'Gemini API error: {e}')
        return None


async def _call_ollama(
    prompt: str, ollama_url: str, model: str, timeout: int = 90
) -> Optional[str]:
    """Llama a Ollama local. Devuelve el texto crudo de la respuesta o None."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f'{ollama_url}/api/generate',
                json={
                    'model': model,
                    'prompt': prompt,
                    'stream': False,
                    'format': 'json',
                    'options': {'temperature': 0.1, 'num_predict': 500},
                },
            )
            resp.raise_for_status()
            return resp.json().get('response', '').strip()
    except Exception as e:
        logger.warning(f'Ollama API error: {e}')
        return None


def _parse_llm_json(text: str) -> Optional[dict]:
    """Parsea la respuesta JSON del LLM con fallback a regex."""
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'\{[\s\S]*\}', text)
        if not m:
            logger.warning(f'No se pudo parsear JSON. Respuesta: {text[:200]}')
            return None
        try:
            return json.loads(m.group())
        except json.JSONDecodeError as e:
            logger.warning(f'JSON inválido: {e}. Respuesta: {text[:200]}')
            return None


async def smart_match(
    supplier_name: str,
    presentation: Optional[str],
    category: Optional[str],
    price: float,
    partner_name: str,
    candidates: list[dict],
    ollama_url: str = 'http://localhost:11434',
    model: str = 'qwen2.5:14b',
    timeout: int = 90,
) -> Optional[dict]:
    """
    Pide al LLM que razone sobre el match óptimo entre ítem del proveedor y catálogo.

    Backend:
      1. Si GEMINI_API_KEY está seteada → usa Gemini (mucho mejor reasoning)
      2. Caso contrario → fallback a Ollama local

    Args:
        supplier_name: Nombre crudo del producto en la lista del proveedor.
        presentation: Presentación/pack del proveedor (ej: "6 Estuches x 12 u.").
        category: Categoría o sección del PDF (ej: "CAJAS EXHIBIDORAS").
        price: Precio del ítem (para contexto, no se usa en match).
        partner_name: Nombre del proveedor (clave para inferir marca).
        candidates: Lista de productos Odoo del subset del partner. Cada dict
            debe tener al menos {id, name, categ_name?}. Idealmente top 10-15.
        ollama_url, model, timeout: configuración del fallback Ollama.

    Returns:
        Dict con {product, confidence, reasoning, llm_used, backend} si hubo match,
        o None si el LLM dijo no_match (match_id=0) o falló.
    """
    if not candidates:
        return None

    # Truncar candidatos a 15 para que el prompt no se vaya de tamaño
    candidates = candidates[:15]

    # Cada candidato pre-parseado: "i. VARIANTE | PACK | nombre completo"
    candidates_list = '\n'.join(
        f'{i+1}. {_summarize_candidate(p)}'
        for i, p in enumerate(candidates)
    )

    # Pre-parseo del ítem del proveedor para ayudar a Gemini
    item_variant = _extract_variant_word(supplier_name)
    item_pack = _parse_pack_size(presentation or '') or _parse_pack_size(supplier_name) or '?'

    prompt = SMART_MATCH_PROMPT.format(
        partner_name=partner_name,
        supplier_name=supplier_name,
        presentation=presentation or '(no especificada)',
        category=category or '(no especificada)',
        item_variant=item_variant or '?',
        item_pack=item_pack,
        price=price or 0,
        candidates_list=candidates_list,
    )

    # Intentar Gemini primero
    response_text = None
    backend = None
    api_key, gem_model = _gemini_config()
    if api_key:
        response_text = await _call_gemini(prompt, timeout=timeout)
        if response_text:
            backend = f'gemini ({gem_model})'

    # Fallback a Ollama si Gemini no responde
    if not response_text:
        response_text = await _call_ollama(prompt, ollama_url, model, timeout=timeout)
        if response_text:
            backend = f'ollama ({model})'

    if not response_text:
        logger.warning(f'smart_match: ningún LLM respondió para "{supplier_name}"')
        return None

    data = _parse_llm_json(response_text)
    if not data:
        return None

    match_id = data.get('match_id', 0)
    try:
        match_id = int(match_id)
    except (TypeError, ValueError):
        match_id = 0
    try:
        confidence = int(data.get('confidence', 0))
    except (TypeError, ValueError):
        confidence = 0
    reasoning = (data.get('reasoning') or '').strip()

    # Interpretación comercial (unit_count = cuántas unidades Odoo hay en el precio)
    try:
        unit_count = int(data.get('unit_count', 1))
        if unit_count < 1:
            unit_count = 1
    except (TypeError, ValueError):
        unit_count = 1

    try:
        unit_price = float(data.get('unit_price')) if data.get('unit_price') is not None else None
    except (TypeError, ValueError):
        unit_price = None

    price_interp = (data.get('price_interpretation') or '').strip()

    # Si el LLM no calculó unit_price pero sí dio unit_count, calcularlo nosotros
    if unit_price is None and price and unit_count >= 1:
        unit_price = price / unit_count

    if match_id < 0 or match_id > len(candidates):
        logger.warning(f'smart_match: match_id fuera de rango: {match_id}')
        return None

    if match_id == 0:
        logger.debug(
            f'smart_match [{backend}]: no_match para "{supplier_name}" '
            f'(reasoning: {reasoning})'
        )
        return {
            'product': None,
            'confidence': confidence,
            'reasoning': reasoning,
            'unit_count': 1,
            'unit_price': None,
            'price_interpretation': '',
            'llm_used': True,
            'backend': backend,
            'no_match': True,
        }

    chosen = candidates[match_id - 1]
    logger.debug(
        f'smart_match [{backend}]: "{supplier_name}" → {chosen["name"][:40]} '
        f'(conf={confidence}%, unit_count={unit_count}, unit_price={unit_price})'
    )
    return {
        'product': chosen,
        'confidence': confidence,
        'reasoning': reasoning,
        'unit_count': unit_count,
        'unit_price': unit_price,
        'price_interpretation': price_interp,
        'llm_used': True,
        'backend': backend,
        'no_match': False,
    }
