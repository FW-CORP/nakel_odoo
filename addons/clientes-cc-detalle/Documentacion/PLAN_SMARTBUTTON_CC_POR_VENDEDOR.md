# Plan: smart button «Cuenta corriente (mis ventas)» en contacto — preventistas

**Alcance:** planificación e implementación por etapas.  
**Addon:** `clientes-cc-detalle`  
**Base de referencia:** `master_dev` (Odoo 18 Enterprise), consulta MCP **2026-05-02**.

### Alcance por etapa

| Etapa | Prioridad | Contenido |
|--------|-----------|-----------|
| **1 — Urgente** | Ahora | Smart button en **contacto**: cuenta corriente del cliente **solo** sobre facturas / movimientos donde el **vendedor actual** es quien generó la venta (`invoice_user_id` y criterios acordados). Sin pantalla de comisiones 40/60 aquí. |
| **2 — Después** | Backlog | **Comisiones:** panel «Mis comisiones» con detalle **40/60** (o smart button en el flujo de `sale_commission`), vista **Gerencia** al liquidar (todos los vendedores). Puede vivir en este mismo repo como submódulo o módulo hermano; ver §11. |

---

## 1. Índice vectorial del vault

La herramienta `vault_search` (Postgres/pgvector en `127.0.0.1:5439`) **no estuvo disponible** en esta sesión (*connection refused*). El contexto se tomó de los `.md` del vault en disco, en particular:

- `usuarios/PERMISOS/PERMISOS_PREVENTISTAS_INFORMES_CC_MASTER_DEV.md` (copia espejo en `nakel_odoo/docs/usuarios/PERMISOS/…`).

Cuando el índice vuelva a estar arriba, conviene re-indexar o buscar: *preventistas*, *cuenta corriente*, *invoice_user_id*, *Partner Ledger*.

---

## 2. Permisos actuales — grupo «Vendedores - Preventistas» (`master_dev`)

### 2.1 Grupo

| Campo | Valor (consulta 2026-05-02) |
|--------|-------------------------------|
| `res.groups` **id** | **102** |
| Nombre | Vendedores - Preventistas |
| XML ID (documentado) | `nakel_perm_scripts.group_vendedores_preventistas` |
| Usuarios en el grupo (hoy) | ids: **90, 91, 103, 106, 112** (5 usuarios; el doc anterior citaba 6 — validar si hubo bajas) |

**Implied (según vault):** el grupo **102** está pensado para incluir **`account.group_account_readonly`** (id **22**), que a su vez trae reglas `account.move` / `account.move.line` con dominio **`(1,'=',1)`** → en la práctica **lectura de toda la contabilidad** legible por ese perfil, no un recorte por vendedor.

Esto **explica** el caso auditado (Chirimonti viendo PDV Belgrano en Partner Ledger): el límite «solo mis ventas» **no** se logra solo con reglas extra mientras el **22** siga aplicando ese OR global (ver Fase 2 del documento de permisos).

### 2.2 Reglas de registro sobre `res.partner` (preventistas)

| `ir.rule` id | Nombre | Grupos |
|--------------|--------|--------|
| **402** | Nakel: Preventistas — solo contactos del vendedor asignado | **102** |
| **403** | Nakel: Preventistas — proveedores (lectura stock/compras) | **102** |

**402 — idea:** el preventista ve contactos `partner_share=False` (internos) **o** clientes ligados a su usuario vía `user_id`, `parent_id.user_id`, `commercial_partner_id.user_id`, `user_ids`, su propio `partner_id`, pedidos `sale.order` donde `user_id` es él, o partners de compañías del usuario (almacén / razón social).

**403 — idea:** ampliar lectura a proveedores (`supplier_rank` o `product.supplierinfo`) con filtro de compañía, para no romper confirmación de ventas/stock.

**Consecuencia para el smart button:** si el usuario **no** puede abrir el `res.partner` del cliente (no cumple 402), no debería ver el botón o la acción debe responder **acceso denegado**. La regla **402** ya acota **qué contactos** ve; falta acotar **qué movimientos** muestra la CC si siguen teniendo **22**.

---

## 3. Objetivo Etapa 1 (contacto — cuenta corriente «mis ventas»)

