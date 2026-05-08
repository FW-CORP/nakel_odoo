# 🔐 Permisos de Inventario por Sucursal

Documentación sobre la configuración de permisos de inventario para encargados de sucursales en Odoo (**base productiva `master_dev`**). Desarrollo: `dev.nakel.net.ar` / `master_test` (`.env`) cuando aplique. La base **master_18** ya no se usa.

## 📋 Descripción General

Este módulo contiene scripts y documentación para configurar permisos de acceso a inventario por sucursal, asegurando que cada encargado solo pueda ver y gestionar información de su propia sucursal.

## 🎯 Objetivo

Restringir el acceso de los encargados de sucursales para que:
- ✅ Vean solo información de inventario de su sucursal
- ✅ No vean información de otras sucursales (Belgrano 2, 3, 4, etc.)
- ✅ No vean información de Nakel Central (CEN)
- ✅ Mantengan acceso a todas las funcionalidades necesarias dentro de su sucursal

## 👥 Encargados de Sucursales

| Sucursal | Encargado | Login | Grupo Odoo |
|----------|-----------|-------|------------|
| Belgrano 1 | Manuel Claudia Isabel | golosinasbelgrano1@nakel.ar | Encargados Belgrano 1 |
| Belgrano 2 | Varas Adrian Marcelo | golosinasbelgrano2@nakel.ar | Encargados Belgrano 2 |
| Belgrano 3 | Robles Angel Jose | golosinasbelgrano3@nakel.ar | Encargados Belgrano 3 |
| Belgrano 4 | Ramos Nancy | golosinasbelgrano4@nakel.ar | Encargados Belgrano 4 |

## 🏢 Ubicaciones y Warehouses

| Sucursal | Warehouse | Ubicación | ID Ubicación | ID Warehouse |
|----------|-----------|-----------|--------------|--------------|
| Belgrano 1 | B1 | B1/Existencias | 109 | 15 |
| Belgrano 2 | B2 | B2/Existencias | 116 | 16 |
| Belgrano 3 | B3 | B3/Existencias | 123 | 17 |
| Belgrano 4 | B4 | B4/Existencias | 130 | 18 |

## 📁 Archivos

### Scripts Principales

1. **`configurar_permisos_inventario_por_sucursal_master18.py`**
   - Script principal para configurar todos los permisos
   - Crea grupos, reglas de registro y asigna usuarios
   - **`--incluir-cen-en-tipos-operacion`:** amplía `stock.picking.type` (sucursal **o** CEN) para ver tipos de Nakel Central en el modal
   - **`--solo-sucursal "Belgrano 1"`:** piloto en una sola sucursal
   - **Uso:** Ver sección "Configuración Inicial" más abajo y `PERMISOS_ENCARGADOS_VENTAS_ALMACEN_PEDIDOS.md`

2. **`diagnosticar_permisos_inventario_por_ubicacion_master18.py`**
   - Diagnóstico completo del sistema de permisos
   - Analiza reglas existentes y acceso actual
   - **Uso:** Para entender el estado actual del sistema

3. **`diagnosticar_permisos_inventario_fabiana_master18.py`**
   - Diagnóstico específico para un usuario
   - Verifica grupos, permisos de acceso y reglas
   - **Uso:** Para diagnosticar problemas de permisos de un usuario específico

4. **`asignar_permisos_ajustes_inventario_fabiana_master18.py`**
   - Script específico para asignar permisos de ajustes de inventario
   - **Uso:** Para casos específicos de permisos de inventario

5. **`diagnosticar_permisos_crear_traslado_master18.py`**
   - Diagnóstico específico para problemas al crear traslados (stock.picking)
   - Verifica permisos de acceso, reglas de registro y grupos
   - **Uso:** Para diagnosticar errores "no tiene acceso crear a Trasladar"

6. **`corregir_permisos_encargado_master18.py`**
   - Corrige permisos de **cualquier** encargado (crear traslados stock.picking)
   - **Uso:** `python3 corregir_permisos_encargado_master18.py 96` o `--login golosinasbelgrano1@nakel.ar`
   - Asigna grupo Encargados [Sucursal], Inventory/User; **no** asigna Product Creation; para logins encargados Belgrano conocidos **retira** Product Creation si aún lo tuvieran (política 2026-04: maestro de productos desde Central)
   - **Fija property_warehouse_id** según sucursal (B1/B2/B3/B4) para que ventas usen el almacén correcto por defecto

