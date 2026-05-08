#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix post-migration names that break l10n_ar tax settlement parsing.

Problem:
  l10n_ar does `pos, invoice_number = document_number.split('-')` expecting exactly ONE '-'
  (PV-NRO). If name contains extra hyphens (e.g. "FA-A 00010-00100648") it crashes.

This script converts:
  "FA-A 00010-00100648" -> "00010-00100648"

Read-only by default. To write: --apply --i-know-what-im-doing
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


NAME_BAD_RE = re.compile(r"^[A-Z]{1,3}-[A-Z]\s+(\d{5}-\d{2,})\s*$")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--journal-code", type=str, default="FACOM")
    ap.add_argument("--only-posted", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out-csv", type=str, default="", help="CSV backup/preview recomendado")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--i-know-what-im-doing", action="store_true")
    args = ap.parse_args()

    apply_enabled = bool(args.apply and args.i_know_what_im_doing)
    if args.apply and not apply_enabled:
        raise SystemExit("Para escribir necesitas: --apply --i-know-what-im-doing")

    cfg = ODOO_CONFIG_MASTER_DEV.copy()
    c = connect(cfg)
    print(f"OK: {c.url} | db={c.db} | uid={c.uid}")

    journals = c.models.execute_kw(
        c.db,
        c.uid,
        c.password,
        "account.journal",
        "search_read",
        [[("code", "=", args.journal_code)]],
        {"fields": ["id", "name"], "limit": 5},
    )
    if not journals:
        raise SystemExit(f"No existe journal code={args.journal_code}")
    jid = int(journals[0]["id"])
    print(f"journal: {jid}:{journals[0].get('name')}")

    dom: list[Any] = [("move_type", "=", "in_invoice"), ("journal_id", "=", jid)]
    if args.only_posted:
        dom.append(("state", "=", "posted"))

    limit = int(args.limit) if int(args.limit) > 0 else None
    ids = search(c, "account.move", dom, limit=limit, order="id asc")
    print(f"moves_scanned={len(ids)}")

    out: list[dict[str, Any]] = []
    changed = 0
    for part in chunked(ids, 300):
        for mv in read(c, "account.move", part, ["id", "name", "state"]):
            name = (mv.get("name") or "").strip()
            m = NAME_BAD_RE.match(name)
            if not m:
                continue
            fixed = m.group(1)
            if apply_enabled:
                ok = write(c, "account.move", [int(mv["id"])], {"name": fixed})
                action = "WROTE" if ok else "WRITE_FAILED"
            else:
                action = "DRYRUN"
            out.append({"move_id": mv["id"], "state": mv.get("state"), "name_old": name, "name_new": fixed, "action": action})
            changed += 1

    print(f"candidates={len(out)}")
    if out:
        print("sample:")
        for r in out[:10]:
            print(r["move_id"], r["name_old"], "->", r["name_new"], r["action"])

    if args.out_csv.strip():
        out_path = args.out_csv.strip()
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["move_id", "state", "name_old", "name_new", "action"])
            w.writeheader()
            w.writerows(out)
        print(f"CSV: {out_path}")

    print(f"changed={changed} apply={apply_enabled}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

