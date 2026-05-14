# Ola logística WAVE/00143 (“wave143”) — incidente post-Barcode

Documentación de referencia para la ola **WAVE/00143** en **Nakel Central**, consultada vía Odoo **master_dev** (MCP / XML-RPC).

| Campo | Valor |
|--------|--------|
| **Entorno** | Base **`master_dev`** en **`https://nakel.net.ar`** (no usar `https://dev.nakel.net.ar` para este caso). |
| **Modelo** | `stock.picking.batch` |
| **ID registro (BD)** | **149** |
| **Nombre** | **WAVE/00143** |
| **Estado (al documentar el incidente)** | `done` (ola validada en Barcode) |

**Fecha de esta nota:** 2026-05-13. **Última actualización:** 2026-05-14 — listado de **16 OV** + diagnóstico OUT en `master_dev` (§6.3). **2026-05-14 (tarde)** — lectura XML-RPC: **18** `sale.order` con `nakel_wave_batch_id = 149`; explicación filtros “solo veo 2 / 3 OV” en **§8**. **2026-05-13** — sync manual en pickings.

---

## 1. Resumen ejecutivo

Tras refrescar Barcode y **validar la ola**, el batch quedó en **`done`**, pero solo **2 de 32** `stock.picking` asociados quedaron en **`done`** con `date_done` coherente; el resto siguió **`assigned`**, muchos con **`batch_id` vacío** pero **`nakel_wave_batch_id = 149`**.

Efecto operativo: el conteo en piso puede haber estado alineado con lo **reservado** (`quantity`), pero **`qty_done` / `picked`** no se reflejaron en todos los albaranes antes del cierre de la ola → riesgo de “perdimos el conteo” en pantalla aunque el stock reservado siga siendo el esperado.

**Mitigación técnica (código):** el botón **SYNC Ola+OUT** (`nakel_sync_ola`) ya **no se oculta** cuando la ola está `done`/`cancel`, para poder alinear `quantity → qty_done` y `picked` en los PICK pendientes **sin reabrir** la ola. Desde **`nakel_sync_ola` 18.0.1.0.2** ese botón **deja de tocar albaranes OUT** (`CEN/OUT/…`): solo PICK (y otros no-OUT), porque forzar `qty_done`/`picked` en OUT rompía la cadena respecto al Barcode.

**Mitigación operativa:** pulsar **SYNC Ola+OUT** sobre el batch **149** (o ejecutar el script XML-RPC listado abajo) y luego **validar** los albaranes según proceso. El SYNC **no valida** traslados.

---

## 2. Hallazgos en `master_dev` (momento del incidente)

- **`stock.picking.batch` id 149**, nombre **`WAVE/00143`**, estado **`done`**.
- **2** pickings en **`done`** con `date_done` **2026-05-13 13:04:07 UTC**:
  - **`CEN/PICK/04012`** (id **15697**, OV **S04370**)
  - **`CEN/PICK/04039`** (id **15724**, OV **S04372**)
- **30** pickings restantes de la ola en **`assigned`**, `batch_id` típicamente **vacío**, con **`nakel_wave_batch_id = 149`** en varios casos.

### 2.1 Lista de ids de pickings usada en el análisis (32)

`15715, 15423, 15716, 15439, 15717, 15465, 15718, 15620, 15719, 15624, 15720, 15632, 15647, 15721, 15657, 15658, 15659, 15722, 15660, 15723, 15697, 15724, 15698, 15725, 15700, 15701, 15726, 15708, 15727, 15709, 15728, 15711`

*(Los dos primeros `done` en la lista son **15697** y **15724**.)*

---

## 3. Lecturas relacionadas