7. **`corregir_reglas_encargados_perm_create_master18.py`**
   - Pone perm_create/perm_write (y read/unlink) en True en las reglas de Encargados
   - **Uso:** Si el error aparece al **facturar** (crear stock.picking al descontar stock)

8. **`asignar_menu_reabastecimiento_encargados_master18.py`**
   - Asigna el menú **Inventario → Operaciones → Reabastecimiento** a los grupos Encargados Belgrano 1/2/3/4
   - **Uso:** Si los encargados no ven el menú Reabastecimiento: `python3 asignar_menu_reabastecimiento_encargados_master18.py` (en master_dev: `--master-dev`). Después deben cerrar sesión y volver a entrar.

9. **`habilitar_menu_reportes_inventario_encargados_master_dev.py`**
   - Habilita el menú **Inventario → Reporting (Reportes)** para **Encargados Belgrano 1/2/3/4** sin dar **Inventory / Administrator** a los usuarios.
   - **Uso:** `python3 habilitar_menu_reportes_inventario_encargados_master_dev.py` (dry-run) o `--apply` para aplicar.
   - **Nota:** el submenú **Locations** sigue restringido por grupos técnicos; este script solo habilita el contenedor "Reporting" para poder ver **Stock**, **Moves History**, **Moves Analysis** y **Valuation** si los accesos a modelos lo permiten.

9. **`implied_grupo_solo_barcode_encargados.py`**
   - Tras instalar el módulo Odoo **`nakel_product_encargado_barcode`** (addons: `nakel/nakel_product_encargado_barcode`), enlaza el grupo *Nakel: Producto solo código de barras* como *implied* de Encargados Belgrano 1–4.
   - **Uso:** `python3 implied_grupo_solo_barcode_encargados.py [--master-dev] [--dry-run]`
   - **Nota 2026-04:** si la política es **cero** edición de producto en sucursal (incl. barcode), **no** usar este script; alinear con `corregir_permisos_encargado_master18.py` / quitar implied si ya se aplicó.

10. **`corregir_permisos_varas_belgrano2_master18.py`**
   - Corrige permisos específicos para Varas Adrian Marcelo (Belgrano 2)
   - Asigna grupo "Encargados Belgrano 2" si falta
   - **Uso:** Caso particular Belgrano 2

11. **`asignar_permisos_account_readonly_cajeros_master18.py`**
   - Asigna **Contabilidad / solo lectura** (Accounting / Read-only) a usuarios cajeros (POS)
   - Necesario para que los cajeros puedan **descargar el PDF** de Venta diaria (acceso a `account.payment`)
   - **Uso:** `python3 asignar_permisos_account_readonly_cajeros_master18.py` (dry-run) o `--apply` para aplicar
   - Documentación: [ERROR_CAJEROS_ACCESO_ACCOUNT_PAYMENT.md](ERROR_CAJEROS_ACCESO_ACCOUNT_PAYMENT.md)

12. **`asignar_permisos_account_invoicing_cajeros_master18.py`**
   - Asigna **Contabilidad/Facturación** (Accounting / Invoicing) a usuarios cajeros (POS)
   - Necesario cuando al **retirar dinero de caja** Odoo intenta crear `account.move` (“Asiento contable”) y el cajero no tiene permisos
   - **Uso:** `python3 asignar_permisos_account_invoicing_cajeros_master18.py` (dry-run) o `--apply` para aplicar
   - Documentación: [ERROR_CAJEROS_NO_CREAR_ASIENTO_ACCOUNT_MOVE.md](ERROR_CAJEROS_NO_CREAR_ASIENTO_ACCOUNT_MOVE.md)

## 🚀 Configuración Inicial

### Prerequisitos

- Acceso a Odoo (`master_dev` u otra base acordada) con permisos de administrador
- Python 3 con librería `xmlrpc.client`
- Archivo `config_nakel.py` en `/media/klap/raid5/cursor_files/`

### Pasos de Configuración (base `master_dev` salvo que se indique otro flag)

1. **Ejecutar diagnóstico (opcional pero recomendado):**
   ```bash
   cd /media/klap/raid5/cursor_files/nakel/usuarios/PERMISOS
   python3 diagnosticar_permisos_inventario_por_ubicacion_master18.py
   ```

2. **Ejecutar configuración en modo dry-run:**
   ```bash
   python3 configurar_permisos_inventario_por_sucursal_master18.py --dry-run
   ```

3. **Revisar el output del dry-run** para verificar que todo está correcto

4. **Ejecutar configuración real:**
   ```bash
   python3 configurar_permisos_inventario_por_sucursal_master18.py
   ```

