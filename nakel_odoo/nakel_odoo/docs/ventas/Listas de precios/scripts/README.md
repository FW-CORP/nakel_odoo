# Scripts de Migración de Listas de Precios desde Excel

## Modelo de datos en `master_dev` (Lista 1 / Lista 2)

Para ver **cómo encadenan** la **Lista 1 CR Distribución**, las **Lista 2** (comercio / particulares), las listas **- FIX** y el **costo** (`standard_price`), sin ejecutar scripts:

→ **`../ESTRUCTURA_COSTOS_Y_LISTAS_1_2_MASTER_DEV.md`** (lectura API **2026-04-07**).

---

Este directorio contiene scripts para migrar listas de precios desde archivos Excel (.xls/.xlsx) a Odoo master_18.

## 📁 Archivos Disponibles

### Scripts Principales

#### Migración de Listas de Precios
1. **`migrar_lista1_desde_excel.py`** - Script principal para migrar precios desde Excel a una lista de Odoo
2. **`crear_productos_faltantes_desde_excel.py`** - Crea productos que no existen en Odoo desde el Excel (con categorías y unidades de compra)
3. **`actualizar_unidades_compra_productos_existentes.py`** - Actualiza unidades de compra en productos ya creados basándose en CxB del Excel
4. **`analizar_productos_no_mapeados.py`** - Analiza productos que no se pudieron mapear
5. **`leer_lista_precios_excel.py`** - Utilidad para leer y analizar archivos Excel
6. **`analizar_lista1_excel.py`** - Analiza la estructura de archivos Excel

#### Sincronización con MSSQL
7. **`sincronizar_embalajes_desde_mssql_master_dev.py`** - Sincroniza embalajes desde MSSQL GESTION a Odoo usando código interno normalizado
8. **`actualizar_barcodes_desde_mssql_master_dev.py`** - Actualiza códigos de barras faltantes o erróneos desde MSSQL
9. **`configurar_productos_completo_master_dev.py`** - Configura flags (ventas, compras, POS) y rutas de inventario para todos los productos

#### Verificación y Corrección de Embalajes
10. **`verificar_embalaje_producto_odoo_vs_mssql.py`** - Verifica y compara embalaje de un producto específico entre Odoo y MSSQL
11. **`revisar_embalajes_todos_productos_vs_mssql.py`** - Revisa y compara embalajes de TODOS los productos entre Odoo y MSSQL, genera reporte detallado
12. **`corregir_discrepancias_cantidad_embalajes_desde_mssql.py`** - Corrige discrepancias de cantidad de embalajes usando UNID_BULTO de MSSQL GESTION

#### Gestión de Permisos
13. **`asignar_permisos_modificar_productos_encargados.py`** - Asigna permisos de modificación de productos a encargados de sucursales

## 🚀 Proceso Completo de Migración

### Paso 1: Preparar Archivo Excel

1. Exportar lista de precios desde el sistema de origen
2. Guardar en formato `.xls` o `.xlsx`
3. Colocar en: `/media/klap/raid5/cursor_files/nakel/ventas/Listas de precios/`
4. El archivo debe contener las siguientes columnas:
   - **Codigo**: Código de referencia interna del producto
   - **Descripcion**: Nombre/descripción del producto
   - **Precio C/IVA**: Precio de venta con IVA (formato argentino: comas como decimales)
   - **Nombre Rubro**: Categoría del producto
   - **CxB**: Cantidad por bulto (opcional)
   - **Stock**: Stock disponible (opcional)

### Paso 2: Analizar Productos No Mapeados (Opcional)

Antes de crear productos, puedes analizar cuáles no existen en Odoo:

```bash
cd "/media/klap/raid5/cursor_files/nakel/ventas/Listas de precios/scripts"
python3 analizar_productos_no_mapeados.py --lista Lista1.xls
```

Esto generará un reporte detallado en: `../reporte_no_mapeados_YYYYMMDD_HHMMSS.txt`

### Paso 3: Crear Productos Faltantes

