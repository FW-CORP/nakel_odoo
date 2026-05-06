# Credenciales XML-RPC / bases de datos e IDs (VERSIÓN PÚBLICA)

**Última actualización:** 2026-04-18

Este documento es una versión **sanitizada** para poder publicarse en un repositorio sin exponer secretos ni datos personales.  
La versión interna (con detalles operativos puntuales) **no se versiona**: `documentacion/CREDENCIALES_Y_IDS_POR_BASE.md`.

## Entornos (FWCORP)

- **Productivo (scripts de este repo)**: `nakel.net.ar` → base típica `**master_dev`**
- **Desarrollo**: `dev.nakel.net.ar` → base típica `**master_test`** (u otra según `.env`)

> Nota: la base histórica **master_18** ya no se utiliza; los procedimientos nuevos deben asumir `**master_dev`** (o `master_test` solo cuando se acuerde operar contra dev).

## Usuario técnico (scripts)

- Login técnico usado por scripts (referencia): `**odoo@nakel.ar**`
- **Secretos (URLs/contraseñas/tokens)**: están fuera de este repo (por ejemplo en un `config_nakel.py` del entorno).  
**No** copiar/pegar credenciales a Markdown ni al código.

## IDs numéricos (entre bases de datos)

Los **IDs numéricos** de Odoo/PostgreSQL (por ejemplo `warehouse_id`, `location_id`, `res.groups`, IDs dentro de dominios de `ir.rule`) **son propios de cada base**.

- No asumir que un ID de `master_dev` coincide en `master_test` u otra copia.
- Preferir que los scripts resuelvan entidades por **código** (p. ej. `B1`, `CEN`) o por **rutas/nombres** (p. ej. `B1/Existencias`) en vez de “IDs fijos” en el código.
- En documentación/auditorías, si se citan IDs, **incluir siempre**: base (`master_dev`, `master_test`, etc.) y fecha de lectura.

## Comparar bases

Comparar bases sirve para validar **nombres** y **lógica de dominios**, pero no para copiar IDs entre documentos sin revalidar en la base destino.