"""
Orquestador del matching de productos.

Estrategia en capas (de más a menos confiable):
  0. Barcode exacto (EAN) → confianza 100, status: auto
  1. Código de proveedor exacto → confianza 100, status: auto
  2. Nombre conocido en mapping memory → confianza 98, status: auto
  2.5 Fuzzy string matching contra subset del partner → auto/review (umbrales relajados)
  2.6 Embeddings contra subset del partner → auto/review (umbrales relajados)
  3. Fuzzy string matching contra catálogo general → auto/review (umbrales estrictos)
  4. Embeddings contra catálogo general → auto/review (umbrales muy estrictos)
  5. Sin match suficiente → status: no_match, top-3 como alternativas

Las capas 2.5/2.6 actúan sobre el "partner_catalog" (productos ya vinculados al
proveedor en Odoo vía product.supplierinfo). Como ese subset es semánticamente
homogéneo (todo bebidas para Pernod, todo snacks para Tunki), los umbrales son
más generosos sin riesgo de falsos positivos del tipo "BEEFEATER → BUTTER CREAM".
"""
import logging
import re
import traceback
from typing import Optional

from rapidfuzz import fuzz

from .embeddings import build_catalog_embeddings, find_best_matches
from .llm_disambiguator import disambiguate_with_llm
from .llm_smart_matcher import smart_match

logger = logging.getLogger(__name__)

# ── Umbrales para matching contra catálogo GENERAL (estrictos) ──
# Subidos para evitar matches basura por semántica genérica
EMBED_AUTO_GENERAL = 0.95
EMBED_REVIEW_GENERAL = 0.85
FUZZY_AUTO_GENERAL = 0.85
FUZZY_REVIEW_GENERAL = 0.65

# ── Umbrales para matching contra subset del PARTNER (relajados) ──
# El subset es chico y temáticamente homogéneo, así que podemos ser más permisivos
EMBED_AUTO_PARTNER = 0.85
EMBED_REVIEW_PARTNER = 0.70
FUZZY_AUTO_PARTNER = 0.75
FUZZY_REVIEW_PARTNER = 0.50

# Compatibilidad hacia atrás
AUTO_THRESHOLD = EMBED_AUTO_GENERAL
REVIEW_THRESHOLD = EMBED_REVIEW_GENERAL
FUZZY_AUTO = FUZZY_AUTO_GENERAL
FUZZY_REVIEW = FUZZY_REVIEW_GENERAL


def _clean_name_for_fuzzy(name: str) -> str:
    """
    Limpia el nombre del producto para comparación fuzzy.
    Elimina:
      - Códigos entre corchetes: [4195.25], [ABC-123]
      - Guiones con números entre guiones: -072-
      - Caracteres especiales excepto letras, números y espacios
      - Espacios múltiples
    Convierte a minúsculas.
    """
    s = name.lower()
    # Eliminar códigos entre corchetes
    s = re.sub(r'\[[^\]]*\]', ' ', s)
    # Eliminar patrones tipo -072- o -ABC-
    s = re.sub(r'-[a-z0-9]{1,6}-', ' ', s)
    # Eliminar caracteres especiales excepto letras/números/espacios
    s = re.sub(r'[^a-z0-9áéíóúüñ\s]', ' ', s)
    # Colapsar espacios
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _is_partner_product(p: dict) -> bool:
    """
    Devuelve True si el producto Odoo está vinculado al proveedor actual.
    Usa cualquiera de los siguientes indicadores:
      - is_known_supplier (flag explícito de Odoo)
      - supplier_product_code (código del proveedor para este producto)
      - supplier_product_name (nombre con que el proveedor lo lista)
      - known_supplier_names (memoria de matches previos para este partner)
    """
    return bool(
        p.get('is_known_supplier')
        or p.get('supplier_product_code')
        or p.get('supplier_product_name')
        or p.get('known_supplier_names')
    )


