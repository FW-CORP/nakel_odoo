# Informe: desfasaje NC A entre Odoo y AFIP/ARCA (error 10016) y subsanación

**Ámbito:** Odoo 18, localización Argentina (ADHOC en módulos estándar `l10n_ar`, `l10n_latam_invoice_document`, `l10n_ar_edi`), base **`master_dev`**.  
**Fecha de referencia:** abril 2026.  
**Copia en repo:** `nakel_odoo/docs/incidentes/INFORME_AFIP_10016_SECUENCIA_NC_RG5329.md` (histórico también en servidor bajo `docs/` según despliegue).

---

## 1. Resumen ejecutivo

- Al validar notas de crédito electrónicas (**NC A**, tipo AFIP **3**) puede aparecer **error 10016** (“número o fecha no corresponde al próximo a autorizar”).
- Caso documentado: en **AFIP** el último comprobante NC A para el punto de venta era **118** (con **CAE**), mientras que en **Odoo** el último asiento **publicado** era el **117**: la **118** estaba autorizada en AFIP pero el asiento en Odoo seguía en **borrador** sin CAE guardado.
- Subsanación típica: **(A)** completar en Odoo los campos de autorización AFIP ya conocidos y **publicar** el asiento (sin re-enviar `FECAESolicitar` si el CAE ya existe y se carga en el move), y **(B)** asegurar que **`modulo_rg5329`** no modifique impuestos en documentos ya publicados desde un `compute` (ver §6.2).
- **Herramienta repo (dry-run / XML-RPC):** `nakel_odoo/tools/sync_latam_sequence_afip/sync_latam_sequence_xmlrpc.py` — compara último **posteado** en Odoo vs último número informado por AFIP y opcionalmente asigna `l10n_latam_document_number` en borradores (no sustituye el flujo de “CAE ya existente” del §6.1).

---

## 2. Síntomas en la interfaz

Mensaje típico al validar:

```text
Error de validación de la AFIP:
* Code 10016: El numero o fecha del comprobante no se corresponde con el proximo a autorizar.
  Consultar metodo FECompUltimoAutorizado.

Eventos de validación de AFIP:
* Code 39: ... (RG 5616 / Condición IVA del receptor; aviso informativo)
```

Consejo del sistema: posible **desajuste de numeración** entre Odoo y AFIP.

**Otros códigos frecuentes en el mismo modal:**

- **39** — aviso RG 5616 / condición IVA receptor; **no** suele ser la causa principal junto a 10016.
- **43** — informativo (manual/versiones WS).
- **10016** — correlatividad / siguiente número o fecha esperada por AFIP para ese **PtoVta** y **tipo**.

---

## 3. Códigos de error y significado

| Código | Origen | Interpretación práctica |
|--------|--------|-------------------------|
| **10016** | AFIP WSFE | El **número** y/o la **fecha** del comprobante enviado no es el que AFIP espera como **siguiente** para ese **Punto de venta** y **tipo de comprobante**. Suele indicar **desfasaje de secuencia** o conflicto de fechas respecto del último autorizado. |
| **39** | AFIP (eventos) | **Aviso** informativo (p. ej. RG 5616, condición IVA receptor). **No** es la causa del rechazo principal cuando viene acompañando al 10016. |
| **11001** | AFIP (consulta último número) | Puede aparecer si el **tipo de comprobante** (`CbteTipo`) no es válido para la consulta (p. ej. tipo incorrecto en el diario/documento). Documentar aparte si se reproduce. |

---

## 4. Causa raíz (caso documentado)

