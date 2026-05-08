#!/usr/bin/env bash
# Regenera todas las listas PDV (-FIX / fijas) definidas abajo.
# Usa: ventas/Listas de precios/scripts/dry_run_snapshot_lista_desde_referencia.py
# y config_nakel.py → master_dev.
#
# Uso:
#   ./regenerar_listas_pdv.sh dry-run    # solo informe, recorre cada lista
#   ./regenerar_listas_pdv.sh apply      # crea listas (falla si el nombre destino ya existe)
#
# Opcional: BATCH=25 ./regenerar_listas_pdv.sh dry-run
#
# Antes de apply con el mismo nombre que una lista ya creada: en Odoo renombrar o archivar
# la lista -FIX anterior.

set -u

SCRIPT_PY="/media/klap/raid5/cursor_files/nakel/ventas/Listas de precios/scripts/dry_run_snapshot_lista_desde_referencia.py"
BATCH="${BATCH:-35}"

# ---------------------------------------------------------------------------
# Pares: LISTA_REFERENCIA_ODDOO|NOMBRE_LISTA_DESTINO
# El nombre de referencia debe coincidir EXACTAMENTE con Odoo (o el script lo resuelve por ilike).
# Si renombraste una lista origen, editá la primera columna aquí.
# Para añadir una lista PDV nueva, agregá una línea al array.
# ---------------------------------------------------------------------------
LISTAS=(
  "Lista 2 Consumidor Final Autoservicios CR|Belgrano Final Comodoro"
  "Lista 2 Autoservicios CR|Lista 2 Autoservicios CR - FIX"
  "Lista 25 Autoservicio Caleta Olivia|Lista 25 Autoservicio Caleta Olivia - FIX"
  "Lista 25 Consumidor Final Autoservicio CO|Lista 25 Consumidor Final Autoservicio CO - FIX"
)

usage() {
  echo "Uso: $0 dry-run|apply" >&2
  exit 1
}

[[ -f "$SCRIPT_PY" ]] || { echo "No existe $SCRIPT_PY" >&2; exit 1; }

MODE="${1:-}"
[[ "$MODE" == "dry-run" || "$MODE" == "apply" ]] || usage

EXTRA=()
[[ "$MODE" == "apply" ]] && EXTRA+=(--apply)

echo "========================================"
echo "Modo: $MODE | batch=$BATCH | listas=${#LISTAS[@]}"
echo "========================================"

failed=0
n=0
for entry in "${LISTAS[@]}"; do
  n=$((n + 1))
  ref="${entry%%|*}"
  dest="${entry#*|}"
  echo ""
  echo ">>> [$n/${#LISTAS[@]}] REF: $ref"
  echo ">>>         →  $dest"
  if ! python3 "$SCRIPT_PY" \
      --lista-referencia "$ref" \
      --nombre-nueva "$dest" \
      --batch "$BATCH" \
      "${EXTRA[@]}"; then
    echo "!!! Falló el par [$n]: $ref → $dest" >&2
    failed=$((failed + 1))
  fi
done

echo ""
echo "========================================"
if [[ "$failed" -eq 0 ]]; then
  echo "Listo: 0 fallos en $n pares."
else
  echo "Atención: $failed par(es) con error (de $n)."
fi
echo "========================================"
exit "$failed"
