# Sync costo y Lista 1: NAKEL SA → NAK

## Objetivo

Mantener sincronizado el **costo** (`standard_price`) desde la empresa **NAKEL SA** hacia **NAK** para productos vendibles, y **replicar las reglas** de la lista **Lista 1 CR Distribución** hacia la **Lista 1** de Nak, mediante una **Acción planificada** (`ir.cron`) en Odoo.

Referencias en el vault: `docs/ventas/Listas de precios/ESTRUCTURA_COSTOS_Y_LISTAS_1_2_MASTER_DEV.md` (lista **id=30** = Lista 1 CR Distribución). La lista destino **id=48** («Lista 1» en compañía Nak) conviene **revalidar** en cada base (`Ajustes → Ventas → Listas de precios`).

## Estado en producción (`nakel.net.ar`)

- **2026-05-09**: el job quedó **aplicado y validado** en la instancia (acción planificada con código Python: sync de **`standard_price`** Nakel SA → Nak y réplica de reglas **lista 30 → lista 48**).
- **Odoo 18**: `product.pricelist.item` **no tiene** campo `sequence`; el script ordena líneas con **`item_ids.sorted("id")`** (equivalente a `sorted(key=lambda r: r.id)`). Usar `sequence` en el `sorted` provoca `AttributeError` en `safe_eval`.
- Tras cada corrida revisar el **log** de la acción (mensajes `Sync costos:` y `Sync listas:`) y, si aplica, el historial de la acción planificada / servidor.

> Nota: `standard_price` es **dependiente de compañía** (propiedad). Por eso es correcto usar `with_company()` al leer/escribir.

---

## Recomendación (mejor práctica)

Hacerlo **dentro de Odoo** con una **Acción planificada** que ejecute **código Python**.

Ventajas:
- respeta el ORM y reglas de negocio
- queda auditado en logs
- evita depender de cron del sistema + `odoo shell`

---

## Crear el cron (UI Odoo)

En Odoo con **modo desarrollador**:

1. Ir a **Ajustes → Técnico → Automatización → Acciones planificadas**.
2. Crear una nueva.
3. Completar:
   - **Nombre**: `Sync costos y Lista 1: NAKEL SA → NAK`
   - **Activo**: ✅
   - **Usuario**: usuario técnico con permisos (ideal: bot/técnico)
   - **Modelo**: cualquiera (ej. `Producto`), el código usa `env[...]`
   - **Ejecutar cada**: lo que defina negocio (ej. 1 día)
   - **Siguiente ejecución**: horario de baja carga
   - **Acción a realizar**: `Ejecutar código Python`
4. Pegar el código de abajo.

---

## Datos validados en `master_dev` (solo lectura)

- **Empresas existentes**:
  - `Nakel SA` (id=1)
  - `Nak` (id=2)

> Importante: en `master_dev` los nombres están con esta capitalización. Si buscás por `name = ...`, respetar mayúsculas/minúsculas.

### Muestreo rápido de productos (solo lectura)

En `master_dev`, el dominio:

- `sale_ok=True`
- `type in ('consu','product')`

devuelve **3889** productos.

Muestra (5 últimos IDs) y `standard_price` leído en el contexto por defecto del conector:

- `product.product` **11032**: costo `1627.70` (producto compartido `company_id=False`)
- `product.product` **11031**: costo `0.00` (compartido)
- `product.product` **11030**: costo `6333.60` (compartido)
- `product.product` **11027**: costo `0.017` (compartido)
- `product.product` **11026**: costo `1769.09` (compartido)

> Importante: el conector de consulta no permite fijar `with_company()`/contexto por empresa, así que esta lectura **no** prueba diferencias entre compañías; solo confirma que el campo existe, que el dominio trae productos y que muchos productos son compartidos (`company_id=False`), lo cual es compatible con “costo por compañía”.

---

## Código Python (para `ir.cron` / “Ejecutar código Python”)

Este código:
- busca las compañías por nombre
- toma todos los productos `product.product` vendibles (`sale_ok=True`) tipo almacenable/consumible
- copia `standard_price` de NAKEL SA a NAK **solo si el costo origen es > 0**
- si `SYNC_PRICELISTS` está activo: **elimina todas las líneas** (`product.pricelist.item`) de la lista destino y las **vuelve a crear** copiando la lista origen (orden de copia por **`id`**; mismas fórmulas, fijos, categorías). Si alguna regla usara `base_pricelist_id` apuntando a la lista **30**, se reasigna a la lista **48** para no referenciar la lista de la otra compañía.
- deja log con cantidades

