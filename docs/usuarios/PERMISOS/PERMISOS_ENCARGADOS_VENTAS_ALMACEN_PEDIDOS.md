# Permisos encargados: Ventas, almacén por defecto, pedidos internos a Central, reabastecimiento y conteo

**Fecha:** 2025-01-23  
**Base:** master_18  
**Usuario de referencia:** Manuel Claudia Isabel (id=96) – Encargados Belgrano 1

---

## 1. Ventas: ¿desde qué almacén se descuenta? (CEN vs B1)

### Comportamiento esperado

Al crear una **orden de venta** desde **VENTAS**, el sistema debe tomar el **almacén de la sucursal del encargado** (Belgrano 1 para Claudia), no Nakel Central (CEN). Así la entrega y los tipos de operación son de B1 y el encargado puede leer/crear sin error.

### Qué está configurado (plantilla)

- **property_warehouse_id** se asigna **automáticamente** según la sucursal del encargado:
  - **Encargados Belgrano 1** → almacén por defecto = **Belgrano 1 (B1)**
  - **Encargados Belgrano 2** → **B2**
  - **Encargados Belgrano 3** → **B3**
  - **Encargados Belgrano 4** → **B4**
- Lo aplican:
  - **configurar_permisos_inventario_por_sucursal_master18.py** al asignar el grupo a cada usuario.
  - **corregir_permisos_encargado_master18.py** al corregir un encargado (por ID o --login).
- Si el módulo Ventas usa este campo como almacén por defecto, las órdenes nuevas del encargado salen con Almacén = su sucursal.

### Si sigue saliendo CEN

1. Al **crear una nueva orden de venta**, revisar el campo **Almacén (Warehouse)**.
2. Si viene **Nakel Central**, cambiarlo manualmente a **Belgrano 1** (para Claudia) y guardar.
3. Si quieres que **siempre** use B1 por defecto para encargados, hace falta un **default en el modelo** (módulo personalizado) que use `user.property_warehouse_id` al crear `sale.order`.

### Error que se evita

Si la orden usa CEN, al confirmar/facturar Odoo intenta usar "Tipo de recolección, Nakel Central: Recolectar" y el encargado no podía leerlo. Con las reglas actuales **sí puede leer** tipos de Central (ver punto 2), pero lo correcto para ventas de sucursal es que la orden use **su almacén (B1)**.

---

## 2. Pedidos internos a Nakel Central

### Objetivo

Los encargados (Claudia y resto de sucursales) deben poder:

- **Solicitar traslado interno a Central** (ej. no hay stock de producto X en B1 → pedir a Central).
- Central procesa, aprueba y envía.

### Cambios aplicados en master_18

- **Reglas de `stock.picking.type`** (Encargados Belgrano 1/2/3/4):  
  Dominio **solo sucursal** (warehouse_id = B1/B2/B3/B4). Así el **resumen de inventario** muestra solo operaciones de su sucursal (no tarjetas de Nakel Central).  
  Para **pedidos internos a Central**: usar menú **Traslados internos** (si el flujo lo permite desde su sucursal) o solicitar a un usuario con acceso a Central.

- **Reglas de `stock.picking`** y **`stock.move`** siguen permitiendo:
  - Transferencias donde **origen o destino** es su sucursal (p. ej. B1).
  - Transferencias cuyo **tipo de operación** es de su sucursal (picking_type_id.warehouse_id = B1) o movimientos que pertenecen a un picking de su sucursal.

Con esto, los encargados pueden crear y ver **traslados internos entre su sucursal y Central** (B1↔CEN, B2↔CEN, etc.).

---

## 3. Reabastecimiento (Inventario → Operaciones → Reabastecimiento)

### Objetivo

Los encargados deben poder **ver el menú** y usar las **reglas de reabastecimiento** (stock.warehouse.orderpoint) de su sucursal (máximos/mínimos y reabastecimiento manual).

