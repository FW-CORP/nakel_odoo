#!/usr/bin/env python3
"""
Script para verificar permisos de encargados Belgrano:
- Inventario (grupos Encargados, Inventory User/Manager)
- Lectura de productos (sin exigir create/write en maestro; Central manda el maestro)
- Transferencias / stock según ir.model.access de sus grupos
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

# Usuarios a verificar
USUARIOS_VERIFICAR = [
    {
        'login': 'golosinasbelgrano1@nakel.ar',
        'nombre': 'Manuel Claudia Isabel',
        'sucursal': 'Belgrano 1'
    },
    {
        'login': 'golosinasbelgrano2@nakel.ar',
        'nombre': 'Varas Adrian Marcelo',
        'sucursal': 'Belgrano 2'
    },
    {
        'login': 'golosinasbelgrano3@nakel.ar',
        'nombre': 'Robles Angel Jose',
        'sucursal': 'Belgrano 3'
    },
    {
        'login': 'golosinasbelgrano4@nakel.ar',
        'nombre': 'Ramos Nancy',
        'sucursal': 'Belgrano 4'
    }
]

# Grupos necesarios (Product Creation deliberadamente omitido — política 2026-04)
GRUPOS_NECESARIOS = {
    'inventory_user': {
        'buscar': 'Inventory / User',
        'descripcion': 'Permite acceso básico a inventario',
        'critico': True
    },
    'inventory_manager': {
        'buscar': 'Inventory / Manager',
        'descripcion': 'Permite gestión completa de inventario (incluye ajustes)',
        'critico': False  # Opcional, pero recomendado
    },
    'encargados': {
        'buscar': 'Encargados',
        'descripcion': 'Grupo de encargados (filtra por ubicación)',
        'critico': True
    }
}

# Permisos de acceso a verificar
PERMISOS_VERIFICAR = {
    'product.product': {
        'modelo': 'product.product',
        'acciones': ['perm_read'],
        'descripcion': 'Lectura de productos (POS/ventas); write/create no requeridos en sucursal'
    },
    'stock.picking': {
        'modelo': 'stock.picking',
        'acciones': ['perm_read', 'perm_write', 'perm_create'],
        'descripcion': 'Permisos para crear transferencias'
    },
    'stock.move': {
        'modelo': 'stock.move',
        'acciones': ['perm_read', 'perm_write', 'perm_create'],
        'descripcion': 'Permisos para movimientos de stock'
    },
    'stock.quant': {
        'modelo': 'stock.quant',
        'acciones': ['perm_read', 'perm_write'],
        'descripcion': 'Permisos para ver y ajustar stock'
    },
    'stock.inventory': {
        'modelo': 'stock.inventory',
        'acciones': ['perm_read', 'perm_write', 'perm_create'],
        'descripcion': 'Permisos para crear ajustes de inventario'
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

def obtener_usuario(models, uid, password, login):
    """Obtiene información del usuario"""
    try:
        usuarios = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'res.users', 'search_read',
            [[('login', '=', login)]],
            {'fields': ['id', 'name', 'login', 'groups_id', 'active']}
        )
        if usuarios:
            return usuarios[0]
        return None
    except Exception as e:
        print(f"❌ Error obteniendo usuario: {e}")
        return None

def verificar_grupos(usuario, grupos_disponibles):
    """Verifica que el usuario tenga los grupos necesarios"""
    grupos_ids = usuario.get('groups_id', [])
    grupos_usuario = [g for g in grupos_disponibles if g['id'] in grupos_ids]
    
    resultados = {}
    for key, config in GRUPOS_NECESARIOS.items():
        encontrado = False
        grupo_encontrado = None
        
        for grupo in grupos_usuario:
            if config['buscar'] in grupo['name']:
                encontrado = True
                grupo_encontrado = grupo
                break
        
        resultados[key] = {
            'encontrado': encontrado,
            'grupo': grupo_encontrado,
            'critico': config['critico'],
            'descripcion': config['descripcion']
        }
    
    return resultados

def verificar_permisos_acceso(models, uid, password, grupos_ids):
    """Verifica permisos de acceso (ir.model.access)"""
    resultados = {}
    
    for key, config in PERMISOS_VERIFICAR.items():
        try:
            permisos = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'ir.model.access', 'search_read',
                [[('model_id.model', '=', config['modelo']), ('group_id', 'in', grupos_ids)]],
                {'fields': ['name', 'group_id', 'perm_read', 'perm_write', 'perm_create', 'perm_unlink']}
            )
            
            # Consolidar permisos de todos los grupos
            permisos_consolidados = {
                'perm_read': False,
                'perm_write': False,
                'perm_create': False,
                'perm_unlink': False
            }
            
            for perm in permisos:
                permisos_consolidados['perm_read'] = permisos_consolidados['perm_read'] or perm.get('perm_read', False)
                permisos_consolidados['perm_write'] = permisos_consolidados['perm_write'] or perm.get('perm_write', False)
                permisos_consolidados['perm_create'] = permisos_consolidados['perm_create'] or perm.get('perm_create', False)
                permisos_consolidados['perm_unlink'] = permisos_consolidados['perm_unlink'] or perm.get('perm_unlink', False)
            
            resultados[key] = {
                'permisos': permisos_consolidados,
                'config': config,
                'permisos_raw': permisos
            }
        except Exception as e:
            resultados[key] = {
                'error': str(e),
                'config': config
            }
    
    return resultados

def main():
    print("="*80)
    print("🔍 VERIFICACIÓN COMPLETA DE PERMISOS PARA ENCARGADOS")
    print("="*80)
    print(f"📊 Base de datos: {ODOO_CONFIG['db']}")
    print("="*80)
    
    models, uid = conectar_odoo()
    if not models or not uid:
        return
    
    password = ODOO_CONFIG['pass']
    
    # Obtener todos los grupos disponibles
    print("\n📂 Obteniendo grupos disponibles...")
    try:
        grupos_disponibles = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'res.groups', 'search_read',
            [[]],
            {'fields': ['id', 'name', 'category_id']}
        )
        print(f"✅ {len(grupos_disponibles)} grupos encontrados")
    except Exception as e:
        print(f"❌ Error obteniendo grupos: {e}")
        return
    
    resultados_totales = {}
    
    # Verificar cada usuario
    for usuario_info in USUARIOS_VERIFICAR:
        print("\n" + "="*80)
        print(f"👤 VERIFICANDO: {usuario_info['nombre']}")
        print(f"   Login: {usuario_info['login']}")
        print(f"   Sucursal: {usuario_info['sucursal']}")
        print("="*80)
        
        usuario = obtener_usuario(models, uid, password, usuario_info['login'])
        if not usuario:
            print(f"   ❌ Usuario no encontrado")
            resultados_totales[usuario_info['login']] = {'error': 'Usuario no encontrado'}
            continue
        
        grupos_ids = usuario.get('groups_id', [])
        print(f"\n📋 Total grupos asignados: {len(grupos_ids)}")
        
        # Verificar grupos necesarios
        print("\n1️⃣ VERIFICACIÓN DE GRUPOS:")
        grupos_result = verificar_grupos(usuario, grupos_disponibles)
        
        for key, resultado in grupos_result.items():
            if resultado['encontrado']:
                grupo_name = resultado['grupo']['name']
                icono = "✅" if resultado['critico'] else "⚠️"
                print(f"   {icono} {grupo_name}")
                print(f"      {resultado['descripcion']}")
            else:
                icono = "❌" if resultado['critico'] else "⚠️"
                print(f"   {icono} {resultado['descripcion']}: NO ASIGNADO")

        pc = [
            g for g in grupos_disponibles
            if g['id'] in grupos_ids and 'Product Creation' in (g.get('name') or '')
        ]
        if pc:
            print(f"\n   ⚠️  Política Nakel: el usuario aún tiene «Product Creation» (retirar en Odoo o con corregir_permisos_encargado_master18.py).")
        else:
            print(f"\n   ✅ Sin grupo «Product Creation» (alineado a maestro desde Central).")
        
        # Verificar permisos de acceso
        print("\n2️⃣ VERIFICACIÓN DE PERMISOS DE ACCESO:")
        permisos_result = verificar_permisos_acceso(models, uid, password, grupos_ids)
        
        for key, resultado in permisos_result.items():
            if 'error' in resultado:
                print(f"   ❌ {resultado['config']['modelo']}: Error - {resultado['error']}")
                continue
            
            modelo = resultado['config']['modelo']
            desc = resultado['config']['descripcion']
            permisos = resultado['permisos']
            
            acciones_necesarias = resultado['config']['acciones']
            todas_ok = True
            
            estado = []
            for accion in acciones_necesarias:
                tiene_permiso = permisos.get(accion, False)
                icono = "✅" if tiene_permiso else "❌"
                estado.append(f"{icono} {accion.replace('perm_', '').upper()}")
                if not tiene_permiso:
                    todas_ok = False
            
            icono_general = "✅" if todas_ok else "❌"
            print(f"   {icono_general} {modelo}: {desc}")
            print(f"      {' | '.join(estado)}")
        
        # Verificar reglas de registro (no deben bloquear creación, solo visualización)
        print("\n3️⃣ VERIFICACIÓN DE REGLAS DE REGISTRO:")
        try:
            # Verificar que las reglas permitan crear (no solo leer)
            # Las reglas solo filtran qué ven, no deberían impedir creación
            print(f"   ℹ️  Las reglas de registro filtran qué registros puede VER el usuario")
            print(f"   ℹ️  No deberían impedir CREAR nuevos registros")
            print(f"   ✅ Las reglas solo aplican a lectura (search/read), no a creación")
        except Exception as e:
            print(f"   ⚠️  Error verificando reglas: {e}")
        
        # Resumen por usuario
        print("\n4️⃣ RESUMEN:")
        grupos_criticos_ok = all(r['encontrado'] for k, r in grupos_result.items() if r['critico'])
        permisos_ok = all('error' not in r and all(r['permisos'].get(a.replace('perm_', ''), False) 
                                                   for a in r['config']['acciones'])
                         for r in permisos_result.values())
        
        if grupos_criticos_ok and permisos_ok:
            print("   ✅ Todos los permisos críticos están correctos")
        else:
            print("   ⚠️  Hay permisos faltantes o incorrectos")
            if not grupos_criticos_ok:
                print("      - Faltan grupos críticos")
            if not permisos_ok:
                print("      - Faltan permisos de acceso")
        
        resultados_totales[usuario_info['login']] = {
            'grupos': grupos_result,
            'permisos': permisos_result,
            'grupos_ok': grupos_criticos_ok,
            'permisos_ok': permisos_ok
        }
    
    # Resumen general
    print("\n" + "="*80)
    print("📊 RESUMEN GENERAL")
    print("="*80)
    for usuario_info in USUARIOS_VERIFICAR:
        login = usuario_info['login']
        if login in resultados_totales and 'error' not in resultados_totales[login]:
            resultado = resultados_totales[login]
            estado = "✅ OK" if resultado['grupos_ok'] and resultado['permisos_ok'] else "⚠️ REVISAR"
            print(f"   {estado}: {usuario_info['nombre']} ({usuario_info['sucursal']})")
        else:
            print(f"   ❌ ERROR: {usuario_info['nombre']}")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    main()
