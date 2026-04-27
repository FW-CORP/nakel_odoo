# Cron: desecho automático Roturas 2 (master_dev)

**Base:** `master_dev` (https://nakel.net.ar)  
**Objetivo:** ejecutar automáticamente **desecho (scrap)** del stock que quede en:

- `CEN/Roturas 2` (stock.location **id=541**)
- `B3/Roturas 2` (stock.location **id=542**)

Esto crea movimientos de **`stock.scrap`** y valida el desecho, para que quede trazabilidad (en vez de “poner a 0” con un inventario manual).

## Datos verificados por consulta (XML-RPC)

- `CEN/Roturas 2`: `usage=internal`, `scrap_location=True`, `company_id=1` (Nakel SA), **id=541**
- `B3/Roturas 2`: `usage=internal`, `scrap_location=True`, `company_id=1` (Nakel SA), **id=542**
- Destino de scrap recomendado: `Virtual Locations/Scrap` (company 1), **id=16**

## Crear el Cron (UI Odoo)

En Odoo con **modo desarrollador**:

1. Ir a **Ajustes → Técnico → Automatización → Acciones planificadas** (`Scheduled Actions`).
2. Crear una nueva.
3. Completar:
   - **Nombre**: `Desecho automático Roturas 2 (CEN + B3)`
   - **Activo**: ✅
   - **Usuario**: un usuario técnico con permisos de Inventario (ideal: `NakelBot` o técnico)
   - **Modelo**: `Desecho` (`stock.scrap`) *(o cualquier modelo; el código usa `env[...]`)*
   - **Ejecutar cada**: por ejemplo `1` **días** (o lo que defina negocio)
   - **Siguiente ejecución**: horario de baja actividad (ej. madrugada)
   - **Acción a realizar**: `Ejecutar código Python`
4. Pegar este código.

## Código Python (para `ir.cron` / “Ejecutar código Python”)

> Nota: si el volumen fuera grande, este código procesa en “chunks” (lotes) para no explotar tiempos.

> **Importante (Odoo):** en “Ejecutar código Python” **no podés usar `return` a nivel módulo** (no hay función envolvente). Eso produce `SyntaxError: 'return' outside function`. Usá `if ...:` y/o `log(...)`.

```python
# Desecha todo el stock positivo en CEN/Roturas 2 y B3/Roturas 2.
# Crea stock.scrap y lo valida para dejar trazabilidad.

LOC_NAMES = ["CEN/Roturas 2", "B3/Roturas 2"]
SCRAP_VIRTUAL_NAME = "Virtual Locations/Scrap"
COMPANY_ID = 1  # Nakel SA
BATCH = 200

Location = env["stock.location"].sudo()
Quant = env["stock.quant"].sudo()
Scrap = env["stock.scrap"].sudo()

locs = Location.search([("complete_name", "in", LOC_NAMES), ("company_id", "=", COMPANY_ID)])
if not locs:
    log("CRON Roturas2: no se encontraron ubicaciones (revisar nombres/company).", level="warning")
else:
    scrap_loc = Location.search(
        [
            ("complete_name", "=", SCRAP_VIRTUAL_NAME),
            ("company_id", "=", COMPANY_ID),
        ],
        limit=1,
    )
    if not scrap_loc:
        log("CRON Roturas2: no se encontró ubicación de scrap virtual.", level="warning")
    else:
        domain = [("location_id", "in", locs.ids), ("quantity", ">", 0)]
        processed = 0

        while True:
            quants = Quant.search(domain, limit=BATCH)
            if not quants:
                break

            for q in quants:
                vals = {
                    "product_id": q.product_id.id,
                    "scrap_qty": q.quantity,
                    "location_id": q.location_id.id,
                    "scrap_location_id": scrap_loc.id,
                    # preserva trazabilidad si existe:
                    "lot_id": q.lot_id.id or False,
                    "package_id": q.package_id.id or False,
                    "owner_id": q.owner_id.id or False,
                    "company_id": COMPANY_ID,
                    # Opcional: "origin": "CRON Roturas 2",
                }
                s = Scrap.create(vals)
                s.action_validate()
                processed += 1

        log("CRON Roturas2: desechos validados=%s" % processed, level="info")
```

## Validación (solo lectura)

Para confirmar que el cron funcionó:

- En **Desechos** (`stock.scrap`) filtrar por fecha/ubicación `CEN/Roturas 2` y `B3/Roturas 2`.
- Ver que los `stock.quant` en esas ubicaciones queden en **0** (o sin quants con `quantity > 0`).

## Riesgos / notas

- Si hay productos con **tracking por lote** y quants mezclados, el scrap se hace por quant preservando `lot_id` cuando exista.
- Si el volumen de quants es muy alto, subir `BATCH` o programar más frecuente.
- Si querés que el cron **solo deseche “viejo”** (por antigüedad), hay que sumar criterio (no está en este mínimo).

