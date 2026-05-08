#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sincronizar numeración LATAM (ej. NC-A) con el último comprobante informado por AFIP.

Caso típico: error AFIP 10016 (próximo a autorizar / correlatividad). El usuario
obtiene el último número en ARCA o con el asistente Odoo "Consultar factura en AFIP"
y lo pasa con --afip-last.

Por defecto solo consulta (dry-run). Con --apply escribe el número en borradores
indicados (--draft-move-ids), formateado como en Odoo (PV 5 dígitos + '-' + 8 dígitos).

Requiere: acceso XML-RPC (mismo patrón que tools/fix-facom).

Ejemplos:
  # Solo diagnóstico (último posteado en Odoo vs AFIP)
  python3 sync_latam_sequence_xmlrpc.py \\
    --journal-id 9 --document-type-id 3 --afip-last 594

  # Asignar el siguiente número a un borrador (594 en AFIP -> proponer 595)
  python3 sync_latam_sequence_xmlrpc.py \\
    --journal-id 9 --document-type-id 3 --afip-last 594 \\
    --apply --draft-move-ids 211693
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import xmlrpc.client
from dataclasses import dataclass
from typing import Any


def _repo_root() -> str:
    # .../nakel/nakel_odoo/tools/sync_latam_sequence_afip/thisfile.py -> .../nakel
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


sys.path.insert(0, _repo_root())

try:
    from config_nakel import ODOO_CONFIG_MASTER_DEV
except Exception:  # pragma: no cover
    ODOO_CONFIG_MASTER_DEV = None  # type: ignore


@dataclass(frozen=True)
class OdooConn:
    url: str
    db: str
    uid: int
    password: str
    models: Any


def connect(url: str, db: str, username: str, password: str) -> OdooConn:
    url = url.rstrip("/")
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(db, username, password, {})
    if not uid:
        raise SystemExit(f"Autenticación fallida: url={url} db={db} user={username}")
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


