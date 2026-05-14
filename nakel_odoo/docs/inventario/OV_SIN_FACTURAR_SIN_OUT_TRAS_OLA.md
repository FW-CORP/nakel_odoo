# OV «sin facturar» sin OUT tras ola / Barcode

## Por qué pasan juntas las dos cosas

En ventas con política basada en **entregado** (`qty_delivered`), si **no hay OUT** o el OUT **no está hecho** (`done`), Odoo suele dejar la OV en **`invoice_status = no`** (o sin camino claro para facturar lo entregado). No es un bug del módulo de ola: es la **cadena stock** (PICK → … → OUT) que no llegó a cerrar la entrega al cliente.

Las **11 OV** «sin facturar porque no tiene OUT» son coherentes con: PICK/ola validada **pero** la entrega cliente **no existe**, está **cancelada**, o sigue en **`waiting`** / **`assigned`** sin validar.

## Cómo saber si el PICK por Barcode «contó bien»

Revisar **por OV** (no solo la ola):

1. **Albarán PICK** de esa OV: estado `done` (¿realmente todo el picking quedó validado o hubo error a mitad?).
2. **Líneas detalladas** (`stock.move.line`): `quantity` vs **`qty_done`** (deberían alinearse tras un pick limpio); **`picked`** en true donde hay cantidad (si no, el progreso verde del Barcode puede mentir; existe **SYNC ola** en módulos Nakel).
3. **Movimientos** (`stock.move`): que no queden líneas en **`cancel`** inesperadas (stock en **Entrada** vs **Existencias** suele cancelar reservas; ver `DIAGNOSTICO_OLA_FALTANTES_POR_STOCK_EN_ENTRADA.md`).
4. ¿Existe **OUT** (`sequence_code` = OUT o nombre `CEN/OUT/...`) vinculado a la misma OV? Estado y si el **move** del OUT tiene demanda en cero por haberse cancelado el origen.

## Herramienta en repo (CSV por lista de OV)

Desde máquina con `config_nakel` y `ODOO_CONFIG_MASTER_DEV`:

```bash
cd /media/klap/raid5/cursor_files/nakel
python3 nakel_odoo/tools/inventario/out_por_ov_master_dev.py --dry-run --archivo-ov /ruta/lista_11_ov.txt
```

`lista_11_ov.txt`: una OV por línea (`S01234`). Genera CSV con OUTs y estados en `backups/` (ver cabecera del script).

Simulación **sin escritura** de «qué OUT manual implicaría» (líneas y cantidades): `nakel_odoo/tools/inventario/dry_run_simular_out_faltantes_por_ov.py` (misma conexión `config_nakel`; ver también `wave143/README.md` §6.4).

Con `--apply` solo si hay proceso acordado (el script advierte wizards).

## Orden operativo sugerido

1. Listar las **11 OV** y correr el script anterior (dry-run).
2. En Odoo, abrir **una** OV problemática → pestaña / smartbutton de **entregas** → dibujar la cadena PICK / PACK / OUT.
3. Si hay PICK `done` pero **sin OUT**: revisar **ruta del almacén** (pasos) y si algún movimiento previo quedó **cancel** o en **0** cantidad.
4. Si el problema es **picked / qty_done** desfasado tras Barcode: usar **SYNC** de ola en **PICK** (módulo `nakel_sync_ola` — **no** aplica a OUT desde 18.0.1.0.2) / pickings según runbooks de `nakel_fix_pick` y **no** revalidar a ciegas sin mirar líneas.

## Síntoma: «valido el PICK y no se crea el OUT»

Odoo **no siempre crea un OUT en el momento de validar** el PICK. Antes de asumir que falta el documento:

1. **Abrir la OV** (`Pedido de venta`) → smartbutton / pestaña **Entregas** (o lista de albaranes con el mismo `Origen` / número de OV).
2. Buscar un albarán tipo **Órdenes de entrega** (`CEN/OUT/…`) que ya exista en **`waiting`** o **`confirmed`**. Con almacén en **dos pasos** (`pick_ship`), el OUT suele **crearse al confirmar la venta** y queda esperando al PICK; al **terminar el PICK** pasa a **`assigned`** / listo para pickear o validar, **no** “nace” un OUT nuevo en ese instante.
3. Si en esa lista **solo** aparece el **PICK** y **ningún** `CEN/OUT/…` para esa OV: entonces el OUT **nunca se generó** (no es un tema de validar “más fuerte”). Causas típicas en Nakel Central:
   - **Rutas en el producto** (p. ej. Nak / sucursal) que dejan el flujo solo hasta **CEN/Salida** sin paso cliente (caso auditado abajo con **S04090**).
   - **Movimientos cancelados** o cantidad en cero en la cadena (p. ej. stock solo en **Entrada** y reserva fallida → `cancel` en `stock.move`; ver `DIAGNOSTICO_OLA_FALTANTES_POR_STOCK_EN_ENTRADA.md`).
   - Almacén en **un paso** (`ship_only`) vs esperabas dos pasos: no habría PICK separado del OUT de la misma forma.
4. Si hay **PACK** u otro paso intermedio en la cadena, el OUT puede seguir en **`waiting`** hasta cerrar ese paso.

**Regla práctica:** siempre diagnosticar desde la **OV** y el **`procurement.group`**, no solo desde el nombre del PICK en la ola.

## Cómo avanzar masivo (lista de OV / misma ola)

Objetivo: que cada OV tenga su **`CEN/OUT/…`** en cadena coherente con el **PICK** (y PACK si aplica), no «generar OUT a ciegas».

