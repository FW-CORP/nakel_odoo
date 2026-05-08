#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Uso:
  tools/deploy/deploy_addon.sh <module_name> [host] [db]

Ejemplos:
  tools/deploy/deploy_addon.sh nakel_picking
  tools/deploy/deploy_addon.sh nakel_picking odoo@10.5.0.41 master_dev

Variables (opcional):
  NAKEL_ENV_SSH_PORT        (default 22)
  NAKEL_ENV_SSH_KEY_PATH    (si necesitás forzar una key concreta)
  NAKEL_REMOTE_ADDONS_ROOT  (default /opt/odoo/custom-addons)
  NAKEL_REMOTE_TMP_ROOT     (default /tmp)
  NAKEL_ODOO_SERVICE        (default odoo)
  NAKEL_ODOO_BIN            (default odoo)
  NAKEL_ODOO_CONF           (default /etc/odoo/odoo.conf)

Notas:
  - Este script copia el módulo a un staging remoto y luego lo espeja a addons con sudo (rsync --delete).
  - Por defecto NO ejecuta -u. Para actualizar el módulo, usar el comando sugerido al final.
EOF
}

MODULE_NAME="${1:-}"
HOST="${2:-odoo@10.5.0.41}"
ODOO_DB="${3:-master_dev}"

if [[ -z "${MODULE_NAME}" || "${MODULE_NAME}" == "-h" || "${MODULE_NAME}" == "--help" ]]; then
  usage
  exit 0
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MODULE_DIR="${REPO_ROOT}/addons/${MODULE_NAME}"

if [[ ! -d "${MODULE_DIR}" ]]; then
  echo "ERROR: no existe el módulo '${MODULE_NAME}' en ${MODULE_DIR}" >&2
  exit 1
fi

SSH_PORT="${NAKEL_ENV_SSH_PORT:-22}"
SSH_KEY="${NAKEL_ENV_SSH_KEY_PATH:-}"
SSH_OPTS=(-o IdentitiesOnly=yes -p "${SSH_PORT}")
if [[ -n "${SSH_KEY}" ]]; then
  SSH_OPTS+=(-i "${SSH_KEY}")
fi

REMOTE_ADDONS_ROOT="${NAKEL_REMOTE_ADDONS_ROOT:-/opt/odoo/custom-addons}"
REMOTE_TMP_ROOT="${NAKEL_REMOTE_TMP_ROOT:-/tmp}"
REMOTE_TMP="${REMOTE_TMP_ROOT}/nakel_odoo_${MODULE_NAME}"
REMOTE_ADDONS="${REMOTE_ADDONS_ROOT}/${MODULE_NAME}"

ODOO_SERVICE="${NAKEL_ODOO_SERVICE:-odoo}"
ODOO_BIN="${NAKEL_ODOO_BIN:-odoo}"
ODOO_CONF="${NAKEL_ODOO_CONF:-/etc/odoo/odoo.conf}"

echo "📦 Deploy módulo: ${MODULE_NAME}"
echo "   Origen local:  ${MODULE_DIR}"
echo "   Host:          ${HOST}"
echo "   DB sugerida:   ${ODOO_DB}"
echo "   Staging remoto:${REMOTE_TMP}"
echo "   Addons remoto: ${REMOTE_ADDONS}"
echo ""

echo "1️⃣  Sincronizando a staging remoto..."
rsync -avz --delete \
  --exclude='.git' \
  --exclude='__pycache__' \
  -e "ssh ${SSH_OPTS[*]}" \
  "${MODULE_DIR}/" \
  "${HOST}:${REMOTE_TMP}/"

echo ""
echo "2️⃣  Sincronizando a addons (sudo, espejo con --delete)..."
# Importante: `cp -r staging/* dest/` NO borra archivos viejos en destino y puede dejar mezcla
# de versiones (p.ej. `models/sale_order.py` viejo + `views/*.xml` nuevo → error de vista al validar botones object).
ssh -t "${SSH_OPTS[@]}" "${HOST}" \
  "sudo mkdir -p '${REMOTE_ADDONS}' && sudo rsync -a --delete '${REMOTE_TMP}/' '${REMOTE_ADDONS}/' && sudo chown -R odoo:odoo '${REMOTE_ADDONS}' && echo '✅ Copiado OK'"

echo ""
echo "✅ Deploy completado."
echo ""
echo "Para actualizar el módulo en Odoo:"
echo "  ssh -t ${SSH_OPTS[*]} ${HOST} \"sudo systemctl stop ${ODOO_SERVICE} && sudo -u odoo ${ODOO_BIN} -c ${ODOO_CONF} -u ${MODULE_NAME} -d ${ODOO_DB} --stop-after-init && sudo systemctl start ${ODOO_SERVICE}\""

