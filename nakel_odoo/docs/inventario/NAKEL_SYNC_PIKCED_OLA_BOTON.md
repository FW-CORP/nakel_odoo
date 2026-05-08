# Botón SYNC en Ola (Batch Transfer) para marcar `picked`

## Problema

En olas grandes, durante la operación por **Barcode**, puede quedar desincronizado el tilde de “Recolectado”:

- `stock.move.line.quantity > 0` pero `stock.move.line.picked = false`

Esto hace que Barcode muestre “0 / …” o líneas no recolectadas aunque ya se haya cargado cantidad.

## Solución

Se extiende el addon **`nakel_fix_pick`** para agregar un botón **SYNC** en el formulario de la ola (`stock.picking.batch`).

Acción del botón:

- Busca líneas (`stock.move.line`) de la ola con:
  - `quantity > 0`
  - `picked = false`
- Escribe:
  - `picked = true`

## Uso recomendado

1. Operarios trabajan la ola con Barcode.
2. Si el progreso se ve “roto” (tildes faltantes), supervisión abre la ola y presiona **SYNC**.
3. Continuar operando / validar cuando corresponda.

## Seguridad

- Restringido a usuarios con permisos de inventario (`stock.group_stock_user`).
- No modifica cantidades ni mueve stock: solo normaliza el flag `picked`.

