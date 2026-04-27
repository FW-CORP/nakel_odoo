#!/usr/bin/env python3
"""
Añade ir.model.access explícitos para los grupos Encargados Belgrano 1/2/3/4
en stock.picking, stock.move, stock.quant, stock.picking.type (CRUD completo).

Cuando el encargado solo tiene la regla de registro pero el permiso de creación
viene de otro grupo (Inventory/User), en algunos flujos Odoo puede denegar el
create. Dar permiso explícito al grupo Encargados asegura que el grupo tenga
perm_create; la regla (ir.rule) sigue filtrando qué registros puede ver/crear.

Uso: python3 asignar_ir_model_access_encargados_master18.py [--master-dev] [--dry-run]
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
# Inventario + Ventas + Reabastecimiento + Chatter (mensajes en documentos)
MODELOS = [
    'stock.picking', 'stock.move', 'stock.quant', 'stock.picking.type',
    'sale.order', 'sale.order.line',
    'stock.warehouse.orderpoint',  # Reglas de reabastecimiento
    'mail.message',   # Mensajes/chatter en documentos (evitar "Error de acceso" al crear Message)
    'mail.activity',  # Actividades en chatter
]

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
    parser = argparse.ArgumentParser(description='Añadir ir.model.access para grupos Encargados')
    parser.add_argument('--master-dev', action='store_true', help='Usar base master_dev')
    parser.add_argument('--dry-run', action='store_true', help='Solo mostrar qué se crearía')
    args = parser.parse_args()

    ODOO_CONFIG = _get_odoo_config(use_master_dev=args.master_dev)
    db = ODOO_CONFIG['db']
    password = ODOO_CONFIG['pass']

    models, uid = conectar_odoo()
    if not models or not uid:
        sys.exit(1)

    print("="*80)
    print("🔧 ASIGNAR ir.model.access A GRUPOS ENCARGADOS")
    print("="*80)
    print(f"📊 Base de datos: {db}")
    print(f"   Modelos: {', '.join(MODELOS)}")
    print(f"   Grupos: Encargados Belgrano 1/2/3/4")
    if args.dry_run:
        print("   Modo: DRY-RUN (no se crean registros)")
    print("="*80)

    # Obtener model_ids
    model_ids = {}
    for model_name in MODELOS:
        mids = models.execute_kw(db, uid, password, 'ir.model', 'search', [[('model', '=', model_name)]])
        if not mids:
            print(f"❌ Modelo {model_name} no encontrado")
            sys.exit(1)
        model_ids[model_name] = mids[0]
    print(f"\n✅ Modelos resueltos: {list(model_ids.keys())}")

    creados = 0
    ya_existentes = 0

    for sucursal in SUCURSALES:
        nombre_grupo = f"Encargados {sucursal}"
        gr = models.execute_kw(
            db, uid, password,
            'res.groups', 'search_read',
            [[('name', '=', nombre_grupo)]],
            {'fields': ['id', 'name']}
        )
        if not gr:
            print(f"\n⚠️  Grupo '{nombre_grupo}' no encontrado, se omite.")
            continue
        grupo_id = gr[0]['id']
        print(f"\n📂 Grupo: {nombre_grupo} (ID: {grupo_id})")

        for model_name in MODELOS:
            model_id = model_ids[model_name]
            name_safe = f"access_{model_name.replace('.', '_')}_encargados_{sucursal.replace(' ', '_').lower()}"
            # Buscar si ya existe acceso para este grupo + modelo
            existentes = models.execute_kw(
                db, uid, password,
                'ir.model.access', 'search',
                [[('model_id', '=', model_id), ('group_id', '=', grupo_id)]]
            )
            if existentes:
                if not args.dry_run:
                    # Actualizar a CRUD completo por si acaso
                    models.execute_kw(
                        db, uid, password,
                        'ir.model.access', 'write',
                        [existentes, {
                            'perm_read': True,
                            'perm_write': True,
                            'perm_create': True,
                            'perm_unlink': True,
                        }]
                    )
                print(f"   • {model_name}: ya existe acceso, actualizado a CRUD ✅")
                ya_existentes += 1
                continue
            if args.dry_run:
                print(f"   • {model_name}: [DRY-RUN] se crearía acceso CRUD")
                creados += 1
                continue
            try:
                models.execute_kw(
                    db, uid, password,
                    'ir.model.access', 'create',
                    [{
                        'name': name_safe,
                        'model_id': model_id,
                        'group_id': grupo_id,
                        'perm_read': True,
                        'perm_write': True,
                        'perm_create': True,
                        'perm_unlink': True,
                    }]
                )
                print(f"   • {model_name}: acceso CRUD creado ✅")
                creados += 1
            except Exception as e:
                print(f"   • {model_name}: ❌ Error: {e}")

    print("\n" + "="*80)
    print(f"📊 Accesos nuevos: {creados} | Ya existentes/actualizados: {ya_existentes}")
    print("="*80)
    if not args.dry_run and (creados > 0 or ya_existentes > 0):
        print("\n⚠️  Los encargados deben CERRAR SESIÓN y volver a INICIAR SESIÓN en Odoo.")
    print("="*80)

if __name__ == "__main__":
    main()
