#!/usr/bin/env python3
"""
Script para asignar permisos de ajustes de inventario a Fabiana Gimenez en master_18
- Asigna el grupo "Inventory / User" que permite crear y modificar ajustes de inventario
- Permite modificar cantidades de productos manualmente
Autor: Corolla
Fecha: 2025-12-29
"""

import sys
import os
import xmlrpc.client
from datetime import datetime

# Agregar ruta del proyecto
sys.path.insert(0, '/media/klap/raid5/cursor_files')

try:
    from config_nakel import ODOO_CONFIG_MASTER18
except ImportError:
    print("❌ Error: No se pudo importar config_nakel.py")
    sys.exit(1)

# Configuración Odoo - MASTER_18
ODOO_CONFIG = {
    'url': ODOO_CONFIG_MASTER18['url'],
    'db': ODOO_CONFIG_MASTER18['db'],
    'user': ODOO_CONFIG_MASTER18['username'],
    'pass': ODOO_CONFIG_MASTER18['password']
}

# Información del usuario
USUARIO_FABIANA = {
    'id': 92,
    'login': 'fabianagimenez@nakel.ar',
    'name': 'Gimenez Fabiana'
}

# IDs de grupos necesarios para ajustes de inventario
GRUPO_INVENTORY_USER_ID = 50  # Inventory / User
GRUPO_INVENTORY_ADMIN_ID = 51  # Inventory / Administrator (necesario para crear/modificar ajustes de inventario)

def conectar_odoo():
    """Conecta a Odoo master_18"""
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

def verificar_grupos_inventory(models, uid, password):
    """Verifica que los grupos de Inventory existen"""
    grupos_ok = True
    
    # Verificar Inventory / User
    try:
        grupo = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'res.groups', 'read',
            [[GRUPO_INVENTORY_USER_ID]],
            {'fields': ['id', 'name', 'category_id']}
        )
        
        if grupo:
            print(f"✅ Grupo encontrado: {grupo[0].get('name')} (ID: {GRUPO_INVENTORY_USER_ID})")
        else:
            print(f"❌ Grupo Inventory / User (ID: {GRUPO_INVENTORY_USER_ID}) no encontrado")
            grupos_ok = False
    except Exception as e:
        print(f"❌ Error verificando grupo User: {e}")
        grupos_ok = False
    
    # Verificar Inventory / Administrator
    try:
        grupo_admin = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'res.groups', 'read',
            [[GRUPO_INVENTORY_ADMIN_ID]],
            {'fields': ['id', 'name', 'category_id']}
        )
        
        if grupo_admin:
            print(f"✅ Grupo encontrado: {grupo_admin[0].get('name')} (ID: {GRUPO_INVENTORY_ADMIN_ID})")
        else:
            print(f"❌ Grupo Inventory / Administrator (ID: {GRUPO_INVENTORY_ADMIN_ID}) no encontrado")
            grupos_ok = False
    except Exception as e:
        print(f"❌ Error verificando grupo Administrator: {e}")
        grupos_ok = False
    
    return grupos_ok

def obtener_usuario_actual(models, uid, password):
    """Obtiene información actual del usuario"""
    try:
        usuario = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'res.users', 'read',
            [[USUARIO_FABIANA['id']]],
            {'fields': ['id', 'name', 'login', 'groups_id']}
        )
        
        if usuario:
            return usuario[0]
        else:
            print(f"❌ Usuario {USUARIO_FABIANA['name']} (ID: {USUARIO_FABIANA['id']}) no encontrado")
            return None
            
    except Exception as e:
        print(f"❌ Error obteniendo usuario: {e}")
        return None

def verificar_grupos_usuario(usuario_info):
    """Verifica qué grupos tiene el usuario"""
    grupos_ids = usuario_info.get('groups_id', [])
    tiene_inventory_user = GRUPO_INVENTORY_USER_ID in grupos_ids
    tiene_inventory_admin = GRUPO_INVENTORY_ADMIN_ID in grupos_ids
    
    print(f"\n📋 Estado actual de {usuario_info.get('name')}:")
    print(f"   Login: {usuario_info.get('login')}")
    print(f"   Total grupos: {len(grupos_ids)}")
    print(f"   ✅ Tiene Inventory / User: {tiene_inventory_user}")
    print(f"   ✅ Tiene Inventory / Administrator: {tiene_inventory_admin}")
    
    return tiene_inventory_user, tiene_inventory_admin

