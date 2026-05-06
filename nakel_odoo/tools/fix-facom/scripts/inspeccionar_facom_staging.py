#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dry-run (read-only) analysis for FACOM numbering on vendor bills.

Goal: for vendor bills (account.move in_invoice) with name like FACOM/...,
compute the desired "visible number" from account.move.ref using Paula's rule:

  ref example: "FC A 10-100648"
  target:      "FA-A 00010-00100648"

Rules:
- First token: doc type (FC/NC/ND/...)
- Second token: letter (A/B/C/M/...)
- Then parse PV-NRO from the first occurrence of \\d+-\\d+ inside ref
  - PV is left-padded to 5 digits
  - NRO is left-padded to 8 digits
- Mapping: FC -> FA (Factura); others keep same (NC, ND, ...)

No writes: only search/read/fields_get. Outputs an optional CSV report.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import xmlrpc.client
from dataclasses import dataclass
from typing import Any


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


def search_read(
    c: OdooConn,
    model: str,
    domain: list,
    *,
    fields: list[str],
    limit: int = 0,
    order: str | None = None,
) -> list[dict[str, Any]]:
    kwargs: dict[str, Any] = {"fields": fields}
    if limit:
        kwargs["limit"] = int(limit)
    if order:
        kwargs["order"] = order
    return c.models.execute_kw(c.db, c.uid, c.password, model, "search_read", [domain], kwargs)

def search(
    c: OdooConn,
    model: str,
    domain: list,
    *,
    limit: int | None = None,
    order: str | None = None,
) -> list[int]:
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


def chunked(seq: list[int], size: int) -> list[list[int]]:
    return [seq[i : i + size] for i in range(0, len(seq), size)]


def fields_get(c: OdooConn, model: str) -> set[str]:
    meta = c.models.execute_kw(c.db, c.uid, c.password, model, "fields_get", [], {"attributes": ["type"]})
    return set(meta.keys())


def only_existing(desired: list[str], existing: set[str]) -> list[str]:
    return [f for f in desired if f in existing]


_PV_NRO_RE = re.compile(r"(\d{1,10})\s*-\s*(\d{1,20})")
_DOC_LETTER_PREFIX_RE = re.compile(r"^\s*([A-Z]{1,3})\s+([A-Z])\b")
_DIGITS_RE = re.compile(r"\d+")


def _split_digits_to_pv_nro(digits: str) -> tuple[str, str] | None:
    # keep digits only
    d = re.sub(r"\D+", "", digits or "")
    if not d:
        return None
    nro = d[-8:].zfill(8)
    pv = d[:-8][-5:].zfill(5) if len(d) > 8 else "00000"
    return pv, nro


