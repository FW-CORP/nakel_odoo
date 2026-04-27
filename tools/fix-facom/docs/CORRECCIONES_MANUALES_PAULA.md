---
title: Correcciones manuales (Paula) — FACOM
updated: 2026-04-25
---

## Objetivo

Dejar documentado, **en staging `sg_dev1`**, el **nombre original** (`account.move.name`) y a cual se pasaria segun la regla de Paula (o fallback) para un primer lote de correccion previa a aplicar la correccion masiva en productivo.

## Fuente de datos (read-only)

- DB: `sg_dev1`
- Dominio base: `account.move` con `move_type=in_invoice`, `state=posted`, `journal_id.code=FACOM`

## Casos a corregir primero (18 candidatos)

> Nota: los 11 casos iniciales estan incluidos aca. El resto son candidatos adicionales detectados por `ref` incompleta o sin `PV-NRO`.

Formato deseado (cuando `ref` lo permite):
- `ref = "FC A 10-100648"` -> `name_nuevo = "FA-A 00010-00100648"`

### Lista

- **move_id 97028**
  - **name_original**: `FACOM/26-27/04/0200`
  - **ref**: `FC A`
  - **name_nuevo (dry-run)**: *(no parseable)* -> requiere completar `ref` con `PV-NRO`

- **move_id 21474**
  - **name_original**: `FACOM/26-27/04/0040`
  - **ref**: `FC A`
  - **name_nuevo (dry-run)**: *(no parseable)* -> requiere completar `ref` con `PV-NRO`

- **move_id 79286**
  - **name_original**: `FACOM/26-27/04/0158`
  - **ref**: *(vacia)*
  - **name_nuevo (fallback)**: `FA-A 00000-27040158`

- **move_id 79202**
  - **name_original**: `FACOM/26-27/04/0153`
  - **ref**: *(vacia)*
  - **name_nuevo (fallback)**: `FA-A 00000-27040153`

- **move_id 64154**
  - **name_original**: `FACOM/26-27/04/0121`
  - **ref**: *(vacia)*
  - **name_nuevo (fallback)**: `FA-A 00000-27040121`

- **move_id 43951**
  - **name_original**: `FACOM/26-27/04/0079`
  - **ref**: *(vacia)*
  - **name_nuevo (fallback)**: `FA-A 00000-27040079`

- **move_id 21456**
  - **name_original**: `FACOM/25-26/03/0096`
  - **ref**: *(vacia)*
  - **name_nuevo (fallback)**: `FA-A 00000-26030096`

- **move_id 14931**
  - **name_original**: `FACOM/26-27/04/0018`
  - **ref**: *(vacia)*
  - **name_nuevo (fallback)**: `FA-A 00000-27040018`

- **move_id 1662**
  - **name_original**: `FACOM/25-26/03/0049`
  - **ref**: *(vacia)*
  - **name_nuevo (fallback)**: `FA-A 00000-26030049`

- **move_id 364**
  - **name_original**: `FACOM/25-26/03/0013`
  - **ref**: *(vacia)*
  - **name_nuevo (fallback)**: `FA-A 00000-26030013`

- **move_id 207**
  - **name_original**: `FACOM/25-26/03/0007`
  - **ref**: *(vacia)*
  - **name_nuevo (fallback)**: `FA-A 00000-26030007`

- **move_id 196**
  - **name_original**: `FACOM/25-26/03/0002`
  - **ref**: *(vacia)*
  - **name_nuevo (fallback)**: `FA-A 00000-26030002`

- **move_id 191**
  - **name_original**: `FACOM/25-26/03/0001`
  - **ref**: *(vacia)*
  - **name_nuevo (fallback)**: `FA-A 00000-26030001`

- **move_id 78155**
  - **name_original**: `FACOM/26-27/04/0144`
  - **ref**: `602889360`
  - **name_nuevo (fallback digitos)**: `FA-A 00006-02889360`

- **move_id 60208**
  - **name_original**: `FACOM/26-27/04/0116`
  - **ref**: `ND 245`
  - **name_nuevo (fallback digitos)**: `FA-A 00000-00000245`

- **move_id 1254**
  - **name_original**: `FACOM/25-26/03/0023`
  - **ref**: `601989600`
  - **name_nuevo (fallback digitos)**: `FA-A 00006-01989600`

- **move_id 690**
  - **name_original**: `FACOM/25-26/03/0020`
  - **ref**: `015400264038`
  - **name_nuevo (fallback digitos)**: `FA-A 00154-00264038`

- **move_id 381**
  - **name_original**: `FACOM/25-26/03/0012`
  - **ref**: `602049902`
  - **name_nuevo (fallback digitos)**: `FA-A 00006-02049902`

## Observacion clave

Los casos con **`ref` vacia** o **`ref='FC A'` sin `PV-NRO`** no permiten asegurar "tomado de la factura" sin completar el dato. Se dejan listados para correccion manual previa o para decidir una regla alternativa.

## Colisiones detectadas en el cambio masivo (staging)

En staging `sg_dev1` al aplicar el fix masivo se detectaron **4 colisiones** (el `name_nuevo` ya existia en el diario), por lo que el script las salto.
Si Paula las corrige a mano, conviene dejarlas listadas como “excluidas del batch” en productivo.

- **move_id 25631**
  - **name_original**: `FACOM/26-27/04/0048`
  - **ref**: `3100-250132`
  - **name_nuevo (propuesto)**: `FA-A 03100-00250132`

- **move_id 38203**
  - **name_original**: `FACOM/26-27/04/0072`
  - **ref**: `FC A 60-11863`
  - **name_nuevo (propuesto)**: `FA-A 00060-00011863`

- **move_id 50143**
  - **name_original**: `FACOM/26-27/04/0086`
  - **ref**: `FAC 10-4602`
  - **name_nuevo (propuesto)**: `FA-A 00010-00004602`

- **move_id 79042**
  - **name_original**: `FACOM/26-27/04/0148`
  - **ref**: `FC 0028-0001366`
  - **name_nuevo (propuesto)**: `FA-A 00028-00001366`

