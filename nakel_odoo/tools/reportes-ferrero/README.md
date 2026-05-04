# Reportes Ferrero (Nakel)

Herramienta en **`/media/klap/raid5/cursor_files/nakel/nakel_odoo/tools/reportes-ferrero/`** (scripts Python y venv). Las **planillas generadas y los `_odoo.xls`** salen por defecto en **`OUT/`**; en la **raíz del tool** conviene dejar solo los **originales de referencia** (p. ej. marzo) que no van al repo por tamaño.

## Archivos de referencia (marzo 2026, ya enviados)

Colocar en la raíz del directorio del tool (no en `OUT/`):

- `FERRERO VENTAS Y STOCK 2026-03.xls` — ventas y stock por SKU (plantilla mensual).
- `Promo Ferrero Marzo.xls` — detalle promo por cliente (entrada para generar abril).

## Abril 2026 — VENTAS Y STOCK

Generado (por defecto en **`OUT/`**): **`OUT/FERRERO VENTAS Y STOCK 2026-04.xls`**

- Misma estructura que marzo (una hoja `Hoja1` con columnas Codigo, Cod.Art. Proveedor, Descripcion, VENTAS, STOCK).
- Título actualizado: **VENTA / STOCK FERRERO ABRIL 2026**.
- **VENTAS** y **STOCK** quedan en **0** en todas las filas de producto: hay que completarlas con los datos reales de abril (no copiar marzo para no enviar cifras equivocadas a Ferrero).

### Odoo — fuente de datos (opcional)

- **URL:** `https://nakel.net.ar`
- **Base:** `master_dev`
- **Config:** `config_nakel.py` → `ODOO_CONFIG_MASTER_DEV` (credenciales locales, no van al repo).

Script opcional que genera un XLS aparte con **VENTAS** (facturado neto abril, ver abajo) y **STOCK** (`qty_available`). Orden de cruce de producto:

1. `product.product.default_code` = *Cod.Art. Proveedor*.
2. Si no: `product.supplierinfo.product_code`.
3. Si no: **nombre** — columna *Descripcion* (se quitan sufijos tipo `.-899-` y ` (10)` al final); búsqueda `ilike` en `product.product.name` y desempate por solapamiento de palabras para evitar homónimos.

**VENTAS** en columna *VENTAS*: misma lógica **facturado neto** (`out_invoice` − `out_refund`, `invoice_date` en abril).

```bash
cd /media/klap/raid5/cursor_files/nakel/nakel_odoo/tools/reportes-ferrero
./.venv/bin/python rellenar_ventas_stock_odoo_master_dev.py --dry-run
./.venv/bin/python rellenar_ventas_stock_odoo_master_dev.py
# salida por defecto: OUT/FERRERO VENTAS Y STOCK 2026-04_odoo.xls
# solo codigo + proveedor (sin nombre): --no-name-fallback
# quitar del XLS un articulo sin producto en Odoo (ej. Kinder Chocolate X100G):
./.venv/bin/python rellenar_ventas_stock_odoo_master_dev.py --exclude-codes 77235547 --out "OUT/FERRERO VENTAS Y STOCK 2026-04_odoo.xls"
```

Al finalizar, el script lista **Sin match Odoo** para códigos que siguen en el informe y no cruzan. Si usás **`--exclude-codes`**, esas filas **no se copian** a la hoja `Hoja1` del XLS de salida (cabeceras y título se mantienen; el resto de hojas se copian igual). Los excluidos sin match se listan aparte como omitidos a propósito.

Los enlaces tipo `https://nakel.net.ar/odoo/action-560/10559` sirven para comprobar en UI el `product.product` (el último segmento numérico es el id); el script sigue resolviendo por código/proveedor/nombre, no hace falta pegar ids en el Excel.

### Artículos accionados (desde 16/04/2026)

El archivo de abril incluye una segunda hoja **`Accionados_16abr2026`** con la tabla de dinámicas y **tope cajas** para NAKEL S.A. según lo acordado.

### Regenerar el XLS de abril

Requiere el venv (una sola vez):

```bash
cd /media/klap/raid5/cursor_files/nakel/nakel_odoo/tools/reportes-ferrero
python3 -m venv .venv
.venv/bin/pip install 'xlrd<2' xlwt
.venv/bin/python generar_ferrero_ventas_stock_abril.py
```

## Promo Ferrero — Abril 2026

Generado (por defecto en **`OUT/`**): **`OUT/Promo Ferrero Abril.xls`** (script `generar_promo_ferrero_abril.py`).

