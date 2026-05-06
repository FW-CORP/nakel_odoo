#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Uso:
  tools/deploy/deploy_all_master_dev.sh [host] [db]

Ejemplos:
  tools/deploy/deploy_all_master_dev.sh
  tools/deploy/deploy_all_master_dev.sh odoo@10.5.0.41 master_dev
EOF
}

HOST="${1:-odoo@10.5.0.41}"
ODOO_DB="${2:-master_dev}"

if [[ "${HOST}" == "-h" || "${HOST}" == "--help" ]]; then
  usage
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

modules=(
  "nakel_picking"
  "nakel_fix_pick"
  "nakel_wave_picking_link"
  "modulo_rg5329"
)

for m in "${modules[@]}"; do
  echo ""
  echo "=============================="
  echo "Deploy: ${m}"
  echo "=============================="
  "${SCRIPT_DIR}/deploy_addon.sh" "${m}" "${HOST}" "${ODOO_DB}"
done

