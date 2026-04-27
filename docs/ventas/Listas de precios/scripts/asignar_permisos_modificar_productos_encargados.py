#!/usr/bin/env python3
"""
Script para asignar permisos de modificación de productos a encargados de sucursales
- Asigna el grupo "Product Creation" que permite modificar productos (incluyendo códigos de barras)
- Usuarios objetivo:
  * Manuel Claudia Isabel - Belgrano 1 (C1, C2)
  * Varas Adrian Marcelo - Belgrano 2 (C1, C2)
  * Robles Angel Jose - Belgrano 3 (C1, C2)
  * Ramos Nancy - Belgrano 4 (C1)
Autor: Corolla
Fecha: 2025-12-27
"""

import sys
import os
import xmlrpc.client
from datetime import datetime

# Agregar ruta del proyecto
sys.path.insert(0, '/media/klap/raid5/cursor_files')

try:
    from config_nakel import ODOO_CONFIG_MASTER_DEV
except ImportError:
    print("❌ Error: No se pudo importar config_nakel.py")
    sys.exit(1)

# Configuración Odoo - MASTER_DEV
ODOO_CONFIG = {
    'url': ODOO_CONFIG_MASTER_DEV['url'],
    'db': ODOO_CONFIG_MASTER_DEV['db'],
    'user': ODOO_CONFIG_MASTER_DEV['username'],
    'pass': ODOO_CONFIG_MASTER_DEV['password']
}

# IDs de usuarios encargados (obtenidos del análisis previo)
USUARIOS_ENCARGADOS = {
    'Manuel Claudia Isabel': {
        'id': 96,
        'login': 'golosinasbelgrano1@nakel.ar',
        'sucursal': 'Belgrano 1',
        'cajas': ['C1', 'C2']
    },
    'Varas Adrian Marcelo': {
        'id': 102,
        'login': 'golosinasbelgrano2@nakel.ar',
        'sucursal': 'Belgrano 2',
        'cajas': ['C1', 'C2']
    },
    'Robles Angel Jose': {
        'id': 100,
        'login': 'golosinasbelgrano3@nakel.ar',
        'sucursal': 'Belgrano 3',
        'cajas': ['C1', 'C2']
    },
    'Ramos Nancy': {
        'id': 99,
        'login': 'golosinasbelgrano4@nakel.ar',
        'sucursal': 'Belgrano 4',
        'cajas': ['C1']
    }
}

# ID del grupo "Product Creation" (Extra Rights)
GRUPO_PRODUCT_CREATION_ID = 20

def conectar_odoo():
    """Conecta a Odoo master_dev"""
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
        print(f"❌ Error conectando a Odoo: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def verificar_grupo_product_creation(models, uid, password):
    """Verifica que el grupo Product Creation existe"""
    try:
        grupo = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'res.groups', 'read',
            [[GRUPO_PRODUCT_CREATION_ID]],
            {'fields': ['id', 'name', 'category_id', 'comment']}
        )
        
        if grupo:
            grupo_info = grupo[0]
            print(f"✅ Grupo encontrado: {grupo_info['name']}")
            print(f"   Categoría: {grupo_info.get('category_id', [None, ''])[1] if grupo_info.get('category_id') else 'N/A'}")
            if grupo_info.get('comment'):
                print(f"   Descripción: {grupo_info['comment']}")
            return True
        else:
            print(f"❌ Grupo Product Creation (ID: {GRUPO_PRODUCT_CREATION_ID}) no encontrado")
            return False
            
    except Exception as e:
        print(f"❌ Error verificando grupo: {e}")
        return False

