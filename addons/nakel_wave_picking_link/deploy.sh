#!/bin/bash
# Despliegue de nakel_wave_picking_link al servidor Odoo
#
# Uso:
#   ./deploy.sh [host] [db]
#
# Ejemplos:
#   ./deploy.sh odoo@10.5.0.41 master_dev
#   ./deploy.sh odoo-ct-nakel master_dev
#   ./deploy.sh odoo@10.5.0.2 master_test
#
# Variables opcionales:
#   NAKEL_ENV_SSH_PORT   (default 22)
#   NAKEL_ENV_SSH_KEY_PATH (si necesitás forzar una key concreta)
#
# Nota: ssh -t asigna TTY para que sudo pueda pedir contraseña.
# Para despliegue sin contraseña, configura en el servidor (ejemplo):
#   echo "odoo ALL=(ALL) NOPASSWD: /usr/bin/cp, /usr/bin/chown" | sudo tee /etc/sudoers.d/odoo-deploy

set -euo pipefail

# Defaults:
# - PROD CT informado por infra: 10.5.0.41 (usuario típico: odoo)
# - DB: NO asumimos prod; default master_dev salvo que lo pases explícito
HOST="${1:-odoo@10.5.0.41}"
ODOO_DB="${2:-master_dev}"

MODULE_DIR="$(cd "$(dirname "$0")" && pwd)"
MODULE_NAME="nakel_wave_picking_link"
REMOTE_TMP="/tmp/${MODULE_NAME}"
REMOTE_ADDONS="/opt/odoo/custom-addons/${MODULE_NAME}"

# SSH options: evitar "Too many authentication failures" (usa solo la identidad indicada)
SSH_PORT="${NAKEL_ENV_SSH_PORT:-22}"
SSH_KEY="${NAKEL_ENV_SSH_KEY_PATH:-}"
SSH_OPTS=(-o IdentitiesOnly=yes -p "$SSH_PORT")
if [ -n "$SSH_KEY" ]; then
  SSH_OPTS+=(-i "$SSH_KEY")
fi

echo "📦 Desplegando ${MODULE_NAME} a ${HOST}..."
echo "   Destino remoto (addons): ${REMOTE_ADDONS}"
echo "   Staging remoto (tmp):    ${REMOTE_TMP}/"
echo "   DB sugerida para -u:     ${ODOO_DB}"
echo ""

echo "1️⃣  Sincronizando archivos a ${REMOTE_TMP}/ ..."
rsync -avz --exclude='.git' --exclude='deploy.sh' \
  -e "ssh ${SSH_OPTS[*]}" \
  "${MODULE_DIR}/" \
  "${HOST}:${REMOTE_TMP}/"

echo ""
echo "2️⃣  Copiando a addons de Odoo (puede pedir contraseña sudo)..."
ssh -t "${SSH_OPTS[@]}" "$HOST" "sudo mkdir -p '${REMOTE_ADDONS}' && sudo cp -r '${REMOTE_TMP}'/* '${REMOTE_ADDONS}/' && sudo chown -R odoo:odoo '${REMOTE_ADDONS}' && echo '✅ Archivos copiados correctamente'"

echo ""
echo "✅ Despliegue completado."
echo ""
echo "Para actualizar el módulo en Odoo (ajustá la DB si corresponde):"
echo "  ssh -t ${SSH_OPTS[*]} ${HOST} \"sudo systemctl stop odoo && sudo -u odoo odoo -c /etc/odoo/odoo.conf -u ${MODULE_NAME} -d ${ODOO_DB} --stop-after-init && sudo systemctl start odoo\""
echo ""
echo "O desde la interfaz: Aplicaciones → actualizar lista → buscar '${MODULE_NAME}' → Actualizar/Instalar"
