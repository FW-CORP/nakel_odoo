"""
LLM Disambiguator: cuando el embedding da varios candidatos con similitud parecida,
usa un modelo LLM (más grande/inteligente) para elegir el correcto.
"""
import json
import logging
import re
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

DISAMBIGUATE_PROMPT = """Sos un experto en productos para distribuidoras en Argentina.

Un proveedor llama a un producto: "{supplier_name}"

Los candidatos en el catálogo son:
{candidates_list}

¿Cuál es el candidato más probable que corresponda al producto del proveedor?
Considerá sinónimos, presentaciones distintas y terminología del sector.

Respondé SOLO con el número del candidato (1, 2, 3...) seguido de una breve explicación.
Ejemplo: "2 - Es el mismo producto pero con diferente nombre comercial"
Si ninguno corresponde, respondé "0 - Ninguno coincide"."""


async def disambiguate_with_llm(
    supplier_name: str,
    candidates: list[dict],
    ollama_url: str = 'http://localhost:11434',
    model: str = 'qwen2.5:7b',
) -> Optional[dict]:
    """
    Usa el LLM para elegir el mejor candidato cuando hay ambigüedad.

    Returns:
        El dict del producto seleccionado, o None si ninguno corresponde.
    """
    if not candidates:
        return None

    candidates_list = '\n'.join(
        f'{i+1}. [{p["id"]}] {p["name"]} (categoría: {p.get("categ_name", "?")})'
        for i, p in enumerate(candidates)
    )

    prompt = DISAMBIGUATE_PROMPT.format(
        supplier_name=supplier_name,
        candidates_list=candidates_list,
    )

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f'{ollama_url}/api/generate',
                json={
                    'model': model,
                    'prompt': prompt,
                    'stream': False,
                    'options': {'temperature': 0.1, 'num_predict': 100},
                }
            )
            resp.raise_for_status()
            response_text = resp.json().get('response', '').strip()

        # Extrae el número elegido
        match = re.match(r'^(\d+)', response_text)
        if not match:
            return None

        choice = int(match.group(1))
        if choice == 0 or choice > len(candidates):
            return None

        chosen = candidates[choice - 1]
        logger.debug(
            f'LLM eligió candidato {choice} para "{supplier_name}": {chosen["name"]}'
        )
        return chosen

    except Exception as e:
        logger.warning(f'Error en LLM disambiguator: {e}')
        return None
