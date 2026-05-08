# PDV no descuenta del almacén correcto (ej. B1 sigue en 50 tras vender 10)

**Fecha:** 2025-01-23  
**Síntoma:** Vendes en el PDV (ej. 10 unidades del producto 2814.10), tienes 50 en stock en B1 (Belgrano 1), pero en el almacén después de la venta sigue figurando 50 y no 40.

---

## Causa más probable

En Odoo, el **PDV (Point of Sale)** no descuenta “del almacén donde miras”, sino **del almacén/ubicación que tiene configurado** ese punto de venta.

Si el PDV que usas en Belgrano 1 está configurado para usar **Nakel Central (CEN)** (o otro almacén), entonces:

- La venta **sí** se registra y el stock **sí** se descuenta.
- Pero se descuenta **de Central (CEN)** (o del almacén configurado), **no de B1**.
- Por eso en **B1** el stock sigue en 50; el descuento está en CEN (o en el almacén que tenga el PDV).

No es que “no descuente”: está descontando del almacén equivocado para tu sucursal.

---

## Qué revisar en Odoo

1. **Ir a:** **Punto de venta → Configuración → Puntos de venta** (o **Point of Sale → Configuration → Point of Sale**).
2. **Abrir** el PDV que usas en Belgrano 1 (el que usas para vender).
3. **Buscar** la sección de **Inventario** (o **Stock** / **Operaciones**):
   - Campo tipo **“Almacén”** / **Warehouse**, o
   - **“Tipo de operación”** / **Operation type** que se usa para las entregas del PDV.
4. **Comprobar** qué almacén está seleccionado:
   - Si pone **Nakel Central (CEN)** → el PDV descuenta de Central; por eso B1 no baja.
   - Debe estar en **Belgrano 1 (B1)** para que al vender desde ese PDV se descuenta de B1.

---

## Cómo corregirlo

1. En la configuración de ese **PDV**, cambiar:
   - **Almacén** a **Belgrano 1 (B1)** (o el almacén de la sucursal que corresponda), **o**
   - El **tipo de operación** que usa el PDV para descontar stock.
2. **Importante:** El tipo de operación debe ser el que **entrega al cliente** (sale de stock), no el de almacenamiento interno:
   - **"Belgrano 1: Almacenamiento"** = suele ser para *almacenamiento interno* (put-away), **no** para descontar en ventas PDV.
   - Debe usarse el tipo que **entrega al cliente** (sale de stock), por ejemplo:
     - **"Belgrano 1: Órdenes de entrega"** (Delivery Orders) → **correcto para PDV**.
     - O equivalentes como "Belgrano 1: Recolectar" (Pick) / "Belgrano 1: Entregar", según nombres en tu Odoo.
3. Guardar.
4. A partir de ahí, las **nuevas** ventas de ese PDV descontarán de B1.

Las ventas ya hechas siguen descontadas del almacén que tenía configurado antes (ej. CEN); no se recalculan solas.

---

## Resumen

| Pregunta | Respuesta |
|----------|-----------|
| ¿Estoy haciendo algo mal en el proceso? | No necesariamente; el flujo de venta en PDV puede estar bien. |
| ¿No me está descontando lo que vendo? | Sí te descuenta, pero **del almacén que tiene configurado el PDV**. Si ese almacén es Central (CEN), B1 no baja. |
| ¿Qué hacer? | Revisar en **Configuración del PDV** que el almacén (o tipo de operación de entrega) sea **Belgrano 1 (B1)** para el PDV de esa sucursal. |

---

**Última actualización:** 2025-01-23
