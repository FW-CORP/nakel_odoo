# Nakel — Informe fiscal carga diferida (`nakel_tax_report_lazy`)

Módulo **Odoo 18** (Enterprise: `account_reports`). PoC para reducir el tamaño del **primer** JSON-RPC del **informe fiscal genérico** cuando la jerarquía completa en una sola respuesta genera payloads muy grandes (típico en acceso **WAN**: timeouts de proxy, `ERR_CONTENT_LENGTH_MISMATCH`, navegador inestable).

## Problema que ataca

- La UI carga el informe con `get_report_information` / `get_report_information_readonly`, que incluye **todas** las líneas dinámicas en un único payload JSON.
- En informes con muchos impuestos / niveles, ese JSON puede superar decenas de MB.
- Por **LAN** a veces “llega”; por **WAN** la cadena Traefik / ISP / cliente puede **cerrar la conexión** o el navegador falla aunque Odoo haya terminado de calcular (en log a veces igual figura **HTTP 200**).

## Qué hace este módulo

- **Hereda** el modelo abstracto `account.generic.tax.report.handler` y redefine `_get_dynamic_lines` para que, en modo normal:
  - El **primer** render solo envíe las líneas de **nivel superior** (p. ej. **Ventas** / **Compras**).
  - Las líneas inferiores (impuestos, y en variantes con más agrupación, cuentas) se cargan al **desplegar** la fila, vía `get_expanded_lines` y el método `_report_expand_unfoldable_line_generic_tax_lazy`.
- Afecta las **tres variantes** que usan ese handler:
  - Agrupación por defecto.
  - Variantes **Cuenta → Impuesto** y **Impuesto → Cuenta** (mismo árbol de herencia en Enterprise).

## Qué **no** modifica (importante)

- **No** aplica al **Libro de IVA argentino** ni a otros informes que usen `l10n_ar.tax.report.handler`. Esos van por otro código; para WAN en el libro IVA ver el módulo hermano **`nakel_vat_book_wan`**.
- **No** elimina el costo de la **agregación SQL inicial** en la primera carga: el servidor sigue calculando la jerarquía para armar totales del nivel superior; lo que baja fuerte es el **tamaño de la respuesta HTTP**, no necesariamente el tiempo de CPU del primer request.
- Cada **expansión** vuelve a leer la jerarquía en servidor (PoC simple y seguro; optimizable después con caché si hiciera falta).

## Comportamiento desactivado automáticamente (vuelve al estándar Odoo)

- `export_mode` distinto de “solo pantalla” (impresión / export a archivo según flujo del cliente).
- `unfold_all` activo.
- Parámetro del sistema `nakel_tax_report_lazy.disable` en `True` / `1` / `yes`.

## Dependencias

- `account_reports` (Odoo Enterprise).

## Instalación / actualización

```bash
# Ajustar -c y -d según el entorno
sudo -u odoo /usr/bin/odoo -c /etc/odoo/odoo.conf -d NOMBRE_BD -i nakel_tax_report_lazy --stop-after-init
# o solo actualizar datos/código:
sudo -u odoo /usr/bin/odoo -c /etc/odoo/odoo.conf -d NOMBRE_BD -u nakel_tax_report_lazy --stop-after-init
```

Reiniciar el servicio Odoo si corresponde tras desplegar código.

## Configuración

| Clave (Parámetros del sistema) | Efecto |
|--------------------------------|--------|
| `nakel_tax_report_lazy.disable` | `False` (por defecto al instalar): carga diferida **activa**. `True` o `1`: comportamiento **estándar** del informe fiscal genérico. |

El registro se crea con `data/system_parameters.xml` (`noupdate="1"`): si ya lo editaste en producción, una actualización del módulo **no** pisa tu valor.

## Impacto en usuarios

- **Positivo:** menos datos en el primer load; menos cortes por WAN; despliegue progresivo familiar si ya usan otros informes con “cargar más”.
- **Trade-off:** más llamadas RPC al expandir; en la primera apertura no se ven todos los impuestos hasta desplegar **Ventas** / **Compras** (y niveles siguientes en variantes con más columnas).

## Mantenimiento / riesgos

- Toca lógica de **Enterprise** (`account_reports` / handler genérico). Tras **actualizar Odoo**, conviene probar el informe fiscal genérico y las tres variantes.
- Si aparece un módulo fantasma `account_tax_report_lazy` en `ir_module_module` (nombre viejo), eliminar ese registro en BD para evitar errores de “inconsistent states” (no forma parte de este paquete).

## Autor y licencia

- **FWCORP** — licencia **LGPL-3** (alineada al manifiesto).
