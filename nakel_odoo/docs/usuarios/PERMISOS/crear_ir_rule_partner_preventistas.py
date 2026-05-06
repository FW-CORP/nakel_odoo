#!/usr/bin/env python3
"""
Crea o actualiza **dos ir.rule** sobre **res.partner** aplicadas **solo** al grupo
**Vendedores - Preventistas** (`nakel_perm_scripts.group_vendedores_preventistas`).

Odoo combina las reglas del **mismo modelo y mismos grupos** con **OR**: un contacto
visible si cumple la regla de “solo asignados” **o** la de “proveedores”.

Dominio (OR): el contacto es “del vendedor” si el comercial (`user_id`) coincide
con el usuario, o el padre / entidad comercial tiene ese comercial asignado.
Así se cubren direcciones hijas y contactos bajo la misma razón social.

Sin **--apply** solo muestra el plan (dry-run implícito).

Uso:
  python3 crear_ir_rule_partner_preventistas.py --master-dev
  python3 crear_ir_rule_partner_preventistas.py --master-dev --apply
  python3 crear_ir_rule_partner_preventistas.py --master-18 --apply
"""

from __future__ import annotations

import argparse
import sys
import xmlrpc.client

sys.path.insert(0, "/media/klap/raid5/cursor_files")

try:
    from config_nakel import ODOO_CONFIG_MASTER18, ODOO_CONFIG_MASTER_DEV
except ImportError:
    print("❌ No se pudo importar config_nakel")
    sys.exit(1)

EXT_MODULE = "nakel_perm_scripts"
EXT_GROUP = "group_vendedores_preventistas"
EXT_RULE = "rule_res_partner_preventistas_solo_asignados"
EXT_RULE_PROV = "rule_res_partner_preventistas_proveedores_catalogo"

RULE_NAME = "Nakel: Preventistas — solo contactos del vendedor asignado"
RULE_NAME_PROV = "Nakel: Preventistas — proveedores (lectura stock/compras)"

# OR en prefijo (Odoo): N términos → N-1 veces '|' al inicio.
# - partner_share=False: admin/empleados (create_uid/write_uid leen res.partner id 3, etc.).
# - user_id / parent / commercial / user_ids / mi partner: clientes “asignados” clásicos.
# - sale_order_ids / commercial_partner_id.sale_order_ids: pedidos donde el usuario es
#   comercial (`sale.order.user_id`) aunque el contacto no tenga `user_id` alineado; cubre
#   confirmación de pedido al leer facturación/envío u otras ramas del partner.
# - id in company partner ids: al confirmar venta+stock Odoo lee `stock.warehouse.partner_id`
#   (contacto de la compañía, p. ej. «Nakel SA» id=1) sin ser «cliente asignado» al vendedor.
DOMAIN_FORCE = (
    "['|', '|', '|', '|', '|', '|', '|', '|', "
    "('partner_share', '=', False), "
    "('user_id', '=', user.id), "
    "('parent_id.user_id', '=', user.id), "
    "('commercial_partner_id.user_id', '=', user.id), "
    "('user_ids', 'any', [('id', '=', user.id)]), "
    "('id', '=', user.partner_id.id), "
    "('sale_order_ids', 'any', [('user_id', '=', user.id)]), "
    "('commercial_partner_id.sale_order_ids', 'any', [('user_id', '=', user.id)]), "
    "('id', 'in', user.company_ids.mapped('partner_id').ids)]"
)

# Segunda regla (mismo grupo): OR con la anterior. Cubre `res.partner` de proveedores
# (`product.supplierinfo`) que Odoo lee al confirmar venta+stock / abastecimiento.
#
# - Rama A: `supplier_rank > 0` (proveedor “marcado” en ficha).
# - Rama B: cualquier partner que figure como `partner_id` en `product.supplierinfo`,
#   aunque `supplier_rank` sea 0 (datos aún no normalizados). Evita AccessError al
#   confirmar cotizaciones. El `search` va en `sudo()` para no depender de otros ACL.
#   Evaluación vía `safe_eval` en `ir.rule` (Odoo 18 lo acepta).
# En ambas ramas se mantiene el filtro de compañía.
DOMAIN_PROVEEDORES = (
    "['|', "
    "'&', ('supplier_rank', '>', 0), '|', "
    "('company_id', '=', False), ('company_id', 'in', company_ids), "
    "'&', ('id', 'in', user.env['product.supplierinfo'].sudo().search([]).mapped('partner_id').ids), "
    "'|', ('company_id', '=', False), ('company_id', 'in', company_ids)]"
)


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
        return None, None
    return xmlrpc.client.ServerProxy(f"{cfg['url']}/xmlrpc/2/object"), uid


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
    return rows[0]["res_id"] if rows else None


