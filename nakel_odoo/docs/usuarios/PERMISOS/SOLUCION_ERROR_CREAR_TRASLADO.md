# 🔧 Solución: Error al Crear Traslados (stock.picking)

## 📋 Problema Reportado

**Error (encargados de sucursal):**
```
Error de acceso

Estos registros están restringidos.

[Nombre] (id=XX) no tiene acceso 'crear' a:

Trasladar (stock.picking)

Si necesita acceso, pregúntele a un administrador.
```

**Usuarios afectados:** Cualquier encargado de sucursal (Belgrano 1, 2, 3, 4). Ejemplos documentados:
- **Varas Adrian Marcelo** (id=102) – Belgrano 2
- **Manuel Claudia Isabel** (id=96) – Belgrano 1

## 🔍 Diagnóstico Realizado

### Verificación de Permisos (2025-01-XX)

1. **Permisos de Acceso (ir.model.access):** ✅ Correctos
   - Usuario tiene grupo "Inventory / User" (ID: 50) con permisos de creación
   - Usuario tiene grupo "Invoicing" (ID: 23) con permisos de creación
   - Usuario tiene grupo "User" (POS) (ID: 65) con permisos de creación

2. **Reglas de Registro (ir.rule):** ✅ Correctas
   - Regla "Encargados Belgrano 2: Ver solo transferencias de Belgrano 2" (ID: 381)
   - `perm_create: True` ✅
   - `perm_write: True` ✅
   - `perm_read: True` ✅
   - Dominio: `['|', ('location_id', 'child_of', 116), ('location_dest_id', 'child_of', 116)]`
   - Activa: ✅

3. **Grupos del Usuario:** ✅ Correctos
   - "Encargados Belgrano 2" (ID: 98) ✅
   - "Inventory / User" (ID: 50) ✅
   - "Product Creation" (ID: 20) — **no** requerido en encargados Belgrano (política 2026-04); puede retirarse

## ✅ Solución

El diagnóstico muestra que **todos los permisos están correctamente configurados**. El problema probablemente se debe a:

### 1. Caché de Sesión
El usuario necesita **cerrar sesión completamente** y volver a iniciar para que los cambios de permisos surtan efecto.

**Pasos:**
1. Cerrar sesión en Odoo
2. Cerrar completamente el navegador (o limpiar caché)
3. Volver a iniciar sesión

### 2. Verificación Post-Reinicio

Después de reiniciar sesión, el usuario debería poder:
- ✅ Crear traslados (stock.picking)
- ✅ Ver solo transferencias de Belgrano 2
- ✅ Crear transferencias desde/hacia B2/Existencias

## 🛠️ Scripts de Verificación

### Diagnosticar Permisos
```bash
cd /media/klap/raid5/cursor_files/nakel/usuarios/PERMISOS
python3 diagnosticar_permisos_crear_traslado_master18.py
```

### Corregir Permisos (cualquier encargado)
```bash
cd /media/klap/raid5/cursor_files/nakel/usuarios/PERMISOS
# Por ID de usuario (ej: Manuel Claudia Isabel = 96)
python3 corregir_permisos_encargado_master18.py 96
# Por login
python3 corregir_permisos_encargado_master18.py --login golosinasbelgrano1@nakel.ar
```
Para solo Belgrano 2 (Varas): `python3 corregir_permisos_varas_belgrano2_master18.py`

### Verificar Todos los Permisos
```bash
cd /media/klap/raid5/cursor_files/nakel/usuarios/PERMISOS
python3 verificar_permisos_completos_encargados_master18.py
```

## 📊 Estado Actual de Permisos

### Varas Adrian Marcelo (ID: 102)
- ✅ **Grupo:** Encargados Belgrano 2 (ID: 98)
- ✅ **Grupo:** Inventory / User (ID: 50)
- **Grupo Product Creation (ID: 20):** no forma parte del objetivo para encargados Belgrano (inventario sí con Inventory/User + Encargados sucursal).
- ✅ **Permiso de Acceso:** stock.picking CREATE ✅
- ✅ **Regla de Registro:** Activa con perm_create=True ✅

## ⚠️ Posibles Causas Adicionales

Si después de reiniciar sesión el problema persiste:

### 1. Ubicaciones no disponibles
Verificar que el usuario puede acceder a las ubicaciones necesarias:
- B2/Existencias (ID: 116) y sub-ubicaciones
- Ubicaciones origen/destino para el traslado

### 2. Tipo de Operación (stock.picking.type)
Verificar que el usuario puede acceder a los tipos de operación necesarios para crear traslados.

### 3. Restricciones de Multi-Company
Si hay múltiples compañías configuradas, verificar que el usuario está en la compañía correcta.

## 🔄 Si el Problema Persiste

1. **Ejecutar diagnóstico completo:**
   ```bash
   python3 diagnosticar_permisos_crear_traslado_master18.py
   ```

2. **Verificar en Odoo directamente:**
   - Configuración > Usuarios y Compañías > Usuarios
   - Buscar "Varas Adrian Marcelo"
   - Verificar grupos asignados
   - Verificar que está activo

3. **Verificar reglas de registro:**
   - Configuración > Técnico > Seguridad > Reglas de Registro
   - Buscar "Encargados Belgrano 2"
   - Verificar que está activa
   - Verificar permisos (perm_create debe ser True)

4. **Verificar permisos de acceso:**
   - Configuración > Técnico > Seguridad > Control de Acceso
   - Buscar "stock.picking"
   - Verificar que los grupos del usuario tienen permiso de creación

## 📝 Notas

- **Base de datos:** master_18
- **Encargados por sucursal:** Belgrano 1 (id=96), Belgrano 2 (id=102), Belgrano 3, Belgrano 4
- Si el usuario **ya tiene** Encargados [Sucursal] + Inventory/User (sin necesidad de Product Creation) y sigue el error, **obligatorio**: cerrar sesión por completo y volver a iniciar sesión (caché de permisos).

---

**Última actualización:** 2025-01-23  
**Autor:** Corolla - Asistente Técnico FWCORP
