# ✅ Resumen de Permisos para Encargados de Sucursales

## 📊 Estado objetivo (2026-04-18)

Encargados Belgrano: inventario y sucursal **sin** grupo **Product Creation** (maestro de productos y barcodes solo desde Central). Los permisos de inventario siguen en **Inventory / User** + **Encargados Belgrano N**.

## 👥 Encargados y Permisos

| Encargado | Sucursal | Product Creation | Inventory User | Grupo Encargados |
|-----------|----------|------------------|----------------|------------------|
| Manuel Claudia Isabel | Belgrano 1 | ❌ (política) | ✅ | ✅ |
| Varas Adrian Marcelo | Belgrano 2 | ❌ (política) | ✅ | ✅ |
| Robles Angel Jose | Belgrano 3 | ❌ (política) | ✅ | ✅ |
| Ramos Nancy | Belgrano 4 | ❌ (política) | ✅ | ✅ |

## 🔐 Permisos Asignados

### 1. Product Creation (Grupo ID: 20) — no usar en sucursal
**Qué otorgaba:** crear/modificar productos (incl. barcode, `default_code`, etc.).

**Estado:** ❌ **No** debe estar asignado a encargados Belgrano. Retirar si quedó de configuraciones antiguas (`corregir_permisos_encargado_master18.py` o `scripts/asignar_permisos_modificar_productos_encargados.py`).

### 2. Inventory / User (Grupo ID: 50)
**Permite:**
- ✅ Crear transferencias internas (stock.picking)
- ✅ Crear movimientos de stock (stock.move)
- ✅ Ver y ajustar cantidades de stock (stock.quant)
- ✅ Acceso al módulo de inventario

**Estado:** ✅ Ya estaba asignado a todos los encargados

### 3. Grupo Encargados [Sucursal] (IDs: 97, 98, 99, 100)
**Función:**
- ✅ Filtra la información visible por ubicación
- ✅ Cada encargado solo ve información de su sucursal
- ✅ No ven información de Nakel Central u otras sucursales

**Estado:** ✅ Creado y asignado

## 📋 Permisos por Funcionalidad

### ❌ Maestro de productos (sucursal)
- **Política:** Central gestiona productos y barcodes; encargados Belgrano **no** tienen Product Creation.
- **Comprobación:** `verificar_permisos_completos_encargados_master18.py` avisa si aún figura Product Creation.

### ✅ Crear Transferencias Internas
- **Permiso necesario:** Inventory / User
- **Estado:** ✅ Todos los encargados pueden crear transferencias
- **Nota:** Las reglas con `perm_create` aplican también al **crear**: el albarán nuevo debe cumplir el dominio (en la práctica suele cumplirse si el **tipo de operación** es del almacén de la sucursal, aunque el origen sea CEN).

### ✅ Reabastecer desde Nakel Central (master_18 — verificado 2026-03-31)
- **Permiso necesario:** Inventory / User + grupo Encargados [sucursal]
- **Estado:** ⚠️ Funciona solo con un flujo concreto; el tipo de operación **«Nakel Central: Traslados internos»** **no** aparece en el desplegable del encargado.
- **Por qué:** La regla `stock.picking.type` limita a `warehouse_id` = almacén de la sucursal (ej. B1=15). Los tipos de CEN (`warehouse_id`=14) quedan ocultos.
- **Funcionamiento real:** Crear **«[Sucursal]: Traslados internos»** (ej. tipo id 133 en B1), **origen** `CEN/Existencias`, **destino** `B*/Existencias`. En la base existen albaranes hechos así (ej. `B1/INT/*` con `location_id` CEN y `picking_type_id` de Belgrano 1).
- **No usar** como sustituto del flujo anterior: **«Control de calidad»** (origen/destino por defecto distintos: Entrada → QC).

### ✅ Ajustes de Inventario
- **Permiso necesario:** Inventory / User (en master_18)
- **Estado:** ⚠️ Necesita verificación práctica
- **Nota:** En Odoo 18, los ajustes de inventario pueden manejarse a través de stock.quant (WRITE permitido)

### ✅ Movimientos Internos dentro de la Sucursal
- **Permiso necesario:** Inventory / User
- **Estado:** ✅ Pueden crear transferencias entre ubicaciones de su sucursal
- **Funcionamiento:** Pueden crear transferencias entre sub-ubicaciones dentro de B1, B2, B3 o B4

