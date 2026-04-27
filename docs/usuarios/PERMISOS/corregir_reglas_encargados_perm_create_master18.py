#!/usr/bin/env python3
"""
Script para corregir las reglas de registro (ir.rule) de Encargados de sucursal.
Establece perm_read, perm_write, perm_create, perm_unlink = True en las reglas
de stock.picking, stock.move, stock.quant, stock.picking.type para los grupos
"Encargados Belgrano 1/2/3/4".

Problema: Al facturar una venta, Odoo crea/escribe stock.picking (entrega).
Si la regla no tiene perm_create/perm_write=True, el encargado no puede crear
ese registro y aparece "no tiene acceso crear a Trasladar (stock.picking)".

Uso: python3 corregir_reglas_encargados_perm_create_master18.py [--dry-run] [--master-dev]
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

# Nombres de reglas que creamos para encargados (patrón)
PREFIJO_REGLA = "Encargados "
MODELOS = ['stock.picking', 'stock.move', 'stock.quant', 'stock.picking.type']

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
    parser = argparse.ArgumentParser(description='Corregir perm_create/perm_write en reglas de Encargados')
    parser.add_argument('--dry-run', action='store_true', help='Solo mostrar qué se actualizaría')
    parser.add_argument('--master-dev', action='store_true', help='Usar base productiva master_dev (dev.nakel.net.ar)')
    parser.add_argument('--force', action='store_true', help='Actualizar todas las reglas aunque ya tengan perm_create/perm_write True (por caché o API)')
    args = parser.parse_args()

    ODOO_CONFIG = _get_odoo_config(use_master_dev=args.master_dev)

    models, uid = conectar_odoo()
    if not models or not uid:
        sys.exit(1)

    db = ODOO_CONFIG['db']
    password = ODOO_CONFIG['pass']

    print("="*80)
    print("🔧 CORRECCIÓN: Reglas de Encargados - perm_create / perm_write")
    print("="*80)
    print(f"📊 Base de datos: {ODOO_CONFIG['db']}")
    print("Objetivo: Permitir a encargados CREAR/ESCRIBIR stock.picking al facturar ventas")
    print("="*80)

    # Buscar reglas cuyo nombre empiece por "Encargados " y modelo sea uno de los nuestros
    model_ids = models.execute_kw(
        db, uid, password,
        'ir.model', 'search',
        [[('model', 'in', MODELOS)]]
    )
    if not model_ids:
        print("❌ No se encontraron modelos")
        sys.exit(1)

    reglas = models.execute_kw(
        db, uid, password,
        'ir.rule', 'search_read',
        [[
            ('name', 'ilike', 'Encargados Belgrano'),
            ('model_id', 'in', model_ids)
        ]],
        {'fields': ['id', 'name', 'model_id', 'perm_read', 'perm_write', 'perm_create', 'perm_unlink', 'active']}
    )

    if not reglas:
        print("⚠️  No se encontraron reglas de 'Encargados Belgrano'. ¿Ya ejecutaste configurar_permisos_inventario_por_sucursal_master18.py?")
        sys.exit(0)

    print(f"\n📋 Reglas encontradas: {len(reglas)}")
    necesitan_actualizacion = []
    for r in reglas:
        if args.force or not r.get('perm_create', True) or not r.get('perm_write', True):
            necesitan_actualizacion.append(r)
            if not args.force:
                print(f"   • {r['name']} (model_id={r.get('model_id', [None])[0]})")
                print(f"     perm_create={r.get('perm_create')}, perm_write={r.get('perm_write')} → se pondrán en True")
    if args.force and necesitan_actualizacion:
        print(f"   [--force] Se actualizarán las {len(necesitan_actualizacion)} reglas para asegurar perm_create/perm_write=True")

    if not necesitan_actualizacion:
        print("\n✅ Todas las reglas ya tienen perm_create y perm_write en True.")
        return

    ids_actualizar = [r['id'] for r in necesitan_actualizacion]
    valores = {
        'perm_read': True,
        'perm_write': True,
        'perm_create': True,
        'perm_unlink': True,
    }

    if args.dry_run:
        print("\n[DRY-RUN] Se actualizarían las reglas con:", valores)
        print("Ejecuta sin --dry-run para aplicar.")
        return

    models.execute_kw(
        db, uid, password,
        'ir.rule', 'write',
        [ids_actualizar, valores]
    )
    print(f"\n✅ Actualizadas {len(ids_actualizar)} reglas: perm_read, perm_write, perm_create, perm_unlink = True")
    print("\n⚠️  Los encargados deben CERRAR SESIÓN y volver a INICIAR SESIÓN para que surta efecto.")
    print("="*80)

if __name__ == "__main__":
    main()
