# Reporte de comisiones — contexto y parámetros (Nakel)

**Objetivo**: dejar documentados los **parámetros de conexión** y el **estado actual del plan de comisiones** (Odoo 18, `master_dev`) para armar un **reporte de cierre 40/60** por vendedor.

> Nota: este documento **no** incluye credenciales (passwords/tokens). Referenciar `.env`/variables de entorno y `config_nakel.py` como fuente local.

---

## Alcance / ambiente

- **Instancia Odoo**: `nakel.net.ar`
- **Base (Odoo 18 Enterprise)**: `master_dev` (**productiva**, aunque conserve “dev” en el nombre)
- **Método de conexión**: **XML-RPC** (a veces referido internamente como “XRMC”)
  - Endpoint auth: `https://nakel.net.ar/xmlrpc/2/common`
  - Endpoint models: `https://nakel.net.ar/xmlrpc/2/object`

Fuente: `config_nakel.py` (local) y scripts del vault.

---

## Configuración de conexión (sin secretos)

### Archivo de configuración central

- **Archivo**: `/media/klap/raid5/cursor_files/config_nakel.py`
- **Carga opcional de .env**:
  - Ruta default: `/media/klap/raid5/cursor_files/nakel/.env`
  - Variable para cambiar ruta: `NAKEL_ENV_FILE`

### Variables `.env` relevantes (cuando se usa `NAKEL_TARGET=master_test`)

En `config_nakel.py` existe un selector para apuntar a `dev.nakel.net.ar/master_test` en lugar de `master_dev`:

- `NAKEL_TARGET=master_test`
- `ODOO_MASTER_DEV_URL`
- `ODOO_MASTER_DEV_DB`
- `ODOO_MASTER_DEV_USERNAME`
- `ODOO_MASTER_DEV_PASSWORD`

> Para `master_dev` el código usa la sección `ODOO_CONFIG_MASTER_DEV`. Mantener **passwords fuera del repo**.

---

## Estado del esquema de comisiones (Odoo 18 / `master_dev`)

Fuente principal: `nakel/comisiones/COMISIONES_PREVENTISTAS_ODOO18_MASTER_DEV.md` (snapshot 2026-04-23).

- **Módulos instalados en `master_dev`**:
  - `sale_commission`
  - `sale_commission_margin`
- **Plan existente**:
  - Nombre: `Plan de Comisión 2026`
  - Estado (auditoría por API, 2026-04-25): `approved` (aprobado).
- **Reglas ya cargadas en el plan** (`sale.commission.plan.achievement`):
  - `type = amount_invoiced`
  - `rate` (% como decimal, ej. `0.048` = 4,8%)
  - Reglas por **categoría** (`product_categ_id`) + una regla “general” (sin categoría)
  - Muestra registrada en la doc:
    - General: 4,8%
    - KIOSCO / Coleccionables / Figuritas: 2%
    - ALMACEN: 2,8%
    - FERRETERIA / AKAPOL: 4,8%
    - KIOSCO / Cigarrillos: 1%

---

## Lógica 40/60 (criterio Nakel)

- **40%**: se paga “sí o sí” al momento del hecho de venta/facturación según el criterio acordado.
- **60%**: se paga por **cobranza**, idealmente **prorrateado** por pagos parciales en el período.

En `master_dev` se verificó por API:

- La OV (`sale.order`) **no** tiene estado de pago.
- El estado de pago está en la **factura** (`account.move.payment_state`).
- Para historial de pagos conciliados existe `invoice_payments_widget` (en la factura).

---

## Scripts “modo consulta” disponibles (solo lectura)

Ubicación: `/media/klap/raid5/cursor_files/nakel/comisiones/`

- **Auditoría de comisiones / modelos / campos**:
  - `auditar_comisiones_master_dev.py`
  - Releva módulos instalados, modelos con “commission/comisi”, y campos clave en `sale.order`, `account.move`, `account.payment`, etc.
- **Cierre 40/60 por período (reporte)**:
  - `reporte_cierre_comisiones_40_60_master_dev.py`
  - Base comisionable actual: `amount_invoiced` (sin impuestos por línea de factura: `account.move.line.price_subtotal`)
  - 40%: sobre la comisión del período
  - 60%: proporcional a lo cobrado en el período usando `invoice_payments_widget['content']`

Ejemplo de ejecución (solo lectura):

```bash
cd /media/klap/raid5/cursor_files/nakel/comisiones
python3 reporte_cierre_comisiones_40_60_master_dev.py --plan-id 1 --from 2026-04-01 --to 2026-04-25
```

### Nota de performance (API)

En períodos con muchas facturas, conviene empezar con:

- `--limit-invoices 200` (o similar) para validar lógica y tiempos
- luego ampliar el límite o partir por rangos de fechas

---

## Entregable “para liquidar” (XLSX)

Se genera un Excel único con pestañas:

- `RESUMEN` (por vendedor, listo para liquidar)
- `DETALLE_FACTURAS`
- `DETALLE_NCS`

Script (sin dependencias):

- `ventas/repote-comisiones/generar_xlsx_comisiones_unificado.py`

Requiere que existan los CSV:

- `reportes/comisiones_detalle_facturas_<stamp>_UNIFICADO.csv`
- `reportes/comisiones_detalle_ncs_<stamp>_UNIFICADO.csv`

Ejemplo:

```bash
cd /media/klap/raid5/cursor_files/nakel/ventas/repote-comisiones
python3 generar_xlsx_comisiones_unificado.py --stamp 2026-04-01_2026-04-25
```

Salida:

- `ventas/repote-comisiones/reportes/comisiones_2026-04-01_2026-04-25.xlsx`

## Vendedores incluidos (preventistas) — IDs detectados

### Usuarios adicionales solicitados

- `res.users` **88** — **Bandeo Marcelo**
- `res.users` **108** — **Przbytek Marisol**

### Preventistas con grupo “Vendedores - Preventistas” (snapshot `master_dev`, 2026-04-12)

Fuente: `nakel/usuarios/PERMISOS/PERMISOS_PREVENTISTAS_INFORMES_CC_MASTER_DEV.md`

- `res.users` **90** — Delgado
- `res.users` **91** — Díaz
- `res.users` **103** — Vera
- `res.users` **105** — Chirimonti
- `res.users` **106** — Choque
- `res.users` **112** — Paredes

### Mapeo histórico de vendedores (MSSQL Gestion → Odoo `res.users`)

Fuente: `nakel/ventas/Pre-ventas-inyeccion/mapeo_preventas_master18.json`

- MSSQL vendedor `2` → `res.users` **105**
- MSSQL vendedor `3` → `res.users` **93**
- MSSQL vendedor `5` → `res.users` **91**
- MSSQL vendedor `6` → `res.users` **103**
- MSSQL vendedor `9` → `res.users` **106**
- MSSQL vendedor `16` → `res.users` **86**
- MSSQL vendedor `17` → `res.users` **90**

> Nota: este mapeo es para el pipeline de preventas (master_18), pero los IDs de `res.users` se reutilizan como referencia útil para comisiones cuando coinciden.

---

## Punteros a documentación existente (vault)

- `nakel/comisiones/COMISIONES_PREVENTISTAS_ODOO18_MASTER_DEV.md`
- `nakel/usuarios/PERMISOS/PERMISOS_PREVENTISTAS_INFORMES_CC_MASTER_DEV.md`
- `nakel/ventas/Pre-ventas-inyeccion/MAPEO_PREVENTAS_MSSQL_MASTER18.md`
- `nakel/ventas/Pre-ventas-inyeccion/mapeo_archivo_a_vendedor_mssql.json`

