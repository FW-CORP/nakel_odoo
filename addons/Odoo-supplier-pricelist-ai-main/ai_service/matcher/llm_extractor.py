"""
LLM Extractor: usa un modelo local (via Ollama) para convertir el texto
crudo de la lista de precios en una lista estructurada de productos.
"""
import json
import logging
import re
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Sos un asistente especializado en procesar listas de precios de proveedores en Argentina.

Analizá el siguiente texto extraído de una lista de precios y extraé TODOS los productos con sus precios.

TEXTO:
{raw_text}

INSTRUCCIONES:
- Extraé CADA línea/fila de producto. No te saltes ninguna.
- El texto puede ser una tabla con columnas separadas por tabulaciones o espacios. Las columnas típicas son:
  subcategoría, número, artículo/nombre, tipo (Bot/Est/Kit), botellas por caja, litros, cajas por pallet, precios base, IVA, precio final botella, precio final caja, variación %, código caja, código botella.
- Usá el campo "nombre" para el nombre del artículo (columna ARTICULO o similar).
- Usá el campo "precio" para el Precio Final BOTELLA (o el precio unitario si no hay columna de botella). Si solo hay precio de caja, dividilo por la cantidad de botellas.
- Si encontrás un código de barras (EAN-13, 13 dígitos, columna "Código Botella" o "Código Caja"), incluilo en "barcode".
- Si el precio ya incluye IVA (21%) indicá vat_included: true. Si es precio neto, vat_included: false.
- Ignorá encabezados, totales, notas y filas que no sean productos.
- El precio debe ser un número sin signos de moneda ni puntos de miles (usá punto decimal).
- Si hay múltiples presentaciones del mismo producto, listá cada una por separado.
- Proveedor: {partner_name}

Respondé ÚNICAMENTE con un JSON válido con este formato exacto:
{{
  "vat_included": false,
  "items": [
    {{
      "name": "nombre del artículo tal cual aparece",
      "presentation": "presentación (ej: 6x700ml, 12x1000ml) - puede ser null",
      "price": 12500.00,
      "barcode": "1234567890123"
    }}
  ]
}}

