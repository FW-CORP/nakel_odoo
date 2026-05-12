# Informe de actividades — Abril 2026 (Nakel / FWCORP)

**Período:** 2026-04-01 a 2026-04-30  
**Alcance:** trabajo registrado en el vault `nakel_odoo` (documentación, addons, herramientas, incidentes) y **commits Git** del repositorio `nakel_odoo` en abril — incluido el **rollout / actualización de plataforma a Odoo 18 Enterprise** (despliegue, validación y estabilización), que concentró una parte muy grande del esfuerzo del mes.  
**Nota:** muchas tareas pasaron por sesiones de Cursor u otros canales; este informe refleja **lo que quedó trazable en el repo**. Para un cierre contable “100% exhaustivo”, complementar con tickets internos, correos o bitácora de despliegues fuera del vault.

### Horas estimadas (metodología)

- Las columnas **«h est.»** son **órdenes de magnitud** (investigación + doc + código + pruebas + deploy), **no** horas cargadas en un timesheet.
- Donde hay **solapamiento** (p. ej. un mismo bloque de commits cubre varias filas), el **§11** resume por **área** para no inflar el total.
- Si necesitás **horas reales**, reemplazar estas celdas con datos de Jira/Linear/Harvest o bitácora interna.

---

## 1. Resumen

| Área | Qué se hizo (alto nivel) | h est. (área) |
|------|---------------------------|---------------|
| **Inventario / logística** | Análisis de picks atorados Central; incidentes Barcode/olas; mejoras PDF de lotes (`nakel_picking`); documentación SYNC olas. | **37** |
| **Ventas / precios / PDV** | Inyección preventas abril; listas de precios y costos (snapshot API); PDV listas -FIX; comisiones preventistas (reporte y XLSX abril); `nak-ventas`. | **31** |
| **Usuarios y permisos** | Preventistas: informes CC, `ir.rule` y `implied_ids` (varias iteraciones 11–13 abr); encargados: política y scripts (18 abr). | **20** |
| **Contabilidad / AFIP / retenciones** | Informe error AFIP 10016 / secuencia NC RG5329; IIBB sufrido liquidación (`get_pos_and_number`); toolkit ARCA retenciones; bloque `fix-facom` (liquidaciones / análisis). | **33** |
| **Infra / repo / deploy** | **Rollout Odoo 18 EE** (paquete, SO, addons, `-u`, smoke y post-deploy); pre-update §8; **bootstrap Git 27–29 abr** (solapa con §3/§7; ver §9). | **60** |
| **QWeb / facturación PDF** | Actualización documentada (abril 2026): QR AFIP en PDF Odoo 18 (`/report/barcode/…`). | **5** |

---

## 2. Incidentes y análisis operativos (abril)

| Fecha (doc) | Tema | Referencia | h est. |
|-------------|------|------------|--------|
| 2026-04-27 | Picks no finalizados hacia `CEN/Salida` y `CEN/OUT` (361 + 2 en muestra); acumulación desde ~02-abr | `docs/ventas/inventario/ANALISIS_PICKS_ATORADOS_CEN_SALIDA_OUT_MASTER_DEV.md` | **4** |
| 2026-04-29 | Barcode: “Registro faltante” por `stock.move.line` borrada; concurrencia / re-reserva; mitigación y variante `stock.move` | `docs/incidentes/BUG_BARCODE_REGISTRO_FALTANTE_stock_move_line_borrada_master_dev_2026-04-29.md` | **3** |
| 2026-04-29 | Upgrade `nakel_wave_picking_link`: error en vista OV (`action_nakel_open_wave`); causas deploy/`addons_path`; `rsync --delete` | `docs/incidentes/NAKEL_wave_picking_link_upgrade_OV_smartbuttons_2026-04-29.md` | **6** |
| Abril 2026 | AFIP 10016 / desfasaje NC A vs Odoo; subsanación y herramienta `sync_latam_sequence_xmlrpc.py` | `docs/incidentes/INFORME_AFIP_10016_SECUENCIA_NC_RG5329.md` | **8** |
| (doc sin día único) | IIBB sufrido: `AttributeError` en liquidación por `withholding_id.name` vacío; parche addon Nakel | `docs/incidentes/IIBB_SUFRIDO_LIQUIDACION_WITHHOLDING_NAME_master_dev.md` | **5** |