**IMPORTANTE**: Este paso debe ejecutarse ANTES de la migración de precios para productos que no existen en Odoo.

```bash
# Modo dry-run (prueba sin cambios)
python3 crear_productos_faltantes_desde_excel.py --dry-run

# Ejecución real
python3 crear_productos_faltantes_desde_excel.py
```

**Parámetros:**
- `--lista`: Nombre del archivo Excel (default: `Lista1.xls`)
- `--nombre-lista-odoo`: Nombre de la lista en Odoo (default: `Lista 1`)
- `--dry-run`: Modo de prueba (no realiza cambios)

**Qué hace este script:**
1. Identifica productos del Excel que no existen en Odoo (por código o nombre)
2. Crea categorías basadas en "Nombre Rubro" (si no existen)
3. Obtiene/crea unidades de compra basadas en CxB (Cantidad por Bulto)
4. Crea productos con:
   - Nombre (Descripcion del Excel)
   - Código de referencia interna (Codigo del Excel)
   - Categoría (basada en Nombre Rubro)
   - **Unidad de compra** (basada en CxB del Excel, ej: "Bulto x12", "Bulto x6")
   - Precio de venta (Precio C/IVA)
   - Activados para Ventas (`sale_ok = True`)
   - Activados para Compras (`purchase_ok = True`)
   - Activados para Puntos de Venta (`available_in_pos = True`)
   - Tipo: Consumible (`type = 'consu'`)
5. Agrega los precios a la lista de precios especificada

### Paso 3.5: Actualizar Unidades de Compra en Productos Existentes (Opcional)

Si productos ya fueron creados sin unidad de compra, puedes actualizarlos:

```bash
# Modo dry-run (prueba sin cambios)
python3 actualizar_unidades_compra_productos_existentes.py --dry-run

# Ejecución real
python3 actualizar_unidades_compra_productos_existentes.py
```

**Parámetros:**
- `--lista`: Nombre del archivo Excel (default: `Lista1.xls`)
- `--dry-run`: Modo de prueba (no realiza cambios)

**Qué hace este script:**
1. Lee productos del Excel
2. Identifica productos en Odoo que tienen código pero no tienen la unidad de compra correcta
3. Actualiza la unidad de compra (`uom_po_id`) basándose en el valor CxB del Excel
4. Busca unidades existentes en Odoo (ej: "Bulto x12", "Bulto x6")

### Paso 4: Migrar Precios

Una vez creados los productos faltantes, migra todos los precios de la lista:

```bash
# Modo dry-run (prueba sin cambios)
python3 migrar_lista1_desde_excel.py --dry-run

# Ejecución real
python3 migrar_lista1_desde_excel.py
```

**Parámetros:**
- `--lista`: Nombre del archivo Excel (default: `Lista1.xls`)
- `--nombre-lista-odoo`: Nombre de la lista en Odoo (default: `Lista 1`)
- `--dry-run`: Modo de prueba (no realiza cambios)

**Qué hace este script:**
1. Lee productos del Excel
2. Crea mapeo de productos usando múltiples estrategias:
   - Por código interno (Codigo ↔ default_code)
   - Por nombre exacto
   - Por nombre normalizado
3. Compara con la lista existente en Odoo
4. Actualiza precios existentes y agrega precios nuevos

## 📋 Requisitos Previos

### Dependencias del Sistema

1. **LibreOffice**: Requerido para convertir archivos Excel a CSV
   ```bash
   # Verificar instalación
   which libreoffice
   
   # Instalar si es necesario (Ubuntu/Debian)
   sudo apt install libreoffice
   ```

2. **Python 3**: Versión 3.8 o superior
   ```bash
   python3 --version
   ```

3. **Configuración Odoo**: El archivo `config_nakel.py` debe estar disponible y contener:
   - `ODOO_CONFIG_MASTER18`: Configuración de conexión a Odoo master_18

### Estructura de Directorios

