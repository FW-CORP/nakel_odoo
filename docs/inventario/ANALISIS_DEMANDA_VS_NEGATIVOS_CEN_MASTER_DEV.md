# Análisis — demanda vs existencias negativas (CEN, `master_dev`)

**Objetivo:** listar productos con cantidad **negativa** y/o **cero** (según modo) en el stock físico de Central, opcionalmente cruzados con **demanda reciente** en pedidos de venta confirmados.

## Ubicación “CEN/STOCK”

En la base **no aparece** una ubicación `complete_name = CEN/STOCK`. El stock del almacén **CEN** (`stock.warehouse`, `code=CEN`) apunta a **`CEN/Existencias`** (`stock.location` **id 102**). Eso es lo que el script usa por defecto.

Si tu “STOCK” es otra ubicación, pasá `--location-id` o `--location-complete-name`.

## Script (solo lectura)

Archivo:

- `nakel_odoo/tools/inventario/analisis_demanda_vs_negativos_cen_master_dev.py`

Ejemplo (últimos 90 días, top 100, orden por *score* = demanda × |qty|):

```bash
python3 nakel_odoo/tools/inventario/analisis_demanda_vs_negativos_cen_master_dev.py \
  --dias 90 --top 100 --sort score --out /tmp/cen_negativos_demanda.csv
```

**Todos** los productos con `quantity <= 0` en CEN/Existencias (sin límite de filas, sin columna de ventas):

```bash
python3 nakel_odoo/tools/inventario/analisis_demanda_vs_negativos_cen_master_dev.py \
  --qty-mode zero_or_negative --top 0 --no-demanda --out /tmp/cen_stock_le0_completo.csv
```

**Todos** los negativos con demanda 90d:

```bash
python3 nakel_odoo/tools/inventario/analisis_demanda_vs_negativos_cen_master_dev.py \
  --qty-mode negative --top 0 --dias 90 --sort score --out /tmp/cen_negativos_demanda_completo.csv
```

Parámetros útiles:

- `--qty-mode negative` — solo `stock.quant.quantity < 0` (default).
- `--qty-mode zero_or_negative` — `quantity <= 0` (incluye filas de quant en **cero**; no incluye productos sin quant en esa ubicación).
- `--top 0` — exporta **todas** las filas (sin truncar).
- `--no-demanda` — no llama a ventas; CSV más liviano.
- `--company-id 1` — compañía para `sale.order.line` (default **1** = Nakel SA).
- `--include-children` — agrega sububicaciones (`child_of`) bajo la raíz elegida.
- `--sort demand|negative|score` — criterio de orden en el CSV (`negative` ordena por \|qty_stock\|).

## Definición de “demanda”

Suma de `sale.order.line.product_uom_qty` con:

- `state = sale` (pedido confirmado)
- `company_id` = el indicado
- `order_id.date_order >= hoy - N días`

Si necesitás otra definición (POS, movimientos de salida, etc.), se puede extender el script.

## Si en Excel ves `-0120` en lugar de `-120`

El CSV guarda el valor correcto (p. ej. `-120`). Ese aspecto suele ser **formato de celda** en Excel (p. ej. un formato personalizado con ceros a la izquierda como `0000.0`). Solución: seleccionar la columna `qty_stock` → **Formato de celdas** → **General** o **Número** sin relleno de ceros.

Si abrís el archivo con **doble clic**, Excel puede malinterpretar separadores según la configuración regional. Mejor: **Datos → Obtener datos → Desde archivo → Desde texto/CSV** y revisar que el decimal sea **punto** (`.`).

El script escribe **cantidades** como entero en texto cuando el valor es entero (`-120`, `1737`, `208440`), y tolera ruido float de Odoo.

Las **referencias internas** (`default_code`) suelen llevar punto (`1039.20`, `9.90`): eso **no** es un decimal de stock; Excel sin ayuda las convierte en número. El CSV exporta esas referencias con fórmula `="…"` para que Excel las trate como **texto**. Los códigos de barras largos solo numéricos van igual, para evitar notación científica.
