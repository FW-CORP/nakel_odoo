#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aplicar (o simular) normalizacion de account.move.name para vendor bills del diario FACOM.

IMPORTANTE:
- Por defecto es DRY-RUN (no escribe).
- Para escribir requiere: --apply --i-know-what-im-doing

Ejemplos:
  # Dry-run (recomendado primero)
  NAKEL_TARGET=staging_sg_dev1 python3 aplicar_fix_facom.py --only-posted --out-csv /tmp/facom_dryrun.csv

  # Aplicar en tanda chica (ej. 10), omitiendo ids corregidos a mano
  NAKEL_TARGET=staging_sg_dev1 python3 aplicar_fix_facom.py --only-posted --limit 10 --skip-move-ids 21474,97028 --apply --i-know-what-im-doing
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import xmlrpc.client
from dataclasses import dataclass
from typing import Any, Iterable


sys.path.insert(0, "/media/klap/raid5/cursor_files")

try:
    from config_nakel import ODOO_CONFIG_MASTER_DEV
except Exception as e:  # pragma: no cover
    raise SystemExit(f"No se pudo importar config_nakel / ODOO_CONFIG_MASTER_DEV: {e}")


@dataclass(frozen=True)
class OdooConn:
    url: str
    db: str
    uid: int
    password: str
    models: Any


def connect(cfg: dict) -> OdooConn:
    url = cfg["url"].rstrip("/")
    db = cfg["db"]
    username = cfg["username"]
    password = cfg["password"]
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(db, username, password, {})
    if not uid:
        raise SystemExit(f"Autenticacion Odoo fallida: url={url} db={db} user={username}")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)
    return OdooConn(url=url, db=db, uid=int(uid), password=password, models=models)


def search(c: OdooConn, model: str, domain: list, *, limit: int | None = None, order: str | None = None) -> list[int]:
    kwargs: dict[str, Any] = {}
    if limit is not None:
        kwargs["limit"] = int(limit)
    if order:
        kwargs["order"] = order
    return c.models.execute_kw(c.db, c.uid, c.password, model, "search", [domain], kwargs)


def read(c: OdooConn, model: str, ids: list[int], fields: list[str]) -> list[dict[str, Any]]:
    if not ids:
        return []
    return c.models.execute_kw(c.db, c.uid, c.password, model, "read", [ids], {"fields": fields})


def write(c: OdooConn, model: str, ids: list[int], values: dict[str, Any]) -> bool:
    if not ids:
        return True
    return bool(c.models.execute_kw(c.db, c.uid, c.password, model, "write", [ids, values]))


def search_count(c: OdooConn, model: str, domain: list) -> int:
    return int(c.models.execute_kw(c.db, c.uid, c.password, model, "search_count", [domain], {}))


def chunked(seq: list[int], size: int) -> Iterable[list[int]]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


_PV_NRO_RE = re.compile(r"(\d{1,10})\s*-\s*(\d{1,20})")
_DOC_LETTER_PREFIX_RE = re.compile(r"^\s*([A-Z]{1,3})\s+([A-Z])\b")


def _split_digits_to_pv_nro(digits: str) -> tuple[str, str] | None:
    d = re.sub(r"\D+", "", digits or "")
    if not d:
        return None
    nro = d[-8:].zfill(8)
    pv = d[:-8][-5:].zfill(5) if len(d) > 8 else "00000"
    return pv, nro


