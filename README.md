# `nakel_odoo` (FW-CORP / NAKEL)

Repositorio “paquete” para centralizar **customizaciones de Odoo NAKEL** que suelen cambiar y desplegarse juntas.

## Estructura

- `addons/`: módulos Odoo (código Python/XML).
- `qweb/`: templates QWeb + scripts de sincronización/aplicación (si aplica).
- `tools/`: utilidades de despliegue, validación, migración.
- `docs/`: runbooks y documentación operativa.

## Reglas

- **Sin secretos** en git (`.env`, passwords, API keys, dumps).
- Evitar IDs hardcodeados entre bases (`master_18` vs `master_dev`).

