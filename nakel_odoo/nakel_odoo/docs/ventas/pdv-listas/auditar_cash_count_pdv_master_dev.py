#!/usr/bin/env python3
"""
Auditoría (solo lectura) de configuración POS relacionada a cash control.

Objetivo:
- Detectar PDVs (pos.config) que tengan >=2 métodos de pago con is_cash_count=True
- Ver qué cash_journal_id queda en las últimas N sesiones de cada PDV

Salida: JSON + resumen en consola.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import xmlrpc.client
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name-ilike", default="Belgrano", help="Filtro pos.config name ilike (default: Belgrano)")
    ap.add_argument("--sessions", type=int, default=5, help="Sesiones recientes por PDV")
    ap.add_argument("--out", default="", help="Ruta JSON salida (opcional)")
    args = ap.parse_args()

    c = connect()

    cfgs = search_read(
        c,
        "pos.config",
        [("name", "ilike", args.name_ilike)],
        ["id", "name", "active", "company_id", "payment_method_ids", "cash_journal_id", "journal_id"],
        limit=0,
        order="id asc",
    )

    # Payment methods cache
    all_pm_ids: set[int] = set()
    for cfg in cfgs:
        for pid in cfg.get("payment_method_ids") or []:
            all_pm_ids.add(int(pid))

    pm_map: dict[int, dict[str, Any]] = {}
    if all_pm_ids:
        pms = search_read(
            c,
            "pos.payment.method",
            [("id", "in", list(sorted(all_pm_ids)))],
            ["id", "name", "is_cash_count", "journal_id", "split_transactions"],
            limit=0,
            order="id asc",
        )
        pm_map = {int(pm["id"]): pm for pm in pms}

    results: list[dict[str, Any]] = []
    flagged: list[dict[str, Any]] = []

    for cfg in cfgs:
        cfg_id = int(cfg["id"])
        pm_ids = [int(x) for x in (cfg.get("payment_method_ids") or [])]
        cash_pms = [pm_map[i] for i in pm_ids if i in pm_map and pm_map[i].get("is_cash_count")]

        # sesiones
        sess = search_read(
            c,
            "pos.session",
            [("config_id", "=", cfg_id)],
            ["id", "name", "state", "cash_journal_id", "start_at", "stop_at", "create_date"],
            limit=args.sessions,
            order="id desc",
        )
        cash_journals_seen = []
        for s in sess:
            cj = s.get("cash_journal_id")
            if isinstance(cj, list) and cj:
                cash_journals_seen.append({"id": cj[0], "name": cj[1] if len(cj) > 1 else ""})
            else:
                cash_journals_seen.append({"id": None, "name": ""})

        row = {
            "pos_config": {
                "id": cfg_id,
                "name": cfg.get("name"),
                "active": cfg.get("active"),
                "cash_journal_id": cfg.get("cash_journal_id"),
                "journal_id": cfg.get("journal_id"),
            },
            "cash_count_payment_methods": [
                {
                    "id": int(pm["id"]),
                    "name": pm.get("name"),
                    "journal_id": pm.get("journal_id"),
                    "split_transactions": pm.get("split_transactions"),
                }
                for pm in cash_pms
            ],
            "recent_sessions": sess,
            "recent_sessions_cash_journals": cash_journals_seen,
        }
        results.append(row)

        if len(cash_pms) >= 2:
            flagged.append(
                {
                    "pos_config_id": cfg_id,
                    "pos_config_name": cfg.get("name"),
                    "cash_count_methods": [pm.get("name") for pm in cash_pms],
                    "cash_journals_seen": list({(x["id"], x["name"]) for x in cash_journals_seen}),
                }
            )

    report = {
        "meta": {
            "db": c.db,
            "url": c.url,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "name_ilike": args.name_ilike,
            "sessions_per_pdv": args.sessions,
        },
        "flagged_multiple_cash_count": flagged,
        "configs": results,
    }

    out = args.out.strip()
    if not out:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = f"/media/klap/raid5/cursor_files/reportes/auditoria_cash_count_{args.name_ilike}_{ts}.json"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"✅ Reporte guardado en: {out}")
    print(f"- PDVs analizados: {len(cfgs)}")
    print(f"- PDVs con >=2 métodos cash_count: {len(flagged)}")
    for x in flagged[:30]:
        cj = ", ".join([f"{a[1]}({a[0]})" for a in x.get("cash_journals_seen", []) if a[0] is not None])
        print(
            f"  - {x['pos_config_name']} (id {x['pos_config_id']}): {x['cash_count_methods']} | "
            f"cash_journal sesiones: {cj or 'N/A'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

