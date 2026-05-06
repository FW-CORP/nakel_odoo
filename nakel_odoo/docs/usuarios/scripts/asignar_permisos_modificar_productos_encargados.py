#!/usr/bin/env python3
"""
Alineación de permisos de producto — miembros de «Encargados Belgrano 1–4» (master_dev).

Política:
  - **Ámbito:** todos los usuarios **activos** que pertenezcan a **alguno** de los grupos
    ``Encargados Belgrano 1`` … ``Encargados Belgrano 4`` (categoría Inventory).
  - **Exclusión:** ``supervision@nakel.ar`` (supervisora; no se alteran sus grupos desde este script).
  - **Acción:** quitar ``Product Creation``; asegurar ``Inventory / User`` si falta.

Los IDs de ``res.groups`` se resuelven por **nombre** (no hardcode), por si cambian entre bases.

Base: ``ODOO_CONFIG_MASTER_DEV`` (p. ej. ``master_dev`` en ``nakel.net.ar``).

Uso:
  python3 asignar_permisos_modificar_productos_encargados.py --verificar-solo
  python3 asignar_permisos_modificar_productos_encargados.py --dry-run
  python3 asignar_permisos_modificar_productos_encargados.py

Autor: Corolla / FWCORP
Fecha: 2025-12-27 (alcance dinámico + exclusión supervisora: 2026-04-18)
"""

import sys
import xmlrpc.client

sys.path.insert(0, '/media/klap/raid5/cursor_files')

try:
    from config_nakel import ODOO_CONFIG_MASTER_DEV
except ImportError:
    print('❌ Error: No se pudo importar config_nakel.py')
    sys.exit(1)

ODOO_CONFIG = {
    'url': ODOO_CONFIG_MASTER_DEV['url'],
    'db': ODOO_CONFIG_MASTER_DEV['db'],
    'user': ODOO_CONFIG_MASTER_DEV['username'],
    'pass': ODOO_CONFIG_MASTER_DEV['password'],
}

# No modificar grupos de estos logins (política supervisión / otros perfiles).
EXCLUDE_LOGINS_NORMALIZED = frozenset({'supervision@nakel.ar'})

NOMBRES_GRUPOS_ENCARGADOS = [
    'Encargados Belgrano 1',
    'Encargados Belgrano 2',
    'Encargados Belgrano 3',
    'Encargados Belgrano 4',
]


def _norm_login(login):
    return (login or '').strip().lower()


def conectar_odoo():
    try:
        common = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/common')
        uid = common.authenticate(
            ODOO_CONFIG['db'], ODOO_CONFIG['user'], ODOO_CONFIG['pass'], {}
        )
        if not uid:
            print(f'❌ Error de autenticación para {ODOO_CONFIG["db"]}')
            return None, None
        models = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/object')
        print(f'✅ Conexión exitosa a Odoo {ODOO_CONFIG["db"]}')
        return models, uid
    except Exception as e:
        print(f'❌ Error conectando a Odoo: {e}')
        import traceback
        traceback.print_exc()
        return None, None


def resolver_grupo_product_creation(models, uid, password):
    rows = models.execute_kw(
        ODOO_CONFIG['db'], uid, password,
        'res.groups', 'search_read',
        [[('name', '=', 'Product Creation')]],
        {'fields': ['id', 'name'], 'limit': 1},
    )
    return rows[0] if rows else None


def resolver_grupo_inventory_user(models, uid, password):
    rows = models.execute_kw(
        ODOO_CONFIG['db'], uid, password,
        'res.groups', 'search_read',
        [[('name', '=', 'User'), ('category_id.name', '=', 'Inventory')]],
        {'fields': ['id', 'name'], 'limit': 1},
    )
    return rows[0] if rows else None


def obtener_ids_grupos_encargados(models, uid, password):
    """IDs de res.groups Encargados Belgrano 1–4."""
    ids = []
    for nombre in NOMBRES_GRUPOS_ENCARGADOS:
        r = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'res.groups', 'search_read',
            [[('name', '=', nombre)]],
            {'fields': ['id', 'name'], 'limit': 1},
        )
        if r:
            ids.append(r[0]['id'])
        else:
            print(f'⚠️  No existe el grupo {nombre!r}')
    return ids


