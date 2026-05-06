# Sync costo: NAKEL SA → NAK (standard_price)

## Objetivo

Mantener sincronizado el **costo** (`standard_price`) desde la empresa **NAKEL SA** hacia **NAK** para productos vendibles, mediante una **Acción planificada** (`ir.cron`) en Odoo.

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
   - **Nombre**: `Sync costos NAKEL SA → NAK`
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
- evita pisar con cero
- deja log con cantidad actualizada

```python
SOURCE_COMPANY_NAME = "Nakel SA"
TARGET_COMPANY_NAME = "Nak"

Company = env["res.company"].sudo()
Product = env["product.product"].sudo()

source_company = Company.search([("name", "=", SOURCE_COMPANY_NAME)], limit=1)
target_company = Company.search([("name", "=", TARGET_COMPANY_NAME)], limit=1)

if not source_company or not target_company:
    raise UserError("No se encontró la empresa origen o destino (revisar nombres).")

# Importante en multicompany: asegurar compañías permitidas en contexto del cron
allowed_company_ids = list(set((env.context.get("allowed_company_ids") or []) + [source_company.id, target_company.id]))

products = Product.with_context(active_test=False, allowed_company_ids=allowed_company_ids).search([
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
```

---

## Notas importantes (para que no te explote en producción)

- **Permisos**: en cron, si el usuario no tiene permisos sobre productos o costos, va a fallar. Por eso el ejemplo usa `sudo()` en los modelos y conviene asignar un **usuario técnico**.
- **Compañías permitidas**: si el cron corre con `allowed_company_ids` restringido, `with_company()` puede leer/escribir mal o dar acceso denegado. Por eso se fuerza `allowed_company_ids` incluyendo ambas compañías.
- **`product.product` vs `product.template`**: el costo normalmente vive a nivel template (y se refleja en variantes). El script funciona con `product.product`, pero si detectás inconsistencias por variantes, conviene migrar a `product.template`.
- **Impacto contable / inventario**: si tenés **valuación automática** y el costo impacta asientos/stock valuation, revisar si este sync debe ejecutarse con reglas adicionales (por ejemplo, solo ciertos productos o con fecha/hora controlada).

---

## Validación rápida

- Tomar 3 productos al azar y verificar:
  - en **NAKEL SA** el costo \(C\)
  - en **NAK** el costo se actualizó a \(C\)
- Revisar el log del cron (desde la acción planificada o logs del servidor) y que no haya errores.

