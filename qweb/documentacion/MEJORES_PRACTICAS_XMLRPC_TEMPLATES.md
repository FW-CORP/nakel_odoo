# Mejores Prácticas: Instalación de Templates QWeb vía XML-RPC

## 📋 Enfoque Actual

Este proyecto utiliza **XML-RPC directo** para instalar y actualizar templates QWeb en Odoo, sin crear módulos completos. Este enfoque tiene ventajas y limitaciones que deben entenderse.

---

## ✅ Ventajas del Enfoque XML-RPC

1. **Rápido de implementar**: No requiere crear estructura de módulo completa
2. **Flexible**: Permite cambios rápidos sin reiniciar Odoo
3. **Adecuado para pruebas**: Ideal para desarrollo y testing
4. **Sin dependencias de addons path**: No requiere configurar rutas de módulos

---

## ⚠️ Limitaciones y Consideraciones

### 1. **Manejo de PDFs con `render_qweb_pdf`**

**Problema**: `ir.actions.report.render_qweb_pdf(...)` devuelve datos en diferentes formatos según la versión de Odoo/XML-RPC.

**Solución implementada**:

```python
pdf_result = models.execute_kw(
    db, uid, password,
    'ir.actions.report', 'render_qweb_pdf',
    [report_id[0], [document_id]]
)

# pdf_result suele ser: [Binary(...), 'pdf']  o  (Binary(...), 'pdf')
pdf_bin = pdf_result[0] if isinstance(pdf_result, (list, tuple)) else pdf_result

# Manejar xmlrpc.client.Binary correctamente
if isinstance(pdf_bin, xmlrpc.client.Binary):
    pdf_bytes = pdf_bin.data
elif hasattr(pdf_bin, 'data'):
    pdf_bytes = pdf_bin.data
elif isinstance(pdf_bin, bytes):
    pdf_bytes = pdf_bin
elif isinstance(pdf_bin, str):
    # Si viene como base64 string, decodificar
    pdf_bytes = base64.b64decode(pdf_bin)
else:
    # Último recurso
    pdf_bytes = base64.b64decode(str(pdf_bin))

with open(pdf_path, 'wb') as f:
    f.write(pdf_bytes)
```

**✅ Esto evita PDFs corruptos o vacíos** cuando cambia el tipo devuelto.

---

### 2. **Versionado y Trazabilidad**

**Limitación**: Los templates instalados vía XML-RPC no tienen:
- Historial de cambios automático
- Sistema de versionado integrado
- Dependencias declaradas

**Soluciones**:
- ✅ **Usar Git** para versionar los archivos XML de templates
- ✅ **Documentar cambios** en archivos `.md` con fechas
- ✅ **Mantener backups** antes de actualizar templates en producción
- ✅ **Usar scripts con `--dry-run`** para verificar cambios antes de aplicar

**Ejemplo de versionado manual**:

```bash
# Antes de actualizar
python3 instalar_templates_todos_master18.py --backup

# Verificar cambios
python3 instalar_templates_todos_master18.py --dry-run

# Aplicar cambios
python3 instalar_templates_todos_master18.py
```

---

### 3. **Templates Base de Odoo**

**Riesgo**: Si Odoo actualiza un template base que estás sobrescribiendo, tu template puede romperse sin avisar.

**Mitigaciones**:
- ✅ **Monitorear updates de Odoo**: Revisar changelogs antes de actualizar Odoo
- ✅ **Probar después de updates**: Siempre probar templates después de actualizar Odoo
- ✅ **Usar keys específicas**: Usar keys personalizadas (`*.nakel_2024`) en vez de sobrescribir los originales
- ✅ **Prioridades altas**: Usar `priority > 16` para que tu template tenga prioridad sobre los genéricos

**Ejemplo**:

```python
# ❌ NO hacer esto (sobrescribe template original)
template_key = 'account.report_invoice_document'

# ✅ HACER esto (template personalizado)
template_key = 'account.report_invoice_document_nakel_2024'
```

---

### 4. **Asociación con `ir.actions.report`**

**Limitación**: Los templates creados vía XML-RPC no están automáticamente vinculados a acciones de reporte.

**Solución implementada**: El script verifica y crea/actualiza el `ir.actions.report` asociado:

```python
# Verificar o crear el reporte asociado
report_ids = models.execute_kw(db, uid, password,
                                'ir.actions.report', 'search_read',
                                [[('report_name', '=', template_key)]],
                                {'fields': ['id', 'name', 'model', 'report_type']})

if report_ids:
    # Actualizar reporte existente
    models.execute_kw(db, uid, password, 'ir.actions.report', 'write',
                    [[report_id], {'report_name': template_key, 'active': True}])
else:
    # Crear nuevo reporte
    report_id = models.execute_kw(db, uid, password, 'ir.actions.report', 'create', [{
        'name': template_name,
        'model': model_name,
        'report_type': 'qweb-pdf',
        'report_name': template_key,
        'active': True,
    }])
```

