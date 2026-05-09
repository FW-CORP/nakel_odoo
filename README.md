# `nakel_odoo` (FW-CORP / NAKEL)

Repositorio “paquete” para centralizar **customizaciones de Odoo NAKEL** que suelen cambiar y desplegarse juntas.

## Fuente de verdad

- **Este repositorio (`nakel_odoo`, remoto [`FW-CORP/nakel_odoo`](https://github.com/FW-CORP/nakel_odoo))** es la **única fuente de verdad** para lo que vive bajo su árbol (`addons/`, `qweb/`, `tools/`, `docs/`).
- **Dos remotos en el mismo clon (vault en disco):** además de GitHub puede existir un remoto **Forgejo** privado (`cursor_nakel`) con el **árbol amplio** del vault. Flujo detallado: [`docs/desarrollo/GIT_REMOTES_GITHUB_FORGEJO.md`](docs/desarrollo/GIT_REMOTES_GITHUB_FORGEJO.md).
- **Migración progresiva:** el material Odoo/custom va **entrando acá** de a poco; otros `.git` o copias versionadas fuera de este árbol (p. ej. en un vault hermano) quedan **legacy / obsoletos** para esos contenidos: no ampliarlos; alinear o archivar cuando toque.
- **No duplicar** el mismo código o runbook en otros árboles con otro historial git: enlazar o clonar este repo y **trabajar aquí** para PRs, tags y despliegues.
- Las herramientas bajo `tools/` (incl. `tools/nak-ventas/`) siguen la **estructura y reglas** de este README (sin secretos, artefactos pesados fuera del índice donde corresponda).

## Estructura

- `addons/`: módulos Odoo (código Python/XML).
- `qweb/`: templates QWeb + scripts de sincronización/aplicación (si aplica).
- `tools/`: utilidades de despliegue, validación, migración.
  - `tools/nak-ventas/`: flujo NAK (cotizaciones `draft`) → traslado interno en Nakel SA `CEN/Existencias` → `CEN/Roturas 2` (script + doc cron desecho).
- `docs/`: runbooks y documentación operativa.
  - Incidentes / postmortems: `docs/incidentes/` (p. ej. upgrade `nakel_wave_picking_link` y OV, 2026-04-29).

### ¿Por qué existe `nakel_odoo/` *dentro* del repo [`FW-CORP/nakel_odoo`](https://github.com/FW-CORP/nakel_odoo)?

El nombre del repositorio y el de una carpeta coinciden: en la raíz del proyecto aparece **`nakel_odoo/`** además de `addons/`, `docs/`, `tools/`, etc. Eso es **histórico** (paquete / mirror del vault en Obsidian, migraciones y convenciones viejas).

Dentro de esa carpeta puede existir otra **`nakel_odoo/nakel_odoo/`**: es un **subárbol duplicado parcial** (misma forma de `addons/`, `docs/`, `tools/`…), no un segundo repositorio Git. **No es la convención deseable para trabajo nuevo.**

| Dónde trabajar (preferido) | Notas |
|----------------------------|--------|
| Raíz del repo: `addons/`, `docs/`, `tools/`, `qweb/` | Es lo que muestra GitHub en `main` junto a `README.md` y submódulo `usuarios/`. |
| Primera carpeta homónima: `nakel_odoo/` (addons, docs, qweb, tools…) | Mantener solo si ya hay flujos o rutas que la usan; evitar **añadir** un tercer nivel `nakel_odoo/nakel_odoo/`. |

Eliminar o fusionar el nivel interno implica comparar miles de archivos y actualizar enlaces; si se hace, debe ser un **cambio planificado** (PR aparte), no al vuelo.

## Módulos (prioridad 1 / instalados en `master_dev`)

- `addons/nakel_picking` (`nakel_picking`)
- `addons/nakel_fix_pick` (`nakel_fix_pick`)
- `addons/nakel_wave_picking_link` (`nakel_wave_picking_link`)
- `addons/modulo_rg5329` (`modulo_rg5329`)

También en `addons/` (p. ej. permisos / UX): `nakel_sale_margin` — restringe margen y `%` a un grupo y evita el `(` huérfano junto a totales cuando no hay permiso.

## Documentación de usuarios y permisos

- `docs/usuarios/` (permisos, grupos, estructuras, troubleshooting)
  - Incluye versión **sanitizada** de credenciales/entornos: `docs/usuarios/documentacion/CREDENCIALES_Y_IDS_POR_BASE.PUBLIC.md`

## Documentación de ventas

- `docs/ventas/` (listas de precios, preventas/inyección, PDV, comisiones, etiquetas, etc.)
  - Se excluyen artefactos generados (`OUT/`, `reportes/`, `.csv/.xlsx`) para mantener el repo liviano y público.

## Herramientas fiscales (ARCA Retenciones)

- `tools/arca-retenciones/` (SICORE / SIRCAR / PERCEIIBB + exportador Excel)
  - Se excluyen outputs (`out/`) y artefactos binarios para mantener el repo liviano.

## Diagnóstico fiscal (liquidación / IIBB sufrido)

- `tools/tax_settlement_diagnostico/` — scripts **solo lectura** (XML-RPC): diagnóstico retenciones / acción 1065 y dependencias de módulo. Ver README en esa carpeta.
- `addons/nakel_fix_iibb_settlement_name/` — parche defensivo (`get_pos_and_number` EE) para `False`/`None` en certificado / nombre; ver `docs/incidentes/IIBB_SUFRIDO_LIQUIDACION_WITHHOLDING_NAME_master_dev.md`.

## Fixes productivos (rollout)

- `tools/fix-facom/` (**Arreglo FACOM** en facturas de compra)
  - Ver `tools/fix-facom/RUNBOOK_PRODUCTIVO.md` (dry-run → batch chico → ejecución completa, con rollback por CSV)

## Reglas

- **Sin secretos** en git (`.env`, passwords, API keys, dumps).
- Evitar IDs hardcodeados entre bases (`master_18` vs `master_dev`).

