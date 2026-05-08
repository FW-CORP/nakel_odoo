# Listas de precios fijas para PDV (-FIX)

## Contexto

En los **puntos de venta (PDV)** de Odoo, las listas con **reglas complejas** (fórmulas sobre otra lista, márgenes, reglas globales por categoría, etc.) **no siempre resuelven el precio** de forma fiable. Mientras se investiga la causa (bug, limitación del POS o configuración), se usan listas **solo con precio fijo** por producto/plantilla.

En **Nakel Central** (ventas estándar) pueden seguir usándose las listas **originales con fórmulas**; las listas **- FIX** son un **snapshot** para PDV y sucursales que lo requieran.

## Idea general

1. Se toma una **lista de referencia** (la misma que ya usan en ventas y que calcula bien con fórmulas).
2. Se calcula el **precio efectivo** por variante con el motor de ventas (cotizaciones temporales por lotes).
3. Se crea una **lista nueva** con una línea **`compute_price = fixed`** por **plantilla** (`product_tmpl_id`).
4. Si el precio de la lista de referencia sale **≤ 0**, el script intenta **`lst_price`** del producto como respaldo; lo que siga en cero **no** recibe ítem en la lista -FIX (conviene revisar catálogo).

## Script

Ubicación:

```
ventas/Listas de precios/scripts/dry_run_snapshot_lista_desde_referencia.py
```

Usa **`ODOO_CONFIG_MASTER_DEV`** (`config_nakel.py`) → base **master_dev** (Odoo 18 en producción Nakel).

### Un solo archivo para todas las listas (recomendado)

En esta carpeta, **`regenerar_listas_pdv.sh`** recorre **todos los pares** origen → destino definidos en el propio script (array `LISTAS`). Ahí se agregan o se corrigen nombres si Odoo cambió.

```bash
cd "/media/klap/raid5/cursor_files/nakel/ventas/pdv-listas"
./regenerar_listas_pdv.sh dry-run   # informe de las 4 listas (tarda varios minutos)
./regenerar_listas_pdv.sh apply     # crear cada lista -FIX (requiere nombres libres en Odoo)
```

Variable opcional: `BATCH=30 ./regenerar_listas_pdv.sh dry-run`

Si un par falla (por ejemplo `--apply` con nombre ya existente), el shell **sigue con el siguiente** y al final indica cuántos fallaron.

### Dry-run (solo informe, no escribe listas)

```bash
cd "/media/klap/raid5/cursor_files/nakel/ventas/Listas de precios/scripts"
python3 dry_run_snapshot_lista_desde_referencia.py \
  --lista-referencia "NOMBRE_LISTA_ORIGEN" \
  --nombre-nueva "NOMBRE_LISTA_FIX"
```

Opciones útiles:

- `--limit 200` — prueba rápida con pocas variantes.
- `--batch 35` — variantes por cotización temporal (ajustar si hay timeouts).
- `--no-lst-price-fallback` — no usar `lst_price` cuando la referencia devuelve 0.

### Aplicar (crea `product.pricelist` + ítems)

```bash
python3 dry_run_snapshot_lista_desde_referencia.py \
  --lista-referencia "NOMBRE_LISTA_ORIGEN" \
  --nombre-nueva "NOMBRE_LISTA_FIX" \
  --apply
```

Si ya existe una lista con el **mismo nombre exacto**, el script **aborta** (renombrar la anterior o elegir otro nombre).

**Recomendación:** backup o ventana de baja carga antes de `--apply` en producción.

## Listas generadas (referencia — abril 2026)

Comprobar siempre **id** y nombre en Odoo: **Ventas → Configuración → Listas de precios**.

| Lista -FIX (destino PDV) | Id (ref. sesión) | Lista origen (fórmulas) | Id origen |
|--------------------------|------------------|-------------------------|-----------|
| Belgrano Final Comodoro | 42 | Lista 2 Consumidor Final Autoservicios CR (nombre vigente en su momento) | 31 |
| Lista 2 Autoservicios CR - FIX | 43 | Lista 2 Autoservicios CR | 33 |
| Lista 25 Autoservicio Caleta Olivia - FIX | 44 | Lista 25 Autoservicio Caleta Olivia | 38 |
| Lista 25 Consumidor Final Autoservicio CO - FIX | 45 | Lista 25 Consumidor Final Autoservicio CO | 32 |

**Asignación:** en cada **Punto de venta** usar la lista -FIX que corresponda a la política comercial de ese mostrador (no la lista con fórmulas, salvo que ya funcione bien en ese PDV).

## Mantenimiento: hay que regenerar cuando cambian precios o productos

Las listas -FIX son **valores congelados en el momento de ejecutar `--apply`**.

Hay que **volver a generar** (o en el futuro automatizar) cuando:

- Cambien **reglas o listas base** de las listas de referencia.
- Cambien **productos nuevos** o variantes que deban venderse en el PDV con la misma lógica que la lista origen.
- Corrijan **precios de lista** en Central y quieran el mismo criterio reflejado en PDV.

### Procedimiento sugerido al actualizar

1. Acordar la **lista origen** correcta (la que sigue siendo la verdad en Central).
2. **Dry-run** contra el nombre exacto de esa lista.
3. Revisar en el resumen cuántas líneas quedan con **precio ≤ 0** (y corregir `lst_price` o reglas si hace falta).
4. Si la lista -FIX ya existe: en Odoo **renombrar** la vieja (ej. añadir sufijo `- OLD 2026-04-01`) o **archivar**, luego `--apply` con el nombre estándar `- FIX`, **o** usar un nombre nuevo y reasignar el PDV.

> **Nota:** El script actual no “actualiza in place” masivamente; crea una lista **nueva** si el nombre está libre. Para refrescar el mismo nombre sin duplicar, archivar/renombrar la anterior antes del `--apply`.

## Órdenes de magnitud típicas (master_dev)

- Variantes `sale_ok`: ~5464.
- Ítems creados en listas -FIX: ~4790 (según corridas documentadas).
- Plantillas **sin** ítem (precio ≤ 0 tras fallback): ~672–674 — revisar si se venden en ese PDV.

## Cuando deje de hacer falta

Si en el futuro el PDV **resuelve bien** las listas con fórmulas, se puede:

- Asignar de nuevo la **lista origen** en el PDV.
- Archivar las listas -FIX o dejarlas solo como respaldo.

## Traducción de botón POS: "Backend" → "Tablero" (staging / API)

En el POS (módulo `point_of_sale`) suele aparecer el botón **"Backend"**. Si se quiere traducirlo a **"Tablero"** sin tocar UI manualmente, se puede upsertear la traducción vía XML-RPC:

```bash
export NAKEL_TARGET=staging_sg_dev1

# dry-run (no escribe)
python3 "/media/klap/raid5/cursor_files/nakel/ventas/pdv-listas/traducir_pdv_backend_a_tablero.py" --lang es_AR

# aplicar (escritura explícita)
python3 "/media/klap/raid5/cursor_files/nakel/ventas/pdv-listas/traducir_pdv_backend_a_tablero.py" --lang es_AR --apply
```

---

**Última actualización:** 2026-04-01 (FWCORP / vault Nakel)
