# Estructura de costos y listas «Lista 1» / «Lista 2» en `master_dev`

Documento de **solo lectura** (snapshot por API) para entender **de dónde sale el precio** en caja y ventas cuando se mueve el **costo** en Central.

| Campo | Valor |
| --- | --- |
| **Base de datos** | `master_dev` (productiva Nakel) |
| **Instancia** | `https://nakel.net.ar` |
| **Fecha de lectura** | **2026-04-07** |
| **Método** | XML-RPC `product.pricelist`, `product.pricelist.item`, `res.company`, muestra `product.template` |

> Si restauran la BD o cambian reglas, **volver a ejecutar** una consulta equivalente: los **IDs** y conteos pueden variar.

---

## 1. Dónde vive el «costo» en Odoo

- En **`product.template`** el campo **`standard_price`** es el costo estándar que usa el catálogo para valoración y para reglas de lista que basan en **`standard_price`**.
- Ese valor **se actualiza** según la **categoría del producto** (método de costo: estándar, AVCO, FIFO, etc.) y los **movimientos de stock / facturas de proveedor** que impacten el costo.
- **`list_price`** es el «precio de venta» público del producto; en listas **-FIX** se usa mucho como base simbólica con **`fixed_price`** real.

**Empresa Nakel SA (id 1)** — campos relevantes leídos:

- `anglo_saxon_accounting`: **False** (no anglosajón en esta lectura).

---

## 2. Listas cuyo nombre empieza por «Lista 1» o «Lista 2» (y afines)

En la lectura aparecieron **12** listas con nombre que contiene **`Lista 1`** o **`Lista 2`** (incluye variantes **Caleta Olivia / Lista 25** y sufijo **- FIX**).

| ID | Nombre | Líneas de regla | Modo principal |
| ---: | --- | ---: | --- |
| **30** | Lista 1 CR Distribución | 31 | Fórmula sobre **costo** + algunos **fijos** |
| **33** | Lista 2 Comercio Autoservicios CR | 13 | Fórmula sobre **Lista 1** (categorías) + excepciones sobre **costo** |
| **31** | Lista 2 Particulares Autoservicios CR | 1 | Regla **global** sobre **Lista 2 Comercio** |
| **43** | Lista 2 Comercios Aut. CR - FIX | 4788 | **Precio fijo** por producto |
| **42** | Lista 2 Particulares Aut. CR - FIX | 4784 | **Precio fijo** por producto |
| **36** | Lista 11 Akapol | 15 | Fórmulas (costo / otra lista) |
| **39** | Lista 17 Mayoristas | 28 | Fórmulas sobre otra lista |
| **38** | Lista 25 Comercio Caleta Olivia | 14 | Similar enfoque a Lista 2 CR (lista base + categorías) |
| **44** | Lista 25 Comercios Aut. Caleta Olivia - FIX | 4786 | Fijo |
| **45** | Lista 25 Part. Autoservicio CO - FIX | 4786 | Fijo |
| **32** | Lista 25 Particulares Autoservicio CO | 1 | Global sobre lista comercio CO |
| **34** | Lista 26 CO Distribución | 7 | Fórmulas sobre otra lista |

Los **conteos de líneas** son los **`product.pricelist.item`** activos en esa lista al momento de la lectura.

---

## 3. «Lista 1» como origen de margen sobre costo (detalle)

**`Lista 1 CR Distribución` (id 30)**

- **26** reglas por **producto** (`applied_on`: producto): **`compute_price` = `formula`**, **`base` = `standard_price`** (costo).  
  Cada una define **`price_discount`** y **`price_markup`** (margen comercial distinto por ítem; ej. Fernet −27% / +27% en la UI).
- **5** reglas por **producto**: **`compute_price` = `fixed`**, **`base` = `list_price`**, con **`fixed_price`** explícito (ej. líneas Kinder): el precio **no** sigue al costo en esos casos, queda el importe fijado en la regla.

Interpretación operativa: **Lista 1** es la lista «de distribución» donde **casi todo** el surtido se apoya en **costo + margen por producto**, salvo **excepciones fijadas** a un precio sobre `list_price`.

---

## 4. «Lista 2» derivada de Lista 1 (sin -FIX)

**`Lista 2 Comercio Autoservicios CR` (id 33)**

- **9** reglas por **categoría**: **`base` = `pricelist`**, **`base_pricelist_id` = Lista 1 CR Distribución (30)**.  
  Ajuste por categoría con **`price_discount` / `price_markup`** (ej. **−1,54% / +1,54%** sobre el precio que devuelve Lista 1 para ese producto).
