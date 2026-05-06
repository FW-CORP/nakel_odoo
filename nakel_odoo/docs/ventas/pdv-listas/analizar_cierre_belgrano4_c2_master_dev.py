#!/usr/bin/env python3
"""
Análisis operativo (solo lectura) de cierres POS y su impacto contable.

Foco: Belgrano4-C2 en master_dev.

Qué hace:
- Lee pos.config (cash_journal_id, journal_id, payment_method_ids)
- Lee N sesiones recientes (pos.session) y sus move_id
- Para cada move_id: trae líneas de account.move.line y resume por diario/cuenta
- Trae pos.payment de órdenes de la sesión (si existe modelo/campos) y resume por método/diario

Objetivo: explicar por qué el asiento de cierre impacta en "Cheques".
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import xmlrpc.client
from dataclasses import dataclass
from datetime import datetime
from typing import Any

sys.path.insert(0, "/media/klap/raid5/cursor_files")
from config_nakel import ODOO_CONFIG_MASTER_DEV  # noqa: E402


@dataclass(frozen=True)
class OdooConn:
    url: str
    db: str
    uid: int
    password: str
    models: Any


def connect() -> OdooConn:
    url = ODOO_CONFIG_MASTER_DEV["url"].rstrip("/")
    db = ODOO_CONFIG_MASTER_DEV["db"]
    user = ODOO_CONFIG_MASTER_DEV["username"]
    pw = ODOO_CONFIG_MASTER_DEV["password"]
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, user, pw, {})
    if not uid:
        raise RuntimeError("No autenticó en Odoo.")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    return OdooConn(url=url, db=db, uid=int(uid), password=pw, models=models)


def fields(c: OdooConn, model: str) -> set[str]:
    meta = c.models.execute_kw(c.db, c.uid, c.password, model, "fields_get", [], {"attributes": ["type"]})
    return set(meta.keys())


def search_read(c: OdooConn, model: str, domain: list, wanted: list[str], *, limit: int = 0, order: str | None = None):
    existing = fields(c, model)
    fs = [f for f in wanted if f in existing]
    kwargs: dict[str, Any] = {"fields": fs}
    if limit:
        kwargs["limit"] = limit
    if order:
        kwargs["order"] = order
    return c.models.execute_kw(c.db, c.uid, c.password, model, "search_read", [domain], kwargs)


def summarize_move_lines(lines: list[dict[str, Any]]) -> dict[str, Any]:
    by_journal: dict[str, dict[str, Any]] = {}
    by_account: dict[str, dict[str, Any]] = {}

    for l in lines:
        j = l.get("journal_id")
        a = l.get("account_id")
        debit = float(l.get("debit") or 0.0)
        credit = float(l.get("credit") or 0.0)
        balance = float(l.get("balance") or (debit - credit))

        jkey = str(j[0]) if isinstance(j, list) else str(j)
        jname = j[1] if isinstance(j, list) and len(j) > 1 else ""
        aj = by_journal.setdefault(jkey, {"journal_name": jname, "debit": 0.0, "credit": 0.0, "balance": 0.0, "count": 0})
        aj["debit"] += debit
        aj["credit"] += credit
        aj["balance"] += balance
        aj["count"] += 1

        akey = str(a[0]) if isinstance(a, list) else str(a)
        aname = a[1] if isinstance(a, list) and len(a) > 1 else ""
        aa = by_account.setdefault(akey, {"account_name": aname, "debit": 0.0, "credit": 0.0, "balance": 0.0, "count": 0})
        aa["debit"] += debit
        aa["credit"] += credit
        aa["balance"] += balance
        aa["count"] += 1

    return {"by_journal": by_journal, "by_account": by_account}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="Belgrano4-C2", help="Nombre (ilike) del pos.config")
    ap.add_argument("--sessions", type=int, default=5, help="Sesiones a analizar")
    ap.add_argument("--out", default="", help="Ruta JSON salida")
    args = ap.parse_args()

    c = connect()

    cfgs = search_read(
        c,
        "pos.config",
        [("name", "ilike", args.config)],
        [
            "id",
            "name",
            "active",
            "company_id",
            "cash_journal_id",
            "journal_id",
            "payment_method_ids",
            "pricelist_id",
        ],
        limit=5,
        order="id desc",
    )
    if not cfgs:
        raise SystemExit(f"No encontré pos.config ilike {args.config!r}")
    cfg = cfgs[0]
    cfg_id = cfg["id"]

    # payment methods detail
    pm_ids = cfg.get("payment_method_ids") or []
    pms = []
    if pm_ids:
        pms = search_read(
            c,
            "pos.payment.method",
            [("id", "in", pm_ids)],
            ["id", "name", "is_cash_count", "journal_id", "split_transactions", "company_id"],
            limit=200,
            order="id asc",
        )

    sessions = search_read(
        c,
        "pos.session",
        [("config_id", "=", cfg_id)],
        [
            "id",
            "name",
            "state",
            "start_at",
            "stop_at",
            "cash_journal_id",
            "move_id",
            "cash_register_balance_start",
            "cash_register_balance_end",
            "cash_register_balance_end_real",
            "cash_real_transaction",
            "create_date",
            "user_id",
        ],
        limit=args.sessions,
        order="id desc",
    )

    moves: dict[str, Any] = {}
    for s in sessions:
        mv = s.get("move_id")
        if not mv:
            continue
        move_id = mv[0] if isinstance(mv, list) else mv
        # move header
        mh = search_read(
            c,
            "account.move",
            [("id", "=", move_id)],
            ["id", "name", "date", "state", "journal_id", "ref", "company_id", "create_date"],
            limit=1,
        )
        # move lines
        mls = search_read(
            c,
            "account.move.line",
            [("move_id", "=", move_id)],
            ["id", "name", "account_id", "debit", "credit", "balance", "journal_id", "partner_id"],
            limit=0,
            order="id asc",
        )
        moves[str(move_id)] = {
            "header": mh[0] if mh else None,
            "lines_count": len(mls),
            "summary": summarize_move_lines(mls),
            # guardamos solo top 40 líneas para no explotar el json
            "lines_sample": mls[:40],
        }

    report = {
        "meta": {"db": c.db, "url": c.url, "generated_at": datetime.utcnow().isoformat() + "Z"},
        "pos_config": cfg,
        "pos_payment_methods": pms,
        "sessions": sessions,
        "moves": moves,
    }

    out = args.out.strip()
    if not out:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = f"/media/klap/raid5/cursor_files/reportes/analisis_cierre_{cfg_id}_{ts}.json"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"✅ Reporte guardado en: {out}")
    print(f"- pos.config: {cfg.get('name')} (id {cfg_id})")
    print(f"- cash_journal_id: {cfg.get('cash_journal_id')}")
    print(f"- journal_id (ventas): {cfg.get('journal_id')}")
    print(f"- métodos de pago: {len(pms)}")
    print(f"- sesiones analizadas: {len(sessions)}")
    print(f"- moves analizados: {len(moves)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

