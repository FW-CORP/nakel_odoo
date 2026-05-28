#!/usr/bin/env bash
# Cron local: mueve cotizaciones «procesar» → Roturas 2 (CEN/NAK + B3).
# Política: demanda completa (--mover-demanda-completa).
#
# Crontab sugerido (dom/mié/vie 22:00):
#   0 22 * * 0,3,5 /media/klap/raid5/cursor_files/nakel/tools/nak-ventas/scripts/run_mover_roturas2_cron.sh
#
# Logs: tools/nak-ventas/logs/mover_roturas2_YYYYMMDD_HHMMSS.log

set -u

NAKEL_ROOT="/media/klap/raid5/cursor_files/nakel"
SCRIPT_DIR="${NAKEL_ROOT}/tools/nak-ventas/scripts"
LOG_DIR="${NAKEL_ROOT}/tools/nak-ventas/logs"
PYTHON="/usr/bin/python3"
SCRIPT="${SCRIPT_DIR}/mover_disponible_pedidos_a_roturas2_master_dev.py"

export NAKEL_CONFIG_ROOT="/media/klap/raid5/cursor_files"
export PATH="/usr/local/bin:/usr/bin:/bin"

mkdir -p "${LOG_DIR}"
TS="$(date +%Y%m%d_%H%M%S)"
LOG="${LOG_DIR}/mover_roturas2_${TS}.log"

exec >>"${LOG}" 2>&1

echo "=== run_mover_roturas2_cron.sh inicio $(date -Is) ==="
echo "LOG=${LOG}"
echo "HOST=$(hostname)"
echo "USER=$(whoami)"

if [[ ! -x "${PYTHON}" ]]; then
  echo "ERROR: no existe ${PYTHON}"
  exit 1
fi
if [[ ! -f "${SCRIPT}" ]]; then
  echo "ERROR: no existe ${SCRIPT}"
  exit 1
fi

run_profile() {
  local label="$1"
  shift
  echo ""
  echo "--- Perfil ${label} $(date -Is) ---"
  echo "CMD: ${PYTHON} ${SCRIPT} $*"
  if "${PYTHON}" "${SCRIPT}" "$@"; then
    echo "OK: perfil ${label}"
    return 0
  fi
  local rc=$?
  echo "ERROR: perfil ${label} exit=${rc}"
  return "${rc}"
}

rc=0

run_profile "CEN/NAK" \
  --apply \
  --mover-demanda-completa \
  || rc=1

run_profile "B3" \
  --apply \
  --mover-demanda-completa \
  --company-nak 1 \
  --company-nakel 1 \
  --warehouse-code B3 \
  --filtrar-warehouse-id 17 \
  || rc=1

echo ""
echo "=== fin $(date -Is) exit=${rc} ==="
exit "${rc}"