- En la **ficha del contacto (cliente)**, un **smart button** que abra el **detalle de cuenta corriente** del cliente.
- **Solo** respecto de **ventas (y en lo posible cobros asociados)** que **ese vendedor** generó / facturó como comercial (`invoice_user_id` y criterios del vault).
- **No** incluir en esta etapa desglose **40/60** ni montos de comisión: eso queda para **Etapa 2** en el área de **comisiones** (vendedor + Gerencia).
- **No** debe mezclar deuda del mismo cliente por **otra sucursal / PDV / otro vendedor** si el dominio y las reglas están bien alineados.
- Quién puede abrir el contacto sigue gobernado por la regla **402** (solo clientes propios).

### 3.1 Valor operativo (Etapa 1)

El vendedor necesita ver **cuánto debe el cliente sobre sus facturas** y el **estado de cobro** (`payment_state`, residual) para gestionar la cobranza en la calle. Eso es el foco del módulo ahora.

---

## 4. Por qué no alcanza el estándar Odoo solo

- Campos típicos en `res.partner`: **`credit`** (*Total Receivable*), **`total_invoiced`**, smart buttons tipo **Customer Statement / Partner Ledger** — se alimentan del **partner a nivel contable global** (por compañía), no de un subconjunto «solo mis facturas».
- El documento de permisos (matiz técnico A.1 / A.2) ya lo dice: hace falta **vista dedicada** o **reglas en `account.move` / `account.move.line`** coherentes, y resolver el conflicto con el grupo **22**.

Por tanto el smart button propio debería abrir, por ejemplo:

- una **acción de ventana** sobre `account.move` y/o `account.move.line` con **dominio fijo** acotado al comercial y al partner; **o**
- un **informe / wizard** que calcule saldo solo desde ese subconjunto.

---

## 5. Campos clave en `master_dev` (MCP `ir.model.fields`)

### 5.1 `account.move`

| Campo | Etiqueta | Tipo | Relación |
|--------|-----------|------|----------|
| `partner_id` | Partner | many2one | `res.partner` |
| `commercial_partner_id` | Commercial Entity | many2one | `res.partner` |
| `invoice_user_id` | Salesperson | many2one | `res.users` |
| `user_id` | User | many2one | `res.users` |
| `invoice_origin` | Origin | char | — |
| `sale_order_count` | Sale Order Count | integer | — |

**Criterio alineado al vault (negocio):** filtrar facturas de cliente donde **`invoice_user_id = uid`** (y tipos `out_invoice` / `out_refund` según corresponda). Opcionalmente cruzar con **`sale.order`** por `invoice_ids` / origen si hace falta más precisión.

### 5.2 `sale.order`

| Campo | Etiqueta | Relación |
|--------|-----------|----------|
| `user_id` | Salesperson | `res.users` |
| `partner_id` | Customer | `res.partner` |
| `invoice_ids` | Invoices | `account.move` |
| `amount_total` | Total | — |

### 5.3 `res.partner` (relevantes)

| Campo | Etiqueta |
|--------|-----------|
| `user_id` | Salesperson |
| `user_ids` | Users |
| `commercial_partner_id` | Commercial Entity |
| `sale_order_ids` | Sales Order |
| `credit` | Total Receivable |
| `debit` | Total Payable |
| `total_invoiced` | Total Invoiced |

---

## 6. Diseño técnico — Etapa 1

### Fase A — UX en contacto

- Heredar la vista de formulario de `res.partner`.
- Smart button con contador opcional (importe pendiente del subconjunto o cantidad de facturas abiertas); cálculo **sin** `sudo` para el usuario final.
- `groups` del botón: **`nakel_perm_scripts.group_vendedores_preventistas`** (u otro acordado).
- Acción `ir.actions.act_window` sobre `account.move` con dominio: entidad comercial del contacto + **`invoice_user_id` = usuario actual** + tipos / estados acordados.

### Fase B — Cobros visibles (solo informativo, Etapa 1)

- En la lista de facturas alcanza **`payment_state`** y **`amount_residual`**; abrir la factura para el detalle de pagos si hace falta.
- Lista aparte de `account.payment` solo si negocio lo pide; no es obligatorio para la primera entrega.

