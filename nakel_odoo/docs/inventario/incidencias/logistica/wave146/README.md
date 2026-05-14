# Ola **WAVE/00146** — caída de conexión durante pickeo (auditoría `qty_done`)

**Base:** `master_dev`  
**Fecha auditoría:** 2026-05-13  

| Campo | Valor |
|--------|--------|
| `stock.picking.batch` | id **152** |
| Nombre | **WAVE/00146** |
| Almacén | Nakel Central (14) |
| Estado batch | `in_progress` |

---

## Respuesta corta: ¿impactó todo lo que contaron?

**No.** En base de datos, casi ninguna línea tiene **cantidad hecha** (`qty_done`) registrada.

- **911** líneas de operación (`stock.move.line`) en la ola.
- Solo **9** líneas tienen `qty_done` &gt; 0 (suma **49** unidades hechas).
- Las otras **902** líneas con cantidad reservada siguen con `qty_done = 0` y `picked = false` (salvo esas 9, que tienen `picked = true`).

**Ningún picking del batch está `done`:** 59 pickings `assigned`, 6 `confirmed`. No hubo validación masiva: lo que “no está en `qty_done`” **no impactó stock** como entregado desde el punto de vista de validación de albarán.

> Si en pantalla del Barcode “vieron” más líneas en verde antes del corte, eso **no quedó persistido** como `qty_done` en esta lectura (típico de pérdida de sesión / no guardar / cierre antes de confirmar líneas según flujo Odoo).

### Relato operativo: “hoja 40 de 49” (Gustavo, PICK por ola)

En el batch hay **49 OV** distintas (`sale_id` en los pickings) y **65** pickings. Si “49” son esas hojas/pedidos, el conteo **40/49** **no** se ve en Odoo: solo **9** OV tienen **alguna** cantidad en `qty_done` en la ola, y solo **9** pickings tienen **al menos una** línea con `qty_done` &gt; 0 (en la práctica, una línea completa por picking). El resto del trabajo **no** quedó en `stock.move.line.qty_done`.

---

## Las 9 líneas que **sí** quedaron grabadas (`qty_done` = reservado)

| id línea | OV | Picking | Producto | Reservado | Hecho (`qty_done`) |
|---------:|----|-----------|------------|----------:|-------------------:|
| 221758 | S04092 | CEN/PICK/04097 | [CA-840] BOCADITO DE DDL FANTOCHE X20U.-596- | 1 | 1 |
| 222212 | S04096 | CEN/PICK/04098 | [8676.00] POXIMIX INTERIOR BOLSA X1250G.-518- | 7 | 7 |
| 223001 | S04105 | CEN/PICK/03741 | [8699.20] CINTA PYTHON ALTA RESISTENCIA 9MTS AZUL.-201- | 3 | 3 |
| 224183 | S04134 | CEN/PICK/03759 | [26301] ALBUM MUNDIAL 2026 X1U.-437- | 4 | 4 |
| 225008 | S04159 | CEN/PICK/03782 | [26301] ALBUM MUNDIAL 2026 X1U.-437- | 2 | 2 |
| 225199 | S04153 | CEN/PICK/03784 | [26301] ALBUM MUNDIAL 2026 X1U.-437- | 19 | 19 |
| 228187 | S04252 | CEN/PICK/03865 | [8653.00] FASTIX ALTA TEMPERATURA CHICO X25ML.-1724-(6) | 6 | 6 |
| 228193 | S04251 | CEN/PICK/03861 | [8282.20] POLVORITA CHOCOLATE-VAINILLA X152G.-143- | 6 | 6 |
| 233416 | S04327 | CEN/PICK/03945 | [80130] OBLEA BAUDUCCO CHOCOLATE x140G.-290- | 1 | 1 |

En las 9, `qty_done` coincide con la cantidad reservada de la línea (no hay parciales a medias guardados).

---

## Contexto stock.move (958 movimientos)

| Estado | Líneas | Suma demanda | Suma reservado (`quantity`) |
|--------|-------:|-------------:|------------------------------:|
| `assigned` | 899 | 6967 | 6967 |
| `partially_available` | 12 | 103 | 70 |
| `confirmed` | 47 | 269 | 0 |

Los **12** `partially_available` son faltante de reserva (similar a WAVE/00145), independiente del corte de red.

---

## Export CSV (misma carpeta)

Generado con `nakel_odoo/tools/inventario/export_wave_pickings_ov_csv.py --name WAVE/00146`:

- `wave_00146_batch152_pickings_20260513_181722.csv`
- `wave_00146_batch152_sale_orders_20260513_181722.csv`

---

## Qué hacer operativamente

1. **Reanudar Barcode** en la misma ola / pickings y volver a marcar cantidades; verificar en web (línea de operación) que **`qty_done`** suba como esperan.
2. Si el Barcode muestra progreso incoherente: **SYNC Ola+OUT** / SYNC `picked` según [NAKEL_SYNC_PIKCED_OLA_BOTON.md](../../NAKEL_SYNC_PIKCED_OLA_BOTON.md) y addon `nakel_sync_ola` (no sustituye re-pickear lo que quedó en cero).
3. Antes de validar en bloque: revisar cadena **PICK → OUT** por OV ([OV_SIN_FACTURAR_SIN_OUT_TRAS_OLA.md](../../OV_SIN_FACTURAR_SIN_OUT_TRAS_OLA.md)).

---

## Reproducir conteos

```bash
cd /media/klap/raid5/cursor_files/nakel
python3 nakel_odoo/tools/inventario/export_wave_pickings_ov_csv.py --name WAVE/00146
```

Lectura fiable de `qty_done`: `read` de `stock.move.line` (dominio en `qty_done` puede no ser fiable si el campo no es almacenado para `search_count` en algunas versiones).