---

## 🔧 Mejores Prácticas Recomendadas

### 1. **Estructura de Archivos**

```
nakel/qweb/
├── templates/                          # Templates XML
│   ├── account.report_invoice_document_nakel_2024_FACTURA_B_MEJORADO.xml
│   ├── stock.report_delivery_document_nakel_2024_MEJORADO.xml
│   └── account.report_credit_note_document_nakel_2024_MEJORADO.xml
├── scripts/                            # Scripts de instalación
│   ├── instalar_templates_todos_master18.py
│   ├── generar_proforma_ejemplo_master18.py
│   └── verificar_templates_instalados.py
├── documentacion/                      # Documentación
│   ├── MEJORES_PRACTICAS_XMLRPC_TEMPLATES.md  (este archivo)
│   └── HISTORIAL_CAMBIOS.md
└── reportes/                           # PDFs de prueba generados
```

### 2. **Nomenclatura de Templates**

**Regla**: Usar keys específicas con sufijo identificador:

- ✅ `account.report_invoice_document_nakel_2024`
- ✅ `stock.report_delivery_document_nakel_2024`
- ✅ `account.report_credit_note_document_nakel_2024`
- ❌ ~~`account.report_invoice_document`~~ (sobrescribe original)

### 3. **Backup Antes de Cambios**

Siempre hacer backup antes de actualizar templates en producción:

```python
def hacer_backup_template(models, uid, password, template_key):
    """Hace backup de un template antes de modificarlo"""
    templates = models.execute_kw(
        db, uid, password,
        'ir.ui.view', 'search_read',
        [[('key', '=', template_key)]],
        {'fields': ['id', 'arch', 'name', 'key']}
    )
    
    if templates:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"backups/template_{template_key.replace('.', '_')}_{timestamp}.xml"
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(templates[0]['arch'])
        print(f"✅ Backup guardado en: {backup_path}")
```

### 4. **Validación Post-Instalación**

Después de instalar, verificar que el template funciona:

```python
def verificar_template_instalado(models, uid, password, template_key, report_model):
    """Verifica que el template está instalado y funciona"""
    # Verificar template existe
    templates = models.execute_kw(...)
    if not templates:
        return False, "Template no encontrado"
    
    # Verificar reporte asociado
    reports = models.execute_kw(...)
    if not reports:
        return False, "Reporte no encontrado"
    
    # Verificar que el template puede renderizarse (opcional)
    # try:
    #     pdf_result = models.execute_kw(..., 'render_qweb_pdf', ...)
    #     ...
    
    return True, "OK"
```

### 5. **Logging y Trazabilidad**

Usar logging detallado para rastrear cambios:

```python
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/templates_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)
```

---

## 📝 Historial de Cambios

Mantener un archivo `HISTORIAL_CAMBIOS.md` con todos los cambios:

```markdown
## 2025-01-XX - Actualización Templates Factura B

- **Cambios**: Agregado campo QR Code obligatorio según RG AFIP 4294/2024
- **Templates afectados**: `account.report_invoice_document_nakel_2024`
- **Script usado**: `instalar_templates_todos_master18.py`
- **Backup**: `backups/template_account_report_invoice_document_nakel_2024_202501XX_HHMMSS.xml`
- **Pruebas**: ✅ Verificado con factura de prueba S00134
```

---

## 🚨 Cuándo Considerar Módulo Odoo

Aunque el enfoque XML-RPC es adecuado para este proyecto, **considera crear un módulo** si:

1. ✅ Necesitas **versionado estricto** para cumplimiento legal (ARCA)
2. ✅ Necesitas **dependencias complejas** entre templates
3. ✅ Necesitas **rollback automático** en caso de errores
4. ✅ Tienes **múltiples entornos** (dev/staging/prod) con CI/CD
5. ✅ Necesitas **auditoría completa** de cambios

Para este proyecto actual, **XML-RPC es suficiente** si sigues estas prácticas.

---

## ✅ Checklist Pre-Producción

Antes de aplicar cambios en producción (`master_18`):

- [ ] Backup de templates existentes
- [ ] Prueba en `master_dev` primero
- [ ] Verificación de PDFs generados
- [ ] Validación de campos AFIP/ARBA/ARCA
- [ ] Documentación de cambios
- [ ] Commit en Git con descripción clara
- [ ] Notificación a equipo si aplica

---

## 📚 Referencias

- [Odoo XML-RPC Documentation](https://www.odoo.com/documentation/18.0/developer/reference/backend/orm.html#xml-rpc)
- [QWeb Template Reference](https://www.odoo.com/documentation/18.0/developer/reference/frontend/qweb.html)
- [RG AFIP 4294/2024](https://www.afip.gob.ar/) - Requisitos QR Code obligatorio

---

**Última actualización**: 2025-01-XX
**Mantenido por**: Equipo Nakel / Corolla (AI Assistant)

