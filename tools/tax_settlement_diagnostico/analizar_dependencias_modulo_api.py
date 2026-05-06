#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Consulta por API (solo lectura) el estado de módulos Odoo y dependencias
declaradas en BD para un módulo técnico (p. ej. l10n_ar_account_tax_settlement).

Usa ir.module.module + ir.module.module.dependency (lo que Odoo guarda al
escanear manifests; puede diferir levemente del __manifest__.py en disco si
no se actualizó el módulo).

Uso:
  python3 analizar_dependencias_modulo_api.py
  python3 analizar_dependencias_modulo_api.py -m account_tax_settlement
"""

from __future__ import annotations

import argparse
import sys
import xmlrpc.client

ROOT = "/media/klap/raid5/cursor_files"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    from config_nakel import ODOO_CONFIG_MASTER_DEV
except ImportError as e:
    raise SystemExit(f"Falta config_nakel en {ROOT}: {e}")


def connect(cfg: dict) -> tuple[xmlrpc.client.ServerProxy, int, str, str]:
    url = str(cfg["url"]).rstrip("/")
    db = str(cfg["db"])
    user = str(cfg["username"])
    pwd = str(cfg["password"])
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)
    uid = common.authenticate(db, user, pwd, {})
    if not uid:
        raise SystemExit(f"Auth fallida: {url} db={db}")
    return models, int(uid), db, pwd


def module_state(models, uid: int, db: str, pwd: str, technical_name: str) -> dict | None:
    rows = models.execute_kw(
        db,
        uid,
        pwd,
        "ir.module.module",
        "search_read",
        [[("name", "=", technical_name)]],
        {"fields": ["name", "state", "latest_version", "summary"], "limit": 1},
    )
    return rows[0] if rows else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "-m",
        "--modulo",
        default="l10n_ar_account_tax_settlement",
        help="Nombre técnico del módulo raíz a analizar",
    )
    args = ap.parse_args()

    cfg = ODOO_CONFIG_MASTER_DEV.copy()
    models, uid, db, pwd = connect(cfg)
    print(f"API solo lectura: {cfg.get('url')} db={db}\n")

    root = args.modulo
    mod = module_state(models, uid, db, pwd, root)
    if not mod:
        print(f"No existe en ir.module.module: {root!r}")
        return 1

    print(f"Módulo {root!r}")
    print(f"  state={mod.get('state')!r} latest_version={mod.get('latest_version')!r}")
    summ = (mod.get("summary") or "")[:120]
    if summ:
        print(f"  summary: {summ!r}…")

    mid = models.execute_kw(
        db,
        uid,
        pwd,
        "ir.module.module",
        "search",
        [[("name", "=", root)]],
        {"limit": 1},
    )
    if not mid:
        return 1

    dep_rows = models.execute_kw(
        db,
        uid,
        pwd,
        "ir.module.module.dependency",
        "search_read",
        [[("module_id", "=", mid[0])]],
        {"fields": ["name"]},
    )
    dep_names = sorted({r["name"] for r in dep_rows if r.get("name")})
    print(f"\nDependencias en BD (ir.module.module.dependency): {len(dep_names)}")
    for n in dep_names:
        st = module_state(models, uid, db, pwd, n)
        if st:
            print(f"  {n:45} state={st.get('state')!r} ver={st.get('latest_version')!r}")
        else:
            print(f"  {n:45} (no aparece como módulo instalable / no escaneado)")

    print("\nSolo lectura.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
