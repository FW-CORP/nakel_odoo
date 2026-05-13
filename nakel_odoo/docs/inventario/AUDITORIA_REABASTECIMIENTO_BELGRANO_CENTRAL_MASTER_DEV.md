# Auditoría: reabastecimiento Belgrano ↔ Nakel Central (`master_dev`)

**Base:** `master_dev` (Odoo 18 EE)  
**Fecha auditoría:** 2026-05-09 (lectura XML-RPC / MCP)

**Objetivo:** Confirmar que las **rutas** de resurtido desde Central están armadas y evaluar **reglas de reabastecimiento** (mínimos/máximos) para dejar de depender de ir producto por producto.

---

## 1. Almacenes y pasos físicos

| ID | Nombre   | Código | Recepción        | Entrega        |
|----|----------|--------|------------------|----------------|
| 14 | Nakel Central | CEN | 2 pasos (entrada + existencias) | 2 pasos (pick + ship) |
| 15 | Belgrano 1    | B1  | **3 pasos** (entrada + QC + existencias) | 1 paso (solo envío) |
| 16 | Belgrano 2    | B2  | 3 pasos | 1 paso |
| 17 | Belgrano 3    | B3  | 3 pasos | 1 paso |
| 18 | Belgrano 4    | B4  | 2 pasos | 1 paso |
| 19 | Nak           | baja| 1 paso  | 1 paso |

**Resurtido explícito (Belgrano 1 como ejemplo):**

- `resupply_wh_ids` → **Nakel Central (14)**  
- `resupply_route_ids` → ruta **58** (*Belgrano 1: suministrar producto de Nakel Central*)

Los demás Belgrano/Nak tienen el mismo patrón con sus rutas **62, 66, 70, 74**.

---

## 2. Rutas “suministrar desde Nakel Central”

Rutas activas, `warehouse_selectable` + `product_selectable` = sí (se eligen en almacén y/o en producto):

| ID | Nombre |
|----|--------|
| 58 | Belgrano 1: suministrar producto de Nakel Central |
| 62 | Belgrano 2: suministrar producto de Nakel Central |
| 66 | Belgrano 3: suministrar producto de Nakel Central |
| 70 | Belgrano 4: suministrar producto de Nakel Central |
| 74 | Nak: suministrar producto de Nakel Central |

### Cadena `stock.rule` (misma lógica para B1–B4 y Nak)

Cada ruta tiene **3 reglas pull** en orden lógico:

1. **Central — Existencias → Salida** (`CEN/Existencias` → `CEN/Salida`), tipo **Recolectar** (PICK), `make_to_stock`.
2. **Central — Salida → Traslado entre almacenes** (`CEN/Salida` → ubicación **Traslado entre almacenes**), tipo **Órdenes de entrega** (OUT Central), `make_to_order`.
3. **Sucursal — Traslado → Existencias** (ubicación intermedia → `B*/Existencias` o `baja/Existencias`), tipo **Recepciones** de esa sucursal, `make_to_order`.

Eso modela bien el hecho de que **el depósito físico sea otro**: la mercadería sale de Central hacia el **hub de traslado** y entra por **recepción** del almacén destino.

---

## 3. Reglas de reabastecimiento (`stock.warehouse.orderpoint`)

| Agrupación | Cantidad |
|------------|----------|
| **Total** activos | **572** |
| Por **disparador** | **572** con `trigger` = **`manual`** (ninguno automático por scheduler) |
| Por **almacén** (`warehouse_id`) | CEN: **150**, B1: **135**, B2: **149**, B3: **60**, B4: **78** |
| Con **`product_max_qty` > 0** | **1** (solo en **Nakel Central**, producto ejemplo min=2 / max=50) |
| Con **mínimo y máximo en 0** | **571** (casi todo el catálogo cubierto por reglas tipo *Reporte de reabastecimiento*) |

### Interpretación

- Las **rutas y reglas** para traer desde Central **están definidas y enlazadas** a los orderpoints (ej. `route_id` = 58 en B1, `rule_ids` apuntando a reglas 130–132 de la cadena CEN→traslado→B1).
- Los **mínimos/máximos en 0** no significan “mal configurado” en Odoo 18 para el flujo **Reabastecimiento**: la cantidad a pedir sale del **reporte** (`qty_to_order`, `qty_forecast`, etc.) y del operador que confirma en lote. Sí significa que **no hay política automática de stock objetivo** por producto/ubicación: nadie “repone hasta X” salvo que se carguen **min/max** o se use **cantidad manual** en la pantalla.
- **Un solo** orderpoint con max > 0 (y en **CEN**, no en sucursal) indica que **no se atacó aún** el tema de **topes por sucursal** a escala.

---

## 4. Permisos y flujo encargados (Nakel)

Si al **confirmar** desde Reabastecimiento falla por tipo de operación o acceso, el vault ya documenta el encaje con **traslado interno** con tipo de la sucursal y origen **CEN/Existencias**:

- [`../usuarios/PERMISOS/PERMISOS_ENCARGADOS_VENTAS_ALMACEN_PEDIDOS.md`](../usuarios/PERMISOS/PERMISOS_ENCARGADOS_VENTAS_ALMACEN_PEDIDOS.md) (secciones *Reabastecimiento* y *Pedidos de reabastecimiento con origen CEN*).

---

## 5. Recomendaciones (prioridad)

### A. Política de mínimos/máximos (donde más impacto)

