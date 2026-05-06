# Análisis consultivo: `apt` upgrades y posible impacto en Odoo

**Modo:** solo consulta (listados + simulación con `apt-get -s`).  
**No se aplicaron actualizaciones.**

## Contexto del servidor

- **Distro:** Ubuntu 22.04 (Jammy) con repos `jammy`, `jammy-updates`, `jammy-security`.
- **Python runtime:** `Python 3.10.12` (paquetes a actualizar: `python3.10*`, `libpython3.10*`).
- **Odoo (paquete Debian):** `odoo 18.0+e.20250205` (no aparece como actualizable desde repos de Ubuntu).
- **PostgreSQL:** `postgresql 14+238` (paquetes a actualizar: `postgresql-14`, `postgresql-client-14`, `libpq5`, `libpq-dev`).
- **wkhtmltopdf (binario en uso):** `/usr/local/bin/wkhtmltopdf` → `wkhtmltopdf 0.12.6.1 (with patched qt)` (OK para Odoo).
- **Kernel del host CT:** `6.8.12-2-pve` (Proxmox kernel). En simulación de `dist-upgrade` aparecen headers Ubuntu 5.15 como “nuevos”, típicamente **no relevantes** para CT sobre Proxmox, pero igual pueden instalarse si se ejecuta el upgrade.

## Qué paquetes se actualizarían (resumen)

### `apt-get -s upgrade`

- **172** paquetes a actualizar
- **0** nuevos
- **0** removidos
- **8** no actualizados
- Reporta **146** “standard security updates”

### `apt-get -s dist-upgrade`

- **178** a actualizar
- **5** nuevos (incluye `linux-headers-5.15.0-176*`, `systemd-hwe-hwdb`, `ubuntu-pro-client*`)
- **0** removidos
- **2** no actualizados
- Reporta **146** “standard security updates”

### Paquetes “retenidos” / no actualizados (según simulación)

En las simulaciones aparecen retenidos (puede variar entre `upgrade` y `dist-upgrade`):

- `libnetplan0`, `netplan.io` (y otros componentes de update-manager/UA tools en el output)

## Paquetes relevantes para Odoo (impacto)

### 1) PostgreSQL 14 (point release)

Se ve upgrade de:

- `postgresql-14` **14.18 → 14.22**
- `postgresql-client-14` **14.18 → 14.22**
- `libpq5` / `libpq-dev` **14.18 → 14.22**

**Riesgo:** normalmente bajo (patch release), pero implica **restart de PostgreSQL** para que la actualización tenga efecto → esto corta conexiones y Odoo puede mostrar “Bad Gateway” si coincide con tráfico.

### 2) Python 3.10 (patch release de Jammy)

Se ve upgrade de:

- `python3.10`, `python3.10-minimal`, `python3.10-dev`
- `libpython3.10*` **3.10.12-1~22.04.11 → 3.10.12-1~22.04.15**

**Riesgo:** bajo/medio. Es el mismo minor (3.10.12) con packaging updates. Odoo (paquete `odoo`) depende de muchas libs `python3-*`; estas actualizaciones suelen ser compatibles, pero **exigen reiniciar Odoo** para que los procesos carguen las libs nuevas.

### 3) OpenSSL / librerías TLS y HTTP

Se ve upgrade de:

- `openssl`
- `libssl3`, `libssl-dev`
- `curl`, `libcurl4`
- `libgnutls30`, `libssh-4`

**Riesgo:** bajo/medio. Cambios aquí pueden afectar integraciones (APIs, conexiones TLS), pero al ser updates de Ubuntu suelen ser “safe”. Requiere reinicio de servicios para que tomen la nueva librería.

### 4) systemd / udev / libc (base del sistema)

Se ve upgrade de:

- `systemd`, `systemd-sysv`, `systemd-timesyncd`, `libsystemd0`, `libpam-systemd`, `libnss-systemd`
- `udev`, `libudev1`
- `libc6`, `libc-bin`, `libc6-dev`

**Riesgo:** medio (operativo). No debería romper Odoo por compatibilidad, pero suele implicar **reinicios de servicios** y a veces **reboot recomendado** (dependiendo del host/CT).

### 5) SSH

Se ve upgrade de:

- `openssh-server`, `openssh-client`, `openssh-sftp-server`

**Riesgo:** bajo, pero operativo (siempre hacer en ventana controlada por si hay cambios de configuración o reinicio del daemon).

### 6) tzdata

Se ve upgrade de:

- `tzdata 2025b → 2026a`

**Riesgo:** bajo. Beneficia a Odoo (conversión de zonas horarias). Puede requerir reinicio de procesos para que tomen la base nueva.

## Conflictos de compatibilidad esperables vs Odoo

Con lo visto, **no aparecen upgrades directos del paquete `odoo`**, solo librerías del SO (Python, OpenSSL, PostgreSQL client/server, systemd). Los conflictos típicos a vigilar en ambientes Odoo son:

- **PostgreSQL restart** durante horas pico.
- **Cambios de libs criptográficas/HTTP** impactando integraciones externas (pagos, APIs, etc.).
- **Cambios de Python libs** si hay módulos custom que importan paquetes fuera del stack estándar.

En Jammy, este set de updates luce como **security/maintenance** usual y, en general, es **compatible** con Odoo 18 empaquetado como `.deb`.

## Recomendación operativa (para documentar)

- **Preferir `upgrade` sobre `dist-upgrade`** si el objetivo es solo parches y minimizar “nuevos paquetes”.
- Planificar una ventana donde puedas reiniciar al menos:
  - `postgresql`
  - `odoo`
  - y verificar conectividad por proxy (evitar 502).
- Si se ejecuta `dist-upgrade`, revisar por qué instala headers Ubuntu (`linux-headers-5.15*`) en un CT Proxmox; suele ser **innecesario**.

## Evidencia usada

- `apt list --upgradable`
- `apt-get -s upgrade`
- `apt-get -s dist-upgrade`
- `apt-cache policy` de paquetes clave
- `dpkg-query -W` para versiones actuales