```
/media/klap/raid5/cursor_files/
├── config_nakel.py                          # Configuración de conexiones
└── nakel/ventas/Listas de precios/
    ├── Lista1.xls                          # Archivo Excel de origen
    ├── Lista2.xls
    └── scripts/                            # Scripts de migración
        ├── README.md                       # Esta documentación
        ├── migrar_lista1_desde_excel.py
        ├── crear_productos_faltantes_desde_excel.py
        └── ...
```

## 🔍 Estrategias de Mapeo de Productos

El script de migración usa múltiples estrategias para mapear productos entre Excel y Odoo:

1. **Por Código Interno** (más confiable)
   - Busca coincidencia exacta: `Codigo` (Excel) = `default_code` (Odoo)

2. **Por Nombre Exacto**
   - Busca coincidencia exacta: `Descripcion` (Excel) = `name` (Odoo)

3. **Por Nombre Normalizado**
   - Normaliza nombres (remueve prefijos, espacios extra, sufijos)
   - Busca coincidencia después de normalización

## ⚙️ Configuración de Productos Creados

Los productos creados tienen la siguiente configuración por defecto:

- **Tipo**: `consu` (Consumible - no almacenable)
- **Ventas**: ✅ Habilitado (`sale_ok = True`)
- **Compras**: ✅ Habilitado (`purchase_ok = True`)
- **Puntos de Venta**: ✅ Habilitado (`available_in_pos = True`)
- **Categoría**: Basada en "Nombre Rubro" del Excel (se crea si no existe)
- **Precio de Venta**: Precio C/IVA del Excel
- **Código Interno**: Codigo del Excel

## 📊 Ejemplo de Uso Completo

```bash
# 1. Ir al directorio de scripts
cd "/media/klap/raid5/cursor_files/nakel/ventas/Listas de precios/scripts"

# 2. Analizar productos no mapeados (opcional)
python3 analizar_productos_no_mapeados.py --lista Lista1.xls

# 3. Crear productos faltantes (dry-run primero)
python3 crear_productos_faltantes_desde_excel.py --lista Lista1.xls --dry-run

# 4. Crear productos faltantes (ejecución real)
python3 crear_productos_faltantes_desde_excel.py --lista Lista1.xls

# 5. Migrar precios (dry-run primero)
python3 migrar_lista1_desde_excel.py --lista Lista1.xls --nombre-lista-odoo "Lista 1" --dry-run

# 6. Migrar precios (ejecución real)
python3 migrar_lista1_desde_excel.py --lista Lista1.xls --nombre-lista-odoo "Lista 1"
```

## ⚠️ Consideraciones Importantes

### Para Base Productiva (master_18)

1. **Siempre ejecutar en dry-run primero**: Verifica qué cambios se realizarán
2. **Respaldo de base de datos**: Hacer backup antes de ejecutar en producción
3. **Horarios de baja carga**: Ejecutar en horarios de menor uso del sistema
4. **Validar resultados**: Verificar algunos productos manualmente después de la migración
5. **Lista predeterminada**: El script protege automáticamente la lista predeterminada de Odoo

### Manejo de Errores

- Si un producto falla al crearse, el script continúa con los siguientes
- Los errores se muestran en la consola pero no detienen el proceso
- Revisar el resumen final para ver cantidad de errores

### Formato de Precios

- Los precios en el Excel deben estar en formato argentino (comas como decimales)
- Ejemplo: `11414,82` se convierte a `11414.82`
- El script maneja automáticamente la conversión

## 📝 Logs y Reportes

Los scripts generan:
- **Salida en consola**: Progreso en tiempo real
- **Reportes de análisis**: `reporte_no_mapeados_*.txt` (si se ejecuta el analizador)

## 🔄 Flujo Recomendado para Nueva Migración

```
1. Preparar archivo Excel → Colocar en directorio
2. Analizar productos no mapeados (opcional)
3. Crear productos faltantes (dry-run → real)
4. Migrar precios (dry-run → real)
5. Validar resultados en Odoo
```

## 🔧 Scripts de Sincronización con MSSQL

### Sincronizar Embalajes desde MSSQL