def obtener_usuarios_encargados_belgrano(models, uid, password, gids_encargados):
    """
    Usuarios activos en al menos un grupo Encargados Belgrano N,
    excluyendo EXCLUDE_LOGINS_NORMALIZED.
    Devuelve dict login -> registro usuario, y dict uid -> lista nombres de grupos Encargados.
    """
    if not gids_encargados:
        return {}, {}

    all_uids = set()
    for gid in gids_encargados:
        uids = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'res.users', 'search',
            [[('active', '=', True), ('groups_id', 'in', [gid])]],
        )
        all_uids.update(uids)

    if not all_uids:
        return {}, {}

    users = models.execute_kw(
        ODOO_CONFIG['db'], uid, password,
        'res.users', 'read',
        [list(all_uids)],
        {'fields': ['id', 'name', 'login', 'active', 'groups_id']},
    )

    gnames = models.execute_kw(
        ODOO_CONFIG['db'], uid, password,
        'res.groups', 'read',
        [gids_encargados],
        {'fields': ['id', 'name']},
    )
    gid_to_name = {g['id']: g['name'] for g in gnames}

    usuarios_info = {}
    enc_por_uid = {}

    for u in users:
        login = u.get('login') or ''
        if _norm_login(login) in EXCLUDE_LOGINS_NORMALIZED:
            continue
        enc_de_u = []
        for g in u.get('groups_id') or []:
            if g in gid_to_name:
                enc_de_u.append(gid_to_name[g])
        enc_por_uid[u['id']] = sorted(enc_de_u)
        usuarios_info[login or f"id_{u['id']}"] = u

    return usuarios_info, enc_por_uid


def verificar_grupos_necesarios(models, uid, password, inv_row):
    if not inv_row:
        print('❌ No se encontró Inventory / User (User + categoría Inventory)')
        return False
    print(f"✅ Grupo Inventory / User: id={inv_row['id']} ({inv_row['name']})")
    return True


def verificar_grupos_usuarios(models, uid, password, usuarios_info, enc_por_uid, pc_id, inv_id):
    print('\n📋 Verificando grupos actuales de los usuarios...')
    for key, usuario in sorted(usuarios_info.items(), key=lambda x: (x[1].get('login') or '')):
        uid_u = usuario['id']
        grupos_ids = usuario.get('groups_id', [])
        tiene_pc = pc_id in grupos_ids if pc_id else False
        tiene_inv = inv_id in grupos_ids if inv_id else False
        enc_s = ', '.join(enc_por_uid.get(uid_u, []))

        print(f"\n  👤 {usuario['name']} ({usuario.get('login', 'N/A')})")
        print(f"     Encargados Belgrano: {enc_s}")
        print(f"     Total grupos: {len(grupos_ids)}")
        print(f"     Tiene 'Product Creation' (debe ser False): {tiene_pc}")
        print(f"     Tiene 'Inventory / User': {tiene_inv}")

        acciones = []
        if tiene_pc:
            acciones.append('QUITAR Product Creation')
        if not tiene_inv:
            acciones.append('asignar Inventory / User')
        if acciones:
            print(f"     ⚠️  Acción sugerida: {', '.join(acciones)}")


def asignar_grupos_necesarios(
    models, uid, password, usuarios_info, pc_id, inv_id, dry_run=True
):
    print(
        f"\n{'🧪 MODO DRY-RUN' if dry_run else '⚠️  MODO REAL'}: "
        'Alineando grupos (sin Product Creation)...'
    )

    usuarios_actualizados = 0
    usuarios_sin_cambios = 0
    quitados_pc = 0
    agregados_inv = 0
    errores = 0

    for _key, usuario in sorted(usuarios_info.items(), key=lambda x: (x[1].get('login') or '')):
        grupos_ids = list(usuario.get('groups_id', []))
        usuario_id = usuario['id']
        grupos_nuevos = list(grupos_ids)
        cambios = []

        if pc_id and pc_id in grupos_nuevos:
            grupos_nuevos = [g for g in grupos_nuevos if g != pc_id]
            cambios.append('quitar Product Creation')
            quitados_pc += 1

        if inv_id and inv_id not in grupos_nuevos:
            grupos_nuevos.append(inv_id)
            cambios.append('añadir Inventory / User')
            agregados_inv += 1

        if not cambios:
            usuarios_sin_cambios += 1
            print(f"   ✓ {usuario['name']}: ya alineado (sin PC, con Inventory / User)")
            continue

        if dry_run:
            print(f"   [DRY-RUN] {usuario['name']}: {', '.join(cambios)}")
            usuarios_actualizados += 1
        else:
            try:
                models.execute_kw(
                    ODOO_CONFIG['db'], uid, password,
                    'res.users', 'write',
                    [[usuario_id], {'groups_id': [(6, 0, grupos_nuevos)]}],
                )
                print(f"   ✅ {usuario['name']}: {', '.join(cambios)}")
                usuarios_actualizados += 1
            except Exception as e:
                print(f"   ❌ Error en {usuario['name']}: {e}")
                errores += 1

    print('\n📊 RESUMEN:')
    print(f'   ✅ Usuarios con cambios aplicables: {usuarios_actualizados}')
    print(f'   ✓  Usuarios ya alineados: {usuarios_sin_cambios}')
    print(f'   📋 Quitarían / quitaron Product Creation: {quitados_pc} usuario(s)')
    print(
        f'   📋 Añadirían / añadieron Inventory / User: {agregados_inv} vez(ces) '
        '(por usuario que lo necesitaba)'
    )
    print(f'   ❌ Errores: {errores}')

    return usuarios_actualizados, usuarios_sin_cambios, errores