## 🚫 Restricciones por Reglas de Registro

Las reglas de registro (ir.rule) aseguran que:

1. **Solo ven transferencias de su sucursal:**
   - Transferencias donde `location_id` o `location_dest_id` pertenecen a su sucursal
   - No ven transferencias exclusivamente entre otras sucursales

2. **Solo ven stock de su sucursal:**
   - Stock ubicado en ubicaciones de su sucursal (`location_id child_of` su ubicación)
   - No ven stock de Nakel Central u otras sucursales

3. **Solo ven tipos de operación de su warehouse:**
   - Tipos de operación asociados a su warehouse
   - No ven tipos de operación de otros warehouses

**IMPORTANTE:** Con `perm_create` activo en la regla, **crear** también exige que el registro cumpla el dominio. Lo que sí ocurre es que el encargado **no elige** el tipo de operación de CEN (regla en `stock.picking.type`), y debe usar el traslado interno **de su sucursal** ajustando ubicaciones.

## 🔄 Qué Pueden Hacer los Encargados

### ✅ SÍ pueden:
1. **Crear transferencias:** Origen/destino internos de la compañía; para pedir desde Central usan el tipo **Traslados internos de su sucursal** y fijan origen **CEN/Existencias** (no ven el tipo «Traslados internos» de Nakel Central).
2. **Ver transferencias:** Solo las que involucran su sucursal
3. **Ajustar stock:** A través de stock.quant (tienen permiso WRITE)
4. **Crear movimientos internos:** Dentro de su sucursal
5. **Reabastecer:** Mismo traslado interno de sucursal con origen manual **CEN/Existencias** → **B*/Existencias** (ver sección arriba).
6. **Usar productos en ventas/POS:** lectura y consumo del maestro; **no** editarlo en sucursal.

### ❌ NO pueden:
1. **Ver información de otras sucursales:** Filtrado por reglas de registro
2. **Ver stock/cantidades en Nakel Central:** `stock.quant` solo de su sucursal (no ven existencias en CEN en informes de stock por ubicación).
3. **Eliminar transferencias creadas por otros:** Solo pueden modificar las que ellos crean o tienen permisos

## 🛠️ Scripts de Gestión

### Asignar Permisos
```bash
cd /media/klap/raid5/cursor_files/nakel/usuarios/PERMISOS
python3 asignar_permisos_completos_encargados_master18.py
```

### Verificar Permisos
```bash
cd /media/klap/raid5/cursor_files/nakel/usuarios/PERMISOS
python3 verificar_permisos_completos_encargados_master18.py
```

### Configurar Reglas de Ubicación
```bash
cd /media/klap/raid5/cursor_files/nakel/usuarios/PERMISOS
python3 configurar_permisos_inventario_por_sucursal_master18.py
```

## 📝 Notas Importantes

1. **Los cambios requieren reinicio de sesión:** Los usuarios deben cerrar sesión y volver a iniciar para que los nuevos permisos surtan efecto.

2. **Reglas y creación:** El albarán creado debe cumplir el dominio de `stock.picking` (origen o destino en su sucursal, o tipo de operación del almacén de la sucursal). Para CEN→sucursal hace falta el tipo de traslado **de la sucursal** y origen manual CEN; no alcanza con elegir solo el tipo de CEN (no lo ven).

3. **Product Creation:** No aplica a encargados Belgrano; el maestro de productos es responsabilidad de Central.

4. **Inventory / User es suficiente:** En master_18, el grupo "User" de Inventory es suficiente para la mayoría de operaciones. No hay un grupo "Manager" separado.

## ✅ Verificación Final

Después de asignar permisos, verificar:

1. ✅ **Ninguno** tiene Product Creation (política sucursal)
2. ✅ Todos tienen Inventory / User
3. ✅ Todos tienen su grupo Encargados [Sucursal]
4. ✅ Pueden crear transferencias
5. ✅ Solo ven información de su sucursal

---

**Última actualización:** 2026-04-18 (política: sin Product Creation en encargados Belgrano)  
**Ambiente:** master_18 (misma línea aplicable a master_dev salvo IDs)  
**Odoo Version:** 18.0 Enterprise
