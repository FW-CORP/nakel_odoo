#!/usr/bin/env python3
"""
Lista vistas `ir.ui.view` cuyo `arch_db` menciona `action_view_partner_invoices`
(smart button «Facturado» en ficha de contacto).

Sirve para ver si una **herencia Nakel** cambió el atributo `groups=` del botón
respecto al estándar Odoo 18 (`account.group_account_invoice` **o**
`account.group_account_readonly`).

Solo lectura (no modifica la base).

Uso:
  python3 auditar_vista_boton_facturado_partner.py --master-dev
  python3 auditar_vista_boton_facturado_partner.py --master-18
"""

from __future__ import annotations

import argparse
import re
import sys
import xmlrpc.client

sys.path.insert(0, "/media/klap/raid5/cursor_files")

try:
    from config_nakel import ODOO_CONFIG_MASTER18, ODOO_CONFIG_MASTER_DEV
except ImportError:
    print("❌ No se pudo importar config_nakel desde /media/klap/raid5/cursor_files")
    sys.exit(1)


def pick_config(master_dev: bool) -> dict:
    src = ODOO_CONFIG_MASTER_DEV if master_dev else ODOO_CONFIG_MASTER18
    return {
        "url": src["url"],
        "db": src["db"],
        "user": src["username"],
        "pass": src["password"],
    }


def connect(cfg: dict):
    common = xmlrpc.client.ServerProxy(f"{cfg['url']}/xmlrpc/2/common")
    uid = common.authenticate(cfg["db"], cfg["user"], cfg["pass"], {})
    if not uid:
        return None, None, "Autenticación fallida"
    models = xmlrpc.client.ServerProxy(f"{cfg['url']}/xmlrpc/2/object")
    return models, uid, None


def snippet_around(arch: str, needle: str, radius: int = 320) -> str:
    i = arch.find(needle)
    if i < 0:
        return ""
    a = max(0, i - radius)
    b = min(len(arch), i + len(needle) + radius)
    return arch[a:b].replace("\n", " ")


def extract_groups_near_button(arch: str) -> str | None:
    """Intenta localizar groups= en el mismo <button ...> que el name."""
    for m in re.finditer(
        r'<button\b[^>]*\bname="action_view_partner_invoices"[^>]*>',
        arch,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        frag = m.group(0)
        gm = re.search(r'\bgroups="([^"]*)"', frag)
        if gm:
            return gm.group(1)
    for m in re.finditer(
        r'<button\b[^>]*\bname=[\'"]action_view_partner_invoices[\'"][^>]*>',
        arch,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        frag = m.group(0)
        gm = re.search(r"\bgroups=['\"]([^'\"]*)['\"]", frag)
        if gm:
            return gm.group(1)
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auditar vistas XML del botón Facturado (partner invoices)"
    )
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--master-dev", action="store_true")
    g.add_argument("--master-18", action="store_true")
    args = parser.parse_args()

    cfg = pick_config(args.master_dev)
    amb = "master_dev" if args.master_dev else "master_18"
    print("=" * 72)
    print(f"Vistas con action_view_partner_invoices  |  {amb}  |  {cfg['db']}")
    print("=" * 72)

    models, uid, err = connect(cfg)
    if err:
        print(f"❌ {err}")
        sys.exit(1)

    db, pwd = cfg["db"], cfg["pass"]
    ids = models.execute_kw(
        db,
        uid,
        pwd,
        "ir.ui.view",
        "search",
        [[("arch_db", "ilike", "action_view_partner_invoices")]],
    )
    if not ids:
        print("ℹ️  Ninguna vista encontrada (raro en Odoo con account instalado).")
        return

    rows = models.execute_kw(
        db,
        uid,
        pwd,
        "ir.ui.view",
        "read",
        [ids],
        {"fields": ["id", "name", "model", "inherit_id", "mode", "active"]},
    )
    archs = models.execute_kw(
        db,
        uid,
        pwd,
        "ir.ui.view",
        "read",
        [ids],
        {"fields": ["id", "arch_db"]},
    )
    arch_by_id = {r["id"]: r.get("arch_db") or "" for r in archs}

    std = "account.group_account_invoice,account.group_account_readonly"
    print(f"\nReferencia estándar Odoo 18 (botón): groups=\"{std}\" (OR entre grupos)\n")

    for r in sorted(rows, key=lambda x: x["id"]):
        vid = r["id"]
        arch = arch_by_id.get(vid, "")
        gstr = extract_groups_near_button(arch)
        inh = r.get("inherit_id")
        inh_txt = f"{inh[1]} (id {inh[0]})" if inh else "—"
        print(f"— id={vid}  active={r.get('active')}  model={r.get('model')}")
        print(f"  name: {r.get('name')}")
        print(f"  inherit_id: {inh_txt}")
        if gstr is not None:
            print(f"  groups (detectado en <button>): {gstr}")
            if std not in gstr.replace(" ", "") and "group_account_readonly" not in gstr:
                print("  ⚠️  No incluye explícitamente group_account_readonly; revisar si es intencional.")
        else:
            print("  groups: (no detectado en una sola línea de button; ver recorte)")
        sn = snippet_around(arch, "action_view_partner_invoices")
        if sn:
            print(f"  recorte: …{sn}…")
        print()


if __name__ == "__main__":
    main()