def verificar_permisos_grupo(models, uid, password):
    """Verifica los permisos que otorga el grupo Product Creation"""
    try:
        print("\n🔍 Verificando permisos del grupo Product Creation...")
        
        # Buscar reglas de acceso para product.template
        ir_model = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.model', 'search_read',
            [[('model', '=', 'product.template')]],
            {'fields': ['id', 'name', 'model']}
        )
        
        if not ir_model:
            print("❌ Modelo product.template no encontrado")
            return False
        
        # Buscar reglas de acceso para el grupo Product Creation
        access_rules = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.model.access', 'search_read',
            [[('model_id', '=', ir_model[0]['id']), ('group_id', '=', GRUPO_PRODUCT_CREATION_ID)]],
            {'fields': ['id', 'name', 'group_id', 'perm_read', 'perm_write', 'perm_create', 'perm_unlink']}
        )
        
        if access_rules:
            rule = access_rules[0]
            print(f"✅ Permisos encontrados para product.template:")
            print(f"   Read: {rule.get('perm_read', False)}")
            print(f"   Write: {rule.get('perm_write', False)} ✅ (permite modificar códigos de barras)")
            print(f"   Create: {rule.get('perm_create', False)}")
            print(f"   Unlink: {rule.get('perm_unlink', False)}")
            return True
        else:
            print("⚠️  No se encontraron reglas de acceso específicas para este grupo")
            print("   (Puede heredar permisos de otros grupos)")
            return True
            
    except Exception as e:
        print(f"❌ Error verificando permisos: {e}")
        import traceback
        traceback.print_exc()
        return False

def obtener_usuarios_actuales(models, uid, password):
    """Obtiene información actual de los usuarios encargados"""
    usuarios_info = {}
    
    for nombre, datos in USUARIOS_ENCARGADOS.items():
        try:
            usuario = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'res.users', 'read',
                [[datos['id']]],
                {'fields': ['id', 'name', 'login', 'active', 'groups_id']}
            )
            
            if usuario:
                usuarios_info[nombre] = usuario[0]
            else:
                print(f"⚠️  Usuario {nombre} (ID: {datos['id']}) no encontrado")
                
        except Exception as e:
            print(f"❌ Error obteniendo usuario {nombre}: {e}")
    
    return usuarios_info

def verificar_grupos_usuarios(models, uid, password, usuarios_info):
    """Verifica qué grupos tienen actualmente los usuarios"""
    print("\n📋 Verificando grupos actuales de los usuarios...")
    
    for nombre, usuario in usuarios_info.items():
        grupos_ids = usuario.get('groups_id', [])
        
        tiene_product_creation = GRUPO_PRODUCT_CREATION_ID in grupos_ids
        
        print(f"\n  👤 {usuario['name']} ({usuario.get('login', 'N/A')})")
        print(f"     Sucursal: {USUARIOS_ENCARGADOS[nombre]['sucursal']}")
        print(f"     Cajas: {', '.join(USUARIOS_ENCARGADOS[nombre]['cajas'])}")
        print(f"     Total grupos: {len(grupos_ids)}")
        print(f"     ✅ Tiene 'Product Creation': {tiene_product_creation}")
        
        if not tiene_product_creation:
            print(f"     ⚠️  NECESITA asignar grupo Product Creation")

def asignar_grupo_product_creation(models, uid, password, usuarios_info, dry_run=True):
    """Asigna el grupo Product Creation a los usuarios que no lo tienen"""
    print(f"\n{'🧪 MODO DRY-RUN' if dry_run else '⚠️  MODO REAL'}: Asignando grupo Product Creation...")
    
    usuarios_actualizados = 0
    usuarios_ya_tienen = 0
    errores = 0
    
    for nombre, usuario in usuarios_info.items():
        grupos_ids = usuario.get('groups_id', [])
        usuario_id = usuario['id']
        
        if GRUPO_PRODUCT_CREATION_ID in grupos_ids:
            usuarios_ya_tienen += 1
            print(f"   ✓ {usuario['name']}: Ya tiene el grupo Product Creation")
        else:
            grupos_nuevos = list(grupos_ids)
            grupos_nuevos.append(GRUPO_PRODUCT_CREATION_ID)
            
            if dry_run:
                print(f"   [DRY-RUN] Asignaría grupo Product Creation a {usuario['name']}")
                usuarios_actualizados += 1
            else:
                try:
                    models.execute_kw(
                        ODOO_CONFIG['db'], uid, password,
                        'res.users', 'write',
                        [[usuario_id], {'groups_id': [(6, 0, grupos_nuevos)]}]
                    )
                    print(f"   ✅ Grupo asignado a {usuario['name']}")
                    usuarios_actualizados += 1
                except Exception as e:
                    print(f"   ❌ Error asignando grupo a {usuario['name']}: {e}")
                    errores += 1
    
    print(f"\n📊 RESUMEN:")
    print(f"   ✅ Usuarios actualizados: {usuarios_actualizados}")
    print(f"   ✓  Usuarios que ya tenían el grupo: {usuarios_ya_tienen}")
    print(f"   ❌ Errores: {errores}")
    
    return usuarios_actualizados, usuarios_ya_tienen, errores