### 1) Clasificar: ¿la OV ya tiene OUT o no?

1. Usar el CSV del repo con tu lista de OV (ej. `lista_ov_wave143.txt`):

   ```bash
   cd /media/klap/raid5/cursor_files/nakel
   python3 nakel_odoo/tools/inventario/out_por_ov_master_dev.py --dry-run \
     --archivo-ov nakel_odoo/docs/inventario/incidencias/logistica/wave143/lista_ov_wave143.txt
   ```

2. Abrir el CSV en `backups/` y agrupar mentalmente:
   - **A — Hay al menos un OUT** (`CEN/OUT/…`): el documento **ya existe**; el trabajo es **operativo** (asignar / pickear / validar según estado), no «crear desde cero».
   - **B — Cero filas OUT** para esa OV: el OUT **no está en la base**; no lo va a crear el SYNC de ola ni validar más veces el PICK si la **ruta / reglas** no generan ese paso (mismo patrón que **S04090** más abajo).

### 2) Ramal A — Ya hay OUT

1. En Odoo: OV → **Entregas** / smartbutton **OUT** (`nakel_wave_picking_link`).
2. Orden típico: **PICK `done`** (o en curso coherente) → OUT en **`waiting`** pasa a **`assigned`** cuando el anterior paso queda listo → **Barcode o pantalla** en el OUT si hace falta alinear `qty_done` → **Validar** el OUT.
3. Si el OUT quedó **roto** por un SYNC masivo previo en líneas: revisar **operaciones detalladas** y corregir cantidades con criterio de piso; no hay regeneración automática documentada aquí.

### 3) Ramal B — No hay OUT (0 registros)

1. **No** hay en Odoo estándar un «Generar todos los OUT» fiable sin corregir la causa: suele ser **ruta en producto** (p. ej. Nak / sucursal) + **`stock.rule`** que deja el flujo en **CEN/Salida** sin paso a cliente, o movimientos **`cancel`** por stock en **Entrada** (ver enlaces arriba).
2. **Acción correcta:** tomar **una OV tipo B** y una **OV buena** del mismo almacén (que sí tenga `CEN/OUT/…`) y comparar en **Inventario → Rutas / reglas** y rutas en **ficha de producto** de las líneas del pedido.
3. Tras **corregir configuración**, el desbloqueo concreto (re-disparar abastecimiento, duplicar líneas de pedido, etc.) lo define **soporte técnico Odoo** según el cambio hecho; **no** recomendar desde repo acciones destructivas (cancelar venta, borrar movimientos) sin acuerdo explícito.

### 4) Validación masiva solo de OUT ya existentes

Si el CSV muestra OUT en `assigned` y el proceso lo permite, existe el script por ola (OV ligadas a `nakel_wave_batch_id`):

`nakel_odoo/tools/inventario/validar_out_por_ola_master_dev.py` (solo con `--apply` si hay acuerdo; suele chocar con wizards).

---

## Relación con el contador «OV sin facturar (ola)»

En `nakel_wave_picking_link`, el smartbutton usa `invoice_status = no` y `nakel_wave_batch_id` = esa ola. Cuenta **órdenes** en ese estado, no confirma por sí solo que el PICK esté bien contado: sirve como **lista de trabajo**, no como auditoría de líneas.

---

## Caso auditado: **S04090** (`master_dev`, 2026-05-09)

| Dato | Valor en BD |
|------|-------------|
| `sale.order` | id **4090**, `state` = **sale**, `invoice_status` = **no** |
| Almacén | **Nakel Central** (id 14), `delivery_steps` = **`pick_ship`** (2 pasos: Recolectar + Órdenes de entrega) |
| `procurement.group` | id **2690** (`S04090`) |
| **Pickings** con `group_id` = 2690 | **Solo uno:** `CEN/PICK/03851` (id **15143**), tipo **Recolectar**, `state` = **assigned** |
| **`stock.move`** ligados a líneas de venta 99061 / 99062 | **Solo 2 movimientos** (ids 234069, 234070), ambos en picking **15143**, `state` = **assigned**, ruta **CEN/Existencias → CEN/Salida** |
| **OUT** (`picking_type_id` = Órdenes de entrega / `origin` = S04090) | **Ninguno** en BD (total 0) |
| Pickings / movimientos **cancel** para esta OV | **Ninguno** |

Conclusión: **no es** que el OUT esté cancelado o oculto: para esta OV **nunca se generó** el segundo paso de entrega (no hay `stock.move` Salida → cliente). El almacén sigue configurado en **pick_ship**; las líneas no tienen `route_id` propio en la OV, pero los **productos** llevan rutas tipo *«Nak / Belgrano X: suministrar producto de Nakel Central»* que pueden interactuar con las reglas `stock.rule` y dejar solo el movimiento hasta **CEN/Salida** sin crear el envío a cliente.

**Reserva / Barcode:** los dos `stock.move` están **assigned** con `product_uom_qty` = `quantity` (12 y 6): a nivel de cantidad reservada coincide con la demanda; el PICK **no está validado** (`done`), coherente con ola mal cerrada respecto a este picking.

**Siguiente paso técnico (en Odoo UI):** Inventario → Configuración → Rutas / reglas del almacén **Nakel Central** y de las rutas **Nak / Belgrano** en los productos del pedido; comparar con una OV del mismo almacén que **sí** tenga `CEN/OUT/...` (p. ej. **S04155** en la misma ola 142) para ver qué regla crea el OUT allí y falta aquí.