async def match_products(
    extracted_items: list[dict],
    catalog: list[dict],
    partner_name: str,
    auto_threshold_pct: int = 88,
    ollama_url: str = 'http://localhost:11434',
    embed_model: str = 'nomic-embed-text',
    llm_model: str = 'qwen2.5:7b',
) -> list[dict]:
    """
    Matchea cada ítem extraído con el catálogo de productos de Odoo.

    Args:
        extracted_items: Lista de dicts {'name', 'presentation', 'price'} del proveedor.
        catalog: Lista de productos Odoo con id, name, standard_price, etc.
        partner_name: Nombre del proveedor (para logs y LLM).
        auto_threshold_pct: Umbral de confianza para match automático (0-100). Por
            compatibilidad — los umbrales reales se rigen por las constantes del módulo.
        ollama_url: URL de Ollama.
        embed_model: Modelo de embeddings de Ollama.
        llm_model: Modelo LLM para desambiguación.

    Returns:
        Lista de dicts con el resultado del match para cada ítem.
    """
    if not catalog:
        logger.error('Catálogo vacío — no hay productos para matchear')
        return _no_match_all(extracted_items)

    # ── Split del catálogo: subset del partner vs general ────────────────────
    partner_catalog = [p for p in catalog if _is_partner_product(p)]
    use_partner_subset = len(partner_catalog) >= 5

    logger.info(
        f'Catálogo: {len(catalog)} productos totales, '
        f'{len(partner_catalog)} vinculados a {partner_name}'
        + (' (matching prioritario)' if use_partner_subset else ' — usando catálogo completo')
    )

    # ── Capa 0: índice de barcodes (sobre catálogo COMPLETO) ─────────────────
    barcode_index: dict[str, dict] = {}
    for p in catalog:
        if p.get('barcode'):
            raw = str(p['barcode']).strip()
            barcode_index[raw] = p
            barcode_index[raw.lstrip('0')] = p  # sin ceros a la izquierda

    # ── Capa 1: índice de códigos de proveedor (solo del partner) ────────────
    code_index: dict[str, dict] = {}
    for p in partner_catalog if use_partner_subset else catalog:
        if p.get('supplier_product_code'):
            code_index[p['supplier_product_code'].strip().lower()] = p

    # ── Capa 2: known_supplier_names del partner ─────────────────────────────
    known_name_index: dict[str, dict] = {}
    for p in partner_catalog if use_partner_subset else catalog:
        for known_name in p.get('known_supplier_names', []):
            if known_name:
                known_name_index[known_name.strip().lower()] = p
        if p.get('supplier_product_name'):
            known_name_index[p['supplier_product_name'].strip().lower()] = p

    # ── Capas 2.5/3: catálogos pre-limpiados para fuzzy ──────────────────────
    fuzzy_partner = [
        (_clean_name_for_fuzzy(p['name']), p)
        for p in partner_catalog if p.get('name')
    ]
    fuzzy_general = [
        (_clean_name_for_fuzzy(p['name']), p)
        for p in catalog if p.get('name')
    ]

    # ── Capas 2.6/4: embeddings ──────────────────────────────────────────────
    catalog_embeddings_general: list[list[float]] = []
    catalog_embeddings_partner: list[list[float]] = []
    use_embeddings_general = False
    use_embeddings_partner = False

    try:
        catalog_embeddings_general = await build_catalog_embeddings(
            catalog, ollama_url, embed_model)
        use_embeddings_general = True
    except Exception as e:
        logger.warning(f'Embeddings (catálogo general) falló: {e}')

    if use_partner_subset:
        try:
            catalog_embeddings_partner = await build_catalog_embeddings(
                partner_catalog, ollama_url, embed_model)
            use_embeddings_partner = True
        except Exception as e:
            logger.warning(f'Embeddings (subset partner) falló: {e}')

    # ── Procesa cada ítem ────────────────────────────────────────────────────
    results = []
    for item in extracted_items:
        try:
            result = await _match_single_item(
                item=item,
                catalog=catalog,
                partner_catalog=partner_catalog,
                use_partner_subset=use_partner_subset,
                catalog_embeddings_general=catalog_embeddings_general,
                catalog_embeddings_partner=catalog_embeddings_partner,
                use_embeddings_general=use_embeddings_general,
                use_embeddings_partner=use_embeddings_partner,
                barcode_index=barcode_index,
                code_index=code_index,
                known_name_index=known_name_index,
                fuzzy_partner=fuzzy_partner,
                fuzzy_general=fuzzy_general,
                partner_name=partner_name,
                ollama_url=ollama_url,
                llm_model=llm_model,
            )
        except Exception as e:
            logger.error(
                f'Error matching item "{item.get("name", "?")}": {e}\n'
                + traceback.format_exc()
            )
            result = {
                'supplier_name': item.get('name', ''),
                'presentation': item.get('presentation'),
                'price_with_vat': item.get('price', 0.0),
                'vat_included': True,
                'product_tmpl_id': None,
                'product_name': None,
                'confidence': 0,
                'match_status': 'no_match',
                'notes': f'Error interno al procesar: {e}',
                'alternative_product_ids': [],
            }
        results.append(result)
        logger.info(
            f'  {item["name"][:40]:40s} → '
            f'{result.get("match_status", "?"):10s} '
            f'conf={result.get("confidence", 0):3d}% '
            f'prod={(result.get("product_name") or "—")[:30]}'
        )

    return results


