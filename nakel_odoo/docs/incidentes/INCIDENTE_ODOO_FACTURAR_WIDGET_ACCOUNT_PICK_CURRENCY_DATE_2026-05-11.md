# Incidente: no deja facturar por widget faltante `account_pick_currency_date` (OwlError)

**Fecha:** 2026-05-11  
**Entorno:** `nakel.net.ar` (`master_dev`)  
**Área:** Ventas → Facturación (crear/abrir factura desde cotización)

## Síntoma

Al intentar **facturar una cotización** aparece:

- `UncaughtPromiseError > OwlError`
- `KeyNotFoundError: Cannot find key "account_pick_currency_date" in the "view_widgets" registry`

## Causa (probable)

La vista estándar de factura/asiento (`account.view_move_form`) incluye:

- `<widget name="account_pick_currency_date" .../>`

Ese widget es un **componente JS** del módulo `account` que debe registrarse en el registry `view_widgets` (frontend).  
El error indica **desalineación** entre:

- **XML de la vista** (pide el widget), y
- **assets JS cargados** (no contienen el registro del widget).

Esto suele pasar tras un upgrade/deploy donde:

- se actualizó el módulo `account` (views) pero **no** se reconstruyeron/invalidaron assets en el cliente/proxy, o
- hay **código en disco** desincronizado (otra copia de addons antes en `addons_path`), o
- quedó cacheado un bundle viejo (`web.assets_web.min.js`) en reverse-proxy / navegador.

## Verificación rápida

1. Confirmar que la vista que lo referencia es `account.view_move_form`:
   - `ir.ui.view` (`xml_id = account.view_move_form`) contiene `account_pick_currency_date` en `arch_db`.
2. En el navegador, abrir Odoo con `?debug=assets` y buscar si el JS del widget se carga (debería estar en `addons/account/static/src/...`).
3. Probar recarga dura / borrar caché (si es solo un usuario).

## Mitigación

- **Recarga dura** del navegador (Ctrl+Shift+R) y/o limpiar caché del sitio.
- Si afecta a todos los usuarios: **reiniciar Odoo** y forzar regeneración de assets (según runbook de deploy), o invalidar caché del reverse proxy/CDN.

## Cierre / caso observado

- **Orden afectada**: `S04169`
- **Resultado**: desde otra PC se pudo **confirmar factura** y facturar correctamente.
- **Interpretación**: el problema era **local al cliente** (caché del bundle `/web/assets/.../web.assets_web.min.js`), no del backend.

## Workaround (si urge operar)

Crear una vista heredada que **oculte** el widget `<widget name="account_pick_currency_date">` en `account.view_move_form`.  
Se pierde el picker de fecha para tipo de cambio, pero permite abrir/facturar.

