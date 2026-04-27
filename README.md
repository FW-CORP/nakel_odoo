# `nakel_odoo` (FW-CORP / NAKEL)

Repositorio “paquete” para centralizar **customizaciones de Odoo NAKEL** que suelen cambiar y desplegarse juntas.

## Estructura

- `addons/`: módulos Odoo (código Python/XML).
- `qweb/`: templates QWeb + scripts de sincronización/aplicación (si aplica).
- `tools/`: utilidades de despliegue, validación, migración.
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

