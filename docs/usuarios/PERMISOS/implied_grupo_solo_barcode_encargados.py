#!/usr/bin/env python3
"""
Tras instalar el módulo ``nakel_product_encargado_barcode`` en Odoo, enlaza el grupo
``Nakel: Producto solo código de barras`` como *implied* de los grupos
``Encargados Belgrano 1`` … ``Encargados Belgrano 4``.

Así todos los encargados heredan la restricción de escritura (solo campo ``barcode``)
sin asignar el grupo a mano en cada usuario.

Uso:
  python3 implied_grupo_solo_barcode_encargados.py [--master-dev] [--dry-run]

Autor: FWCORP / asistente
Fecha: 2026-04-05
"""

import argparse
import sys
import xmlrpc.client

sys.path.insert(0, '/media/klap/raid5/cursor_files')

try:
    from config_nakel import ODOO_CONFIG_MASTER18, ODOO_CONFIG_MASTER_DEV
except ImportError:
    print('❌ No se pudo importar config_nakel.py')
    sys.exit(1)


def _cfg(master_dev: bool):
    c = ODOO_CONFIG_MASTER_DEV if master_dev else ODOO_CONFIG_MASTER18
    return {'url': c['url'], 'db': c['db'], 'user': c['username'], 'pass': c['password']}


SUCURSALES = ['Belgrano 1', 'Belgrano 2', 'Belgrano 3', 'Belgrano 4']
XML_MODULE = 'nakel_product_encargado_barcode'
XML_NAME = 'group_nakel_producto_solo_barcode'


def _res_id_grupo_nakel(models, db, uid, password):
    rows = models.execute_kw(
        db,
        uid,
        password,
        'ir.model.data',
        'search_read',
        [[('module', '=', XML_MODULE), ('name', '=', XML_NAME)]],
        {'fields': ['res_id'], 'limit': 1},
    )
    if not rows:
        return None
    return rows[0]['res_id']


def main():
    ap = argparse.ArgumentParser(description='Implied: grupo solo barcode → Encargados B1–B4')
    ap.add_argument('--master-dev', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    cfg = _cfg(args.master_dev)
    common = xmlrpc.client.ServerProxy(f'{cfg["url"]}/xmlrpc/2/common')
    uid = common.authenticate(cfg['db'], cfg['user'], cfg['pass'], {})
    if not uid:
        print('❌ Autenticación fallida')
        sys.exit(1)
    m = xmlrpc.client.ServerProxy(f'{cfg["url"]}/xmlrpc/2/object')
    db = cfg['db']
    p = cfg['pass']

    nakel_gid = _res_id_grupo_nakel(m, db, uid, p)
    if not nakel_gid:
        print(
            f'❌ No está el XML-ID {XML_MODULE}.{XML_NAME}. '
            'Instale y actualice el módulo nakel_product_encargado_barcode primero.'
        )
        sys.exit(1)
    print(f'✅ Grupo Nakel solo barcode: res.groups id={nakel_gid}')

    for suc in SUCURSALES:
        gname = f'Encargados {suc}'
        gr = m.execute_kw(db, uid, p, 'res.groups', 'search_read', [[('name', '=', gname)]], {'fields': ['id', 'name', 'implied_ids']})
        if not gr:
            print(f'⚠️  No existe grupo {gname!r}, se omite.')
            continue
        gid = gr[0]['id']
        implied = list(gr[0].get('implied_ids') or [])
        if nakel_gid in implied:
            print(f'   {gname} (id={gid}): ya tenía implied ✅')
            continue
        if args.dry_run:
            print(f'   [DRY-RUN] {gname} (id={gid}): añadiría implied {nakel_gid}')
            continue
        implied.append(nakel_gid)
        m.execute_kw(db, uid, p, 'res.groups', 'write', [[gid], {'implied_ids': [(6, 0, implied)]}])
        print(f'   {gname} (id={gid}): implied actualizado ✅')

    if not args.dry_run:
        print('\n⚠️  Cerrar sesión y volver a entrar en Odoo para recargar grupos.')
    print('Listo.')


if __name__ == '__main__':
    main()
