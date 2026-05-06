# Procedimiento de Migración de Listas de Precios desde Excel a Odoo

## Resumen

Este procedimiento documenta el proceso completo para migrar listas de precios desde archivos Excel (.xls/.xlsx) a Odoo master_18, incluyendo la creación de productos faltantes.

## Contexto

Cuando se tiene una lista de precios en formato Excel que necesita ser migrada a Odoo, este proceso:
1. Identifica productos que no existen en Odoo
2. Crea los productos faltantes con sus categorías
3. Migra los precios a la lista de precios correspondiente

## Requisitos

### Archivo Excel

El archivo Excel debe contener las siguientes columnas:

| Columna | Descripción | Requerido | Ejemplo |
|---------|-------------|-----------|---------|
| Codigo | Código de referencia interna | Sí | `781.3` |
| Descripcion | Nombre del producto | Sí | `BABY DOLL MISTERIO 12X3U.-690-` |
| Precio C/IVA | Precio de venta con IVA | Sí | `11414,82` (formato argentino) |
| Nombre Rubro | Categoría del producto | Recomendado | `NOVEDADES` |
| CxB | Cantidad por bulto | Opcional | `16` |
| Stock | Stock disponible | Opcional | `24` |

**Formato de precios**: Los precios deben estar en formato argentino (comas como separador decimal):
- ✅ Correcto: `11414,82`
- ❌ Incorrecto: `11414.82`

### Sistema

- **Odoo**: Versión 18.0 Enterprise
- **Base de datos**: master_18 (Producción)
- **Python**: 3.8 o superior
- **LibreOffice**: Instalado (para conversión Excel → CSV)

## Proceso Paso a Paso

### 1. Preparación del Archivo Excel

1. Exportar la lista de precios desde el sistema de origen
2. Guardar como `.xls` o `.xlsx`
3. Verificar que contenga las columnas requeridas
4. Colocar el archivo en: `/media/klap/raid5/cursor_files/nakel/ventas/Listas de precios/`

### 2. Análisis Inicial (Opcional pero Recomendado)

Analizar qué productos no existen en Odoo:

```bash
cd "/media/klap/raid5/cursor_files/nakel/ventas/Listas de precios/scripts"
python3 analizar_productos_no_mapeados.py --lista Lista1.xls
```

**Resultado**: Genera un reporte `reporte_no_mapeados_*.txt` con:
- Productos con código que no existe
- Productos con nombre que no existe
- Posibles similares encontrados

### 3. Creación de Productos Faltantes

**IMPORTANTE**: Este paso debe ejecutarse ANTES de la migración de precios.

#### 3.1. Ejecución en Modo Dry-Run

```bash
python3 crear_productos_faltantes_desde_excel.py \
    --lista Lista1.xls \
    --nombre-lista-odoo "Lista 1" \
    --dry-run
```

**Qué verifica:**
- Cantidad de productos que se crearán
- Categorías que se crearán
- Precios que se agregarán

#### 3.2. Ejecución Real

```bash
python3 crear_productos_faltantes_desde_excel.py \
    --lista Lista1.xls \
    --nombre-lista-odoo "Lista 1"
```

**Qué hace:**
1. Identifica productos del Excel que no existen en Odoo
2. Crea categorías basadas en "Nombre Rubro" (si no existen)
3. Obtiene unidades de compra basadas en CxB (Cantidad por Bulto)
4. Crea cada producto con:
   - Nombre (Descripcion)
   - Código interno (Codigo)
   - Categoría (Nombre Rubro)
   - **Unidad de compra** (basada en CxB, ej: "Bulto x12", "Bulto x6")
   - Precio de venta (Precio C/IVA)
   - Habilitado para Ventas, Compras y Puntos de Venta
   - Tipo: Consumible
5. Agrega los precios a la lista de precios especificada

**Tiempo estimado**: ~1-2 minutos por cada 100 productos

#### 3.3. Actualizar Unidades de Compra en Productos Existentes (Opcional)

Si productos ya fueron creados anteriormente sin unidad de compra, puedes actualizarlos:

```bash
# Modo dry-run
python3 actualizar_unidades_compra_productos_existentes.py --lista Lista1.xls --dry-run

# Ejecución real
python3 actualizar_unidades_compra_productos_existentes.py --lista Lista1.xls
```

Este script actualiza la unidad de compra (`uom_po_id`) en productos existentes basándose en el valor CxB del Excel.

### 4. Migración de Precios

Una vez creados los productos faltantes, migrar todos los precios:

#### 4.1. Ejecución en Modo Dry-Run

```bash
python3 migrar_lista1_desde_excel.py \
    --lista Lista1.xls \
    --nombre-lista-odoo "Lista 1" \
    --dry-run
```

#### 4.2. Ejecución Real

```bash
python3 migrar_lista1_desde_excel.py \
    --lista Lista1.xls \
    --nombre-lista-odoo "Lista 1"
```

**Qué hace:**
1. Lee todos los productos del Excel
2. Crea mapeo con productos existentes en Odoo (por código, nombre exacto, nombre normalizado)
3. Para cada producto mapeado:
   - Si existe en la lista: actualiza el precio
   - Si no existe en la lista: agrega el precio
4. Genera reporte de productos no mapeados

**Tiempo estimado**: ~30-60 segundos por cada 100 productos

## Configuración de Productos Creados

Los productos creados tienen la siguiente configuración:

