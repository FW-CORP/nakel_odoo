# Ticket — Olas WAVE + Modo demanda OV + Planificador por zona

| Campo | Valor |
|-------|--------|
| **Cliente** | Nakel |
| **Entorno** | Odoo 18 — `master_dev` (prod operativa) / `staging_mayo` (QA) |
| **Tipo** | Desarrollo custom + implementación operativa |
| **Estado** | Implementado en master_dev — pendiente capacitación / producción |
| **Wiki FWHQ** | [nakel_barcode_wave_demand_mode](https://docs.fwhq.com.ar/link/283#bkmrk-puente-operativo-par) |
| **Repo** | `nakel_odoo/addons/` |

---

## Resumen ejecutivo

Puente operativo para **olas WAVE + Barcode** cuando el inventario Odoo no refleja el piso logístico.

**Problema:** OV pide 10 u; reserva Odoo deja `stock.move.line.quantity = 1`; Barcode topa en 1.

**Solución entregada:**

1. **`nakel_wave_planner`** — Armar olas por zona/vendedor con checklist (~30 OV).
2. **`nakel_barcode_wave_demand_mode`** — Modo demanda OV, semáforo verde/amarillo/rojo, Ver faltantes, Agregar a la ola.
3. Integración con **`nakel_wave_picking_link`** y **`nakel_fix_pick`**.

**Regla operativa:**

```text
Verde → Barcode | Amarillo → Modo demanda OV → Barcode | Rojo → Ver faltantes → Agregar a la ola
```

---

## Módulos y versiones desplegadas

| Módulo | Versión | Rol |
|--------|---------|-----|
| `nakel_wave_planner` | 18.0.1.0.2 | Wizard “Armar ola por zona” |
| `nakel_barcode_wave_demand_mode` | 18.0.1.0.8 | Modo demanda, semáforo, faltantes, guardia batch |
| `nakel_wave_picking_link` | 18.0.1.0.7+ | Enlace OV ↔ ola (`nakel_wave_batch_id`) |
| `nakel_fix_pick` | 18.0.1.1.5 | Sync `picked` / `qty_done` (requerido) |

**Documentación adicional:**

- `nakel_odoo/docs/inventario/BARCODE_OLA_MODO_DEMANDA_PLAN.md`
- `nakel_odoo/docs/inventario/BARCODE_OLA_FLUJO_MODULOS_Y_STOCK.md`
- `nakel_odoo/addons/nakel_barcode_wave_demand_mode/README.md`

---

## Estimación de horas

| Fase | Actividad | Horas |
|------|-----------|------:|
| **Desarrollo** | Modo demanda OV Fase 1 (quantity = demanda, SQL Odoo 18, PICK hermanos) | 10 |
| | Semáforo cobertura OV (verde / amarillo / rojo) | 6 |
| | Wizard Ver faltantes + Agregar a la ola (`_action_launch_stock_rule`) | 8 |
| | Planificador olas por zona/vendedor (`nakel_wave_planner`) | 10 |
| | Integración `nakel_fix_pick` (`nakel_demand_mode_bump`) | 2 |
| | Documentación técnica + diagramas de flujo | 4 |
| | **Subtotal desarrollo** | **40** |
| **Testing / QA** | Casos staging (WAVE/00144–00156, reserva parcial, sin PICK) | 8 |
| | Barcode + validación PICK/OUT + facturación parcial | 4 |
| | Regresión olas completas vs faltantes OV viejas | 4 |
| | **Subtotal testing** | **16** |
| **Implementación** | Deploy staging + master_dev, upgrade módulos | 3 |
| | Configuración ICP + verificación permisos | 2 |
| | Runbook operativo + wiki FWHQ | 3 |
| | Capacitación supervisor / operario (1 sesión) | 2 |
| | Rollout producción (cuando aplique) + soporte post-go-live | 4 |
| | **Subtotal implementación** | **14** |
| | **TOTAL ESTIMADO** | **70 h** |

*Nota: horas reales de desarrollo ya ejecutadas en el ciclo may-2026; testing e implementación parcialmente completados en staging/master_dev.*

---

## Configuración requerida (master_dev)

### Parámetros del sistema

| Clave | Valor Nakel | Uso |
|-------|-------------|-----|
| `nakel_barcode_wave_demand_mode.enable` | **`1`** | Activa semáforo y botones |
| `nakel_barcode_wave_demand_mode.apply_on` | `pick` | Solo CEN/PICK |
| `nakel_barcode_wave_demand_mode.warehouses` | vacío o `14` | Vacío = todos; `14` = solo CEN |
| `nakel_barcode_wave_demand_mode.log` | `1` | Chatter en ola |
| `nakel_barcode_wave_demand_mode.include_so_sibling_picks` | `1` | PICK hermanos OV |
| `nakel_barcode_wave_demand_mode.strict_batch` | `1` | Bloquea Barcode/validación si hay PICK ligados por trazabilidad pero fuera del batch oficial |
| `nakel_fix_pick.enable` | `1` | Sync Barcode |
| `nakel_fix_pick.barcode_soft_missing` | `1` | Mitiga errores JS |

---

## Documentación funcional — `nakel_barcode_wave_demand_mode`

### Problema

OV pide **10** u; reserva Odoo deja `stock.move.line.quantity = **1**`; Barcode topea en 1.

### Fase 1 (este módulo)

Botón **Modo demanda OV** en el formulario de la ola:

1. Busca PICK pendientes del **batch oficial** (`batch_id = ola`), **sin OUT**.
2. Opcional (ICP `include_so_sibling_picks=1`): **incorpora a la ola** otros PICK de las **mismas OV** que quedaron fuera (ej. sin reserva / PICK partido) y verifica que queden en `batch_id`.
3. Por cada `stock.move`: si `sum(quantity) < product_uom_qty`, sube `quantity` a la **demanda** (crea línea si no hay).
4. Opcional: chatter en la ola (ICP `log=1`).

**No** modifica `qty_done`, `picked`, ni valida. Después de pickear, seguir usando `nakel_fix_pick` / **SYNC Ola+OUT** si hace falta.

Con `nakel_fix_pick.enable=1`, el bump usa contexto `nakel_demand_mode_bump` para **no** marcar pickeado ni copiar reserva→done.

En **Odoo 18**, `write(quantity=…)` re-reserva y capa al stock disponible; este módulo escribe `quantity` por SQL en modo demanda para permitir tope = demanda OV aunque los quants no alcancen.

---

### Guardia batch oficial (v18.0.1.0.7)

Después del incidente **WAVE/00164**, se endurece la diferencia entre:

- `batch_id`: lote/ola oficial de Odoo; es lo seguro para Barcode.
- `nakel_wave_batch_id`: trazabilidad Nakel para relacionar OV/PICK/OUT.

Con `strict_batch=1`, la ola muestra **Barcode bloqueado** y no permite validar si quedan PICK pendientes con `nakel_wave_batch_id = ola` pero `batch_id != ola`.

Regla operativa:

1. Primero **Ver faltantes** / **Agregar a la ola**.
2. Luego **Modo demanda OV** si el semáforo lo pide.
3. Si aparece **Barcode bloqueado**, no abrir ni validar Barcode.
4. Tras agregar o aplicar modo demanda, el operario debe **cerrar y reabrir Barcode**.

Desde **v18.0.1.0.8**, si el semáforo está en **Cobertura OV** (`missing`), el header no muestra **Modo demanda OV**: el camino correcto es **Ver faltantes**. Modo demanda queda solo para amarillo (`needed`).

---

### Semáforo en la ola (v18.0.1.0.4 – 18.0.1.0.8)

Aparece en olas **WAVE/** (formulario de la ola, smart buttons arriba a la derecha).  
Requiere ICP `nakel_barcode_wave_demand_mode.enable = 1`.

#### Resumen rápido

| Color | Etiqueta | ¿Ir a Barcode? | Acción supervisor |
|-------|----------|----------------|-------------------|
| Verde | **Demanda OV — OK** | **Sí, ya** | Ninguna |
| Amarillo | **Modo demanda** | Después de ajustar | **Modo demanda OV** |
| Rojo | **Cobertura OV** | **No** | **Ver faltantes** → **Agregar a la ola** |
| Rojo | **Barcode bloqueado** | **No** | Incorporar PICK al batch oficial o corregir trazabilidad |

#### Regla de oro operarios

```text
Mirá el semáforo ANTES de abrir Barcode:
  Verde   → pickear
  Amarillo → Modo demanda OV → pickear
  Rojo    → NO pickear → avisar supervisor
```

---

#### Verde — Demanda OV OK

- Todas las líneas OV tienen PICK en el batch.
- `move.line.quantity` = pedido OV (`product_uom_qty`).
- No hay PICK hermanos fuera de la ola.

**No implica:** stock físico en góndola ni que ya se pickeó.

**Acción:** Barcode → cantidad real → validar PICK → OUT → facturar entregado.

---

#### Amarillo — Modo demanda

Causas: reserva &lt; pedido; línea sin reserva; PICK hermano fuera de ola.

**Acción:** Modo demanda OV → verde → Barcode.

**Efecto:** sube `quantity` a demanda OV; no mueve stock; `picked=False`.

---

#### Rojo — Cobertura OV

Faltan productos del pedido en la ola (sin PICK, PICK fuera, qty incompleta).

**No corrige:** pickear en Barcode ni Modo demanda solo.

**Acción:** Ver faltantes → Agregar a la ola (✓ modo demanda recomendado) → revisar semáforo.

| Motivo | Agregar a la ola |
|--------|------------------|
| Sin PICK generado | Sí |
| PICK fuera de la ola | Sí |
| Cantidad incompleta | Sí |
| Reserva menor al pedido | No → amarillo |

---

### Agregar faltantes a la ola (v18.0.1.0.6)

1. Marcá líneas agregables en **Ver faltantes**.
2. **Agregar a la ola** → relanza entrega Odoo y suma PICK al `batch_id` oficial.
3. Opcional: **Aplicar modo demanda después**.
4. Operario pickea en Barcode; qty 0 si no hay → no factura en OUT.

Si Odoo no logra incorporar un PICK al `batch_id` oficial, el proceso se bloquea con error. No alcanza con que el PICK quede solo en `nakel_wave_batch_id`.

---

### Impacto en stock

| Etapa | ¿Mueve `stock.quant`? |
|-------|------------------------|
| Modo demanda OV | **No** |
| Semáforo / planner | **No** |
| Barcode (qty_done) | **No** |
| Validar PICK / OUT | **Sí** |
| Factura | Según qty entregada |

---

## Documentación funcional — `nakel_wave_planner`

**Menú:** Inventario → Wave Transfers → **Armar ola por zona**

1. Zona(s) y/o vendedor(es) — varios a la vez.
2. Fecha opcional.
3. Buscar pedidos → checklist.
4. Crear WAVE + opcional Modo demanda.

---

## Criterios de aceptación

- [ ] Ola WAVE armada desde planificador con ≥20 OV sin error manual PICK por PICK.
- [ ] Semáforo visible con `enable=1` en olas WAVE.
- [ ] Ola con reserva parcial: amarillo → Modo demanda → Barcode tope = pedido OV.
- [ ] Ola con líneas sin PICK: rojo → Agregar a la ola → verde.
- [ ] Pickeo 0 u en Barcode no genera entrega/factura de esa línea.
- [ ] `nakel_fix_pick.enable=1` — líneas no quedan verdes sin escanear tras Modo demanda.
- [ ] Chatter legible (texto plano, sin HTML crudo).
- [ ] ICP documentados y configurados en master_dev.

---

## Checklist implementación

### Técnico

- [x] Instalar/upgrade módulos en master_dev
- [x] `nakel_barcode_wave_demand_mode.enable = 1`
- [x] `nakel_fix_pick.enable = 1`
- [ ] Upgrade `nakel_fix_pick` a 18.0.1.1.5 si master_dev en 1.1.4
- [ ] Reinicio Odoo post-deploy JS (`nakel_fix_pick`)

### Operativo

- [ ] Capacitar supervisores: semáforo + Ver faltantes
- [ ] Capacitar operarios: solo pickear con verde
- [ ] Probar 1 ola piloto en piso antes de uso masivo
- [ ] Publicar wiki FWHQ actualizada

### Casos de prueba ejecutados (staging)

| Ola | Resultado |
|-----|-----------|
| WAVE/00155 | 9 OV, 173 líneas, verde, demanda OK |
| WAVE/00156 | 39 OV, rojo→Agregar faltantes→verde, Barcode OK |

---

## Cuándo desactivar Modo demanda

Cuando quants CEN estén confiables: `enable = 0` y flujo estándar Odoo con `action_assign`.

---

## Referencias repo

```
nakel_odoo/addons/nakel_barcode_wave_demand_mode/
nakel_odoo/addons/nakel_wave_planner/
nakel_odoo/addons/nakel_wave_picking_link/
nakel_odoo/addons/nakel_fix_pick/
nakel_odoo/docs/inventario/BARCODE_OLA_FLUJO_MODULOS_Y_STOCK.md
```
