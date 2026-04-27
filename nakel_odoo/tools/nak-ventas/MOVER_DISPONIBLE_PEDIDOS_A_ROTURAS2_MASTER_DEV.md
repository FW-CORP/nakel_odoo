# Mover **lo disponible** desde `CEN/Existencias` → `CEN/Roturas 2` según órdenes (`master_dev`)

**Contexto:** hay cotizaciones/pedidos en compañía **`Nak`** que no deben tocarse, pero el stock físico vive en **`Nakel SA`**. La necesidad operativa es mover mercadería real entre ubicaciones de Central:

- Origen: `CEN/Existencias` (`stock.location`, típicamente **id=102**)
- Destino: `CEN/Roturas 2` (`stock.location`, típicamente **id=541**)

**Política:** por cada `sale.order` listado por nombre (ej. `S02202`), se calcula la necesidad por producto (suma de líneas) y se mueve:

\[
\text{qty\_mover} = \min(\text{pedido},\text{disponible en CEN/Existencias})
\]

Si no hay disponible, **no mueve** ese producto (y queda explícito en el reporte del dry-run).

## Script

Archivo:

- `nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py`

Requisitos:

- `config_nakel.py` accesible (por defecto busca `/media/klap/raid5/cursor_files` en `PYTHONPATH`, o exportá `NAKEL_CONFIG_ROOT`).

## Uso

Dry-run (no crea nada):

```bash
python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py --dry-run --orden S02202
```

Varias órdenes:

```bash
python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py --dry-run --orden S02202 --orden S02203
```

O CSV:

```bash
python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py --dry-run --ordenes "S02202,S02203,S02204"
```

Archivo (una orden por línea):

```bash
python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py --dry-run --archivo-ordenes /ruta/ordenes.txt
```

Aplicar (crea **un** `stock.picking` interno por orden, validado):

```bash
python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py --apply --orden S02202
```

## Notas / límites

- El picking queda con `origin` tipo `S02202 -> Roturas2 (mover disponible)` para trazabilidad en **Nakel SA** (no modifica la cotización en **Nak**).
- Si algún producto es **trazado por lote/serie** y hay múltiples lotes, puede aparecer un **wizard** al validar; en ese caso el script aborta con error explícito para no asumir un resultado ambiguo.
- Si necesitás “un solo picking” para muchas órdenes juntas, decilo: hoy está **1 picking por orden** (más simple de auditar).