- [NAKEL_SYNC_QTY_DONE_BOTON.md](../../NAKEL_SYNC_QTY_DONE_BOTON.md) — copia `quantity → qty_done` donde `qty_done` sigue en cero.
- [NAKEL_SYNC_PIKCED_OLA_BOTON.md](../../NAKEL_SYNC_PIKCED_OLA_BOTON.md) — tilde `picked` alineado a cantidad.
- [OV_SIN_FACTURAR_SIN_OUT_TRAS_OLA.md](../../OV_SIN_FACTURAR_SIN_OUT_TRAS_OLA.md) — cadena PICK/OUT y facturación.
- Bug Barcode / líneas borradas (contexto de desalineación): [BUG_BARCODE_REGISTRO_FALTANTE_stock_move_line_borrada_master_dev_2026-04-29.md](../../../../incidentes/BUG_BARCODE_REGISTRO_FALTANTE_stock_move_line_borrada_master_dev_2026-04-29.md).

---

## 4. Sync masivo sin ir picking por picking

### 4.1 Desde Odoo (recomendado tras desplegar `nakel_sync_ola` 18.0.1.0.1+)

Abrir el formulario del batch **WAVE/00143** (id **149**) y pulsar **SYNC Ola+OUT** aunque la ola figure **`done`**.

### 4.2 Desde consola (XML-RPC)

Script: `nakel_odoo/tools/inventario/sync_qty_done_nakel_wave_batch_xmlrpc.py`

```bash
cd /media/klap/raid5/cursor_files/nakel
python3 nakel_odoo/tools/inventario/sync_qty_done_nakel_wave_batch_xmlrpc.py --batch-id 149 --dry-run
python3 nakel_odoo/tools/inventario/sync_qty_done_nakel_wave_batch_xmlrpc.py --batch-id 149
```

Requiere en el `.env` (o en el entorno) las variables `ODOO_MASTER_DEV_URL`, `ODOO_MASTER_DEV_DB`, `ODOO_MASTER_DEV_USERNAME`, `ODOO_MASTER_DEV_PASSWORD`. Para **esta** base, **`ODOO_MASTER_DEV_URL`** debe ser **`https://nakel.net.ar`** y **`ODOO_MASTER_DEV_DB`** debe ser **`master_dev`** (el prefijo `ODOO_MASTER_DEV_*` es solo convención del repo; no implica el host `dev.`).

---

## 5. Nota sobre entornos

Los números corresponden a lecturas en **`master_dev`** servido desde **`https://nakel.net.ar`**. No confundir con **`https://dev.nakel.net.ar`**, que suele llevar otras bases (p. ej. pruebas). En otra instancia los **ids** pueden diferir; cruzar siempre por **`WAVE/00143`** o el id del formulario del batch.

---

## 6. OV ligadas a **WAVE/00143** (listado operativo)

Origen: pegado desde listado en Odoo / planilla (fechas y montos tal cual llegaron). Sirve para cruzar con **entregas / OUT** y facturación (ver [OV_SIN_FACTURAR_SIN_OUT_TRAS_OLA.md](../../OV_SIN_FACTURAR_SIN_OUT_TRAS_OLA.md)).

**Archivo para scripts** (una OV por línea): [`lista_ov_wave143.txt`](lista_ov_wave143.txt) — **18** OV (incluye **S04291** y **S04302** detectadas en BD con `nakel_wave_batch_id = 149`; ver **§8**).