### Aplicar a la base productiva (master_dev)

Si en **master_dev** no ves los grupos "Encargados Belgrano 1/2/3/4" ni las opciones para ajustar encargados de sucursales, hay que **crear la misma plantilla** en esa base:

1. **Configuración inicial en master_dev** (crea grupos y reglas por sucursal):
   ```bash
   cd /media/klap/raid5/cursor_files/nakel/usuarios/PERMISOS
   # Primero en modo dry-run para revisar
   python3 configurar_permisos_inventario_por_sucursal_master18.py --master-dev --dry-run
   # Luego aplicar
   python3 configurar_permisos_inventario_por_sucursal_master18.py --master-dev
   ```
   El script busca warehouses por código (B1, B2, B3, B4) y ubicaciones por ruta (B1/Existencias, etc.), así que **master_dev debe tener los mismos almacenes/ubicaciones** (B1, B2, B3, B4).

2. **Corregir reglas** (perm_create/perm_write) si hace falta:
   ```bash
   python3 corregir_reglas_encargados_perm_create_master18.py --master-dev
   ```

3. **Asignar grupos a un encargado concreto** (por ID o login):
   ```bash
   python3 corregir_permisos_encargado_master18.py 96 --master-dev
   # o por login:
   python3 corregir_permisos_encargado_master18.py --login golosinasbelgrano1@nakel.ar --master-dev
   ```

4. **Si los encargados no ven Inventario → Operaciones → Reabastecimiento**, ejecutar:
   ```bash
   python3 asignar_menu_reabastecimiento_encargados_master18.py --master-dev
   ```
   Luego los encargados deben cerrar sesión y volver a entrar.

### Verificación Post-Configuración

Después de ejecutar la configuración, los usuarios deben:
1. Cerrar sesión en Odoo
2. Volver a iniciar sesión para que los cambios surtan efecto
3. Verificar que solo ven información de su sucursal

## 📊 Reglas de Registro Creadas

El script crea **16 reglas de registro** (4 por sucursal) para los siguientes modelos:

### 1. stock.picking (Transferencias)
**Dominio:** `['|', ('location_id', 'child_of', <location_id>), ('location_dest_id', 'child_of', <location_id>)]`

**Efecto:** Los usuarios solo ven transferencias que involucren su sucursal (origen o destino)

### 2. stock.move (Movimientos)
**Dominio:** `['|', ('location_id', 'child_of', <location_id>), ('location_dest_id', 'child_of', <location_id>)]`

**Efecto:** Los usuarios solo ven movimientos de inventario de su sucursal

### 3. stock.quant (Stock/Cantidades)
**Dominio:** `[('location_id', 'child_of', <location_id>)]`

**Efecto:** Los usuarios solo ven stock ubicado en su sucursal

### 4. stock.picking.type (Tipos de Operación)
**Dominio:** `[('warehouse_id', '=', <warehouse_id>)]`

**Efecto:** Los usuarios solo ven tipos de operación de su warehouse

## 🔍 Grupos de Usuarios

El script crea/utiliza los siguientes grupos (categoría: Inventory):

- **Encargados Belgrano 1** (ID: 97)
- **Encargados Belgrano 2** (ID: 98)
- **Encargados Belgrano 3** (ID: 99)
- **Encargados Belgrano 4** (ID: 100)

Cada grupo tiene reglas de registro asociadas que restringen el acceso por ubicación.

## 📝 Historial de Cambios

### 2025-01-XX - Configuración Inicial
- Creados grupos de usuarios por sucursal
- Creadas 16 reglas de registro (4 por sucursal)
- Asignados usuarios a sus grupos correspondientes
- Documentación completa creada

**Reglas creadas:**
- Belgrano 1: IDs 377-380
- Belgrano 2: IDs 381-384
- Belgrano 3: IDs 385-388
- Belgrano 4: IDs 389-392

## ⚠️ Notas Importantes

1. **Los cambios requieren reinicio de sesión:** Los usuarios deben cerrar sesión y volver a iniciar para que los nuevos permisos surtan efecto.

2. **Administradores no afectados:** Los usuarios con permisos de administrador no están afectados por estas reglas.

3. **Reglas aplicadas a grupos específicos:** Las reglas solo aplican a los grupos "Encargados [Sucursal]", otros usuarios no se ven afectados.

4. **Reglas activas:** Todas las reglas creadas están activas por defecto. Para desactivarlas, hacerlo manualmente desde Odoo (Configuración > Técnico > Seguridad > Reglas de Registro).

