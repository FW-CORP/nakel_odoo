# Mapeo pre-ventas: MSSQL GESTION ↔ Odoo master_18

Documentación para inyectar pedidos desde `Pedidos.csv` (`inyectar_pedidos_csv_master18.py`).

## Vendedores (`VENDEDORES.ID_VENDEDOR` → `res.users`)

| ID MSSQL | Nombre (referencia) | Odoo `res.users` id | Login / email |
|----------|---------------------|---------------------|---------------|
| 3 | Carlos Hernandez (preventista) | **93** | fernando31alberto@gmail.com |

En Odoo el usuario figura como **Hernandez Carlos Alberto** (mismo email).

Los seis vendedores principales históricos siguen en `mapeo_preventas_master18.json` (IDs 2, 5, 6, 9, 16, 17) según `modulos/contactos/documentacion/RESUMEN_VENDEDORES_PRINCIPALES.md`.

## Clientes (`CLIENTES` / cartera → `res.partner`)

El CSV trae **ID interno MSSQL** en la columna Cliente. En **master_18** el vínculo usado para localizar el contacto es **`res.partner.ref`** = ese ID como texto.

| ID cliente MSSQL | `partner_id` Odoo | Nombre | `ref` |
|------------------|-------------------|--------|-------|
| 2561 | **11676** | CONDORI FLORES GABRIELA ESTELA | 2561 |

Si aparecen más clientes en exportes futuros, conviene comprobar primero en Odoo: **Contactos → filtrar por Referencia interna = (id MSSQL)** o vía XML-RPC `search_read` con dominio `[('ref', '=', '<id>')]`.

## Productos (`default_code`)

- Algunos códigos en Odoo llevan **espacio inicial** en `default_code` (ej. ` 1039.20`). El script prueba variantes (`1039.20`, ` 1039.20`, y si aplica entero sin `.00`).
- Si el CSV numérico da `1812.00` pero en catálogo el artículo es **`1812`**, el script intenta también la forma entera.
- Cuando el código normalizado desde el CSV (p. ej. `8372.10` por `837210`) **no** coincide con el `default_code` en Odoo (p. ej. `587` para el mismo artículo), usar en `mapeo_preventas_master18.json` la clave **`codigo_csv_a_default_code_odoo`**: `"8372.10": "587"`. No crear un producto duplicado en Odoo.

## Archivos

- `mapeo_preventas_master18.json` — mapeos numéricos para el script.
- `inyectar_pedidos_csv_master18.py` — `--dry-run` (por defecto) / `--apply`.

## SQLite enriquecida (CSV/XLSX + MSSQL)

Para planillas exportadas de la plataforma vieja (campos codificados: vendedor y cliente como **ID MSSQL**, código de artículo como entero sin punto decimal), se genera una **SQLite** donde primero se vuelcan las líneas del CSV y luego se **traduce contra MSSQL**:

- **Vendedor:** `id_vendedor_mssql` + **`vendedor_nombre`** (y `vendedor_codigo`) desde `VENDEDORES`, no solo el número.
- **Cliente:** desde `CLIENTES`: `cliente_razon_social`, `cliente_codigo`, **`cliente_nombre_fantasia`**, **`cliente_cuit`**, **`cliente_direccion`**, **`cliente_email`**, y **`cliente_display`** (texto único legible: razón social y fantasía si difieren). En Gestion no hay columnas separadas nombre/apellido; el nombre fiscal es `RAZON_SOCIAL`.
- **Artículo:** **`codigo_articulo_odoo`** = mismo formato que `product.product.default_code` en Odoo (decimales, ej. `885725` → `8857.25`); además `cod_articulo_mssql` y `descripcion_articulo` desde `ARTICULOS`.

### Cantidad pedida: ¿unidades, cajas o bultos?

En el **export de preventas** la columna **Cantidad pedida** no trae explícitamente la unidad de medida. Por cruce con **MSSQL Gestion** se puede razonar así:

- En **`ARTICULOS`**, **`UNIDAD_MEDIDA`** suele ser **`UNI`** (unidad de venta al detalle) o **`DIS`** (display / exhibidor). Para la mayoría de golosinas con **`UNI`**, la cantidad del CSV se interpreta de forma coherente con **piezas al consumidor** (no como “número de bultos de 60 unidades”, etc.).
- **`UNID_BULTO`** es un dato de **empaque / logística** en la ficha del artículo (unidades por bulto en depósito). **No** implica que el vendedor haya cargado el pedido en ese múltiplo: sirve de referencia, no como conversor automático del CSV.
- **`UNIDAD_MIN_VTA`** indica venta mínima declarada para ese código (cuando aplica).
- La tabla **`CALVO_PEDIDOS`** (integración histórica) tiene **`CANTIDAD_PEDIDA`** en el mismo espíritu que el preventa: número de “unidades de pedido” del flujo móvil, alineado con el catálogo.

