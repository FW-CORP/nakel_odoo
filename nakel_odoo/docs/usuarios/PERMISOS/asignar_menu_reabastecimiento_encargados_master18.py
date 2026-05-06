#!/usr/bin/env python3
"""
Asigna el menú Inventario → Operaciones → Reabastecimiento (Replenishment)
a los grupos Encargados Belgrano 1/2/3/4 para que los encargados de sucursal
puedan ver y usar la pantalla de reabastecimiento de su sucursal.

Los encargados ya tienen:
- ir.model.access sobre stock.warehouse.orderpoint (CRUD)
- Regla de registro que filtra por location_id de su sucursal

Sin este script, el menú puede estar restringido a otros grupos y no ser visible.

Uso: python3 asignar_menu_reabastecimiento_encargados_master18.py [--master-dev] [--dry-run]
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

SUCURSALES = ['Belgrano 1', 'Belgrano 2', 'Belgrano 3', 'Belgrano 4']

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
    parser = argparse.ArgumentParser(description='Asignar menú Reabastecimiento a grupos Encargados')
    parser.add_argument('--master-dev', action='store_true', help='Usar base master_dev')
    parser.add_argument('--dry-run', action='store_true', help='Solo mostrar qué se haría')
    args = parser.parse_args()

    ODOO_CONFIG = _get_odoo_config(use_master_dev=args.master_dev)
    db = ODOO_CONFIG['db']
    password = ODOO_CONFIG['pass']

    models, uid = conectar_odoo()
    if not models or not uid:
        sys.exit(1)

    print("=" * 80)
    print("🔧 ASIGNAR MENÚ REABASTECIMIENTO A ENCARGADOS")
    print("=" * 80)
    print(f"📊 Base de datos: {db}")
    if args.dry_run:
        print("   Modo: DRY-RUN (no se modifican menús)")
    print("=" * 80)

    # Buscar menú Reabastecimiento (nombre en EN o ES)
    menus = models.execute_kw(
        db, uid, password,
        'ir.ui.menu', 'search_read',
        [[
            '|',
            ('name', 'ilike', 'Replenishment'),
            ('name', 'ilike', 'Reabastecimiento')
        ]],
        {'fields': ['id', 'name', 'groups_id', 'action']}
    )

    # Si hay varios, preferir el que tiene acción de orderpoint o el primero bajo Operaciones
    menu_replen = None
    for m in menus:
        action = m.get('action') or ''
        if 'orderpoint' in str(action) or 'replenishment' in str(action).lower():
            menu_replen = m
            break
    if not menu_replen and menus:
        menu_replen = menus[0]

    if not menu_replen:
        print("❌ No se encontró el menú de Reabastecimiento (Replenishment).")
        print("   Comprueba en Configuración → Técnico → Interfaz de usuario → Menús.")
        sys.exit(1)

    print(f"\n📂 Menú encontrado: «{menu_replen['name']}» (ID: {menu_replen['id']})")

    # IDs de grupos Encargados Belgrano 1/2/3/4
    grupos_encargados = []
    for sucursal in SUCURSALES:
        gr = models.execute_kw(
            db, uid, password,
            'res.groups', 'search_read',
            [[('name', '=', f'Encargados {sucursal}')]],
            {'fields': ['id', 'name']}
        )
        if gr:
            grupos_encargados.append(gr[0]['id'])
            print(f"   • Encargados {sucursal} (ID: {gr[0]['id']})")
        else:
            print(f"   ⚠️  Grupo 'Encargados {sucursal}' no encontrado")

    if not grupos_encargados:
        print("\n❌ No se encontró ningún grupo Encargados. Ejecuta antes configurar_permisos_inventario_por_sucursal_master18.py")
        sys.exit(1)

    groups_id_actual = list(menu_replen.get('groups_id') or [])
    faltan = [g for g in grupos_encargados if g not in groups_id_actual]
    # Si el menú no tiene grupos (groups_id vacío), en Odoo lo ven todos los que ven el padre.
    # Para que también lo vean los encargados sin quitar a nadie, añadimos solo los 4 Encargados.
    # Si ya tiene grupos, añadimos los Encargados al conjunto existente.
    nuevos_groups = list(set(groups_id_actual) | set(grupos_encargados))

    if not faltan:
        print("\n✅ El menú ya incluye a todos los grupos Encargados. Nada que hacer.")
        print("=" * 80)
        return

    print(f"\n📝 Grupos que se añaden al menú: {len(faltan)}")
    if args.dry_run:
        print("   [DRY-RUN] No se modificó el menú.")
        print("=" * 80)
        return

    try:
        models.execute_kw(
            db, uid, password,
            'ir.ui.menu', 'write',
            [[menu_replen['id']], {'groups_id': [(6, 0, nuevos_groups)]}]
        )
        print("   ✅ Menú actualizado: los grupos Encargados Belgrano 1/2/3/4 pueden ver Reabastecimiento.")
    except Exception as e:
        print(f"   ❌ Error actualizando menú: {e}")
        sys.exit(1)

    print("\n" + "=" * 80)
    print("💡 Los encargados deben CERRAR SESIÓN y volver a INICIAR SESIÓN para ver el menú.")
    print("=" * 80)

if __name__ == "__main__":
    main()