1. **Secuencia:** Para NC A, Odoo calcula el siguiente número a partir de los **`account.move` publicados** del mismo **diario** y **`l10n_latam_document_type_id`** (en AR se añade esa condición en `l10n_ar`).
2. **AFIP** ya había **autorizado** la NC **118** (CAE real vía `FECompConsultar`).
3. **Odoo** mantenía el asiento **118** en **borrador** sin **`l10n_ar_afip_auth_code`**, por lo que la lista de “última NC publicada” seguía en **117** → al validar otros borradores, Odoo intentaba de nuevo el **118** y AFIP respondía **10016** (o situaciones equivalentes de desalineación).
4. **Segundo factor:** el módulo **`modulo_rg5329`** ejecutaba `_auto_apply_rg5329_taxes()` desde `_compute_rg5329_perception` **también tras publicar**, intentando cambiar `tax_ids` en líneas ya publicadas → **UserError** en el `commit` intermedio del flujo EDI.

---

## 5. Diagnóstico paso a paso (solo lectura / consulta)

### 5.1 En Odoo (base de datos / shell de solo lectura)

- Localizar borradores **NC A** (`l10n_latam.document.type` código **3**), mismo **diario** (PV `l10n_ar_afip_pos_number`).
- Última NC **publicada**: ordenar por `sequence_number` o por nombre `NC-A 00050-XXXXXXXX`.
- Comparar con el comprobante que falla (ej. `account.move` **33317**, **32740**, etc.).

### 5.2 En AFIP (API WSFE, misma conexión que Odoo)

- **`FECompUltimoAutorizado`**: último número autorizado para **CbteTipo** + **PtoVta**.
- **`FECompConsultar`**: para un **número concreto**, confirmar **Resultado**, **CAE** (`CodAutorizacion`), importes, receptor y comprobantes asociados.

En Odoo esto equivale al asistente **Consultar factura en AFIP** (`l10n_ar_afip.ws.consult`), o a llamadas programáticas iguales a las del estándar `l10n_ar_edi`.

### 5.3 Coherencia negocio ↔ AFIP

Ejemplo resuelto: pedido **S01769**, factura **FA-A 00050-00000175** (`account.move` **17347**), NC en borrador **`account.move` 33026** (mismos importes que AFIP para la **118**).  
Cruce por **CUIT receptor**, **ImpTotal**, **CbtesAsoc** (FA **175**), etc.

### 5.4 Script XML-RPC (repo)

Dry-run (sin escritura):

```bash
cd nakel_odoo/tools/sync_latam_sequence_afip
PYTHONPATH=/ruta/al/padre-de-config python3 sync_latam_sequence_xmlrpc.py \
  --journal-id 9 --document-type-id 3 --afip-last 594
```

(Usar credenciales vía `config_nakel` / variables `ODOO_URL`, `ODOO_DB`, `ODOO_USER`, `ODOO_PASSWORD`.)

---

## 6. Subsanación aplicada (referencia técnica)

> **Nota:** Reproducir siempre con **backup** y ventana de mantenimiento.

### 6.1 Completar CAE en Odoo cuando AFIP ya autorizó

**Condición:** `FECompConsultar` devuelve **Resultado A** y **CAE** para ese **PtoVta**, **tipo 3** y **número N**.

**Campos** (modelo `account.move`, módulo `l10n_ar_edi`):

- `l10n_ar_afip_auth_mode` = `CAE`
- `l10n_ar_afip_auth_code` = valor de `CodAutorizacion`
- `l10n_ar_afip_auth_code_due` = `FchVto` (fecha)
- `l10n_ar_afip_result` = `A`

**Orden:** `write` con esos valores **en borrador** → luego **`action_post()`**.

**Motivo:** En `_l10n_ar_do_afip_ws_request_cae`, el flujo evita duplicar `FECAESolicitar` cuando el asiento ya tiene `l10n_ar_afip_auth_code` (según versión/localización).

### 6.2 Parche `modulo_rg5329` (evitar error al publicar)

En `_compute_rg5329_perception`, llamar a `_auto_apply_rg5329_taxes()` **solo si** `move.state == 'draft'`.  
Así no se intenta modificar `tax_ids` en líneas **ya publicadas** durante flushes/commits posteriores al post.

**Archivo versionado:** `nakel_odoo/addons/modulo_rg5329/models/account_move.py`