### Fase C — Seguridad (misma prioridad que antes)

- Dominio del botón **no** sustituye reglas de modelo si se quiere impedir ver PDV por otros menús.
- Camino **2a** del doc de permisos si hay que recortar `account.move` para el grupo **102**; mientras exista **22** implied, validar riesgo residual.

### Fase D — Pruebas (Etapa 1)

- Cliente con facturas de dos vendedores → cada uno ve solo las suyas.
- Usuario **102**: sin `AccessError` en flujo normal; partners internos (402).

---

## 7. Referencias cruzadas

- Permisos e informes CC: `usuarios/PERMISOS/PERMISOS_PREVENTISTAS_INFORMES_CC_MASTER_DEV.md`
- Scripts mencionados allí: `crear_grupo_vendedores_preventistas.py`, `crear_ir_rule_partner_preventistas.py`, `habilitar_boton_estado_cliente_vendedores_master_dev.py`

---

## 8. Próximo paso (Etapa 1)

1. Cerrar **0.1 / 0.2 / 0.5** con negocio (dominio «mis ventas», NC, diarios opcionales).  
2. Implementar **smart button + acción** con dominio explícito.  
3. **Reglas** `account.move` (y líneas si aplica) alineadas al botón si se avanza en camino **2a**.

---

## 9. Tareas concretas — Etapa 1 (urgente)

Orden: **negocio → seguridad → datos → UX → pruebas**.

### Bloque 0 — Criterios (antes de codificar)

| # | Tarea | Entregable |
|---|--------|------------|
| 0.1 | Semántica «mis ventas»: ¿solo `invoice_user_id = usuario` o también fallback `sale.order.user_id`? | Acta |
| 0.2 | **NC** (`out_refund`) y notas de débito en el listado y totales. | Reglas |
| 0.3 | Lista opcional de **diarios** a excluir (retail / PDV) además del filtro por comercial. | Lista |

### Bloque 1 — Esqueleto `clientes_cc_detalle`

| # | Tarea | Entregable |
|---|--------|------------|
| 1.1 | `__manifest__.py` con dependencias **`base`, `account`, `sale`**. **No** declarar `sale_commission` en Etapa 1 (facilita mantener el alcance chico). | Módulo instalable |
| 1.2 | `security/ir.model.access.csv` solo si hay modelos propios. | CSV |
| 1.3 | Grupo del botón: **`nakel_perm_scripts.group_vendedores_preventistas`** (dependencia de módulo donde viva ese XML ID, o referencia documentada). | XML / README |

**Moldeado para Etapa 2:** dejar `models/` y `views/` con convención clara (p. ej. `res_partner_views.xml` solo contacto; carpeta `commission/` vacía o un `README` que apunte a §11) para no mezclar pantallas.

### Bloque 2 — Seguridad

| # | Tarea | Entregable |
|---|--------|------------|
| 2.1 | Documentar **22 vs 2a** en vault si cambia algo. | `.md` |
| 2.2 | Si **2a**: `ir.rule` en `account.move` (+ `account.move.line` si hace falta) para grupo **102**, misma semántica que el dominio del botón. | Data |
| 2.3 | Opcional: `account.payment` solo si hay segunda vista de cobros. | — |

### Bloque 3 — Datos (CC, sin comisiones)

| # | Tarea | Entregable |
|---|--------|------------|
| 3.1 | Helper de **dominio** reutilizable (partner comercial + usuario + tipos + `state=posted` + 0.3). | Python |
| 3.2 | Opcional: campos computados en `res.partner` para **saldo pendiente** del subconjunto (badge del smart button). | Python |
| 3.3 | Multi-moneda: usar importes en moneda de la factura o conversión acordada. | Pruebas |

### Bloque 4 — UX

| # | Tarea | Entregable |
|---|--------|------------|
| 4.1 | Smart button «**Cuenta corriente (mis ventas)**» en formulario contacto. | XML |
| 4.2 | Acción ventana `account.move`: columnas **nombre, fecha, total, residual, payment_state** (y las que pidan). | XML |
| 4.3 | Totales opcionales (facturado / pendiente) en cabecera o vista pivot **sin** campos de comisión. | XML |
| 4.4 | UX si no hay facturas o el partner no aplica. | — |

