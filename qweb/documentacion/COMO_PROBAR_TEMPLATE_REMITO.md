# Cómo Probar el Template de Remito Nakel 2024

Esta guía explica cómo probar el template mejorado de remito después de instalarlo en Odoo.

---

## 📋 Pasos para Probar el Template

### 1. Acceder a Remitos en Odoo

1. **Navegar a Inventario**:
   - Menú principal → **Inventario** → **Operaciones** → **Remitos** (o **Picking**)

2. **O buscar directamente**:
   - Buscar en el menú: "Remitos" o "Delivery Orders"

### 2. Seleccionar o Crear un Remito

#### Opción A: Usar un Remito Existente

1. Abrir la lista de remitos
2. Buscar un remito que tenga:
   - ✅ Estado: "Hecho" (Done) o "En espera" (Waiting)
   - ✅ Tipo: "Salida" (Outgoing)
   - ✅ Con productos asignados
3. Hacer clic en el remito para abrirlo

#### Opción B: Crear un Remito Nuevo (Si no hay existentes)

1. Hacer clic en **"Crear"**
2. Completar:
   - **Tipo de operación**: Salida (Outgoing)
   - **Cliente**: Seleccionar un cliente existente
   - **Origen**: Puede ser un pedido de venta o dejarlo vacío
3. En la pestaña **"Productos"**, agregar:
   - Al menos un producto
   - Cantidades
4. Guardar el remito
5. (Opcional) Hacer clic en **"Validar"** para cambiar el estado a "Hecho"

### 3. Imprimir el Remito

Una vez abierto el remito:

1. Hacer clic en el botón **"Imprimir"** (arriba a la derecha)
2. En el menú desplegable, seleccionar:
   - **"Remito Nakel 2024"** o
   - **"Delivery Document Nakel 2024"**
3. Se generará el PDF con el nuevo template

### 4. Verificar el PDF Generado

Revisar que el PDF incluya:

✅ **Encabezado fiscal**:
- Razón social de la empresa
- Letra "R" grande
- CUIT
- IIBB
- Condición fiscal

✅ **Datos del destinatario**:
- Nombre, CUIT/DNI
- Domicilio completo

✅ **Información del pedido**:
- Número de pedido
- Fecha

✅ **Detalle de mercadería**:
- Tabla con código, descripción, cantidad, lote

✅ **QR Code**:
- Debe aparecer un código QR (o un placeholder si no está disponible)

✅ **Información de transporte**:
- Transportista (si aplica)
- Observaciones

✅ **Firma y conformidad**:
- Espacios para firma

✅ **Leyendas legales**:
- Menciona RG AFIP 4294/2024
- Condiciones legales

---

## 🔍 Solución de Problemas

### Problema 1: No aparece el reporte "Remito Nakel 2024" en el menú

**Posibles causas:**
- El reporte no está activo
- El reporte no está asociado al template
- Permisos de usuario

**Solución:**
```python
# Verificar estado del reporte (puedes usar el script o verificar manualmente)
# En Odoo: Configuración → Técnico → Reportes → Reportes de Acción
# Buscar: "Remito Nakel 2024"
# Verificar que esté activo y que el "Report Name" sea: stock.report_delivery_document_nakel_2024
```

### Problema 2: El PDF no se genera o muestra error

**Verificar:**
1. Que el remito tenga productos
2. Que el remito tenga un cliente asignado
3. Revisar logs de Odoo para ver errores específicos

### Problema 3: El QR Code no aparece o aparece como placeholder

**Causa probable:**
- El campo `qr_code_url` no está disponible en `stock.picking`
- El remito no está asociado a una factura electrónica

**Solución:**
- El template tiene un placeholder que aparece cuando no hay QR Code disponible
- Para que aparezca el QR Code real, el remito debe estar vinculado a una factura electrónica
- Verificar que el módulo `l10n_ar` esté instalado y configurado correctamente

### Problema 4: Faltan datos en el encabezado fiscal (CUIT, IIBB, etc.)

**Verificar:**
1. Ir a **Contabilidad** → **Configuración** → **Compañías** → Seleccionar la compañía
2. Verificar que estén completos:
   - **CUIT**: Campo "VAT" (Identificación Fiscal)
   - **IIBB**: Campo "Gross Income Number" (Número de IIBB)
   - **Inicio de actividades**: Campo "AFIP Start Date"
