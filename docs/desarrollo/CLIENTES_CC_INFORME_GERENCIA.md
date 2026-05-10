# Módulo `clientes_cc_informe` — Detalle CC clientes (gerencia)

**Ubicación código:** `nakel_odoo/addons/clientes_cc_informe/` (`__manifest__.py` en la raíz del directorio, misma convención que `clientes_cc_detalle`).  
**Odoo:** 18.  
**Depende de:** `clientes_cc_detalle` (reutiliza vistas lista/pivote/gráfico de FC/NC).

## Objetivo

Pantalla y PDF para **gerencia y administración**: ver **todas** las facturas y notas de crédito de cliente publicadas, **sin** limitar por `invoice_user_id = uid`, con filtros por fechas, vendedor, cliente opcional y saldo pendiente.

La semántica de saldo sigue siendo la de Odoo: **`amount_residual`** / estado de pago sobre asientos publicados (pagos y NC ya impactan vía contabilidad).

## Grupo de seguridad

| XML ID | Nombre en UI |
|--------|----------------|
| `clientes_cc_informe.group_cc_informe_gerencia` | **Nakel: informes CC clientes (gerencia)** |

- **ACL:** lectura/escritura ligera sobre `account.move` y `account.move.line` (misma filosofía que `clientes_cc_detalle` para evitar errores de chatter al abrir facturas).
- **`ir.rule`:** solo movimientos **`out_invoice` / `out_refund`** en estado **`posted`**, con filtro de compañía coherente con el usuario.

Quien también tenga **`sales_team.group_sale_salesman`** sigue sujeto a la regla de `clientes_cc_detalle` (solo “mis ventas”); la regla de informe se **combina en OR** con la de vendedor, por lo que **no se reduce** el alcance para documentos de otros comerciales.

## Menú

**Ventas → Órdenes → Informe de cuentas corrientes clientes** (secuencia 46, inmediatamente después de *Cuentas corrientes (mis ventas)*).

Visibilidad del ítem: **`base.group_system`** y el grupo **gerencia** del módulo.

## Asistente (modelo transitorio `clientes.cc.informe.wizard`)

### Título en pantalla y registros temporales

El asistente es un **`TransientModel`**: cada vez que entrás al menú, Odoo crea un **registro nuevo** con id 4, 5, 6… Eso **no** guarda un historial de informes ni “llena el disco” de reportes: son filas **temporales** que el **autovacuum** (`Base: Auto-vacuum internal data`) **borra** al cabo de un tiempo (orden de horas/días según versión y carga). **No debería crecer sin límite** en operación normal.

El **título** visible usa el campo **`name`** (`_rec_name`) con el texto **Informe de cuentas corrientes clientes**, para no mostrar el nombre técnico del modelo en la miga de pan.

### Filtros

| Campo | Uso |
|--------|-----|
| **Rango de fechas (factura)** | **Desde** / **hasta** sobre `invoice_date` (cualquiera vacío = sin límite en ese extremo; ambos vacíos = sin filtro por fecha). |
| **Vendedor** | `invoice_user_id` (vacío = todos). |
| **Cliente** | Entidad comercial (`commercial_partner_id`). Vacío = todos. El desplegable usa **`allowed_partner_ids`** (almacenado): con vendedor, solo entidades con FC/NC **publicadas** y **`invoice_user_id`** = ese vendedor (misma compañía); sin vendedor, entidades que aparecen en FC/NC publicadas de la compañía. Así el buscador ya no mezcla “todo el padrón” cuando hay comercial elegido. |
| **Solo con saldo pendiente** | Por defecto activo; restringe a `payment_state` en `not_paid` / `partial`. |

### Resumen y vista previa

