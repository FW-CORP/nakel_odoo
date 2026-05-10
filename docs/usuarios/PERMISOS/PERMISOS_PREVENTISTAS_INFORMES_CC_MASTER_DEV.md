# Preventistas: consulta cuentas corrientes / informes contables (`account.report`)

**Base:** `master_dev` (Odoo 18 Enterprise)  
**Consulta XML-RPC:** 2026-04-11  
**Objetivo:** Un solo grupo de permisos para muchos vendedores, sin tocar código en el repositorio.

---

## Conclusión operativa

1. El bloqueo no se resuelve con **vistas** (`ir.ui.view`). El motor de informes usa **`ir.model.access`** sobre modelos `account.report` y relacionados.
2. En esta base, el acceso **solo lectura** a esos modelos ya está definido para el grupo estándar **`account.group_account_readonly`** (nombre en inglés: *Accounting / Read-only*; en español suele coincidir con *Contabilidad / Mostrar funciones de contabilidad: solo lectura*).
3. Los menús de **Partner Ledger** y **Aged Receivable** exigen explícitamente ese grupo (`groups_id` apunta a `account.group_account_readonly`).

---

## Grupo estándar a reutilizar

| Campo | Valor |
|--------|--------|
| **ID** (`res.groups`) | `22` |
| **XML ID** | `account.group_account_readonly` |
| **Nombre (UI inglés)** | `Accounting / Read-only` |
| **Hereda (`implied_ids`)** | Solo *User types / Internal User* (no arrastra Facturación ni Administrador) |

En `master_dev` había **12** usuarios con este grupo al momento de la lectura (conteo orientativo).

---

## Derechos de acceso concretos (`ir.model.access`, grupo 22)

Líneas estándar que otorgan **R=1, W=C=U=0** sobre el motor de informes (XML IDs en la base):

| XML ID (`module.name`) | Nombre técnico del acceso |
|-------------------------|---------------------------|
| `account.access_account_report_readonly` | `account.report.readonly` |
| `account.access_account_report_line_readonly` | `account.report.line.readonly` |
| `account.access_account_report_column_readonly` | `account.report.column.readonly` |
| `account.access_account_report_expression_readonly` | `account.report.expression.readonly` |
| `account.access_account_report_external_value_readonly` | `account.report.external.value.readonly` |
| `account_reports.access_account_report_horizontal_group_readonly` | `account.report.horizontal.group.readonly` |
| `account_reports.access_account_report_horizontal_group_rule_readonly` | `account.report.horizontal.group.rule.readonly` |
| `account_reports.access_account_report_budget_readonly` | `account.report.budget.readonly` |
| `account_reports.access_account_report_budget_item_readonly` | `account.report.budget.item.readonly` |

No hace falta “crear vistas”: si duplicáramos permisos para un **grupo nuevo**, habría que replicar estas líneas (o usar la estrategia de **implied** del apartado siguiente).

---

## Menús y acciones (referencia `master_dev`)

Informes útiles para saldo / vencimientos de clientes:

| Menú (`ir.ui.menu`) | Ruta aproximada | Acción |
|---------------------|-----------------|--------|
| `214` | Accounting → Reporting → Partner Reports → **Partner Ledger** | `ir.actions.client,356` → XML `account_reports.action_account_report_partner_ledger` |
| `215` | … → **Aged Receivable** | `ir.actions.client,353` → `account_reports.action_account_report_ar` |

Ambos menús llevan restricción de grupo a **`account.group_account_readonly`**.

La acción **Customer Statement** (`ir.actions.client,357`, XML `account_reports.action_account_report_customer_statement`) existe en la base; puede abrirse desde flujos del partner u otros menús según localización—el permiso de modelo sigue siendo el mismo conjunto `account.report` + readonly.

**Seguimiento:** el modelo **`account.report.send`** solo tiene acceso con grupo **`account.group_account_invoice`** (*Accounting / Invoicing*). Si tras asignar solo lectura falla el envío por correo de un estado de cuenta, el siguiente paso sería revisar ese flujo (no implica dar Facturación a todos si no lo usan).

---

