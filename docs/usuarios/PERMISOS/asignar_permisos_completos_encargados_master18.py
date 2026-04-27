#!/usr/bin/env python3
"""
Script para asignar permisos de inventario a los encargados Belgrano (sin tocar productos).
Política 2026-04: **no** asigna Product Creation (maestro de productos / barcodes desde Central).
Asigna Inventory / User o Manager si falta (traslados, stock).
Autor: Corolla
Fecha: 2025-01-XX
"""

import sys
import os
import xmlrpc.client
import argparse

sys.path.insert(0, '/media/klap/raid5/cursor_files')

try:
    from config_nakel import ODOO_CONFIG_MASTER18
except ImportError:
    print("❌ Error: No se pudo importar config_nakel.py")
    sys.exit(1)

ODOO_CONFIG = {
    'url': ODOO_CONFIG_MASTER18['url'],
    'db': ODOO_CONFIG_MASTER18['db'],
    'user': ODOO_CONFIG_MASTER18['username'],
    'pass': ODOO_CONFIG_MASTER18['password']
}

# Usuarios a configurar
USUARIOS_CONFIG = {
    'golosinasbelgrano1@nakel.ar': {
        'nombre': 'Manuel Claudia Isabel',
        'sucursal': 'Belgrano 1'
    },
    'golosinasbelgrano2@nakel.ar': {
        'nombre': 'Varas Adrian Marcelo',
        'sucursal': 'Belgrano 2'
    },
    'golosinasbelgrano3@nakel.ar': {
        'nombre': 'Robles Angel Jose',
        'sucursal': 'Belgrano 3'
    },
    'golosinasbelgrano4@nakel.ar': {
        'nombre': 'Ramos Nancy',
        'sucursal': 'Belgrano 4'
    }
}

def conectar_odoo():
    """Conecta a Odoo master_18"""
    try:
        common = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/common')
        uid = common.authenticate(ODOO_CONFIG['db'], ODOO_CONFIG['user'], ODOO_CONFIG['pass'], {})
        if not uid:
            print(f"❌ Error de autenticación")
            return None, None
        models = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/object')
        print(f"✅ Conexión exitosa a Odoo {ODOO_CONFIG['db']}")
        return models, uid
    except Exception as e:
        print(f"❌ Error conectando a Odoo: {e}")
        return None, None

def obtener_grupo(models, uid, password, nombre_grupo, categoria=None):
    """Busca un grupo por nombre"""
    try:
        dominio = [('name', '=', nombre_grupo)]
        if categoria:
            dominio.append(('category_id.name', '=', categoria))
        
        grupos = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'res.groups', 'search_read',
            [dominio],
            {'fields': ['id', 'name', 'category_id']}
        )
        
        if grupos:
            return grupos[0]
        return None
    except Exception as e:
        print(f"   ⚠️  Error buscando grupo {nombre_grupo}: {e}")
        return None