### Cambios aplicados en master_18

- **ir.model.access** para el grupo de cada encargado (Encargados Belgrano 1/2/3/4) sobre **stock.warehouse.orderpoint** con permisos **CRUD** (crear, leer, escribir, eliminar).
- **Regla de registro** para `stock.warehouse.orderpoint`: cada encargado ve solo las reglas cuya `location_id` es de su sucursal (creada por `configurar_permisos_inventario_por_sucursal_master18.py`).
- **Menú Reabastecimiento**: si los encargados no ven **Inventario → Operaciones → Reabastecimiento**, ejecutar:
  ```bash
  python3 asignar_menu_reabastecimiento_encargados_master18.py
  ```
  (En master_dev: añadir `--master-dev`). Ese script añade los grupos Encargados Belgrano 1/2/3/4 al menú para que sea visible. Después, los encargados deben cerrar sesión y volver a entrar.

### Pedidos de reabastecimiento con origen CEN/Existencias (Central)

Es frecuente que informen que **no pueden “generar” el pedido de reabastecimiento** hacia Central. No suele ser falta de menú ni de `orderpoint`, sino el **resto de reglas**:

1. **`stock.picking.type`**: el dominio en `configurar_permisos_inventario_por_sucursal_master18.py` es **`warehouse_id` = solo su sucursal** (B1/B2/B3/B4). Por eso **no ven** el tipo de operación *«Nakel Central: Traslados internos»* ni otros tipos cuyo almacén sea CEN.
2. **`stock.quant`**: solo ven existencias **de su sucursal**; no consultan stock en CEN desde listas estándar.
3. Al **confirmar** un pedido desde la pantalla de reabastecimiento, Odoo puede intentar crear traslados con un **tipo de operación de Central** o rutas que exigen permisos/vistas que el encargado no tiene → **error de acceso** o flujo bloqueado.

**Flujo operativo que sí encaja con las reglas actuales** (verificado en master_18, 2026-03-31; detalle en `RESUMEN_PERMISOS_ENCARGADOS.md`):

- Crear **Traslado interno** con tipo **«[Sucursal]: Traslados internos»** (ej. Belgrano 1).
- **Origen manual:** `CEN/Existencias`.
- **Destino:** `B*/Existencias` (la sucursal correspondiente).

Así el `picking_type_id` sigue siendo del almacén de la sucursal y el dominio de `stock.picking` se cumple (origen o destino en la sucursal o tipo de la sucursal).

**Si se quiere que el botón “Pedir” / reabastecimiento desde la lista genere directamente ese flujo**, hace falta o bien **ajustar rutas y tipos** para que no dependan de tipos de CEN, o bien **ampliar** la regla `stock.picking.type` con una OR a `warehouse_id = CEN` (impacto: pueden volver a aparecer tarjetas de Central en el resumen de inventario; valorar con negocio).

#### Opción A en el script (mismo grupo Encargados, regla más amplia)

**Qué amplía:** solo **`stock.picking.type`**: `warehouse_id` = sucursal **o** CEN (código `CEN`). **No** modifica `stock.picking` ni `stock.move` por defecto.

**Comandos** (`PERMISOS/configurar_permisos_inventario_por_sucursal_master18.py`):

```bash
# Piloto solo Encargados Belgrano 1 en master_dev (probar con --dry-run antes):
python3 configurar_permisos_inventario_por_sucursal_master18.py --master-dev \
  --incluir-cen-en-tipos-operacion --solo-sucursal "Belgrano 1"

# Las cuatro sucursales (sin --solo-sucursal):
python3 configurar_permisos_inventario_por_sucursal_master18.py --master-dev \
  --incluir-cen-en-tipos-operacion
```

En **master_18** omitir `--master-dev`. Tras aplicar, el usuario encargado debe **cerrar sesión y volver a entrar**.

### Punto de venta: tablero de cajas (solo las de la sucursal)

