# Checklist de mantenimiento / upgrade (FWCORP Odoo)

**Objetivo:** ejecutar cambios con validación rápida y evidencias en logs.  
**Ámbito:** mover addons custom + `apt upgrade` + upgrade `.deb` de Odoo.  

## Convenciones (qué registrar en cada etapa)

- **Hora inicio/fin** (UTC-3) y responsable.
- **Versión Odoo** (antes/después): `odoo 18.0+e.YYYYMMDD`.
- **Versiones clave** (antes/después):
  - PostgreSQL: `postgresql-14`
  - `wkhtmltopdf --version` (esperado: `0.12.6.1 (with patched qt)`)
- **Logs a revisar** (por ventana de tiempo):
  - `/var/log/odoo/odoo-server.log`
  - `journalctl -u odoo`

## 0) Pre-flight (antes de tocar nada)

- **Backup**:
  - BD: dump/snapshot consistente.
  - Addons custom: copia de `/opt/odoo/custom-addons` y de los custom hoy mezclados en `dist-packages`.
  - Config: `/etc/odoo/odoo.conf` (ya con timestamp).
- **Confirmar `addons_path`** contiene `/opt/odoo/custom-addons`.
- **Confirmar salud básica**:
  - Login web
  - Inventario → Transferencias (lista + abrir 1)
  - Productos → Productos (lista + abrir 1)
  - POS (si aplica)
  - Factura/PDF (imprimir 1)

**Qué mirar en logs (si falla):**
- `ERROR`, `CRITICAL`, `Traceback`
- `worker timeout`, `Killed`, `limit_memory`
- `Bad Gateway` suele ser proxy, pero Odoo suele mostrar saturación en workers/tiempos.

## 1) Mover addons custom a `/opt/odoo/custom-addons`

### 1.1 Alcance (los detectados en `dist-packages`)

Mover (según relevamiento):
- `droggol_theme_common`
- `theme_prime`
- `modulo_rg5329`
- `nakel_fix_pick`
- `nakel_picking`
- `nakel_wave_picking_link`
- `purchase_flete_markup`

### 1.2 Validación inmediata (post-move + reinicio Odoo)

- **Odoo arranca** (service `active`) y web responde.
- **Apps**:
  - Ajustes → Aplicaciones → “Actualizar lista” (modo dev).
  - Ver que los módulos anteriores siguen “instalados” (no desaparecen).
- **Flujos críticos**:
  - Inventario → Transferencias → abrir/confirmar (sin ejecutar movimientos reales si no querés).
  - Productos → lista → abrir.
  - POS: abrir sesión / sincronizar (si aplica).
  - Facturación: abrir una factura y **descargar PDF**.

**Logs (filtros típicos):**
- `odoo.modules.loading` (carga de módulos)
- `ERROR`/`Traceback` con nombres de tus módulos: `nakel_`, `modulo_rg5329`, `theme_`.

## 2) Actualización de SO: `apt-get update` + `apt-get upgrade` (no `dist-upgrade`)

### 2.1 Qué esperar

- Se actualizan libs base (OpenSSL, libc, systemd), Python packaging, y **PostgreSQL 14 point release**.
- Es normal que requiera reinicio de servicios para aplicar cambios.

### 2.2 Validación inmediata (post-upgrade + reinicios controlados)

- **Servicios**:
  - PostgreSQL operativo.
  - Odoo operativo (y proxy si lo administrás en el mismo host).
- **Web**:
  - Login
  - Inventario / Productos
  - PDF (factura) + QR/imagen
  - POS sync (si aplica)

**Logs a buscar:**
- PostgreSQL: desconexiones durante restart (esperable durante ventana).
- Odoo: `OperationalError`, `could not connect`, `psycopg2`.

## 3) Upgrade de Odoo con `.deb` (18.0+e.20260424)

### 3.1 Pre-check (antes)

- Confirmar que custom ya está fuera de `dist-packages`.
- Confirmar que el `.deb` fue analizado (ver `preupdate/ANALISIS_DEB_vs_PRODUCCION.md`).

### 3.2 Validación inmediata (post-install + reinicio Odoo)

- **Odoo version** en log arranque coincide con el nuevo build.
- **Web**:
  - Login
  - Inventario / Productos
  - PDF factura (ver QR AFIP y que no haya 500 en `/report/barcode`)
  - POS: sincronización (al menos 1 operación simple)
- **Módulos**:
  - Revisar “Apps → Actualizar lista” (si hace falta).
  - Actualizar solo módulos necesarios (si aplica).

**Logs a buscar (muy importante):**
- `TypeError: ReportController.report_barcode()` (debe ser **0**)
- `wkhtmltopdf ... InternalServerError` (debe ser **0**)
- `ERROR` durante `odoo.modules.loading` / `registry`


## 3-a)

 Aplicar correccion fix-facom


## 4) Post-check (24–48h)

- Monitorear:
  - Errores 500/502 reportados por usuarios.
  - `worker timeout` / `limit_memory` / restarts.
  - Volumen de 404 de bots (si llega a Odoo, considerar rate-limit en Traefik).

## 5) Rollback (si algo sale mal)

- **Si falla después del move de addons:** volver a la copia del filesystem de addons + reiniciar.
- **Si falla después de `apt upgrade`:** rollback típico es snapshot/backup (no trivial “desinstalar” updates).
- **Si falla después del `.deb`:** reinstalar versión anterior del paquete o rollback por snapshot + BD.

