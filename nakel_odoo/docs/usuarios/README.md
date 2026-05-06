# 👥 Gestión de Usuarios y Permisos - NAKEL Odoo

Este directorio contiene toda la documentación, scripts y reportes relacionados con la gestión de usuarios y permisos en Odoo para NAKEL.

**Credenciales e IDs (sanitizado para repo):** ver [documentacion/CREDENCIALES_Y_IDS_POR_BASE.PUBLIC.md](documentacion/CREDENCIALES_Y_IDS_POR_BASE.PUBLIC.md).  
La versión interna con detalles sensibles **no se versiona** (`documentacion/CREDENCIALES_Y_IDS_POR_BASE.md`).

## 📁 Estructura del Directorio

```
nakel/usuarios/
├── README.md                          # Este archivo (índice principal)
├── scripts/                           # Scripts de gestión de usuarios y permisos
│   ├── asignar_permisos_modificar_productos_encargados.py
│   ├── listar_todos_usuarios_master_dev.py
│   ├── analizador_modificador_permisos_contactos.py
│   ├── analizador_permisos_vendedores.py
│   └── buscador_usuarios_contactos.py
├── PERMISOS/                          # Scripts y documentación de permisos de inventario
│   ├── README.md                      # Documentación principal de permisos
│   ├── RESUMEN_EJECUTIVO.md          # Resumen ejecutivo
│   ├── CONFIGURACION_PERMISOS_INVENTARIO.md  # Configuración técnica detallada
│   ├── configurar_permisos_inventario_por_sucursal_master18.py  # Script principal
│   ├── diagnosticar_permisos_inventario_por_ubicacion_master18.py
│   ├── diagnosticar_permisos_inventario_fabiana_master18.py
│   └── asignar_permisos_ajustes_inventario_fabiana_master18.py
├── reportes/                          # Reportes de usuarios y permisos
│   ├── informe_detallado_permisos_*.txt
│   ├── comparacion_usuarios_*.json
│   ├── listado_completo_usuarios_*.json
│   └── ...
└── documentacion/                     # Documentación adicional
```

---

## 🚀 Scripts Disponibles

### 1. Alinear permisos de producto (Encargados Belgrano 1–4, master_dev)

**Archivo:** `scripts/asignar_permisos_modificar_productos_encargados.py`

**Propósito:** Política 2026-04: **retira** el grupo "Product Creation" y **asegura** "Inventory / User" en **todos los usuarios activos** miembros de **Encargados Belgrano 1 … 4** (encargados `@nakel.ar`, cajeros `@gmail.com`, etc., según estén dados de alta en esos grupos).

**Exclusión:** `supervision@nakel.ar` (no se modifican sus grupos desde este script).

**Uso:**

```bash
cd /media/klap/raid5/cursor_files/nakel/usuarios/scripts

# Solo verificar
python3 asignar_permisos_modificar_productos_encargados.py --verificar-solo

# Modo dry-run
python3 asignar_permisos_modificar_productos_encargados.py --dry-run

# Aplicar alineación
python3 asignar_permisos_modificar_productos_encargados.py
```

**Efecto:** sin Product Creation en usuarios sujetos a la política; inventario operativo con Inventory / User. Los IDs de grupo se resuelven por nombre en la base.

**Referencia original:** `nakel/ventas/Listas de precios/scripts/asignar_permisos_modificar_productos_encargados.py` (histórico; el script del vault cambió de propósito en 2026-04).

---

### 2. Listar Todos los Usuarios de master_dev

**Archivo:** `scripts/listar_todos_usuarios_master_dev.py`

**Propósito:** Lista todos los usuarios del sistema master_dev con información detallada de grupos y permisos.

**Uso:**

```bash
cd /media/klap/raid5/cursor_files/nakel/usuarios/scripts
python3 listar_todos_usuarios_master_dev.py
```

**Referencia original:** `modulos/ventas/scripts/listar_todos_usuarios_master_dev.py`

---

### 3. Analizador y Modificador de Permisos de Contactos

**Archivo:** `scripts/analizador_modificador_permisos_contactos.py`

**Propósito:** Analiza y permite modificar permisos de acceso a contactos para vendedores y usuarios específicos.

**Funcionalidades:**

