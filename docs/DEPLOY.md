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

---

## Runbook: `addons_path` con ruta custom (dev / staging / productivo)

**Objetivo:** que Odoo cargue los módulos NAKEL desde un directorio **fuera** del árbol estándar de Debian (`/usr/lib/python3/dist-packages/odoo/addons`), sin mezclar código custom con paquetes del sistema.

### 1. Directorio en el servidor

- **Ruta canónica (deploy scripts):** `NAKEL_REMOTE_ADDONS_ROOT` → por defecto **`/opt/odoo/custom-addons`**.
- Cada módulo queda en un subdirectorio:  
  `/opt/odoo/custom-addons/nakel_picking/`, etc. (como hace `tools/deploy/deploy_addon.sh`).

En el host (SSH como operador con sudo):

```bash
sudo mkdir -p /opt/odoo/custom-addons
sudo chown -R odoo:odoo /opt/odoo/custom-addons
```

### 2. Configuración `odoo.conf`

- **Archivo típico:** `NAKEL_ODOO_CONF` → por defecto **`/etc/odoo/odoo.conf`**.
- Editar **`addons_path`**: lista **separada por comas**, **sin espacios** entre rutas (convención Odoo). Debe incluir:
  - las rutas **estándar** de addons de la instalación (suelen ser al menos la de `odoo/addons` y `addons` de la distro);
  - la **raíz custom** `/opt/odoo/custom-addons` (no hace falta un path por módulo: Odoo recorre subcarpetas).

Ejemplo **ilustrativo** (las rutas exactas dependen del servidor; **no** copiar ciegamente):

```ini
[options]
addons_path = /usr/lib/python3/dist-packages/odoo/addons,/usr/lib/python3/dist-packages/addons,/opt/odoo/custom-addons
```

**Comprobar** en el servidor qué paths usa hoy el servicio (antes de tocar):

```bash
sudo grep -E '^addons_path' /etc/odoo/odoo.conf
# o, si el unit pasa -c:
systemctl cat odoo
```

### 3. Reinicio del servicio

Tras guardar `odoo.conf`:

```bash
sudo systemctl restart odoo
# nombre alternativo: NAKEL_ODOO_SERVICE (ej. odoo, odoo18, etc.)
```

### 4. Verificación en Odoo (UI)

1. **Aplicaciones** → **Actualizar lista de aplicaciones** (o equivalente en la versión).
2. Los módulos cuyo `__manifest__` esté bajo `/opt/odoo/custom-addons/<modulo>` deberían listarse.
3. Si el módulo no aparece: en **Modo desarrollador**, revisar **Aplicaciones** y el mensaje de carga, o logs (`journalctl -u odoo -f` / `tail` del log Odoo).

### 5. Actualizar código del módulo (CLI)

Copiar/actualizar archivos en `/opt/odoo/custom-addons/<modulo>/` (o usar `deploy_addon.sh` desde el repo) y luego, con la **misma** `-c` y base correcta:

```bash
sudo systemctl stop odoo
sudo -u odoo odoo -c /etc/odoo/odoo.conf -u <modulo> -d <base_datos> --stop-after-init
sudo systemctl start odoo
```

(Ver también `addons/nakel_picking/ACTUALIZACION_CORRECTA.md`: **dev.nakel** suele usar base **`master_test`**, productivo **`master_dev`**, etc.)

### 6. Entornos (dev / staging / productivo)

- **Misma idea** en `dev.nakel`, `staging.nakel` y productivo: `addons_path` + árbol bajo `/opt/odoo/custom-addons` (o variable equivalente en cada host).
- **Antes de productivo:** validar en **staging** (y si aplica en **dev**) que la lista de aplicaciones ve los módulos, que `-u` corre sin error y que no chocan rutas con otra instancia en el mismo LXC/VM.
- **Backup:** copia de `odoo.conf` previa y, si aplica, snapshot/backup de la BD antes de cambios masivos.

### 7. Problemas frecuentes

| Síntoma | Causa probable |
|--------|-----------------|
| El módulo no aparece en Aplicaciones | `addons_path` no incluye el directorio raíz del custom, o el servicio no se reinició |
| `fe_sendauth` al usar `odoo -u` en CLI | Falta `-c /etc/odoo/odoo.conf` (credenciales PG) |
| Código Python viejo tras “Actualizar” en UI | Hace falta **reiniciar** Odoo tras desplegar archivos (ver runbook de actualización del módulo) |

Referencias en repo: `tools/deploy/deploy_addon.sh` (variables `NAKEL_*`), y en `nakel_picking/UPGRADE.md` / `ACTUALIZACION_CORRECTA.md` (orden stop → `-u` → start).

