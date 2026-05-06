#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnóstico solo lectura (XML-RPC): líneas de movimiento con retención/percepción
cuyo campo *name* está vacío — caso que rompe get_pos_and_number().split() en
l10n_ar_account_tax_settlement (IIBB sufrido).

No ejecuta liquidaciones ni escribe en la base.

Uso:
  cd /media/klap/raid5/cursor_files/nakel/nakel_odoo/tools/tax_settlement_diagnostico
  python3 diagnostico_iibb_sufrido_aml.py
  python3 diagnostico_iibb_sufrido_aml.py --limite-aml 500
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--limite-aml",
        type=int,
        default=200,
        help="Máximo de account.move.line con withholding_id a muestrear (defensa RPC).",
    )
    ap.add_argument(
        "--server-action-id",
        type=int,
        default=1065,
        help="ir.actions.server leído solo metadatos (opcional, 0=omitir).",
    )
    args = ap.parse_args()

    cfg = ODOO_CONFIG_MASTER_DEV.copy()
    models, uid, db, pwd = connect(cfg)
    print(f"Conectado (solo lectura): {cfg.get('url')} db={db}")

    fg = models.execute_kw(
        db,
        uid,
        pwd,
        "account.move.line",
        "fields_get",
        [[]],
        {"attributes": ["string", "type", "relation"]},
    )
    wh_field = fg.get("withholding_id") or {}
    wh_model = wh_field.get("relation")
    if not wh_model:
        print("No hay campo withholding_id en account.move.line; candidatos similares:")
        for name, meta in sorted(fg.items()):
            if "withhold" in name.lower():
                print(f"  {name}: type={meta.get('type')} relation={meta.get('relation')}")
        return 1

    print(f"withholding_id -> modelo {wh_model!r}")
    wh_meta = fg.get("withholding_id") or {}
    if wh_meta:
        print(
            f"  meta: type={wh_meta.get('type')} store={wh_meta.get('store')} "
            f"readonly={wh_meta.get('readonly')} compute={wh_meta.get('compute')!r}"
        )

    # Retenciones con name vacío (mismo fallo que .split() sobre False)
    dom_bad_name: list = ["|", ("name", "=", False), ("name", "=", "")]
    bad_ids = models.execute_kw(
        db,
        uid,
        pwd,
        wh_model,
        "search",
        [dom_bad_name],
        {"limit": 500},
    )
    print(f"Registros {wh_model} con name False o '': {len(bad_ids)} (tope búsqueda 500)")

    if bad_ids:
        rows = models.execute_kw(
            db,
            uid,
            pwd,
            wh_model,
            "read",
            [bad_ids[:50]],
            {"fields": ["id", "name", "display_name", "create_date"]},
        )
        print("Muestra retenciones sin name (hasta 50):")
        for r in rows:
            print(f"  id={r['id']!r} name={r.get('name')!r} display_name={r.get('display_name')!r}")
        print(
            "(Nota) Cruzar AML ↔ withholding por dominio RPC puede verse afectado por "
            "reglas de registro / permisos del usuario; en UI o shell Odoo suele ser más fiable."
        )

    lim = max(1, min(args.limite_aml, 5000))
    aml_domain = [("withholding_id", "!=", False)]
    aml_ids = models.execute_kw(
        db,
        uid,
        pwd,
        "account.move.line",
        "search",
        [aml_domain],
        {"limit": lim, "order": "id desc"},
    )
    if not aml_ids:
        print("No hay account.move.line con withholding_id en el muestreo.")
        return 0

    amls = models.execute_kw(
        db,
        uid,
        pwd,
        "account.move.line",
        "read",
        [aml_ids],
        {"fields": ["id", "move_id", "withholding_id", "name", "balance"]},
    )
    wh_ids = list({a["withholding_id"][0] for a in amls if a.get("withholding_id")})
    wh_rows = models.execute_kw(
        db,
        uid,
        pwd,
        wh_model,
        "read",
        [wh_ids],
        {"fields": ["id", "name", "display_name"]},
    )
    wh_by_id = {r["id"]: r for r in wh_rows}

    bad_aml: list[dict] = []
    for a in amls:
        wid = a.get("withholding_id")
        if not wid:
            continue
        wrow = wh_by_id.get(wid[0], {})
        n = wrow.get("name")
        if not n and n != "":
            bad_aml.append({**a, "_withholding_name": n})

    print(
        f"Muestreo AML con withholding_id: {len(amls)} líneas; "
        f"con retención name vacío en ese conjunto: {len(bad_aml)}"
    )
    for row in bad_aml[:30]:
        mid = row["move_id"][0] if row.get("move_id") else None
        wid = row["withholding_id"][0] if row.get("withholding_id") else None
        print(
            f"  aml_id={row['id']} move_id={mid} withholding_id={wid} "
            f"wh_name={row.get('_withholding_name')!r} line_name={row.get('name')!r}"
        )

    if args.server_action_id:
        sa = models.execute_kw(
            db,
            uid,
            pwd,
            "ir.actions.server",
            "read",
            [[args.server_action_id]],
            {"fields": ["name", "model_id", "code", "state"]},
        )
        if sa:
            s = sa[0]
            mid = s.get("model_id")
            mname = mid[1] if isinstance(mid, (list, tuple)) else mid
            print(
                f"ir.actions.server({args.server_action_id}): name={s.get('name')!r} "
                f"model={mname!r} state={s.get('state')!r}"
            )
            code = (s.get("code") or "").strip()
            if code:
                print(f"  code (primeras 200 chars): {code[:200]!r}")

    print("\nSolo lectura: no se modificó ningún registro.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