**En Odoo**, la línea de cotización usa el **UoM del producto** (`product_uom`, normalmente “Unidades”). Si el producto en master_18 está mal configurado (p. ej. UoM = caja y el CSV trae unidades), habría que corregir catálogo o aplicar un factor manual; el pipeline actual **no multiplica** por `UNID_BULTO`.

Columnas añadidas en **`pedido_lineas`** para dejar constancia:

| Columna | Origen / uso |
|---------|----------------|
| `mssql_unidad_medida` | `ARTICULOS.UNIDAD_MEDIDA` (recortada) |
| `mssql_unid_bulto` | `ARTICULOS.UNID_BULTO` (>0) |
| `mssql_unidad_min_vta` | `ARTICULOS.UNIDAD_MIN_VTA` (>0) |
| `mssql_ctd_unidades` | `ARTICULOS.CTD_UNIDADES` (>0) |
| `cantidad_pedida_contexto` | Texto orientativo generado al cargar (no sustituye regla de negocio formal) |

### Mapa de correcciones de código (varios vendedores)

Cuando el export “come” mal el entero (ej. **`124309`** → fórmula da **`1243.09`** = Playmovil, pero el artículo pedido es **Kinder Bueno `1243.90`** en MSSQL), usar el JSON:

- **`correcciones_codigo_articulo_preventas.json`** (plantilla: `correcciones_codigo_articulo_preventas.example.json`)
- **`raw_a_cod_odoo`:** clave = texto del CSV en “Codigo articulo” → valor = `default_code` correcto.
- **`codigo_odoo_a_correcto`:** clave = código ya calculado (mal) → valor = código correcto.

Lógica en `correccion_codigos_preventas.py`; el enriquecedor aplica **primero** `raw`, **luego** `codigo_odoo_a_correcto`.

Columnas en SQLite para auditoría y carga masiva:

| Columna | Uso |
|---------|-----|
| `codigo_odoo_antes_correccion` | Valor previo si hubo corrección |
| `correccion_codigo_detalle` | Texto tipo `raw_a_cod_odoo:124309→1243.90` |
| `alerta_articulo_mssql` | Si la descripción MSSQL empieza por **ZZ** / **ZZZ** (baja lógica en ERP viejo) |

Flag CLI: `--correcciones /ruta/otro.json` (por defecto el JSON del directorio).

- **Script:** `enriquecer_pedido_csv_sqlite_mssql.py`
- **Salida por defecto:** `reportes_pedido_sqlite/pedido_enriquecido.sqlite`
- **Tabla:** `pedido_lineas` — incluye `id_*_mssql`, nombres/descripciones, `codigo_articulo_odoo` (formato `XXXX.XX` como en Odoo), `estado_articulo` (`ok` / `no_en_mssql` / `sin_codigo` / `sin_mssql` si se usa el modo offline).

**Lectura del CSV:** no usar solo `DictReader` si el archivo trae varias columnas con cabecera vacía: Python fusiona la clave `''` y se pierden fecha, hora y columnas intermedias. El script lee por **posición** de columnas (compatible con el export probado: operación, vendedor, cliente, ruta, código artículo, cantidad, …, fecha, hora).

**Comando (MSSQL accesible en `localhost,1434` según `config_nakel`):**

```bash
python3 enriquecer_pedido_csv_sqlite_mssql.py \
  --csv "/ruta/Pedidos.csv" \
  --db /ruta/pedido.sqlite \
  --export-csv /ruta/pedido_enriquecido.csv
```

**Sin MSSQL** (solo comprobar parseo y códigos Odoo): `--sin-mssql`.

**Agregar otro CSV al mismo .sqlite** (sin borrar lo ya cargado): `--append` (la base debe existir). Si el archivo **no trae fila de cabecera**, usar además `--sin-cabecera-csv`.

### Columnas “Odoo friendly” en la misma SQLite

Tras la carga MSSQL, se pueden rellenar ids y nombres útiles para **importar o armar `sale.order`** (misma lógica que `inyectar_pedidos_csv_master18.py`):

| Columna | Uso típico |
|---------|------------|
| `date_order_odoo` | Fecha/hora normalizada para `sale.order.date_order` |
| `user_id_odoo` | `res.users` (vendedor) desde JSON |
| `user_name_odoo` | Nombre del usuario en Odoo |
| `partner_id_odoo` | `res.partner` (cliente) |
| `partner_name_odoo` / `partner_ref_odoo` | Verificación |
| `product_id_odoo` | `product.product` por `default_code` |
| `product_name_odoo` / `product_default_code_resuelto` | Verificación |
| `estado_linea_odoo` | `ok` o códigos unidos con `+` (ej. `falta_vendedor`, `partner_no_encontrado`, `producto_ambiguo`) |