- Analiza reglas de acceso actuales
- Analiza grupos de usuarios
- Propone soluciones para acceso a contactos
- Puede crear grupos con permisos amplios
- Asigna grupos a usuarios

**Uso:**

```bash
cd /media/klap/raid5/cursor_files/nakel/usuarios/scripts
python3 analizador_modificador_permisos_contactos.py
```

**Referencia original:** `modulos/contactos/scripts/analizador_modificador_permisos_contactos.py`

---

### 4. Analizador de Permisos de Vendedores

**Archivo:** `scripts/analizador_permisos_vendedores.py`

**Propósito:** Analiza permisos específicos de vendedores en el sistema.

**Referencia original:** `modulos/contactos/scripts/analizador_permisos_vendedores.py`

---

### 5. Buscador de Usuarios y Contactos

**Archivo:** `scripts/buscador_usuarios_contactos.py`

**Propósito:** Busca usuarios y contactos en el sistema con criterios específicos.

**Referencia original:** `modulos/contactos/scripts/buscador_usuarios_contactos.py`

---

## 🔐 Permisos de Inventario por Sucursal

**Ubicación:** `PERMISOS/`

Esta carpeta contiene scripts y documentación completa para configurar permisos de inventario por sucursal, asegurando que cada encargado solo vea información de su propia sucursal.

### Script Principal

**Archivo:** `PERMISOS/configurar_permisos_inventario_por_sucursal_master18.py`

**Propósito:** Configura permisos de inventario por sucursal creando grupos, reglas de registro y asignando usuarios.

**Usuarios objetivo:**

- Manuel Claudia Isabel - Belgrano 1
- Varas Adrian Marcelo - Belgrano 2
- Robles Angel Jose - Belgrano 3
- Ramos Nancy - Belgrano 4

**Uso:**

```bash
cd /media/klap/raid5/cursor_files/nakel/usuarios/PERMISOS

# Modo dry-run (recomendado primero)
python3 configurar_permisos_inventario_por_sucursal_master18.py --dry-run

# Aplicar configuración
python3 configurar_permisos_inventario_por_sucursal_master18.py
```

**Documentación completa:**

- **[PERMISOS/README.md](PERMISOS/README.md)** - Documentación completa
- **[PERMISOS/RESUMEN_EJECUTIVO.md](PERMISOS/RESUMEN_EJECUTIVO.md)** - Resumen ejecutivo
- **[PERMISOS/CONFIGURACION_PERMISOS_INVENTARIO.md](PERMISOS/CONFIGURACION_PERMISOS_INVENTARIO.md)** - Detalles técnicos

**Estado:** ✅ Configurado y activo en `master_dev` (referencia operativa)

---

## 📊 Reportes

### Informes de Permisos

Los reportes se generan automáticamente con timestamps y contienen:

- Comparaciones de permisos entre ambientes
- Grupos faltantes por usuario
- Análisis detallado de permisos
- Listados completos de usuarios

**Ubicación:** `reportes/`

**Ejemplos:**

- `informe_detallado_permisos_20251222_232144.txt` - Informe detallado de permisos
- `comparacion_usuarios_*.json` - Comparaciones entre usuarios
- `listado_completo_usuarios_*.json` - Listados de usuarios

---

## 🔐 Conceptos Clave

### Grupos de Usuarios en Odoo

Los grupos en Odoo controlan los permisos de acceso. Principales categorías:

1. **Extra Rights**
  - Product Creation (crear/editar maestro de productos; **no** asignado a encargados Belgrano desde 2026-04)
  - Contact Creation
  - Multi Companies
2. **Technical**
  - Manage Product Packaging
  - Manage Product Variants
  - Manage Lots / Serial Numbers
3. **Sales**
  - User: All Documents
  - User: Own Documents Only
  - Administrator
4. **Inventory**
  - User
  - Manager
5. **Point of Sale**
  - User
  - Administrator

### Permisos de Acceso (ir.model.access)

Los permisos se definen por modelo (`ir.model.access`) y pueden ser:

- **Read (perm_read)**: Leer registros
- **Write (perm_write)**: Modificar registros
- **Create (perm_create)**: Crear nuevos registros
- **Unlink (perm_unlink)**: Eliminar registros