Sincroniza embalajes (packaging) desde MSSQL GESTION a Odoo master_dev usando código interno normalizado:

```bash
# Modo dry-run (ver qué se actualizaría)
python3 sincronizar_embalajes_desde_mssql_master_dev.py --dry-run

# Solo crear embalajes faltantes (no actualizar existentes)
python3 sincronizar_embalajes_desde_mssql_master_dev.py --solo-faltantes

# Crear y actualizar todo
python3 sincronizar_embalajes_desde_mssql_master_dev.py
```

**Qué hace:**
- Obtiene `UNID_BULTO` (unidades por bulto) desde MSSQL
- Usa código interno normalizado (coma → punto) para matching mejorado
- Crea embalajes faltantes en Odoo
- Actualiza cantidades de embalajes existentes si difieren

### Actualizar Códigos de Barras desde MSSQL

Actualiza códigos de barras faltantes o erróneos desde MSSQL:

```bash
# Modo dry-run
python3 actualizar_barcodes_desde_mssql_master_dev.py --dry-run

# Solo agregar códigos faltantes (no corregir diferentes)
python3 actualizar_barcodes_desde_mssql_master_dev.py --solo-faltantes

# Agregar faltantes y corregir diferentes
python3 actualizar_barcodes_desde_mssql_master_dev.py
```

**Qué hace:**
- Obtiene códigos de barras (PLU) desde MSSQL por `COD_ARTICULO`
- Normaliza códigos internos (coma → punto) para matching
- Agrega códigos de barras a productos que no los tienen
- Corrige códigos de barras que difieren entre MSSQL y Odoo

### Configurar Productos Completos

Configura flags y rutas de inventario para todos los productos:

```bash
# Modo dry-run
python3 configurar_productos_completo_master_dev.py --dry-run

# Ejecución real
python3 configurar_productos_completo_master_dev.py
```

**Qué hace:**
- Activa `sale_ok`, `purchase_ok`, `available_in_pos` para todos los productos
- Asigna rutas de inventario requeridas:
  - Belgrano 1: suministrar producto de Nakel Central
  - Belgrano 2: suministrar producto de Nakel Central
  - Belgrano 3: suministrar producto de Nakel Central
  - Belgrano 4: suministrar producto de Nakel Central
  - Nak: suministrar producto de Nakel Central
  - Buy (Comprar)

## 🔍 Verificación y Corrección de Embalajes

### Verificar Embalaje de un Producto Específico

Compara embalaje de un producto entre Odoo y MSSQL:

```bash
# Por ID de producto
python3 verificar_embalaje_producto_odoo_vs_mssql.py --producto-id 5363

# Por código interno
python3 verificar_embalaje_producto_odoo_vs_mssql.py --codigo 781.10
```

**Qué hace:**
- Obtiene información completa del producto en Odoo (embalajes, dimensiones, peso)
- Busca el producto en MSSQL por código de barras o código interno
- Compara:
  - Cantidad del embalaje (qty) vs UNID_BULTO y CTD_UNIDADES de MSSQL
  - Nombre del producto vs cantidad sugerida
  - Dimensiones y peso
- Genera análisis de discrepancias y recomendaciones

### Revisar Todos los Embalajes

Revisa y compara embalajes de TODOS los productos entre Odoo y MSSQL:

```bash
# Revisión completa (genera reporte)
python3 revisar_embalajes_todos_productos_vs_mssql.py

# Limitar a N productos (para pruebas)
python3 revisar_embalajes_todos_productos_vs_mssql.py --limit 100
```

**Qué hace:**
- Obtiene todos los productos con embalajes de Odoo
- Busca correspondientes en MSSQL por código de barras
- Compara cantidades (qty vs UNID_BULTO, CTD_UNIDADES)
- Analiza discrepancias nombre vs cantidad
- Genera reporte detallado con:
  - Estadísticas generales
  - Lista de discrepancias de cantidad
  - Lista de discrepancias nombre vs cantidad

