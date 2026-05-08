# 📖 Configuración Detallada: Permisos de Inventario por Sucursal

Documentación técnica detallada sobre la implementación de permisos de inventario por sucursal.

## 🎯 Problema Original

Los encargados de sucursales veían información de todas las ubicaciones en el módulo de inventario:
- Veían recepciones, almacenamiento y entregas de Nakel Central
- Veían información de otras sucursales Belgrano
- No había restricciones por ubicación/warehouse

**Ejemplo:** El encargado de Belgrano 1 podía ver 131 transferencias de Nakel Central cuando solo debería ver las de su sucursal.

## 💡 Solución Implementada

Se implementó un sistema de **reglas de registro (ir.rule)** que filtran el acceso por ubicación según el grupo de usuarios asignado a cada encargado.

### Componentes de la Solución

1. **Grupos de Usuarios por Sucursal**
   - Un grupo específico para cada sucursal
   - Categoría: Inventory
   - Nombre: "Encargados [Nombre Sucursal]"

2. **Reglas de Registro (ir.rule)**
   - Una regla por modelo de inventario por sucursal
   - Aplicadas solo a los grupos específicos
   - Filtran registros usando dominios basados en ubicación

3. **Asignación de Usuarios**
   - Cada encargado asignado a su grupo correspondiente
   - Los grupos pueden tener múltiples usuarios si es necesario

## 🔧 Implementación Técnica

### Estructura de Reglas

Para cada sucursal se crean 4 reglas de registro:

#### 1. Regla para stock.picking

**Nombre:** `Encargados [Sucursal]: Ver solo transferencias de [Sucursal]`

**Dominio:**
```python
['|', 
 ('location_id', 'child_of', <location_id>), 
 ('location_dest_id', 'child_of', <location_id>)
]
```

**Explicación:** 
- Muestra transferencias donde la ubicación origen O la ubicación destino pertenezcan a la sucursal
- Usa `child_of` para incluir sub-ubicaciones si las hay

**Modelo afectado:** `stock.picking`
- Recepciones
- Almacenamiento
- Traslados internos
- Órdenes de entrega
- Cross-dock

#### 2. Regla para stock.move

**Nombre:** `Encargados [Sucursal]: Ver solo movimientos de [Sucursal]`

**Dominio:**
```python
['|', 
 ('location_id', 'child_of', <location_id>), 
 ('location_dest_id', 'child_of', <location_id>)
]
```

**Explicación:**
- Similar a stock.picking pero a nivel de movimientos individuales
- Cada línea de transferencia es un stock.move

**Modelo afectado:** `stock.move`

#### 3. Regla para stock.quant

**Nombre:** `Encargados [Sucursal]: Ver solo stock de [Sucursal]`

**Dominio:**
```python
[('location_id', 'child_of', <location_id>)]
```

**Explicación:**
- Muestra solo las cantidades de stock ubicadas en la sucursal
- Filtro más simple porque stock.quant tiene una sola ubicación

**Modelo afectado:** `stock.quant`
- Vista de inventario
- Cantidades por ubicación
- Ajustes de inventario

#### 4. Regla para stock.picking.type

**Nombre:** `Encargados [Sucursal]: Ver solo tipos de operación de [Sucursal]`

**Dominio:**
```python
[('warehouse_id', '=', <warehouse_id>)]
```

**Explicación:**
- Filtra por warehouse directamente
- Cada warehouse tiene sus propios tipos de operación

**Modelo afectado:** `stock.picking.type`
- Tipos de recepción
- Tipos de almacenamiento
- Tipos de entrega
- Tipos de cross-dock

### Operador `child_of`

El operador `child_of` en Odoo incluye:
- La ubicación misma
- Todas las sub-ubicaciones (hijos, nietos, etc.)

**Ejemplo:**
Si la ubicación es `B1/Existencias` (ID: 109), el filtro `('location_id', 'child_of', 109)` incluirá:
- B1/Existencias
- B1/Existencias/Cualquier sub-ubicación
- B1/Entrada (si está dentro del árbol)
- etc.

## 📊 Datos de Configuración

### Ubicaciones

