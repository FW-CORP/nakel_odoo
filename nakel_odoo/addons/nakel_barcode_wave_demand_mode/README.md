# nakel_barcode_wave_demand_mode

Puente operativo para **olas + Barcode** cuando el inventario Odoo no refleja el piso.

## Problema

OV pide **10** u; reserva Odoo deja `stock.move.line.quantity = **1**`; Barcode topea en 1.

## Fase 1 (este módulo)

Botón **Modo demanda OV** en el formulario de la ola:

1. Busca PICK pendientes (`batch_id` o `nakel_wave_batch_id`), **sin OUT**.
2. Opcional (ICP `include_so_sibling_picks=1`): **incorpora a la ola** otros PICK de las **mismas OV** que quedaron fuera (ej. sin reserva / PICK partido).
3. Por cada `stock.move`: si `sum(quantity) < product_uom_qty`, sube `quantity` a la **demanda** (crea línea si no hay).
3. Opcional: chatter en la ola (ICP `log=1`).

**No** modifica `qty_done`, `picked`, ni valida. Después de pickear, seguir usando `nakel_fix_pick` / **SYNC Ola+OUT** si hace falta.

Con `nakel_fix_pick.enable=1`, el bump usa contexto `nakel_demand_mode_bump` para **no** marcar pickeado ni copiar reserva→done.

**Semáforo en la ola** (desde v18.0.1.0.4, ampliado en 18.0.1.0.6):

