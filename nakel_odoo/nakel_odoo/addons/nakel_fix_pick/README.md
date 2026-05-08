# nakel_fix_pick

Mini-módulo Nakel sobre **Inventario / Código de barras** (Enterprise `stock_barcode`). Conviene **extender este módulo** en lugar de parchear a mano los archivos de Odoo: se despliega con el resto de custom addons y sobrevive a upgrades del `.deb`.

Corre dos dolores distintos (cada uno con su propia bandera):

1. **Flag `picked` desalineado** en `stock.move.line` (UI “0 / …”).
2. **Popup “registro no existe”** por `stock.move` / `stock.move.line` ya borrados mientras la SPA Barcode sigue con IDs viejos.

## Enfoque propuesto (seguro por defecto)

Este módulo **no hace nada** en cliente ni en `write` si no se activa explícitamente.

### A) `nakel_fix_pick.enable` — consistencia `picked` (servidor)

- `False` o no seteado: no altera `stock.move.line.write`.
- `True`: si se escribe `qty_done` sin `picked`, fuerza `picked = (qty_done > 0)`.
  - Fallback: si solo viene `quantity`, `picked = (quantity > 0)` (flujos raros).

### B) `nakel_fix_pick.barcode_soft_missing` — recuperación suave (navegador)

- `False` o no seteado: comportamiento Odoo estándar (diálogo RPC).
- `True`: ante `MissingError` en RPC sobre **`stock.move`** o **`stock.move.line`**, se evita el diálogo bloqueante, se muestra un aviso y se **recarga la página** para que Barcode vuelva a cargar datos frescos.

**Nota:** el reload es brusco pero fiable; una evolución futura podría intentar reabrir solo el picking/ola sin recargar todo el cliente.

## Backfill (opcional, no automático)

Incluye un método utilitario para backfill controlado por Wave (Batch Picking), pensado para ejecutarse **manualmente** (por ejemplo desde un shell de Odoo o un script de mantenimiento), nunca en automático.

## Notas operativas

- No cambia `quantity`. Solo corrige `picked` para que `qty_done` refleje lo real.
- Pensado para escenarios sin lotes/paquetes (igual no depende de eso).

## Documentación

- Ver informe del incidente y fix: `docs/BUGREPORT_BARCODE_PICKED_FLAG_master_dev_2026-04-23.md`