| Sucursal | Path Completo | ID | Warehouse ID |
|----------|---------------|----|--------------| 
| Belgrano 1 | B1/Existencias | 109 | 15 |
| Belgrano 2 | B2/Existencias | 116 | 16 |
| Belgrano 3 | B3/Existencias | 123 | 17 |
| Belgrano 4 | B4/Existencias | 130 | 18 |

### IDs de Reglas Creadas

| Sucursal | stock.picking | stock.move | stock.quant | stock.picking.type |
|----------|---------------|------------|-------------|-------------------|
| Belgrano 1 | 377 | 378 | 379 | 380 |
| Belgrano 2 | 381 | 382 | 383 | 384 |
| Belgrano 3 | 385 | 386 | 387 | 388 |
| Belgrano 4 | 389 | 390 | 391 | 392 |

## 🧪 Testing y Verificación

### Verificación Manual

1. **Iniciar sesión como encargado:**
   - Login: `golosinasbelgrano1@nakel.ar`
   - Ir a: Inventario > Operaciones > Transferencias

2. **Verificar que solo aparecen transferencias de Belgrano 1:**
   - No deberían aparecer transferencias de Nakel Central
   - No deberían aparecer transferencias de otras sucursales Belgrano

3. **Verificar stock:**
   - Ir a: Inventario > Informes > Inventario por ubicación
   - Solo debería ver stock de B1/Existencias

### Verificación Técnica

Ejecutar el script de diagnóstico:
```bash
python3 diagnosticar_permisos_inventario_por_ubicacion_master18.py
```

Este script verifica:
- Existencia de grupos
- Existencia de reglas
- Asignación de usuarios
- Configuración de ubicaciones

## 🔄 Flujo de Ejecución del Script

1. **Conexión a Odoo**
   - Autenticación con credenciales de master_18

2. **Obtención de Categoría Inventory**
   - Busca categoría de grupos "Inventory"

3. **Por cada sucursal:**
   - Busca/obtiene ubicación por path completo
   - Busca/obtiene warehouse por código
   - Crea/obtiene grupo de usuarios
   - Crea/actualiza reglas de registro (4 por sucursal)
   - Asigna usuarios al grupo

4. **Resumen de resultados**

## ⚠️ Consideraciones Importantes

### Rendimiento

- Las reglas de registro se evalúan en cada búsqueda
- El operador `child_of` puede ser costoso si hay muchas sub-ubicaciones
- En este caso es aceptable porque cada sucursal tiene pocas ubicaciones

### Mantenimiento

- Si se crea una nueva ubicación bajo B1/Existencias, automáticamente será visible para Belgrano 1
- Si se cambia la estructura de ubicaciones, puede ser necesario revisar las reglas

### Extensibilidad

- Para agregar una nueva sucursal, solo hay que agregarla en `SUCURSALES_CONFIG`
- El script creará automáticamente grupo y reglas

## 🐛 Troubleshooting

### Usuario ve información de otras sucursales

1. Verificar que el usuario tiene asignado el grupo correcto
2. Verificar que las reglas están activas
3. Verificar que el usuario cerró sesión y volvió a iniciar
4. Ejecutar diagnóstico específico del usuario

### Reglas no funcionan

1. Verificar que las reglas están activas en Odoo
2. Verificar que el dominio es correcto
3. Verificar que el grupo está asignado a las reglas
4. Verificar que el usuario no tiene permisos de administrador (los admins no se ven afectados)

### Error al ejecutar script

1. Verificar conexión a Odoo
2. Verificar credenciales en config_nakel.py
3. Verificar que los paths de ubicación son correctos
4. Ejecutar en modo dry-run primero para identificar problemas

## 📚 Referencias Técnicas

- [Documentación Odoo: Record Rules](https://www.odoo.com/documentation/18.0/developer/reference/backend/orm.html#record-rules)
- [Documentación Odoo: Domain Syntax](https://www.odoo.com/documentation/18.0/developer/reference/backend/orm.html#domain)
- [Documentación Odoo: Groups](https://www.odoo.com/documentation/18.0/developer/reference/backend/orm.html#groups)

## 👤 Autor

Corolla - Asistente Técnico FWCORP

## 📅 Fecha

2025-01-XX