### Reglas de Registro (ir.rule)

Las reglas de registro filtran qué registros puede ver un usuario, incluso si tiene permisos de lectura.

---

## 📋 Casos de Uso Comunes

### Caso 1: Encargados Belgrano sin tocar el maestro de productos

**Problema:** Política Nakel: barcodes y datos de producto solo desde Central; sucursal no debe tener Product Creation.

**Solución:**

1. Ejecutar `asignar_permisos_modificar_productos_encargados.py` (master_dev) o `corregir_permisos_encargado_master18.py --login … [--master-dev]` por encargado.
2. El script **retira** Product Creation y mantiene Inventory / User donde aplica.

**Script:** `scripts/asignar_permisos_modificar_productos_encargados.py`, `PERMISOS/corregir_permisos_encargado_master18.py`

---

### Caso 2: Analizar Permisos de un Usuario

**Problema:** Un usuario reporta que no puede acceder a ciertos módulos.

**Solución:**

1. Ejecutar `listar_todos_usuarios_master_dev.py` para ver todos los usuarios
2. Buscar el usuario específico
3. Revisar grupos asignados
4. Comparar con reportes de permisos si es necesario

**Script:** `scripts/listar_todos_usuarios_master_dev.py`

---

### Caso 3: Permitir Acceso Completo a Contactos

**Problema:** Vendedores necesitan acceso completo a contactos sin restricciones.

**Solución:**

1. Ejecutar `analizador_modificador_permisos_contactos.py`
2. Analizar reglas de acceso actuales
3. Seguir las opciones propuestas por el script

**Script:** `scripts/analizador_modificador_permisos_contactos.py`

---

## 🔗 Referencias Externas

### Archivos Originales (No Modificar)

Los siguientes archivos son referencias originales. Se mantienen en sus ubicaciones originales pero se copian aquí para fácil acceso:

- `modulos/ventas/scripts/listar_todos_usuarios_master_dev.py`
- `modulos/contactos/scripts/analizador_modificador_permisos_contactos.py`
- `modulos/contactos/scripts/analizador_permisos_vendedores.py`
- `modulos/contactos/scripts/buscador_usuarios_contactos.py`
- `nakel/ventas/Listas de precios/scripts/asignar_permisos_modificar_productos_encargados.py`

### Documentación Relacionada

- **Permisos de Filestore:** `documentacion/README_SOLUCION_PERMISOS_FILESTORE.md` (copiado desde `nakel/db/`)
- **Scripts de Listas de Precios:** `../ventas/Listas de precios/scripts/README.md`

---

## 📝 Notas Importantes

1. **Siempre usar dry-run primero:** Antes de asignar permisos, ejecutar en modo dry-run para verificar cambios.
2. **Backup antes de cambios:** Aunque los cambios de permisos son reversibles, es recomendable hacer backup de la base de datos antes de cambios masivos.
3. **Verificar impactos:** Al asignar grupos, verificar que no se otorguen permisos excesivos.
4. **Documentar cambios:** Cuando se asignen permisos manualmente o mediante scripts, documentar el motivo y la fecha.
5. **Pruebas después de cambios:** Verificar que los usuarios pueden realizar las acciones deseadas después de asignar permisos.

---

## 🛠️ Mantenimiento

### Agregar Nuevos Scripts

Cuando se creen nuevos scripts relacionados con usuarios y permisos:

1. Copiar el script a `scripts/`
2. Actualizar este README con la descripción del script
3. Agregar referencia al archivo original si corresponde

### Generar Reportes

Los reportes se generan automáticamente por los scripts, pero se pueden crear manualmente ejecutando los scripts de análisis correspondientes.

---

## 📞 Soporte

Para problemas o preguntas sobre usuarios y permisos:

- Revisar los reportes en `reportes/`
- Ejecutar scripts en modo dry-run para diagnóstico
- Consultar la documentación de Odoo sobre grupos y permisos
- Revisar logs de ejecución de scripts

---

---

**Última actualización:** 2026-04-18  
**Odoo Version:** 18.0 Enterprise  
**Ambientes:** `master_dev` (productivo scripts); `dev.nakel.net.ar` / `master_test` vía `.env` para desarrollo (sin scripts obligatorios aquí). **master_18** deprecado.