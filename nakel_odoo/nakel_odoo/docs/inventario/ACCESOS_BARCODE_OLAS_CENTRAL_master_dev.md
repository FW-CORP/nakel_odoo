# Accesos — Barcode / Olas (Batch Transfers) en Central (`master_dev`)

Este documento resume una verificación rápida de accesos para un usuario específico en `master_dev`.

## Usuario verificado

- **Login**: `nathanmaximoasael@gmail.com`
- **Nombre**: Ruiz Gustavo
- **`res.users` id**: 119
- **Activo**: Sí
- **Compañía**: `Nakel SA` (company_id=1)
- **Compañías permitidas (`company_ids`)**: solo `[1]` (Nakel SA)

## Conclusión (alto nivel)

En `master_dev`, el usuario **tiene permisos de Inventario suficientes** para:

- ver y operar **Pickings** (`stock.picking`) desde Inventario
- ver y operar **Olas / Batch Transfers** (`stock.picking.batch`)
- ver y operar líneas de movimientos (`stock.move` / `stock.move.line`) usadas por Barcode

No se detectó una regla de registro que limite “solo mis olas/picks”. La única regla global relevante es multi-compañía.

## Evidencia (permisos / reglas)

### Grupos relevantes detectados

- `Inventory / User` (res.groups id **50**)
- `Internal User` (id **1**)

> El usuario NO pertenece a grupos “Encargados Belgrano 1..4” (ids 97..100), que son los que aplican reglas de visibilidad por sucursal.

### ACLs (ir.model.access) relevantes

Para el grupo `Inventory / User`:

- `stock.picking` (**write/create** habilitado)
- `stock.move` (**write/create** habilitado; unlink puede estar restringido según ACL)
- `stock.move.line` (**write/create** habilitado)
- `stock.picking.batch` (**read/write/create/unlink** habilitado)

### Record Rules (ir.rule) relevantes

- `stock_picking multi-company`: `[('company_id', 'in', company_ids)]` (global)
- `stock.picking.batch multi-company`: `[('company_id', 'in', company_ids)]` (global)
- Reglas “Encargados Belgrano *”: existen, pero aplican solo si el usuario está en esos grupos.

## Checklist práctico (cómo validar en UI)

### 1) Desde Inventario (web)

- Ir a **Inventario → Operaciones → Transferencias**:
  - Quitar filtro “Mis transferencias” si estuviera.
  - Filtrar por **Almacén = CEN** (o por `Tipo de operación` que pertenezca a CEN).
  - Abrir un picking y comprobar que aparecen botones de acción (p.ej. **Validar**).

- Ir a **Inventario → Operaciones → Transferencias por lote / Batch Transfers** (Olas):
  - Quitar filtro “Mis lotes / My Batches” si estuviera.
  - Abrir una ola y comprobar que puede ver líneas y (según estado) ejecutar acciones.

### 2) Desde Barcode

En Barcode, la “visibilidad” suele estar sesgada por filtros de la UI (“mis operaciones”), más que por reglas de seguridad.

- Entrar a **Inventario → Código de barras (Barcode)**.
- Elegir la operación (picking) o la ola (batch):
  - Si solo aparecen “asignadas a mí”, buscar y quitar el filtro “Mi usuario / Assigned to me / My …”.

## Nota: validar olas “no asignadas” al usuario

Como no hay rule “solo mis olas”, debería poder abrir/validar olas no asignadas **siempre que**:

- el estado lo permita (p. ej. ola/picking `assigned` o con reservas disponibles), y
- no haya una configuración operativa que obligue “Responsable” (esto suele ser proceso, no seguridad).

