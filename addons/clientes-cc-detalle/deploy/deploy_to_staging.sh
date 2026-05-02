#!/usr/bin/env bash
# Deploy del módulo clientes_cc_detalle → staging (10.5.0.40).
# Requiere: rsync, acceso SSH como odoo@10.5.0.40 (clave o agente).
#
# Uso:
#   ./deploy_to_staging.sh              # sincroniza
#   ./deploy_to_staging.sh --dry-run    # solo muestra qué haría
#
# Variables opcionales:
#   STAGE_HOST=10.5.0.40 STAGE_USER=odoo REMOTE_BASE=/opt/odoo/custom-addons ./deploy_to_staging.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ADDON_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MODULE_DIR="${ADDON_ROOT}/clientes_cc_detalle"

STAGE_HOST="${STAGE_HOST:-10.5.0.40}"
STAGE_USER="${STAGE_USER:-odoo}"
REMOTE_BASE="${REMOTE_BASE:-/opt/odoo/custom-addons}"
MODULE_NAME="${MODULE_NAME:-clientes_cc_detalle}"

REMOTE_TARGET="${STAGE_USER}@${STAGE_HOST}:${REMOTE_BASE}/${MODULE_NAME}/"

if [[ ! -d "${MODULE_DIR}" ]]; then
  echo "Error: no existe el módulo local: ${MODULE_DIR}" >&2
  exit 1
fi

RSYNC_OPTS=(
  -avz
  --delete
  --exclude '__pycache__'
  --exclude '*.pyc'
  --exclude '.git'
)

if [[ "${1:-}" == "--dry-run" ]]; then
  RSYNC_OPTS+=(-n)
  echo "Modo dry-run (no se copia nada)."
fi

echo "Origen:  ${MODULE_DIR}/"
echo "Destino: ${REMOTE_TARGET}"
rsync "${RSYNC_OPTS[@]}" "${MODULE_DIR}/" "${REMOTE_TARGET}"

echo
echo "Listo. En staging:"
echo "  1) Aplicaciones → actualizar lista → actualizar módulo «Nakel - CC por vendedor (Contacto)»."
echo "  2) Asignar grupo: Ajustes → Usuarios → [usuario] → Derechos de acceso:"
echo "     categoría «Nakel — Cuenta corriente (contacto)» → «Nakel: ver CC cliente (mis ventas)»."
echo "     (XML ID técnico: clientes_cc_detalle.group_cc_my_sales)"
echo "  3) Si el grupo no aparece: el módulo no está instalado o falló la carga del XML."
