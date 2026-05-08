#!/usr/bin/env python3
"""
Asigna el grupo Contabilidad / solo lectura (Accounting / Read-only) a usuarios cajeros
en master_18 para que puedan descargar el PDF de Venta diaria (acceso a account.payment).

Sin este grupo, Odoo muestra: "No puede acceder a los registros 'Pagos' (account.payment)".

Uso:
  python3 asignar_permisos_account_readonly_cajeros_master18.py           # dry-run
  python3 asignar_permisos_account_readonly_cajeros_master18.py --apply # aplicar

Requisitos: config_nakel.ODOO_CONFIG_MASTER18
"""

import sys
import argparse

sys.path.insert(0, '/media/klap/raid5/cursor_files')

try:
    from config_nakel import ODOO_CONFIG_MASTER18, ODOO_CONFIG_MASTER_DEV
except ImportError:
    print("❌ Error: No se pudo importar config_nakel (ODOO_CONFIG_MASTER18/ODOO_CONFIG_MASTER_DEV)")
    sys.exit(1)

import xmlrpc.client

ODOO_CONFIG = {
    'url': ODOO_CONFIG_MASTER18['url'],
    'db': ODOO_CONFIG_MASTER18['db'],
    'user': ODOO_CONFIG_MASTER18['username'],
    'pass': ODOO_CONFIG_MASTER18['password'],
}


def conectar_odoo():
    """Conecta a Odoo master_18."""
    try:
        common = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/common')
        uid = common.authenticate(ODOO_CONFIG['db'], ODOO_CONFIG['user'], ODOO_CONFIG['pass'], {})
        if not uid:
            print(f"❌ Error de autenticación para {ODOO_CONFIG['db']}")
            return None, None
        models = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/object')
        print(f"✅ Conexión exitosa a Odoo {ODOO_CONFIG['db']}")
        return models, uid
    except Exception as e:
        print(f"❌ Error conectando: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def get_group_accounting_readonly(models, uid, password):
    """
    Busca el grupo Contabilidad / solo lectura (Accounting / Read-only).
    Usa solo res.groups con category_id.name por si res.groups.category no existe.
    """
    for cat_name in ['Accounting', 'Contabilidad']:
        for name_search in ['Read-only', 'solo lectura', 'solo lecutra']:
            groups = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'res.groups', 'search_read',
                [[('category_id.name', 'ilike', cat_name), ('name', 'ilike', name_search)]],
                {'fields': ['id', 'name', 'category_id'], 'limit': 1}
            )
            if groups:
                return groups[0]
    return None


def get_pos_user_group_id(models, uid, password):
    """Obtiene el ID del grupo Point of Sale / User (solo res.groups)."""
    for cat_name in ['Point of Sale', 'Punto de venta']:
        gr = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'res.groups', 'search_read',
            [[('category_id.name', 'ilike', cat_name), ('name', 'ilike', 'User')]],
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
        description='Asignar Contabilidad/solo lectura a cajeros para descargar PDF (account.payment) en master_18/master_dev'
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

    print(f"\n🔐 Permisos account.payment para cajeros ({amb})")
    print("   Objetivo: poder descargar PDF Venta diaria / cierre de caja\n")

    # Grupo Accounting / Read-only
    gr_readonly = get_group_accounting_readonly(models, uid, password)
    if not gr_readonly:
        print("❌ No se encontró el grupo Contabilidad / solo lectura (Accounting / Read-only)")
        sys.exit(1)
    readonly_gid = gr_readonly['id']
    print(f"✅ Grupo a asignar: {gr_readonly.get('name')} (ID: {readonly_gid})")

    # Grupo Point of Sale / User
    pos_user_gid = get_pos_user_group_id(models, uid, password)
    if not pos_user_gid:
        print("❌ No se encontró el grupo Point of Sale / User")
        sys.exit(1)
    print(f"✅ Grupo cajero (POS User) ID: {pos_user_gid}\n")

    cajeros = get_cajeros(models, uid, password, pos_user_gid)
    if not cajeros:
        print("ℹ️ No hay usuarios con Point of Sale / User en esta base.")
        return

    print(f"📋 Cajeros (POS User) encontrados: {len(cajeros)}\n")

    to_update = []
    for u in cajeros:
        gids = u.get('groups_id', [])
        if readonly_gid in gids:
            print(f"   ✅ {u['login']} ({u['name']}) — ya tiene Contabilidad/solo lectura")
        else:
            print(f"   ⚠️ {u['login']} ({u['name']}) — sin Contabilidad/solo lectura")
            to_update.append(u)

    if not to_update:
        print("\n✅ Todos los cajeros ya tienen el grupo necesario. Nada que hacer.")
        return

    if not apply:
        print(f"\n🔍 DRY-RUN: Se asignaría Contabilidad/solo lectura a {len(to_update)} usuario(s).")
        print("   Ejecuta con --apply para aplicar los cambios.")
        return

    print(f"\n📝 Aplicando grupo a {len(to_update)} usuario(s)...")
    for u in to_update:
        gids = list(u.get('groups_id', []))
        gids.append(readonly_gid)
        try:
            models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'res.users', 'write',
                [[u['id']], {'groups_id': [(6, 0, gids)]}]
            )
            print(f"   ✅ {u['login']} — asignado Contabilidad/solo lectura")
        except Exception as e:
            print(f"   ❌ {u['login']} — error: {e}")

    print("\n✅ Hecho. Los cajeros deben cerrar sesión y volver a iniciar para que surta efecto.")


if __name__ == '__main__':
    main()
