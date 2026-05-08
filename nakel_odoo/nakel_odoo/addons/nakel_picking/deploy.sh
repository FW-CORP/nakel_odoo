#!/usr/bin/env bash
set -euo pipefail

# Wrapper legacy: mantenido para no romper hábitos.
# Preferir: tools/deploy/deploy_addon.sh nakel_picking [host] [db]

HOST="${1:-odoo@10.5.0.41}"
ODOO_DB="${2:-master_dev}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
"${REPO_ROOT}/tools/deploy/deploy_addon.sh" "nakel_picking" "${HOST}" "${ODOO_DB}"