def main() -> None:
    parser = argparse.ArgumentParser(description="ir.rule res.partner solo grupo Preventistas")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--master-dev", action="store_true")
    g.add_argument("--master-18", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Persistir regla")
    args = parser.parse_args()

    cfg = pick_config(args.master_dev)
    amb = "master_dev" if args.master_dev else "master_18"
    db, pwd = cfg["db"], cfg["pass"]

    print("=" * 72)
    print(f"ir.rule res.partner → grupo {EXT_MODULE}.{EXT_GROUP}")
    print(f"Base: {db} | Modo: {'APPLY' if args.apply else 'DRY-RUN'}")
    print("=" * 72)

    models, uid = connect(cfg)
    if not models:
        print("❌ Autenticación fallida")
        sys.exit(1)
    print("✅ Conexión OK\n")

    grupo_id = xmlid_res_id(models, uid, pwd, db, EXT_MODULE, EXT_GROUP)
    if not grupo_id:
        print(f"❌ No existe XML ID {EXT_MODULE}.{EXT_GROUP}. Ejecutá primero crear_grupo_vendedores_preventistas.py --apply")
        sys.exit(1)
    ginfo = models.execute_kw(
        db, uid, pwd, "res.groups", "read", [[grupo_id]], {"fields": ["name", "full_name"]}
    )[0]
    print(f"✅ Grupo: id={grupo_id} — {ginfo.get('full_name') or ginfo.get('name')}")

    mid = models.execute_kw(
        db, uid, pwd, "ir.model", "search", [[("model", "=", "res.partner")]], {"limit": 1}
    )
    if not mid:
        print("❌ No se encontró modelo res.partner")
        sys.exit(1)
    model_id = mid[0]
    print(f"✅ ir.model res.partner id={model_id}")

    rule_id = xmlid_res_id(models, uid, pwd, db, EXT_MODULE, EXT_RULE)
    vals = {
        "name": RULE_NAME,
        "model_id": model_id,
        "domain_force": DOMAIN_FORCE,
        "groups": [(6, 0, [grupo_id])],
        "perm_read": True,
        "perm_write": True,
        "perm_create": True,
        "perm_unlink": True,
        "active": True,
    }

    vals_prov = {
        "name": RULE_NAME_PROV,
        "model_id": model_id,
        "domain_force": DOMAIN_PROVEEDORES,
        "groups": [(6, 0, [grupo_id])],
        "perm_read": True,
        "perm_write": True,
        "perm_create": True,
        "perm_unlink": True,
        "active": True,
    }

    print(f"\nRegla 1 — {RULE_NAME}\n  {DOMAIN_FORCE}\n")
    print(f"Regla 2 — {RULE_NAME_PROV}\n  {DOMAIN_PROVEEDORES}\n")

    rule_prov_id = xmlid_res_id(models, uid, pwd, db, EXT_MODULE, EXT_RULE_PROV)

    if not args.apply:
        if rule_id:
            cur = models.execute_kw(
                db, uid, pwd, "ir.rule", "read", [[rule_id]], {"fields": ["domain_force"]}
            )[0]
            print(f"🔍 DRY-RUN regla 1: ir.rule id={rule_id}")
            print(f"   domain actual: {cur.get('domain_force')}")
        else:
            print(f"🔍 DRY-RUN: se crearía regla 1 + XML {EXT_MODULE}.{EXT_RULE}")
        if rule_prov_id:
            curp = models.execute_kw(
                db, uid, pwd, "ir.rule", "read", [[rule_prov_id]], {"fields": ["domain_force"]}
            )[0]
            print(f"🔍 DRY-RUN regla 2: ir.rule id={rule_prov_id}")
            print(f"   domain actual: {curp.get('domain_force')}")
        else:
            print(f"🔍 DRY-RUN: se crearía regla 2 + XML {EXT_MODULE}.{EXT_RULE_PROV}")
        print("\n🔍 Ejecutá con --apply para persistir.")
        return

    if rule_id:
        models.execute_kw(db, uid, pwd, "ir.rule", "write", [[rule_id], vals])
        print(f"✅ Regla 1 actualizada (ir.rule id={rule_id}).")
    else:
        new_id = models.execute_kw(db, uid, pwd, "ir.rule", "create", [vals])
        print(f"✅ Regla 1 creada ir.rule id={new_id}")
        models.execute_kw(
            db,
            uid,
            pwd,
            "ir.model.data",
            "create",
            [{"name": EXT_RULE, "module": EXT_MODULE, "model": "ir.rule", "res_id": new_id}],
        )
        print(f"✅ XML ID {EXT_MODULE}.{EXT_RULE}")

    if rule_prov_id:
        models.execute_kw(db, uid, pwd, "ir.rule", "write", [[rule_prov_id], vals_prov])
        print(f"✅ Regla 2 actualizada (ir.rule id={rule_prov_id}).")
    else:
        newp = models.execute_kw(db, uid, pwd, "ir.rule", "create", [vals_prov])
        print(f"✅ Regla 2 creada ir.rule id={newp}")
        models.execute_kw(
            db,
            uid,
            pwd,
            "ir.model.data",
            "create",
            [
                {
                    "name": EXT_RULE_PROV,
                    "module": EXT_MODULE,
                    "model": "ir.rule",
                    "res_id": newp,
                }
            ],
        )
        print(f"✅ XML ID {EXT_MODULE}.{EXT_RULE_PROV}")

    print("\n✅ Listo. Las dos reglas se combinan en OR para el grupo 102.")
    print("   Usuarios deben cerrar sesión y volver a entrar.")
    print(f"   Ambiente: {amb}")


if __name__ == "__main__":
    main()