def parse_latam_document_number(s: str | bool | None) -> tuple[int, int] | None:
    if not s or not isinstance(s, str):
        return None
    m = re.match(r"^(\d{1,5})-(\d{1,8})$", s.strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def format_latam_document_number(pv: int, n: int) -> str:
    return f"{int(pv):05d}-{int(n):08d}"


def main() -> None:
    p = argparse.ArgumentParser(description="Dry-run / ajuste numeración LATAM vs AFIP (XML-RPC)")
    p.add_argument("--url", default=os.environ.get("ODOO_URL", ""))
    p.add_argument("--db", default=os.environ.get("ODOO_DB", ""))
    p.add_argument("--user", default=os.environ.get("ODOO_USER", ""))
    p.add_argument("--password", default=os.environ.get("ODOO_PASSWORD", ""))
    p.add_argument("--journal-id", type=int, required=True)
    p.add_argument("--document-type-id", type=int, required=True, help="l10n_latam.document.type id, ej. 3 = NC A")
    p.add_argument("--afip-last", type=int, required=True, help="Último número (solo parte correlativa) según AFIP / asistente")
    p.add_argument(
        "--pv-override",
        type=int,
        default=0,
        help="Punto de venta para formatear (default: journal.l10n_ar_afip_pos_number)",
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="Escribir l10n_latam_document_number en borradores (sin esto solo informa)",
    )
    p.add_argument(
        "--draft-move-ids",
        type=str,
        default="",
        help="IDs de account.move en borrador, separados por coma (ej. 211693)",
    )
    args = p.parse_args()

    if ODOO_CONFIG_MASTER_DEV and not (args.url and args.db and args.user and args.password):
        cfg = ODOO_CONFIG_MASTER_DEV
        args.url = args.url or cfg.get("url", "")
        args.db = args.db or cfg.get("db", "")
        args.user = args.user or cfg.get("username", "")
        args.password = args.password or cfg.get("password", "")

    if not all([args.url, args.db, args.user, args.password]):
        raise SystemExit(
            "Faltan credenciales: use --url/--db/--user/--password o variables "
            "ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD o config_nakel ODOO_CONFIG_MASTER_DEV"
        )

    c = connect(args.url, args.db, args.user, args.password)

    journals = search_read(
        c,
        "account.journal",
        [["id", "=", args.journal_id]],
        fields=["name", "code", "l10n_ar_afip_pos_number"],
        limit=1,
    )
    if not journals:
        raise SystemExit(f"No existe account.journal id={args.journal_id}")
    j = journals[0]
    pv = int(args.pv_override or j.get("l10n_ar_afip_pos_number") or 0)
    if not pv:
        raise SystemExit(
            "No se pudo determinar PV: configure journal.l10n_ar_afip_pos_number o use --pv-override"
        )

    doc_types = search_read(
        c,
        "l10n_latam.document.type",
        [["id", "=", args.document_type_id]],
        fields=["name", "code"],
        limit=1,
    )
    if not doc_types:
        raise SystemExit(f"No existe l10n_latam.document.type id={args.document_type_id}")

    posted = search_read(
        c,
        "account.move",
        [
            ["journal_id", "=", args.journal_id],
            ["l10n_latam_document_type_id", "=", args.document_type_id],
            ["state", "=", "posted"],
        ],
        fields=["id", "name", "l10n_latam_document_number"],
        limit=1,
        order="id desc",
    )

    odoo_last_num: int | None = None
    odoo_last_pair: tuple[int, int] | None = None
    if posted:
        raw = posted[0].get("l10n_latam_document_number")
        odoo_last_pair = parse_latam_document_number(raw)
        if odoo_last_pair:
            odoo_pv, odoo_last_num = odoo_last_pair
            if odoo_pv != pv:
                print(
                    f"AVISO: último posteado en Odoo usa PV {odoo_pv}, journal indica PV {pv}. "
                    "Revise coherencia.",
                    file=sys.stderr,
                )

    afip_last = int(args.afip_last)
    next_required = afip_last + 1

    print("=== Dry-run / diagnóstico ===")
    print(f"Base:        {args.db}")
    print(f"Diario:      {j.get('name')} (id={args.journal_id}, code={j.get('code')})")
    print(f"Tipo doc:    {doc_types[0].get('name')} (id={args.document_type_id})")
    print(f"PV (formato): {pv}")
    if posted:
        print(
            f"Último Odoo:  {posted[0].get('l10n_latam_document_number')!r} "
            f"(move id={posted[0].get('id')})"
        )
        if odoo_last_num is None:
            print(
                "  (no se pudo parsear PV-NRO; revise formato l10n_latam_document_number)",
                file=sys.stderr,
            )
    else:
        print("Último Odoo:  (no hay posteados con ese filtro)")
    print(f"Último AFIP:  correlativo {afip_last}")
    print(f"Siguiente OK: {format_latam_document_number(pv, next_required)} (n={next_required})")

    if odoo_last_num is not None:
        if odoo_last_num < afip_last:
            print(
                f"\n⚠ Hueco/desfase: Odoo último={odoo_last_num}, AFIP último={afip_last}. "
                "Puede haber comprobantes en AFIP que no están en Odoo (emisión fuera de Odoo o error humano)."
            )
        elif odoo_last_num > afip_last:
            print(
                f"\n⚠ Conflicto: Odoo último={odoo_last_num} > AFIP último={afip_last}. "
                "Revise ambiente (homologación/producción) o datos AFIP."
            )

    if not args.apply:
        print("\n(Modo solo lectura: agregue --apply y --draft-move-ids para escribir en borradores)")
        return

    if not args.draft_move_ids.strip():
        raise SystemExit("Con --apply debe indicar --draft-move-ids (IDs separados por coma)")

    draft_ids = [int(x.strip()) for x in args.draft_move_ids.split(",") if x.strip()]
    if not draft_ids:
        raise SystemExit("Lista --draft-move-ids vacía")

    drafts = search_read(
        c,
        "account.move",
        [["id", "in", draft_ids]],
        fields=[
            "id",
            "state",
            "journal_id",
            "l10n_latam_document_type_id",
            "l10n_latam_document_number",
            "name",
        ],
        limit=len(draft_ids),
    )
    by_id = {r["id"]: r for r in drafts}
    n_cursor = next_required
    for mid in draft_ids:
        rec = by_id.get(mid)
        if not rec:
            print(f"SKIP id={mid}: no existe", file=sys.stderr)
            continue
        if rec.get("state") != "draft":
            print(f"SKIP id={mid}: state={rec.get('state')} (solo borrador)", file=sys.stderr)
            continue
        jid = rec["journal_id"][0] if isinstance(rec.get("journal_id"), list) else rec.get("journal_id")
        dtid = (
            rec["l10n_latam_document_type_id"][0]
            if isinstance(rec.get("l10n_latam_document_type_id"), list)
            else rec.get("l10n_latam_document_type_id")
        )
        if jid != args.journal_id or dtid != args.document_type_id:
            print(
                f"SKIP id={mid}: journal o tipo distinto (journal={jid}, tipo={dtid})",
                file=sys.stderr,
            )
            continue
        new_str = format_latam_document_number(pv, n_cursor)
        print(f"APPLY move {mid}: l10n_latam_document_number={new_str}")
        c.models.execute_kw(
            c.db,
            c.uid,
            c.password,
            "account.move",
            "write",
            [[mid], {"l10n_latam_document_number": new_str}],
        )
        n_cursor += 1

    print("\nListo. Revise el borrador en Odoo y vuelva a validar con AFIP.")


if __name__ == "__main__":
    main()