**En un solo paso** (CSV + MSSQL + Odoo):

```bash
python3 enriquecer_pedido_csv_sqlite_mssql.py \
  --csv "/ruta/Pedidos.csv" \
  --db /ruta/pedido.sqlite \
  --resolver-odoo \
  --mapeo mapeo_preventas_master18.json \
  --export-csv /ruta/pedido_export.csv
```

**Solo resolver** sobre una SQLite ya generada:

```bash
python3 resolver_odoo_pedido_sqlite.py --db /ruta/pedido.sqlite
```

Módulo interno: `pedido_sqlite_odoo.py`.

**Clientes no listados en el JSON:** en el mapeo conviene definir `"res_partner_campo_id_mssql": "ref"` para que Odoo busque el contacto con `ref` igual al **ID cliente MSSQL** como texto (p. ej. `"1830"`). El `mapeo_preventas_master18.json` del repo usa ya `"ref"`.

## Cotizaciones en master_18 desde la SQLite

Script: `inyectar_pedido_sqlite_master18.py`

- Agrupa `pedido_lineas` por **`operacion`** → **una `sale.order` en borrador (cotización) por operación**, con todas sus líneas de producto/cantidad.
- `client_order_ref` = `PREVENTA-OP-{operacion}` (si ya existe, no duplica y marca error en el informe).
- Vendedor: mapeo `vendedores_mssql_a_user_id_odoo` o **`--user-login`** / email (p. ej. `omar.delrincon@hotmail.com` → confirma `res.users` 91, *Diaz Omar Humberto*).
- Cliente y producto: igual que el CSV (`ref` + búsqueda por `default_code`); si en la SQLite corriste `resolver_odoo_pedido_sqlite.py`, se usan `partner_id_odoo` / `product_id_odoo` cuando apliquen.

```bash
# Solo informe (recomendado primero)
python3 inyectar_pedido_sqlite_master18.py \
  --db reportes_pedido_sqlite/pedido_omar_las_heras.sqlite \
  --user-login omar.delrincon@hotmail.com

# Crear cotizaciones en Odoo
python3 inyectar_pedido_sqlite_master18.py \
  --db reportes_pedido_sqlite/pedido_omar_las_heras.sqlite \
  --user-login omar.delrincon@hotmail.com \
  --apply
```

Operaciones con **códigos ambiguos** o **sin match** en catálogo quedan omitidas en `--apply` (se listan en consola y en el JSON de reporte). El propio script ahora:

- amplía **variantes de `default_code`** (p. ej. `698.5` / `698.50`);
- si el `in` de variantes devuelve **varios** `product.product` con el mismo valor numérico pero distinto texto (p. ej. Odoo tiene **`1243.9`** y **`1243.90`**), **`reducir_ambiguedad_default_code`** deja **una** fila priorizando la coincidencia **literal** con el código pedido (`1243.90` → variante de 30 u., no la de 15);
- carga **PLU desde MSSQL** (`mssql_plu_pedidos.py`) y desambigua por **barcode** en Odoo cuando hay varios candidatos; la búsqueda por barcode prueba el PLU **tal cual** y **sin ceros a la izquierda**;
- **`resolver_odoo_pedido_sqlite.py`** / `--resolver-odoo` usan la misma lógica de PLU + barcode al rellenar `product_id_odoo` en la SQLite;
- si `ref` ≠ id cliente, intenta **nombre** (razón social de la SQLite) y **CUIT** (`vat`).

Para desactivar MSSQL: `--sin-mssql-plu`.

Opcional: añadir en el JSON `clientes_mssql_a_partner_id` el id definitivo (p. ej. `919` → partner Odoo) si querés fijar a mano.

**CSV sin cabecera** (export crudo, columnas A–I): `inyectar_pedidos_csv_master18.py --sin-cabecera`. Opciones: `--master-dev`, `--agrupar-por-cliente`, `--mapeo-archivo-vendedor`, `--sin-hora`, `--omitir-lineas-sin-producto`. En el JSON: `clientes_mssql_a_vat` y `clientes_mssql_vat_nombre_contiene` para resolver contacto por CUIT.
Ejemplo y lista de archivos abril: `ventas/inyeccion-ventas-abril/README_INYECCION_ABRIL.md`.

**Última actualización:** 2026-03-28
