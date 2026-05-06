#!/usr/bin/env python3
"""
Asigna el grupo de Contabilidad/Facturación (Accounting / Invoicing)
a usuarios cajeros (Point of Sale / User) en master_18.

Motivo:
- Al retirar dinero de caja / hacer cierre/reconciliación, Odoo intenta
  crear un 'Asiento contable' en account.move.
- El error típico indica que la creación está permitida para:
  - Contabilidad/Facturación (Accounting / Invoicing)
  - (y a veces) Compra/Usuario

Este script agrega solo el grupo de Contabilidad/Facturación faltante.
Por seguridad, por defecto corre en modo dry-run; con --apply aplica.

Uso:
  cd /media/klap/raid5/cursor_files/nakel/usuarios/PERMISOS
  python3 asignar_permisos_account_invoicing_cajeros_master18.py
  python3 asignar_permisos_account_invoicing_cajeros_master18.py --apply
"""

import sys
import argparse
import xmlrpc.client

sys.path.insert(0, '/media/klap/raid5/cursor_files')

try:
    from config_nakel import ODOO_CONFIG_MASTER18, ODOO_CONFIG_MASTER_DEV
except ImportError:
    print("❌ Error: No se pudo importar config_nakel (ODOO_CONFIG_MASTER18/ODOO_CONFIG_MASTER_DEV)")
    sys.exit(1)

ODOO_CONFIG = {
    'url': ODOO_CONFIG_MASTER18['url'],
    'db': ODOO_CONFIG_MASTER18['db'],
    'user': ODOO_CONFIG_MASTER18['username'],
    'pass': ODOO_CONFIG_MASTER18['password'],
}


def conectar_odoo():
    """Conecta a Odoo master_18 y retorna (models_proxy, uid)."""
    common = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/common')
    uid = common.authenticate(ODOO_CONFIG['db'], ODOO_CONFIG['user'], ODOO_CONFIG['pass'], {})
    if not uid:
        print(f"❌ Error de autenticación para {ODOO_CONFIG['db']}")
        return None, None
    models = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/object')
    print(f"✅ Conexión exitosa a Odoo {ODOO_CONFIG['db']}")
    return models, uid


def find_group_accounting_invoicing(models, uid, password):
    """
    Encuentra el grupo de Accounting / Invoicing o Contabilidad / Facturación.
    No usa res.groups.category (porque en tu Odoo no existe como modelo).
    """
    # Contabilidad/Facturación suele llamarse "Invoicing" en inglés.
    # Buscamos con ilike y filtramos por categoría Accounting/Contabilidad.
    name_filters = [
        'Invoicing',
        'Factur',
        'Facturación',
        'Contabilidad/Facturación',
    ]
    cat_filters = ['Accounting', 'Contabilidad']

    for cat_name in cat_filters:
        for name_f in name_filters:
            groups = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'res.groups', 'search_read',
                [[('category_id.name', 'ilike', cat_name), ('name', 'ilike', name_f)]],
                {'fields': ['id', 'name', 'category_id'], 'limit': 5}
            )
            if groups:
                # Elegimos el mejor match por preferencia de "Invoicing" y luego "Factur".
                def score(g):
                    n = (g.get('name') or '').lower()
                    s = 0
                    if 'invoicing' in n:
                        s += 10
                    if 'factur' in n:
                        s += 8
                    return s
                groups_sorted = sorted(groups, key=score, reverse=True)
                g0 = groups_sorted[0]
                return g0
    return None


def find_pos_user_group_id(models, uid, password):
    """Obtiene el ID del grupo Point of Sale / User (solo res.groups)."""
    pos_user_filters = [
        ('Point of Sale', 'User'),
        ('Punto de venta', 'User'),
    ]
    for cat_name, user_name in pos_user_filters:
        gr = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'res.groups', 'search_read',
            [[('category_id.name', 'ilike', cat_name), ('name', 'ilike', user_name)]],
            {'fields': ['id', 'name'], 'limit': 1}
        )
        if gr:
            return gr[0]['id']
    return None


