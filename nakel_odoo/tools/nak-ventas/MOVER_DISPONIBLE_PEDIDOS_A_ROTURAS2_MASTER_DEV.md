# Mover **lo disponible** desde `CEN/Existencias` → `CEN/Roturas 2` según órdenes (`master_dev`)

## Reglas (obligatorias)

- **Solo** se leen `sale.order` de la compañía **NAK** (en `master_dev` suele ser `company_id=2`), en estado **borrador** (`state=draft` = cotización).  
- **No** se procesan —ni se usan para cantidades— las órdenes de venta/cotizaciones de **Nakel SA** (`company_id=1`). El script **falla** si el nombre de orden corresponde a otra compañía.  
- El movimiento de stock se crea solo en **Nakel SA** (`stock.picking` interno).  
- **Con `--apply`**, además de validar el picking, el script puede **actualizar etiquetas** en la cotización NAK (`sale.order.tag_ids`): quita **`procesar`** y agrega **`ProcesadaNN`** (nombre configurable), salvo `--no-mark-processed`.

**Plan A (elegido):** ejecutar el script a mano con `--dry-run` y luego `--apply` cuando corresponda.

### Selección por etiquetas (NAK): `procesar` → `ProcesadaNN`

Por **defecto**:

- Solo entran cotizaciones que tengan la etiqueta **`procesar`** (nombre exacto, como en la ficha de venta).
- Si **no** pasás `--orden` / `--ordenes` / `--archivo-ordenes`, el script **lista solo** cotizaciones NAK en borrador con **`procesar`** y **sin** la etiqueta de “ya procesada” (`ProcesadaNN` por defecto). Equivale al flujo “solo las que el usuario etiquetó para procesar”.
- Con **`--apply`**, tras mover stock: **agrega** `ProcesadaNN` y **quita** `procesar` (un solo `write` en Odoo). Con **`--dry-run`** no se tocan etiquetas ni stock.

**Excepciones útiles:**

- **`--permitir-sin-tag-procesar`**: si listás órdenes por nombre, no se exige que lleven `procesar` (solo para casos excepcionales).
- **`--no-mark-processed`**: con `--apply`, no modifica `tag_ids` tras validar el picking.
- **`--ensure-tag-procesar`**: si no existe el `crm.tag` con nombre `procesar`, lo crea (color por `--tag-procesar-color`, default 6).
- **`--tag-procesar-name` / `--tag-procesar-id`**: otro nombre o ID fijo para la etiqueta “a procesar”.
- **`--skip-tag-name` / `--skip-tag-id`**: nombre o ID de la etiqueta “ya procesada” (default `ProcesadaNN`).

**Contexto:** el stock físico a mover vive en **`Nakel SA`**, aunque el pedido “documental” esté en **NAK**:

- Origen: `CEN/Existencias` (`stock.location`, típicamente **id=102**)
- Destino: `CEN/Roturas 2` (`stock.location`, típicamente **id=541**)

**Política:** por cada `sale.order` elegible, se calcula la necesidad por producto (suma de líneas) y se mueve:

\[
\text{qty\_mover} = \min(\text{pedido},\text{disponible en CEN/Existencias})
\]

Si en **`CEN/Existencias`** el disponible es **0**, **no se crea línea de movimiento** para ese producto: queda **omitido** (comportamiento esperado; no es error). La cotización en NAK **no cambia cantidades** por el script.

Si hay **menos** stock que lo pedido, se mueve **`min(pedido, disponible)`** (movimiento parcial); el faltante sigue solo en el documento de venta.

## Script

Archivo:

- `nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py`

Requisitos:

- `config_nakel.py` accesible (por defecto busca `/media/klap/raid5/cursor_files` en `PYTHONPATH`, o exportá `NAKEL_CONFIG_ROOT`).

## Referencia `master_dev`: compañías, `crm.tag` y uso por ID

Esta sección documenta valores **observados en la base `master_dev`** (XML-RPC vía `ODOO_CONFIG_MASTER_DEV`). **No asumir los mismos IDs en producción** u otra copia de la base: los `id` de `crm.tag` dependen del orden de creación y de migraciones.

### Compañías (típico en `master_dev`)

| Rol | `res.company` `id` |
|-----|-------------------|
| NAK (cotizaciones / `sale.order` a leer) | **2** |
| Nakel SA (stock / `stock.picking` interno) | **1** |

