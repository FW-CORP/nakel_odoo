#!/usr/bin/env bash
# Respaldo + diferencial WAVE/00156 — solo lectura master_dev
set -euo pipefail
ROOT=/media/klap/raid5/cursor_files/nakel
BACKUPS="$ROOT/Prod-Incidencias/wave156/backups"
cd "$ROOT"

python3 nakel_odoo/tools/inventario/backup_wave_progress_master_dev.py \
  --batch-id 163 \
  --output-dir "$BACKUPS"

# Si hay al menos 2 snapshots move_lines, genera diff del último vs el anterior
if ls "$BACKUPS"/wave_00156_batch163_move_lines_*.csv >/dev/null 2>&1; then
  count=$(ls -1 "$BACKUPS"/wave_00156_batch163_move_lines_*.csv 2>/dev/null | wc -l)
  if [ "$count" -ge 2 ]; then
    python3 nakel_odoo/tools/inventario/diff_wave_move_lines_backups.py \
      --dir "$BACKUPS" \
      --prefix wave_00156_batch163
  else
    echo "Diff: omitido (solo hay $count snapshot; hace falta una 2.ª corrida)."
  fi
fi