def verificar_permisos_finales(models, uid, password, usuarios_info):
    """Verifica que los usuarios ahora tienen los permisos correctos"""
    print("\n🔍 Verificando permisos finales...")
    
    for nombre, usuario in usuarios_info.items():
        try:
            # Re-leer el usuario para obtener grupos actualizados
            usuario_actualizado = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'res.users', 'read',
                [[usuario['id']]],
                {'fields': ['id', 'name', 'groups_id']}
            )
            
            if usuario_actualizado:
                grupos_ids = usuario_actualizado[0].get('groups_id', [])
                tiene_product_creation = GRUPO_PRODUCT_CREATION_ID in grupos_ids
                
                print(f"\n  👤 {usuario['name']}:")
                print(f"     ✅ Tiene Product Creation: {tiene_product_creation}")
                
                if tiene_product_creation:
                    print(f"     ✅ Puede modificar productos (incluyendo códigos de barras)")
                else:
                    print(f"     ❌ NO puede modificar productos")
                    
        except Exception as e:
            print(f"   ❌ Error verificando {usuario['name']}: {e}")

def main():
    """Función principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Asignar permisos de modificación de productos a encargados')
    parser.add_argument('--dry-run', action='store_true', help='Modo dry-run (no realiza cambios)')
    parser.add_argument('--verificar-solo', action='store_true', help='Solo verificar, no asignar')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("🔐 ASIGNACIÓN DE PERMISOS PARA MODIFICAR PRODUCTOS")
    print("=" * 80)
    print(f"📊 Base de datos: {ODOO_CONFIG['db']}")
    print(f"👥 Usuarios objetivo: {len(USUARIOS_ENCARGADOS)} encargados de sucursales")
    print(f"🔍 Modo: {'DRY-RUN' if args.dry_run else 'REAL'}")
    if args.verificar_solo:
        print(f"⚠️  Solo verificación (no se asignarán grupos)")
    print("=" * 80)
    
    # Conectar a Odoo
    models, uid = conectar_odoo()
    if not models or not uid:
        print("\n❌ No se pudo conectar a Odoo")
        return
    
    password = ODOO_CONFIG['pass']
    
    # Verificar grupo Product Creation
    if not verificar_grupo_product_creation(models, uid, password):
        print("\n❌ No se puede continuar sin el grupo Product Creation")
        return
    
    # Verificar permisos del grupo
    verificar_permisos_grupo(models, uid, password)
    
    # Obtener información de usuarios
    print("\n📋 Obteniendo información de usuarios...")
    usuarios_info = obtener_usuarios_actuales(models, uid, password)
    
    if not usuarios_info:
        print("\n❌ No se encontraron usuarios")
        return
    
    print(f"✅ {len(usuarios_info)} usuarios encontrados")
    
    # Verificar grupos actuales
    verificar_grupos_usuarios(models, uid, password, usuarios_info)
    
    # Asignar grupo si no es solo verificación
    if not args.verificar_solo:
        asignar_grupo_product_creation(models, uid, password, usuarios_info, dry_run=args.dry_run)
        
        # Verificar permisos finales
        if not args.dry_run:
            verificar_permisos_finales(models, uid, password, usuarios_info)
    
    print("\n" + "=" * 80)
    print("✅ PROCESO COMPLETADO")
    print("=" * 80)
    
    if args.dry_run and not args.verificar_solo:
        print("\n💡 Ejecuta sin --dry-run para aplicar los cambios")
    elif args.verificar_solo:
        print("\n💡 Ejecuta sin --verificar-solo para asignar los grupos")

if __name__ == "__main__":
    main()