| OV | Fecha/hora (listado) | Cliente / sucursal (texto) | Vendedor | Fecha entrega (listado) |
|:---|:---------------------|:---------------------------|:---------|:------------------------|
| S04381 | 13/05/2026 03:37:37 | GOICOECHEA JM GJI Y GXM - AXION EL CRUCE | Choque Jorge Ariel | 20/05/2026 |
| S04377 | 13/05/2026 03:32:34 | GOICOECHEA JM GJI Y GXM - AXION EL CRUCE | Choque Jorge Ariel | 20/05/2026 |
| S04373 | 13/05/2026 02:21:22 | CHOQUE JORGE ARIEL - SPIRIT | Choque Jorge Ariel | 20/05/2026 |
| S04368 | 13/05/2026 02:19:07 | CHOQUE JORGE ARIEL - SPIRIT | Choque Jorge Ariel | 19/05/2026 |
| S04372 | 12/05/2026 22:59:39 | OLIVAREZ JAVIER ANTONIO - MONTSERRAT | Delgado Hector Daniel | 19/05/2026 |
| S04370 | 12/05/2026 22:28:22 | WENG SHUIZHI - SUPER DIAMANTE | Delgado Hector Daniel | 19/05/2026 |
| S04347 | 12/05/2026 21:49:18 | LI LIJUAN - PANDA SUPERMERCADO | Delgado Hector Daniel | 19/05/2026 |
| S04350 | 12/05/2026 21:44:05 | QUISPE JUAN CARLOS - ALMACEN 10 DE NOVIEMBRE | Hernandez Carlos Alberto | 19/05/2026 |
| S04352 | 12/05/2026 21:43:44 | CRESPIN CECILIA ISABEL, PALETONA I - MAXIMO ABASOLO | Hernandez Carlos Alberto | 19/05/2026 |
| S04354 | 12/05/2026 21:43:32 | CARCAMO PEDRO RIGOBERTO - ALMACEN RIGO | Hernandez Carlos Alberto | 19/05/2026 |
| S04351 | 12/05/2026 19:04:35 | SUCESION DE RODRIGUEZ HAYDEE JULIA - FERRETERIA MIL COSAS | Chirimonti Jose Luis | 19/05/2026 |
| S04335 | 12/05/2026 18:03:30 | SUCESION DE RODRIGUEZ HAYDEE JULIA - FERRETERIA MIL COSAS | Chirimonti Jose Luis | 19/05/2026 |
| S04332 | 12/05/2026 17:48:12 | GONZALEZ ORONO JUAN CARLOS - SANIGAS PUEYRREDÓN | Chirimonti Jose Luis | 19/05/2026 |
| S04331 | 12/05/2026 17:43:43 | FERNANDO COELHO DE JESUS Y PATRICIA COELHO DE JESUS SOCIEDAD DE HECHO - TODO GOMA AKAPOL | Chirimonti Jose Luis | 19/05/2026 |
| S04301 | 12/05/2026 13:51:09 | WALKER MONICA INES - PASEO DE COMPRAS MIRADA DE ANGEL | Delgado Hector Daniel | 19/05/2026 |
| S04297 | 12/05/2026 12:55:25 | BRITO ELBA GLADYS - MINI MERCADO DON JULIO | Delgado Hector Daniel | 19/05/2026 |

Además, en `master_dev` figuran con `nakel_wave_batch_id = 149` las OV **S04291** y **S04302** (no estaban en el pegado original; están en `lista_ov_wave143.txt` y en **§8**).

Montos del listado original (Nakel SA, total aprox.): no se repiten aquí para mantener la tabla liviana; están en el origen del pegado.

### 6.1 CSV de OUT por estas OV (herramienta repo)

Con `config_nakel` / `ODOO_CONFIG_MASTER_DEV` apuntando a **`nakel.net.ar`** + **`master_dev`**:

```bash
cd /media/klap/raid5/cursor_files/nakel
python3 nakel_odoo/tools/inventario/out_por_ov_master_dev.py \
  --dry-run \
  --archivo-ov nakel_odoo/docs/inventario/incidencias/logistica/wave143/lista_ov_wave143.txt
```

Genera CSV bajo `backups/` con estados de **OUT** por OV (útil para ver quién quedó sin `CEN/OUT` o con OUT trabado).

### 6.2 Siguiente paso: «generar» o cerrar todos los OUT

No hay un paso único mágico: primero **clasificar** cada OV (¿ya tiene OUT o no?) con el CSV y el procedimiento de [OV_SIN_FACTURAR_SIN_OUT_TRAS_OLA.md](../../OV_SIN_FACTURAR_SIN_OUT_TRAS_OLA.md) (sección **«Cómo avanzar masivo»**). Ramal con OUT existente = operar/validar cadena; ramal sin OUT = revisar **rutas/reglas** antes de intentar regenerar documentos.

### 6.3 Diagnóstico en `master_dev` (lectura 2026-05-14, MCP)

Sobre las **18 OV** de `lista_ov_wave143.txt`:

| Situación | OV | Notas |
|-----------|----|--------|
| **Ya tienen `CEN/OUT/…`** (estado `assigned` al leer) | **S04370**, **S04372**, **S04377**, **S04373** | El OUT **ya está creado**. No hace falta «generarlo»: falta **operar** (PICKs pendientes si los hay, luego **validar / despachar** el OUT en Barcode o formulario). |
| **Sin OUT** (solo `CEN/PICK/…` en `picking_ids`) | **S04297**, **S04301**, **S04331**, **S04332**, **S04335**, **S04347**, **S04351**, **S04352**, **S04350**, **S04354**, **S04368**, **S04381** | Patrón tipo **S04090** en `OV_SIN_FACTURAR…`: los `stock.move` del recolectar llevan **`location_dest_id` = CEN/Salida** y **no** se generó la pata **Salida → Clientes**. **No** se puede crear el OUT fiable «por API» sin corregir **rutas/reglas** (y luego un reintento técnico supervisado en Odoo). |

**Conclusión operativa:** para **despachar hoy** lo que está sano en datos: cerrar la cadena en las **cuatro** OV que ya muestran OUT. Para las **doce** sin OUT, primero alinear **ruta en producto / reglas del almacén** con una OV del mismo almacén que sí tenga OUT; después intervención en shell o soporte (no automatizado desde este repo sin acuerdo).

**No** intentar crear `stock.picking` OUT a mano vía RPC sin el ORM de Odoo (riesgo de stock y facturación incoherentes).

### 6.4 Dry-run: simular OUT faltantes (solo lectura, sin MCP)

Script: `nakel_odoo/tools/inventario/dry_run_simular_out_faltantes_por_ov.py`

- **No escribe** en Odoo: solo lee OV, pickings OUT existentes y líneas de venta; arma un CSV con qué implicaría **un** picking OUT manual (movimientos **Salida del almacén → stock del cliente**) por cantidad pendiente `product_uom_qty - qty_delivered` en productos almacenables.
- Misma conexión que `out_por_ov_master_dev.py` (`config_nakel` → `ODOO_CONFIG_MASTER_DEV`).

```bash
cd /media/klap/raid5/cursor_files/nakel
python3 nakel_odoo/tools/inventario/dry_run_simular_out_faltantes_por_ov.py \
  --archivo-ov nakel_odoo/docs/inventario/incidencias/logistica/wave143/lista_ov_wave143.txt
```

Salida: `backups/dry_run_out_faltantes_sim_<fecha>.csv` (columnas `simular_out` = `si`/`no`/`ambiguo`, detalle de líneas simuladas, ubicaciones Salida/cliente).

### 6.5 Crear OUT por API (una OV, prueba controlada)

Script **con escritura** (solo con `--apply --i-know-what-im-doing`): `nakel_odoo/tools/inventario/crear_out_faltante_por_ov_xmlrpc.py`

- Crea **un** `stock.picking` OUT + movimientos Salida→Cliente si **no** hay OUT no cancelado.
- **Prueba documentada (2026-05-13):** `S04368` → creado **`CEN/OUT/02167`** (`stock.picking` id **15854**), `assigned`, tras validar PICKs previos y stock en **CEN/Salida**.
- **Bug primera versión (misma fecha):** si el picking se creaba **con** `sale_id` relleno, en `action_confirm` **sale_stock** podía **volver a crear** movimientos por las líneas de la OV y **duplicar** cantidades (ej. 5+5 y 3+3 en pantalla). El script actual **no** pone `sale_id` en el `create`; hace `write(sale_id)` **después** de `action_confirm` / `action_assign`. Si quedó un OUT duplicado, corregir en Odoo (devolución / cancelar según proceso) y volver a generar con el script corregido si aplica.

```bash
# Dry-run (solo imprime)
python3 nakel_odoo/tools/inventario/crear_out_faltante_por_ov_xmlrpc.py --ov S04368

# Escritura
python3 nakel_odoo/tools/inventario/crear_out_faltante_por_ov_xmlrpc.py --ov S04368 --apply --i-know-what-im-doing
```

