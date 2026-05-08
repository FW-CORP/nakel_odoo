---
title: l10n_ar_edi_ux — Facturación electrónica Argentina (UX ARCA)
updated: 2026-05-05
instance: nakel.net.ar (Odoo 18 Enterprise)
maintainer_upstream: ADHOC SA
---

## Objetivo

Registrar en el repositorio **qué hace** el módulo **`l10n_ar_edi_ux`** (descripción comercial: *Argentinian Electronic Invoicing UX*), **prerrequisitos**, **configuración** relevante para FWCORP/Nakel y **incidencias** conocidas al activarlo.

Este archivo **no sustituye** el README del paquete en `addons_path`; sirve como memoria operativa del equipo cuando el módulo está en la jerarquía `adhoc` / `odoo-argentina` y no siempre hay carpeta versionada bajo `nakel_odoo/addons`.

## Alcance funcional (resumen)

- **Notas de crédito/débito:** campos de período asociado (`l10n_ar_afip_asoc_period_start` / `l10n_ar_afip_asoc_period_end`) cuando no hay factura relacionada, para reportes ARCA.
- **Vinculación de documentos:** mejor detección de documentos enlazados al validar NC/ND contra ARCA (incluye enlaces vía pedidos de venta).
- **Padrón ARCA:** lógica para consultar el padrón reutilizando el enfoque de `l10n_ar_edi` (Enterprise).
- **Diarios electrónicos:** acciones para obtener tipos de comprobante válidos según el web service, con mensajes más claros al usuario.
- **Exportación:** soporte a **permisos de embarque** en facturas electrónicas de exportación.
- **Contactos:** sincronización / actualización de datos de partner desde el padrón ARCA, con opción de formato **Title Case** vía parámetro del sistema.

## Auto-instalación

Según documentación ADHOC, el módulo puede **auto-instalar** cuando están instalados **`l10n_ar_ux`** y **`l10n_ar_edi`**.

## Prerrequisitos

| Módulo / requisito | Notas |
|--------------------|--------|
| `l10n_ar_ux` | Localización UX Argentina |
| `l10n_ar_edi` | Facturación electrónica (Enterprise) |
| `account_accountant` | Funcionalidades de contabilidad |
| Empresa con **CUIT** válido | Obligatorio para ARCA |
| Certificados / conexión ARCA | Configurados en `l10n_ar_edi` |

## Configuración opcional

### Title case en datos del padrón

**Ajustes → Técnico → Parámetros → Parámetros del sistema**

- **Clave:** `use_title_case_on_padron_afip`
- **Valor:** `False` para desactivar title case en datos traídos del padrón (por defecto suele ser comportamiento “bonito” tipo título).

### Permisos de embarque

**Contabilidad → Configuración → Argentina → Permisos de embarque** (Boarding Permissions).

Uso: facturas de exportación con concepto ARCA tipo **Productos / Exportación definitiva de bienes**, campo **Permiso de embarque**.

### Tipos de comprobante desde ARCA

**Contabilidad → Configuración → Diarios** → diario electrónico → acción para obtener tipos de documento válidos (mensajes orientados al usuario).

### NC/ND sin factura origen

En la nota, completar **inicio/fin de período asociado** cuando no exista factura relacionada; esos datos van en el envío electrónico ARCA.

## Uso — sincronización de partners

- **Individual:** formulario de contacto con CUIT → botón tipo **Actualizar desde ARCA** → revisar wizard.
- **Masivo:** asistente desde menú de Contactos (según versión del módulo).

### CUIT de prueba (ambientes test)

La documentación oficial ADHOC (`ws_sr_constancia_inscripción`) lista CUIT de prueba en la base de conocimiento de localización Argentina (sección *Padrón Datos Contacto*):

<https://www.adhoc.inc/odoo/action-7014/139/knowledge/2109>

## Versionado en entorno Nakel

En inventarios de módulos DEV apareció **`l10n_ar_edi_ux`** como **`18.0.1.0.0`** (ver `inventario/CHANGELOG_NAKEL_upgrade_18e_20250205_to_20260424.md`).

---

## Incidencia: instalación fallida — `LockNotAvailable` / lock timeout

### Síntoma

Al pulsar **Instalar** en Apps sobre `l10n_ar_edi_ux` (o actualización que cree FK nuevas):

```text
psycopg2.errors.LockNotAvailable: canceling statement due to lock timeout
```

Traza típica: fallo en `registry.check_foreign_keys` → `sql.add_foreign_key` durante `button_immediate_install`.

### Interpretación

No es un error de Python del módulo en sí: **PostgreSQL canceló la sentencia** porque no pudo obtener el **bloqueo** necesario en el tiempo configurado (`lock_timeout`). Suele ocurrir en bases **con uso concurrente** (usuarios en UI, cron, procesos largos, otro worker instalando módulos).

### Qué hacer (operativo)

1. **Reintentar** en ventana de **baja actividad** (noche / sin cierres masivos).
2. Evitar en paralelo: **otras instalaciones/updates**, **restores**, jobs pesados de **contabilidad/stock**.
3. Si persiste, revisar en PostgreSQL sesiones bloqueantes (`pg_locks` / `pg_stat_activity`) con un DBA; a veces un worker queda colgado tras un error previo.
4. Solo en coordinación con infraestructura: valor de **`lock_timeout`** en el servidor (subirlo puntualmente para mantenimiento **no** siempre es la mejor solución; primero conviene liberar bloqueos).

### Alternativa de instalación

Donde sea aceptable para mantenimiento programado: **`odoo-bin -i l10n_ar_edi_ux`** con instancia en modo mantenimiento y sin usuarios concurrentes suele evitar el problema.

---

## Referencias upstream

- Mantenedor: **ADHOC SA** — incidencias en GitHub del repositorio correspondiente.
- Contribuciones: ver sitio ADHOC indicado en el manifiesto del módulo.
