# Diagnóstico: PDF no refleja nakel_picking y error de actualización

## 1. Error de conexión PostgreSQL al actualizar

```
psycopg2.OperationalError: connection to server on socket "/var/run/postgresql/.s.PGSQL.5432" failed: fe_sendauth: no password supplied
```

**Causa:** Odoo intenta conectarse a PostgreSQL sin credenciales. El comando `odoo` usa configuración por defecto.

**Solución:** Usar el archivo de configuración de Odoo que tiene las credenciales:

```bash
# Opción A: Si Odoo usa un archivo de configuración (ej. /etc/odoo/odoo.conf)
odoo -c /etc/odoo/odoo.conf -u nakel_picking -d master_18 --stop-after-init

# Opción B: Si usas systemd, el servicio ya tiene la config. Actualizar desde la interfaz:
# Aplicaciones → Buscar "Nakel Picking" → Actualizar

# Opción C: Variables de entorno
export PGPASSWORD=tu_password
odoo -u nakel_picking -d master_18 --stop-after-init
```

**Verificar configuración:** Revisar en `/etc/odoo/odoo.conf` o donde esté tu config:
- `db_host`
- `db_user`
- `db_password`
- `db_name` (o usar `-d master_18`)

---

## 2. PDF no muestra el formato de nakel_picking

### Posibles causas

| Causa | Descripción | Cómo verificar |
|-------|-------------|----------------|
| **A. Módulo no actualizado** | La actualización falló por PostgreSQL, el módulo sigue en versión antigua | En Odoo: Ajustes → Aplicaciones → Nakel Picking → ver versión |
| **B. XPath no coincide** | Odoo 18 puede tener estructura distinta en `stock_picking_batch.report_picking_batch` | Revisar logs al imprimir; si hay error de template |
| **C. move_line_ids vacíos** | Los pickings no tienen operaciones detalladas; `_get_consolidated_lines()` usa `move_line_ids` | Si los traslados están en "Esperando" o "Asignado" sin "Comprobar disponibilidad" |
| **D. Reporte estándar se usa** | Otro módulo o caché usa el reporte original | Limpiar caché del navegador; reiniciar Odoo |

### Si ves solo flechas (→) en el PDF

Las flechas vienen de la columna **Paquete** cuando no hay paquete asignado:
```xml
<span>→ <span t-esc="line['result_package_name'] or 'PACK0000002'"/></span>
```

Eso indica que **el template de nakel_picking SÍ se está usando**, pero:
- La sección "Productos Consolidados" puede estar vacía si `move_line_ids` está vacío
- O las tablas se renderizan mal en el PDF

### Si ves el reporte estándar (sin "Resumen:", sin "Productos Consolidados")

Entonces el template de nakel_picking **no se está aplicando**. Posibles motivos:
1. Módulo no actualizado correctamente
2. XPath no coincide con la estructura de Odoo 18
3. Orden de carga: otro módulo sobrescribe después

---

## 3. Pasos de diagnóstico

### Paso 1: Verificar que el módulo está instalado y actualizado

```bash
# En Odoo (shell o desde psql)
# O desde la interfaz: Aplicaciones → Nakel Picking → debe estar "Instalado"
```

### Paso 2: Verificar estado de los pickings del lote

Antes de imprimir, en el lote:
- Los traslados deben tener **operaciones detalladas** (move_line_ids)
- Si están en "Esperando" o "Asignado", hacer clic en **"Comprobar disponibilidad"** para generar move_line_ids

### Paso 3: Revisar logs de Odoo al imprimir

```bash
# Al imprimir el reporte, revisar:
tail -f /var/log/odoo/odoo-server.log
# O si usas docker:
docker-compose logs -f odoo
```

Buscar errores relacionados con `nakel_picking`, `report_picking_batch` o `_get_consolidated_lines`.

### Paso 4: Actualizar con configuración correcta

```bash
# Usar el config de producción
sudo -u odoo odoo -c /etc/odoo/odoo.conf -u nakel_picking -d master_18 --stop-after-init
```

---

## 4. Cambios aplicados (v18.0.1.2.0)

1. **Fallback a move_ids** (`models/stock_picking_batch.py`): Si los pickings no tienen `move_line_ids` (operaciones detalladas), ahora se usan `move_ids` para generar la sección "Productos Consolidados". Así el reporte muestra datos aunque no se haya hecho "Comprobar disponibilidad".

2. **Secuencia en tabla de traslados** (`reports/stock_picking_batch_report.xml`): La columna "Secuencia" ahora muestra 1, 2, 3... en lugar de 0, 1, 2...

