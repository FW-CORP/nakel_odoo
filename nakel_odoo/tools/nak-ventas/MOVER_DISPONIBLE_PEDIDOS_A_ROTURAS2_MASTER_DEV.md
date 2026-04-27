# Mover **lo disponible** desde `CEN/Existencias` → `CEN/Roturas 2` según órdenes (`master_dev`)

## Reglas (obligatorias)

- **Solo** se leen `sale.order` de la compañía **NAK** (en `master_dev` suele ser `company_id=2`), en estado **borrador** (`state=draft` = cotización).  
- **No** se procesan —ni se usan para cantidades— las órdenes de venta/cotizaciones de **Nakel SA** (`company_id=1`). El script **falla** si el nombre de orden corresponde a otra compañía.  
- **No** se modifica la cotización: solo **lectura** de `sale.order` / `sale.order.line`. El movimiento de stock se crea solo en **Nakel SA** (`stock.picking` interno).

**Plan A (elegido):** ejecutar el script a mano con `--dry-run` y luego `--apply` cuando corresponda (lista de `S0…` vía `--orden`, `--ordenes` o `--archivo-ordenes`).

**Contexto:** el stock físico a mover vive en **`Nakel SA`**, aunque el pedido “documental” esté en **NAK**:

- Origen: `CEN/Existencias` (`stock.location`, típicamente **id=102**)
- Destino: `CEN/Roturas 2` (`stock.location`, típicamente **id=541**)

**Política:** por cada `sale.order` listado por nombre (ej. `S02202`), se calcula la necesidad por producto (suma de líneas) y se mueve:

\[
\text{qty\_mover} = \min(\text{pedido},\text{disponible en CEN/Existencias})
\]

Si en **`CEN/Existencias`** el disponible es **0**, **no se crea línea de movimiento** para ese producto: queda **omitido** (comportamiento esperado; no es error). La cotización en NAK **no se modifica**.

Si hay **menos** stock que lo pedido, se mueve **`min(pedido, disponible)`** (movimiento parcial); el faltante sigue solo en el documento de venta.

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

Listar productos omitidos por **stock 0** en `CEN/Existencias` (auditoría):

```bash
python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py --dry-run --orden S02966 --listar-omitidos
```

Aplicar (crea **un** `stock.picking` interno por orden, validado):

```bash
python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py --apply --orden S02202
```

Solo en casos excepcionales: permitir una orden NAK **no** borrador (no recomendado):

```bash
python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py --dry-run --orden S02202 --permitir-venta-confirmada
```

## Notas / límites

- El picking queda con `origin` tipo `S02202 -> Roturas2 (mover disponible)` para trazabilidad en **Nakel SA** (no modifica la cotización en **Nak**).
- Si algún producto es **trazado por lote/serie** y hay múltiples lotes, puede aparecer un **wizard** al validar; en ese caso el script aborta con error explícito para no asumir un resultado ambiguo.
- Si necesitás “un solo picking” para muchas órdenes juntas, decilo: hoy está **1 picking por orden** (más simple de auditar).