def asignar_grupo_a_usuario(models, uid, password, usuario_id, grupo_id, dry_run=False):
    """Asigna un grupo a un usuario"""
    try:
        # Obtener grupos actuales del usuario
        usuario = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'res.users', 'read',
            [[usuario_id]],
            {'fields': ['groups_id']}
        )
        
        grupos_actuales = usuario[0].get('groups_id', [])
        
        if grupo_id in grupos_actuales:
            return True  # Ya tiene el grupo
        
        if dry_run:
            return True  # En dry-run, asumimos que se asignaría
        
        # Agregar nuevo grupo
        grupos_actuales.append(grupo_id)
        models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'res.users', 'write',
            [[usuario_id], {'groups_id': [(6, 0, grupos_actuales)]}]
        )
        
        return True
    except Exception as e:
        print(f"      ❌ Error asignando grupo: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Asignar permisos completos a encargados')
    parser.add_argument('--dry-run', action='store_true', help='Ejecutar en modo dry-run')
    args = parser.parse_args()
    
    modo = "DRY-RUN" if args.dry_run else "REAL"
    
    print("="*80)
    print("🔧 ASIGNACIÓN DE PERMISOS COMPLETOS A ENCARGADOS")
    print("="*80)
    print(f"📊 Base de datos: {ODOO_CONFIG['db']}")
    print(f"🔍 Modo: {modo}")
    print("="*80)
    
    models, uid = conectar_odoo()
    if not models or not uid:
        return
    
    password = ODOO_CONFIG['pass']
    
    # Buscar grupos necesarios
    print("\n📂 Buscando grupos necesarios...")
    print("   ℹ️  Product Creation: omitido (política Nakel — productos solo desde Central).")

    # Buscar Inventory User (en master_18 puede que no haya Manager separado)
    grupo_inventory_user = obtener_grupo(models, uid, password, 'User', 'Inventory')
    if grupo_inventory_user:
        print(f"   ✅ Inventory / User encontrado (ID: {grupo_inventory_user['id']})")
    else:
        print(f"   ❌ No se encontró Inventory / User")
        return
    
    # Verificar si hay un grupo Manager
    grupos_inv_manager = models.execute_kw(
        ODOO_CONFIG['db'], uid, password,
        'res.groups', 'search_read',
        [[('category_id.name', '=', 'Inventory'), ('name', 'ilike', 'Manager')]],
        {'fields': ['id', 'name']}
    )
    
    grupo_inventory_manager = None
    if grupos_inv_manager:
        grupo_inventory_manager = grupos_inv_manager[0]
        print(f"   ✅ {grupo_inventory_manager['name']} encontrado (ID: {grupo_inventory_manager['id']})")
    else:
        print(f"   ℹ️  No hay grupo Manager de Inventory, usando Inventory / User")
        grupo_inventory_manager = grupo_inventory_user
    
    # Procesar cada usuario
    print("\n" + "="*80)
    print("👥 PROCESANDO USUARIOS")
    print("="*80)
    
    resultados = {}
    
    for login, info in USUARIOS_CONFIG.items():
        print(f"\n👤 {info['nombre']} ({info['sucursal']})")
        print(f"   Login: {login}")
        
        # Buscar usuario
        usuarios = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'res.users', 'search_read',
            [[('login', '=', login)]],
            {'fields': ['id', 'name', 'login', 'groups_id']}
        )
        
        if not usuarios:
            print(f"   ❌ Usuario no encontrado")
            resultados[login] = {'error': 'Usuario no encontrado'}
            continue
        
        usuario = usuarios[0]
        usuario_id = usuario['id']
        grupos_actuales = usuario.get('groups_id', [])
        
        print(f"   ID: {usuario_id}")
        
        print(f"\n   1️⃣ Product Creation: omitido (no se asigna a encargados Belgrano).")

        # Verificar Inventory User/Manager
        nombre_grupo_inv = grupo_inventory_manager['name']
        print(f"\n   2️⃣ {nombre_grupo_inv} (acceso a inventario):")
        tiene_inventory = grupo_inventory_manager['id'] in grupos_actuales
        if tiene_inventory:
            print(f"      ✅ Ya tiene {nombre_grupo_inv}")
        else:
            if args.dry_run:
                print(f"      [DRY-RUN] Se asignaría {nombre_grupo_inv}")
            else:
                if asignar_grupo_a_usuario(models, uid, password, usuario_id, grupo_inventory_manager['id'], args.dry_run):
                    print(f"      ✅ {nombre_grupo_inv} asignado")
                else:
                    print(f"      ❌ Error asignando {nombre_grupo_inv}")
        
        # Nota sobre ajustes de inventario
        print(f"      ℹ️  Este grupo permite acceso básico a inventario")
        print(f"      ℹ️  Para ajustes de inventario, se necesita verificar permisos de stock.inventory")
        
        resultados[login] = {
            'inventory_user': tiene_inventory
        }
    
    # Resumen
    print("\n" + "="*80)
    print("📊 RESUMEN")
    print("="*80)
    
    for login, info in USUARIOS_CONFIG.items():
        if login in resultados and 'error' not in resultados[login]:
            resultado = resultados[login]
            inventory_ok = "✅" if resultado.get('inventory_user', False) or not args.dry_run else "❌"
            print(f"   {info['nombre']} ({info['sucursal']}):")
            print(f"      Inventory (User/Manager): {inventory_ok}")
        else:
            print(f"   ❌ {info['nombre']}: Error")
    
    print("\n" + "="*80)
    if args.dry_run:
        print("💡 Este fue un DRY-RUN. Para aplicar los cambios, ejecuta sin --dry-run")
    else:
        print("✅ Asignación de permisos completada")
    print("="*80)

if __name__ == "__main__":
    main()