## Un solo grupo para muchos vendedores (solo UI)

**Recomendado:** crear un grupo propio (ej. *Nakel — Preventistas: consulta CC*) y en **Heredados / Implied groups** incluir:

- `account.group_account_readonly`

Asignás **solo** ese grupo Nakel a los preventistas: Odoo les suma automáticamente el readonly de contabilidad y no tenés que tildar dos categorías manualmente en cada usuario.

**Alternativa** (sin grupo propio): asignar directamente **Contabilidad → Mostrar funciones de contabilidad: solo lectura** a un grupo de usuarios ya existente (si tenés un grupo “Vendedores” homogéneo).

Tras cualquier cambio de grupos: **cerrar sesión y volver a entrar** en Odoo.

---

## Script XML-RPC (grupo + implied)

`PERMISOS/crear_grupo_vendedores_preventistas.py` crea o actualiza el grupo **`Vendedores - Preventistas`** con `implied_ids` → `account.group_account_readonly`. Por defecto **solo dry-run**; con **`--apply`** persiste cambios.

```bash
cd PERMISOS
# Probar (no escribe)
python3 crear_grupo_vendedores_preventistas.py --master-dev
# Aplicar en master_dev
python3 crear_grupo_vendedores_preventistas.py --master-dev --apply
# O en master_18
python3 crear_grupo_vendedores_preventistas.py --master-18 --apply
```

XML ID opcional del grupo creado: `nakel_perm_scripts.group_vendedores_preventistas` (idempotencia entre ejecuciones).

**Aplicado en `master_dev`:** 2026-04-11 — `res.groups` **102** «Vendedores - Preventistas» quedó con `implied_ids` → `account.group_account_readonly` (id 22); registrado `nakel_perm_scripts.group_vendedores_preventistas`.

---

## Regla granular: solo contactos del vendedor (grupo Preventistas)

Solo para quienes tienen **Vendedores - Preventistas** (`nakel_perm_scripts.group_vendedores_preventistas`), existe una **`ir.rule`** sobre **`res.partner`** que limita los registros visibles a:

- **`partner_share = False`** (contactos **internos**: administrador, empleados, etc.). Sin esta rama, al abrir un cliente Odoo lee `create_uid` / `write_uid` y sus `res.partner` (p. ej. id **3** Administrator) y dispara *registros restringidos*.
- **O** una de: `user_id`; `parent_id.user_id`; `commercial_partner_id.user_id`; `user_ids` (any); `id = user.partner_id.id` (misma lógica de “solo mis clientes” en `partner_share=True`).
- **O** (desde **2026-04-13**): el contacto aparece en **pedidos de venta** donde el usuario es comercial (`sale_order_ids` / `commercial_partner_id.sale_order_ids` con `user_id` del pedido), para no bloquear **confirmación de pedidos** cuando el cliente no tiene el vendedor bien cargado en la ficha pero el `sale.order` sí.
- **O** (desde **2026-04-13** bis): **`id` en los partners de las compañías del usuario** (`user.company_ids.mapped('partner_id').ids`), porque al confirmar con **stock** Odoo lee el **`partner_id` del almacén** (contacto de la razón social, p. ej. «Nakel SA»), que no cumple «cliente asignado» y disparaba *AccessError*.

Dominio actual:  
`['|','|','|','|','|','|','|','|',('partner_share','=',False),('user_id','=',user.id),('parent_id.user_id','=',user.id),('commercial_partner_id.user_id','=',user.id),('user_ids','any',[('id','=',user.id)]),('id','=',user.partner_id.id),('sale_order_ids','any',[('user_id','=',user.id)]),('commercial_partner_id.sale_order_ids','any',[('user_id','=',user.id)]),('id','in',user.company_ids.mapped('partner_id').ids)]`.

