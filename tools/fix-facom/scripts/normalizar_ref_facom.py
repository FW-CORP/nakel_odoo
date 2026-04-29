#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Normalizar account.move.ref (Referencia de factura) para compras FACOM.

Objetivo:
  - Mantener account.move.name como PV-NRO (por compatibilidad l10n_ar: split('-') espera 1 guion)
  - Estandarizar account.move.ref con prefijo documental estilo NAKEL:
      "FA-A 00010-00101199", "FA-B ...", "ND-A ...", "NC-A ...", etc.

Fuentes:
  - Preferimos parsear DOC+LETRA desde ref actual (ej: "FC A 10-101199")
  - El PV-NRO se toma de:
      1) account.move.name si ya es PV-NRO
      2) sino, se intenta extraer PV-NRO desde ref

Read-only por defecto. Para escribir: --apply --i-know-what-im-doing
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


def chunked(seq: list[int], size: int) -> Iterable[list[int]]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


PV_NRO_RE = re.compile(r"^\s*(\d{5})\s*-\s*(\d{2,})\s*$")
PV_NRO_ANY_RE = re.compile(r"(\d{1,10})\s*-\s*(\d{1,20})")
DOC_LETTER_RE = re.compile(r"^\s*([A-Z]{1,3})\s+([A-Z])\b")


def pad_pv_nro(pv_raw: str, nro_raw: str) -> str:
    pv = (pv_raw or "").strip().zfill(5)
    nro = (nro_raw or "").strip()
    nro = nro.zfill(8) if len(nro) <= 8 else nro
    return f"{pv}-{nro}"


def doc_map(doc: str) -> str:
    d = (doc or "").upper().strip()
    # En NAKEL: FC (factura compra) se ve como FA
    if d == "FC":
        return "FA"
    return d or "FA"


def derive_pv_nro_from_name_or_ref(name: str, ref: str) -> str | None:
    name = (name or "").strip()
    m = PV_NRO_RE.match(name)
    if m:
        return pad_pv_nro(m.group(1), m.group(2))
    m2 = PV_NRO_ANY_RE.search((ref or "").strip())
    if m2:
        return pad_pv_nro(m2.group(1), m2.group(2))
    return None


def derive_doc_letter_from_ref(ref: str) -> tuple[str, str] | None:
    ref = (ref or "").strip().upper()
    m = DOC_LETTER_RE.match(ref)
    if not m:
        return None
    return doc_map(m.group(1)), m.group(2)


def build_new_ref(old_ref: str, pv_nro: str) -> tuple[str | None, str]:
    old_ref = (old_ref or "").strip()
    dl = derive_doc_letter_from_ref(old_ref)
    if not dl:
        return None, "SKIP_NO_DOC_LETTER"
    doc, letter = dl
    return f"{doc}-{letter} {pv_nro}", "OK"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--journal-code", type=str, default="FACOM")
    ap.add_argument("--only-posted", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="0 = sin limite")
    ap.add_argument("--skip-move-ids", type=str, default="")
    ap.add_argument("--out-csv", type=str, default="", help="CSV backup/preview recomendado")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--i-know-what-im-doing", action="store_true")
    args = ap.parse_args()

    apply_enabled = bool(args.apply and args.i_know_what_im_doing)
    if args.apply and not apply_enabled:
        raise SystemExit("Para escribir necesitas: --apply --i-know-what-im-doing")

    skip_ids: set[int] = set()
    if args.skip_move_ids.strip():
        skip_ids = {int(x.strip()) for x in args.skip_move_ids.split(",") if x.strip()}

    c = connect(ODOO_CONFIG_MASTER_DEV.copy())
    print(f"OK: {c.url} | db={c.db} | uid={c.uid}")

    journals = c.models.execute_kw(
        c.db,
        c.uid,
        c.password,
        "account.journal",
        "search_read",
        [[("code", "=", args.journal_code)]],
        {"fields": ["id", "name", "code"], "limit": 5},
    )
    if not journals:
        raise SystemExit(f"No existe account.journal con code={args.journal_code}")
    jid = int(journals[0]["id"])
    print(f"journal: {jid}:{journals[0].get('name')}")

    dom: list[Any] = [("move_type", "=", "in_invoice"), ("journal_id", "=", jid)]
    if args.only_posted:
        dom.append(("state", "=", "posted"))
    # Solo donde ref parece "FC A ..." / "ND A ..." etc (doc+letra al inicio)
    dom.append(("ref", "=ilike", "__ __%"))  # heurística: "FC A ..." => 2 chars, espacio, 1 char

    limit = int(args.limit) if int(args.limit) > 0 else None
    ids = search(c, "account.move", dom, limit=limit, order="id asc")
    if skip_ids:
        ids = [i for i in ids if int(i) not in skip_ids]
    print(f"moves_target={len(ids)} limit={limit or 0} skip={len(skip_ids)}")

    rows: list[dict[str, Any]] = []
    for part in chunked(ids, 250):
        for mv in read(c, "account.move", part, ["id", "name", "ref", "state"]):
            mid = int(mv["id"])
            name = str(mv.get("name") or "")
            ref = str(mv.get("ref") or "")
            pv_nro = derive_pv_nro_from_name_or_ref(name, ref)
            if not pv_nro:
                rows.append(
                    {
                        "move_id": mid,
                        "state": mv.get("state"),
                        "name": name,
                        "ref_old": ref,
                        "ref_new": "",
                        "action": "SKIP_NO_PV_NRO",
                        "reason": "no_pv_nro",
                    }
                )
                continue

            new_ref, reason = build_new_ref(ref, pv_nro)
            if not new_ref:
                rows.append(
                    {
                        "move_id": mid,
                        "state": mv.get("state"),
                        "name": name,
                        "ref_old": ref,
                        "ref_new": "",
                        "action": "SKIP_NO_DOC_LETTER",
                        "reason": reason,
                    }
                )
                continue

            if new_ref.strip() == ref.strip():
                rows.append(
                    {
                        "move_id": mid,
                        "state": mv.get("state"),
                        "name": name,
                        "ref_old": ref,
                        "ref_new": new_ref,
                        "action": "NOOP",
                        "reason": "already_ok",
                    }
                )
                continue

            if apply_enabled:
                ok = write(c, "account.move", [mid], {"ref": new_ref})
                action = "WROTE" if ok else "WRITE_FAILED"
            else:
                action = "DRYRUN"

            rows.append(
                {
                    "move_id": mid,
                    "state": mv.get("state"),
                    "name": name,
                    "ref_old": ref,
                    "ref_new": new_ref,
                    "action": action,
                    "reason": reason,
                }
            )

    if args.out_csv.strip():
        out_path = args.out_csv.strip()
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=["move_id", "state", "name", "ref_old", "ref_new", "action", "reason"],
            )
            w.writeheader()
            w.writerows(rows)
        print(f"CSV: {out_path}")

    from collections import Counter

    c_actions = Counter(r["action"] for r in rows)
    print("Resumen actions:")
    for k, v in c_actions.most_common():
        print(f"- {k}: {v}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

