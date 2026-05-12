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

Con `--apply` solo si hay proceso acordado (el script advierte wizards).

## Orden operativo sugerido

1. Listar las **11 OV** y correr el script anterior (dry-run).
2. En Odoo, abrir **una** OV problemática → pestaña / smartbutton de **entregas** → dibujar la cadena PICK / PACK / OUT.
3. Si hay PICK `done` pero **sin OUT**: revisar **ruta del almacén** (pasos) y si algún movimiento previo quedó **cancel** o en **0** cantidad.
4. Si el problema es **picked / qty_done** desfasado tras Barcode: usar **SYNC** de ola / pickings según runbooks de `nakel_sync_ola` / `nakel_fix_pick` y **no** revalidar a ciegas sin mirar líneas.

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
