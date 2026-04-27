# Bug report — Barcode muestra 0 por `picked` desincronizado (master_dev)

**Fecha:** 2026-04-23  
**Entorno:** Producción `nakel.net.ar` / DB `master_dev`  

## Síntoma

Durante la recolección con **Operaciones → Código de barras** (especialmente en **olas/waves**), la UI puede mostrar **“0 / …”** o comportamientos inconsistentes en líneas donde el operario ya cargó cantidades, bloqueando o degradando el proceso (horas perdidas en logística).

## Evidencia en datos (master_dev)

Se observó un volumen alto de `stock.move.line` con el patrón:

- `quantity > 0` y `picked = false`

En particular, la ola `WAVE/00081` (batch id **82**) tenía:

- `stock.move.line` totales: **940**
- `quantity > 0`: **940**
- `quantity > 0` y `picked = false`: **938**
- `quantity > 0` y `picked = true`: **2**

Esto causa que Barcode interprete la línea como “no pickeada” y muestre valores 0.

## Causa técnica (hipótesis)

En ciertos flujos de Barcode/Odoo, se escriben cantidades en `stock.move.line` sin sincronizar el booleano `picked`, dejando la línea en estado inconsistente para la UI de Barcode.

## Fix aplicado

Se implementa el módulo `nakel_fix_pick` con “feature flag”:

- `ir.config_parameter` **`nakel_fix_pick.enable`**

Con el flag activo, el módulo intercepta `stock.move.line.write(vals)` y si se escribe cantidad **sin** `picked`:

- **Preferencia:** si viene `qty_done`, fuerza `picked = (qty_done > 0)`
- **Fallback:** si viene `quantity` (flujo custom/raro), fuerza `picked = (quantity > 0)`

## Activación

En Odoo (modo desarrollador):

**Ajustes → Técnico → Parámetros → Parámetros del sistema**

- Clave: `nakel_fix_pick.enable`
- Valor: `1`

## Notas

- El fix no modifica cantidades: solo evita que `picked` quede desincronizado.
- La corrección retroactiva (“backfill”) debe basarse en **`qty_done > 0`**, no en `quantity`, porque `quantity` en Odoo puede representar reservado/planeado.