**Bug report interno (addon):** Barcode flag “picked” inconsistente — `addons/nakel_fix_pick/docs/BUGREPORT_BARCODE_PICKED_FLAG_master_dev_2026-04-23.md`. **h est.: 3**

---

## 3. Desarrollos y cambios en addons (abril)

### 3.1 `nakel_picking` (PDF lote / wave)

Versiones documentadas en changelog con fecha **2026-04-01** y **2026-04-22**:

- **18.0.1.18.1 (2026-04-01):** saltos de página en PDF de lote (tablas por fila, `page-break`); secciones por ruta. **h est.: 6**
- **18.0.1.18.2–18.0.1.18.5 (2026-04-22):** pie con referencia wave + paginación; columna PLU en consolidados; uso de `product.barcode` vs `default_code` con fallback; imagen Code128 para PLU. **h est.: 8**

Fuente: `addons/nakel_picking/CHANGELOG.md`.

### 3.2 `nakel_fix_pick` (Barcode)

- **2026-04-29 (Git):** recuperación suave ante `MissingError` en Barcode (`feat(nakel_fix_pick): … 18.0.1.0.2` en historial de abril). Documentación asociada en incidente Barcode (misma fecha). **h est.: 5**

### 3.3 `nakel_wave_picking_link` y despliegue

- Documentación de incidente y despliegue (29-abr); referencia cruzada en `docs/DEPLOY.md` y `docs/pre_update/checklist.md`. **h est.: 2** *(parcial; el grueso del incidente está en §2)*

---

## 4. Documentación funcional — ventas y listas (abril)

| Tema | Referencia | h est. |
|------|------------|--------|
| Inyección CSV preventas → cotizaciones Odoo (`master_dev`), mapeos abril | `docs/ventas/inyeccion-ventas-abril/README_INYECCION_ABRIL.md` (últ. act. 2026-04-02) | **8** |
| Estructura costos y listas 1/2 en `master_dev` (lectura API) | `docs/ventas/Listas de precios/ESTRUCTURA_COSTOS_Y_LISTAS_1_2_MASTER_DEV.md` (2026-04-07) | **5** |
| Listas precios vs impuestos | `docs/ventas/Calculo-costos-impuestos/ODOO_LISTAS_PRECIOS_VS_IMPUESTOS.md` (registro 2026-04-03) | **2** |
| PDV listas -FIX (referencia abril 2026) | `docs/ventas/pdv-listas/README.md` | **3** |
| Comisiones preventistas: parámetros, auditoría API 25-abr, comandos cierre **2026-04-01 → 2026-04-25** | `docs/ventas/repote-comisiones/REPORTE_COMISIONES_MASTER_DEV.md` | **6** |
| Mapeo preventas MSSQL ↔ Odoo (enlace a inyección abril) | `docs/ventas/Pre-ventas-inyeccion/MAPEO_PREVENTAS_MSSQL_MASTER18.md` | **1** *(documentación; el esfuerzo de inyección está arriba)* |

---

## 5. Usuarios, permisos y roles (abril)

| Tema | Referencia | h est. |
|------|------------|--------|
| Preventistas: informes CC, `account.group_account_readonly`, menús; **aplicado 2026-04-11**; evolución reglas **2026-04-11 a 2026-04-13** | `docs/usuarios/PERMISOS/PERMISOS_PREVENTISTAS_INFORMES_CC_MASTER_DEV.md` | **12** |
| Encargados: estado objetivo **2026-04-18**, scripts y política Belgrano | `docs/usuarios/PERMISOS/RESUMEN_PERMISOS_ENCARGADOS.md`, `docs/usuarios/documentacion/ENCARGADOS_SUCURSALES.md` | **4** |
| Permisos encargados ventas/almacén (últ. act. 2026-04-05) | `docs/usuarios/PERMISOS/PERMISOS_ENCARGADOS_VENTAS_ALMACEN_PEDIDOS.md` | **2** |
| Credenciales/IDs por base (público, **2026-04-18**) | `docs/usuarios/documentacion/CREDENCIALES_Y_IDS_POR_BASE.PUBLIC.md` | **1** |
| Índice usuarios actualizado **2026-04-12** | `docs/usuarios/INDICE.md` | **1** |

