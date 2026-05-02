# Cómo actualizar nakel_picking correctamente

## Orden correcto (importante)

Odoo **carga el código Python en memoria** al iniciar. Si solo copias archivos y haces "Actualizar" en la UI, **puede que siga usando el código viejo** hasta reiniciar.

### Pasos en el orden correcto

```
1. DESPLEGAR (copiar archivos al servidor)
2. PARAR Odoo
3. ACTUALIZAR el módulo (o reiniciar Odoo)
4. ARRANCAR Odoo
```

---

## Opción A: Servidor con systemd (recomendado)

```bash
# 1. Conectar al servidor
ssh odoo-ct-nakel   # o el host que uses (ej. 10.5.0.28)

# 2. Parar Odoo
sudo systemctl stop odoo

# 3. Actualizar el módulo (usa la config de odoo.conf)
sudo -u odoo odoo -c /etc/odoo/odoo.conf -u nakel_picking -d master_18 --stop-after-init

# 4. Arrancar Odoo
sudo systemctl start odoo
```

### Nota DEV (dev.nakel.net.ar)

En **DEV** la base de datos usada es **`master_test`** (copia nueva). Al actualizar, usar `-d master_test`:

```bash
sudo -u odoo odoo -c /etc/odoo/odoo.conf -u nakel_picking -d master_test --stop-after-init
```

**Importante:** El paso 3 debe usar `-c /etc/odoo/odoo.conf` para que Odoo tenga las credenciales de PostgreSQL. Sin eso puede fallar con `fe_sendauth: no password supplied`.

---

## Opción B: Desde tu máquina (deploy.sh + SSH)

```bash
# 1. Desplegar (copiar archivos)
cd /ruta/al/nakel_picking   # ej. vault: nakel/nakel_picking (raíz del addon, donde está deploy.sh)
./deploy.sh odoo-ct-nakel

# 2. Actualizar en el servidor (todo en uno)
ssh -t odoo-ct-nakel "sudo systemctl stop odoo && sudo -u odoo odoo -c /etc/odoo/odoo.conf -u nakel_picking -d master_18 --stop-after-init && sudo systemctl start odoo"
```

### Usar credenciales SSH desde `.env` (recomendado)

En el vault, podés centralizar el acceso SSH al LXC de `env.nakel.net.ar` en:

- `/media/klap/raid5/cursor_files/nakel/.env`

Variables sugeridas:

- `NAKEL_ENV_SSH_HOST`
- `NAKEL_ENV_SSH_USER`
- `NAKEL_ENV_SSH_PORT`
- `NAKEL_ENV_SSH_KEY_PATH`

Cargar variables en tu shell:

```bash
set -a
source /media/klap/raid5/cursor_files/nakel/.env
set +a
```

Ejemplo de conexión:

```bash
ssh -i "$NAKEL_ENV_SSH_KEY_PATH" -p "$NAKEL_ENV_SSH_PORT" "$NAKEL_ENV_SSH_USER@$NAKEL_ENV_SSH_HOST"
```

---

## Opción C: Solo desde la interfaz (cuándo funciona)

La UI **sí actualiza** el módulo, pero **solo si**:

1. Los archivos ya están copiados en el servidor (deploy previo)
2. Odoo se reinició después de copiar (para cargar el código nuevo)

Si copiaste archivos **sin reiniciar**, la UI "Actualizar" puede no aplicar los cambios de Python porque el proceso sigue con el código viejo en memoria.

**Recomendación:** Después de cada deploy, reinicia Odoo (`systemctl restart odoo`) y luego usa "Actualizar" en la UI si prefieres.

---

## Errores frecuentes

| Error | Causa | Solución |
|-------|-------|----------|
| `fe_sendauth: no password supplied` | Odoo no encuentra credenciales de PostgreSQL | Usar `-c /etc/odoo/odoo.conf` |
| `Address already in use` | Odoo ya está corriendo y lanzas otro proceso | Parar con `systemctl stop odoo` antes |
| BULTO sigue vacío tras actualizar | Código viejo en memoria | Parar Odoo → actualizar → arrancar |
| El módulo no aparece en Aplicaciones | Ruta no está en `addons_path` | Verificar en odoo.conf que la ruta del módulo esté incluida |

---

## Verificar que se aplicó la actualización

1. **Versión del módulo:** Ajustes → Aplicaciones → Nakel Picking → debe mostrar versión 18.0.1.7.0 (o la actual)
2. **Logs:** Al imprimir un lote, revisar que no haya errores en `/var/log/odoo/odoo-server.log`
3. **Reporte:** Imprimir un lote con productos que tengan bulto (ej. GUAYMALLEN NEGRO 24.10) y comprobar si la columna BULTO muestra "Bulto x40"
