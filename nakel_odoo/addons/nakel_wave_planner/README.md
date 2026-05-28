# Nakel — Planificador de olas por zona

Arma **olas WAVE** desde **OV filtradas por etiqueta de cliente** (zona logística), con checklist de PICKs y alertas antes de confirmar.

## Problema que resuelve

Los operarios preparan olas por **zona + día** (~30 OV). Buscar PICK por OV una a una es lento y propenso a errores.

## Flujo operativo

1. **Inventario → Operaciones → Jobs → Wave Transfers → Armar ola por zona**
2. Elegir **zona(s)** y/o **vendedor(es)** (varios a la vez). La **fecha es opcional**.
3. **Buscar pedidos** → tabla con checklist (OV, PICKs, alertas).
4. Revisar filas **Revisar** / **Bloqueado**.
5. **Crear / agregar a ola WAVE** → abre la ola con todos los traslados.
6. Opcional: **Dejar ola lista para pickear** + **Modo demanda**.

## Criterios de búsqueda

| Campo | Uso |
|-------|-----|
| Zonas (etiquetas) | `category_id` en cliente o entrega. **Varias a la vez.** |
| Vendedores | `user_id` de la OV. **Varios a la vez.** Al menos zona **o** vendedor. |
| Fecha (opcional) | Si está vacía → todos los PICK pendientes. Si la completan → filtra según criterio. |
| Solo pedidos sin ola | Oculta OV que ya tienen ola asignada |
| Almacén | Opcional (ej. Nakel Central) |

## Alertas en la grilla

| Estado | Significado |
|--------|-------------|
| OK | Lista para incluir en la ola |
| Revisar | Sin PICK o fecha distinta |
| Bloqueado | OV o PICK ya en otra ola abierta |

## Dependencias

- `nakel_wave_picking_link` — enlace OV ↔ ola
- Opcional: `nakel_barcode_wave_demand_mode` — botón Modo demanda OV tras crear

## Instalación (staging / master_dev)

1. Actualizar lista de apps.
2. Instalar **Nakel — Planificador de olas por zona**.
3. Probar: etiqueta `Zona Norte` + fecha de hoy → Buscar OV → Crear ola.

## Ventas — control de fugas

En **Ventas → Pedidos**, filtros:

- **Sin ola Nakel** — OV confirmadas aún sin ola.
- Agrupar por **Etiqueta zona entrega**.

## Notas

- Crea olas con `is_wave=True` (secuencia **WAVE/**), no BATCH/.
- Agrega **traslados** (`picking_ids`), no líneas de operación (evita el modal vacío sin reserva).
- Normalizar etiquetas duplicadas (`Zona Norte` vs `ZONA NORTE`) mejora filtros; el wizard acepta varias etiquetas a la vez.