## 🛠️ Mantenimiento

### Agregar un nuevo encargado

1. Editar `configurar_permisos_inventario_por_sucursal_master18.py`
2. Agregar el nuevo usuario en `SUCURSALES_CONFIG`
3. Ejecutar el script (el grupo ya existirá, solo se asignará el usuario)

### Modificar reglas existentes

Las reglas pueden modificarse desde Odoo:
- Ir a: Configuración > Técnico > Seguridad > Reglas de Registro
- Buscar las reglas "Encargados [Sucursal]"
- Modificar el dominio según sea necesario

### Eliminar permisos

Para eliminar las restricciones:
1. Desactivar las reglas desde Odoo (marcar como "Inactivo")
2. O eliminar el grupo del usuario desde Odoo

## 🐛 Solución de Problemas

### Error: "no tiene acceso crear a Trasladar (stock.picking)" (al facturar o pedir mercadería)

Si un encargado reporta este error (sobre todo **al facturar** una venta):

1. **Corregir reglas** (perm_create/perm_write en reglas de Encargados):
   ```bash
   python3 corregir_reglas_encargados_perm_create_master18.py
   # En master_dev: añadir --master-dev
   ```

2. **Verificar grupos del usuario** (Encargados [Sucursal], Inventory/User):
   ```bash
   python3 corregir_permisos_encargado_master18.py 96
   # En master_dev: python3 corregir_permisos_encargado_master18.py 96 --master-dev
   ```
   (Reemplazar 96 por el ID del usuario.)

3. **Diagnóstico detallado:**
   ```bash
   python3 diagnosticar_permisos_crear_traslado_master18.py
   ```

4. **Solución más común:** El usuario debe **cerrar sesión completamente** y volver a iniciar.

- Flujo venta → factura → stock: [ANALISIS_ERROR_FACTURAR_ENCARGADOS.md](ANALISIS_ERROR_FACTURAR_ENCARGADOS.md)
- Detalle del error: [SOLUCION_ERROR_CREAR_TRASLADO.md](SOLUCION_ERROR_CREAR_TRASLADO.md)

### Error: "No puede acceder a los registros 'Pagos' (account.payment)" (cajeros, descargar PDF)

Si un **cajero** no puede descargar el PDF de Venta diaria / cierre de caja:

1. **Asignar Contabilidad / solo lectura** a los cajeros (recomendado por script):
   ```bash
   python3 asignar_permisos_account_readonly_cajeros_master18.py --apply
   ```
2. O manualmente en **Configuración → Usuarios**: marcar para cada cajero **Contabilidad → Mostrar funciones de contabilidad: solo lectura**.
3. El cajero debe **cerrar sesión y volver a iniciar**.

- Documentación completa: [ERROR_CAJEROS_ACCESO_ACCOUNT_PAYMENT.md](ERROR_CAJEROS_ACCESO_ACCOUNT_PAYMENT.md)

### Error: "No puede crear registros 'Asiento contable' (account.move)" (cajeros, retirar dinero)

Si un **cajero** no puede **retirar dinero de caja** y el error menciona que no puede crear `Asiento contable` (`account.move`):

1. Ejecutar el script recomendado:
   ```bash
   python3 asignar_permisos_account_invoicing_cajeros_master18.py --apply
   ```
2. Alternativa manual en Odoo: asignar al usuario el grupo **Contabilidad/Facturación** (**Accounting / Invoicing**).
3. El cajero debe **cerrar sesión y volver a iniciar**.

- Documentación completa: [ERROR_CAJEROS_NO_CREAR_ASIENTO_ACCOUNT_MOVE.md](ERROR_CAJEROS_NO_CREAR_ASIENTO_ACCOUNT_MOVE.md)

## 📚 Referencias

- [Error Cajeros account.payment (descargar PDF)](ERROR_CAJEROS_ACCESO_ACCOUNT_PAYMENT.md) - Cajeros no pueden descargar PDF por falta de acceso a Pagos
- [Solución Error Crear Traslado](SOLUCION_ERROR_CREAR_TRASLADO.md) - Documentación detallada del error reportado
- [Documentación de Encargados de Sucursales](../documentacion/ENCARGADOS_SUCURSALES.md)
- [README Principal de Usuarios](../README.md)
- [Índice de Usuarios](../INDICE.md)

## 👤 Autor

Corolla - Asistente Técnico FWCORP

## 📅 Última Actualización

2025-01-XX