def _fuzzy_best_match(
    clean_supplier: str,
    fuzzy_catalog: list[tuple[str, dict]],
) -> tuple[Optional[dict], float, float]:
    """Devuelve (producto, mejor_score, segundo_score) sobre un catálogo fuzzy."""
    best_score = 0.0
    best_product = None
    second_score = 0.0
    for clean_odoo, prod in fuzzy_catalog:
        if not clean_odoo:
            continue
        score = fuzz.token_sort_ratio(clean_supplier, clean_odoo) / 100.0
        if score > best_score:
            second_score = best_score
            best_score = score
            best_product = prod
        elif score > second_score:
            second_score = score
    return best_product, best_score, second_score


async def _match_single_item(
    item: dict,
    catalog: list[dict],
    partner_catalog: list[dict],
    use_partner_subset: bool,
    catalog_embeddings_general: list[list[float]],
    catalog_embeddings_partner: list[list[float]],
    use_embeddings_general: bool,
    use_embeddings_partner: bool,
    barcode_index: dict,
    code_index: dict,
    known_name_index: dict,
    fuzzy_partner: list[tuple[str, dict]],
    fuzzy_general: list[tuple[str, dict]],
    partner_name: str,
    ollama_url: str,
    llm_model: str,
) -> dict:
    """Proceso de match para un único ítem del proveedor."""
    supplier_name = item.get('name', '').strip()
    presentation = item.get('presentation')
    price = item.get('price', 0.0)
    item_barcode = str(item.get('barcode') or '').strip()

    base_result = {
        'supplier_name': supplier_name,
        'presentation': presentation,
        'price_with_vat': price,
        'vat_included': True,
        'product_tmpl_id': None,
        'product_name': None,
        'confidence': 0,
        'match_status': 'no_match',
        'notes': '',
        'alternative_product_ids': [],
        # Interpretación comercial del LLM (cuántas unidades Odoo hay en el precio
        # del proveedor, y precio normalizado por unidad). Defaults: unit_count=1
        # significa "el precio es por unidad Odoo directamente, sin conversión".
        'unit_count': 1,
        'unit_price': price,
        'price_interpretation': '',
    }

    if not supplier_name:
        return base_result

    # ── Capa 0: barcode exacto ────────────────────────────────────────────────
    if item_barcode and len(item_barcode) >= 8:
        bc_match = barcode_index.get(item_barcode) or barcode_index.get(item_barcode.lstrip('0'))
        if bc_match:
            return {**base_result,
                    'product_tmpl_id': bc_match['id'],
                    'product_name': bc_match['name'],
                    'confidence': 100,
                    'match_status': 'auto',
                    'notes': f'Match exacto por código de barras ({item_barcode})'}

    # ── Capa 1: código de proveedor exacto ───────────────────────────────────
    item_supplier_code = str(item.get('supplier_code') or '').strip().lower()
    if item_supplier_code and item_supplier_code in code_index:
        p = code_index[item_supplier_code]
        return {**base_result,
                'product_tmpl_id': p['id'],
                'product_name': p['name'],
                'confidence': 100,
                'match_status': 'auto',
                'notes': f'Match exacto por código de proveedor ({item_supplier_code})'}

    code_match = re.search(r'\[([^\]]+)\]', supplier_name)
    if code_match:
        code = code_match.group(1).strip().lower()
        if code in code_index:
            p = code_index[code]
            return {**base_result,
                    'product_tmpl_id': p['id'],
                    'product_name': p['name'],
                    'confidence': 100,
                    'match_status': 'auto',
                    'notes': f'Match exacto por código [{code_match.group(1)}]'}

    name_lower = supplier_name.lower()
    if name_lower in code_index:
        p = code_index[name_lower]
        return {**base_result,
                'product_tmpl_id': p['id'],
                'product_name': p['name'],
                'confidence': 100,
                'match_status': 'auto',
                'notes': 'Match exacto por código de proveedor'}

    # ── Capa 2: nombre conocido (mapping memory) ─────────────────────────────
    if name_lower in known_name_index:
        p = known_name_index[name_lower]
        return {**base_result,
                'product_tmpl_id': p['id'],
                'product_name': p['name'],
                'confidence': 98,
                'match_status': 'auto',
                'notes': 'Match por memoria de matches previos'}

    for known, p in known_name_index.items():
        if name_lower in known or known in name_lower:
            if len(name_lower) > 4 and len(known) > 4:
                return {**base_result,
                        'product_tmpl_id': p['id'],
                        'product_name': p['name'],
                        'confidence': 90,
                        'match_status': 'auto',
                        'notes': f'Match parcial por nombre conocido: {known}'}

    # ─────────────────────────────────────────────────────────────────────────
    # PASADA 1: contra el subset del proveedor (umbrales relajados)
    # ─────────────────────────────────────────────────────────────────────────
    clean_supplier = _clean_name_for_fuzzy(supplier_name)

    if use_partner_subset and clean_supplier and fuzzy_partner:
        best_p, score_p, second_p = _fuzzy_best_match(clean_supplier, fuzzy_partner)

        # 1. Fuzzy muy fuerte (>=0.85) → auto directo, sin necesidad de LLM
        if best_p and score_p >= FUZZY_AUTO_GENERAL:
            conf = round(score_p * 100)
            return {**base_result,
                    'product_tmpl_id': best_p['id'],
                    'product_name': best_p['name'],
                    'confidence': conf,
                    'match_status': 'auto',
                    'notes': f'Match fuzzy fuerte en subset {partner_name} ({conf}%)'}

        # 2. Pre-filtrar candidatos con embedding + fuzzy y mandárselos al LLM
        #    para que razone sobre marca, presentación y variante.
        embed_top = []
        if use_embeddings_partner and catalog_embeddings_partner:
            embed_top = await find_best_matches(
                supplier_name=supplier_name,
                catalog=partner_catalog,
                catalog_embeddings=catalog_embeddings_partner,
                ollama_url=ollama_url,
                embed_model='nomic-embed-text',
                top_k=10,
            )

        # Combinar top fuzzy + top embedding (deduplicar por id)
        candidate_pool: dict[int, dict] = {}
        # Top 10 por fuzzy
        fuzzy_scored = []
        for clean_odoo, prod in fuzzy_partner:
            if not clean_odoo:
                continue
            s = fuzz.token_sort_ratio(clean_supplier, clean_odoo) / 100.0
            fuzzy_scored.append((s, prod))
        fuzzy_scored.sort(key=lambda x: x[0], reverse=True)
        for s, prod in fuzzy_scored[:10]:
            if prod.get('id') and prod['id'] not in candidate_pool:
                candidate_pool[prod['id']] = prod
        for m in embed_top:
            p = m.get('product')
            if p and p.get('id') and p['id'] not in candidate_pool:
                candidate_pool[p['id']] = p

        candidates_for_llm = list(candidate_pool.values())[:15]

        if not candidates_for_llm:
            return {**base_result,
                    'match_status': 'no_match',
                    'notes': f'Sin candidatos en subset {partner_name}'}

        # 3. LLM razona y elige (o dice no_match con justificación)
        llm_result = await smart_match(
            supplier_name=supplier_name,
            presentation=presentation,
            category=item.get('category'),
            price=price,
            partner_name=partner_name,
            candidates=candidates_for_llm,
            ollama_url=ollama_url,
            model=llm_model,
        )

        if llm_result is None:
            # LLM falló, fallback a la lógica fuzzy/embedding anterior
            logger.debug(f'smart_match falló para "{supplier_name}", usando fallback fuzzy')
            if best_p and score_p >= FUZZY_REVIEW_PARTNER:
                conf = round(score_p * 100)
                return {**base_result,
                        'product_tmpl_id': best_p['id'],
                        'product_name': best_p['name'],
                        'confidence': conf,
                        'match_status': 'review',
                        'notes': f'Match fuzzy fallback ({conf}%) — revisar (LLM no disponible)'}
            return {**base_result,
                    'match_status': 'no_match',
                    'notes': 'LLM no disponible y fuzzy insuficiente'}

        # 4. Interpretar respuesta del LLM (incluyendo unit_count / unit_price)
        llm_conf = llm_result['confidence']
        reasoning = llm_result['reasoning']
        unit_count = llm_result.get('unit_count', 1) or 1
        unit_price = llm_result.get('unit_price')
        price_interp = llm_result.get('price_interpretation', '')
        alternatives = [p['id'] for p in candidates_for_llm[1:4] if p.get('id')]

        # Construir notes incluyendo interpretación comercial cuando aplica
        notes_parts = [f'LLM ({llm_conf}%): {reasoning[:120]}']
        if price_interp and unit_count > 1:
            notes_parts.append(f' | {price_interp[:120]}')
        notes_str = ''.join(notes_parts)

        if llm_result.get('no_match') or not llm_result.get('product'):
            return {**base_result,
                    'confidence': llm_conf,
                    'match_status': 'no_match',
                    'notes': f'LLM: {reasoning[:120]}',
                    'unit_count': 1,
                    'unit_price': None,
                    'price_interpretation': '',
                    'alternative_product_ids': alternatives}

        chosen = llm_result['product']
        # Decisión auto/review según confianza del LLM
        # Auto requiere 90+ (era 85 — los matches con dudas tipo "aunque..." al 85
        # solían ser falsos positivos). Review baja a 60+ (más permisivo porque
        # la sugerencia llega con razonamiento explicito que el usuario puede leer).
        if llm_conf >= 90:
            status = 'auto'
        elif llm_conf >= 60:
            status = 'review'
        else:
            # Confianza muy baja: tratar como no_match con sugerencia
            return {**base_result,
                    'confidence': llm_conf,
                    'match_status': 'no_match',
                    'notes': f'LLM baja confianza: {reasoning[:80]}',
                    'unit_count': 1,
                    'unit_price': None,
                    'price_interpretation': '',
                    'alternative_product_ids': [chosen.get('id')] + alternatives[:2]}

        return {**base_result,
                'product_tmpl_id': chosen['id'],
                'product_name': chosen['name'],
                'confidence': llm_conf,
                'match_status': status,
                'notes': notes_str,
                'unit_count': unit_count,
                'unit_price': unit_price,
                'price_interpretation': price_interp,
                'alternative_product_ids': alternatives}

    # ─────────────────────────────────────────────────────────────────────────
    # PASADA 2: contra el catálogo GENERAL (umbrales estrictos)
    # Solo se usa si no hay subset del partner (proveedor nuevo o sin
    # supplierinfo cargada en Odoo). Para proveedores conocidos, el embedding
    # general es demasiado ruidoso.
    # ─────────────────────────────────────────────────────────────────────────
    if clean_supplier and fuzzy_general:
        best_g, score_g, _ = _fuzzy_best_match(clean_supplier, fuzzy_general)
        if best_g and score_g >= FUZZY_AUTO_GENERAL:
            conf = round(score_g * 100)
            return {**base_result,
                    'product_tmpl_id': best_g['id'],
                    'product_name': best_g['name'],
                    'confidence': conf,
                    'match_status': 'auto',
                    'notes': f'Match fuzzy en catálogo general ({conf}%)'}

    if use_embeddings_general and catalog_embeddings_general:
        top_matches = await find_best_matches(
            supplier_name=supplier_name,
            catalog=catalog,
            catalog_embeddings=catalog_embeddings_general,
            ollama_url=ollama_url,
            embed_model='nomic-embed-text',
            top_k=5,
        )

        if top_matches:
            best = top_matches[0]
            best_sim = best['similarity']
            best_pct = best['score_pct']

            if best_sim >= EMBED_AUTO_GENERAL:
                # Confianza alta + posible ambigüedad → LLM
                second_best_sim = top_matches[1]['similarity'] if len(top_matches) > 1 else 0
                if best_sim - second_best_sim < 0.05 and best_sim < 0.97:
                    candidates = [m['product'] for m in top_matches[:3]]
                    llm_result = await disambiguate_with_llm(
                        supplier_name=supplier_name,
                        candidates=candidates,
                        ollama_url=ollama_url,
                        model=llm_model,
                    )
                    if llm_result:
                        confidence = min(95, best_pct)
                        return {**base_result,
                                'product_tmpl_id': llm_result['id'],
                                'product_name': llm_result['name'],
                                'confidence': confidence,
                                'match_status': 'auto' if confidence >= EMBED_AUTO_GENERAL * 100 else 'review',
                                'notes': f'Match embedding general ({best_pct}%) + LLM',
                                'alternative_product_ids': [
                                    m['product']['id'] for m in top_matches[1:3] if m.get('product')
                                ]}

                return {**base_result,
                        'product_tmpl_id': best['product']['id'],
                        'product_name': best['product']['name'],
                        'confidence': best_pct,
                        'match_status': 'auto',
                        'notes': f'Match embedding general alta confianza ({best_pct}%)',
                        'alternative_product_ids': [
                            m['product']['id'] for m in top_matches[1:3] if m.get('product')
                        ]}

            elif best_sim >= EMBED_REVIEW_GENERAL:
                return {**base_result,
                        'product_tmpl_id': best['product']['id'],
                        'product_name': best['product']['name'],
                        'confidence': best_pct,
                        'match_status': 'review',
                        'notes': f'Match embedding general media ({best_pct}%) — revisar',
                        'alternative_product_ids': [
                            m['product']['id'] for m in top_matches[1:3] if m.get('product')
                        ]}

            # No alcanza umbrales: devolver top-3 como alternativas
            return {**base_result,
                    'confidence': best_pct,
                    'match_status': 'no_match',
                    'notes': f'Sin match (mejor candidato: {best["product"]["name"][:40]}, {best_pct}%)',
                    'alternative_product_ids': [m['product']['id'] for m in top_matches[:3]]}

    # Fuzzy general dio score bajo y embeddings no disponibles
    return base_result


def _no_match_all(items: list[dict]) -> list[dict]:
    """Devuelve todos los ítems como no_match."""
    return [
        {
            'supplier_name': item.get('name', ''),
            'presentation': item.get('presentation'),
            'price_with_vat': item.get('price', 0.0),
            'vat_included': True,
            'product_tmpl_id': None,
            'product_name': None,
            'confidence': 0,
            'match_status': 'no_match',
            'notes': 'Catálogo vacío o error en embeddings',
            'alternative_product_ids': [],
        }
        for item in items
    ]
