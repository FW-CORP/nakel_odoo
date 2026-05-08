# 🔧 SOLUCIÓN: Permisos del Filestore de Odoo

## 📋 Descripción del Problema

**Error:** `[Errno 13] Permission denied: '/var/lib/odoo/filestore/master_2'`

**Causa:** Los archivos del `filestore` de Odoo pertenecen al usuario `ubuntu` en lugar del usuario `odoo`, lo que impide que Odoo pueda escribir en estos directorios al restaurar backups.

## 🔍 Diagnóstico

### Verificar Permisos Actuales
```bash
docker exec -it odoo_temp_restore-odoo-1 ls -la /var/lib/odoo/filestore/
```

**Resultado esperado del problema:**
```
drwxrwxr-x 259 ubuntu ubuntu 4096 Aug 18 05:33 .
drwxrwxr-x   2 ubuntu ubuntu 4096 Aug 18 05:33 00
drwxrwxr-x   2 ubuntu ubuntu 4096 Aug 18 05:33 01
...
```

## 🛠️ Solución

### Comando de Solución
```bash
docker exec -it --user root odoo_temp_restore-odoo-1 chown -R odoo:odoo /var/lib/odoo/filestore
```

### Verificación de la Solución
```bash
docker exec -it odoo_temp_restore-odoo-1 ls -la /var/lib/odoo/filestore/
```

**Resultado esperado después de la solución:**
```
drwxrwxr-x 259 odoo odoo 4096 Aug 18 05:33 .
drwxrwxr-x   2 odoo odoo 4096 Aug 18 05:33 00
drwxrwxr-x   2 odoo odoo 4096 Aug 18 05:33 01
...
```

## 📁 Archivos de la Solución

### 1. `solucion_permisos_filestore.py`
Script automatizado que:
- Verifica los permisos actuales
- Ejecuta la solución
- Valida que la solución funcionó
- Genera logs detallados

### 2. `README_SOLUCION_PERMISOS_FILESTORE.md`
Esta documentación con:
- Descripción del problema
- Diagnóstico
- Solución paso a paso
- Comandos de verificación

## 🚀 Uso del Script Automatizado

```bash
python3 solucion_permisos_filestore.py
```

El script:
1. Verifica los permisos actuales
2. Ejecuta la solución automáticamente
3. Valida que la solución funcionó
4. Genera un log con timestamp

## ⚠️ Consideraciones Importantes

### Cuándo Aplicar esta Solución
- Al restaurar backups de Odoo en contenedores Docker
- Cuando aparezca el error "Permission denied" en el filestore
- Cuando los archivos del filestore pertenezcan a un usuario diferente a `odoo`

### Precauciones
- **Siempre hacer backup** antes de cambiar permisos
- Verificar que el contenedor esté funcionando
- Asegurar que el nombre del contenedor sea correcto

### Variaciones del Comando
Si el nombre del contenedor es diferente, ajustar:
```bash
docker exec -it --user root [NOMBRE_CONTENEDOR] chown -R odoo:odoo /var/lib/odoo/filestore
```

## 🔄 Proceso Completo de Restauración

1. **Restaurar backup** en el contenedor
2. **Verificar permisos** del filestore
3. **Aplicar solución** si es necesario
4. **Verificar** que Odoo puede acceder al filestore
5. **Probar** la restauración manual

## 📊 Casos de Éxito

### Restauración del 2025-08-22
- ✅ Backup restaurado exitosamente
- ✅ Permisos corregidos
- ✅ Odoo funcionando correctamente
- ✅ Acceso al filestore restaurado

## 🎯 Comandos Rápidos

### Diagnóstico Rápido
```bash
docker exec -it odoo_temp_restore-odoo-1 ls -la /var/lib/odoo/filestore/ | head -5
```

### Solución Rápida
```bash
docker exec -it --user root odoo_temp_restore-odoo-1 chown -R odoo:odoo /var/lib/odoo/filestore
```

### Verificación Rápida
```bash
docker exec -it odoo_temp_restore-odoo-1 ls -la /var/lib/odoo/filestore/ | grep "odoo odoo" | wc -l
```

---

**Última actualización:** 2025-08-22  
**Versión:** 1.0  
**Autor:** Corolla AI Assistant  
**Estado:** ✅ Verificado y funcionando