def normalize_from_ref_paula(ref: str) -> tuple[str | None, str]:
    """
    Paula format:
      "<DOC> <LETTER> <PV>-<NRO>"
    Examples seen:
      "FC A 10-100648" -> "FA-A 00010-00100648"
      "ND A 909-5120009" -> "ND-A 00909-005120009" (note: if NRO is > 8 digits, we keep it)

    The user requirement states PV=5 digits, NRO=8 digits. If the parsed NRO has
    more than 8 digits, we do not truncate in dry-run; we just keep it as-is.
    """
    ref = (ref or "").strip()
    if not ref:
        return None, "ref_vacia"

    # 1) Preferred: "<DOC> <LETTER>" prefix + PV-NRO anywhere
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

        # doc mapping
        doc_map = {"FC": "FA"}  # Factura compra -> Factura (FA)
        doc_out = doc_map.get((doc or "").upper(), None)

        # Fallbacks when doc/letter missing but PV-NRO is present
        if not doc_out:
            # Heuristic: if ref starts with FAC... treat as FA
            if ref.upper().startswith("FAC"):
                doc_out = "FA"
            else:
                doc_out = "FA"  # vendor bill default

        if not letter:
            letter = "A"

        reason = "ok_ref_doc_letter" if m0 else "fallback_pv_nro_sin_doc_o_letra"
        return f"{doc_out}-{letter} {pv}-{nro}", reason

    # 2) No PV-NRO: try digits-only split rule (last8=nro, previous up to5=pv)
    digits = re.sub(r"\D+", "", ref)
    if digits:
        sp = _split_digits_to_pv_nro(digits)
        if sp:
            pv, nro = sp
            # Doc/letter if present; otherwise default FA-A
            doc_out = "FA"
            if doc and doc.upper() != "FC":
                doc_out = doc.upper()
            letter_out = letter or "A"
            return f"{doc_out}-{letter_out} {pv}-{nro}", "fallback_digits_sin_guion"

    # 3) Unparseable
    return None, "no_parseable"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-moves", type=int, default=0, help="0 = sin limite (cuidado con la cantidad)")
    ap.add_argument("--only-posted", action="store_true", help="Inspeccionar solo posted")
    ap.add_argument("--journal-code", type=str, default="FACOM")
    ap.add_argument(
        "--skip-move-ids",
        type=str,
        default="",
        help="CSV de account.move IDs a omitir (ej: '21474,97028').",
    )
    ap.add_argument(
        "--out-csv",
        type=str,
        default="",
        help="Si se indica, guarda un CSV con antes/despues (dry-run).",
    )
    args = ap.parse_args()
    skip_ids: set[int] = set()
    if args.skip_move_ids.strip():
        skip_ids = {int(x.strip()) for x in args.skip_move_ids.split(",") if x.strip()}

    cfg = ODOO_CONFIG_MASTER_DEV.copy()
    c = connect(cfg)
    print(f"OK: {c.url} | db={c.db} | uid={c.uid}")

    journal_existing = fields_get(c, "account.journal")
    j_fields = only_existing(
        [
            "id",
            "name",
            "code",
            "type",
            "company_id",
            "sequence",
            "sequence_override_regex",
            "refund_sequence",
            "debit_sequence",
            "payment_sequence",
            "active",
        ],
        journal_existing,
    )
    journals = search_read(
        c,
        "account.journal",
        [("code", "=", args.journal_code)],
        fields=j_fields,
        limit=10,
        order="id desc",
    )
    print(f"\nJournals code='{args.journal_code}': {len(journals)}")
    for j in journals[:10]:
        print(f"- journal_id={j.get('id')} name={j.get('name')} type={j.get('type')} company={j.get('company_id')}")
        if "sequence" in j_fields:
            print(f"  sequence={j.get('sequence')}")
        if "sequence_override_regex" in j_fields:
            print(f"  sequence_override_regex={j.get('sequence_override_regex')}")

    move_existing = fields_get(c, "account.move")
    m_fields = only_existing(
        [
            "id",
            "name",
            "ref",
            "move_type",
            "state",
            "journal_id",
            "date",
            "invoice_date",
            "partner_id",
            "company_id",
            "sequence_prefix",
            "sequence_number",
            "secure_sequence_number",
        ],
        move_existing,
    )

    dom: list[Any] = [("move_type", "=", "in_invoice")]
    if args.only_posted:
        dom.append(("state", "=", "posted"))
    dom.extend(["|", ("name", "ilike", "FACOM"), ("name", "ilike", "/FACOM")])

    limit = int(args.limit_moves) if int(args.limit_moves) > 0 else None
    move_ids = search(c, "account.move", dom, limit=limit, order="id desc")
    if skip_ids:
        move_ids = [i for i in move_ids if int(i) not in skip_ids]
    print(f"\nVendor bills with FACOM in name: {len(move_ids)} (limit={limit or 0})")

    rows: list[dict[str, Any]] = []
    produced = 0
    by_reason: dict[str, int] = {}

    for part in chunked(move_ids, 400):
        for mv in read(c, "account.move", part, m_fields):
            ref = (mv.get("ref") or "").strip()
            new_name, reason = normalize_from_ref_paula(ref)
            if not new_name:
                # Last resort: if ref empty or unusable, derive something deterministic from old name digits
                # so we can plan a write that removes FACOM everywhere.
                old = (mv.get("name") or "")
                tail_digits = re.sub(r"\D+", "", old)[-8:]
                pv = "00000"
                nro = tail_digits.zfill(8) if tail_digits else str(int(mv.get("id") or 0)).zfill(8)
                new_name = f"FA-A {pv}-{nro}"
                reason = f"fallback_from_old_name_or_id({reason})"

            produced += 1
            by_reason[reason] = by_reason.get(reason, 0) + 1

            journal = mv.get("journal_id")
            journal_str = ""
            if isinstance(journal, (list, tuple)) and journal:
                journal_str = f"{journal[0]}:{journal[1]}"

            rows.append(
                {
                    "move_id": mv.get("id"),
                    "state": mv.get("state"),
                    "journal": journal_str,
                    "name_old": mv.get("name"),
                    "ref": ref,
                    "name_new_dryrun": new_name or "",
                    "fallback_reason": reason,
                }
            )

    # Print a small sample
    print("\nSample (top 10):")
    for r in rows[:10]:
        print(
            f"- move_id={r['move_id']} state={r['state']} name_old={r['name_old']} "
            f"ref={r['ref'] or '-'} -> new={r['name_new_dryrun'] or '-'}"
        )

    print("\nResumen:")
    print(f"- total: {len(rows)}")
    print(f"- nuevos generados: {produced}")
    print("- por razon:")
    for k in sorted(by_reason, key=lambda x: (-by_reason[x], x)):
        print(f"  - {k}: {by_reason[k]}")

    if args.out_csv.strip():
        out_path = args.out_csv.strip()
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=["move_id", "state", "journal", "name_old", "ref", "name_new_dryrun", "fallback_reason"],
            )
            w.writeheader()
            w.writerows(rows)
        print(f"\nCSV generado (dry-run): {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

