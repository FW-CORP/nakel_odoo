# Faltantes S04370 y S04372 (`master_dev`, lectura técnica)

**Fecha de análisis:** 2026-05-13.  
**Ola:** WAVE/00143 (`nakel_wave_batch_id` = 149).  
**Herramienta:** XML-RPC vía `config_nakel` (mismo entorno que `out_por_ov_master_dev.py`).

---

## 1. Resumen ejecutivo

| OV | Líneas de venta | Líneas almacenables con **falta de entrega** (`qty_delivered` &lt; `product_uom_qty`) | Hallazgo principal |
|----|----------------:|----------------:|----------------------|
| **S04370** | 49 | **12** | Varios productos tienen movimientos en **`cancel`** en el PICK **`CEN/PICK/04012`** (no llegaron a entregarse). Además hay **muchas** líneas donde la suma de `product_uom_qty` de movimientos **no cancelados** es **el doble** del pedido (`dem_moves ≈ 2 × pedido`) pero `qty_delivered` coincide con el pedido: típico de **cadena PICK + OUT** con dos patas de movimiento por la misma línea de venta (no implica “el doble pedido”, pero conviene revisión técnica). Hay **dos** OUT **`done`**: `CEN/OUT/02162` y `CEN/OUT/02169`. |
| **S04372** | 20 | **15** | Los faltantes coinciden con movimientos en **`cancel`** en **`CEN/PICK/04039`** (y dos en **`CEN/PICK/04013`**). El OUT **`CEN/OUT/02163`** está **`done`**, pero esas líneas **nunca** tuvieron movimiento efectivo hasta cliente (cancelados en recolecta). |

**Conclusión:** no es que el pedido “pida mal” la cantidad en la OV en general: lo que falló es la **cadena de stock** (recolectas / cancelaciones / cierre de ola). Para **agregar lo faltante** en sentido operativo hay dos frentes: (A) **reponer y volver a disparar entrega** en Odoo para esas líneas, o (B) **corregir datos** (líneas duplicadas, OUT duplicado, etc.) con soporte si el stock ya se movió mal.

---

## 2. S04370 — productos con falta real (`qty_delivered` &lt; pedido)

| `sale_line_id` | Producto (resumen) | Pedido | Entregado | Falta |
|----------------:|-------------------|-------:|----------:|------:|
| 104575 | BELDENT INFINIT CITRUS 15×7U | 1 | 0 | 1 |
| 104581 | MENTOS TUTTI FRUTTI ×12U | 1 | 0 | 1 |
| 104584 | OBLEA HAMLETON BLANCO 16×28G | 1 | 0 | 1 |
| 104593 | MEGA HAMLET MANI ×165G | 10 | 0 | 10 |
| 104606 | ALF.FULBITO RELL.CHOCOLATE 40×30G | 1 | 0 | 1 |
| 104608 | PIPAS GIGANTES ×160G | 12 | 2 | 10 |
| 104609 | PIPAS EXHIBIDOR GIGANTES 12×50G | 2 | 0 | 2 |
| 104613 | CHOCOLATINA EL TRIO ×300G | 24 | 0 | 24 |
| 104617 | PEPAS CHOCOTRIO EL TRIO ×500G | 20 | 0 | 20 |
| 104619 | PEPAS ALEMANAS EL TRIO ×500G | 20 | 0 | 20 |
| 104623 | CHOCOLATE MISKY LECHE 30×25G | 1 | 0 | 1 |
| 104628 | OBLEA OBLITA MIX FRUTAL ×100G | 48 | 0 | 48 |

**Pickings de la OV (referencia):** `CEN/PICK/04012` y `CEN/PICK/04038` (**done**); `CEN/OUT/02162` y `CEN/OUT/02169` (**done**).

Los ítems con entrega 0 aparecen en la lectura con **`stock.move` `cancel`** ligados al PICK **04012** (demanda original en ese albarán).

---

## 3. S04372 — productos con falta real

| `sale_line_id` | Producto (resumen) | Pedido | Entregado | Falta |
|----------------:|-------------------|-------:|----------:|------:|
| 104632 | LATITUD 33° MALBEC ×750ML | 30 | 0 | 30 |
| 104633 | POXI-RAN CHICO | 6 | 0 | 6 |
| 104634 | UNIPOX CHICO ×25ML | 6 | 0 | 6 |
| 104636 | BOBINA DE ARRANQUE MAPSA | 2 | 0 | 2 |
| 104637 | SUGUS ×700G | 1 | 0 | 1 |
| 104638 | FRUTOMILA SURTIDO ×500G | 1 | 0 | 1 |
| 104639 | CATCH POP ×8U | 1 | 0 | 1 |
| 104640 | TIVIS FELFORT 20×25G | 1 | 0 | 1 |
| 104643 | D.R.F. LIMON ×12U | 1 | 0 | 1 |
| 104644 | ALF.FANTOCHE TRIPLE NEGRO ×24U | 1 | 0 | 1 |
| 104645 | ALF.FANTOCHE TRIPLE BLANCO ×24U | 1 | 0 | 1 |
| 104646 | BUBBLE ROLL FUN CANDY SURTIDO ×8U | 1 | 0 | 1 |
| 104647 | CHERRY TRANSPARENTE MISKY ×405G | 1 | 0 | 1 |
| 104648 | LICORITAS 25×20G | 1 | 0 | 1 |
| 104649 | MILKA LEGER COMBINADO ×50G | 5 | 0 | 5 |

**Pickings de la OV:** `CEN/PICK/04013` y `CEN/PICK/04039` (**done**); `CEN/OUT/02163` (**done**).

En lectura, los movimientos de esas líneas constan como **`cancel`** en **`CEN/PICK/04039`** (y SUGUS / LICORITAS en **04013**).

---

## 4. Qué hacer para “agregar lo faltante” (orden sugerido)

1. **Depósito / piso:** preparar físicamente las cantidades de las tablas §2 y §3 (o acordar backorder / cancelación parcial comercial).
2. **Odoo (con usuario con permisos stock/ventas):**
   - Abrir cada OV → **Entregas** y revisar **PICK** con líneas `cancel` y el **OUT** ya `done` (no asumir que “OUT hecho = todo entregado”).
   - Según política Nakel: **nuevo traslado / nueva entrega** para la cantidad pendiente (p. ej. duplicar línea con qty 0 y relanzar abastecimiento, o ajuste de cantidades en OV + recomprobar disponibilidad); esto **no** está automatizado en este repo sin acuerdo de proceso.
3. **Técnico:** si persisten `dem_moves` ≈ **doble** del pedido en muchas líneas de S04370, revisar duplicidad de movimientos **PICK+OUT** y el segundo OUT **02169** para evitar doble facturación o stock incoherente.

---

## 5. Script de reapertura

Para **solo simular** OUT faltantes por OV (sin escribir): `nakel_odoo/tools/inventario/dry_run_simular_out_faltantes_por_ov.py`.  
Para **crear** un OUT manual (una OV, con cuidado): `nakel_odoo/tools/inventario/crear_out_faltante_por_ov_xmlrpc.py` (versión corregida: `sale_id` **después** de `action_confirm`; ver `wave143/README.md` §6.5).

No sustituyen **recrear** movimientos cancelados en PICK ni mercadería sin stock.
