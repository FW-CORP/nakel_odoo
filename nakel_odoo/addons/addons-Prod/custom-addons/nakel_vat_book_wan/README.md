# Nakel — Libro IVA: límite vista previa WAN (`nakel_vat_book_wan`)

Módulo **Odoo 18** (Enterprise: `l10n_ar_reports`). Ajusta el **`load_more_limit`** del informe **Libro de IVA argentino** para que la **vista previa web** no envíe miles de filas en un solo JSON-RPC (causa típica de **timeout**, **proxy** o **`ERR_CONTENT_LENGTH_MISMATCH`** por **WAN**).

## Problema que ataca

- El dato estándar del Libro de IVA trae **`load_more_limit` = 4000**: hasta 4000 comprobantes en pantalla.
- Cada fila tiene **muchas columnas** (gravado, IVA 10,5 %, 21 %, percepciones, etc.) → el JSON de `get_report_information_readonly` crece muy rápido (órdenes de **decenas de MB**).
- Por **LAN** suele completarse; por **WAN** el camino hasta el navegador es más frágil: el usuario ve timeout o errores de conexión aunque Odoo registre **200** en `werkzeug`.

Este módulo **no** sustituye a `nakel_tax_report_lazy`: aquel aplica solo al **informe fiscal genérico** (`account.generic.tax.report.handler`). El Libro de IVA usa **`l10n_ar.tax.report.handler`**; este módulo actúa **solo** sobre ese informe.

## Qué hace este módulo

- En la carga de datos (`data/vat_book_limits.xml`) ejecuta un `write` sobre el `account.report` con xmlid estándar `l10n_ar_reports.l10n_ar_vat_book_report`.
- Fija **`load_more_limit = 400`** (valor pensado para equilibrio **WAN vs usabilidad** en vista previa).

### Vista previa vs export

- **Vista previa (navegador):** como mucho **400** líneas (más la fila resumen de “+N líneas no mostradas” que ya implementa `l10n_ar_reports` cuando se trunca).
- **Export PDF / XLSX / ZIP del Libro de IVA:** sigue incluyendo el **contenido completo** según el motor estándar (no limitado por este `load_more_limit` en modo export).

## Cómo cambiar el límite

1. **Por código (recomendado en repo):** editar `data/vat_book_limits.xml` y cambiar el valor `400`; luego `-u nakel_vat_book_wan`.
2. **Por interfaz (modo desarrollador):** abrir el registro `account.report` del Libro de IVA y ajustar el campo **Load More Limit** / límite de carga.
3. **Por SQL (emergencia):** actualizar `load_more_limit` en `account.report` para ese informe (coherente con el `id` / xmlid del libro).

## Dependencias

- `l10n_ar_reports` (localización argentina informes, Enterprise).

## Instalación / actualización

```bash
sudo -u odoo /usr/bin/odoo -c /etc/odoo/odoo.conf -d NOMBRE_BD -i nakel_vat_book_wan --stop-after-init
# o
sudo -u odoo /usr/bin/odoo -c /etc/odoo/odoo.conf -d NOMBRE_BD -u nakel_vat_book_wan --stop-after-init
```

## Impacto en usuarios

| Aspecto | Efecto |
|--------|--------|
| Usuarios que solo miran pantalla | Ven como máximo **400** movimientos en preview; el aviso azul de líneas omitidas puede aparecer antes. |
| Contabilidad que exporta | **Sin cambio** en totales exportados; el archivo completo sigue disponible. |
| Rendimiento WAN | Menor tamaño de respuesta → menos timeouts y menos cortes de cuerpo HTTP. |

## Infraestructura complementaria

Si tras bajar el límite aún hay cortes, revisar **Traefik** (timeouts, buffering, compresión) y el bus **WebSocket** (errores `SerializationFailure` en logs no son este módulo, pero empeoran la sensación de “conexión inestable”).

## Mantenimiento / riesgos

- Una **actualización mayor** de `l10n_ar_reports` podría redefinir datos del informe; conviene tras upgrade verificar que `load_more_limit` siga siendo el deseado (el XML de este módulo puede volver a aplicarse con `-u nakel_vat_book_wan`).
- Si en la misma base se edita manualmente el límite y luego se fuerza una recarga del XML sin `noupdate`, el valor podría sobrescribirse según cómo esté definido el dato; en la práctica este módulo usa un `function write` en XML que se ejecuta al instalar/actualizar el módulo.

## Autor y licencia

- **FWCORP** — licencia **LGPL-3** (alineada al manifiesto).