| Campo | Valor (`master_dev`, 2026-04-11) |
|--------|----------------------------------|
| **XML ID** | `nakel_perm_scripts.rule_res_partner_preventistas_solo_asignados` |
| **`ir.rule` id** | `402` (orientativo; puede cambiar si se borra y recrea) |
| **Nombre** | Nakel: Preventistas — solo contactos del vendedor asignado |
| **XML ID (2)** | `nakel_perm_scripts.rule_res_partner_preventistas_proveedores_catalogo` |
| **`ir.rule` id (2)** | `403` — **OR** con la 402: proveedores con **`supplier_rank > 0`** **o** `partner_id` en **`product.supplierinfo`** (aunque rank 0), siempre con filtro de compañía; mitiga *AccessError* al confirmar ventas con catálogo aún no normalizado. |

Script: `PERMISOS/crear_ir_rule_partner_preventistas.py` (dry-run por defecto, `--apply` para crear/actualizar).

```bash
python3 crear_ir_rule_partner_preventistas.py --master-dev
python3 crear_ir_rule_partner_preventistas.py --master-dev --apply
```

**Notas:** los clientes con **vendedor vacío** (`partner_share=True`) siguen fuera salvo otras ramas; los **internos** (`partner_share=False`) son visibles para evitar bloqueos al abrir fichas. Quien **no** tenga el grupo Preventistas **no** queda sujeto a esta regla.

---

## Habilitar creación de contactos (ACL `res.partner`)

Si un preventista ve:

- *“no tiene acceso 'crear' a: Contacto (res.partner)”*

entonces el bloqueo es por **ACL** (`ir.model.access`), no por vista.

Solución aplicada en código (para evitar “tocar usuario por usuario”):

- En el módulo `clientes_cc_detalle` se agregó una ACL que da **R/W/C** (sin borrar) sobre `res.partner`
  al grupo `nakel_perm_scripts.group_vendedores_preventistas`.
- Archivo: `nakel_odoo/addons/clientes_cc_detalle/security/res_partner_access.xml`

Luego: actualizar módulo `clientes_cc_detalle` en la base y refrescar sesión.

**Actualización dominio (`master_dev`):** 2026-04-11 — rama `user_ids` + **`user_ids any`** + **`id = user.partner_id.id`**. **Tercera actualización** — rama **`partner_share=False`** para no bloquear lecturas indirectas de contactos internos (create/write uid, chatter, etc.). **Cuarta (2026-04-13):** ramas **`sale_order_ids`** / **`commercial_partner_id.sale_order_ids`** (comercial del pedido = usuario) — corrige *AccessError* al **confirmar** pedidos si Odoo lee dirección de envío/facturación o entidad comercial sin `user_id` alineado en la ficha. **Quinta (2026-04-13):** rama **`id in user.company_ids.mapped('partner_id').ids`** — contacto **de la compañía** usado en **`stock.warehouse.partner_id`** al confirmar venta + entregas. **Sexta (2026-04-13):** segunda **`ir.rule` 403** (mismo grupo 102, dominio **OR** respecto a la 402) para **`supplier_rank > 0`** — desbloquea lectura de **proveedores** en `product.supplierinfo` (p. ej. ENERGIZER, AKAPOL) que el motor de stock/compras consulta al confirmar. **Séptima (2026-04-14):** la **403** pasa a **OR interno**: sigue la rama `supplier_rank > 0` **o** partners cuyo `id` está en `user.env['product.supplierinfo'].sudo().search([]).mapped('partner_id').ids` (mismo filtro de compañía), para proveedores con **`supplier_rank = 0`** aún presentes en líneas de compra del producto (caso p. ej. S02253 / DELLEPIANE / REGIONAL).

---

## Ensayo dry-run: alinear «Vendedores - Preventistas» al rol vendedor (sin aplicar cambios)

**Objetivo:** que el paquete de permisos refleje *cotización / pedido / clientes asignados / documentos de venta ligados al usuario*, sin exponer **toda** la contabilidad (PDV, cajas, saldo global del cliente) salvo lo que negocio acepte explícitamente.

**Estado actual (snapshot `master_dev`, solo lectura):**

| Elemento | Valor |
|----------|--------|
| Grupo | `nakel_perm_scripts.group_vendedores_preventistas` → `res.groups` **102**, nombre *Vendedores - Preventistas* |
| **Implied** | Solo **`account.group_account_readonly`** (Accounting / Read-only, id **22**) |
| Regla propia | `ir.rule` **402** sobre **`res.partner`**, solo grupo **102** (contactos + internos `partner_share=False`) |
| Ventas “propias” (estándar Odoo) | **`sales_team.group_sale_salesman`** (id **35**) — *Own Documents Only*; suele asignarse aparte al usuario, **no** está hoy como *implied* del 102 |