def get_cajeros(models, uid, password, pos_user_gid):
    """Usuarios activos que tienen Point of Sale / User (cajeros)."""
    users = models.execute_kw(
        ODOO_CONFIG['db'], uid, password,
        'res.users', 'search_read',
        [[('active', '=', True), ('groups_id', 'in', [pos_user_gid])]],
        {'fields': ['id', 'name', 'login', 'groups_id']}
    )
    return users


def main():
    parser = argparse.ArgumentParser(
        description='Asignar Contabilidad/Facturación a cajeros para poder crear account.move (master_18/master_dev)'
    )
    parser.add_argument('--apply', action='store_true', help='Aplicar cambios (por defecto solo dry-run)')
    parser.add_argument('--master-dev', action='store_true', help='Usar base productiva master_dev (master_dev)')
    parser.add_argument('--master-dev-password', default=None, help='Override contraseña para master_dev (opcional)')
    args = parser.parse_args()
    apply = args.apply

    amb = 'master_dev' if args.master_dev else 'master_18'
    if args.master_dev:
        # Sobrescribimos la config para que el resto del script use master_dev.
        ODOO_CONFIG['url'] = ODOO_CONFIG_MASTER_DEV['url']
        ODOO_CONFIG['db'] = ODOO_CONFIG_MASTER_DEV['db']
        ODOO_CONFIG['user'] = ODOO_CONFIG_MASTER_DEV['username']
        if args.master_dev_password:
            ODOO_CONFIG['pass'] = args.master_dev_password
        else:
            ODOO_CONFIG['pass'] = ODOO_CONFIG_MASTER_DEV.get('password') or ODOO_CONFIG_MASTER_DEV.get('master_password')

    models, uid = conectar_odoo()
    if not models:
        sys.exit(1)
    password = ODOO_CONFIG['pass']

    print(f"\n🔐 Permisos account.move para cajeros ({amb})")
    print("   Fix: agregar Contabilidad/Facturación a usuarios con POS User\n")

    group_invoicing = find_group_accounting_invoicing(models, uid, password)
    if not group_invoicing:
        print("❌ No se encontró el grupo Contabilidad/Facturación (Accounting / Invoicing).")
        sys.exit(1)
    invoicing_gid = group_invoicing['id']
    print(f"✅ Grupo a asignar: {group_invoicing.get('name')} (ID: {invoicing_gid})")

    pos_user_gid = find_pos_user_group_id(models, uid, password)
    if not pos_user_gid:
        print("❌ No se encontró el grupo Point of Sale / User.")
        sys.exit(1)
    print(f"✅ Grupo cajero (POS User) ID: {pos_user_gid}\n")

    cajeros = get_cajeros(models, uid, password, pos_user_gid)
    print(f"📋 Cajeros (POS User) encontrados: {len(cajeros)}\n")

    to_update = []
    for u in cajeros:
        gids = u.get('groups_id', []) or []
        if invoicing_gid in gids:
            print(f"   ✅ {u['login']} ({u['name']}) — ya tiene Contabilidad/Facturación")
        else:
            print(f"   ⚠️ {u['login']} ({u['name']}) — sin Contabilidad/Facturación")
            to_update.append(u)

    if not to_update:
        print("\n✅ Todos los cajeros ya tienen el grupo Contabilidad/Facturación. Nada que hacer.")
        return

    if not apply:
        print(f"\n🔍 DRY-RUN: Se asignaría Contabilidad/Facturación a {len(to_update)} usuario(s).")
        print("   Ejecuta con --apply para aplicar los cambios.")
        return

    print(f"\n📝 Aplicando grupo a {len(to_update)} usuario(s)...")
    for u in to_update:
        gids = list(u.get('groups_id', []) or [])
        if invoicing_gid not in gids:
            gids.append(invoicing_gid)
        try:
            models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'res.users', 'write',
                [[u['id']], {'groups_id': [(6, 0, gids)]}]
            )
            print(f"   ✅ {u['login']} — asignado Contabilidad/Facturación")
        except Exception as e:
            print(f"   ❌ {u['login']} — error: {e}")

    print("\n✅ Hecho. Los usuarios deben cerrar sesión y volver a iniciar para que surta efecto.")


if __name__ == '__main__':
    main()