El campo "barcode" puede ser null si no hay código disponible.
No incluyas texto fuera del JSON. Si no podés extraer ningún producto, devolvé {{"vat_included": false, "items": []}}."""


async def extract_products_from_text(
    raw_text: str,
    partner_name: str,
    ollama_url: str = 'http://localhost:11434',
    model: str = 'qwen2.5:3b',
) -> dict:
    """
    Llama al LLM local para extraer la lista estructurada de productos.
    Devuelve dict con 'vat_included' y 'items' (lista de dicts).
    Si el texto es muy largo, lo procesa en chunks y combina los resultados.
    """
    MAX_CHUNK = 6000  # chars por chunk para no superar contexto del modelo

    if len(raw_text) <= MAX_CHUNK:
        result = await _extract_chunk(raw_text, partner_name, ollama_url, model)
        return _enrich_barcodes(result, raw_text)

    # Texto largo: divide en chunks por líneas y combina
    logger.info(f'Texto largo ({len(raw_text)} chars), procesando en chunks...')
    lines = raw_text.split('\n')
    chunks = []
    current = []
    current_len = 0

    for line in lines:
        if current_len + len(line) > MAX_CHUNK and current:
            chunks.append('\n'.join(current))
            current = [line]
            current_len = len(line)
        else:
            current.append(line)
            current_len += len(line) + 1

    if current:
        chunks.append('\n'.join(current))

    logger.info(f'Procesando {len(chunks)} chunks...')
    all_items = []
    vat_included = False

    for i, chunk in enumerate(chunks):
        result = await _extract_chunk(chunk, partner_name, ollama_url, model)
        all_items.extend(result.get('items', []))
        if i == 0:
            vat_included = result.get('vat_included', False)

    logger.info(f'Total extraído en {len(chunks)} chunks: {len(all_items)} productos')
    result = {'vat_included': vat_included, 'items': all_items}
    result = _enrich_barcodes(result, raw_text)
    return result


async def _extract_chunk(
    raw_text: str,
    partner_name: str,
    ollama_url: str,
    model: str,
) -> dict:
    """Extrae productos de un chunk de texto."""
    prompt = EXTRACTION_PROMPT.format(
        raw_text=raw_text,
        partner_name=partner_name,
    )

    try:
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(
                f'{ollama_url}/api/generate',
                json={
                    'model': model,
                    'prompt': prompt,
                    'stream': False,
                    'options': {
                        'temperature': 0.1,
                        'num_predict': 8192,
                    }
                }
            )
            resp.raise_for_status()
            response_text = resp.json().get('response', '')

        return _parse_json_response(response_text)

    except Exception as e:
        logger.error(f'Error en extracción LLM: {e}')
        return {'vat_included': False, 'items': []}


def _parse_json_response(text: str) -> dict:
    """Extrae y parsea el JSON de la respuesta del LLM."""
    # Intenta parsear directamente
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Busca bloque ```json ... ```
    json_block = re.search(r'```json\s*([\s\S]*?)\s*```', text)
    if json_block:
        try:
            return json.loads(json_block.group(1))
        except json.JSONDecodeError:
            pass

    # Busca el bloque JSON en el texto
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # Último recurso: extrae líneas con formato "nombre|precio"
    logger.warning('No se pudo parsear JSON del LLM, usando fallback regex')
    items = []
    for line in text.split('\n'):
        parts = line.split('|')
        if len(parts) >= 2:
            try:
                price_str = re.sub(r'[^\d.,]', '', parts[-1]).replace(',', '.')
                price = float(price_str)
                items.append({
                    'name': parts[0].strip(),
                    'presentation': None,
                    'price': price,
                    'barcode': None,
                })
            except (ValueError, IndexError):
                continue

    return {'vat_included': False, 'items': items}


def _enrich_barcodes(result: dict, raw_text: str) -> dict:
    """
    Post-procesamiento: busca códigos EAN-13 en el texto crudo y los asocia
    a los ítems que no tienen barcode pero cuyo nombre aparece cerca del código.

    Esto cubre el caso de PDFs tabulares (ej: Pernod Ricard) donde el LLM
    no extrajo el barcode de la columna "Código Botella".

    Estrategia:
    1. Extraer todos los EAN-13 del texto con su posición (char offset)
    2. Para cada ítem sin barcode, buscar si su nombre aparece en el texto
       y si hay un EAN-13 en las mismas N líneas
    """
    items = result.get('items', [])
    if not items:
        return result

    # Busca todos los EAN-13 (13 dígitos consecutivos) en el texto
    # También acepta EAN con cero inicial (14 dígitos con 0 al inicio)
    ean_pattern = re.compile(r'\b(0?\d{13})\b')
    ean_matches = list(ean_pattern.finditer(raw_text))

    if not ean_matches:
        logger.debug('_enrich_barcodes: no se encontraron EAN-13 en el texto')
        return result

    logger.debug(f'_enrich_barcodes: {len(ean_matches)} EAN encontrados en texto crudo')

    # Construir índice de líneas para localización rápida
    lines = raw_text.split('\n')
    # Posición acumulada de inicio de cada línea
    line_starts = []
    acc = 0
    for line in lines:
        line_starts.append(acc)
        acc += len(line) + 1  # +1 por el \n

    def char_to_line(pos: int) -> int:
        """Convierte posición de char a número de línea (0-indexed)."""
        for i in range(len(line_starts) - 1, -1, -1):
            if pos >= line_starts[i]:
                return i
        return 0

    # Mapear EAN → número de línea donde aparece
    ean_by_line: list[tuple[int, str]] = []  # (lineno, ean_digits)
    for m in ean_matches:
        lineno = char_to_line(m.start())
        # Normalizar: quitar cero inicial si tiene 14 dígitos
        ean = m.group(1)
        if len(ean) == 14 and ean.startswith('0'):
            ean = ean[1:]
        ean_by_line.append((lineno, ean))

    # Para cada ítem sin barcode, intentar encontrar EAN cercano
    enriched = 0
    for item in items:
        if item.get('barcode'):
            continue  # ya tiene barcode, no sobreescribir

        name = item.get('name', '').strip()
        if not name or len(name) < 4:
            continue

        # Buscar el nombre del ítem en el texto (case-insensitive, primeras palabras)
        # Usamos las primeras 3 palabras para mayor tolerancia
        name_words = name.lower().split()
        search_term = ' '.join(name_words[:3]) if len(name_words) >= 3 else name.lower()

        pos = raw_text.lower().find(search_term)
        if pos == -1:
            # Intentar con las primeras 2 palabras
            search_term2 = ' '.join(name_words[:2]) if len(name_words) >= 2 else None
            if search_term2:
                pos = raw_text.lower().find(search_term2)

        if pos == -1:
            continue

        name_line = char_to_line(pos)

        # Buscar EAN-13 dentro de ±1 líneas del nombre, priorizando misma línea
        # y, en caso de empate, el EAN físicamente más cercano (preferentemente
        # a la derecha del nombre, que es donde suelen estar los códigos en tablas).
        WINDOW = 1
        best_ean = None
        # score = (line_distance ASC, -char_position DESC)
        # → preferimos misma línea; dentro de misma línea, el EAN más a la
        # derecha (que en tablas suele ser el código de BOTELLA, no de CAJA).
        best_score = (999, 0)
        for ean_line, ean in ean_by_line:
            line_dist = abs(ean_line - name_line)
            if line_dist > WINDOW:
                continue
            ean_pos = raw_text.find(ean, line_starts[ean_line]) if ean_line < len(line_starts) else -1
            if ean_pos == -1:
                ean_pos = raw_text.find('0' + ean, line_starts[ean_line]) if ean_line < len(line_starts) else -1
            # tuple comparison: menor line_dist gana; con igual line_dist gana mayor ean_pos (rightmost)
            score = (line_dist, -ean_pos)
            if score < best_score:
                best_score = score
                best_ean = ean

        if best_ean:
            item['barcode'] = best_ean
            enriched += 1
            logger.debug(
                f'_enrich_barcodes: "{name[:30]}" → barcode={best_ean} '
                f'(line_dist={best_score[0]}, char_dist={best_score[1]})'
            )

    if enriched:
        logger.info(f'_enrich_barcodes: enriquecidos {enriched}/{len(items)} ítems con EAN-13 del texto')

    return result