### 6.3 Ajuste solo de numeración en borrador (sin CAE previo)

Si AFIP confirma **último = N** y el siguiente válido es **N+1**, y no hay comprobante “huérfano” con CAE: alinear `l10n_latam_document_number` / secuencia según procedimiento contable, o usar el script con `--apply --draft-move-ids` tras validar el dry-run.

---

## 7. Numeración: equivalencia Odoo ↔ AFIP

Para NC A en Argentina (formato habitual):

`NC-A` + ` ` + **PV cinco dígitos** + `-` + **número ocho dígitos** = mismo **`CbteNro`** que en AFIP (relleno con ceros).

---

## 8. Si vuelve a pasar (checklist corto)

1. **`FECompUltimoAutorizado`** vs última NC **publicada** en Odoo (mismo diario, tipo **3**).
2. Si AFIP tiene un número **N** con **CAE** y Odoo no tiene **`NC-A … N`** publicado: **`FECompConsultar`** para **N** y localizar el **borrador** que coincida por importes/receptor/documento asociado.
3. Si corresponde: **completar CAE** + **`action_post`** (sin duplicar solicitud a AFIP).
4. Si al publicar aparece error de **impuestos en líneas publicadas**: revisar **`modulo_rg5329`** (solo `_auto_apply_*` en borrador).
5. Tras **cambios de normativa / módulo RG**: revisar **borradores** creados antes del deploy (importes/impuestos vs factura origen).

---

## 9. Referencias de código (Odoo estándar)

- Secuencia por tipo documento (AR): `l10n_ar/models/account_move.py` — `_get_last_sequence_domain`, `_get_formatted_sequence`.
- Post + CAE: `l10n_ar_edi/models/account_move.py` — `_post`, `_l10n_ar_do_afip_ws_request_cae` (condición `not l10n_ar_afip_auth_code`).
- Consulta comprobante: `l10n_ar_edi/wizards/l10n_ar_afip_ws_consult.py` — `FECompConsultar` / último comprobante.

---

## 10. Historial de este documento

| Versión | Notas |
|---------|--------|
| 1.0 | Incidencia NC 118 / move 33026, errores 10016 y 39, parche RG5329 y alineación CAE. |
| 1.1 | Copia al vault Obsidian/repo; enlace a `sync_latam_sequence_xmlrpc.py`; parche RG5329 referenciado en código versionado. |
| 1.2 | Verificación en **master_dev** (2026-05-08): `FECompConsultar` vía asistente Odoo **Consultar factura en AFIP** (`l10n_ar_afip.ws.consult`, método `button_confirm`); cruce NC **594** ↔ `account.move` **210838** (ver §11). |
| 1.3 | **master_dev** (2026-05-08): subsanación **210838** ejecutada por **XML-RPC** (`account.move` `write` + `action_post`); NC **594** quedó **publicada** en Odoo con CAE alineado a AFIP (detalle §11.6). |
| 1.4 | §12: clasificación **bug vs. acción de usuario** (RG5329 + desfasaje numeración / 10016). |

---

## 11. Verificación AFIP ↔ Odoo (master_dev, 2026-05-08)

**Contexto:** Diario **FACT NAKEL CENTRAL** (`account.journal` **9**, PV **50**), tipo **NC A** (`l10n_latam.document.type` **3**, `CbteTipo` **3**).

### 11.1 Delimitación del último número en AFIP

Consultas **`FECompConsultar`** (misma conexión/certificado que Odoo):

| `CbteNro` | Resultado | Notas |
|-----------|-----------|--------|
| **593** | **A** (CAE **86194696133093**) | Coincide con última NC **publicada** en Odoo: **210576** (`00050-00000593`), total **28667,85**. |
| **594** | **A** (CAE **86194696461936**) | Antes del 2026-05-08 no figuraba publicada en Odoo; subsanado — **210838** → **NC-A 00050-00000594** (§11.6). |
| **595**, **596** | Error AFIP **602** (*No existen datos en nuestros registros…*) | Confirma que el **último autorizado** para ese PV/tipo es **594**; el siguiente libre para **nueva** solicitud CAE es **595**. |