**Bloqueo conceptual ya identificado:** el grupo **22** aporta reglas **`(1,'=',1)`** en **`account.move`** / **`account.move.line`**. Cualquier regla restrictiva adicional (por comercial, por diario, etc.) en otro grupo del mismo usuario queda **anulada en la práctica** por el **OR** entre reglas de grupos. Por tanto, **alinear al rol vendedor en contabilidad** exige **replantear el implied 22** o sustituirlo por un perfil contable **acotado** (módulo / datos técnicos), no solo “sumar reglas” al 102.

---

### Fase 0 — Definición de producto (**respuestas negocio, 2026-04-12**)

| Bloque | Pregunta | Respuesta acordada |
|--------|----------|-------------------|
| **A.1** | Saldo real vs subconjunto comercial | **Solo subconjunto comercial** ligado a **sus pedidos y facturas**, aunque **no** coincida con el total contable global. |
| **A.2** | Customer Statement / Estado del cliente | **Sí** deben usarlo: necesitan saber **cuánto les debe el cliente** (información para gestión / comisiones; ver matiz técnico abajo). |
| **A.3** | Cobros / pagos | **Solo facturas y pedidos**; solo cosas **que ellos registraron** (no ver flujos de cobro contable amplios). |
| **B.4** | `invoice_user_id` al facturar Central | **Siempre** preventista asignado; **corrigen proceso antes de facturar** si no, pierden comisión. |
| **B.5** | `user_id` en pedido | **Siempre** interviene el preventista, **salvo** compra en POS donde el preventista **no** está. |
| **B.6** | Clientes compartidos / compras rápidas en Belgrano POS | **No** comparten clientes entre vendedores; compras rápidas en POS **sin** comisión y **no** deben verlas — *indican que la plantilla actual ya cumple bien esa parte*. |
| **C.7** | Alcance ocultación | Ideal **solo** actividad **PDV / retail sucursal** (no “todo banco central” salvo que apunte a otro acuerdo). |
| **C.8** | Facturas Central y pedidos ajenos | Deben **ver facturas** que emite Administración; **no facturan** ellos. **No** deben ver **pedidos** que **no** generaron ellos. **Cierre explícito (2026-04-12):** “ver facturas de Administración” = **solo** `account.move` (out_invoice / out_refund según caso) donde **`invoice_user_id` = preventista** (comercial en cabecera). |
| **D.9** | Accounting completo | **Probablemente no** todo; necesitan **cotizaciones**, **confirmar** → orden de venta, **stock/productos** para cotizar. |
| **D.10** | Facturación | **Solo ventas**; **no** llevan grupo de facturación amplio. |
| **E.11** | Excepciones | **Administración Nakel Central**. |
| **E.12** | Batch / robots | **No**; uso **móvil** (cotizaciones, altas cliente, confirmar cotización → venta, consulta inventario/stock). |

#### Matiz técnico (A.2 vs A.1 / A.3)

En Odoo estándar, **“Estado del cliente”** y el importe del smart button se alimentan de **cuenta por cobrar del contacto** (partner ↔ compañía), **no** de un saldo “personal del vendedor” distinto del contable. Para que el número muestre **solo** lo comercial (pedidos/facturas **suyos**) y **excluya** PDV/retail como pidieron, hace falta **una de**: (a) **reglas / lecturas** en `account.move.line` alineadas a ese subconjunto **y** quitar el conflicto con el **solo lectura `(1,1)`** (camino **2a** del ensayo), o (b) **campo o informe dedicado** (“mi saldo comisionable”) además o en lugar del estándar. Eso **no contradice** la decisión de negocio; solo fija el **trabajo técnico** a hacer para que la UI coincida con el significado que ustedes le dan al botón.

#### ¿Queda claro el flujo?