Aparece en olas **WAVE/** (formulario de la ola, arriba a la derecha, junto a los smart buttons).  
Requiere ICP `nakel_barcode_wave_demand_mode.enable = 1`.

### Resumen rápido

| Color | Etiqueta en pantalla | ¿Ir a Barcode? | Acción del supervisor |
|-------|----------------------|----------------|------------------------|
| 🟢 Verde | **Demanda OV — OK** | **Sí, ya** | Ninguna |
| 🟡 Amarillo | **Modo demanda** | Después de ajustar | **Modo demanda OV** |
| 🔴 Rojo | **Cobertura OV** | **No** (ola incompleta) | **Ver faltantes** → **Agregar a la ola** |

### Regla de oro para operarios

```text
Mirá el semáforo ANTES de abrir Barcode:
  Verde   → pickear
  Amarillo → Modo demanda OV → pickear
  Rojo    → NO pickear → avisar supervisor
```

---

### 🟢 Verde — Demanda OV OK

**Qué significa**

- Todas las líneas de producto de las **OV de la ola** tienen operación **PICK** dentro del batch.
- En cada línea PICK, la cantidad que Barcode usa como tope (`stock.move.line.quantity`) **coincide con el pedido OV** (`product_uom_qty`).
- No hay PICK hermanos de esas OV pendientes **fuera** de la ola (si ICP `include_so_sibling_picks=1`).

**Qué NO implica**

- No significa que el stock físico exista (Odoo puede decir una cosa y el piso otra).
- No ejecuta Modo demanda OV solo por estar verde.
- No garantiza que ya se pickeó: solo que **la ola está lista para pickear**.

**Acción**

1. Abrir **Barcode** con la ola WAVE/xxxxx.
2. Pickear **cantidad real** (0 si no hay en depósito).
3. Validar PICK / ola según proceso Nakel.
4. **OUT** y factura según lo **entregado** (`qty_done`), no según stock teórico Odoo.

**Botones visibles**

- Smart button verde **Demanda OV — OK**.
- **No** aparece el botón naranja **Modo demanda OV** en el header (no hace falta).

---

### 🟡 Amarillo — Modo demanda

**Qué significa**

Hay productos **ya en la ola**, pero algo impide pickear al tope del pedido OV:

| Causa | Ejemplo |
|-------|---------|
| Reserva Odoo &lt; pedido OV | OV pide 10, `quantity` en línea = 1 |
| Línea PICK sin reserva | Move existe pero sin `move_line_ids` |
| PICK hermano fuera de la ola | Misma OV, otro `CEN/PICK/` no sumado al batch |

**Qué NO es**

- No es “falta producto en Odoo” (eso es rojo).
- Pickear en Barcode **sin** arreglar esto → el operario ve tope bajo (ej. 1/10).

**Acción**

1. Tocar **Modo demanda OV** (header naranja o smart button amarillo).
2. Esperar notificación / revisar chatter.
3. Semáforo debería pasar a **verde**.
4. Ir a **Barcode**.

**Qué hace Modo demanda OV**

- Sube `quantity` de líneas PICK al **`product_uom_qty`** del pedido (demanda OV).
- Opcionalmente agrega PICK hermanos de la misma OV al batch (ICP).
- **No** marca pickeado (`picked=False`); **no** valida; **no** mueve stock real.

---

### 🔴 Rojo — Cobertura OV

**Qué significa**

Faltan productos del **pedido de venta** en la ola. Barcode **no puede** mostrarlos porque no hay operación PICK (o no está en este batch).

El subtítulo del semáforo detalla el caso, por ejemplo:

- `19 sin PICK en Odoo` — Odoo nunca generó la transferencia PICK para esa línea OV.
- `3 en PICK fuera de ola` — el PICK existe pero no está en el WAVE.
- `2 incompletos en ola` — hay move pero cantidad menor al pedido.

**Qué NO corrige el rojo**

| Acción | ¿Apaga el rojo? |
|--------|-----------------|
| Pickear en Barcode | **No** |
| Modo demanda OV | **No** (no hay línea que ajustar) |
| Validar otros PICK de la ola | **No** |

**Acción**

1. Botón **Ver faltantes** (header o smart button rojo).
2. Revisar tabla: OV, producto, **Pide OV**, **En ola**, **Motivo**, **Qué hacer**.
3. Marcar líneas agregables → **Agregar a la ola**.
4. Recomendado: ✓ **Aplicar modo demanda después**.
5. Revisar semáforo otra vez (verde o amarillo).

**Motivos en “Ver faltantes”**

| Motivo | Significado | ¿Agregar a la ola? |
|--------|-------------|-------------------|
| Sin PICK generado | OV pide producto; Odoo no creó move/PICK | **Sí** — relanza entrega |
| PICK fuera de la ola | PICK existe en otra ola o sin batch | **Sí** — suma PICK al WAVE |
| Cantidad incompleta en ola | Move en ola con qty &lt; pedido | **Sí** — intenta relanzar |
| Reserva menor al pedido | Ya en ola; tema de reserva | **No** — usar Modo demanda (amarillo) |

**Después de agregar**

- Si pasa a **verde** → Barcode.
- Si pasa a **amarillo** → Modo demanda OV → Barcode.

---

### Flujo completo (supervisor + operario)

```text
Armar ola (planificador WAVE)
        ↓
   ¿Semáforo?
        ↓
   ROJO → Ver faltantes → Agregar a la ola → revisar de nuevo
        ↓
   AMARILLO → Modo demanda OV
        ↓
   VERDE → Operario: Barcode → pickear cantidad real
        ↓
   Validar PICK / ola → OUT → facturar lo entregado
```

---

### Preguntas frecuentes

**¿Pickear pone el semáforo verde?**  
No. El semáforo controla **preparación de la ola**, no el avance del pickeo. Tras bajar cantidades en Barcode puede seguir **amarillo** (reserva Odoo &lt; pedido); **igual podés validar** si ya contaste en piso (v18.0.1.0.15+).

**¿Validar con 6/10 u o cero en piso?**  
Sí. Si el operario bajó `qty_done` (stock real), la ola **no debe** pedir Modo demanda OV solo para desbloquear validar. **No** uses Modo demanda después de contar: re-armaría cantidades al pedido OV.

**¿Amarillo + Validar sin Modo demanda?**  
Correcto cuando ya pickearon. Modo demanda OV es **antes** de pickear (reserva Odoo baja). Después de contar → **Validar** directo.

**¿Verde = stock real en góndola?**  
No. Verde = “en Odoo la ola refleja el pedido OV”. El operario confirma existencia en Barcode.

**¿Siempre Modo demanda antes de Barcode?**  
No. Solo si está **amarillo**, o al agregar faltantes si no marcaste “Aplicar modo demanda después”.

**¿Dónde se ve?**  
Solo en olas **WAVE/** (`is_wave=True`), con el módulo instalado e ICP activo.

---

No hace falta usar Modo demanda en olas verdes (ej. todo `assigned` con stock completo).

## Agregar faltantes a la ola (v18.0.1.0.6)

Desde **Ver faltantes** (semáforo rojo):

1. Marcá líneas con motivo *Sin PICK generado* o *PICK fuera de la ola*.
2. **Agregar a la ola** → relanza entrega Odoo (`_action_launch_stock_rule`) y suma el PICK al batch.
3. Opcional: **Aplicar modo demanda después** (tope Barcode = pedido OV).
4. El operario pickea en Barcode; cantidad 0 si no hay en depósito → no factura esa línea en el OUT.

En **Odoo 18**, `write(quantity=…)` re-reserva y capa al stock disponible; este módulo escribe `quantity` por SQL en modo demanda para permitir tope = demanda OV aunque los quants no alcancen.

## Guardia estricta de batch oficial (v18.0.1.0.7)

Desde esta versión, el flujo operativo diferencia dos conceptos:

- `batch_id`: pertenencia real al lote/ola estándar de Odoo. Es lo que debe usar Barcode para operar.
- `nakel_wave_batch_id`: trazabilidad Nakel para unir OV, PICK y OUT aunque Odoo ya no los liste en `picking_ids`.

Con `nakel_barcode_wave_demand_mode.strict_batch = 1` (default), la ola queda **bloqueada para Barcode/validación** si hay PICK pendientes vinculados por trazabilidad pero fuera del lote oficial.

El bloqueo evita operar sobre una ola mixta como:

```text
PICK A: batch_id = WAVE/xxxxx        ← seguro para Barcode
PICK B: nakel_wave_batch_id = WAVE   ← trazabilidad, pero fuera del batch oficial
```

Regla operativa:

1. Ejecutar **Ver faltantes** / **Agregar a la ola**.
2. Confirmar que el botón/semáforo no muestre **Barcode bloqueado**.
3. Ejecutar **Modo demanda OV** si corresponde.
4. Pedir al operario **cerrar y reabrir Barcode** antes de empezar o validar.

Si el sistema no puede incorporar un PICK al `batch_id` oficial, muestra un error y no continúa con Modo demanda.

### Ajuste UX v18.0.1.0.8

Cuando la ola está en **Cobertura OV** (`missing`), el botón **Modo demanda OV** deja de mostrarse en el header. Ese estado se resuelve con **Ver faltantes** porque Modo demanda solo ajusta PICK existentes.

El bloqueo **Barcode bloqueado** queda reservado para el caso específico de PICK pendientes trazados por `nakel_wave_batch_id` pero fuera del `batch_id` oficial. La validación de la ola sigue bloqueando también cobertura incompleta o demanda pendiente.

## Activación

Parámetros del sistema (Técnico):

| Clave | Default | Uso |
|-------|---------|-----|
| `nakel_barcode_wave_demand_mode.enable` | `0` | `1` = muestra botón y permite ejecutar |
| `nakel_barcode_wave_demand_mode.apply_on` | `pick` | `pick` = solo CEN/PICK; `non_out` = todo excepto OUT |
| `nakel_barcode_wave_demand_mode.warehouses` | vacío | CSV de IDs almacén, ej. `14` |
| `nakel_barcode_wave_demand_mode.log` | `1` | Mensaje en chatter de la ola |
| `nakel_barcode_wave_demand_mode.include_so_sibling_picks` | `1` | `1` = agrega a la ola PICK hermanos de las mismas OV antes de aplicar |
| `nakel_barcode_wave_demand_mode.strict_batch` | `1` | Bloquea Barcode/validación si hay PICK trazados fuera del `batch_id` oficial |

## Dependencias

- `stock_picking_batch`
- `nakel_wave_picking_link` (`nakel_wave_batch_id`, `_nakel_is_out_picking`)

## Instalación (master_dev)

1. Actualizar lista de apps e instalar **Nakel Barcode Ola — Modo demanda OV**.
2. Poner `nakel_barcode_wave_demand_mode.enable = 1`.
3. En ola con PICK parcialmente reservados → **Modo demanda OV** → abrir Barcode y verificar tope 10.

## Cuándo desactivar

Cuando quants CEN estén confiables: `enable = 0` y re-asignar pickings (`action_assign`) en flujo estándar.

## Planning

Ver `nakel_odoo/docs/inventario/BARCODE_OLA_MODO_DEMANDA_PLAN.md`.
