#!/usr/bin/env bash
# Backup WAVE/00156 cada 15 minutos durante 3 horas.
# Log: backups/scheduled_3h_<fecha_inicio>.log
set -euo pipefail

ROOT=/media/klap/raid5/cursor_files/nakel
DIR="$ROOT/Prod-Incidencias/wave156"
BACKUPS="$DIR/backups"
INTERVAL_SEC=$((15 * 60))
DURATION_SEC=$((3 * 60 * 60))
RUNS=$((DURATION_SEC / INTERVAL_SEC + 1))  # 13 corridas (0..180 min)

cd "$DIR"
START_TS=$(date +%Y%m%d_%H%M%S)
LOG="$BACKUPS/scheduled_3h_${START_TS}.log"

mkdir -p "$BACKUPS"
{
  echo "=== Inicio programación backup WAVE/00156 ==="
  echo "Inicio: $(date -Iseconds)"
  echo "Intervalo: 15 min | Duración: 3 h | Corridas planificadas: $RUNS"
  echo "PID: $$"
  echo ""
} >>"$LOG"

for ((i = 1; i <= RUNS; i++)); do
  {
    echo "----------------------------------------"
    echo "Corrida $i/$RUNS — $(date -Iseconds)"
    echo "----------------------------------------"
  } >>"$LOG"
  if ./run_backup.sh >>"$LOG" 2>&1; then
    echo "OK corrida $i" >>"$LOG"
  else
    echo "ERROR corrida $i (exit $?)" >>"$LOG"
  fi
  if ((i < RUNS)); then
    echo "Sleep ${INTERVAL_SEC}s hasta próxima corrida..." >>"$LOG"
    sleep "$INTERVAL_SEC"
  fi
done

{
  echo ""
  echo "=== Fin programación ==="
  echo "Fin: $(date -Iseconds)"
} >>"$LOG"
