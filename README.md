# `nakel_odoo` (FW-CORP / NAKEL)

Repositorio “paquete” para centralizar **customizaciones de Odoo NAKEL** que suelen cambiar y desplegarse juntas.

## Fuente de verdad

- **Este repositorio (`nakel_odoo`, remoto [`FW-CORP/nakel_odoo`](https://github.com/FW-CORP/nakel_odoo))** es la **única fuente de verdad** para lo que vive bajo su árbol (`addons/`, `qweb/`, `tools/`, `docs/`).
- **Migración progresiva:** el material Odoo/custom va **entrando acá** de a poco; otros `.git` o copias versionadas fuera de este árbol (p. ej. en un vault hermano) quedan **legacy / obsoletos** para esos contenidos: no ampliarlos; alinear o archivar cuando toque.
- **No duplicar** el mismo código o runbook en otros árboles con otro historial git: enlazar o clonar este repo y **trabajar aquí** para PRs, tags y despliegues.
- Las herramientas bajo `tools/` (incl. `tools/nak-ventas/`) siguen la **estructura y reglas** de este README (sin secretos, artefactos pesados fuera del índice donde corresponda).

## Estructura

- `addons/`: módulos Odoo (código Python/XML).
- `qweb/`: templates QWeb + scripts de sincronización/aplicación (si aplica).
- `tools/`: utilidades de despliegue, validación, migración.
  - `tools/nak-ventas/`: flujo NAK (cotizaciones `draft`) → traslado interno en Nakel SA `CEN/Existencias` → `CEN/Roturas 2` (script + doc cron desecho).
- `docs/`: runbooks y documentación operativa.

## Módulos (prioridad 1 / instalados en `master_dev`)

- `addons/nakel_picking` (`nakel_picking`)
- `addons/nakel_fix_pick` (`nakel_fix_pick`)
- `addons/nakel_wave_picking_link` (`nakel_wave_picking_link`)
- `addons/modulo_rg5329` (`modulo_rg5329`)

## Documentación de usuarios y permisos

- `docs/usuarios/` (permisos, grupos, estructuras, troubleshooting)
  - Incluye versión **sanitizada** de credenciales/entornos: `docs/usuarios/documentacion/CREDENCIALES_Y_IDS_POR_BASE.PUBLIC.md`

## Documentación de ventas

- `docs/ventas/` (listas de precios, preventas/inyección, PDV, comisiones, etiquetas, etc.)
  - Se excluyen artefactos generados (`OUT/`, `reportes/`, `.csv/.xlsx`) para mantener el repo liviano y público.

## Herramientas fiscales (ARCA Retenciones)

- `tools/arca-retenciones/` (SICORE / SIRCAR / PERCEIIBB + exportador Excel)
  - Se excluyen outputs (`out/`) y artefactos binarios para mantener el repo liviano.

## Fixes productivos (rollout)

- `tools/fix-facom/` (**Arreglo FACOM** en facturas de compra)
  - Ver `tools/fix-facom/RUNBOOK_PRODUCTIVO.md` (dry-run → batch chico → ejecución completa, con rollback por CSV)

## Reglas

- **Sin secretos** en git (`.env`, passwords, API keys, dumps).
- Evitar IDs hardcodeados entre bases (`master_18` vs `master_dev`).

