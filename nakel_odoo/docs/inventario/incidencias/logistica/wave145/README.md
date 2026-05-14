# Ola logística WAVE/00145 (“wave145”)

Documentación de referencia para la ola **WAVE/00145** en **Nakel Central**, consultada vía Odoo **master_dev** (MCP / XML-RPC).

| Campo | Valor |
|--------|--------|
| **Modelo** | `stock.picking.batch` |
| **ID registro (BD)** | **151** |
| **Nombre** | **WAVE/00145** |
| **Almacén** | Nakel Central (`warehouse_id` **14**) |
| **Estado (al documentar)** | `in_progress` |

**Fecha de esta nota:** 2026-05-13.

---

## 1. URL de Odoo vs “OLA 145” vs id interno

En URLs del cliente web Odoo suele aparecer el **id numérico del registro** del batch, no el sufijo del nombre `WAVE/00xxx`.

Ejemplo de patrón (entorno web Nakel):

`https://nakel.net.ar/odoo/inventory/.../151`

- El **`151`** al final corresponde al **id de `stock.picking.batch`** en bases alineadas con esta nomenclatura.
- Ese registro es **`WAVE/00145`**, no confundir con otro batch cuyo **id** sea distinto (p. ej. id **145** en `master_dev` es **`WAVE/00139`**, otra ola).

**Regla práctica:** validar siempre el **nombre** `WAVE/…` en pantalla o el **id** del formulario; los números de secuencia del nombre y el id de BD no coinciden en general.

---

## 2. Resumen ejecutivo — stock / reserva

Dominio usado en consultas: movimientos y líneas cuyo picking pertenece al batch **151** (`picking_id.batch_id = 151`).

### 2.1 `stock.move` (una fila por demanda de producto en el picking)

| Estado | Cantidad de líneas |
|--------|-------------------:|
| `assigned` | 1504 |
| `partially_available` | 8 |
| **Total** | **1512** |

- **Sin stock suficiente para cubrir toda la demanda de la línea:** **8** (`partially_available`).
- **Con reserva completa:** **1504** (`assigned`).
- No se observaron movimientos `cancel` en este dominio en la consulta.

### 2.2 `stock.move.line` (operaciones detalladas)

| Estado | Cantidad de líneas |
|--------|-------------------:|
| `assigned` | 1506 |
| `partially_available` | 8 |
| **Total** | **1514** |

La diferencia **1514 − 1512 = 2** líneas extra respecto a `stock.move` es coherente con que algunos movimientos se desglosen en **más de una** línea de operación (detalle por ubicación/lote, etc.), sin cambiar el conteo de líneas “en problema” (**8**).