### Bloque 5 — Pruebas y doc

| # | Tarea | Entregable |
|---|--------|------------|
| 5.1 | Dos vendedores, mismo cliente → subconjuntos distintos. | Checklist |
| 5.2 | Pago parcial → `amount_residual` coherente. | Checklist |
| 5.3 | Usuario **102**, partners internos → sin regresión **402**. | Checklist |
| 5.4 | Nota en vault con flujo Etapa 1. | `.md` |

---

## 10. Matriz Etapa 1 — qué ve el vendedor

| Necesidad | Dónde |
|-----------|--------|
| Deuda del cliente **solo por mis facturas** | Lista filtrada + opcional total pendiente |
| Si está paga / parcial | `payment_state`, residual |
| **No** mezclar otro vendedor / PDV | Dominio + reglas 2.x |
| Desglose **40/60** y comisión por cobro | **Etapa 2** (§11), no en contacto |

---

## 11. Etapa 2 (backlog) — Comisiones 40/60 y Gerencia

**No forma parte del entregable urgente.** Objetivo acordado con vos:

- **Vendedor:** en el flujo de **comisiones** (p. ej. «Mis comisiones» / modelo `sale.commission.*`), un **panel o smart button** que detalle el reparto **40/60** sobre la base que use hoy el plan (`sale.commission.plan`, achievements, cobros — ver `docs/ventas/repote-comisiones/REPORTE_COMISIONES_MASTER_DEV.md`).
- **Gerencia:** misma información en **vista agregada** (todos los vendedores) para **liquidación**, con permisos de grupo dedicado (solo lectura o según política).

**Implementación sugerida cuando toque:**

- Añadir módulo **`clientes_cc_detalle_commission`** (o carpeta `commission/` en este addon con `__manifest__` que dependa de `sale_commission`) para no mezclar dependencias con Etapa 1.
- O un solo manifest con `sale_commission` en `depends` solo cuando existan las vistas Python; hasta entonces **no** activar esa dependencia.

**Sí se puede** un smart button en pantallas de comisiones en Etapa 2; el diseño exacto depende de qué vista usen hoy (`sale.commission.plan.user`, informes, etc.) y conviene una mini especificación aparte cuando arranquen.

---

## 12. Después del nuevo módulo: cerrar el «leak» del botón «Estado del cliente»

**Recomendación:** sí — **sacar del paquete preventista** lo que solo existía para ver **Estado del cliente** / libros globales del partner. Ese botón llama a **`open_customer_statement`**: muestra la **cuenta corriente contable del contacto** (toda la compañía), no «solo mis ventas». Por eso un cliente con deuda o compras en **Belgrano / PDV / otro canal** sigue apareciendo ahí; es coherente con el problema que ya documentaste en permisos.

### Qué suele habilitar ese leak

1. **`account.group_account_readonly` (22)** como *implied* del grupo **«Vendedores - Preventistas» (102)**  
   En la práctica trae reglas **`(1,'=',1)`** en `account.move` / líneas → **leen toda la contabilidad** accesible a ese perfil, no un recorte por vendedor.

2. **Vista heredada** (script `docs/usuarios/PERMISOS/habilitar_boton_estado_cliente_vendedores_master_dev.py`) que agrega el grupo **102** al atributo `groups` del botón `open_customer_statement`, para que lo vean sin Facturación.

### Pasos sugeridos (orden)

1. **Validar** que preventistas ya usan el botón **«Cuenta corriente cliente»** del módulo `clientes_cc_detalle` y que cubre el uso operativo (cobranza sobre **sus** facturas).
2. **Revertir la vista** del script de «habilitar Estado del cliente»: en ese script existe **`--rollback --apply`** para desactivar la vista `nakel_perm_scripts.res_partner_open_customer_statement_groups` (o equivalente en la base).
3. En **Ajustes → Usuarios → Grupos → Vendedores - Preventistas**: **quitar** de *Grupos heredados* **`account.group_account_readonly`** (y cualquier otro grupo contable que solo se hubiera puesto para informes/CC global), **salvo** que negocio confirme que lo necesitan para otra pantalla.
4. **Probar** con un usuario preventista: no debe ver **Estado del cliente**; sí el botón nuevo (grupo `clientes_cc_detalle.group_cc_my_sales`); abrir **sus** facturas desde la lista no debe dar `AccessError`. Si falla algo (p. ej. botón «Facturado» en contacto), ajustar **solo** lo necesario en lugar de volver a dar el 22 a todos.