- **Comprador:** mismas columnas que marzo — *Codigo Cliente* y *Razón Social* (copia fila a fila desde `Promo Ferrero Marzo.xls`).
- **Promo:** *Codigo* y *Descripcion* se actualizan con el mapeo **marzo → abril** del script (p. ej. `PROMO ROCHER T8` / `T12` → `PROMO ROCHER T24 (15% OFF)` con código `2.6`; Kinder Maxi / Huevo / Nutella 140 / Bueno se mantienen alineados al texto estándar).
- **Ctd. Vendida:** en **0** en todas las filas (plantilla abril; no arrastrar cantidades de marzo). Para conservar cantidades de marzo: `--mantener-cantidades`.
- Hoja **`Accionados_16abr2026`:** tres columnas — dinámica, **tope de cajas (acuerdo comercial, no son ventas)** y columna C en **0** hasta correr el script Odoo, que reescribe esa hoja con **ventas agregadas** por línea accionada.

```bash
cd /media/klap/raid5/cursor_files/nakel/nakel_odoo/tools/reportes-ferrero
./.venv/bin/python generar_promo_ferrero_abril.py
# opcional: --in "Promo Ferrero Marzo.xls" --out "OUT/Promo Ferrero Abril.xls"
```

Las líneas de accionados **Kinder Chocolate T4**, **Nutella B-Ready**, **Nutella 350** y **Tic Tac** no aparecían como promo distinta en el marzo analizado; si Ferrero pide esas líneas por cliente, habrá que **agregar filas** manualmente o ampliar el script con otro origen (export Odoo / plantilla Ferrero).

### Cantidades vendidas en abril (Odoo)

El XLS de plantilla pone **Ctd. Vendida** en 0. Para rellenar con **ventas netas facturadas** del mes (ver criterio AML abajo):

```bash
cd /media/klap/raid5/cursor_files/nakel/nakel_odoo/tools/reportes-ferrero
./.venv/bin/python rellenar_promo_cantidades_odoo_master_dev.py --dry-run
./.venv/bin/python rellenar_promo_cantidades_odoo_master_dev.py
# salida: OUT/Promo Ferrero Abril_odoo.xls
# mes/año: --month 4 --year 2026
# Hoja1 por defecto solo filas con Ctd. Vendida > 0; grid completo con ceros: --todas-las-filas
```

- **Cliente:** `res.partner.ref` = *Codigo Cliente*; si la razón trae sucursal `NOMBRE (SUCURSAL)` y el `ref` es el comercial, se intenta bajar al **contacto hijo** por nombre de sucursal (si no existe en Odoo, queda el comercial y la suma puede agrupar sucursales). Algunas filas de la planilla vienen **desalineadas** (código en columna B); el script las toma en cuenta.
- **Ventas:** cantidad **neta facturada** (`out_invoice` − `out_refund` en `account.move.line`, `invoice_date` en el mes, `posted`). No se usan cantidades de pedido (`sale.order.line`) para que las **notas de crédito / devoluciones** resten. Las líneas AML se filtran por **`partner_id` exacto** al contacto resuelto: si en Odoo las facturas van al **comercial** y no a la sucursal, la fila de sucursal puede salir **0** aunque el grupo haya vendido (convendría alinear el cliente en facturación o revisar con contabilidad).
- **Promo → productos:** reglas por texto *Descripcion* (p. ej. Raffaello se busca como en catálogo **RAFFAELLO**; Rocher T24 con `ROCHER`+`BOMBONERA` excluyendo huevos/cajas en el nombre). Revisar con negocio si alguna promo suma artículos de más o de menos.

**Extracto Odoo** `Reporte de análisis de ventas (sale.report).xlsx`: útil como referencia del **nombre de variante** (`[default_code] descripción…`), alineado con `product.product` en Odoo. Los scripts siguen cruzando por RPC; el XLS no se lee automáticamente (se puede ampliar si hace falta un mapeo fijo).
- Filas **sin partner** en Odoo quedan con cantidad 0; conviene revisar el log del script o ampliar el cruce (otro campo de código cliente, etc.).

**Ceros en Hoja1:** la plantilla lista **todas** las combinaciones comprador + promo heredadas de marzo; muchas quedan en 0 en abril (sin movimiento o sin cruce de cliente en Odoo). El script **omite por defecto** las filas de detalle con **Ctd. Vendida ≤ 0** para el entregable `_odoo.xls`. Si necesitás auditoría fila a fila con ceros: **`--todas-las-filas`**.

**Cuadro Accionados:** la columna de **topes** (B) nunca fue “cajas vendidas”; son **límites del acuerdo**. La columna **C** es la suma Odoo del detalle de Hoja1 por cada línea accionada; puede dar **0** si en el detalle no hay promos que casen con esa dinámica (ej. mucho volumen va en *PROMO HUEVO KINDER*, que no forma parte de la tabla de ocho accionados).
