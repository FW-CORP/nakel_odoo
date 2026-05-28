#!/bin/bash
# ============================================================
# Nakel AI Supplier Pricelist Service — Script de arranque
# Ejecutar en la VM: bash run.sh
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Verificaciones previas ────────────────────────────────────────────────────

echo "🔍 Verificando dependencias..."

# Python 3.10+
if ! command -v python3 &>/dev/null; then
    echo "❌ Python3 no encontrado. Instalá con: sudo apt install python3 python3-pip python3-venv"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "   Python $PYTHON_VERSION ✓"

# Ollama corriendo
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "⚠️  Ollama no está corriendo. Intentando iniciar..."
    if command -v ollama &>/dev/null; then
        ollama serve &
        sleep 3
    else
        echo "❌ Ollama no instalado. Ver: https://ollama.ai"
        echo "   Después: ollama pull qwen2.5:3b && ollama pull nomic-embed-text"
        exit 1
    fi
fi

echo "   Ollama ✓"

# Verifica modelos requeridos
check_model() {
    local model=$1
    if ollama list 2>/dev/null | grep -q "$model"; then
        echo "   Modelo $model ✓"
    else
        echo "⚠️  Modelo $model no encontrado. Descargando..."
        ollama pull "$model"
    fi
}

check_model "qwen2.5:3b"
check_model "nomic-embed-text"
# check_model "qwen2.5:7b"    # Descomentar si se usa desambiguación LLM
# check_model "llama3.2-vision"  # Descomentar si se procesan imágenes

# ── Entorno virtual Python ────────────────────────────────────────────────────

if [ ! -d "venv" ]; then
    echo "📦 Creando entorno virtual..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "📦 Instalando/actualizando dependencias..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# ── Variables de entorno ──────────────────────────────────────────────────────

if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
    echo "   Variables cargadas desde .env ✓"
else
    echo "   (usando valores por defecto — creá .env desde .env.example para personalizar)"
fi

PORT=${PORT:-8001}

# ── Arranque ─────────────────────────────────────────────────────────────────

echo ""
echo "🚀 Iniciando Nakel AI Service en puerto $PORT..."
echo "   Documentación: http://localhost:$PORT/docs"
echo "   Health check:  http://localhost:$PORT/api/health"
echo ""

uvicorn main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --log-level info \
    --reload