**Problema:** En el tablero de **Punto de venta** los encargados veían **todas** las cajas (Belgrano1-C1/C2 … Belgrano4-C1/C2).

**Causa de datos:** En `master_dev`, `pos.config.warehouse_id` está en **Nakel Central** para todas las cajas; filtrar solo por ese campo **no** separa sucursales.

**Solución:** Regla `ir.rule` sobre **`pos.config`** para cada grupo **Encargados Belgrano N**, con dominio:

`[('picking_type_id.warehouse_id', '=', <id almacén B1/B2/B3/B4>)]`

(el tipo de operación de entrega del POS sí está ligado al almacén de la sucursal).

Lo crea/actualiza el mismo script `configurar_permisos_inventario_por_sucursal_master18.py` junto al resto de reglas de encargados. Tras desplegar en una base, **cerrar sesión y volver a entrar** con el usuario encargado.

### Productos: solo poder corregir el código de barras

**Política 2026-04 (Nakel):** en sucursal Belgrano **no** se edita el maestro de productos (incl. barcode) desde encargados; lo siguiente aplica solo si negocio reactivara el flujo “solo barcode” o usuarios distintos.

**Límite de Odoo:** `ir.model.access` e `ir.rule` son por **modelo** (y registro), no por **campo**. No existe en estándar “solo escritura en `barcode`” solo con grupos y reglas.

**Enfoque recomendado:** módulo personalizado que hereda `product.template` y `product.product`, sobrescribe `write` y, si el usuario pertenece al grupo **Nakel: Producto solo código de barras**, solo permite claves `barcode` en `vals`; cualquier otro campo → `AccessError`.

- **Código:** `nakel/nakel_product_encargado_barcode` (depende de `product`).
- **Grupo de seguridad (XML ID):** `nakel_product_encargado_barcode.group_nakel_producto_solo_barcode`.
- **Encargados:** script `PERMISOS/implied_grupo_solo_barcode_encargados.py` añade ese grupo como *implied* de **Encargados Belgrano 1–4** (tras instalar el módulo en el servidor):

```bash
cd PERMISOS
python3 implied_grupo_solo_barcode_encargados.py --master-dev
```

- **Automatismos / código interno:** usar contexto `skip_nakel_barcode_only_check=True` en el `write` si algún proceso técnico debe actualizar otros campos actuando como usuario restringido.
- **Interfaz:** el formulario de producto puede seguir mostrando otros campos; al guardar cambios que no sean solo el barcode, Odoo rechazará el guardado. Opcional: vistas heredadas `readonly` por grupo para UX (mismo módulo o otro).
- **Códigos de barras múltiples / packaging:** si usan modelos extra (p. ej. líneas de códigos), habría que ampliar la lista permitida en el mismo módulo.

**Nota:** Si los encargados tienen **Product Creation** u otros permisos amplios, siguen pudiendo **leer** y usar el producto; la restricción aplica a **qué campos pueden persistir** en `write`. Quien **no** lleve el grupo Nakel no se ve afectado por esta regla. Los usuarios con **Ajustes / Administración** (`base.group_system`) no quedan sujetos a este filtro en el código del módulo.

---

## 4. Conteo de inventario (controles mensuales en sucursal)

### Objetivo

Los encargados deben poder **realizar conteo de inventario** en su sucursal (controles mensuales de stock).

### Estado

- En Odoo 18, el modelo de inventario/conteo puede ser **stock.request.count** u otros según versión y módulos.
- Los encargados ya tienen permisos y reglas sobre **stock.quant** (solo ubicaciones de su sucursal), lo que suele ser la base para ver existencias en su almacén.

Si al usar la funcionalidad de **conteo / inventario** aparece un **Error de acceso** sobre un modelo concreto (p. ej. `stock.request.count` o `stock.inventory`), se puede:

1. Añadir **ir.model.access** para ese modelo para los grupos Encargados B1/B2/B3/B4.
2. Si hace falta, añadir una **regla de registro** para que solo vean conteos de su sucursal.

---

## 5. Resumen de scripts y reglas (plantilla)

| Qué | Dónde | Comando / nota |
|-----|--------|------------------|
| Tipos de operación | Reglas `stock.picking.type` | Por defecto: solo sucursal. Opcional: `--incluir-cen-en-tipos-operacion` (sucursal **o** CEN) para ver tipos de Nakel Central en el modal. |
| Cajas PDV (tablero) | Reglas `pos.config` | `picking_type_id.warehouse_id` = almacén de la sucursal (ver subsección “Punto de venta” arriba). |
| Accesos CRUD (ventas, inventario, orderpoint) | ir.model.access | `python3 asignar_ir_model_access_encargados_master18.py` |
| Menú Reabastecimiento visible para encargados | ir.ui.menu | `python3 asignar_menu_reabastecimiento_encargados_master18.py` |
| Almacén por defecto por sucursal | res.users | Asignado por configurar_permisos... o corregir_permisos_encargado... (B1/B2/B3/B4 según grupo Encargados) |
| Crear / actualizar reglas por sucursal | Script de configuración | `python3 configurar_permisos_inventario_por_sucursal_master18.py [--master-dev] [--incluir-cen-en-tipos-operacion] [--solo-sucursal "Belgrano 1"]` |
| Solo barcode en productos | Módulo + implied | Instalar `nakel_product_encargado_barcode`; luego `python3 implied_grupo_solo_barcode_encargados.py [--master-dev]` |

---

## 6. Asignar encargado desde la interfaz Odoo (“solo tildar la opción”)

Si en **Configuración → Usuarios** solo marcas el grupo **Inventario / Encargados Belgrano 1** (o 2, 3, 4) para un usuario, ese usuario **no** recibe automáticamente el **almacén por defecto** (property_warehouse_id) — Odoo no lo hace por grupo. Para que quede todo aplicado (grupos + almacén por defecto), ejecuta después:

```bash
python3 corregir_permisos_encargado_master18.py --login email@encargado.ar
# o por ID:
python3 corregir_permisos_encargado_master18.py 96
```

Ese script asigna los grupos que falten y **fija property_warehouse_id** según la sucursal (B1/B2/B3/B4). En **master_dev** añade `--master-dev`.

## 7. Checklist para encargados

- [ ] Al crear una **orden de venta** desde VENTAS, comprobar que **Almacén** = su sucursal (Belgrano 1 para Claudia). Si no, cambiarlo antes de confirmar (o asegurar que se ejecutó corregir_permisos_encargado para ese usuario).
- [ ] **Pedidos internos a Central**: con regla **solo sucursal**, traslado con tipo de la sucursal y origen **CEN/Existencias**; si activaron **`--incluir-cen-en-tipos-operacion`**, también pueden usar el tipo **Nakel Central: Traslados internos** (y ver tarjetas de Central en el resumen).
- [ ] **Reabastecimiento**: acceso a `stock.warehouse.orderpoint` y menú; si “Pedir” hacia Central falla, usar el flujo de traslado interno anterior o valorar ampliar regla `stock.picking.type` (ver §3).
- [ ] **Conteo de inventario**: si aparece error de acceso al usar la función de conteo, indicar el modelo del mensaje para añadir permisos/regla.
- [ ] **Punto de venta**: en el tablero de cajas deben verse solo **dos** POS por encargado (los de su sucursal). Si ven las ocho, ejecutar el script de permisos en esa base y volver a iniciar sesión.
- [ ] **Productos**: si está activo el módulo solo-barcode, un encargado solo debe poder **guardar** cambios en el campo código de barras; otras ediciones deben dar error de acceso.

---

**Última actualización:** 2026-04-05 (módulo `nakel_product_encargado_barcode` + script implied; reglas `pos.config`; opción A en script de permisos)
