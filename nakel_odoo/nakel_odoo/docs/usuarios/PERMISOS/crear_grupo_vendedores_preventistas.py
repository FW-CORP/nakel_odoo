#!/usr/bin/env python3
"""
Crea (o actualiza) el grupo de seguridad **Vendedores - Preventistas** con
herencia del grupo estándar **Accounting / Read-only** (`account.group_account_readonly`),
necesario para consultar informes del motor `account.report` (mayor de empresa,
antigüedad de cobro, etc.) sin dar Facturación ni Administrador.

Por defecto solo conecta y muestra el plan (**dry-run**). Con **--apply** crea o
corrige el grupo.

Uso:
  python3 crear_grupo_vendedores_preventistas.py --master-dev
  python3 crear_grupo_vendedores_preventistas.py --master-dev --apply

  python3 crear_grupo_vendedores_preventistas.py --master-18
  python3 crear_grupo_vendedores_preventistas.py --master-18 --apply
"""

from __future__ import annotations

import argparse
import sys
import xmlrpc.client

sys.path.insert(0, "/media/klap/raid5/cursor_files")

try:
    from config_nakel import ODOO_CONFIG_MASTER18, ODOO_CONFIG_MASTER_DEV
except ImportError:
    print("❌ No se pudo importar config_nakel desde /media/klap/raid5/cursor_files")
    sys.exit(1)

GROUP_NAME = "Vendedores - Preventistas"
# XML ID estable para idempotencia (módulo ficticio; no requiere addon instalado)
EXT_MODULE = "nakel_perm_scripts"
EXT_NAME = "group_vendedores_preventistas"


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


def xmlid_res_id(models, uid, pwd, db: str, module: str, name: str) -> int | None:
    rows = models.execute_kw(
        db,
        uid,
        pwd,
        "ir.model.data",
        "search_read",
        [[("module", "=", module), ("name", "=", name)]],
        {"fields": ["res_id"], "limit": 1},
    )
    if not rows:
        return None
    return rows[0]["res_id"]


def resolve_account_readonly_group_id(models, uid, pwd, db: str) -> int | None:
    gid = xmlid_res_id(models, uid, pwd, db, "account", "group_account_readonly")
    if gid:
        return gid
    # Respaldo por nombre (UI ES/EN)
    for domain in [
        [("full_name", "=", "Accounting / Read-only")],
        [("name", "ilike", "solo lectura"), ("category_id.name", "ilike", "contab")],
    ]:
        rows = models.execute_kw(
            db,
            uid,
            pwd,
            "res.groups",
            "search_read",
            [domain],
            {"fields": ["id", "full_name"], "limit": 1},
        )
        if rows:
            return rows[0]["id"]
    return None


def resolve_sales_category_id(models, uid, pwd, db: str) -> int | None:
    """Categoría UI Ventas / Sales (opcional)."""
    for term in ("Sales", "Ventas", "Ventes"):
        rows = models.execute_kw(
            db,
            uid,
            pwd,
            "ir.module.category",
            "search_read",
            [[("name", "=", term)]],
            {"fields": ["id", "name"], "limit": 1},
        )
        if rows:
            return rows[0]["id"]
    rows = models.execute_kw(
        db,
        uid,
        pwd,
        "ir.module.category",
        "search_read",
        [[("name", "ilike", "sale")]],
        {"fields": ["id", "name"], "limit": 1},
    )
    return rows[0]["id"] if rows else None


def find_existing_group_id(models, uid, pwd, db: str) -> int | None:
    rid = xmlid_res_id(models, uid, pwd, db, EXT_MODULE, EXT_NAME)
    if rid:
        return rid
    gids = models.execute_kw(
        db,
        uid,
        pwd,
        "res.groups",
        "search",
        [[("name", "=", GROUP_NAME)]],
        {"limit": 1},
    )
    return gids[0] if gids else None


def implied_contains_readonly(
    models, uid, pwd, db: str, group_id: int, readonly_id: int
) -> bool:
    g = models.execute_kw(
        db,
        uid,
        pwd,
        "res.groups",
        "read",
        [[group_id]],
        {"fields": ["implied_ids"]},
    )
    if not g:
        return False
    implied = g[0].get("implied_ids") or []
    implied_ids = [x[0] if isinstance(x, (list, tuple)) else x for x in implied]
    return readonly_id in implied_ids