**Sí**, a nivel proceso queda claro: **preventista** en calle → **cotización** → **confirmación** → **orden de venta**; **Central** factura con **comercial = preventista**; **no** comisionan ni deben ver **POS ajeno**; **sí** necesitan **vista comercial** de deuda **acotada** a su actividad y **Estado del cliente** como herramienta, con la salvedad de **cómo** materializarlo en Odoo (párrafo anterior + fases 1–3 del ensayo).

---

### Fase 1 — Alinear **ventas** al grupo plantilla (bajo riesgo conceptual)

**Dry-run (diseño):**

- Opción **A**: poner **`sales_team.group_sale_salesman`** (35) como **implied** del grupo **102**, para que *todo* preventista herede **Own Documents** en pedidos (y reglas estándar de facturas personales donde apliquen).
- Opción **B**: no implied; checklist operativo: **todo usuario con 102 debe tener también 35** (o explícitamente **36** si negocio lo pide).

**Prueba sugerida (cuando haya apply):** usuario solo con 102+35: listar `sale.order` y `account.move` out_invoice y verificar dominios estándar.

---

### Fase 2 — **Contabilidad** para informes CC sin “ver todo” (alto impacto)

**Dry-run (dos caminos mutuamente excluyentes en intención):**

| Camino | Idea | Consecuencia |
|--------|------|----------------|
| **2a — Mínimo contable custom** | Quitar **implied** `account.group_account_readonly` del **102**. Crear **grupo Nakel** (o reutilizar 102) con **`ir.model.access` read-only** solo a modelos necesarios (`account.report`, líneas del motor, etc.) **sin** las `ir.rule` `(1,1)` del 22, **más** `ir.rule` finas en `account.move` / `account.move.line` (p. ej. `invoice_user_id`, partners permitidos, y/o blacklist de `journal_id`). | **Menos** exposición global; **más** trabajo de mantenimiento y pruebas; hay que validar **cada** pantalla que usan hoy (pagos, extractos, conciliación). |
| **2b — Mantener 22** | Conservar implied **solo lectura** estándar. | Las reglas **comerciales** o **blacklist diarios** en el **102** **no** recortan saldos ni líneas contables; solo sirven UX parcial u otros modelos. |

Recomendación del ensayo: si el objetivo es **alineación rol vendedor en números**, el plan serio apunta a **2a** a medio plazo; **2b** solo si aceptan que vean **toda** la contabilidad legible por 22.

---

### Fase 3 — Filtros de negocio (después de desbloquear el OR)

**Orden sugerido en dry-run:**

1. **`account.move.line`** (impacta `credit`/`debit` en contacto vía SQL estándar): dominio acorde a negocio — **solo comercial** (`move_id.invoice_user_id`, vínculos a `sale_line_ids`, etc.) **y/o** **blacklist** de `journal_id` (lista de diarios retail/caja por sucursal).
2. **`account.move`** coherente con lo anterior.
3. **`account.payment`** si siguen viendo cobros por ahí.
4. Revisar **Customer Statement** (`action` cliente `account_report`): puede seguir mostrando más de lo deseado si el motor lee fuera del dominio de líneas; validar con casos reales (GOITA, PDV, Mercado Pago).

---

### Fase 4 — UX opcional (no sustituto de seguridad)

- Ocultar smart button **Customer Statement** / importe para quienes **no** deban verlo (`groups` en vista heredada), **solo** si negocio lo pide.
- Documentar URLs directas (bookmark) como riesgo residual.
- Si negocio pide habilitar el smart button «Estado del cliente» sin dar **Facturación** (23), ver script: `PERMISOS/habilitar_boton_estado_cliente_vendedores_master_dev.py` (crea vista heredada que ajusta `groups` del botón `open_customer_statement` a `account.group_account_invoice` **OR** `nakel_perm_scripts.group_vendedores_preventistas`).

---

### Checklist de pruebas (post-implementación futura)

- [ ] Usuario **102** + **35**, sin **23**: pedidos, facturas propias, clientes asignados, informe CC que deban usar.
- [ ] Mismo usuario: **no** debe ver líneas de diarios excluidos / movimientos ajenos según reglas acordadas.
- [ ] Abrir ficha contacto cliente asignado: sin *registros restringidos*; `credit` / **Estado del cliente** acorde a lo esperado.
- [ ] Usuario **sin** 102: comportamiento **idéntico** al actual (regresión).