### Defensa en profundidad (opcional)

- Si en alguna base quedara una vista que sigue mostrando `open_customer_statement` al 102, corregir el `groups` del botón para **no** incluir preventistas.
- Gerencia / contabilidad mantienen los grupos que correspondan para **Estado del cliente** y reportes globales.

---

### Diagnóstico AccessError «no puede modificar» con solo lectura en ACL

Por API (`ir.logging` en `master_dev`/`sg_dev1`) **suele no haber traza**: los errores de acceso del cliente no siempre se persisten ahí; hace falta **log del worker** (`odoo.log`) con `--log-level=debug_rpc` o reproducir con XML-RPC como el usuario.

Hallazgos en código Odoo 18: **`mail.thread`** puede seguir disparando rutas que llaman **`write`** en el documento (p. ej. actividades, flags internos). **`_mail_post_access = 'read'`** ayuda en mensajes, pero no cubre todo. Por eso el ACL del módulo incluye **`perm_write=1`** en `account.move` / `line` **solo** para los grupos CC/vendedor, manteniendo **`perm_create` y `perm_unlink` en 0** y las **`ir.rule`** que limitan a facturas del comercial. El **`write()`** estándar de `account.move` sigue impidiendo tocar campos críticos en asientos **publicados**.

### Vista pivote por defecto (sin configurar a mano)

El menú usa **`ir.actions.act_window`** persistida **`action_act_window_clientes_cc_my_sales`** (no solo un dict devuelto por servidor): así Odoo 18 enlaza **`ir.actions.act_window.view`** al pivote y evalúa el dominio con **`uid`**.

- **Pivote:** filas **cliente comercial**; columnas **tipo de movimiento** (factura / NC) y **mes de factura**; medidas **saldo pendiente** y **total en moneda compañía**. Contexto **`pivot_row_groupby` / `pivot_column_groupby` / `pivot_measures`** fuerza el primer render en el cliente OWL.
- **Gráfico:** barras **saldo por cliente** (orden descendente).
- **Lista:** columnas útiles (fecha, diario, importes, estado de pago).

### OwlError `total_due` undefined al abrir contacto (preventistas sin contabilidad)

Tras **quitar** `account.group_account_readonly` al grupo preventistas, `account_followup` puede seguir declarando **`total_due`** en la lista *Customer statements* o en el **`invisible`** del botón *Customer Statement* mientras los campos mostrados pasaron a **`total_all_due`**. El cliente OWL entonces falla al abrir `res.partner`.

**Mitigación en el addon (18.0.1.0.15+):** dependencia `account_followup` + `views/res_partner_account_followup_fix.xml`. El `replace` del botón *Customer Statement* debe colgar de **`base.view_partner_form`** con **prioridad 5000** (18.0.1.0.18): así corre **después** de las herencias que cuelgan del form base (Nakel ~99 + followup). El `replace` colgado solo de `account_followup.res_partner_view_form` podía quedar **antes** en el grafo y no ganarle a la vista Nakel. La lista `total_due` sigue acotada a contabilidad.

### Tablero (Spreadsheet / Dashboard)

La acción **`account.move.action_clientes_cc_open_my_sales_pivot()`** y el ítem de menú **Ventas → Órdenes → Cuentas corrientes (mis ventas)** (no bajo *Informes*, que en Odoo 18 es solo para *Responsable de ventas*) usan el mismo dominio que el smart button. En **Hoja de cálculo / Dashboard** (Enterprise) suele poder crearse un tablero que referencie la misma fuente (pivote sobre `account.move` con ese dominio) o duplicar la lógica en una celda vinculada; la ruta exacta depende de los módulos de BI instalados en cada base.

---

*Etapa 1: implementar Bloques 0–5. Etapa 2: §11 cuando negocio priorice liquidaciones y detalle 40/60 en comisiones.*
