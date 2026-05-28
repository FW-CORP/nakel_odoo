#!/bin/bash
# ============================================================
# Descarga los modelos de Ollama necesarios para el servicio
# Ejecutar UNA SOLA VEZ en la VM antes de usar el servicio
# ============================================================

echo "📥 Descargando modelos de Ollama para Nakel AI..."
echo ""

# Modelo principal de extracción (pequeño y rápido, ~2GB)
echo "1/3 qwen2.5:3b — extracción de listas de precios"
ollama pull qwen2.5:3b

echo ""

# Modelo de embeddings (muy liviano, ~274MB)
echo "2/3 nomic-embed-text — matching semántico"
ollama pull nomic-embed-text

echo ""

# Modelo de desambiguación (más grande, ~4.7GB) — OPCIONAL
# Comentar si el servidor no tiene suficiente RAM (necesita ~6GB libres)
echo "3/3 qwen2.5:7b — desambiguación (opcional, ~4.7GB)"
read -p "¿Descargar qwen2.5:7b para desambiguación? (s/N): " resp
if [[ "$resp" =~ ^[Ss]$ ]]; then
    ollama pull qwen2.5:7b
else
    echo "   Saltando. El sistema usará qwen2.5:3b también para desambiguación."
    echo "   Actualizá DISAMBIG_MODEL=qwen2.5:3b en el .env"
fi

echo ""
echo "✅ Modelos listos. Ahora podés ejecutar: bash run.sh"
