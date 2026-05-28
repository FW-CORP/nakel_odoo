#!/bin/bash
# ============================================================
# Deploy del servicio IA a la VM (ajustar VM_HOST a tu entorno)
# Ejecutar desde Windows Git Bash o WSL
# ============================================================

VM_HOST="${VM_HOST:-aiadmin@192.168.1.10}"
VM_KEY="${VM_KEY:-$HOME/.ssh/id_rsa_aiservice}"
VM_PATH="/home/aiadmin/nakel_ai_service"

echo "🚀 Deploying Nakel AI Service a $VM_HOST..."

# Crea directorio en VM
ssh -i "$VM_KEY" "$VM_HOST" "mkdir -p $VM_PATH"

# Copia archivos
rsync -avz --exclude='venv' --exclude='__pycache__' --exclude='*.pyc' \
    -e "ssh -i $VM_KEY" \
    . "$VM_HOST:$VM_PATH/"

echo "✅ Archivos copiados."

# Instala dependencias y configura
ssh -i "$VM_KEY" "$VM_HOST" << 'REMOTE'
cd /home/aiadmin/nakel_ai_service

# Entorno virtual
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

# .env inicial si no existe
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "⚠️  .env creado desde .env.example — revisar configuración"
fi

echo "✅ Dependencias instaladas."
REMOTE

echo ""
echo "📋 Próximos pasos en la VM:"
echo "   1. Conectarse: ssh -i \"$VM_KEY\" \"$VM_HOST\""
echo "   2. Descargar modelos: cd ~/nakel_ai_service && bash install_models.sh"
echo "   3. Configurar: nano ~/nakel_ai_service/.env"
echo "   4. Iniciar: bash run.sh"
echo ""
echo "   O instalar como servicio systemd:"
echo "   sudo cp ~/nakel_ai_service/nakel-ai.service /etc/systemd/system/"
echo "   sudo systemctl enable nakel-ai --now"