No usar en masa sin revisar cada OV; si ya existe OUT, el script aborta.

---

## 7. Análisis faltantes S04370 / S04372 (WAVE/00143)

Ver [ANALISIS_FALTANTES_S04370_S04372.md](ANALISIS_FALTANTES_S04370_S04372.md): listas de SKU con `qty_delivered` &lt; pedido, vínculo con movimientos `cancel` en PICK y pasos sugeridos.

---

## 8. «Se comieron las OV» / el filtro solo muestra 2 o 3 órdenes

Lectura **`master_dev`** (XML-RPC, `config_nakel`), batch **`WAVE/00143`** id **149**, estado **`done`**.

### 8.1 Las OV siguen en la base: el problema es **qué dominio** usa la vista

| Fuente | Cantidad | Qué mide |
|--------|----------|----------|
| `stock.picking.batch.picking_ids` (albaranes con **`batch_id` = 149**) | **2** | Solo los PICK que Odoo **dejó** enganchados al registro del batch después del cierre. Son **`CEN/PICK/04012`** (S04370) y **`CEN/PICK/04039`** (S04372). Desde el formulario de la ola, un smartbutton o lista basada solo en `picking_ids` puede dar la sensación de que «solo quedaron 2 OV». |
| `stock.picking` con **`nakel_wave_batch_id` = 149** | **35** | Todos los albaranes que **siguen marcados** con la ola aunque **`batch_id`** esté vacío (caso documentado en §2). |
| `sale.order` con **`nakel_wave_batch_id` = 149** | **18** | Conjunto completo de OV **etiquetadas** con esta ola en el campo personalizado. Es el dominio correcto para «todas las OV de WAVE/00143». |
| Archivo [`lista_ov_wave143.txt`](lista_ov_wave143.txt) | **16** | Lista operativa pegada en su momento; en BD hay **dos OV más** con el mismo `nakel_wave_batch_id`: **S04291** y **S04302** (conviene sumarlas al archivo si las tratás en scripts). |

**Conclusión:** no se «comieron» las OV; muchas **ya no aparecen** en la relación **`batch_id` ↔ batch** porque el batch quedó `done` y la mayoría de los PICK quedaron **`assigned`** con **`batch_id` vacío** (pero con **`nakel_wave_batch_id` = 149**).

### 8.2 Si el filtro muestra **exactamente 3** OV

En las **18** OV con `nakel_wave_batch_id = 149`, el campo estándar **`invoice_status`** reparte así (lectura 2026-05-14):

| `invoice_status` | Cantidad | OV |
|------------------|----------:|----|
| `invoiced` | 13 | (resto) |
| `to invoice` | 2 | **S04370**, **S04372** |
| `no` | **3** | **S04297**, **S04302**, **S04347** |

Si en la lista de ventas tenés un filtro tipo **«Estado facturación = No facturado»** / `invoice_status = no` **y** además limitás por ola, es **esperable ver solo 3** OV: **no** significa que las otras 15 desaparecieron, sino que **ya figuran facturadas** (`invoiced`) o **a facturar** (`to invoice`) según Odoo.

### 8.3 Dominios útiles (técnico / favoritos)

- Todas las OV de la ola: `[('nakel_wave_batch_id', '=', 149)]` en `sale.order`.
- Todos los PICK “de la ola” aunque el batch no los liste: `[('nakel_wave_batch_id', '=', 149), ('picking_type_id.code', '=', 'outgoing')]` (ajustar código de tipo según almacén) o filtrar por prefijo **`CEN/PICK/`** en el nombre si aplica a vuestro proceso.

Para exportar de nuevo pickings + OV como en wave145:  
`python3 nakel_odoo/tools/inventario/export_wave_pickings_ov_csv.py --batch-id 149`  
*(Nota: con la ola `done` y solo 2 `picking_ids`, el CSV por **batch_id** puede listar solo esos 2; para el universo completo habría que extender el script con dominio `nakel_wave_batch_id` o unir ambos criterios.)*
