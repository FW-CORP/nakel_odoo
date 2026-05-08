# 📚 Índice de Documentación - Usuarios y Permisos

Este archivo sirve como índice rápido de toda la documentación disponible.

## 📖 Documentación Principal

- **[README.md](README.md)** - Índice principal con descripción completa de scripts y herramientas
- **[CREDENCIALES_Y_IDS_POR_BASE.PUBLIC.md](documentacion/CREDENCIALES_Y_IDS_POR_BASE.PUBLIC.md)** - Credenciales/entornos e IDs por base (versión sanitizada para repo)

## 👥 Documentación Específica

- **[ENCARGADOS_SUCURSALES.md](documentacion/ENCARGADOS_SUCURSALES.md)** - Documentación sobre encargados de sucursales y sus permisos

## 🔐 Permisos de Inventario

- **[PERMISOS/README.md](PERMISOS/README.md)** - Documentación completa sobre permisos de inventario por sucursal
- **[PERMISOS/CONFIGURACION_PERMISOS_INVENTARIO.md](PERMISOS/CONFIGURACION_PERMISOS_INVENTARIO.md)** - Configuración técnica detallada
- **[PERMISOS/ERROR_CAJEROS_ACCESO_ACCOUNT_PAYMENT.md](PERMISOS/ERROR_CAJEROS_ACCESO_ACCOUNT_PAYMENT.md)** - Error cajeros: no pueden descargar PDF (account.payment), solución con Contabilidad/solo lectura
- **[PERMISOS/PERMISOS_PREVENTISTAS_INFORMES_CC_MASTER_DEV.md](PERMISOS/PERMISOS_PREVENTISTAS_INFORMES_CC_MASTER_DEV.md)** - Preventistas: `account.report`, grupo `account.group_account_readonly`, menús y XML IDs (`master_dev`, 2026-04-11)
- `PERMISOS/crear_grupo_vendedores_preventistas.py` - Crear/actualizar grupo **Vendedores - Preventistas** (implied solo lectura contable); `--dry-run` implícito, `--apply` para escribir
- `PERMISOS/crear_ir_rule_partner_preventistas.py` - **`ir.rule`** `res.partner` solo para ese grupo (contactos del vendedor asignado); dry-run implícito, `--apply` para escribir
- `PERMISOS/auditar_vista_boton_facturado_partner.py` - Solo lectura: listar vistas XML que definen el smart button **Facturado** (`action_view_partner_invoices`) y el atributo `groups`
- **[PERMISOS/ERROR_CAJEROS_NO_CREAR_ASIENTO_ACCOUNT_MOVE.md](PERMISOS/ERROR_CAJEROS_NO_CREAR_ASIENTO_ACCOUNT_MOVE.md)** - Error cajeros: no pueden crear “Asiento contable” (account.move) al retirar dinero

## 🔧 Scripts Disponibles

### Gestión de Permisos
- `scripts/asignar_permisos_modificar_productos_encargados.py` - Miembros de Encargados Belgrano 1–4 en `master_dev` (menos `supervision@nakel.ar`): quita Product Creation, asegura Inventory / User
- `scripts/analizador_modificador_permisos_contactos.py` - Analizar y modificar permisos de contactos
- `scripts/analizador_permisos_vendedores.py` - Analizar permisos de vendedores

### Permisos de Inventario (Ver PERMISOS/)
- `PERMISOS/configurar_permisos_inventario_por_sucursal_master18.py` - **Configurar permisos por sucursal (Principal)**
- `PERMISOS/diagnosticar_permisos_inventario_por_ubicacion_master18.py` - Diagnosticar permisos por ubicación
- `PERMISOS/diagnosticar_permisos_inventario_fabiana_master18.py` - Diagnosticar permisos de un usuario específico
- `PERMISOS/asignar_permisos_ajustes_inventario_fabiana_master18.py` - Asignar permisos de ajustes de inventario
- `PERMISOS/asignar_permisos_account_readonly_cajeros_master18.py` - Asignar Contabilidad/solo lectura a cajeros (descargar PDF account.payment)
- `PERMISOS/asignar_permisos_account_invoicing_cajeros_master18.py` - Asignar Contabilidad/Facturación a cajeros (crear account.move al retirar dinero)

### Listado y Búsqueda
- `scripts/listar_todos_usuarios_master_dev.py` - Listar todos los usuarios
- `scripts/buscador_usuarios_contactos.py` - Buscar usuarios y contactos

## 📊 Reportes (no versionados)

Los reportes se generan automáticamente con timestamps y **pueden contener información sensible** (usuarios/emails/datos operativos), por lo que el directorio `reportes/` queda **excluido** del repositorio vía `.gitignore`.

## 🔗 Referencias Externas

### Archivos Originales
- `modulos/ventas/scripts/listar_todos_usuarios_master_dev.py`
- `modulos/contactos/scripts/analizador_modificador_permisos_contactos.py`
- `modulos/contactos/scripts/analizador_permisos_vendedores.py`
- `modulos/contactos/scripts/buscador_usuarios_contactos.py`
- `nakel/ventas/Listas de precios/scripts/asignar_permisos_modificar_productos_encargados.py`

### Documentación Relacionada
- `nakel/db/README_SOLUCION_PERMISOS_FILESTORE.md` - Permisos de filestore
- `nakel/ventas/Listas de precios/scripts/README.md` - Scripts de listas de precios

---

**Última actualización:** 2026-04-12