- **Total documentos**, **Cobrado / aplicado** y **Adeudado** se calculan sobre la **vista previa** (suma de importes firmados y residuales de los movimientos listados).
- En listas **embebidas** dentro del formulario, Odoo a veces **no muestra** la suma al pie de columna (aparece “—”); por eso los mismos totales se repiten bajo la grilla y en **Resumen**.
- La **tabla** se **actualiza sola** al **abrir** el informe, al **guardar** el formulario y al **cambiar filtros** (onchange). Botón **Actualizar vista** por si hace falta forzar.

### PDF y Excel

- **Exportar a PDF** en cabecera y pie (el informe QWeb no se publica en el menú Acción / tuerca). El PDF va **agrupado por cliente**: resumen global, luego un bloque por entidad comercial (ordenado por **mayor saldo** en el informe) con mini-resumen y tabla de documentos sin repetir el nombre del cliente en cada fila; la columna **Vendedor** en el detalle solo aparece si el filtro no fija un vendedor.
- **Exportar a Excel:** si en el servidor está instalado **`xlsxwriter`** (`pip install xlsxwriter`), la descarga es **.xlsx** con dos hojas: **Detalle** (listado plano + resumen global al pie) y **Por cliente** (mismo criterio que el PDF: bloques por entidad comercial con subtotal de comprobantes, total firmado y saldo, luego líneas sin repetir el nombre del cliente; orden de clientes por **mayor saldo**). Cabecera de filtros en ambas hojas. Si el filtro ya fija un vendedor, la columna «Vendedor» no se repite en el detalle. Sin `xlsxwriter`, el **.csv** sigue siendo solo el detalle plano y totales al final.

### Otras acciones

- **Abrir en ventana completa:** `account.move` con el mismo dominio; pivote por defecto agrupado por **vendedor** y **cliente comercial**.

## Despliegue

1. Copiar/actualizar el addon en `addons_path`.
2. Actualizar lista de aplicaciones e instalar **Nakel - Detalle CC clientes (gerencia)** (carpeta del addon: `clientes_cc_informe`; actualizar con `-u clientes_cc_informe` cuando corresponda). Si en una base antigua el módulo figuraba con otro nombre de carpeta (p. ej. con guión), puede hacer falta alinear `addons_path` y el nombre en `ir_module_module` o reinstalar el módulo tras respaldo.
3. Asignar el grupo **Nakel: informes CC clientes (gerencia)** a usuarios de gerencia/administración que deban el menú (los administradores del sistema ya ven el ítem por `base.group_system`).

### Si **Instalar** desde Apps falla con `LockNotAvailable` / lock timeout

La traza en `ir.module.module` → `check_foreign_keys` → `add_foreign_key` indica que **PostgreSQL** no pudo tomar el bloqueo a tiempo (`lock_timeout`), suele por **uso concurrente** (UI, cron, otros workers), no por un fallo del código del módulo.

- **Primera instalación:** con el servicio Odoo **totalmente detenido** (incl. workers si hay varios procesos), ejecutar  
  `odoo -c /etc/odoo/odoo.conf -d <base> -i clientes_cc_informe --stop-after-init`  
  (no basta `-u` si el módulo aún no está `installed`).
- En horario de mucha carga, la UI suele seguir fallando; repetir en ventana de bajo uso o revisar sesiones bloqueantes en PostgreSQL. Misma pauta documentada en `nakel_odoo/addons/Documentacion/l10n_ar_edi_ux.md` (incidencia LockNotAvailable).

## Relación con `clientes_cc_detalle`

| Módulo | Audiencia | Alcance `account.move` |
|--------|-----------|-------------------------|
| `clientes_cc_detalle` | Preventistas / CC “mis ventas” | `invoice_user_id = usuario` (+ reglas vendedor). |
| `clientes_cc_informe` | Gerencia / administración | FC/NC publicadas de la compañía (según reglas del módulo). |

---

*Documento creado para el vault FWCORP / NAKEL; alinear con cambios de permisos en `usuarios/PERMISOS/` si el grupo 102 u otros perfiles se ajustan.*
