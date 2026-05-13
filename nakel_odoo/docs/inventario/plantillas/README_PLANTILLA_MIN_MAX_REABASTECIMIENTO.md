# Plantilla: mínimos y máximos de reabastecimiento (Belgrano 1 / B1)

## Archivo

- **`PLANTILLA_MIN_MAX_REABASTECIMIENTO_B1.csv`** — copiar o enviar al cliente para completar en Excel / LibreOffice.

## Alcance (acordado con la auditoría `master_dev`)

- **Almacén:** Belgrano 1 (**B1**).
- **Ubicación de stock en Odoo:** **`B1/Existencias`** (todas las reglas de reabastecimiento B1 apuntan ahí).
- **Ruta hacia Central:** ya configurada en Odoo (*Belgrano 1: suministrar producto de Nakel Central*). **No** hace falta que el cliente escriba rutas en la planilla: solo **mínimos, máximos y opcionalmente múltiplo**.

## Cómo completar cada columna

| Columna | Obligatorio | Descripción |
|---------|-------------|-------------|
| **referencia_interna** | Sí | Código interno del producto en Odoo (equivalente a **Referencia interna** / `default_code` en la ficha). Debe coincidir con un producto que **ya** tenga regla de reabastecimiento en B1 o que vayan a parametrizar en Odoo. |
| **nombre_producto** | No | Solo ayuda a revisar que la referencia sea la correcta; **Odoo no importa** esta columna en el flujo estándar de “reglas de reabastecimiento” si usan importación técnica por `product_id`. |
| **cantidad_minima** | Sí | Stock mínimo deseado en **B1/Existencias** (número entero o decimal con punto `.`, ej. `12.5`). |
| **cantidad_maxima** | Sí | Stock máximo / techo a repener hasta (mismo formato). Debe ser **≥ cantidad_minima**. |
| **multiplo_unidades** | No | Si compran o piden a Central solo por **caja/bulto**, poner unidades por bulto (ej. `12`). Si no aplica, dejar `1` o vacío según acuerden con quien cargue en Odoo. |
| **notas** | No | Comentarios libres (rotación, estación, acuerdo con proveedor, etc.). |

**Eliminar** la fila de ejemplo `[REEMPLAZAR]` antes de devolver el archivo o marcarla para que no se importe.

## Qué hace el cliente y qué hace quien carga en Odoo

1. **Cliente / sucursal:** completa el CSV con los SKU que quieren **priorizar** (no es obligatorio llenar los ~135 de golpe; pueden empezar por 20–40 de mayor rotación).
2. **Equipo técnico / administración Odoo:** en **Inventario → Operaciones → Reabastecimiento**, filtrar **Belgrano 1** y ubicación **B1/Existencias**, localizar cada producto por **referencia interna** y cargar **Mínimo**, **Máximo** y **Múltiplo** en la regla correspondiente; o bien preparar **importación** mapeando columnas a los campos `product_min_qty`, `product_max_qty`, `qty_multiple` del modelo **Reglas de reabastecimiento** (`stock.warehouse.orderpoint`), identificando cada fila por `id` de la regla o por combinación producto + ubicación + almacén (según política de la empresa).

La importación directa en Odoo desde este CSV **puede** requerir columnas técnicas adicionales (`id`, `external_id`, etc.); por eso la plantilla está pensada como **origen de datos** negocio → carga manual o script de actualización.

## Referencia de auditoría

- [AUDITORIA_REABASTECIMIENTO_BELGRANO_CENTRAL_MASTER_DEV.md](../AUDITORIA_REABASTECIMIENTO_BELGRANO_CENTRAL_MASTER_DEV.md) — anexo B1, rutas y conteo de reglas.
