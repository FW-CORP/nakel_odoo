#!/usr/bin/env python3
"""
Habilita el menú Inventario → Reporting (Reportes) para Encargados Belgrano 1–4 en master_dev.

Objetivo:
  - Sin dar Inventory / Administrator (51) a cajeros/encargados, agregar los grupos
    Encargados Belgrano 1–4 (ids res.groups resueltos por nombre) al menú
    `ir.ui.menu` "Reporting" bajo "Inventory".

Alcance (master_dev actual):
  - Menú raíz: Inventory (id variable por base)
  - Submenú: Reporting (id variable por base; en master_dev actual id=352)
  - Hijos directos (Stock, Moves History, Moves Analysis, Valuation) no tienen groups_id,
    por lo que al habilitar "Reporting" ya quedan visibles si el usuario puede ver Inventory.
  - "Locations" tiene groups_id técnicos propios; no se modifica aquí.

Modo:
  - Por defecto: DRY-RUN (no escribe)
  - --apply: aplica write en ir.ui.menu.groups_id

Notas:
  - Solo usa ODOO_CONFIG_MASTER_DEV (no contempla master_18; deprecado).
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


ENCARGADOS_NAMES = [
    "Encargados Belgrano 1",
    "Encargados Belgrano 2",
    "Encargados Belgrano 3",
    "Encargados Belgrano 4",
]


def main():
    ap = argparse.ArgumentParser(
        description="Inventario→Reporting: agregar Encargados Belgrano 1–4 (master_dev)"
    )
    ap.add_argument("--apply", action="store_true", help="Aplicar cambios (por defecto dry-run)")
    args = ap.parse_args()

    url, db, uid, pwd, m = conectar()
    print(f"✅ Conectado a {url} / {db}")
    print(f"Modo: {'APPLY' if args.apply else 'DRY-RUN'}\n")

    # 1) Resolver grupos Encargados Belgrano por nombre
    enc_rows = m.execute_kw(
        db,
        uid,
        pwd,
        "res.groups",
        "search_read",
        [[("name", "in", ENCARGADOS_NAMES)]],
        {"fields": ["id", "name"], "limit": 20},
    )
    found = {r["name"]: r["id"] for r in enc_rows}
    missing = [n for n in ENCARGADOS_NAMES if n not in found]
    if missing:
        print("❌ Faltan grupos Encargados en la base:")
        for n in missing:
            print(f"   - {n}")
        sys.exit(1)

    enc_ids = [found[n] for n in ENCARGADOS_NAMES]
    print("Grupos Encargados Belgrano:")
    for n in ENCARGADOS_NAMES:
        print(f"  - {n}: id={found[n]}")
    print()

    # 2) Resolver Inventory root menu y Reporting submenu
    inv = m.execute_kw(
        db,
        uid,
        pwd,
        "ir.ui.menu",
        "search_read",
        [[("parent_id", "=", False), ("name", "=", "Inventory")]],
        {"fields": ["id", "name", "groups_id"], "limit": 1},
    )
    if not inv:
        print("❌ No se encontró menú raíz 'Inventory'")
        sys.exit(1)
    inv = inv[0]
    inv_id = inv["id"]

    rep = m.execute_kw(
        db,
        uid,
        pwd,
        "ir.ui.menu",
        "search_read",
        [[("parent_id", "=", inv_id), ("name", "=", "Reporting")]],
        {"fields": ["id", "name", "groups_id"], "limit": 1},
    )
    if not rep:
        print("❌ No se encontró menú 'Reporting' bajo 'Inventory'")
        sys.exit(1)
    rep = rep[0]
    rep_id = rep["id"]
    rep_groups = list(rep.get("groups_id") or [])

    print(f"Menú Inventory: id={inv_id}, groups_id={inv.get('groups_id') or []}")
    print(f"Menú Reporting: id={rep_id}, groups_id={rep_groups}")

    new_groups = sorted(set(rep_groups + enc_ids))
    if new_groups == sorted(set(rep_groups)):
        print("\n✅ Reporting ya incluye los grupos Encargados (nada que hacer).")
        return

    print(f"\nPreview groups_id nuevo para Reporting: {new_groups}")

    if not args.apply:
        print("\n🔍 DRY-RUN: no se aplican cambios.")
        print("   Ejecuta con --apply para escribir ir.ui.menu.groups_id.")
        return

    ok = m.execute_kw(
        db,
        uid,
        pwd,
        "ir.ui.menu",
        "write",
        [[rep_id], {"groups_id": [(6, 0, new_groups)]}],
    )
    if ok:
        print("\n✅ Actualizado. Usuarios deben cerrar sesión y volver a entrar.")
    else:
        print("\n❌ No se pudo actualizar el menú Reporting (write devolvió False).")


if __name__ == "__main__":
    main()

