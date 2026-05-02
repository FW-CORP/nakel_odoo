# nakel_fix_pick

Mini-módulo para **analizar** y (opcionalmente) corregir el caso detectado en Barcode:

- En `stock.move.line`, `qty_done` (UI) se computa como `quantity` si `picked` es verdadero, si no **0**.
- Se observó data inconsistente: `quantity > 0` pero `picked = false`, lo que hace que Barcode muestre “0 / …” aun teniendo cantidades hechas.

## Enfoque propuesto (seguro por defecto)

Este módulo **no hace nada** si no se activa explícitamente.

- **Bandera**: parámetro de sistema `nakel_fix_pick.enable`
  - `False` o no seteado: no toca nada.
  - `True`: al escribir en `stock.move.line`, si se escribe `qty_done` sin `picked`, sincroniza `picked = (qty_done > 0)`.
    - Fallback: si se escribe `quantity` sin `picked` (custom/flujo raro), sincroniza `picked = (quantity > 0)`.

## Backfill (opcional, no automático)

Incluye un método utilitario para backfill controlado por Wave (Batch Picking), pensado para ejecutarse **manualmente** (por ejemplo desde un shell de Odoo o un script de mantenimiento), nunca en automático.

## Notas operativas

- No cambia `quantity`. Solo corrige `picked` para que `qty_done` refleje lo real.
- Pensado para escenarios sin lotes/paquetes (igual no depende de eso).