| Campo | Valor | Descripción |
|-------|-------|-------------|
| `type` | `consu` | Tipo: Consumible (no almacenable) |
| `sale_ok` | `True` | ✅ Disponible para ventas |
| `purchase_ok` | `True` | ✅ Disponible para compras |
| `available_in_pos` | `True` | ✅ Disponible en puntos de venta |
| `categ_id` | Basada en "Nombre Rubro" | Categoría del producto |
| `uom_po_id` | Basada en CxB (ej: "Bulto x12") | **Unidad de compra** |
| `uom_id` | `1` (Units) | Unidad de medida (venta) |
| `list_price` | Precio C/IVA del Excel | Precio de venta |
| `default_code` | Codigo del Excel | Código de referencia interna |
| `active` | `True` | Producto activo |

### Unidades de Compra

El script asigna automáticamente la unidad de compra basándose en la columna **CxB** (Cantidad por Bulto) del Excel:

- **CxB = 1**: Usa "Units" (unidades individuales)
- **CxB > 1**: Busca la unidad "Bulto x{CxB}" (ej: "Bulto x12", "Bulto x6")
- Si la unidad no existe en Odoo, usa "Units" por defecto

Las unidades de compra deben existir previamente en Odoo. La mayoría ya están creadas (Bulto x2, Bulto x6, Bulto x12, etc.).

## Estrategias de Mapeo

El script usa múltiples estrategias para mapear productos (en orden de prioridad):

1. **Por Código Interno** (más confiable)
   - `Codigo` (Excel) = `default_code` (Odoo)

2. **Por Nombre Exacto**
   - `Descripcion` (Excel) = `name` (Odoo)

3. **Por Nombre Normalizado**
   - Normaliza nombres (remueve prefijos como "ZZZ", espacios extra, sufijos)
   - Compara después de normalización

## Protecciones del Sistema

### Lista Predeterminada

El script **NO modifica** la lista predeterminada de Odoo. Detecta automáticamente la lista predeterminada y la excluye de las operaciones.

### Validaciones

- Productos sin código ni nombre: Se omiten
- Precios inválidos (≤ 0): Se omiten
- Errores de creación: Se registran pero no detienen el proceso

## Resultados Esperados

### Creación de Productos

**Ejemplo de salida:**
```
📊 RESUMEN
✅ Productos creados: 839
💰 Precios agregados a lista: 838
📁 Categorías procesadas: 153
❌ Errores: 0
```

### Migración de Precios

**Ejemplo de salida:**
```
📊 RESUMEN:
   ✅ Precios nuevos: 748
   🔄 Precios actualizados: 1958
   ❌ Sin mapeo: 760
   ⚠️  Errores: 0
```

## Verificación Post-Migración

Después de completar la migración, verificar:

1. **En Odoo**:
   - Ir a Ventas → Configuración → Listas de Precios
   - Seleccionar la lista migrada
   - Verificar que tenga los productos esperados

2. **Productos creados**:
   - Ir a Inventario → Productos → Productos
   - Buscar algunos productos por código
   - Verificar categoría, precio, y disponibilidad

3. **Puntos de Venta**:
   - Verificar que los productos aparezcan en el POS
   - Verificar precios correctos

## Troubleshooting

### Error: "No se pudo generar el CSV"

**Causa**: LibreOffice no está instalado o no está en el PATH.

**Solución**:
```bash
sudo apt install libreoffice
```

### Error: "No se encontró la lista en Odoo"

**Causa**: El nombre de la lista no coincide exactamente.

**Solución**: Verificar el nombre exacto de la lista en Odoo y usar `--nombre-lista-odoo` con el nombre correcto.

### Productos no se mapean

**Causas posibles**:
- Código diferente en Odoo
- Nombre diferente en Odoo
- Producto realmente no existe

**Solución**: Ejecutar `analizar_productos_no_mapeados.py` para ver detalles.

### Precios con formato incorrecto

**Causa**: Precios en formato incorrecto (puntos en lugar de comas).

**Solución**: Corregir formato en Excel antes de ejecutar.

## Ejemplo Completo de Ejecución

```bash
# 1. Ir al directorio
cd "/media/klap/raid5/cursor_files/nakel/ventas/Listas de precios/scripts"

# 2. Analizar (opcional)
python3 analizar_productos_no_mapeados.py --lista Lista1.xls

# 3. Crear productos - DRY RUN
python3 crear_productos_faltantes_desde_excel.py \
    --lista Lista1.xls \
    --nombre-lista-odoo "Lista 1" \
    --dry-run

# 4. Crear productos - REAL
python3 crear_productos_faltantes_desde_excel.py \
    --lista Lista1.xls \
    --nombre-lista-odoo "Lista 1"

# 5. Migrar precios - DRY RUN
python3 migrar_lista1_desde_excel.py \
    --lista Lista1.xls \
    --nombre-lista-odoo "Lista 1" \
    --dry-run

# 6. Migrar precios - REAL
python3 migrar_lista1_desde_excel.py \
    --lista Lista1.xls \
    --nombre-lista-odoo "Lista 1"
```

## Notas Importantes

1. **Orden de ejecución**: Siempre crear productos ANTES de migrar precios
2. **Dry-run**: Siempre ejecutar en modo dry-run primero
3. **Backup**: Hacer backup de la base de datos antes de ejecutar en producción
4. **Horarios**: Ejecutar en horarios de baja carga
5. **Validación**: Validar resultados manualmente después de la migración

## Referencias

- Scripts: `/media/klap/raid5/cursor_files/nakel/ventas/Listas de precios/scripts/`
- Documentación: Ver `README.md` en el directorio de scripts
- Configuración: `/media/klap/raid5/cursor_files/config_nakel.py`

---

**Versión**: 1.0  
**Fecha**: 2025-12-27  
**Autor**: Corolla  
**Ambiente**: master_18 (Odoo 18.0 Enterprise)