```python
SOURCE_COMPANY_NAME = "Nakel SA"
TARGET_COMPANY_NAME = "Nak"
# Listas (IDs típicos master_dev / nakel.net.ar — revisar tras restore de BD)
SOURCE_PRICELIST_ID = 30   # Lista 1 CR Distribución (Nakel SA)
TARGET_PRICELIST_ID = 48   # Lista 1 (Nak)
SYNC_PRICELISTS = True

Company = env["res.company"].sudo()
Product = env["product.product"].sudo()

source_company = Company.search([("name", "=", SOURCE_COMPANY_NAME)], limit=1)
target_company = Company.search([("name", "=", TARGET_COMPANY_NAME)], limit=1)

if not source_company or not target_company:
    raise UserError("No se encontró la empresa origen o destino (revisar nombres).")

# Importante en multicompany: asegurar compañías permitidas en contexto del cron
allowed_company_ids = list(set((env.context.get("allowed_company_ids") or []) + [source_company.id, target_company.id]))
_ctx = dict(env.context, allowed_company_ids=allowed_company_ids)

products = Product.with_context(_ctx).with_context(active_test=False).search([
    ("type", "in", ["consu", "product"]),
    ("sale_ok", "=", True),
])

updated = 0
skipped_zero = 0

for product in products:
    source_product = product.with_company(source_company)
    target_product = product.with_company(target_company)

    source_cost = source_product.standard_price

    # Evita pisar costos con cero si por algún motivo el origen está vacío
    if source_cost and source_cost > 0:
        target_product.write({"standard_price": source_cost})
        updated += 1
    else:
        skipped_zero += 1

log("Sync costos: %s → %s | actualizados=%s | omitidos_costo_cero=%s | productos_total=%s" % (source_company.name, target_company.name, updated, skipped_zero, len(products)), level="info")

if SYNC_PRICELISTS:
    Pricelist = env["product.pricelist"].sudo()
    source_pl = Pricelist.with_context(_ctx).browse(SOURCE_PRICELIST_ID)
    target_pl = Pricelist.with_context(_ctx).browse(TARGET_PRICELIST_ID)
    if not source_pl.exists() or not target_pl.exists():
        raise UserError(
            "No existe product.pricelist id=%s (origen) o id=%s (destino)."
            % (SOURCE_PRICELIST_ID, TARGET_PRICELIST_ID)
        )
    if source_pl.company_id and source_pl.company_id != source_company:
        log(
            "Sync listas: advertencia — lista origen id=%s tiene company_id=%s (esperado %s)."
            % (SOURCE_PRICELIST_ID, source_pl.company_id.name, source_company.name),
            level="warning",
        )
    if target_pl.company_id and target_pl.company_id != target_company:
        log(
            "Sync listas: advertencia — lista destino id=%s tiene company_id=%s (esperado %s)."
            % (TARGET_PRICELIST_ID, target_pl.company_id.name, target_company.name),
            level="warning",
        )
    # Odoo 18+: `product.pricelist.item` no tiene `sequence`; orden estable por id
    source_lines = source_pl.item_ids.sorted("id")
    n_source = len(source_lines)
    n_removed = len(target_pl.item_ids)
    target_pl.item_ids.unlink()
    n_created = 0
    for line in source_lines:
        new_line = line.copy({"pricelist_id": target_pl.id})
        if new_line.base_pricelist_id and new_line.base_pricelist_id.id == source_pl.id:
            new_line.write({"base_pricelist_id": target_pl.id})
        n_created += 1
    log(
        "Sync listas: %s (id=%s) → %s (id=%s) | lineas_origen=%s | eliminadas_destino=%s | creadas=%s"
        % (source_pl.name, source_pl.id, target_pl.name, target_pl.id, n_source, n_removed, n_created),
        level="info",
    )
```

---

## Notas importantes (para que no te explote en producción)

- **Permisos**: en cron, si el usuario no tiene permisos sobre productos o costos, va a fallar. Por eso el ejemplo usa `sudo()` en los modelos y conviene asignar un **usuario técnico**.
- **Compañías permitidas**: si el cron corre con `allowed_company_ids` restringido, `with_company()` puede leer/escribir mal o dar acceso denegado. Por eso se fuerza `allowed_company_ids` incluyendo ambas compañías.
- **`product.product` vs `product.template`**: el costo normalmente vive a nivel template (y se refleja en variantes). El script funciona con `product.product`, pero si detectás inconsistencias por variantes, conviene migrar a `product.template`.
- **Impacto contable / inventario**: si tenés **valuación automática** y el costo impacta asientos/stock valuation, revisar si este sync debe ejecutarse con reglas adicionales (por ejemplo, solo ciertos productos o con fecha/hora controlada).
- **Listas de precio**: cada ejecución **borra y recrea** todas las líneas de la lista destino (48). Si en Nak hubo ajustes manuales solo en esa lista, se perderán en el próximo cron. Las reglas que en origen dependan de **otra** lista distinta a la 30 no se remapean (solo el caso `base_pricelist_id == 30`).
- **Orden**: conviene que el costo (`standard_price`) quede actualizado **antes** de recalcular precios que usan fórmula sobre costo; en este script el bloque de costos corre primero.

---

## Validación rápida

- Tomar 3 productos al azar y verificar:
  - en **NAKEL SA** el costo \(C\)
  - en **NAK** el costo se actualizó a \(C\)
- Revisar el log del cron (desde la acción planificada o logs del servidor) y que no haya errores.
- Abrir la lista destino en Nak (ej. [Lista 1 id 48](https://nakel.net.ar/odoo/pricelists/48)) y comprobar que el número de líneas y montos coinciden con la lista origen ([id 30](https://nakel.net.ar/odoo/pricelists/30)) en un par de productos de prueba.