def verificar_permisos_finales(models, uid, password, usuarios_info, pc_id, inv_id):
    print('\n🔍 Verificando permisos finales...')
    for _k, usuario in sorted(usuarios_info.items(), key=lambda x: (x[1].get('login') or '')):
        try:
            actualizado = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'res.users', 'read',
                [[usuario['id']]],
                {'fields': ['id', 'name', 'groups_id']},
            )
            if not actualizado:
                continue
            grupos_ids = actualizado[0].get('groups_id', [])
            tiene_pc = pc_id in grupos_ids if pc_id else False
            tiene_inv = inv_id in grupos_ids if inv_id else False

            print(f"\n  👤 {usuario['name']}:")
            print(f"     Product Creation (debe ser False): {tiene_pc}")
            print(f"     Inventory / User: {tiene_inv}")
            if tiene_pc:
                print(
                    '     ⚠️  Aún tiene Product Creation — revisar o volver a ejecutar sin dry-run.'
                )
            else:
                print('     ✅ Sin Product Creation (maestro producto desde Central).')
            if tiene_inv:
                print('     ✅ Traslados / inventario operativo vía Inventory / User')
            else:
                print('     ❌ Falta Inventory / User')
        except Exception as e:
            print(f"   ❌ Error verificando {usuario['name']}: {e}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Quitar Product Creation a miembros Encargados Belgrano (excepto supervisora); '
        'asegurar Inventory / User'
    )
    parser.add_argument('--dry-run', action='store_true', help='Modo dry-run (no escribe)')
    parser.add_argument('--verificar-solo', action='store_true', help='Solo verificar')

    args = parser.parse_args()

    excl = ', '.join(sorted(EXCLUDE_LOGINS_NORMALIZED))

    print('=' * 80)
    print('🔐 ALINEACIÓN: Encargados Belgrano (todos los miembros del grupo, master_dev)')
    print('=' * 80)
    print(f"📊 Base: {ODOO_CONFIG['db']}")
    print(f"📌 Excluidos (no se modifican): {excl}")
    if args.verificar_solo:
        print('🔍 Modo: solo verificación (sin escrituras)')
    else:
        print(f"🔍 Modo: {'DRY-RUN' if args.dry_run else 'REAL'}")
    print('=' * 80)

    models, uid = conectar_odoo()
    if not models or not uid:
        print('\n❌ No se pudo conectar a Odoo')
        return

    password = ODOO_CONFIG['pass']

    pc_row = resolver_grupo_product_creation(models, uid, password)
    inv_row = resolver_grupo_inventory_user(models, uid, password)
    pc_id = pc_row['id'] if pc_row else None
    inv_id = inv_row['id'] if inv_row else None

    if pc_row:
        print(f"✅ Product Creation: id={pc_id}")
    else:
        print('⚠️  No se encontró Product Creation en la base')

    if not verificar_grupos_necesarios(models, uid, password, inv_row):
        print('\n❌ Falta Inventory / User')
        return

    gids_enc = obtener_ids_grupos_encargados(models, uid, password)
    usuarios_info, enc_por_uid = obtener_usuarios_encargados_belgrano(
        models, uid, password, gids_enc
    )

    print('\n📋 Obteniendo usuarios en Encargados Belgrano 1–4 (menos exclusión)...')
    if not usuarios_info:
        print('❌ No hay usuarios sujetos a la política (o no existen grupos Encargados).')
        return

    print(f"✅ {len(usuarios_info)} usuario(s) en alcance")

    verificar_grupos_usuarios(models, uid, password, usuarios_info, enc_por_uid, pc_id, inv_id)

    if not args.verificar_solo:
        asignar_grupos_necesarios(
            models, uid, password, usuarios_info, pc_id, inv_id, dry_run=args.dry_run
        )
        if not args.dry_run:
            verificar_permisos_finales(models, uid, password, usuarios_info, pc_id, inv_id)

    print('\n' + '=' * 80)
    print('✅ PROCESO COMPLETADO')
    print('=' * 80)

    if args.dry_run and not args.verificar_solo:
        print('\n💡 Ejecuta sin --dry-run para aplicar')
    elif args.verificar_solo:
        print(
            '\n💡 Ejecuta sin --verificar-solo para aplicar la alineación '
            '(quitar PC, añadir Inventory si falta)'
        )


if __name__ == '__main__':
    main()