- **4** reglas por **producto** (ej. Fernet): **`base` = `standard_price`** con fórmula de margen **directamente sobre costo** (paralelo a Lista 1 para esos ítems).

**`Lista 2 Particulares Autoservicios CR` (id 31)**

- **1** regla **global** (`3_global`): precio calculado desde **`base_pricelist_id` = Lista 2 Comercio Autoservicios CR (33)** con **`price_discount` −25%** y **`price_markup` 25%** (según convención de signos de Odoo en pantalla = recargo sobre la lista comercio).

Cadena resumida:

```text
costo (standard_price)  →  Lista 1 (30)  →  Lista 2 Comercio (33)  →  Lista 2 Particulares (31)
         ↑ excepciones fijas (5 ítems)              ↑ por categoría              ↑ +25 % global
         ↑ 4 ítems también en (33) sobre costo
```

---

## 5. Listas «- FIX» (snapshot)

**`Lista 2 Comercios Aut. CR - FIX` (43)** y **`Lista 2 Particulares Aut. CR - FIX` (42)**

- **Todas** las líneas leídas: **`compute_price` = `fixed`**, **`base` = `list_price`**, con **`fixed_price`** por producto (~**4788** / **4784** ítems).
- Efecto: el precio de venta en PDV **no se recalcula** en vivo desde el costo ni desde Lista 1; **solo cambia** si se **actualizan** esas líneas (importación, script, o edición manual).

Misma lógica para las **Lista 25 … - FIX** en Caleta Olivia (ids **44**, **45**): miles de precios **fijos**.

Referencia cruzada: `ventas/pdv-listas/README.md` y `ventas/Calculo-costos-impuestos/ODOO_LISTAS_PRECIOS_VS_IMPUESTOS.md` (listas -FIX para POS).

---

## 6. Implicación cuando «Central» actualiza costos

| Lista usada | ¿El precio sigue al nuevo costo al instante? |
| --- | --- |
| **Lista 1** (fórmulas sobre `standard_price`) | **Sí**, en la medida en que Odoo ya haya actualizado **`standard_price`** por compras/valoración. |
| **Lista 2 Comercio / Particulares** (no FIX) | **Sí**, porque dependen de **Lista 1** o del **costo** en reglas puntuales. |
| **Lista 2 … - FIX** | **No** hasta que se **regeneren** o editen los **`fixed_price`**. |

---

## 7. Documentos relacionados en el vault

- Criterio impuestos vs listas: `ventas/Calculo-costos-impuestos/ODOO_LISTAS_PRECIOS_VS_IMPUESTOS.md`
- Scripts migración Excel / listas: `ventas/Listas de precios/scripts/README.md`
- Costos Excel / `master_dev`: `mssql/ANALISIS_ACTUALIZACION_COSTOS_NAKEL.md`
- **Cron** — sync costo + réplica **Lista 1 CR Distribución (id 30)** → **Lista 1 Nak (id 48)**: `tools/costo_nak_to_nakel/README.md` (validado en **nakel.net.ar** el **2026-05-09**; ver sección *Estado en producción*).

---

## 8. Cómo reproducir la lectura (sin modificar datos)

Desde máquina con `config_nakel.py` y usuario técnico configurado:

1. Autenticar XML-RPC contra `ODOO_CONFIG_MASTER_DEV`.
2. `product.pricelist`: `search` con dominio `[["name","ilike","Lista 1"]]` y `[["name","ilike","Lista 2"]]`.
3. Por cada id: `product.pricelist.item` con dominio `pricelist_id = id`, leer `base`, `compute_price`, `base_pricelist_id`, `percent_price`, `fixed_price`, `price_discount`, `price_markup`, `applied_on`, `categ_id`, `product_tmpl_id`.

Los números de este archivo salieron de un script equivalente ejecutado el **2026-04-07**.

---

## 9. Lista 1 en compañía «Nak» (referencia operativa)

En **producción** se usa una **Lista 1** para la compañía **Nak** (`product.pricelist` **id=48** en la lectura asociada al cron de mayo 2026). Las reglas de esa lista se mantienen alineadas con **Lista 1 CR Distribución (id=30)** de **Nakel SA** mediante la acción planificada documentada en `tools/costo_nak_to_nakel/README.md` (copia de ítems + sync de `standard_price` previo). Si restauran la base, **confirmar ids 30 y 48** antes de confiar en el cron.