3. Guardar los cambios

---

## 📸 Qué Buscar en el PDF

### Ejemplo Visual del Template

```
┌─────────────────────────────────────────────────────────────┐
│ EMPRESA NAKEL S.A.        [R]        Remito                 │
│ Dirección completa          Nro: REM-001                     │
│                             Fecha: 27/12/2025               │
│ CUIT: 20-12345678-9        IIBB: 123456789                  │
│ IVA Responsable Inscripto  Inicio: 01/01/2020               │
├─────────────────────────────────────────────────────────────┤
│ DATOS DEL DESTINATARIO                                      │
│ Nombre: Cliente Ejemplo                                     │
│ CUIT/DNI: 20-98765432-1                                     │
│ Domicilio: Calle Falsa 123, CABA                            │
├─────────────────────────────────────────────────────────────┤
│ INFORMACIÓN DEL PEDIDO                                      │
│ Nº Pedido: SO001                                            │
│ Fecha Pedido: 27/12/2025                                    │
├─────────────────────────────────────────────────────────────┤
│ DETALLE DE MERCADERÍA                                       │
│ ┌──────────┬──────────────┬──────────┬─────────┐           │
│ │ Código   │ Descripción  │ Cantidad │ Lote    │           │
│ ├──────────┼──────────────┼──────────┼─────────┤           │
│ │ PROD-001 │ Producto 1   │    5     │ L001    │           │
│ └──────────┴──────────────┴──────────┴─────────┘           │
├─────────────────────────────────────────────────────────────┤
│ ┌──────────────────────┬──────────────────────────────────┐ │
│ │   [QR CODE]          │  INFORMACIÓN DE TRANSPORTE       │ │
│ │                      │  Transportista: ...              │ │
│ │  RG AFIP 4294/2024   │  Observaciones: ...              │ │
│ └──────────────────────┴──────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ FIRMA Y ACLARACIÓN          RECIBÍ CONFORME                 │
│ _____________________       _____________________            │
│                             Firma, Aclaración y DNI         │
│                             Fecha: ___/___/___               │
├─────────────────────────────────────────────────────────────┤
│ CONDICIONES:                                                │
│ Se requiere DNI para la entrega. Verificar cantidad y...    │
│                                                             │
│ CONDICIONES LEGALES                                         │
│ Este remito cumple con los requisitos de la RG AFIP...     │
└─────────────────────────────────────────────────────────────┘
```

---

## 🧪 Pruebas Recomendadas

### Test 1: Remito Básico
- ✅ Crear remito con un solo producto
- ✅ Verificar que todos los campos se muestren correctamente

### Test 2: Remito con Varios Productos
- ✅ Crear remito con 5-10 productos
- ✅ Verificar que la tabla se ajuste correctamente
- ✅ Verificar paginación si aplica

### Test 3: Remito con Lotes
- ✅ Crear remito con productos que tengan lotes
- ✅ Verificar que los lotes se muestren en la columna correspondiente

### Test 4: Remito sin QR Code
- ✅ Verificar que aparezca el placeholder cuando no hay QR Code
- ✅ Verificar que el diseño no se rompa

### Test 5: Remito con Transportista
- ✅ Asignar un transportista al remito
- ✅ Verificar que se muestre en la sección de transporte

---

## 📝 Notas Adicionales

1. **Actualizar Cache de Odoo**:
   - Si después de instalar el template no se ve el cambio, actualizar el cache:
   - Menú → **Configuración** → **Actualizar lista de apps** (o reiniciar Odoo)

2. **Modo Desarrollador**:
   - Si necesitas hacer cambios rápidos, activar el modo desarrollador:
   - Menú → **Configuración** → **Activar modo desarrollador**

3. **Ver Template en Código**:
   - Menú → **Configuración** → **Técnico** → **Interfaz de Usuario** → **Vistas**
   - Buscar: `stock.report_delivery_document_nakel_2024`
   - Ver y editar el código XML directamente si es necesario

---

**Última actualización**: 2025-12-27