---

## 6. QWeb / reportes factura (abril)

- Documentación QWeb sobre **modificaciones en PDF de facturas** (abril 2026: QR AFIP, endpoint `/report/barcode/`, `quote_plus`); detalle en `qweb/documentacion/` — **h est.: 4**  
- Resumen en `qweb/README.md` (actualización abril 2026; última actualización doc **2026-04-01**). — **h est.: 1**

---

## 7. Herramientas (`tools/`) — trabajo documentado en abril

| Bloque | Contenido típico | Referencia / fechas en doc | h est. |
|--------|-------------------|-----------------------------|--------|
| **ARCA retenciones** | Quincenas ejemplo abril 2026, SICORE/SIRCAR/PERCEIIBB | `tools/arca-retenciones/ARCA-RETENCIONES/**/*.md` (`updated: 2026-04-20` a `2026-04-28`) | **12** |
| **fix-facom** | Runbook productivo, incidente liquidación IIBB, análisis campos | `tools/fix-facom/**/*.md` (`updated: 2026-04-25`–`28`) | **8** |
| **nak-ventas** | Herramienta NAK draft → stock Roturas2 (añadida con la ola de docs fin abril) | Commit `4493a14` (2026-04-27) | **6** |

---

## 8. Rollout Odoo 18 y preparación de entorno (abril)

### 8.1 Rollout / nueva versión de Odoo (Enterprise 18)

En **abril 2026** se llevó adelante el **despliegue (rollout) a Odoo 18 Enterprise** en el entorno Nakel (`nakel.net.ar`, base `master_dev` / productiva), con el paquete típico de trabajo de plataforma:

- Coordinación de **ventana de cambio**, comunicación a usuarios y **plan de vuelta atrás** (snapshot / backup según política).
- Actualización del **stack del servidor**: `apt` / dependencias, **paquete Odoo `.deb`**, reinicios de servicio en orden seguro.
- Alineación de **`addons_path`**, módulos **custom Nakel** y **`odoo.conf`**; upgrades **`-u`** selectivos donde hacía falta tras el salto de versión.
- **Pruebas de humo** (ventas, stock/almacén, facturación, POS si aplica, localización AR / AFIP) y **seguimiento post-deploy** (regresiones, assets web, PDF/wkhtmltopdf según checklist).
- Incidentes y ajustes posteriores ligados al salto de versión (p. ej. módulos que cambian comportamiento en 18, vistas/JS, permisos) — parte de ese esfuerzo aparece también en §2 y §3.

Referencias en vault: `docs/pre_update/checklist.md`, `docs/pre_update/rollupdate_pasos.md`, `docs/pre_update/ubuntu_update.md`, `docs/DEPLOY.md`.

**h est. (rollout + estabilización en abril): 48**

### 8.2 Checklist, relevamientos e inventario técnico

| Tema | Referencia | h est. |
|------|------------|--------|
| Checklist pre-update (incluye `nakel_wave_picking_link`) | `docs/pre_update/checklist.md` | **2** |
| Listado mover a custom (relevamiento **2026-04-28**) | `docs/pre_update/Listado_mover_a_custom.md` | **3** |
| Análisis dev vs producción (**~2026-04-22**) | `docs/pre_update/Analisis_deB_vs_produccion.md` | **4** |
| Demanda vs negativos CEN | `docs/inventario/ANALISIS_DEMANDA_VS_NEGATIVOS_CEN_MASTER_DEV.md` (presente en repo; cruzar fecha si se precisa informe legal) | **3** |

---

## 9. Commits Git en `nakel_odoo` (abril 2026)

El repositorio muestra actividad concentrada **del 27 al 29 de abril** (bootstrap del monorepo y primera ola de documentación/herramientas):

