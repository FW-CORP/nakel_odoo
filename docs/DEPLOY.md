# Deploy (NAKEL Odoo)

## Objetivo

Unificar el despliegue de módulos custom de NAKEL a los servidores Odoo, evitando scripts duplicados por módulo.

## Deploy de un módulo

Desde la raíz del repo:

```bash
tools/deploy/deploy_addon.sh <module_name> [host] [db]
```

Ejemplos:

```bash
tools/deploy/deploy_addon.sh nakel_picking odoo@10.5.0.41 master_dev
tools/deploy/deploy_addon.sh nakel_fix_pick odoo@10.5.0.41 master_dev
```

## Deploy del “pack” (master_dev)

```bash
tools/deploy/deploy_all_master_dev.sh [host] [db]
```

## Variables útiles

- `NAKEL_REMOTE_ADDONS_ROOT` (default `/opt/odoo/custom-addons`)
- `NAKEL_ODOO_CONF` (default `/etc/odoo/odoo.conf`)
- `NAKEL_ODOO_SERVICE` (default `odoo`)
- `NAKEL_ENV_SSH_KEY_PATH` / `NAKEL_ENV_SSH_PORT`

## Nota sobre rutas antiguas

Algunos scripts legacy copiaban módulos a rutas del estilo `/usr/lib/python3/dist-packages/odoo/addons/...`.
El enfoque recomendado para custom addons es un árbol dedicado como `/opt/odoo/custom-addons/` y que el
`addons_path` de Odoo incluya ese root.

