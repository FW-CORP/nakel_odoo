#!/usr/bin/env python3
"""
Script para diagnosticar permisos de creación de traslados (stock.picking)
específicamente para Varas Adrian Marcelo (Belgrano 2)
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
    print("🔍 DIAGNÓSTICO DE PERMISOS: CREAR TRASLADOS (stock.picking)")
    print("="*80)
    print("Usuario: Varas Adrian Marcelo (ID: 102)")
    print("="*80)
    
    models, uid = conectar_odoo()
    if not models or not uid:
        return
    
    password = ODOO_CONFIG['pass']
    db = ODOO_CONFIG['db']
    
    # 1. Obtener información del usuario
    print("\n1️⃣ INFORMACIÓN DEL USUARIO")
    print("-" * 80)
    
    usuario = models.execute_kw(
        db, uid, password,
        'res.users', 'read',
        [[102]],
        {'fields': ['id', 'name', 'login', 'groups_id', 'active']}
    )
    
    if not usuario:
        print("❌ Usuario ID 102 no encontrado")
        return
    
    usuario = usuario[0]
    print(f"   Nombre: {usuario['name']}")
    print(f"   Login: {usuario.get('login', 'N/A')}")
    print(f"   Activo: {'Sí' if usuario.get('active', True) else 'No'}")
    print(f"   Grupos asignados: {len(usuario.get('groups_id', []))}")
    
    grupos_ids = usuario.get('groups_id', [])
    if grupos_ids:
        grupos = models.execute_kw(
            db, uid, password,
            'res.groups', 'read',
            [grupos_ids],
            {'fields': ['id', 'name', 'category_id']}
        )
        print(f"\n   Grupos del usuario:")
        for grupo in grupos:
            categoria = grupo.get('category_id', [False, ''])[1] if grupo.get('category_id') else 'Sin categoría'
            print(f"      • {grupo['name']} (Categoría: {categoria}, ID: {grupo['id']})")
    
    # 2. Verificar permisos de acceso (ir.model.access) para stock.picking
    print("\n2️⃣ PERMISOS DE ACCESO (ir.model.access)")
    print("-" * 80)
    
    # Buscar todos los permisos de acceso para stock.picking
    access_rights = models.execute_kw(
        db, uid, password,
        'ir.model.access', 'search_read',
        [[('model_id.model', '=', 'stock.picking')]],
        {'fields': ['id', 'name', 'perm_read', 'perm_write', 'perm_create', 'perm_unlink', 'group_id']}
    )
    
    print(f"   Total de reglas de acceso para stock.picking: {len(access_rights)}")
    
    # Verificar qué grupos del usuario tienen permisos
    grupos_usuario_ids = set(grupos_ids)
    permisos_encontrados = []
    
    for access in access_rights:
        group_id = access.get('group_id', [False])[0] if access.get('group_id') else False
        if group_id and group_id in grupos_usuario_ids:
            permisos_encontrados.append({
                'access': access,
                'grupo_id': group_id
            })
    
    if permisos_encontrados:
        print(f"\n   ✅ Permisos encontrados en grupos del usuario:")
        for perm in permisos_encontrados:
            acc = perm['access']
            grupo_nombre = next((g['name'] for g in grupos if g['id'] == perm['grupo_id']), 'Desconocido')
            print(f"\n      Grupo: {grupo_nombre} (ID: {perm['grupo_id']})")
            print(f"         Nombre regla: {acc.get('name', 'N/A')}")
            print(f"         Crear: {'✅' if acc.get('perm_create') else '❌'}")
            print(f"         Leer: {'✅' if acc.get('perm_read') else '❌'}")
            print(f"         Escribir: {'✅' if acc.get('perm_write') else '❌'}")
            print(f"         Eliminar: {'✅' if acc.get('perm_unlink') else '❌'}")
    else:
        print(f"\n   ❌ NO se encontraron permisos de acceso en los grupos del usuario")
    
    # Buscar permisos públicos (sin grupo)
    permisos_publicos = [a for a in access_rights if not a.get('group_id')]
    if permisos_publicos:
        print(f"\n   ℹ️  Permisos públicos encontrados (aplican a todos):")
        for acc in permisos_publicos:
            print(f"      Regla: {acc.get('name', 'N/A')}")
            print(f"         Crear: {'✅' if acc.get('perm_create') else '❌'}")
    
    # 3. Verificar reglas de registro (ir.rule)
    print("\n3️⃣ REGLAS DE REGISTRO (ir.rule)")
    print("-" * 80)
    
    reglas = models.execute_kw(
        db, uid, password,
        'ir.rule', 'search_read',
        [[('model_id.model', '=', 'stock.picking')]],
        {'fields': ['id', 'name', 'domain_force', 'groups', 'active', 'perm_read', 'perm_write', 'perm_create', 'perm_unlink']}
    )
    
    print(f"   Total de reglas de registro para stock.picking: {len(reglas)}")
    
    # Verificar reglas que aplican a grupos del usuario
    reglas_usuario = []
    for regla in reglas:
        grupos_regla = regla.get('groups', [])
        grupos_regla_ids = [g[0] for g in grupos_regla if isinstance(g, (list, tuple)) and len(g) > 0]
        
        # Si no tiene grupos, aplica a todos
        if not grupos_regla_ids:
            reglas_usuario.append(regla)
        else:
            # Si intersecta con grupos del usuario
            if any(gid in grupos_usuario_ids for gid in grupos_regla_ids):
                reglas_usuario.append(regla)
    
    if reglas_usuario:
        print(f"\n   Reglas que aplican al usuario: {len(reglas_usuario)}")
        for regla in reglas_usuario:
            print(f"\n      Regla: {regla.get('name', 'N/A')} (ID: {regla['id']})")
            print(f"         Activa: {'✅' if regla.get('active', True) else '❌'}")
            print(f"         Dominio: {regla.get('domain_force', '[]')}")
            
            # Verificar permisos específicos en la regla
            perm_create = regla.get('perm_create', True)
            perm_write = regla.get('perm_write', True)
            perm_read = regla.get('perm_read', True)
            perm_unlink = regla.get('perm_unlink', True)
            
            print(f"         Permisos:")
            print(f"            Crear: {'✅' if perm_create else '❌'}")
            print(f"            Leer: {'✅' if perm_read else '❌'}")
            print(f"            Escribir: {'✅' if perm_write else '❌'}")
            print(f"            Eliminar: {'✅' if perm_unlink else '❌'}")
            
            # Verificar si los grupos
            grupos_regla = regla.get('groups', [])
            if grupos_regla:
                grupos_regla_ids = [g[0] for g in grupos_regla if isinstance(g, (list, tuple)) and len(g) > 0]
                grupos_regla_nombres = [
                    next((g['name'] for g in grupos if g['id'] == gid), f'ID:{gid}')
                    for gid in grupos_regla_ids if gid in grupos_usuario_ids
                ]
                if grupos_regla_nombres:
                    print(f"         Grupos: {', '.join(grupos_regla_nombres)}")
    else:
        print(f"\n   ℹ️  No hay reglas específicas para los grupos del usuario")
    
    # 4. Verificar grupo específico "Encargados Belgrano 2"
    print("\n4️⃣ GRUPO ESPECÍFICO: ENCARGADOS BELGRANO 2")
    print("-" * 80)
    
    grupo_encargados_b2 = models.execute_kw(
        db, uid, password,
        'res.groups', 'search_read',
        [[('name', '=', 'Encargados Belgrano 2')]],
        {'fields': ['id', 'name', 'users', 'category_id']}
    )
    
    if grupo_encargados_b2:
        grupo_b2 = grupo_encargados_b2[0]
        print(f"   ✅ Grupo encontrado: {grupo_b2['name']} (ID: {grupo_b2['id']})")
        
        # Verificar si el usuario está en este grupo
        usuarios_grupo = grupo_b2.get('users', [])
        usuarios_grupo_ids = [u[0] for u in usuarios_grupo if isinstance(u, (list, tuple)) and len(u) > 0]
        
        if 102 in usuarios_grupo_ids:
            print(f"   ✅ Usuario está en este grupo")
        else:
            print(f"   ❌ Usuario NO está en este grupo")
        
        # Verificar reglas de este grupo específicamente
        reglas_b2 = models.execute_kw(
            db, uid, password,
            'ir.rule', 'search_read',
            [[('groups', 'in', [grupo_b2['id']]), ('model_id.model', '=', 'stock.picking')]],
            {'fields': ['id', 'name', 'domain_force', 'perm_create', 'perm_write', 'active']}
        )
        
        if reglas_b2:
            print(f"\n   Reglas de registro para este grupo: {len(reglas_b2)}")
            for regla in reglas_b2:
                print(f"      • {regla.get('name', 'N/A')} (ID: {regla['id']})")
                print(f"         Activa: {'✅' if regla.get('active', True) else '❌'}")
                print(f"         Crear: {'✅' if regla.get('perm_create', True) else '❌'}")
                print(f"         Escribir: {'✅' if regla.get('perm_write', True) else '❌'}")
                if not regla.get('perm_create', True):
                    print(f"         ⚠️  PROBLEMA: Esta regla bloquea la creación de traslados")
    else:
        print(f"   ❌ Grupo 'Encargados Belgrano 2' no encontrado")
    
    # 5. Resumen y diagnóstico
    print("\n" + "="*80)
    print("📊 DIAGNÓSTICO FINAL")
    print("="*80)
    
    tiene_permiso_create = False
    if permisos_encontrados:
        tiene_permiso_create = any(p['access'].get('perm_create') for p in permisos_encontrados)
    
    regla_bloquea_create = False
    for regla in reglas_usuario:
        if regla.get('perm_create') is False:
            regla_bloquea_create = True
            break
    
    print(f"\n   Permisos de acceso (ir.model.access):")
    print(f"      {'✅ Tiene permiso de creación' if tiene_permiso_create else '❌ NO tiene permiso de creación'}")
    
    print(f"\n   Reglas de registro (ir.rule):")
    if regla_bloquea_create:
        print(f"      ❌ Una regla está BLOQUEANDO la creación")
        print(f"      💡 Solución: Modificar la regla para permitir creación (perm_create=True)")
    else:
        print(f"      ✅ Las reglas NO bloquean la creación")
    
    if not tiene_permiso_create:
        print(f"\n   ⚠️  PROBLEMA IDENTIFICADO:")
        print(f"      El usuario NO tiene permisos de acceso para crear stock.picking")
        print(f"      💡 Solución: Asignar grupo 'Inventory / User' o 'Inventory / Manager'")
        print(f"         que tenga permisos de creación en stock.picking")
    
    if tiene_permiso_create and regla_bloquea_create:
        print(f"\n   ⚠️  PROBLEMA IDENTIFICADO:")
        print(f"      Aunque tiene permisos de acceso, una regla bloquea la creación")
        print(f"      💡 Solución: Modificar la regla para permitir creación")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    main()