---

*Este apartado es **ensayo / planificación**; no modifica `master_dev`. Fecha de redacción: 2026-04-12.*

### Dry-run: usuarios con grupo **102** y traducción `res.groups` (`master_dev`, 2026-04-12)

**Usuarios con «Vendedores - Preventistas» (6):** 90 Delgado, 91 Díaz, 103 Vera, 105 Chirimonti, 106 Choque, 112 Paredes.

**Hallazgo:** los **seis** tienen también **`account.group_account_invoice` (id 23)** — *Accounting / Invoicing*. En la UI suele aparecer como **Contabilidad / Facturación** (amplía mucho más que “solo ventas”). Si la plantilla objetivo es **no facturar**, conviene **desmarcar ese grupo** usuario por usuario (o por plantilla de acceso) y validar que no rompa un flujo que sí necesiten.

**Grupos “marcados” que suelen revisar a mano** (id → XML ID → nombre en inglés en BD):

| id | XML ID | Nombre (UI inglés típico) |
|----|--------|----------------------------|
| 1 | `base.group_user` | User types / Internal User |
| 9 | `base.group_partner_manager` | Extra Rights / Contact Creation |
| 22 | `account.group_account_readonly` | Accounting / Read-only |
| 23 | `account.group_account_invoice` | Accounting / Invoicing |
| 35 | `sales_team.group_sale_salesman` | Sales / User: Own Documents Only |
| 50 | `stock.group_stock_user` | Inventory / User |
| 102 | `nakel_perm_scripts.group_vendedores_preventistas` | Vendedores - Preventistas |

En **Ajustes → Usuarios → [usuario] → Derechos de acceso**, los nombres pueden salir en **español** según idioma; los **XML ID** son los estables para documentar y buscar en modo desarrollador.

---

## Smart button «Facturado» (`action_view_partner_invoices`)

**Odoo 18 estándar (módulo `account`):**

- En la vista `account.partner_view_buttons`, el botón lleva  
  `groups="account.group_account_invoice,account.group_account_readonly"`  
  (en Odoo, la coma en `groups` significa **OR**: alcanza con uno de los dos).
- El campo computado **`total_invoiced`** en `res.partner` declara los mismos grupos; sin ellos el widget no muestra el importe aunque el botón exista.

Por tanto, el grupo **Vendedores - Preventistas** que ya **implica** `account.group_account_readonly` (`crear_grupo_vendedores_preventistas.py`) **cubre el estándar** para ese botón: no hace falta un permiso extra “mágico” sobre el botón en sí.

**Si igual no lo ven:**

1. Confirmar en el usuario que, tras cerrar sesión, figure **Contabilidad / solo lectura** (heredado del 102) o el XML ID `account.group_account_readonly`.
2. Buscar una **vista heredada** que haya cambiado `groups=` del botón (p. ej. dejando solo Facturación). Script de solo lectura: `PERMISOS/auditar_vista_boton_facturado_partner.py`.
3. **No** recomendamos sumar `account.group_account_invoice` al 102 solo por este botón: amplía mucho más que la factura del cliente (véase el hallazgo de usuarios con grupo 23 en el ensayo).

**Si negocio exige el botón y una vista Nakel lo restringió:** corregir esa herencia (restaurar OR con `account.group_account_readonly`) **o** añadir en la misma herencia el XML ID `nakel_perm_scripts.group_vendedores_preventistas` al atributo `groups` del botón (cambio en módulo personalizado / datos importados), sin sustituir la seguridad contable en profundidad.

---

## Notas

- Los **IDs numéricos** de menús y grupos pueden variar si restauran otra base; los **XML IDs** (`account.group_account_readonly`, etc.) son los estables para documentar y comparar.
- Credenciales y URLs (sanitizado para repo): `documentacion/CREDENCIALES_Y_IDS_POR_BASE.PUBLIC.md` (no repetir secretos aquí).
