#!/usr/bin/env python3
"""
Traduce el label "Backend" del POS (point_of_sale) a "Tablero" vía XML-RPC.

- Por defecto: dry-run (no escribe).
- Con --apply: crea o actualiza la traducción en ir.translation para el idioma elegido.

Uso (staging sg_dev1):
  export NAKEL_TARGET=staging_sg_dev1
  python3 traducir_pdv_backend_a_tablero.py --lang es_AR
  python3 traducir_pdv_backend_a_tablero.py --lang es_AR --apply
"""

from __future__ import annotations

import argparse
import os
import sys
import xmlrpc.client
from dataclasses import dataclass
from typing import Any


sys.path.insert(0, "/media/klap/raid5/cursor_files")

try:
    from config_nakel import ODOO_CONFIG_MASTER_DEV
except Exception as e:  # pragma: no cover
    print(f"❌ No se pudo importar config_nakel. Error: {e}")
    raise


@dataclass(frozen=True)
class OdooConn:
    url: str
    db: str
    uid: int
    password: str
    models: Any


def odoo_connect() -> OdooConn:
    url = ODOO_CONFIG_MASTER_DEV["url"].rstrip("/")
    db = ODOO_CONFIG_MASTER_DEV["db"]
    username = ODOO_CONFIG_MASTER_DEV["username"]
    password = ODOO_CONFIG_MASTER_DEV["password"]

    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, username, password, {})
    if not uid:
        raise RuntimeError(f"Fallo autenticación en {db} ({url}).")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    return OdooConn(url=url, db=db, uid=int(uid), password=password, models=models)


def _search_read(c: OdooConn, model: str, domain: list, *, fields: list[str], limit: int = 0) -> list[dict]:
    kwargs: dict[str, Any] = {"fields": fields}
    if limit:
        kwargs["limit"] = limit
    return c.models.execute_kw(c.db, c.uid, c.password, model, "search_read", [domain], kwargs)


def _search(c: OdooConn, model: str, domain: list, *, limit: int = 0) -> list[int]:
    kwargs: dict[str, Any] = {}
    if limit:
        kwargs["limit"] = limit
    return c.models.execute_kw(c.db, c.uid, c.password, model, "search", [domain], kwargs)


def _create(c: OdooConn, model: str, values: dict) -> int:
    return int(c.models.execute_kw(c.db, c.uid, c.password, model, "create", [values]))


def _write(c: OdooConn, model: str, ids: list[int], values: dict) -> bool:
    return bool(c.models.execute_kw(c.db, c.uid, c.password, model, "write", [ids, values]))


def detectar_idioma(c: OdooConn, requested: str) -> str:
    # Normalizamos: si pidieron es_AR pero no existe, intentamos es_ES, luego cualquier es_*
    candidates = [requested]
    if requested != "es_AR":
        candidates.append("es_AR")
    if requested != "es_ES":
        candidates.append("es_ES")

    for code in candidates:
        rows = _search_read(c, "res.lang", [("code", "=", code), ("active", "=", True)], fields=["code"], limit=1)
        if rows:
            return rows[0]["code"]

    rows = _search_read(c, "res.lang", [("code", "=ilike", "es_%"), ("active", "=", True)], fields=["code"], limit=1)
    if rows:
        return rows[0]["code"]

    raise RuntimeError("No hay idiomas 'es_*' activos en la base (res.lang).")


def upsert_traduccion_backend_a_tablero(
    *,
    lang: str,
    apply: bool,
    verbose: bool,
) -> int:
    c = odoo_connect()

    lang = detectar_idioma(c, lang)

    src = "Backend"
    value = "Tablero"
    module = "point_of_sale"

    # En esta instancia en particular se detectó que `ir.translation` puede no existir
    # como modelo expuesto por XML-RPC (registro ausente en ir.model y fault "Object ... doesn't exist").
    # Validamos antes de intentar operar.
    has_ir_translation = _search_read(
        c,
        "ir.model",
        [("model", "=", "ir.translation")],
        fields=["id", "model", "name"],
        limit=1,
    )
    if not has_ir_translation:
        print(
            "❌ Esta base no expone el modelo `ir.translation` por XML-RPC, así que no se puede upsertear "
            "la traducción por API en este entorno.\n"
            "✅ Alternativas:\n"
            "- UI: Ajustes → Traducciones → Términos de la aplicación (buscar 'Backend' y traducir a 'Tablero').\n"
            "- Módulo: agregar un .po con msgid 'Backend' / msgstr 'Tablero' y actualizar traducciones.\n"
        )
        return 0

    # En UI del POS, el término suele venir de JS (_t("Backend")) => type "code".
    # Si no aparece como "code", también buscamos "model_terms" por robustez.
    dom_base = [("lang", "=", lang), ("src", "=", src), ("module", "=", module)]
    existing = _search_read(
        c,
        "ir.translation",
        dom_base,
        fields=["id", "type", "name", "src", "value", "module", "state"],
        limit=50,
    )

    if verbose:
        print(f"Target: url={c.url} db={c.db} lang={lang}")
        print(f"Buscar ir.translation: module={module} src={src!r}")
        print(f"Encontradas: {len(existing)}")
        for row in existing[:20]:
            print(
                f"- id={row.get('id')} type={row.get('type')} name={row.get('name')} "
                f"state={row.get('state')} value={row.get('value')!r}"
            )

    # Elegimos un registro preferente si existe (prioridad: type=code, si no el primero)
    chosen: dict | None = None
    for row in existing:
        if row.get("type") == "code":
            chosen = row
            break
    if not chosen and existing:
        chosen = existing[0]

    if chosen:
        tid = int(chosen["id"])
        current = (chosen.get("value") or "").strip()
        if current == value:
            print(f"✅ Ya está traducido: ir.translation {tid} value={value!r} (lang={lang}).")
            return tid
        print(f"🧪 Dry-run: actualizar ir.translation {tid} value: {current!r} -> {value!r}")
        if apply:
            ok = _write(c, "ir.translation", [tid], {"value": value, "state": "translated"})
            if not ok:
                raise RuntimeError("Falló write() sobre ir.translation.")
            print(f"✅ Actualizado: ir.translation {tid} value={value!r} (lang={lang}).")
        else:
            print("ℹ️ No se aplicó (usar --apply).")
        return tid

    # No existía: creamos una traducción mínima. Para type/name, preferimos "code".
    values = {
        "lang": lang,
        "type": "code",
        "name": module,
        "src": src,
        "value": value,
        "module": module,
        "state": "translated",
    }

    print("🧪 Dry-run: crear ir.translation para 'Backend' -> 'Tablero'")
    if apply:
        tid = _create(c, "ir.translation", values)
        print(f"✅ Creado: ir.translation {tid} (lang={lang}) {src!r} -> {value!r}")
        return tid
    print("ℹ️ No se aplicó (usar --apply).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Traducir "Backend" -> "Tablero" en PDV (POS) vía XML-RPC.')
    parser.add_argument("--lang", default=os.environ.get("NAKEL_LANG", "es_AR"), help="Idioma (ej: es_AR, es_ES).")
    parser.add_argument("--apply", action="store_true", help="Aplicar cambios (por defecto es dry-run).")
    parser.add_argument("--quiet", action="store_true", help="Menos output.")
    args = parser.parse_args()

    tid = upsert_traduccion_backend_a_tablero(lang=args.lang, apply=bool(args.apply), verbose=not args.quiet)
    return 0 if (args.apply and tid) or (not args.apply) else 1


if __name__ == "__main__":
    raise SystemExit(main())