### Cómo desplegar los cambios en producción

1. Copiar el módulo actualizado a `/usr/lib/python3/dist-packages/odoo/addons/nakel_picking/`
2. Actualizar con config correcta:
   ```bash
   sudo -u odoo odoo -c /etc/odoo/odoo.conf -u nakel_picking -d master_18 --stop-after-init
   ```
3. O desde la interfaz: Aplicaciones → Nakel Picking → Actualizar

---

## 5. Olas/lotes muy grandes (PDF 1000+ páginas): posibles causas y mitigaciones

### Observación

En olas extremadamente grandes (por ejemplo, reportes de **1500 páginas**), pueden aparecer **diferencias entre el “digital” (preview/descarga desde Odoo) y el resultado impreso**: páginas incompletas, saltos raros o elementos que “no salen” al imprimir.

### Lo que hace este módulo (y lo que NO hace)

- **Consolidación (Python)**: `_get_consolidated_lines()` recorre movimientos del batch y **acumula** cantidades. La salida se **ordena** antes de pasar a QWeb.
- **Render (QWeb → HTML → PDF)**: el template genera **mucho HTML** (y muchos `<img>` base64) y luego Odoo lo convierte a PDF con **wkhtmltopdf**.
- **Importante**: si hay diferencias “a veces sí / a veces no” en olas enormes, suele ser más consistente con **limitaciones de wkhtmltopdf / recursos / impresión**, no con lógica de consolidación (que es determinista).

### Causas probables (ordenadas por frecuencia/impacto)

1. **wkhtmltopdf bajo estrés (memoria/tiempo)**:
   - HTML gigante + muchas imágenes base64 → alto consumo de RAM/CPU.
   - En algunos escenarios, wkhtmltopdf puede **fallar o truncar** el resultado (a veces sin un error “claro” en UI).

2. **Workers/timeouts de Odoo**:
   - Renderizar 1000+ páginas puede exceder límites de tiempo o memoria del worker.
   - Si el worker se recicla/reinicia, el PDF puede salir incompleto o la descarga puede ser inconsistente.

3. **Entorno de impresión (spooler/driver/viewer)**:
   - Un PDF enorme puede “imprimirse distinto” según visor (Chrome, Evince, Acrobat) y driver.
   - El preview digital puede verse bien, pero el spool de impresión puede cortar/rasterizar distinto bajo carga.

4. **wkhtmltopdf “unpatched qt”**:
   - No suele “saltar líneas”, pero sí rompe header/footer y paginación; además es señal de un entorno PDF no soportado por Odoo.
   - Ver `upgradewkhtmltopdf.md`.

### Verificaciones rápidas recomendadas (para confirmar hipótesis)

- **A. Confirmar integridad del PDF**: descargar el PDF, verificar cantidad de páginas y revisar si el “faltante” ya está en el archivo (antes de imprimir).
- **B. Probar distintos visores**: imprimir el mismo PDF desde 2 visores distintos (por ejemplo, Chrome vs Evince/Acrobat) y comparar.
- **C. Revisar logs al generar el PDF**: buscar warnings/errores de wkhtmltopdf o tiempos excesivos durante el render.

### Mitigación recomendada (mejor relación riesgo/beneficio): “chunking” (imprimir por partes)

La estrategia más robusta es **no generar un único PDF monstruoso**:

- **Imprimir por lotes internos**: dividir `picking_ids` del batch en “chunks” (ej. 50/100/200 pickings o un objetivo de ~200 páginas por PDF).
- **Generar varios PDFs** (Parte 1/N, Parte 2/N, …) y:
  - descargarlos por separado, o
  - opcionalmente **unirlos** en servidor (si se decide incorporar un merge, con librería tipo pypdf).

Ventajas:
- baja el pico de RAM/CPU por render
- reduce probabilidad de timeouts/reciclado de workers
- reduce problemas de spool/driver al imprimir
- hace más fácil reimprimir solo una parte si falla

Trade-offs:
- si el “Productos Consolidados” debe ser global, hay que decidir:
  - **Consolidado global solo en el primer PDF** (y el resto solo “Traslados”), o
  - **Consolidado por chunk** (útil operativamente si se recolecta por partes), o
  - **Un PDF “Consolidado” separado** + PDFs de “Traslados” por chunk.

### Mitigaciones adicionales (complementarias)

- Reducir peso del HTML/PDF:
  - evitar generar códigos de barras repetidos si no agregan valor operativo para olas gigantes
  - cachear/rehusar imágenes de barcode (si se repiten valores)
- Asegurar wkhtmltopdf con **patched Qt** y revisar `report.url` (assets).
