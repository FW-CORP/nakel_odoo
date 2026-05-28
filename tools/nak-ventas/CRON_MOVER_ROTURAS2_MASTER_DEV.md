# Cron Odoo: mover cotizaciones «procesar» → Roturas 2 (CEN/NAK + B3)

**Base:** producción / `master_dev` (https://nakel.net.ar)  
**Objetivo:** ejecutar automáticamente el mismo flujo que el script manual, pero **dentro del servidor Odoo** (acción planificada / `ir.cron`).

- **Perfil CEN:** cotizaciones **NAK** (`company_id=2`) → traslado `CEN/Existencias` → `CEN/Roturas 2` en Nakel SA.
- **Perfil B3:** cotizaciones **Nakel SA** Belgrano 3 (`warehouse_id=17`) → `B3/Existencias` → `B3/Roturas 2`.
- **Política:** **demanda completa** (mueve todo lo pedido; el origen puede quedar negativo).
- **Etiquetas:** quita `procesar`, agrega `ProcesadaNN` (aunque no haya stock que mover).

Relacionado:

- Script manual: [MOVER_DISPONIBLE_PEDIDOS_A_ROTURAS2_MASTER_DEV.md](MOVER_DISPONIBLE_PEDIDOS_A_ROTURAS2_MASTER_DEV.md)
- **Código para pegar en Odoo:** [cron_code/mover_roturas2_accion_planificada.py](cron_code/mover_roturas2_accion_planificada.py)
- Desecho posterior en Roturas 2: [CRON_DESECHO_ROTURAS2_MASTER_DEV.md](CRON_DESECHO_ROTURAS2_MASTER_DEV.md)

---

## Ventaja vs cron en tu PC

| | Cron PC local | Acción planificada Odoo |
|---|---------------|-------------------------|
| Depende de la PC encendida | Sí | **No** |
| Credenciales XML-RPC | Sí (`config_nakel.py`) | **No** (usa `env` del servidor) |
| Horario exacto | `crontab` del SO | `ir.cron` de Odoo |
| Logs | archivo local | log de Odoo / chatter del cron |

Si activás el cron en Odoo, **desactivá** el de tu PC para no duplicar:

```bash
crontab -e
# comentar o borrar la línea run_mover_roturas2_cron.sh
```

---

## Crear la acción planificada (UI Odoo)

Modo **desarrollador** activado.

1. **Ajustes → Técnico → Automatización → Acciones planificadas**.
2. **Nuevo**.
3. Completar:

| Campo | Valor sugerido |
|-------|----------------|
| **Nombre** | `Mover cotizaciones procesar → Roturas 2 (CEN + B3)` |
| **Activo** | ✅ |
| **Usuario** | Técnico con Inventario + Ventas (ej. `NakelBot`) |
| **Modelo** | `Transferencia` (`stock.picking`) |
| **Ejecutar cada** | `1` **días** |
| **Siguiente ejecución** | Próximo dom/mié/vie a las **22:00** (hora del servidor Odoo) |
| **Número de llamadas** | `-1` (ilimitado) |
| **Acción a realizar** | **Ejecutar código Python** |

4. Pegar el código desde el archivo indicado abajo.
5. Guardar. Probar con **Ejecutar manualmente** la primera vez.

> **Horario dom/mié/vie:** programar el cron **todos los días a las 22:00**. El código filtra con `RUN_WEEKDAYS = (6, 2, 4)` (dom/mié/vie).

> **Zona horaria:** Odoo usa la TZ del servidor / compañía.

---

## Código Python — archivo fuente

**No copiar desde este README.** Usar el archivo:

```
nakel_odoo/tools/nak-ventas/cron_code/mover_roturas2_accion_planificada.py
```

En el vault también está en:

```
tools/nak-ventas/cron_code/mover_roturas2_accion_planificada.py
```

### Cómo pegar en Odoo (paso a paso)

1. Abrí **`mover_roturas2_accion_planificada.py`** en el editor (Cursor / VS Code).
2. **Ctrl+A → Ctrl+C** (copiar todo el archivo).
3. En Odoo, cuadro **Ejecutar código Python**: **Ctrl+A → Delete** (borrar todo, incluidos comentarios grises de ayuda).
4. **Ctrl+V** pegar.
5. **Borrá solo las líneas que empiezan con `#`** al inicio del archivo (comentarios de instrucciones; Odoo las tolera pero es más limpio sin ellas).  
   **O** dejá los `#` — no molestan.
6. **Verificá** que la primera línea ejecutable sea exactamente:

   ```python
   COMPANY_STOCK = 1
   ```

   Si ves `OMPANY_STOCK = 1` (sin **C**), el pegado truncó el inicio → corregí a mano o volvé a copiar desde el `.py`.

7. Guardar en Odoo → **Ejecutar manualmente**.

Para copiar desde terminal (solo líneas sin `#`):

```bash
grep -v '^#' /media/klap/raid5/cursor_files/nakel/nakel_odoo/tools/nak-ventas/cron_code/mover_roturas2_accion_planificada.py | grep -v '^[[:space:]]*$'
```

(Pegá esa salida en Odoo.)

### Probar un día cualquiera

En el `.py`, cambiá temporalmente:

```python
RUN_WEEKDAYS = (0, 1, 2, 3, 4, 5, 6)
```

Volvé a `(6, 2, 4)` cuando termines de probar.

---

## Reglas del sandbox Odoo (`safe_eval`)

| Prohibido | Usar en su lugar |
|-----------|------------------|
| `import ...` | `datetime` ya inyectado por Odoo |
| `lambda` / `def` internas | código plano |
| `record.campo = valor` | `record.write({"campo": valor})` |
| `return` a nivel módulo | `log(...)` |

### Errores típicos

| Error | Causa |
|-------|--------|
| `NameError: name 'COMPANY_STOCK' is not defined` | Primera línea truncada: `OMPANY_STOCK` en vez de `COMPANY_STOCK` |
| `SyntaxError ... )ased on specific precision` | Comentarios de ayuda de Odoo pegados al final |
| `forbidden opcode ... IMPORT_NAME` | Líneas `import` |
| `forbidden opcode ... STORE_ATTR` | Asignación directa a campo de registro |

---

## Si el sandbox sigue bloqueando

Alternativas que **sí funcionan**:

1. **Cron en tu PC:** `tools/nak-ventas/scripts/run_mover_roturas2_cron.sh`
2. **Script manual:** `scripts/mover_disponible_pedidos_a_roturas2_master_dev.py --apply --mover-demanda-completa`
3. **Módulo Odoo** con método Python normal (sin sandbox) — opción robusta a mediano plazo

---

## Validación

1. Etiquetar una cotización de prueba con `procesar` (sin `ProcesadaNN`).
2. Acción planificada → **Ejecutar manualmente**.
3. Revisar:
   - **Inventario → Transferencias** con `origin` `S0xxxx -> Roturas2 (mover demanda)`.
   - Cotización: `ProcesadaNN` sí, `procesar` no.
   - Stock en `CEN/Roturas 2` o `B3/Roturas 2`.
4. Logs del servidor Odoo / `ir.logging`.

---

## Riesgos / notas

- Puede dejar **negativo** `CEN/Existencias` / `B3/Existencias`.
- Productos con **lote/serie** ambiguos pueden devolver **wizard** → se loguea warning y se salta esa orden.
- **No duplicar** con cron PC ni ejecuciones manuales simultáneas.
- IDs `warehouse_id=17`, tags `procesar` / `ProcesadaNN`: verificar en cada base.
- Complemento: [CRON_DESECHO_ROTURAS2_MASTER_DEV.md](CRON_DESECHO_ROTURAS2_MASTER_DEV.md).

---

## Resumen rápido

1. Crear acción planificada en Odoo.
2. Pegar código desde **`cron_code/mover_roturas2_accion_planificada.py`**.
3. Verificar **`COMPANY_STOCK = 1`** al inicio.
4. **Ejecutar cada 1 día** a las **22:00**; el código filtra dom/mié/vie.
5. Desactivar cron local si migrás a Odoo.