1. **Definir por sucursal** (B1–B4) **stock mínimo objetivo** para **SKU A/B** (rotación), no para todo el catálogo el primer día.
2. Cargar **`product_min_qty` / `product_max_qty`** en los `orderpoint` existentes (import CSV o script), manteniendo `route_id` = ruta “suministrar desde Central”.
3. Revisar **`qty_multiple`** (caja/bulto) donde aplique, para que lo que pide Central sea **logístico**.

### B. Disparador

- Evaluar pasar los más críticos de **`manual`** a **`auto`** (según versión/campos disponibles) y correr el **planificador** con procedimiento acordado, **o** mantener manual pero con **rutina diaria/semanal** desde **Inventario → Reabastecimiento** (lista masiva, no ficha por ficha).

### C. Calidad de datos

- Orderpoints con **forecast negativo** (ej. `qty_on_hand` negativo en muestra) exigen **ajuste de quants / inventarios**; si no, el reabastecimiento sugiere números incoherentes.

### D. Ventas desde Central vs sucursal

- Alinear **ruta en producto / OV** para que las ventas “de depósito Central” no mezclen reglas con ventas “solo sucursal” (caso ya visto en OV tipo **S04090** sin OUT: revisar consistencia ruta + `delivery_steps`).

---

## 7. Anexo: **Belgrano 1 (B1)** — foco operativo

Datos `master_dev` específicos del almacén **Belgrano 1** (`stock.warehouse` **id 15**, código **B1**).

### Configuración ya alineada

| Elemento | Valor en BD |
|----------|-------------|
| Resurtido desde | **Nakel Central (14)** |
| Ruta de resurtido | **58** — *Belgrano 1: suministrar producto de Nakel Central* |
| Recepción almacén | Ruta **55** (3 pasos: entrada + QC + existencias) |
| Entrega desde B1 | Ruta **56** (1 paso: envío) |

### Reglas de reabastecimiento (orderpoints) en B1

| Métrica | Valor |
|---------|--------|
| Cantidad de `stock.warehouse.orderpoint` | **135** |
| Ubicación | **Todas** en **`B1/Existencias`** (id **109**) — un solo punto de stock para la política |
| `route_id` | **Todas** apuntan a la ruta **58** (Central → B1 vía traslado) |
| `trigger` | **manual** en las 135 |
| `product_min_qty` / `product_max_qty` | **0 / 0** en el conjunto (sin techo de stock objetivo en datos) |

Los productos quedan repartidos en **muchas categorías** (típicamente 3–5 SKUs por categoría en los grupos más frecuentes); no hay una sola categoría que concentre la mayor parte de las 135 reglas.

### Limitación técnica al auditar “prioridad” por API

Campos como **`qty_to_order`** y **`qty_forecast`** en el modelo de reabastecimiento **no son almacenados** en esta versión: no se pueden usar en `search`/`order` por XML-RPC para listar “top faltantes” sin código servidor o export desde la UI **Inventario → Operaciones → Reabastecimiento** filtrando almacén **Belgrano 1**.

### Plan piloto sugerido (solo B1)

1. **En Odoo (UI):** Reabastecimiento → filtrar almacén / ubicación **Belgrano 1 / Existencias** → ordenar por la columna de cantidad a pedir / pronóstico (lo que muestre la vista).
2. **Elegir 20–30 SKU** de mayor rotación o mayor hueco y cargar en esas reglas **`product_min_qty`** (piso) y **`product_max_qty`** (techo), más **`qty_multiple`** si compran por bulto. **Plantilla para el cliente (CSV + instrucciones):** [`plantillas/PLANTILLA_MIN_MAX_REABASTECIMIENTO_B1.csv`](plantillas/PLANTILLA_MIN_MAX_REABASTECIMIENTO_B1.csv) y [`plantillas/README_PLANTILLA_MIN_MAX_REABASTECIMIENTO.md`](plantillas/README_PLANTILLA_MIN_MAX_REABASTECIMIENTO.md).
3. **Proceso semanal:** misma vista, **Pedir** en lote, confirmar; Central prepara según la cadena de reglas ya existente.
4. **Datos:** revisar inventarios / quants en B1 si hay pronósticos negativos antes de confiar ciegamente en las cantidades sugeridas.

### Permisos encargados B1

Si al confirmar desde la lista aparece error de tipo de operación, seguir el flujo documentado para encargados (traslado con tipo **Belgrano 1** y origen **CEN/Existencias**): [PERMISOS encargados / reabastecimiento](../usuarios/PERMISOS/PERMISOS_ENCARGADOS_VENTAS_ALMACEN_PEDIDOS.md).

---

## 8. Referencias cruzadas en repo

- [OV sin facturar / sin OUT tras ola](OV_SIN_FACTURAR_SIN_OUT_TRAS_OLA.md) — coherencia cadena PICK/OUT y rutas en producto.
- [Faltantes ola / stock en Entrada](DIAGNOSTICO_OLA_FALTANTES_POR_STOCK_EN_ENTRADA.md) — stock en ubicación equivocada.

---

**Conclusión:** En `master_dev`, **sí** están armadas las rutas y reglas de **reabastecimiento desde Nakel Central hacia Belgrano (y Nak)** vía traslado entre almacenes. El cuello de botella para “no ir uno por uno” no es la ruta, sino **operación**: casi todo el reabastecimiento está en **disparador manual** y **min/max en cero**; conviene un **plan de min/max por rotación y sucursal** + proceso masivo desde el menú Reabastecimiento.
