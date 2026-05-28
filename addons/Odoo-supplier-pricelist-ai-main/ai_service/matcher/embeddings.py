"""
Embedding-based product matcher usando Ollama (nomic-embed-text).
Calcula la similitud coseno entre el nombre del producto del proveedor
y todos los productos del catálogo de Odoo.
"""
import logging
import math
import re
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

# Patrón para limpiar códigos internos de Odoo en nombres de producto
# Ej: "WHISKY CHIVAS REGAL 12 AÑOS X700ML.-931-" → "WHISKY CHIVAS REGAL 12 AÑOS X700ML."
_INTERNAL_CODE_RE = re.compile(r'\s*-\s*\d+\s*-\s*$')


def _clean_product_name(name: str) -> str:
    """Elimina códigos internos del final del nombre para mejorar los embeddings."""
    return _INTERNAL_CODE_RE.sub('', name).strip()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Similitud coseno entre dos vectores."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def get_embedding(
    text: str,
    ollama_url: str = 'http://localhost:11434',
    model: str = 'nomic-embed-text',
) -> list[float]:
    """Obtiene el embedding de un texto via Ollama."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f'{ollama_url}/api/embeddings',
            json={'model': model, 'prompt': text}
        )
        resp.raise_for_status()
        return resp.json()['embedding']


async def get_embeddings_batch(
    texts: list[str],
    ollama_url: str = 'http://localhost:11434',
    model: str = 'nomic-embed-text',
    chunk_size: int = 100,
) -> list[list[float]]:
    """
    Obtiene embeddings para una lista de textos usando el endpoint batch /api/embed.
    Procesa de a `chunk_size` textos por request para no sobrecargar Ollama.
    """
    all_embeddings: list[list[float]] = []
    async with httpx.AsyncClient(timeout=120) as client:
        for i in range(0, len(texts), chunk_size):
            chunk = texts[i:i + chunk_size]
            resp = await client.post(
                f'{ollama_url}/api/embed',
                json={'model': model, 'input': chunk}
            )
            resp.raise_for_status()
            data = resp.json()
            # /api/embed devuelve {"embeddings": [[...], [...]]}
            all_embeddings.extend(data['embeddings'])
    return all_embeddings


async def find_best_matches(
    supplier_name: str,
    catalog: list[dict],
    catalog_embeddings: list[list[float]],
    ollama_url: str = 'http://localhost:11434',
    embed_model: str = 'nomic-embed-text',
    top_k: int = 5,
) -> list[dict]:
    """
    Encuentra los top_k productos del catálogo más similares al nombre del proveedor.

    Returns:
        Lista de dicts con {product, similarity} ordenados por similitud descendente.
    """
    # Embedding del nombre del proveedor
    query_emb = await get_embedding(supplier_name, ollama_url, embed_model)

    # Calcula similitud con todos los productos
    scores = []
    for i, prod_emb in enumerate(catalog_embeddings):
        sim = _cosine_similarity(query_emb, prod_emb)
        scores.append((i, sim))

    # Ordena por similitud descendente
    scores.sort(key=lambda x: x[1], reverse=True)

    # Devuelve top_k
    results = []
    for idx, sim in scores[:top_k]:
        results.append({
            'product': catalog[idx],
            'similarity': sim,
            'score_pct': round(sim * 100),
        })
    return results


async def build_catalog_embeddings(
    catalog: list[dict],
    ollama_url: str = 'http://localhost:11434',
    embed_model: str = 'nomic-embed-text',
) -> list[list[float]]:
    """
    Genera embeddings para todos los productos del catálogo.
    El texto a embedear combina nombre limpio + categoría para mejor discriminación.
    Se eliminan los códigos internos del final del nombre (ej: -931-).
    """
    texts = []
    for p in catalog:
        # Limpia el nombre quitando código interno al final
        name = _clean_product_name(p['name'])

        # Combina con categoría
        if p.get('categ_name'):
            text = f"{name} ({p['categ_name']})"
        else:
            text = name

        # Si hay nombre de proveedor conocido, también lo incluye
        if p.get('supplier_product_name'):
            text = f"{text} | {p['supplier_product_name']}"

        texts.append(text)

    logger.info(f'Generando embeddings para {len(texts)} productos del catálogo...')
    embeddings = await get_embeddings_batch(texts, ollama_url, embed_model)
    logger.info('Embeddings generados.')
    return embeddings