- Esqueleto inicial, addons `master_dev`, unificación `deploy`, documentación usuarios/ventas, `arca-retenciones`, `fix-facom`, `nak-ventas`, saneamiento credenciales, snapshot addons-Prod.
- **2026-04-29:** docs incidentes wave/Barcode, `nakel_fix_pick` MissingError, README raíz.

**Horas (calendario Git, solapadas con §3–§8):** el bloque **27–29 abr** se estima en **~22 h** de corrida intensiva (migración + paquetes + doc); **no sumar** al total del §11 si ya se contabilizó el mismo trabajo en filas anteriores.

| Fecha | Agrupación | h est. |
|-------|------------|--------|
| 2026-04-27 | Skeleton, addons, deploy, tools, docs masivos | **14** |
| 2026-04-28 | Ajustes / “actualizaciones de cosas” | **2** |
| 2026-04-29 | Incidentes + `nakel_fix_pick` + README + snapshot | **6** |

Listado completo (una línea por commit):

```text
80ea042|2026-04-29|feat(nakel_fix_pick): recuperación suave MissingError Barcode (18.0.1.0.2)
d57b583|2026-04-29|docs(incidentes): variante stock.move y mitigación al salir de Barcode
0a1aea1|2026-04-29|docs: enlazar incidentes desde README raíz
076e4fb|2026-04-29|docs+wave: incidente upgrade OV, deploy espejo, inventario y 18.0.1.0.6
c572a5d|2026-04-29|chore: snapshot addons-Prod y herramientas
66079aa|2026-04-28|actualizaciones de cosas
3573ca5|2026-04-27|docs: migración progresiva a nakel_odoo; repos legacy obsoletos
5a13d32|2026-04-27|docs: fuente de verdad = repo nakel_odoo (tools/nak-ventas)
4493a14|2026-04-27|feat(tools): add nak-ventas (NAK draft → stock Roturas2)
a5d576d|2026-04-27|chore(security): remove hardcoded Odoo credentials
21572a4|2026-04-27|feat(tools): add fix-facom productive runbook and scripts
9b9d247|2026-04-27|chore(tools): remove binary artifacts from arca-retenciones
7d6e8cf|2026-04-27|feat(tools): add arca-retenciones (sanitized)
abdb933|2026-04-27|docs(ventas): add sales workflows documentation (sanitized)
5ce2d0f|2026-04-27|docs(usuarios): add permissions and roles documentation
dea2286|2026-04-27|chore(deploy): unify addon deployment scripts
3ee0afe|2026-04-27|feat(addons): add master_dev Nakel modules
aeea036|2026-04-27|chore: initial nakel_odoo skeleton
```

---

## 11. Total por área (solo §1; evita doble conteo con §9)

| Área | h est. |
|------|--------|
| Inventario / logística | 37 |
| Ventas / precios / PDV | 31 |
| Usuarios y permisos | 20 |
| Contabilidad / AFIP / retenciones | 33 |
| Infra / repo / deploy | 60 |
| QWeb / facturación PDF | 5 |
| **Subtotal** | **186** |

**Cruce con §2–§8 (suma de filas / bloques detallados):** \(29 + 21 + 25 + 20 + 5 + 26 + 48 + 12 = 186\) h — incluye **48 h** del **§8.1 rollout Odoo 18** más **12 h** del **§8.2** checklist/relevamientos.

Interpretación: **~23 jornadas de 8 h** de trabajo de ingeniería, plataforma y documentación **según evidencia en repo** (orden de magnitud). Ajustar cifras cuando haya timesheet real.

**Versión PDF (misma carpeta):** `INFORME_ACTIVIDADES_ABRIL_2026.pdf` — regenerar con  
`tools/reports/.venv_pdf/bin/python tools/reports/render_informe_abril_pdf.py`  
(primer uso: `python3 -m venv tools/reports/.venv_pdf && tools/reports/.venv_pdf/bin/pip install fpdf2 markdown`).

**Elaborado:** 2026-05-11 (Markdown + PDF desde el vault `nakel_odoo`).