**Reporte generado:**
- Ubicación: `../reportes/comparacion_embalajes_odoo_mssql_YYYYMMDD_HHMMSS.txt`
- Incluye top 50 discrepancias ordenadas por diferencia

### Corregir Discrepancias de Cantidad

Corrige automáticamente discrepancias de cantidad usando UNID_BULTO de MSSQL GESTION:

```bash
# Modo dry-run (ver qué se corregiría)
python3 corregir_discrepancias_cantidad_embalajes_desde_mssql.py --dry-run

# Corregir discrepancias
python3 corregir_discrepancias_cantidad_embalajes_desde_mssql.py
```

**Qué hace:**
- Identifica productos con discrepancias entre qty (Odoo) y UNID_BULTO (MSSQL)
- Actualiza el qty del embalaje con el valor de UNID_BULTO de MSSQL
- Actualiza el nombre del embalaje a "Bulto x{N}"
- **Omite lo que diga el nombre del artículo** (solo usa UNID_BULTO de MSSQL)

**Nota importante:** Este script corrige solo discrepancias de cantidad reales, no las discrepancias nombre vs cantidad (que pueden ser normales si el nombre describe otra cosa).

## 🔐 Gestión de Permisos

### Asignar Permisos para Modificar Productos

Asigna el grupo "Product Creation" a encargados de sucursales para que puedan modificar productos (especialmente códigos de barras):

```bash
# Solo verificar (no asignar)
python3 asignar_permisos_modificar_productos_encargados.py --verificar-solo

# Modo dry-run (ver qué se asignaría)
python3 asignar_permisos_modificar_productos_encargados.py --dry-run

# Asignar permisos
python3 asignar_permisos_modificar_productos_encargados.py
```

**Usuarios objetivo:**
- Manuel Claudia Isabel - Belgrano 1 (C1, C2)
- Varas Adrian Marcelo - Belgrano 2 (C1, C2)
- Robles Angel Jose - Belgrano 3 (C1, C2)
- Ramos Nancy - Belgrano 4 (C1)

**Permisos otorgados:**
- Grupo "Product Creation" (Extra Rights) - Permite modificar productos (Read, Write, Create)
- Grupo "Inventory / User" - Permite crear y modificar traslados internos (pedidos de mercadería)
- Incluye modificación de códigos de barras
- Permite actualizar información de productos desde colectoras
- Permite realizar ajustes en pedidos de mercadería

## 📞 Soporte

Para problemas o preguntas:
- Revisar los logs de ejecución
- Verificar que LibreOffice esté instalado
- Confirmar que `config_nakel.py` tenga la configuración correcta
- Ejecutar en modo dry-run primero para diagnosticar
- Para scripts de MSSQL, verificar que `pyodbc` y ODBC Driver 18 estén instalados

## 📊 Información de Embalajes en MSSQL

### Campos Relevantes en ARTICULOS

- **UNID_BULTO**: Unidades por bulto (campo principal para embalajes)
- **CTD_UNIDADES**: Cantidad de unidades (información adicional)
- **UNIDAD_MEDIDA**: Unidad de medida del producto
- **DIMBULTO_ALTO**: Altura del bulto (en cm)
- **DIMBULTO_ANCHO**: Ancho del bulto (en cm)
- **DIMBULTO_LARGO**: Largo del bulto (en cm)
- **PESO_UMEDIDA**: Peso del producto (en kg)

### Matching entre Odoo y MSSQL

Los scripts usan código de barras (PLU) como método principal de matching, ya que es el más confiable:
- Busca en `ARTICULOPLU.PLU` (MSSQL) = `product.template.barcode` (Odoo)
- Si no se encuentra por código de barras, intenta por código interno normalizado

### Normalización de Códigos

Los scripts normalizan códigos internos para mejorar el matching:
- Reemplaza comas por puntos: `781,10` → `781.10`
- Elimina espacios en blanco
- Esto permite matching entre formatos diferentes

---

**Última actualización**: 2025-12-27  
**Odoo Version**: 18.0 Enterprise  
**Ambiente**: master_dev / master_18

