#!/usr/bin/env python3
"""
master_dev: habilitar smart button «Estado del cliente» (open_customer_statement) para vendedores.

Contexto (diagnóstico 2026-04):
  - En master_dev, el botón open_customer_statement estaba restringido a:
      groups="account.group_account_invoice"
    lo que oculta el botón a vendedores que tienen `account.group_account_readonly` + grupo Nakel
    `Vendedores - Preventistas` (102), pero no `account.group_account_invoice`.

Objetivo (opción B, granular por rol negocio):
  - Ajustar el botón para que sea visible si el usuario tiene:
      account.group_account_invoice OR nakel_perm_scripts.group_vendedores_preventistas
    sin conceder grupos contables amplios adicionales.

Implementación:
  - NO se edita la vista existente: se crea una vista heredada nueva sobre `res.partner.form`
    que actualiza el atributo groups del botón mediante xpath.
  - Por defecto: DRY-RUN (no escribe). Usar --apply para crear/activar la vista.
  - Para deshacer: usar --rollback --apply para desactivar la vista creada por este script.
"""

import sys
import argparse
import xmlrpc.client

sys.path.insert(0, "/media/klap/raid5/cursor_files")

try:
    from config_nakel import ODOO_CONFIG_MASTER_DEV
except ImportError:
    print("❌ No se pudo importar config_nakel.py")
    sys.exit(1)


VIEW_NAME = "Nakel: Partner button Estado del cliente (vendedores)"
VIEW_KEY = "nakel_perm_scripts.res_partner_open_customer_statement_groups"

# groups attr uses OR semantics with comma
GROUPS_ATTR = "account.group_account_invoice,nakel_perm_scripts.group_vendedores_preventistas"


def conectar():
    cfg = ODOO_CONFIG_MASTER_DEV
    url = cfg["url"]
    db = cfg["db"]
    user = cfg["username"]
    pwd = cfg["password"]

    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, user, pwd, {})
    if not uid:
        raise RuntimeError("Autenticación fallida")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    return url, db, uid, pwd, models


def _xmlid_exists(m, db, uid, pwd, module, name):
    rows = m.execute_kw(
        db,
        uid,
        pwd,
        "ir.model.data",
        "search_read",
        [[("module", "=", module), ("name", "=", name)]],
        {"fields": ["module", "name", "model", "res_id"], "limit": 1},
    )
    return rows[0] if rows else None


def _find_parent_view(m, db, uid, pwd):
    # parent: res.partner.form
    rows = m.execute_kw(
        db,
        uid,
        pwd,
        "ir.ui.view",
        "search_read",
        [[("model", "=", "res.partner"), ("name", "=", "res.partner.form")]],
        {"fields": ["id", "name"], "limit": 1},
    )
    return rows[0] if rows else None


def _find_our_view(m, db, uid, pwd):
    rows = m.execute_kw(
        db,
        uid,
        pwd,
        "ir.ui.view",
        "search_read",
        [[("key", "=", VIEW_KEY)]],
        {"fields": ["id", "name", "key", "active", "inherit_id", "priority"], "limit": 1},
    )
    return rows[0] if rows else None


def main():
    ap = argparse.ArgumentParser(description="Habilitar Estado del cliente a vendedores (master_dev)")
    ap.add_argument("--apply", action="store_true", help="Crear/activar/desactivar (por defecto dry-run)")
    ap.add_argument("--rollback", action="store_true", help="Desactivar la vista creada por este script")
    args = ap.parse_args()

    url, db, uid, pwd, m = conectar()
    print(f"✅ Conectado a {url} / {db}")
    print(f"Modo: {'APPLY' if args.apply else 'DRY-RUN'}")
    if args.rollback:
        print("Acción: rollback (desactivar vista)\n")
    else:
        print("Acción: crear/activar vista\n")

    # sanity: required XMLID exists
    need = [
        ("account", "group_account_invoice"),
        ("nakel_perm_scripts", "group_vendedores_preventistas"),
    ]
    for mod, name in need:
        row = _xmlid_exists(m, db, uid, pwd, mod, name)
        if not row:
            print(f"❌ Falta XMLID requerido: {mod}.{name}")
            sys.exit(1)
        print(f"✅ XMLID OK: {mod}.{name} → {row['model']}({row['res_id']})")

    parent = _find_parent_view(m, db, uid, pwd)
    if not parent:
        print("❌ No se encontró vista padre 'res.partner.form' (res.partner)")
        sys.exit(1)
    parent_id = parent["id"]
    print(f"✅ Vista padre: {parent['name']} (id={parent_id})")

    existing = _find_our_view(m, db, uid, pwd)

    if args.rollback:
        if not existing:
            print("ℹ️  No existe la vista (nada que desactivar).")
            return
        if not args.apply:
            print(f"🔍 DRY-RUN: desactivaría la vista id={existing['id']} key={VIEW_KEY!r}")
            print("   Ejecuta con --rollback --apply para desactivar.")
            return
        ok = m.execute_kw(
            db,
            uid,
            pwd,
            "ir.ui.view",
            "write",
            [[existing["id"]], {"active": False}],
        )
        print("✅ Vista desactivada." if ok else "❌ No se pudo desactivar (write devolvió False).")
        return

    if existing:
        print(f"ℹ️  Ya existe vista key={VIEW_KEY!r}: id={existing['id']} active={existing.get('active')}")
        if not existing.get("active", True):
            if not args.apply:
                print("🔍 DRY-RUN: la reactivaría.")
                print("   Ejecuta con --apply para reactivar.")
                return
            ok = m.execute_kw(
                db, uid, pwd, "ir.ui.view", "write", [[existing["id"]], {"active": True}]
            )
            print("✅ Vista reactivada." if ok else "❌ No se pudo reactivar.")
        return

    arch = f"""<data>
  <xpath expr=\"//button[@name='open_customer_statement']\" position=\"attributes\">
    <attribute name=\"groups\">{GROUPS_ATTR}</attribute>
  </xpath>
</data>"""

    vals = {
        "name": VIEW_NAME,
        "key": VIEW_KEY,
        "type": "form",
        "model": "res.partner",
        "inherit_id": parent_id,
        "priority": 99,
        "arch_db": arch,
        "active": True,
    }

    print("\nVista a crear (preview):")
    print(f"  name={VIEW_NAME!r}")
    print(f"  key={VIEW_KEY!r}")
    print(f"  inherit_id={parent_id}")
    print(f"  priority={vals['priority']}")
    print(f"  groups={GROUPS_ATTR!r} en botón open_customer_statement")

    if not args.apply:
        print("\n🔍 DRY-RUN: no se crea la vista.")
        print("   Ejecuta con --apply para crearla.")
        return

    new_id = m.execute_kw(db, uid, pwd, "ir.ui.view", "create", [vals])
    print(f"\n✅ Vista creada: id={new_id}")
    print("⚠️  Los usuarios deben cerrar sesión y volver a entrar.")


if __name__ == "__main__":
    main()

