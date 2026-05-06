#!/usr/bin/env python3
"""
Script para corregir permisos de un encargado de sucursal (crear traslados stock.picking).
Asigna el grupo "Encargados [Sucursal]", Inventory/User y fija property_warehouse_id.
Política 2026-04: para logins encargados Belgrano conocidos, **retira** Product Creation
(maestro de productos y barcodes solo desde Central).
Uso: python3 corregir_permisos_encargado_master18.py [usuario_id] [--master-dev]
     python3 corregir_permisos_encargado_master18.py 96
     python3 corregir_permisos_encargado_master18.py --login golosinasbelgrano1@nakel.ar --master-dev
Autor: Corolla
Fecha: 2025-01-23
"""

import sys
import argparse
import xmlrpc.client

sys.path.insert(0, '/media/klap/raid5/cursor_files')

try:
    from config_nakel import ODOO_CONFIG_MASTER18, ODOO_CONFIG_MASTER_DEV
except ImportError:
    print("❌ Error: No se pudo importar config_nakel.py")
    sys.exit(1)

def _get_odoo_config(use_master_dev=False):
    cfg = ODOO_CONFIG_MASTER_DEV if use_master_dev else ODOO_CONFIG_MASTER18
    return {'url': cfg['url'], 'db': cfg['db'], 'user': cfg['username'], 'pass': cfg['password']}

ODOO_CONFIG = _get_odoo_config(False)

# Mapeo login -> sucursal (grupo "Encargados {sucursal}")
ENCARGADOS_SUCURSAL = {
    'golosinasbelgrano1@nakel.ar': 'Belgrano 1',
    'golosinasbelgrano2@nakel.ar': 'Belgrano 2',
    'golosinasbelgrano3@nakel.ar': 'Belgrano 3',
    'golosinasbelgrano4@nakel.ar': 'Belgrano 4',
}
# Código de almacén por sucursal (para property_warehouse_id)
SUCURSAL_WAREHOUSE_CODE = {
    'Belgrano 1': 'B1',
    'Belgrano 2': 'B2',
    'Belgrano 3': 'B3',
    'Belgrano 4': 'B4',
}

def conectar_odoo():
    try:
        common = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/common')
        uid = common.authenticate(ODOO_CONFIG['db'], ODOO_CONFIG['user'], ODOO_CONFIG['pass'], {})
        if not uid:
            print("❌ Error de autenticación")
            return None, None
        models = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/object')
        print(f"✅ Conexión exitosa a Odoo {ODOO_CONFIG['db']}")
        return models, uid
    except Exception as e:
        print(f"❌ Error conectando a Odoo: {e}")
        return None, None