> **Los totales anteriores son una instantánea** (misma mañana del 2026-05-13). Si cambian pickings del batch o el stock, los conteos **bajan o suben**. Para respaldo antes de validar, ver **[§9](#9-respaldo-pre-validación--error-de-validación--barcode-mayo-2026)** y el archivo [RESPALDO_PRE_VALIDACION_WAVE145_2026-05-13.md](RESPALDO_PRE_VALIDACION_WAVE145_2026-05-13.md).

---

## 3. Detalle — las 8 líneas con reserva incompleta

Criterio Odoo: estado **`partially_available`** (no se reserva el `product_uom_qty` completo desde la ubicación de origen del picking).

- **Demanda** = unidades pedidas en el movimiento de stock (`product_uom_qty`).
- **Reservado** = unidades que Odoo pudo reservar para ese PICK (`quantity` en el movimiento / línea; es lo que “hay” para pickear desde la ubicación de origen del picking).
- **Stock (catálogo)** = `free_qty` / cantidad a mano del **producto** en `master_dev` al documentar: sirve de referencia; si hay mercadería en **Entrada** u otra ubicación no usada por el PICK, puede haber “stock en sistema” pero **reserva parcial** en el recolectar (ver [DIAGNOSTICO_OLA_FALTANTES_POR_STOCK_EN_ENTRADA.md](../../DIAGNOSTICO_OLA_FALTANTES_POR_STOCK_EN_ENTRADA.md)).

### 3.1 Lista para cliente — revisar estos 8 (OV / Pick / demanda / reservado / stock ref.)

1. **OV `S04122`** — Pick **`CEN/PICK/04070`** — **[4106.60] TERMA SERRANO X1350ML.-318-** — Demanda **12** — Reservado **6** — Stock ref. (libre / a mano): **-9** / **27**
2. **OV `S04200`** — Pick **`CEN/PICK/04078`** — **[8654.00] FASTIX ALTA TEMPERATURA GRANDE X100ML.-1066-** — Demanda **12** — Reservado **2,12** — Stock ref.: **-6** / **20,12**
3. **OV `S04201`** — Pick **`CEN/PICK/03994`** — **[472.00] TABACO PACHAMAMA X30G.-019- (5)** — Demanda **5** — Reservado **4** — Stock ref.: **37** / **61**
4. **OV `S04295`** — Pick **`CEN/PICK/04083`** — **[3870.25] YERBA REI VERDE PREMIUM X500G.-711-** — Demanda **12** — Reservado **5** — Stock ref.: **102** / **113**
5. **OV `S04295`** — Pick **`CEN/PICK/04083`** — **[7304] YERBA MATE CANARIAS SERENA X500G.-038- (20)** — Demanda **6** — Reservado **1** — Stock ref.: **84** / **85**
6. **OV `S04321`** — Pick **`CEN/PICK/04085`** — **[553.40] BELDENT INFINIT BLUEBERRY 12X14U.-440-** — Demanda **3** — Reservado **1** — Stock ref.: **27** / **38**
7. **OV `S04329`** — Pick **`CEN/PICK/04086`** — **[1636.00] YERBA PLAYADITO X2KG.-041- (5)** — Demanda **50** — Reservado **7** — Stock ref.: **87** / **94**
8. **OV `S04329`** — Pick **`CEN/PICK/04086`** — **[BIZ0222] BRIGITTE 9 DE ORO CHOC.RELL.LIMON X120G.-135-** — Demanda **16** — Reservado **4** — Stock ref.: **25** / **29**

### 3.2 Tabla técnica (ids línea detalle / movimiento)

| `stock.move.line` id | `stock.move` id | OV (`origin`) | Picking | Producto | Demanda | Reservado |
|---------------------:|----------------:|:---------------|---------|----------|--------:|----------:|
| 234689 | 240433 | S04122 | CEN/PICK/04070 | [4106.60] TERMA SERRANO X1350ML.-318- | 12 | 6 |
| 235198 | 241032 | S04200 | CEN/PICK/04078 | [8654.00] FASTIX ALTA TEMPERATURA GRANDE X100ML.-1066- | 12 | 2,12 |
| 235205 | 241044 | S04201 | CEN/PICK/03994 | [472.00] TABACO PACHAMAMA X30G.-019- (5) | 5 | 4 |
| 235329 | 241195 | S04295 | CEN/PICK/04083 | [3870.25] YERBA REI VERDE PREMIUM X500G.-711- | 12 | 5 |
| 235331 | 241197 | S04295 | CEN/PICK/04083 | [7304] YERBA MATE CANARIAS SERENA X500G.-038- (20) | 6 | 1 |
| 235463 | 241348 | S04321 | CEN/PICK/04085 | [553.40] BELDENT INFINIT BLUEBERRY 12X14U.-440- | 3 | 1 |
| 235482 | 241368 | S04329 | CEN/PICK/04086 | [1636.00] YERBA PLAYADITO X2KG.-041- (5) | 50 | 7 |
| 235496 | 241383 | S04329 | CEN/PICK/04086 | [BIZ0222] BRIGITTE 9 DE ORO CHOC.RELL.LIMON X120G.-135- | 16 | 4 |

**Pickings afectados** (conteo de líneas `partially_available`):

| Picking | Líneas en problema |
|---------|-------------------:|
| CEN/PICK/04086 | 2 |
| CEN/PICK/04083 | 2 |
| CEN/PICK/04070 | 1 |
| CEN/PICK/04078 | 1 |
| CEN/PICK/03994 | 1 |
| CEN/PICK/04085 | 1 |

**IDs de pickings** (referencia): 15755, 15763, 15679, 15768, 15770, 15771.

---

## 4. IDs técnicos útiles (batch)

Lista de **pickings** incluidos en el batch **151** (referencia al momento de la consulta; si se regenera la ola en otra BD los IDs pueden variar):

`15747, 15661, 15748, 15662, 15749, 15663, 15750, 15664, 15751, 15665, 15752, 15666, 15753, 15667, 15754, 15668, 15755, 15669, 15756, 15670, 15757, 15671, 15758, 15672, 15759, 15673, 15674, 15760, 15675, 15761, 15676, 15762, 15677, 15763, 15678, 15679, 15764, 15680, 15765, 15681, 15766, 15682, 15767, 15683, 15768, 15684, 15769, 15685, 15770, 15686, 15771, 15687, 15772, 15688, 15773, 15689, 15690, 15691, 15774, 15692, 15775, 15693, 15776, 15694, 15777, 15695, 15778, 15696, 15779, 15702, 15780, 15703`

---

## 5. Contexto operativo y lecturas relacionadas

- Stock “visible” en catálogo pero **no reservable** en recolección (p. ej. mercadería en **Entrada** vs **Existencias**): ver [DIAGNOSTICO_OLA_FALTANTES_POR_STOCK_EN_ENTRADA.md](../../DIAGNOSTICO_OLA_FALTANTES_POR_STOCK_EN_ENTRADA.md).
- Cadena PICK/OUT y facturación tras olas: [OV_SIN_FACTURAR_SIN_OUT_TRAS_OLA.md](../../OV_SIN_FACTURAR_SIN_OUT_TRAS_OLA.md).

---

## 6. Nota sobre entornos

Los números de esta carpeta corresponden a lecturas en **`master_dev`**. En **producción** (`nakel.net.ar`) los **ids** pueden coincidir o no según migraciones; siempre cruzar por **`WAVE/00145`** o por el id mostrado en el formulario del batch.

---

## 7. Cómo reproducir la consulta (Odoo)

- Agrupar `stock.move` o `stock.move.line` con dominio: `[('picking_id.batch_id', '=', 151)]`, agrupar por `state`, medir `__count` / `id:count`.
- Filtrar `partially_available` para el detalle de SKUs y pickings.

---

## 8. Procedimiento recomendado (Barcode, SYNC, facturación)

Objetivo: evitar el escenario donde **“se pickeó toda la ola”** pero solo **parte** de las OV queda facturable (típico cuando la cadena **PICK → OUT** no queda coherente: OUT sin `done`, `qty_done` desfasado, rutas que no generan OUT, etc.). Ver [OV_SIN_FACTURAR_SIN_OUT_TRAS_OLA.md](../../OV_SIN_FACTURAR_SIN_OUT_TRAS_OLA.md).

### 8.1 ¿“Comprobar disponibilidad” antes del Barcode?

- **Si la ola ya tiene líneas detalladas y casi todo está `assigned`:** no es **obligatorio** volver a comprobar disponibilidad en toda la ola solo “por las dudas”; puede reordenar reservas sin aportar mucho y confundir al operario.
- **Las 8 líneas `partially_available` de esta ola:** “Comprobar disponibilidad” **no inventa stock**. Tiene sentido **después** de poner mercadería en la ubicación que usa el PICK (p. ej. de **Entrada** a **Existencias** en Central) y entonces **recomprobar** en los pickings afectados o donde indique supervisión. Ver [DIAGNOSTICO_OLA_FALTANTES_POR_STOCK_EN_ENTRADA.md](../../DIAGNOSTICO_OLA_FALTANTES_POR_STOCK_EN_ENTRADA.md).
- **Si algún picking siguiera sin operaciones detalladas** (caso raro en olas ya armadas): ahí sí aplica lo documentado en picking/PDF sobre usar **Comprobar disponibilidad** para generar `move_line_ids`.

**Resumen:** se puede **comenzar el picking por Barcode** sin tocar nada masivo; lo crítico es **decidir qué hacer con los 8 faltantes** (reponer / pickear parcial con criterio / backorder) según proceso comercial.

### 8.2 ¿“SYNC Ola+OUT” al terminar el Barcode?

El botón **SYNC Ola+OUT** (`nakel_sync_ola`) sobre pickings **pendientes** de la ola (desde **18.0.1.0.2** **no** toca albaranes **OUT**; solo PICK y demás traslados vinculados por `batch_id` / `nakel_wave_batch_id`):

1. Copia **`quantity` → `qty_done`** en líneas donde `qty_done` sigue en cero y `quantity` es positiva (misma lógica que [NAKEL_SYNC_QTY_DONE_BOTON.md](../../NAKEL_SYNC_QTY_DONE_BOTON.md)).
2. Marca **`picked = True`** donde había cantidad y el tilde quedó desfasado (ver [NAKEL_SYNC_PIKCED_OLA_BOTON.md](../../NAKEL_SYNC_PIKCED_OLA_BOTON.md)).

**No valida** traslados: después sigue siendo necesario **validar** PICK/OUT según el flujo del almacén.

**Recomendación:** sí, como **paso de supervisión antes de validar en bloque** en **recolectas** (o cuando el progreso del Barcode “miente” en el PICK): pulsar **SYNC Ola+OUT** y luego revisar **OUT** por OV en Barcode o pantalla estándar; el OUT no se alinea con este botón (forzarlo rompía cadena operativa). No sustituye validar ni corrige OV que **nunca** generaron OUT por ruta/configuración (caso auditado en `OV_SIN_FACTURAR…`).

### 8.3 Cierre y control para no repetir el “~60 % facturado”

1. Tras Barcode (+ SYNC si correspondió): en **varias OV al azar** de la ola, abrir la cadena de entregas y confirmar **CEN/OUT** (o equivalente) **creado y listo para validar / validado**, no solo el PICK.
2. Usar el **smartbutton / lista de OV sin facturar** ligada a la ola como **lista de trabajo**, no como prueba de que todo esté bien contado (`nakel_wave_picking_link`, ver doc OV citada arriba).
3. Opcional técnico: script `nakel_odoo/tools/inventario/out_por_ov_master_dev.py` en **dry-run** con lista de OV de la ola para CSV de OUTs y estados.

**Regla de oro:** el desastre de facturación parcial casi siempre es **cadena de stock / OUT**, no “tocar de menos” el SYNC. SYNC ayuda cuando **`qty_done`** o **`picked`** quedaron desalineados respecto a lo que Barcode mostró; no crea OUTs faltantes por reglas de ruta.

---

## 9. Respaldo pre-validación / error de validación / Barcode (mayo 2026)

Cuando la ola tiene **muchas líneas** (~1500+) y en piso “está todo contado” pero Odoo **rechaza validar** o el progreso no refleja el piso, conviene tener **CSV + conteos** en disco antes de pulsar de nuevo **Validar**.

### 9.1 Lecturas recientes (2026-05-13, `master_dev`) — el batch sigue mutando

Dominio: `[('picking_id.batch_id', '=', 151)]`.

En **pocos minutos** cambió el número de pickings en el batch (operarios o sistema moviendo albaranes). Por eso los totales **no** van a coincidir con el **§2** histórico (**1512 / 1514**) ni con el “~1513 líneas” que comentás en chat: hay que anclar siempre al **CSV con timestamp**.

**Instantánea B — script `export_wave_pickings_ov_csv.py` (2026-05-13 11:39:30, archivos `wave_00145_batch151_*_20260513_113930.csv`):**

| Métrica | Valor |
|---------|------:|
| Pickings en el batch | **65** (63 `assigned`, 2 `confirmed`) |
| `stock.move` total | **1423** |
| `stock.move` `assigned` / `partially_available` / `confirmed` | **1364** / **8** / **51** |
| `stock.move.line` total | **1374** |
| Líneas con `quantity > 0` y `qty_done = 0` | **1374** (= todas las líneas detalladas con `quantity` → **nada persistido como hecho** en BD) |
| Líneas con `quantity > 0` y `picked = False` | **1371** |
| OV distintas (`sale_id` en pickings) | **36** |

**Instantánea A — misma lógica ~3 min antes (CSV manual `wave145_batch151_*_20260513_113739.csv`):** **68** pickings, **1467** `stock.move`, **1418** `stock.move.line`, brecha `qty_done` **1418/1418**, **37** OV. Sirve de prueba de que **el batch se estaba editando** entre una corrida y la otra.

La discrepancia con el **§2** de esta carpeta (**1512 / 1514**, más pickings listados) es **otra fecha/hora de lectura**; las **8** líneas `partially_available` se mantienen como foco de validación.

### 9.2 Documento narrativo + procedimiento

Ver **[RESPALDO_PRE_VALIDACION_WAVE145_2026-05-13.md](RESPALDO_PRE_VALIDACION_WAVE145_2026-05-13.md)** (enlace a [Diagnostico.md](../../Diagnostico.md), SYNC `qty_done` / `picked`, las **8** `partially_available`).

### 9.3 Regenerar CSV (script en repo)

```bash
cd /media/klap/raid5/cursor_files/nakel
python3 nakel_odoo/tools/inventario/export_wave_pickings_ov_csv.py --batch-id 151
# o:
python3 nakel_odoo/tools/inventario/export_wave_pickings_ov_csv.py --name WAVE/00145
```

Escribe en `/media/klap/raid5/cursor_files/backups/` dos CSV (pickings + OV) e imprime por consola los mismos conteos que arriba.

---

## 10. Faltantes en hoja de picking (F / X) — cuadro unificado

Marcas **F** / **X** en las hojas impresas de **WAVE/00145** (yerbas, bebidas, etc.), cruzadas con **OV / PICK / OUT** en `master_dev` (`nakel_wave_batch_id = 151`).

**Documento detallado:** [FALTANTES_HOJA_PICKEO_WAVE145.md](FALTANTES_HOJA_PICKEO_WAVE145.md) (págs. **7**, **9**, **11**–**19**, **22**–**25**, **26**–**27**, **28**–**29**, **31**–**43**, **45**–**51**, **53**–**54**, **55**–**56** / 61 y siguientes que aportes; tabla única + notas).
