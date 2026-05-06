# Incidente resuelto: upgrade `nakel_wave_picking_link` y botones OV (olas / OUT)

**Fecha:** 2026-04-29  
**Entorno:** `https://nakel.net.ar`, base **`master_dev`** (Odoo 18 Enterprise).  
**Estado:** resuelto (upgrade OK tras alinear código en disco, deploy y reinicio / `-u`).

## Síntoma

- Al **Actualizar** el módulo desde Apps: `RPC_ERROR` / `ParseError` en `views/sale_order_views.xml`.
- Mensaje (ES): **`action_nakel_open_wave no es una acción válida en sale.order`**.

## Qué significa el mensaje (Odoo 18)

En `ir.ui.view` la validación de `<button type="object">` usa `getattr(modelo, nombre, None)`. Si no hay método **público** con ese nombre en `sale.order`, Odoo muestra ese texto (traducción de *“is not a valid action on sale.order”*). **No** implica necesariamente `type="action"` mal puesto: suele ser **método ausente en el registry** al validar.

## Causas que vimos / cómo descartarlas

### 1) XML del botón

Los smart buttons en `sale.order` deben usar explícitamente:

- `type="object"`
- `name="action_nakel_open_wave"` / `action_nakel_open_out_pickings"`

Si falta `type="object"`, el default interpreta otra semántica y el error puede confundir.

### 2) Deploy que mezcla versiones (`cp` vs espejo)

El script histórico usaba `cp -r staging/* dest/`, que **no elimina** archivos viejos en el servidor. Caso típico: `views/*.xml` nuevos + `models/sale_order.py` **viejo** (sin métodos) → el XML pide métodos que el Python cargado no define.

**Corrección en repo:** `tools/deploy/deploy_addon.sh` pasó a **`rsync -a --delete`** del staging al directorio final del módulo (espejo del addon).

### 3) Dos copias del mismo módulo en `addons_path`

Si hay **otro** `nakel_wave_picking_link` **antes** en `addons_path`, Odoo puede cargar ese árbol aunque el operador inspeccione `/opt/odoo/custom-addons/...`.

Comprobar en el servidor:

```bash
sudo grep -E '^addons_path' /etc/odoo/odoo.conf
sudo find /opt /usr -type d -name 'nakel_wave_picking_link' 2>/dev/null
```

Y con shell Odoo (misma `-c` y `-d`):

```python
import odoo.modules.module as mm
print(mm.get_module_path("nakel_wave_picking_link"))
```

Debe coincidir con la ruta canónica desplegada (p. ej. `/opt/odoo/custom-addons/nakel_wave_picking_link`).

### 4) Código en disco correcto pero servicio con registry viejo

Tras desplegar **Python** nuevo, conviene **reiniciar** el servicio Odoo y luego ejecutar **`-u nakel_wave_picking_link`** (stop → `--stop-after-init` → start), como sugiere el mensaje final de `deploy_addon.sh`.

## Verificación rápida por XML-RPC

Con credenciales de la base afectada, comprobar:

1. `sale.order.fields_get` contiene `nakel_wave_batch_id`.
2. `execute_kw('sale.order', 'action_nakel_open_wave', [[<id_ov>]])` **no** debe fallar con *method does not exist*.
3. `ir.module.module` para `nakel_wave_picking_link`: `latest_version` coherente con `__manifest__.py` tras upgrade exitoso.

## Cambios de producto en el módulo (18.0.1.0.6)

- Formulario **OV**: smart buttons **Ola/Wave** y **OUT** (`type="object"`).
- Menú **Ventas → Olas/Waves** (lista `stock.picking.batch`).
- Árbol / búsqueda OV: campo y filtros por `nakel_wave_batch_id`.
- `models/sale_order.py`: `action_nakel_open_wave`, `action_nakel_open_out_pickings`.
- Migración `migrations/18.0.1.0.6/post-migrate.py`: noop (solo UI).

## Nota sobre `deploy.sh` dentro del addon

El archivo `addons/nakel_wave_picking_link/deploy.sh` es un **wrapper** pensado para ejecutarse desde el **checkout del repo** (`nakel_odoo/`). Si se ejecuta desde `/opt/odoo/custom-addons/...`, el cálculo de `REPO_ROOT` con `../..` **no** apunta al repositorio. Para deploy usar:

```bash
tools/deploy/deploy_addon.sh nakel_wave_picking_link odoo@<host> master_dev
```

(desde la raíz `nakel_odoo` del repo).
