# Informe CC clientes — «Saldo inicial» (facturas)

**Módulo:** `clientes_cc_informe`  
**Desde versión:** 18.0.1.0.13

## Qué hace

Si el usuario informa **Fecha desde (factura)**, el asistente calcula dos cosas extra en el resumen, PDF y Excel:

1. **Saldo inicial (FC/NC antes del «desde»):** suma de `amount_residual` de facturas y notas de crédito de cliente **publicadas**, con **fecha de factura estrictamente anterior** a «Fecha desde», aplicando los **mismos** filtros que el listado principal: vendedor (`invoice_user_id`), cliente (entidad comercial), solo pendiente / incluye pagados, diario PDV y opción migración.

2. **Adeudado total (inicial + listado):** saldo inicial + suma de `amount_residual` de las facturas **dentro** del rango mostrado en la tabla (las que cumplen `invoice_date >= date_from` y el resto de filtros).

## Qué **no** es

- **No** es el saldo inicial del **mayor contable** ni el del informe **Estado del cliente** estándar (no incluye pagos como líneas, asientos manuales en cuenta deudores sin FC, saldo arrastrado distinto del corte contable, etc.).
- Usa el **saldo pendiente actual** (`amount_residual`) de las FC/NC antiguas, no el saldo «histórico» a la medianoche del día anterior si después hubo cobros que Odoo aplicó a esas facturas.

Sirve para **acercar** el informe operativo a la idea de «cartera al inicio del período + movimientos del período» sin reimplementar el mayor.

## Uso recomendado

- Poner **Fecha desde** al primer día del mes o del ejercicio que quieren analizar.
- Comparar **Adeudado total** con otros informes solo si el alcance (vendedor, PDV, cliente) es el mismo.

## Relación con PDV / diarios

Misma lógica de diarios que el listado principal: ver [PDV_DIARIOS_VENTA_AFIP_MASTER_DEV.md](PDV_DIARIOS_VENTA_AFIP_MASTER_DEV.md).

---

## Módulo `clientes_cc_detalle` (mis ventas / vendedores)

**Desde versión:** 18.0.1.0.27

### Parámetro de sistema

| Clave | Valor | Efecto |
|-------|--------|--------|
| `clientes_cc_detalle.my_sales_balance_from_date` | `YYYY-MM-DD` (ej. `2026-04-01`) | En **contactos**, columna opcional **«Saldo anterior al corte»**: suma de `amount_residual_signed` en FC/NC donde el usuario es `invoice_user_id`, con **fecha de factura anterior** a esa fecha (mismos diarios que el filtro PDV ICP si está activo). El **total adeudado** del botón CC no cambia (sigue siendo toda la cartera en alcance). |

Sin el parámetro, el campo «saldo anterior» queda en cero.

### Exportación Excel/CSV desde **Ventas → Cuentas corrientes (mis ventas)**

- Si la lista tiene filtro **`Fecha factura >= …`** (u otro límite inferior que Odoo envía en `active_domain`), el export suma aparte el **saldo inicial** (FC/NC con factura **anterior** a esa fecha, mismos filtros de cliente/diario que la búsqueda) y muestra **adeudado total = inicial + suma de la tabla**.
- Si solo existe el **parámetro** de corte ICP pero **no** hay filtro de fecha en la lista, el export añade una **línea informativa** con el saldo anterior al ICP (sin duplicar totales de tabla si la tabla incluye todo el historial).

No sustituye al mayor contable; misma advertencia que arriba sobre `amount_residual` actual.