def normalize_from_ref_paula(ref: str) -> tuple[str | None, str]:
    ref = (ref or "").strip()
    if not ref:
        return None, "ref_vacia"

    doc = None
    letter = None
    m0 = _DOC_LETTER_PREFIX_RE.match(ref.upper())
    if m0:
        doc = m0.group(1)
        letter = m0.group(2)

    m = _PV_NRO_RE.search(ref)
    if m:
        pv = m.group(1).zfill(5)
        nro_raw = m.group(2)
        nro = nro_raw.zfill(8) if len(nro_raw) <= 8 else nro_raw
        # IMPORTANT: l10n_ar expects document_number as "PV-NRO" with ONE '-' only.
        # If we include something like "FA-A 00010-..." it will break split('-') in tax settlement.
        # So we write account.move.name as PV-NRO only.
        reason = "ok_ref_doc_letter" if m0 else "fallback_pv_nro_sin_doc_o_letra"
        return f"{pv}-{nro}", reason

    digits = re.sub(r"\D+", "", ref)
    if digits:
        sp = _split_digits_to_pv_nro(digits)
        if sp:
            pv, nro = sp
            return f"{pv}-{nro}", "fallback_digits_sin_guion"

    return None, "no_parseable"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--journal-code", type=str, default="FACOM")
    ap.add_argument("--only-posted", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="0 = sin limite")
    ap.add_argument("--skip-move-ids", type=str, default="", help="CSV de ids a omitir (ej: '21474,97028')")
    ap.add_argument("--out-csv", type=str, default="", help="CSV de backup (antes/despues). Recomendado.")
    ap.add_argument("--apply", action="store_true", help="Habilita escritura")
    ap.add_argument("--i-know-what-im-doing", action="store_true", help="Segundo seguro para escritura")
    args = ap.parse_args()

    skip_ids: set[int] = set()
    if args.skip_move_ids.strip():
        skip_ids = {int(x.strip()) for x in args.skip_move_ids.split(",") if x.strip()}

    cfg = ODOO_CONFIG_MASTER_DEV.copy()
    c = connect(cfg)
    print(f"OK: {c.url} | db={c.db} | uid={c.uid}")

    # Journal id (FACOM)
    journals = c.models.execute_kw(
        c.db, c.uid, c.password, "account.journal", "search_read", [[("code", "=", args.journal_code)]], {"fields": ["id", "name", "code"], "limit": 5}
    )
    if not journals:
        raise SystemExit(f"No existe account.journal con code={args.journal_code}")
    jid = int(journals[0]["id"])
    print(f"journal: {jid}:{journals[0].get('name')}")

    dom: list[Any] = [("move_type", "=", "in_invoice"), ("journal_id", "=", jid)]
    if args.only_posted:
        dom.append(("state", "=", "posted"))
    dom.extend(["|", ("name", "ilike", "FACOM"), ("name", "ilike", "/FACOM")])

    limit = int(args.limit) if int(args.limit) > 0 else None
    move_ids = search(c, "account.move", dom, limit=limit, order="id asc")
    if skip_ids:
        move_ids = [i for i in move_ids if int(i) not in skip_ids]
    print(f"moves_target={len(move_ids)} limit={limit or 0} skip={len(skip_ids)}")

    move_fields = ["id", "name", "ref", "state"]
    rows_out: list[dict[str, Any]] = []

    apply_enabled = bool(args.apply and args.i_know_what_im_doing)
    if args.apply and not apply_enabled:
        raise SystemExit("Para escribir necesitas: --apply --i-know-what-im-doing")

    for part in chunked(move_ids, 200):
        moves = read(c, "account.move", part, move_fields)
        for mv in moves:
            mid = int(mv["id"])
            old = str(mv.get("name") or "")
            ref = str(mv.get("ref") or "").strip()

            new, reason = normalize_from_ref_paula(ref)
            if not new:
                # Safe mode: do NOT invent a new name when ref is unusable.
                # Leave it for manual review. This keeps the write set "clean".
                rows_out.append(
                    {
                        "move_id": mid,
                        "state": mv.get("state"),
                        "name_old": old,
                        "ref": ref,
                        "name_new": "",
                        "action": "SKIP_NO_PARSE",
                        "reason": reason,
                    }
                )
                continue

            # Collision check (very important)
            if search_count(c, "account.move", [("journal_id", "=", jid), ("name", "=", new)]):
                rows_out.append(
                    {
                        "move_id": mid,
                        "state": mv.get("state"),
                        "name_old": old,
                        "ref": ref,
                        "name_new": new,
                        "action": "SKIP_COLLISION",
                        "reason": reason,
                    }
                )
                continue

            if apply_enabled:
                ok = write(c, "account.move", [mid], {"name": new})
                action = "WROTE" if ok else "WRITE_FAILED"
            else:
                action = "DRYRUN"

            rows_out.append(
                {
                    "move_id": mid,
                    "state": mv.get("state"),
                    "name_old": old,
                    "ref": ref,
                    "name_new": new,
                    "action": action,
                    "reason": reason,
                }
            )

    # Output CSV
    if args.out_csv.strip():
        out_path = args.out_csv.strip()
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=["move_id", "state", "name_old", "ref", "name_new", "action", "reason"],
            )
            w.writeheader()
            w.writerows(rows_out)
        print(f"CSV: {out_path}")

    # Summary
    from collections import Counter

    c_actions = Counter(r["action"] for r in rows_out)
    print("Resumen actions:")
    for k, v in c_actions.most_common():
        print(f"- {k}: {v}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