def main():
    global ODOO_CONFIG
    parser = argparse.ArgumentParser(description='Corregir permisos de encargado (crear traslados)')
    parser.add_argument('usuario_id', nargs='?', type=int, help='ID del usuario (ej: 96)')
    parser.add_argument('--login', type=str, help='Login del usuario (ej: golosinasbelgrano1@nakel.ar)')
    parser.add_argument('--master-dev', action='store_true', help='Usar base productiva master_dev (dev.nakel.net.ar)')
    args = parser.parse_args()

    ODOO_CONFIG = _get_odoo_config(use_master_dev=args.master_dev)

    if not args.usuario_id and not args.login:
        print("❌ Indica usuario_id o --login")
        print("   Ejemplo: python3 corregir_permisos_encargado_master18.py 96")
        print("   Ejemplo: python3 corregir_permisos_encargado_master18.py --login golosinasbelgrano1@nakel.ar")
        sys.exit(1)

    models, uid = conectar_odoo()
    if not models or not uid:
        sys.exit(1)

    db = ODOO_CONFIG['db']
    password = ODOO_CONFIG['pass']

    # Resolver usuario
    if args.login:
        usuarios = models.execute_kw(
            db, uid, password,
            'res.users', 'search_read',
            [[('login', '=', args.login)]],
            {'fields': ['id', 'name', 'login', 'groups_id']}
        )
        if not usuarios:
            print(f"❌ Usuario con login {args.login} no encontrado")
            sys.exit(1)
        usuario = usuarios[0]
        usuario_id = usuario['id']
        sucursal_esperada = ENCARGADOS_SUCURSAL.get(args.login, None)
    else:
        usuario = models.execute_kw(
            db, uid, password,
            'res.users', 'read',
            [[args.usuario_id]],
            {'fields': ['id', 'name', 'login', 'groups_id']}
        )
        if not usuario:
            print(f"❌ Usuario ID {args.usuario_id} no encontrado")
            sys.exit(1)
        usuario = usuario[0]
        usuario_id = usuario['id']
        sucursal_esperada = ENCARGADOS_SUCURSAL.get(usuario.get('login', ''), None)

    print("="*80)
    print("🔧 CORRECCIÓN DE PERMISOS: Crear traslados (stock.picking)")
    print("="*80)
    print(f"   Base de datos: {ODOO_CONFIG['db']}")
    print(f"   Usuario: {usuario['name']} (ID: {usuario_id}, Login: {usuario.get('login', 'N/A')})")
    if sucursal_esperada:
        print(f"   Sucursal esperada: {sucursal_esperada} → Grupo 'Encargados {sucursal_esperada}'")
    print("="*80)

    grupos_actuales = list(usuario.get('groups_id', []))

    # 1) Grupo de sucursal
    nombre_grupo_sucursal = f"Encargados {sucursal_esperada}" if sucursal_esperada else None
    if nombre_grupo_sucursal:
        gr = models.execute_kw(
            db, uid, password,
            'res.groups', 'search_read',
            [[('name', '=', nombre_grupo_sucursal)]],
            {'fields': ['id', 'name']}
        )
        if not gr:
            print(f"\n❌ Grupo '{nombre_grupo_sucursal}' no encontrado.")
            print("   💡 Ejecuta primero: configurar_permisos_inventario_por_sucursal_master18.py [--master-dev]")
            sys.exit(1)
        grupo_sucursal_id = gr[0]['id']
        if grupo_sucursal_id not in grupos_actuales:
            grupos_actuales.append(grupo_sucursal_id)
            models.execute_kw(
                db, uid, password,
                'res.users', 'write',
                [[usuario_id], {'groups_id': [(6, 0, grupos_actuales)]}]
            )
            print(f"\n✅ Grupo '{nombre_grupo_sucursal}' asignado.")
        else:
            print(f"\n✅ Usuario ya tiene el grupo '{nombre_grupo_sucursal}'.")

        # Almacén por defecto (property_warehouse_id) según sucursal: ventas usarán B1/B2/B3/B4
        wh_code = SUCURSAL_WAREHOUSE_CODE.get(sucursal_esperada)
        if wh_code:
            wh = models.execute_kw(
                db, uid, password,
                'stock.warehouse', 'search_read',
                [[('code', '=', wh_code)]],
                {'fields': ['id', 'name', 'code']}
            )
            if wh:
                models.execute_kw(
                    db, uid, password,
                    'res.users', 'write',
                    [[usuario_id], {'property_warehouse_id': wh[0]['id']}]
                )
                print(f"✅ Almacén por defecto (property_warehouse_id) = {wh[0]['name']} (ID: {wh[0]['id']})")
    else:
        print("\n⚠️  No se pudo determinar sucursal por login; solo se verificará Inventory/User (no se retira Product Creation).")

    # Refrescar grupos actuales por si se asignó grupo sucursal
    usuario = models.execute_kw(
        db, uid, password,
        'res.users', 'read',
        [[usuario_id]],
        {'fields': ['groups_id']}
    )
    grupos_actuales = list(usuario[0].get('groups_id', []))

    # 2) Inventory / User
    inv_user = models.execute_kw(
        db, uid, password,
        'res.groups', 'search_read',
        [[('name', '=', 'User'), ('category_id.name', '=', 'Inventory')]],
        {'fields': ['id', 'name']}
    )
    if inv_user:
        gid = inv_user[0]['id']
        if gid not in grupos_actuales:
            grupos_actuales.append(gid)
            models.execute_kw(
                db, uid, password,
                'res.users', 'write',
                [[usuario_id], {'groups_id': [(6, 0, grupos_actuales)]}]
            )
            print(f"✅ Grupo 'Inventory / User' asignado.")
        else:
            print(f"✅ Usuario ya tiene 'Inventory / User'.")
    else:
        print("⚠️  No se encontró grupo 'Inventory / User'.")

    usuario = models.execute_kw(
        db, uid, password,
        'res.users', 'read',
        [[usuario_id]],
        {'fields': ['groups_id', 'login']}
    )
    grupos_actuales = list(usuario[0].get('groups_id', []))
    login_u = usuario[0].get('login') or ''

    # 3) Product Creation: no asignar. Para encargados Belgrano (login conocido), retirar si está.
    prod_cre = models.execute_kw(
        db, uid, password,
        'res.groups', 'search_read',
        [[('name', '=', 'Product Creation')]],
        {'fields': ['id', 'name']}
    )
    if prod_cre:
        gid_pc = prod_cre[0]['id']
        if login_u in ENCARGADOS_SUCURSAL and gid_pc in grupos_actuales:
            grupos_actuales = [g for g in grupos_actuales if g != gid_pc]
            models.execute_kw(
                db, uid, password,
                'res.users', 'write',
                [[usuario_id], {'groups_id': [(6, 0, grupos_actuales)]}]
            )
            print(f"✅ Grupo 'Product Creation' retirado (política: maestro de productos desde Central).")
        elif login_u in ENCARGADOS_SUCURSAL:
            print(f"✅ Sin 'Product Creation' (correcto para encargado Belgrano).")
        elif gid_pc in grupos_actuales:
            print(f"ℹ️  Usuario tiene 'Product Creation'; no se retira (login no es encargado Belgrano mapeado).")
        else:
            print(f"ℹ️  Sin 'Product Creation'.")
    else:
        print("⚠️  No se encontró grupo 'Product Creation' en la base (omisión).")

    print("\n" + "="*80)
    print("✅ CORRECCIÓN COMPLETADA")
    print("="*80)
    print("\n⚠️  IMPORTANTE: El usuario debe CERRAR SESIÓN y volver a INICIAR SESIÓN en Odoo.")
    print("   Luego debería poder crear traslados (pedir mercadería) sin error.")
    print("\n💡 Si persiste el error: python3 diagnosticar_permisos_crear_traslado_master18.py")
    print("="*80)

if __name__ == "__main__":
    main()
