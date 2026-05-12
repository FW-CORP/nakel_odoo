# PDV AFIP vs diarios de venta (Odoo) — referencia **master_dev**

Documento de referencia para **FWCORP / Nakel**: qué es cada identificador y cómo están cargados los puntos de venta en la base **master_dev** (Odoo 18 + localización AR). Útil para informes CC, comisiones y filtros por diario.

**Fecha de extracción:** 2026-05-11 (consulta MCP `account.journal`, `type = sale`).

---

## Conceptos (no mezclar)

| Concepto | Modelo / campo | Uso |
|----------|------------------|-----|
| **ID interno Odoo** | `account.journal.id` | Clave primaria en PostgreSQL; relaciones Many2one, XML IDs de datos, etc. **No** es el número de AFIP. |
| **Número de punto de venta AFIP (ARCA/AFIP)** | `account.journal.l10n_ar_afip_pos_number` | Dato fiscal para numeración y CAE; es el “PV” que coincide con lo registrado ante AFIP. |
| **Código del diario** | `account.journal.code` | Código corto en Odoo (convención interna); puede parecerse al PV pero **no** es la fuente de verdad fiscal. |
| **Compañía** | `account.journal.company_id` | Misma configuración de diarios puede repetirse en otra compañía con otros `id`. |

Regla práctica: para alinear criterios con “solo Central / PV 50” hay que filtrar por **`l10n_ar_afip_pos_number`** o por el **diario** cuyo PV AFIP sea 50, no por el `id` 9 del diario (ese `id` puede cambiar en otra base o tras recrear datos).

---

## Nakel SA (`res.company` id **1**)

Diarios `type = sale` en master_dev:

| `journal.id` | Nombre | `code` | `l10n_ar_afip_pos_number` | `l10n_ar_afip_pos_system` |
|--------------|--------|--------|---------------------------|---------------------------|
| 9 | FACT NAKEL CENTRAL | 0050 | **50** | RAW_MAW |
| 44 | Facturación Electrónica B1C1 | 00051 | 51 | RAW_MAW |
| 45 | Facturación Electrónica B1C2 | 00052 | 52 | RAW_MAW |
| 46 | Facturación Electrónica B2C1 | 00053 | 53 | RAW_MAW |
| 47 | Facturación Electrónica B2C2 | 00054 | 54 | RAW_MAW |
| 48 | Facturación Electrónica B3C1 | 00055 | 55 | RAW_MAW |
| 49 | Facturación Electrónica B3C2 | 00056 | 56 | RAW_MAW |
| 52 | Facturación Electrónica B4C1 | 00057 | 57 | RAW_MAW |
| 60 | Facturación Electrónica B4C2 | 00058 | 58 | RAW_MAW |
| 21 | Facturación OFFLINE | FACTO | 1 | — |
| 78 | Facturación Deudores por Venta migración | 00404 | **404** | — |

**Central:** diario **“FACT NAKEL CENTRAL”**, PV AFIP **50**, `journal.id` **9** en esta base.

**Migración deudores:** diario **78**, PV AFIP **404** (no confundir con el código `00404` del diario ni con el PV 50).

---

## Nak — compañía `res.company` id **2**

| `journal.id` | Nombre | `code` | `l10n_ar_afip_pos_number` | `l10n_ar_afip_pos_system` |
|--------------|--------|--------|---------------------------|---------------------------|
| 62 | NAK FACTURA OFFLINE | 00404 | **404** | II_IM |

Es otra compañía: los `id` de diario no son comparables con los de Nakel SA.

---

## Relación con módulos custom

- **`clientes_cc_informe`:** el asistente permite elegir **diario de ventas** (`filtro_pdv_journal_id`); por defecto intenta proponer el diario con **`l10n_ar_afip_pos_number = 50`** si existe. Vacío = todos los diarios de venta. Con **Fecha desde**, el informe puede mostrar **saldo inicial** sobre FC/NC anteriores (ver [INFORME_CC_CLIENTES_SALDO_INICIAL.md](INFORME_CC_CLIENTES_SALDO_INICIAL.md)).
- **`clientes_cc_detalle`:** filtros “mis ventas” vía **parámetros del sistema** (ICP), no vía el wizard del informe; ver código y parámetros en `account_move.py` si se unifica criterio.

---

## Cómo volver a verificar en otra base

En Odoo (modo desarrollador o SQL), diarios de venta con PV:

- Listado: Contabilidad → Configuración → Diarios → filtrar tipo **Ventas**.
- O búsqueda técnica en `account.journal` con dominio `[('type', '=', 'sale')]` y leer `l10n_ar_afip_pos_number`.

Si se restaura o migra la base, **los `journal.id` pueden diferir**; lo que suele mantenerse es el **nombre/código del diario** y el **PV AFIP** configurado en cada diario.

---

## Referencias en repo

- Incidente / secuencias AFIP (contexto NC): `docs/incidentes/INFORME_AFIP_10016_SECUENCIA_NC_RG5329.md`
- Permisos informes CC: `docs/usuarios/PERMISOS/PERMISOS_PREVENTISTAS_INFORMES_CC_MASTER_DEV.md`
- Saldo inicial en informe CC (FC/NC): `docs/contabilidad/INFORME_CC_CLIENTES_SALDO_INICIAL.md`
