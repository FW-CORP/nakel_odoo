#!/usr/bin/env bash
# Respaldo + diferencial WAVE/00156 — solo lectura master_dev
set -euo pipefail
ROOT=/media/klap/raid5/cursor_files/nakel
BACKUPS="$ROOT/Prod-Incidencias/wave156/backups"
PREFIX="wave_00156_batch163"
cd "$ROOT"

python3 nakel_odoo/tools/inventario/backup_wave_progress_master_dev.py \
  --batch-id 163 \
  --output-dir "$BACKUPS"

python3 nakel_odoo/tools/inventario/diff_wave_move_lines_backups.py \
  --dir "$BACKUPS" \
  --prefix "$PREFIX" \
  --vs-baseline
