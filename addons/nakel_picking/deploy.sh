#!/bin/bash
# Despliegue de nakel_picking al servidor Odoo
# Uso: ./deploy.sh [host]
# Ejemplos:
#   ./deploy.sh               # dev.nakel (default)
#   ./deploy.sh 10.5.0.2      # dev.nakel
#   ./deploy.sh odoo-ct-nakel # prod (si tenés alias SSH)
#
# Nota: ssh -t asigna TTY para que sudo pueda pedir contraseña.
# Para despliegue sin contraseña, configura en el servidor:
#   echo "odoo ALL=(ALL) NOPASSWD: /usr/bin/cp, /usr/bin/chown" | sudo tee /etc/sudoers.d/odoo-deploy

set -e

# Default: DEV (dev.nakel) — IP interna informada: 10.5.0.2
HOST="${1:-odoo@10.5.0.2}"
MODULE_DIR="$(cd "$(dirname "$0")" && pwd)"
REMOTE_ADDONS="/usr/lib/python3/dist-packages/odoo/addons/nakel_picking"

# SSH options: evitar "Too many authentication failures" (usa solo la identidad indicada)
SSH_PORT="${NAKEL_ENV_SSH_PORT:-22}"
SSH_KEY="${NAKEL_ENV_SSH_KEY_PATH:-}"
SSH_OPTS=(-o IdentitiesOnly=yes -p "$SSH_PORT")
if [ -n "$SSH_KEY" ]; then
  SSH_OPTS+=(-i "$SSH_KEY")
fi

echo "📦 Desplegando nakel_picking a $HOST..."
echo "   (rsync incluye models/*.py y reports/*.xml; si solo subís el XML, el PDF fallará o verá lógica vieja.)"
echo ""

# 1. Sincronizar archivos a /tmp en el servidor
echo "1️⃣  Sincronizando archivos..."
rsync -avz --exclude='.git' --exclude='deploy.sh' \
    -e "ssh ${SSH_OPTS[*]}" \
    "$MODULE_DIR/" \
    "$HOST:/tmp/nakel_picking/"

# 2. Copiar a addons (requiere sudo en el servidor)
#    -t asigna TTY para que sudo pueda pedir contraseña si hace falta
echo ""
echo "2️⃣  Copiando a addons de Odoo (puede pedir contraseña sudo)..."
ssh -t "${SSH_OPTS[@]}" "$HOST" "sudo cp -r /tmp/nakel_picking/* $REMOTE_ADDONS/ && sudo chown -R odoo:odoo $REMOTE_ADDONS && echo '✅ Archivos copiados correctamente'"

echo ""
echo "✅ Despliegue completado."
echo ""
echo "Para actualizar el módulo en Odoo:"
echo "  ssh -t ${SSH_OPTS[*]} $HOST \"sudo systemctl stop odoo && sudo -u odoo odoo -c /etc/odoo/odoo.conf -u nakel_picking -d master_18 --stop-after-init && sudo systemctl start odoo\""
echo ""
echo "O desde la interfaz: Aplicaciones → Nakel Picking → Actualizar"