### 11.2 Detalle AFIP de la NC 594 (comprobante “huérfano” en Odoo)

Datos relevantes devueltos por AFIP para **PtoVta 50**, **CbteTipo 3**, **CbteNro 594**:

| Campo (WS) | Valor |
|------------|--------|
| **Resultado** | A |
| **CodAutorizacion** (CAE) | 86194696461936 |
| **FchVto** (vencimiento CAE) | 20260518 |
| **CbteFch** | 20260508 |
| **ImpTotal** | 22667,11 |
| **ImpNeto** | 18733,15 |
| **ImpIVA** | 3933,96 |
| **DocTipo / DocNro** (receptor) | 80 / **27266025594** |
| **CbtesAsoc** | Factura **A** (`Tipo` 1), **PtoVta 50**, **Nro 1156** |
| **Observaciones** | Código **10217** (texto informativo RG transición crédito fiscal; **Resultado** sigue siendo **A**) |

### 11.3 Cruce con Odoo (identificación previa a la subsanación)

| Odoo | Valor (estado al momento del análisis) |
|------|--------|
| **`account.move`** | **210838** (entonces en borrador; ver §11.6) |
| Cliente | **LOPEZ LORENA IVANA** (`res.partner` **16099**, CUIT **27266025594**) |
| **invoice_date** | 2026-05-08 |
| **amount_total** / **amount_untaxed** | **22667,11** / **18733,15** |
| **reversed_entry_id** | **150995** — **FA-A 00050-00001156** (`00050-00001156`) |
| **invoice_origin** | S03136 |
| **l10n_latam_document_number** | (vacío antes del `write`) |
| **l10n_ar_afip_auth_code** | (vacío antes del `write`) |

**Conclusión:** la NC **594** autorizada en AFIP correspondía de forma **consistente** al move **210838**. Procedimiento aplicado: §6.1 + §11.6.

### 11.4 Restantes borradores (mismo diario / tipo)

Con la **594** ya **publicada** en Odoo (`210838`), los demás borradores deben alinearse a partir del **595** (p. ej. `sync_latam_sequence_xmlrpc.py` con **`--afip-last 594`** y **`--apply --draft-move-ids`**, en el orden contable). IDs que seguían en borrador en la corrida de análisis (actualizar si la base cambió): **32740**, **51706**, **51707**, **210842**, **210845**, **211693** (**210838** ya no aplica: publicada como **NC-A 00050-00000594**).

### 11.5 Nota técnica (automatización)

Para repetir la consulta por **XML-RPC** sin salir de Odoo: crear registro en `l10n_ar_afip.ws.consult` con `journal_id`, `document_type_id`, `consult_type='specific'`, `number`, y ejecutar **`button_confirm`**. En esta versión del servidor, una respuesta exitosa de AFIP puede devolverse como **`UserError`** con el detalle en el mensaje (comportamiento habitual del asistente al mostrar el resultado).

### 11.6 Ejecución completada — `write` + `action_post` por XML-RPC (2026-05-08)

**Base:** `master_dev`. **Modelo:** `account.move`. **ID:** **210838**.

Secuencia ejecutada vía `execute_kw` (mismo patrón que §5.4 / integraciones internas):

1. Comprobación: estado **draft** antes de escribir.
2. **`write`** con:

```python
{
    "l10n_latam_document_number": "00050-00000594",
    "l10n_ar_afip_auth_mode": "CAE",
    "l10n_ar_afip_auth_code": "86194696461936",
    "l10n_ar_afip_auth_code_due": "2026-05-18",
    "l10n_ar_afip_result": "A",
}
```

3. **`action_post`** sobre el mismo id.

**Resultado verificado:** `state` = **posted**, `name` = **NC-A 00050-00000594**, campos AFIP coincidentes con §11.2. Sin error en RPC.

