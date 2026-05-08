#!/usr/bin/env python3
"""
Script para configurar permisos de inventario por sucursal
Crea grupos de usuarios por sucursal y reglas de registro que filtran por ubicación
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

# Mapeo de sucursales a usuarios
SUCURSALES_CONFIG = {
    'Belgrano 1': {
        'warehouse_code': 'B1',
        'location_path': 'B1/Existencias',
        'usuarios': ['golosinasbelgrano1@nakel.ar']
    },
    'Belgrano 2': {
        'warehouse_code': 'B2',
        'location_path': 'B2/Existencias',
        'usuarios': ['golosinasbelgrano2@nakel.ar']
    },
    'Belgrano 3': {
        'warehouse_code': 'B3',
        'location_path': 'B3/Existencias',
        'usuarios': ['golosinasbelgrano3@nakel.ar']
    },
    'Belgrano 4': {
        'warehouse_code': 'B4',
        'location_path': 'B4/Existencias',
        'usuarios': ['golosinasbelgrano4@nakel.ar']
    }
}

# Definición de reglas por modelo
REGLAS_POR_MODELO = {
    'stock.picking': {
        'name_template': 'Encargados {sucursal}: Ver solo transferencias de {sucursal}',
        'domain_template': [
            '|',
            ('location_id', 'child_of', '{location_id}'),
            ('location_dest_id', 'child_of', '{location_id}')
        ]
    },
    'stock.move': {
        'name_template': 'Encargados {sucursal}: Ver solo movimientos de {sucursal}',
        'domain_template': [
            '|',
            ('location_id', 'child_of', '{location_id}'),
            ('location_dest_id', 'child_of', '{location_id}')
        ]
    },
    'stock.quant': {
        'name_template': 'Encargados {sucursal}: Ver solo stock de {sucursal}',
        'domain_template': [
            ('location_id', 'child_of', '{location_id}')
        ]
    },
    'stock.picking.type': {
        'name_template': 'Encargados {sucursal}: Ver solo tipos de operación de {sucursal}',
        'domain_template': [
            ('warehouse_id', '=', '{warehouse_id}')
        ]
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

def obtener_ubicacion_por_path(models, uid, password, path):
    """Busca una ubicación por su ruta completa"""
    try:
        locations = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'stock.location', 'search_read',
            [[('complete_name', '=', path)]],
            {'fields': ['id', 'name', 'complete_name', 'warehouse_id']}
        )
        if locations:
            return locations[0]
        return None
    except Exception as e:
        print(f"   ⚠️  Error buscando ubicación {path}: {e}")
        return None

def obtener_warehouse_por_codigo(models, uid, password, code):
    """Busca un warehouse por su código"""
    try:
        warehouses = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'stock.warehouse', 'search_read',
            [[('code', '=', code)]],
            {'fields': ['id', 'name', 'code']}
        )
        if warehouses:
            return warehouses[0]
        return None
    except Exception as e:
        print(f"   ⚠️  Error buscando warehouse {code}: {e}")
        return None

def obtener_categoria_inventory(models, uid, password):
    """Obtiene la categoría de grupos 'Inventory'"""
    try:
        categorias = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.module.category', 'search_read',
            [[('name', '=', 'Inventory')]],
            {'fields': ['id', 'name']}
        )
        if categorias:
            return categorias[0]['id']
        return None
    except Exception as e:
        print(f"   ⚠️  Error obteniendo categoría Inventory: {e}")
        return None

def crear_o_obtener_grupo(models, uid, password, nombre_grupo, categoria_id):
    """Crea un grupo de usuarios o lo obtiene si ya existe"""
    try:
        # Buscar grupo existente
        grupos = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'res.groups', 'search_read',
            [[('name', '=', nombre_grupo)]],
            {'fields': ['id', 'name', 'category_id']}
        )
        
        if grupos:
            print(f"      ✅ Grupo ya existe: {nombre_grupo} (ID: {grupos[0]['id']})")
            return grupos[0]['id']
        
        # Crear nuevo grupo
        grupo_id = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'res.groups', 'create',
            [{
                'name': nombre_grupo,
                'category_id': categoria_id,
                'comment': f'Grupo para encargados de {nombre_grupo}. Restringe acceso a inventario solo de su sucursal.'
            }]
        )
        print(f"      ✅ Grupo creado: {nombre_grupo} (ID: {grupo_id})")
        return grupo_id
        
    except Exception as e:
        print(f"      ❌ Error creando/obteniendo grupo {nombre_grupo}: {e}")
        return None

def crear_regla_registro(models, uid, password, modelo, nombre, dominio, grupo_id, dry_run=False):
    """Crea una regla de registro (ir.rule)"""
    try:
        # Obtener model_id
        model_ids = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.model', 'search',
            [[('model', '=', modelo)]]
        )
        if not model_ids:
            print(f"         ❌ Modelo {modelo} no encontrado")
            return None
        
        model_id = model_ids[0]
        
        if dry_run:
            print(f"         [DRY-RUN] Crearía regla: {nombre}")
            print(f"         [DRY-RUN]   Dominio: {dominio}")
            return None
        
        # Buscar si ya existe una regla con el mismo nombre
        reglas_existentes = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.rule', 'search',
            [[('name', '=', nombre), ('model_id', '=', model_id)]]
        )
        
        if reglas_existentes:
            # Actualizar regla existente
            models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'ir.rule', 'write',
                [reglas_existentes, {
                    'domain_force': str(dominio),
                    'groups': [(6, 0, [grupo_id])],
                    'active': True
                }]
            )
            print(f"         ✅ Regla actualizada: {nombre}")
            return reglas_existentes[0]
        
        # Crear nueva regla
        regla_id = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.rule', 'create',
            [{
                'name': nombre,
                'model_id': model_id,
                'domain_force': str(dominio),
                'groups': [(6, 0, [grupo_id])],
                'active': True
            }]
        )
        print(f"         ✅ Regla creada: {nombre} (ID: {regla_id})")
        return regla_id
        
    except Exception as e:
        print(f"         ❌ Error creando regla {nombre}: {e}")
        import traceback
        traceback.print_exc()
        return None

def asignar_grupo_a_usuarios(models, uid, password, grupo_id, logins_usuarios, dry_run=False):
    """Asigna un grupo a una lista de usuarios"""
    try:
        usuarios_ids = []
        for login in logins_usuarios:
            usuarios = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'res.users', 'search',
                [[('login', '=', login)]]
            )
            if usuarios:
                usuarios_ids.append(usuarios[0])
            else:
                print(f"         ⚠️  Usuario {login} no encontrado")
        
        if not usuarios_ids:
            print(f"         ⚠️  No se encontraron usuarios para asignar")
            return False
        
        if dry_run:
            print(f"         [DRY-RUN] Asignaría grupo a {len(usuarios_ids)} usuario(s)")
            return True
        
        # Asignar grupo a usuarios
        for user_id in usuarios_ids:
            # Obtener grupos actuales del usuario
            usuario = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'res.users', 'read',
                [[user_id]],
                {'fields': ['groups_id']}
            )
            grupos_actuales = usuario[0].get('groups_id', [])
            
            # Agregar nuevo grupo si no está ya asignado
            if grupo_id not in grupos_actuales:
                grupos_actuales.append(grupo_id)
                models.execute_kw(
                    ODOO_CONFIG['db'], uid, password,
                    'res.users', 'write',
                    [[user_id], {'groups_id': [(6, 0, grupos_actuales)]}]
                )
                user_info = models.execute_kw(
                    ODOO_CONFIG['db'], uid, password,
                    'res.users', 'read',
                    [[user_id]],
                    {'fields': ['name', 'login']}
                )
                print(f"         ✅ Grupo asignado a: {user_info[0].get('name')} ({user_info[0].get('login')})")
            else:
                user_info = models.execute_kw(
                    ODOO_CONFIG['db'], uid, password,
                    'res.users', 'read',
                    [[user_id]],
                    {'fields': ['name', 'login']}
                )
                print(f"         ℹ️  Usuario ya tenía el grupo: {user_info[0].get('name')}")
        
        return True
        
    except Exception as e:
        print(f"         ❌ Error asignando grupo a usuarios: {e}")
        import traceback
        traceback.print_exc()
        return False

def procesar_sucursal(models, uid, password, sucursal_nombre, config, categoria_id, dry_run=False):
    """Procesa la configuración para una sucursal"""
    print(f"\n{'='*80}")
    print(f"🏢 PROCESANDO SUCURSAL: {sucursal_nombre}")
    print(f"{'='*80}")
    
    # Obtener ubicación
    print(f"\n📍 Obteniendo ubicación...")
    ubicacion = obtener_ubicacion_por_path(models, uid, password, config['location_path'])
    if not ubicacion:
        print(f"   ❌ No se pudo encontrar la ubicación: {config['location_path']}")
        return False
    
    location_id = ubicacion['id']
    print(f"   ✅ Ubicación encontrada: {ubicacion.get('complete_name')} (ID: {location_id})")
    
    # Obtener warehouse
    print(f"\n🏭 Obteniendo warehouse...")
    warehouse = obtener_warehouse_por_codigo(models, uid, password, config['warehouse_code'])
    if not warehouse:
        print(f"   ❌ No se pudo encontrar el warehouse: {config['warehouse_code']}")
        return False
    
    warehouse_id = warehouse['id']
    print(f"   ✅ Warehouse encontrado: {warehouse.get('name')} (ID: {warehouse_id})")
    
    # Crear grupo
    nombre_grupo = f"Encargados {sucursal_nombre}"
    print(f"\n👥 Creando/obteniendo grupo...")
    grupo_id = crear_o_obtener_grupo(models, uid, password, nombre_grupo, categoria_id)
    if not grupo_id:
        return False
    
    # Crear reglas de registro
    print(f"\n📋 Creando reglas de registro...")
    for modelo, regla_config in REGLAS_POR_MODELO.items():
        nombre_regla = regla_config['name_template'].format(sucursal=sucursal_nombre)
        dominio_template = regla_config['domain_template']
        
        # Construir dominio reemplazando placeholders
        dominio = []
        for item in dominio_template:
            if isinstance(item, str):
                # Operadores lógicos ('|', '&', '!')
                dominio.append(item)
            elif isinstance(item, tuple) and len(item) == 3:
                # Tupla (campo, operador, valor)
                campo, operador, valor = item
                # Reemplazar placeholders en el valor
                if valor == '{location_id}':
                    valor = location_id
                elif valor == '{warehouse_id}':
                    valor = warehouse_id
                dominio.append((campo, operador, valor))
            else:
                # Otros tipos (listas anidadas, etc.)
                dominio.append(item)
        
        crear_regla_registro(
            models, uid, password,
            modelo, nombre_regla, dominio, grupo_id, dry_run
        )
    
    # Asignar grupo a usuarios
    print(f"\n👤 Asignando grupo a usuarios...")
    asignar_grupo_a_usuarios(
        models, uid, password,
        grupo_id, config['usuarios'], dry_run
    )
    
    return True

def main():
    parser = argparse.ArgumentParser(description='Configurar permisos de inventario por sucursal')
    parser.add_argument('--dry-run', action='store_true', help='Ejecutar en modo dry-run (sin hacer cambios)')
    args = parser.parse_args()
    
    modo = "DRY-RUN" if args.dry_run else "REAL"
    
    print("="*80)
    print("🔧 CONFIGURACIÓN DE PERMISOS DE INVENTARIO POR SUCURSAL")
    print("="*80)
    print(f"📊 Base de datos: {ODOO_CONFIG['db']}")
    print(f"🔍 Modo: {modo}")
    print("="*80)
    
    models, uid = conectar_odoo()
    if not models or not uid:
        return
    
    password = ODOO_CONFIG['pass']
    
    # Obtener categoría Inventory
    print("\n📂 Obteniendo categoría de grupos 'Inventory'...")
    categoria_id = obtener_categoria_inventory(models, uid, password)
    if not categoria_id:
        print("   ❌ No se pudo obtener la categoría Inventory")
        return
    
    print(f"   ✅ Categoría encontrada (ID: {categoria_id})")
    
    # Procesar cada sucursal
    resultados = {}
    for sucursal_nombre, config in SUCURSALES_CONFIG.items():
        resultado = procesar_sucursal(
            models, uid, password,
            sucursal_nombre, config, categoria_id, args.dry_run
        )
        resultados[sucursal_nombre] = resultado
    
    # Resumen
    print("\n" + "="*80)
    print("📊 RESUMEN")
    print("="*80)
    for sucursal, resultado in resultados.items():
        estado = "✅ Completado" if resultado else "❌ Error"
        print(f"   {estado}: {sucursal}")
    
    print("\n" + "="*80)
    if args.dry_run:
        print("💡 Este fue un DRY-RUN. Para aplicar los cambios, ejecuta sin --dry-run")
    else:
        print("✅ Configuración completada")
    print("="*80)

if __name__ == "__main__":
    main()