def ensure_external_id(
    models, uid, pwd, db: str, group_id: int, dry_run: bool
) -> None:
    existing = models.execute_kw(
        db,
        uid,
        pwd,
        "ir.model.data",
        "search",
        [[("module", "=", EXT_MODULE), ("name", "=", EXT_NAME)]],
        {"limit": 1},
    )
    if existing:
        return
    if dry_run:
        print(f"   [dry-run] Se crearía ir.model.data {EXT_MODULE}.{EXT_NAME} → res.groups id={group_id}")
        return
    models.execute_kw(
        db,
        uid,
        pwd,
        "ir.model.data",
        "create",
        [
            {
                "name": EXT_NAME,
                "module": EXT_MODULE,
                "model": "res.groups",
                "res_id": group_id,
            }
        ],
    )
    print(f"   ✅ Creado XML ID {EXT_MODULE}.{EXT_NAME}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Grupo 'Vendedores - Preventistas' con implied Accounting / Read-only"
    )
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--master-dev", action="store_true", help="Base master_dev")
    g.add_argument("--master-18", action="store_true", help="Base master_18")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Crear/actualizar grupo (sin este flag solo dry-run)",
    )
    args = parser.parse_args()

    cfg = pick_config(args.master_dev)
    amb = "master_dev" if args.master_dev else "master_18"

    print("=" * 72)
    print(f"Grupo: «{GROUP_NAME}» → implied account.group_account_readonly")
    print(f"Base: {cfg['db']}  |  Host: {cfg['url']}  |  Modo: {'APPLY' if args.apply else 'DRY-RUN'}")
    print("=" * 72)

    models, uid, err = connect(cfg)
    if err:
        print(f"❌ {err}")
        sys.exit(1)
    print("✅ Conexión XML-RPC OK\n")

    db, pwd = cfg["db"], cfg["pass"]

    readonly_id = resolve_account_readonly_group_id(models, uid, pwd, db)
    if not readonly_id:
        print("❌ No se encontró account.group_account_readonly ni equivalente.")
        sys.exit(1)
    gr = models.execute_kw(
        db,
        uid,
        pwd,
        "res.groups",
        "read",
        [[readonly_id]],
        {"fields": ["full_name", "name"]},
    )[0]
    print(f"✅ Grupo estándar solo lectura: id={readonly_id} — {gr.get('full_name') or gr.get('name')}")

    cat_id = resolve_sales_category_id(models, uid, pwd, db)
    if cat_id:
        c = models.execute_kw(
            db,
            uid,
            pwd,
            "ir.module.category",
            "read",
            [[cat_id]],
            {"fields": ["name"]},
        )[0]
        print(f"✅ Categoría UI para el nuevo grupo: [{cat_id}] {c.get('name')}")
    else:
        print("ℹ️  Sin categoría Sales/Ventas; el grupo se creará sin category_id")

    existing_id = find_existing_group_id(models, uid, pwd, db)

    if existing_id:
        ok = implied_contains_readonly(models, uid, pwd, db, existing_id, readonly_id)
        print(f"\n📌 Grupo existente: res.groups id={existing_id} name={GROUP_NAME}")
        if ok:
            print("   ✅ Ya hereda Accounting / Read-only (implied_ids).")
            ensure_external_id(models, uid, pwd, db, existing_id, not args.apply)
            if not args.apply:
                print("\n🔍 DRY-RUN: nada que modificar. Usa --apply solo si querés recrear XML ID faltante.")
            else:
                ensure_external_id(models, uid, pwd, db, existing_id, False)
            return
        print(f"   ⚠️  Falta implied hacia read-only. Se añadiría [(4, {readonly_id})]")
        if not args.apply:
            print("\n🔍 DRY-RUN: ejecutar con --apply para actualizar implied_ids.")
            return
        models.execute_kw(
            db,
            uid,
            pwd,
            "res.groups",
            "write",
            [[existing_id], {"implied_ids": [(4, readonly_id)]}],
        )
        print("   ✅ implied_ids actualizado.")
        ensure_external_id(models, uid, pwd, db, existing_id, False)
        return

    vals = {
        "name": GROUP_NAME,
        "implied_ids": [(4, readonly_id)],
    }
    if cat_id:
        vals["category_id"] = cat_id

    print(f"\n📝 Alta nueva: res.groups con vals={vals!r}")
    if not args.apply:
        print("\n🔍 DRY-RUN: no se creó ningún registro. Ejecuta con --apply para crear el grupo.")
        return

    new_id = models.execute_kw(db, uid, pwd, "res.groups", "create", [vals])
    print(f"✅ Creado res.groups id={new_id}")
    ensure_external_id(models, uid, pwd, db, new_id, False)
    print("\n✅ Listo. Asigná este grupo a los usuarios desde Configuración → Usuarios (o masivamente).")
    print("   Tras asignar grupos, los usuarios deben cerrar sesión y volver a entrar.")


if __name__ == "__main__":
    main()