def asignar_grupos_inventory(models, uid, password, dry_run=True):
    """Asigna los grupos de Inventory necesarios al usuario"""
    usuario_actual = obtener_usuario_actual(models, uid, password)
    if not usuario_actual:
        return False
    
    tiene_user, tiene_admin = verificar_grupos_usuario(usuario_actual)
    
    grupos_actuales = usuario_actual.get('groups_id', [])
    grupos_nuevos = list(grupos_actuales)
    cambios_necesarios = False
    
    # Agregar Inventory / User si no lo tiene
    if not tiene_user:
        grupos_nuevos.append(GRUPO_INVENTORY_USER_ID)
        cambios_necesarios = True
        print(f"\n⚠️  Falta el grupo Inventory / User")
    
    # Agregar Inventory / Administrator si no lo tiene (necesario para ajustes)
    if not tiene_admin:
        grupos_nuevos.append(GRUPO_INVENTORY_ADMIN_ID)
        cambios_necesarios = True
        print(f"\n⚠️  Falta el grupo Inventory / Administrator (necesario para ajustes de inventario)")
    
    if not cambios_necesarios:
        print(f"\n✅ {usuario_actual.get('name')} ya tiene todos los grupos necesarios de Inventory")
        return True
    
    if dry_run:
        print(f"\n🔍 DRY-RUN: Se asignarían los grupos faltantes a {usuario_actual.get('name')}")
        print(f"   Grupos actuales: {len(grupos_actuales)}")
        print(f"   Grupos nuevos: {len(grupos_nuevos)}")
        if not tiene_user:
            print(f"   ➕ Se agregaría: Inventory / User (ID: {GRUPO_INVENTORY_USER_ID})")
        if not tiene_admin:
            print(f"   ➕ Se agregaría: Inventory / Administrator (ID: {GRUPO_INVENTORY_ADMIN_ID})")
        return True
    
    try:
        models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'res.users', 'write',
            [[USUARIO_FABIANA['id']], {'groups_id': [(6, 0, grupos_nuevos)]}]
        )
        print(f"\n✅ Grupos de Inventory asignados correctamente a {usuario_actual.get('name')}")
        if not tiene_user:
            print(f"   ➕ Agregado: Inventory / User")
        if not tiene_admin:
            print(f"   ➕ Agregado: Inventory / Administrator")
        return True
        
    except Exception as e:
        print(f"❌ Error asignando grupos: {e}")
        import traceback
        traceback.print_exc()
        return False

def verificar_permisos_finales(models, uid, password):
    """Verifica que el usuario ahora tiene los permisos correctos"""
    print("\n🔍 Verificando permisos finales...")
    
    usuario_actual = obtener_usuario_actual(models, uid, password)
    if not usuario_actual:
        return
    
    grupos_ids = usuario_actual.get('groups_id', [])
    tiene_inventory_user = GRUPO_INVENTORY_USER_ID in grupos_ids
    tiene_inventory_admin = GRUPO_INVENTORY_ADMIN_ID in grupos_ids
    
    print(f"\n  👤 {usuario_actual.get('name')}:")
    print(f"     ✅ Tiene Inventory / User: {tiene_inventory_user}")
    print(f"     ✅ Tiene Inventory / Administrator: {tiene_inventory_admin}")
    
    if tiene_inventory_admin:
        print(f"     ✅ Puede crear y modificar ajustes de inventario")
        print(f"     ✅ Puede modificar cantidades de productos manualmente")
        print(f"     ✅ Tiene permisos completos de inventario")
    elif tiene_inventory_user:
        print(f"     ⚠️  Tiene Inventory / User pero puede necesitar Inventory / Administrator")
        print(f"     ⚠️  Puede tener limitaciones para crear ajustes de inventario")
    else:
        print(f"     ❌ NO tiene permisos suficientes para ajustes de inventario")

def main():
    """Función principal"""
    import argparse
    parser = argparse.ArgumentParser(description='Asignar permisos de ajustes de inventario a Fabiana Gimenez')
    parser.add_argument('--dry-run', action='store_true', help='Modo dry-run (no realiza cambios)')
    parser.add_argument('--verificar-solo', action='store_true', help='Solo verificar, no hacer cambios')
    args = parser.parse_args()
    
    print("="*80)
    print("🔧 ASIGNACIÓN DE PERMISOS DE AJUSTES DE INVENTARIO")
    print("="*80)
    print(f"👤 Usuario: {USUARIO_FABIANA['name']} ({USUARIO_FABIANA['login']})")
    print(f"📊 Base de datos: {ODOO_CONFIG['db']}")
    print(f"🔍 Modo: {'DRY-RUN' if args.dry_run else ('VERIFICAR SOLO' if args.verificar_solo else 'REAL')}")
    print("="*80)
    
    models, uid = conectar_odoo()
    if not models or not uid:
        return
    
    password = ODOO_CONFIG['pass']
    
    # Verificar que los grupos existen
    if not verificar_grupos_inventory(models, uid, password):
        print("\n❌ No se puede continuar sin los grupos necesarios")
        return
    
    # Obtener estado actual del usuario
    usuario_actual = obtener_usuario_actual(models, uid, password)
    if not usuario_actual:
        return
    
    verificar_grupos_usuario(usuario_actual)
    
    if args.verificar_solo:
        print("\n✅ Verificación completada (sin cambios)")
        return
    
    # Asignar grupos si es necesario
    if asignar_grupos_inventory(models, uid, password, dry_run=args.dry_run):
        if not args.dry_run:
            verificar_permisos_finales(models, uid, password)
        
        print("\n" + "="*80)
        if args.dry_run:
            print("💡 Ejecuta sin --dry-run para aplicar los cambios")
        else:
            print("✅ Proceso completado")
        print("="*80)
    else:
        print("\n❌ No se pudieron asignar los permisos")

if __name__ == "__main__":
    main()

