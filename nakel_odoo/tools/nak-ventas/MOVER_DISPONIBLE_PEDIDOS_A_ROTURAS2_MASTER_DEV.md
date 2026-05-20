# Mover **lo disponible** → **Roturas 2** según cotizaciones etiquetadas (`master_dev`)

Script único con **dos perfiles** de almacén. Ambos usan las mismas etiquetas (`procesar` → `ProcesadaNN`) pero difieren en **de dónde se leen las cotizaciones** y **qué ubicaciones de stock se usan**.

**Plan A (elegido):** ejecutar a mano con `--dry-run` y luego `--apply`.

Archivo: `nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py`

Requisito: `config_nakel.py` (por defecto bajo `NAKEL_CONFIG_ROOT` o `/media/klap/raid5/cursor_files`).

---

## Perfiles

| | **Perfil CEN (NAK)** | **Perfil B3 (Belgrano 3 / Nakel SA)** |
|---|---------------------|--------------------------------------|
| Cotizaciones (`sale.order`) | Compañía **NAK** (`company_id=2`) | Compañía **Nakel SA** (`company_id=1`) |
| Almacén en la cotización | Sin filtro | **Belgrano 3** (`warehouse_id=17`, code `B3`) |
| Origen stock | `CEN/Existencias` (id ~102) | `B3/Existencias` (id ~123) |
| Destino | `CEN/Roturas 2` (id ~541) | `B3/Roturas 2` (id ~542) |
| Picking en | Nakel SA (`company_id=1`) | Nakel SA (`company_id=1`) |
| Defaults del script | Sin flags extra | Ver [comandos B3](#perfil-b3-belgrano-3) |

**Política de cantidad** (igual en ambos):

\[
\text{qty\_mover} = \min(\text{pedido},\text{disponible en origen})
\]

- Si el disponible en origen es **0** → **no se crea movimiento** para ese producto (esperado).
- Si hay **menos** stock que lo pedido → movimiento **parcial**; la cotización **no cambia cantidades**.

---

## Etiquetas: `procesar` → `ProcesadaNN`

Por **defecto**:

- Solo entran cotizaciones con **`procesar`** (nombre exacto en `crm.tag`).
- Sin `--orden` / `--ordenes` / `--archivo-ordenes`, el script **lista automáticamente** cotizaciones en borrador con **`procesar`** y **sin** `ProcesadaNN`.
- Con **`--dry-run`**: no toca stock ni etiquetas.
- Con **`--apply`**: quita **`procesar`** y agrega **`ProcesadaNN`** (salvo `--no-mark-processed`).

### Etiquetar aunque el stock sea 0

**Comportamiento intencional:** con `--apply`, la cotización se marca **`ProcesadaNN`** aunque **no haya ninguna línea de movimiento** (todo el pedido sin stock en origen).

Motivo: evitar **reprocesar por error** la misma cotización en una corrida posterior. Si no se movió nada, igual queda “ya procesada” desde el punto de vista operativo.

Para **no** marcar etiquetas: `--no-mark-processed`.

### Otras flags útiles

| Flag | Uso |
|------|-----|
| `--permitir-sin-tag-procesar` | Órdenes por nombre sin exigir `procesar` (excepcional) |
| `--no-mark-processed` | `--apply` sin tocar `tag_ids` |
| `--ensure-tag-procesar` | Crea `crm.tag` «procesar» si no existe |
| `--tag-procesar-name` / `--tag-procesar-id` | Etiqueta “a procesar” |
| `--skip-tag-name` / `--skip-tag-id` | Etiqueta “ya procesada” (default `ProcesadaNN`) |
| `--warehouse-code` | Código almacén: `CEN` (default) o `B3` |
| `--src-location` / `--dst-location` | Override de ubicaciones (complete_name) |
| `--filtrar-warehouse-id` | Solo cotizaciones de ese almacén (ej. `17` = Belgrano 3) |
| `--company-nak` | Compañía de las cotizaciones a leer |
| `--company-nakel` | Compañía del `stock.picking` (default Nakel SA = 1) |
| `--listar-omitidos` | Detalle de productos con pedido>0 y stock=0 |
| `--limit-auto N` | Tope al listado automático por etiqueta |

---

## Referencia `master_dev`

Valores **observados** en `master_dev`. **No asumir** los mismos IDs en otra base.

### Compañías

| Rol | `res.company` `id` |
|-----|-------------------|
| Nakel SA (stock / cotizaciones B3) | **1** |
| NAK (cotizaciones CEN) | **2** |

### Etiquetas `crm.tag`

| `name` | `id` | `color` (0–11) |
|--------|------|----------------|
| `ProcesadaNN` | **1** | 10 |
| `procesar` | **2** | 9 |

`--tag-procesar-id` y `--skip-tag-id` tienen prioridad sobre los nombres.

### Ubicaciones Roturas 2

| Ubicación | `id` | Uso |
|-----------|------|-----|
| `CEN/Roturas 2` | 541 | Destino perfil CEN |
| `B3/Roturas 2` | 542 | Destino perfil B3 |

### Variables de entorno (opcional)

```bash
export NAKEL_MOVER_TAG_PROCESAR_ID=2
export NAKEL_MOVER_SKIP_TAG_ID=1
```

---

## Perfil CEN (NAK)

Cotizaciones **NAK** en borrador; stock en **Nakel SA** desde **Centro**.

### Comandos

Dry-run (todas con `procesar`):

```bash
python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py --dry-run
```

Apply:

```bash
python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py --apply
```

Una orden:

```bash
python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py --dry-run --orden S02202
```

### Alias sugerido (shell)

```bash
alias nak-mover-cen-dry='python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py --dry-run'
alias nak-mover-cen-apply='python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py --apply'
```

---

## Perfil B3 (Belgrano 3)

Cotizaciones **Nakel SA** en borrador con almacén **Belgrano 3**; stock **B3/Existencias → B3/Roturas 2**.

**Importante:** usar **`--company-nak 1`** (cotizaciones en Nakel SA) y **`--filtrar-warehouse-id 17`** para no mezclar con otros almacenes.

### Comandos

Dry-run:

```bash
python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py \
  --dry-run \
  --company-nak 1 \
  --company-nakel 1 \
  --warehouse-code B3 \
  --filtrar-warehouse-id 17
```

Apply (todas las pendientes con `procesar`):

```bash
python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py \
  --apply \
  --company-nak 1 \
  --company-nakel 1 \
  --warehouse-code B3 \
  --filtrar-warehouse-id 17
```

Prueba con órdenes concretas:

```bash
python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py \
  --apply \
  --company-nak 1 \
  --company-nakel 1 \
  --warehouse-code B3 \
  --filtrar-warehouse-id 17 \
  --orden S03007 \
  --orden S04607
```

Auditoría (productos sin stock en B3):

```bash
python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py \
  --dry-run \
  --company-nak 1 \
  --warehouse-code B3 \
  --filtrar-warehouse-id 17 \
  --orden S03447 \
  --listar-omitidos
```

### Alias sugerido (shell)

```bash
alias nak-mover-b3-dry='python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py --dry-run --company-nak 1 --company-nakel 1 --warehouse-code B3 --filtrar-warehouse-id 17'
alias nak-mover-b3-apply='python3 nakel_odoo/tools/nak-ventas/scripts/mover_disponible_pedidos_a_roturas2_master_dev.py --apply --company-nak 1 --company-nakel 1 --warehouse-code B3 --filtrar-warehouse-id 17'
```

Pickings B3 quedan con nombre tipo `B3/INT/00013` y `origin` `S03007 -> Roturas2 (mover disponible)`.

### Historial en `master_dev` (mayo 2026)

- **Perfil CEN/NAK:** corridas previas con pickings `CEN/STOR/…` (ej. 27–12 abr y 12 may 2026); cotizaciones NAK pasaron a solo `ProcesadaNN`.
- **Perfil B3:** corrida completa 26 cotizaciones Belgrano 3 (22 pickings con movimiento + 6 solo etiqueta por stock 0): S03007, S04607 (prueba) y lote S03017…S04851.

---

## Notas / límites

- A veces Odoo **parte** un traslado en **varios** `stock.picking` con el mismo `origin`. El script cierra los pendientes (asigna, crea `stock.move.line` si hace falta, valida con `skip_backorder`).
- **1 picking por cotización** (auditoría simple).
- Productos con **lote/serie** ambiguos pueden devolver un **wizard** al validar → el script aborta con error explícito.
- Picking type internal en B3: se prefiere **«Traslados internos»** si hay varios tipos internal en el almacén.

## Relacionado

- [CRON_DESECHO_ROTURAS2_MASTER_DEV.md](CRON_DESECHO_ROTURAS2_MASTER_DEV.md) — desecho automático de lo acumulado en **CEN/Roturas 2** y **B3/Roturas 2** vía `stock.scrap`.
