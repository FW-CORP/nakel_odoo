#!/usr/bin/env python3
"""
Script para diagnosticar permisos de inventario de Fabiana Gimenez en master_18
Verifica grupos, permisos de acceso y reglas de registro que puedan estar limitando el acceso
Autor: Corolla
Fecha: 2025-12-29
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

USUARIO_FABIANA_ID = 92

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
    print("🔍 DIAGNÓSTICO DE PERMISOS DE INVENTARIO")
    print("="*80)
    print(f"👤 Usuario: Fabiana Gimenez (ID: {USUARIO_FABIANA_ID})")
    print(f"📊 Base de datos: {ODOO_CONFIG['db']}")
    print("="*80)
    
    models, uid = conectar_odoo()
    if not models or not uid:
        return
    
    password = ODOO_CONFIG['pass']
    
    # 1. Verificar grupos del usuario
    print("\n1️⃣ GRUPOS DEL USUARIO:")
    usuario = models.execute_kw(
        ODOO_CONFIG['db'], uid, password,
        'res.users', 'read',
        [[USUARIO_FABIANA_ID]],
        {'fields': ['name', 'login', 'groups_id']}
    )
    grupos_ids = []
    if usuario:
        grupos_ids = usuario[0].get('groups_id', [])
        print(f"   Nombre: {usuario[0].get('name')}")
        print(f"   Login: {usuario[0].get('login')}")
        print(f"   Total grupos: {len(grupos_ids)}")
        
        # Buscar grupos de Inventory individualmente
        grupos_inv_all = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'res.groups', 'search_read',
            [[('category_id.name', '=', 'Inventory')]],
            {'fields': ['id', 'name']}
        )
        print(f"   Grupos de Inventory que tiene:")
        for g in grupos_inv_all:
            if g['id'] in grupos_ids:
                print(f"     ✅ {g.get('name')} (ID: {g['id']})")
    
    # 2. Verificar permisos de acceso para stock.inventory
    print("\n2️⃣ PERMISOS DE ACCESO PARA stock.inventory:")
    permisos = models.execute_kw(
        ODOO_CONFIG['db'], uid, password,
        'ir.model.access', 'search_read',
        [[('model_id.model', '=', 'stock.inventory'), ('group_id', 'in', grupos_ids)]],
        {'fields': ['name', 'group_id', 'perm_read', 'perm_write', 'perm_create', 'perm_unlink']}
    )
    if permisos:
        for p in permisos:
            grupo_name = p.get('group_id', [False, ''])[1] if p.get('group_id') else 'N/A'
            print(f"   Grupo: {grupo_name}")
            print(f"     Read: {p.get('perm_read')}, Write: {p.get('perm_write')}, Create: {p.get('perm_create')}")
    else:
        print("   ⚠️  No se encontraron permisos de acceso específicos para este usuario")
    
    # 3. Verificar permisos para stock.quant
    print("\n3️⃣ PERMISOS DE ACCESO PARA stock.quant:")
    permisos_quant = models.execute_kw(
        ODOO_CONFIG['db'], uid, password,
        'ir.model.access', 'search_read',
        [[('model_id.model', '=', 'stock.quant'), ('group_id', 'in', grupos_ids)]],
        {'fields': ['name', 'group_id', 'perm_read', 'perm_write', 'perm_create']}
    )
    if permisos_quant:
        for p in permisos_quant:
            grupo_name = p.get('group_id', [False, ''])[1] if p.get('group_id') else 'N/A'
            print(f"   Grupo: {grupo_name}")
            print(f"     Read: {p.get('perm_read')}, Write: {p.get('perm_write')}, Create: {p.get('perm_create')}")
    
    # 4. Verificar reglas de registro que puedan estar limitando acceso
    print("\n4️⃣ REGLAS DE REGISTRO (ir.rule) PARA stock.inventory:")
    try:
        rules = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.rule', 'search_read',
            [[('model_id.model', '=', 'stock.inventory')]],
            {'fields': ['name', 'domain_force', 'groups']}
        )
        if rules:
            for r in rules[:5]:  # Primeras 5 reglas
                grupos_rule = r.get('groups', [])
                print(f"   Regla: {r.get('name')}")
                if grupos_rule:
                    print(f"     Grupos: {grupos_rule}")
                domain = r.get('domain_force', '')
                if domain:
                    print(f"     Dominio: {domain[:100]}...")
        else:
            print("   ✅ No hay reglas de registro que limiten el acceso")
    except Exception as e:
        print(f"   ⚠️  Error verificando reglas: {e}")
    
    print("\n" + "="*80)
    print("💡 RECOMENDACIONES:")
    print("="*80)
    print("Si el usuario tiene Inventory / Administrator pero aún no puede modificar cantidades:")
    print("1. Verificar que está usando 'Ajustes de Inventario' (no modificar directamente en productos)")
    print("2. Verificar que tiene acceso a las ubicaciones de inventario")
    print("3. Verificar reglas de registro específicas por ubicación")
    print("4. Intentar crear un ajuste de inventario nuevo desde Inventario > Ajustes")

if __name__ == "__main__":
    main()