> **Seguridad:** no versionar credenciales en el repo; usar variables de entorno o `config_nakel` según política FWCORP.

---

## 12. Clasificación: ¿bug de software o mala acción de usuario?

**Ámbito:** incidente **10016** / desfasaje donde el **último posteado en Odoo queda por debajo del último autorizado en AFIP** (caso NC **594**, move **210838**), y error colateral al publicar vinculado a **RG 5329**.

### 12.1 Hallazgo con evidencia de **bug** (código)

| Elemento | Qué ocurría | Por qué es defecto de producto/customización |
|----------|-------------|---------------------------------------------|
| **`modulo_rg5329`** | `_auto_apply_rg5329_taxes()` se invocaba desde `_compute_rg5329_perception` **aun con el asiento ya publicado** (antes del parche). | Un `compute` que **modifica** `tax_ids` en líneas **posteadas** choca con las reglas de Odoo (`UserError` / transacción) y puede interrumpir el flujo **después** de que AFIP ya haya respondido en el proceso EDI. |
| **Parche aplicado** | Solo aplicar `_auto_apply_rg5329_taxes()` si `move.state == 'draft'`. | Corrige el comportamiento incorrecto descrito arriba (ver §6.2 y código en `nakel_odoo/addons/modulo_rg5329/models/account_move.py`). |

**Conclusión:** no atribuir el bloqueo “impuestos en líneas publicadas” a un usuario sin más datos: encaja con un **bug de implementación** en la interacción compute ↔ líneas publicadas.

### 12.2 Hueco de numeración (AFIP **N**, Odoo último **N−1** sin publicar **N**)

Aquí la causa suele ser **mixta**:

- **Proceso / operación:** en el flujo normal, AFIP solo otorga CAE si alguien **confirmó** el comprobante desde Odoo (u otro sistema con el mismo certificado). Que el move quede en **borrador** sin CAE en Odoo pero con CAE en AFIP indica que en algún momento el **resultado de AFIP quedó aplicado en ARCA** y **no** reflejado (o no persistido) en Odoo como asiento publicado.
- **Bug o fallo técnico posible:** corte de sesión, error de servidor, o **error de cliente** (p. ej. excepción tras la respuesta AFIP) — el parche **RG5329** es un candidato creíble a **abortar el post** después de la autorización, según el orden interno del flujo EDI en esa versión.
- **Mala acción voluntaria:** poco habitual como explicación *principal* (haría falta evidencia de emisión fuera de Odoo con el mismo PV o manipulación de borradores); no se puede afirmar sin auditoría de **quién** validó y **logs** de ese instante.

**Conclusión práctica:** tratar el desfasaje como **riesgo operativo + posible bug**; el **10016** en sí es la **consecuencia esperada** de la regla de correlatividad de AFIP, no un “bug de AFIP”.

### 12.3 Resumen para informar a negocio / auditoría

| Pregunta | Respuesta breve |
|----------|-------------------|
| ¿Fue solo culpa de un usuario? | **No necesariamente.** El código **RG5329** tenía un defecto que podía romper el post; el hueco **594** puede ser **fallo de flujo** o interrupción, no un error consciente. |
| ¿Hubo bug en Nakel? | **Sí**, en **`modulo_rg5329`**: aplicación de impuestos fuera de borrador; **corregido** condicionando a `draft`. |
| ¿Odoo estándar “falló”? | El diseño de secuencia (último número por **posteados**) es **coherente**; el problema es **desalineación** entre lo publicado y lo que AFIP ya autorizó. |
| ¿Qué falta para culpabilidad fina? | Logs del servidor y trazas **EDI** en la fecha/hora del CAE **86194696461936**, usuario Odoo que confirmó, y si hubo **traceback** posterior al CAE. |

### 12.4 Versión de documento

Esta sección se agregó para respuestas tipo auditoría (“¿bug o usuario?”). Histórico: ver §10 (versión **1.4**).
