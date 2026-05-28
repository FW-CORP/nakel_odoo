"""
Parser de imágenes (JPG/PNG) usando el modelo de visión de Ollama.
Convierte la imagen en texto de lista de precios.
"""
import base64
import logging
import httpx

logger = logging.getLogger(__name__)


async def extract_text_from_image(
    file_bytes: bytes,
    ollama_url: str = 'http://localhost:11434',
    vision_model: str = 'llama3.2-vision',
) -> str:
    """
    Envía la imagen a Ollama (modelo de visión) y pide que extraiga
    la lista de precios en formato texto estructurado.
    """
    image_b64 = base64.b64encode(file_bytes).decode('utf-8')
    prompt = (
        'Sos un asistente que extrae listas de precios de imágenes. '
        'Analizá esta imagen y extraé TODOS los productos con sus precios. '
        'Formato de salida: una línea por producto, con el nombre del producto '
        'y el precio separados por "|". Ejemplo: "Silla gaming X300|15000". '
        'Si el precio tiene IVA incluido indicalo al final con "(c/IVA)". '
        'Solo dame los datos, sin explicaciones adicionales.'
    )

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f'{ollama_url}/api/generate',
            json={
                'model': vision_model,
                'prompt': prompt,
                'images': [image_b64],
                'stream': False,
            }
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get('response', '')


async def extract_text_from_image_b64(
    file_b64: str,
    ollama_url: str = 'http://localhost:11434',
    vision_model: str = 'llama3.2-vision',
) -> str:
    """Wrapper que acepta base64 directamente."""
    file_bytes = base64.b64decode(file_b64)
    return await extract_text_from_image(file_bytes, ollama_url, vision_model)
