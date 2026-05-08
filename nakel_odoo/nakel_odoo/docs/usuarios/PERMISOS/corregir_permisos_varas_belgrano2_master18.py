#!/usr/bin/env python3
"""
Script para corregir permisos de Varas Adrian Marcelo (Belgrano 2)
Asigna el grupo "Encargados Belgrano 2" que falta
Autor: Corolla
Fecha: 2025-01-XX
"""

import sys
import os
import xmlrpc.client

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

def main():
    print("="*80)
    print("🔧 CORRECCIÓN DE PERMISOS: Varas Adrian Marcelo (Belgrano 2)")
    print("="*80)
    print("Problema: Usuario no puede crear traslados (stock.picking)")
    print("Causa: Falta grupo 'Encargados Belgrano 2'")
    print("="*80)
    
    models, uid = conectar_odoo()
    if not models or not uid:
        return
    
    password = ODOO_CONFIG['pass']
    db = ODOO_CONFIG['db']
    usuario_id = 102
    
    # 1. Verificar usuario
    print("\n1️⃣ Verificando usuario...")
    usuario = models.execute_kw(
        db, uid, password,
        'res.users', 'read',
        [[usuario_id]],
        {'fields': ['id', 'name', 'login', 'groups_id']}
    )
    
    if not usuario:
        print("❌ Usuario ID 102 no encontrado")
        return
    
    usuario = usuario[0]
    print(f"   ✅ Usuario: {usuario['name']} ({usuario.get('login', 'N/A')})")
    
    grupos_actuales = usuario.get('groups_id', [])
    print(f"   Grupos actuales: {len(grupos_actuales)}")
    
    # 2. Buscar grupo "Encargados Belgrano 2"
    print("\n2️⃣ Buscando grupo 'Encargados Belgrano 2'...")
    grupos_b2 = models.execute_kw(
        db, uid, password,
        'res.groups', 'search_read',
        [[('name', '=', 'Encargados Belgrano 2')]],
        {'fields': ['id', 'name', 'category_id']}
    )
    
    if not grupos_b2:
        print("   ❌ Grupo 'Encargados Belgrano 2' no encontrado")
        print("   💡 Ejecuta primero: configurar_permisos_inventario_por_sucursal_master18.py")
        return
    
    grupo_b2 = grupos_b2[0]
    grupo_b2_id = grupo_b2['id']
    print(f"   ✅ Grupo encontrado: {grupo_b2['name']} (ID: {grupo_b2_id})")
    
    # 3. Verificar si ya tiene el grupo
    if grupo_b2_id in grupos_actuales:
        print("\n   ✅ Usuario YA tiene el grupo asignado")
        print("   ⚠️  El problema puede ser otro. Verifica:")
        print("      - Que el usuario cerró sesión y volvió a iniciar")
        print("      - Que las reglas de registro están activas")
        return
    
    # 4. Asignar grupo al usuario
    print("\n3️⃣ Asignando grupo al usuario...")
    grupos_actuales.append(grupo_b2_id)
    
    try:
        models.execute_kw(
            db, uid, password,
            'res.users', 'write',
            [[usuario_id], {'groups_id': [(6, 0, grupos_actuales)]}]
        )
        print(f"   ✅ Grupo 'Encargados Belgrano 2' asignado exitosamente")
    except Exception as e:
        print(f"   ❌ Error asignando grupo: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 5. Verificar grupos de inventario necesarios
    print("\n4️⃣ Verificando grupos adicionales necesarios...")
    
    # Verificar Inventory / User
    grupo_inventory_user = models.execute_kw(
        db, uid, password,
        'res.groups', 'search_read',
        [[('name', '=', 'User'), ('category_id.name', '=', 'Inventory')]],
        {'fields': ['id', 'name']}
    )
    
    if grupo_inventory_user:
        grupo_inv_user_id = grupo_inventory_user[0]['id']
        if grupo_inv_user_id in grupos_actuales:
            print(f"   ✅ Tiene 'Inventory / User' (ID: {grupo_inv_user_id})")
        else:
            print(f"   ⚠️  No tiene 'Inventory / User' - Este grupo es necesario para operaciones de inventario")
            print(f"   💡 Considera agregarlo si el problema persiste")
    else:
        print(f"   ⚠️  No se encontró 'Inventory / User'")
    
    # Verificar Product Creation
    grupo_product_creation = models.execute_kw(
        db, uid, password,
        'res.groups', 'search_read',
        [[('name', '=', 'Product Creation')]],
        {'fields': ['id', 'name']}
    )
    
    if grupo_product_creation:
        grupo_prod_cre_id = grupo_product_creation[0]['id']
        if grupo_prod_cre_id in grupos_actuales:
            print(f"   ✅ Tiene 'Product Creation' (ID: {grupo_prod_cre_id})")
        else:
            print(f"   ℹ️  No tiene 'Product Creation' (no crítico para traslados)")
    
    # Resumen final
    print("\n" + "="*80)
    print("✅ CORRECCIÓN COMPLETADA")
    print("="*80)
    print("\n⚠️  IMPORTANTE:")
    print("   1. El usuario debe CERRAR SESIÓN en Odoo")
    print("   2. Volver a INICIAR SESIÓN para que los cambios surtan efecto")
    print("   3. Luego debería poder crear traslados sin problemas")
    print("\n💡 Si el problema persiste después de reiniciar sesión:")
    print("   - Verifica que las reglas de registro están activas")
    print("   - Ejecuta: diagnosticar_permisos_crear_traslado_master18.py")
    print("="*80)

if __name__ == "__main__":
    main()