Coincide con los defaults del script: `--company-nak 2`, `--company-nakel 1`.

### Etiquetas `crm.tag` usadas por el flujo (típico en `master_dev`)

Búsqueda por `name` exacto en `crm.tag`:

| `name` (exacto) | `id` | `color` (índice Odoo 0–11) |
|-----------------|------|----------------------------|
| `procesar` | **2** | 9 |
| `ProcesadaNN` | **1** | 10 |

En el script, **`--tag-procesar-id` y `--skip-tag-id` tienen prioridad** sobre `--tag-procesar-name` y `--skip-tag-name`, lo que evita colisiones si existieran dos etiquetas con texto parecido.

Ejemplo **dry-run** fijando IDs (misma lógica que por nombre, más explícito para esta base):

```bash
python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py \
  --dry-run \
  --tag-procesar-id 2 \
  --skip-tag-id 1
```

Ejemplo **`--apply`** con los mismos IDs:

```bash
python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py \
  --apply \
  --tag-procesar-id 2 \
  --skip-tag-id 1
```

### Defaults por variable de entorno (sin repetir flags)

Si en tu shell o perfil exportás (valores típicos **solo** para `master_dev` actual):

```bash
export NAKEL_MOVER_TAG_PROCESAR_ID=2
export NAKEL_MOVER_SKIP_TAG_ID=1
```

entonces **`--tag-procesar-id` y `--skip-tag-id` toman esos valores por defecto** y podés invocar solo:

```bash
python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py --dry-run
python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py --apply
```

Los flags en línea de comandos **siguen teniendo prioridad** sobre el entorno. Sin variables y sin flags, el comportamiento sigue siendo por **nombre** (`procesar` / `ProcesadaNN`).

### Cómo comprobar los IDs en otra base

- **Interfaz Odoo** (modo desarrollador): menú donde se editan las etiquetas de CRM / ventas, abrir el registro: el **`id`** aparece en la URL (`…/web#id=…&model=crm.tag`).
- **Técnico:** en `crm.tag`, dominio `[("name", "=", "procesar")]` (y lo mismo para `ProcesadaNN`) y leer el campo `id` (y opcionalmente `color`).

Tras migración o restore, **volver a leer** `id` y actualizar esta tabla en la documentación si querés mantener la referencia al día.

## Uso

### Flujo recomendado (solo etiqueta `procesar`)

Dry-run sobre todas las cotizaciones NAK con `procesar` (sin pasar nombres de orden):

```bash
python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py --dry-run
```

Aplicar (stock + marcar `ProcesadaNN` y quitar `procesar`):

```bash
python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py --apply
```

No hace falta **`--auto-desde-tag-procesar`**, **`--require-tag-procesar`** ni **`--mark-processed`**: el listado vacío ya usa `procesar`; `--apply` ya marca por defecto.  
`--auto-desde-tag-procesar` sigue siendo opcional (explícito) si querés el mismo comportamiento aunque hayas pasado otras flags.

### Órdenes concretas por CLI

Dry-run (solo se procesan si cumplen `procesar`, salvo `--permitir-sin-tag-procesar`):

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

Límite al listado automático por etiqueta:

```bash
python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py --dry-run --limit-auto 50
```

Solo en casos excepcionales: permitir una orden NAK **no** borrador (no recomendado):

```bash
python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py --dry-run --orden S02202 --permitir-venta-confirmada
```

## Notas / límites

- A veces Odoo **divide** el traslado en **más de un** `stock.picking` con el mismo `origin`. El script, tras validar el principal, **busca y cierra** los demás albaranes pendientes con ese `origin` (asigna, crea `stock.move.line` con `qty_done` si el movimiento quedó sin reserva, y valida con `skip_backorder`).
- El picking queda con `origin` tipo `S02202 -> Roturas2 (mover disponible)` para trazabilidad en **Nakel SA**.
- Si algún producto es **trazado por lote/serie** y hay múltiples lotes, puede aparecer un **wizard** al validar; en ese caso el script aborta con error explícito para no asumir un resultado ambiguo.
- Si necesitás “un solo picking” para muchas órdenes juntas, decilo: hoy está **1 picking por orden** (más simple de auditar).
