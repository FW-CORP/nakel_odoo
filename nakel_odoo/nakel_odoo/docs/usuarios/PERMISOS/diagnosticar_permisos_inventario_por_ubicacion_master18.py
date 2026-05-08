#!/usr/bin/env python3
"""
Script para diagnosticar permisos de inventario por ubicación
Analiza reglas de registro y propone solución para filtrar información por sucursal
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

# Usuario de Belgrano 1
USUARIO_LOGIN = 'golosinasbelgrano1@nakel.ar'

# Modelos de inventario que necesitan filtrado por ubicación
MODELOS_INVENTARIO = [
    'stock.picking',
    'stock.move',
    'stock.quant',
    'stock.inventory',
    'stock.picking.type',
    'stock.warehouse',
]

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
            {'fields': ['id', 'name', 'login', 'groups_id']}
        )
        if usuarios:
            return usuarios[0]
        return None
    except Exception as e:
        print(f"❌ Error obteniendo usuario: {e}")
        return None

def obtener_ubicaciones_warehouse(models, uid, password):
    """Obtiene información de los warehouses (almacenes)"""
    try:
        warehouses = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'stock.warehouse', 'search_read',
            [[]],
            {'fields': ['id', 'name', 'code', 'view_location_id', 'lot_stock_id']}
        )
        return warehouses
    except Exception as e:
        print(f"❌ Error obteniendo warehouses: {e}")
        return []

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
        print(f"❌ Error buscando ubicación {path}: {e}")
        return None

def obtener_reglas_registro(models, uid, password, model_name):
    """Obtiene las reglas de registro para un modelo"""
    try:
        rules = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.rule', 'search_read',
            [[('model_id.model', '=', model_name)]],
            {'fields': ['id', 'name', 'domain_force', 'groups', 'active']}
        )
        return rules
    except Exception as e:
        print(f"❌ Error obteniendo reglas para {model_name}: {e}")
        return []

def main():
    print("="*80)
    print("🔍 DIAGNÓSTICO DE PERMISOS DE INVENTARIO POR UBICACIÓN")
    print("="*80)
    print(f"👤 Usuario: {USUARIO_LOGIN}")
    print(f"📊 Base de datos: {ODOO_CONFIG['db']}")
    print("="*80)
    
    models, uid = conectar_odoo()
    if not models or not uid:
        return
    
    password = ODOO_CONFIG['pass']
    
    # 1. Obtener información del usuario
    print("\n1️⃣ INFORMACIÓN DEL USUARIO:")
    usuario = obtener_usuario(models, uid, password, USUARIO_LOGIN)
    if not usuario:
        print(f"   ❌ Usuario {USUARIO_LOGIN} no encontrado")
        return
    
    print(f"   Nombre: {usuario.get('name')}")
    print(f"   Login: {usuario.get('login')}")
    print(f"   ID: {usuario.get('id')}")
    
    grupos_ids = usuario.get('groups_id', [])
    print(f"   Total grupos: {len(grupos_ids)}")
    
    # Obtener nombres de grupos
    if grupos_ids:
        grupos = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'res.groups', 'read',
            [grupos_ids],
            {'fields': ['id', 'name', 'category_id']}
        )
        print(f"   Grupos asignados:")
        for g in grupos[:10]:  # Primeros 10
            cat_name = g.get('category_id', [False, ''])[1] if g.get('category_id') else 'Sin categoría'
            print(f"     • {g.get('name')} ({cat_name})")
    
    # 2. Obtener información de warehouses y ubicaciones
    print("\n2️⃣ WAREHOUSES Y UBICACIONES:")
    warehouses = obtener_ubicaciones_warehouse(models, uid, password)
    print(f"   Total warehouses: {len(warehouses)}")
    
    ubicacion_belgrano1 = None
    ubicacion_central = None
    
    for wh in warehouses:
        wh_name = wh.get('name', '')
        wh_code = wh.get('code', '')
        print(f"\n   🏢 {wh_name} (Código: {wh_code})")
        
        # Buscar ubicación de existencias
        lot_stock_id = wh.get('lot_stock_id', [False])[0] if wh.get('lot_stock_id') else None
        if lot_stock_id:
            location = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'stock.location', 'read',
                [[lot_stock_id]],
                {'fields': ['id', 'name', 'complete_name']}
            )
            if location:
                print(f"      Ubicación de existencias: {location[0].get('complete_name')}")
                
                # Identificar Belgrano 1 y Central
                if 'Belgrano 1' in wh_name or 'B1' in wh_code or 'belgrano1' in wh_name.lower():
                    ubicacion_belgrano1 = location[0]
                    print(f"      ✅ Identificada como Belgrano 1")
                elif 'Central' in wh_name or 'CEN' in wh_code:
                    ubicacion_central = location[0]
                    print(f"      ✅ Identificada como Nakel Central")
    
    # Buscar ubicaciones si no se encontraron
    if not ubicacion_belgrano1:
        print("\n   🔍 Buscando ubicación B1/Existencias...")
        ubicacion_belgrano1 = obtener_ubicacion_por_path(models, uid, password, 'B1/Existencias')
        if ubicacion_belgrano1:
            print(f"      ✅ Encontrada: {ubicacion_belgrano1.get('complete_name')}")
    
    if not ubicacion_central:
        print("\n   🔍 Buscando ubicación CEN/Existencias...")
        ubicacion_central = obtener_ubicacion_por_path(models, uid, password, 'CEN/Existencias')
        if ubicacion_central:
            print(f"      ✅ Encontrada: {ubicacion_central.get('complete_name')}")
    
    # 3. Analizar reglas de registro existentes
    print("\n3️⃣ REGLAS DE REGISTRO EXISTENTES:")
    print("="*80)
    
    reglas_por_modelo = {}
    for modelo in MODELOS_INVENTARIO:
        print(f"\n   📋 Modelo: {modelo}")
        reglas = obtener_reglas_registro(models, uid, password, modelo)
        reglas_por_modelo[modelo] = reglas
        
        if reglas:
            print(f"      Total reglas: {len(reglas)}")
            for r in reglas[:3]:  # Primeras 3
                nombre = r.get('name', 'Sin nombre')
                activa = "✅" if r.get('active') else "❌"
                grupos = r.get('groups', [])
                domain = r.get('domain_force', '')
                print(f"      {activa} {nombre}")
                if grupos:
                    print(f"         Grupos: {len(grupos)} grupo(s)")
                if domain:
                    domain_preview = str(domain)[:100] + "..." if len(str(domain)) > 100 else str(domain)
                    print(f"         Dominio: {domain_preview}")
        else:
            print(f"      ⚠️  No hay reglas de registro (todos los usuarios ven todos los registros)")
    
    # 4. Verificar qué información ve el usuario actualmente
    print("\n4️⃣ VERIFICACIÓN DE ACCESO ACTUAL:")
    print("="*80)
    
    # Verificar stock.picking (recepciones, almacenamiento, entregas)
    if ubicacion_belgrano1 and ubicacion_central:
        picking_belgrano1 = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'stock.picking', 'search_count',
            [[('location_id', 'child_of', ubicacion_belgrano1['id'])]]
        )
        picking_central = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'stock.picking', 'search_count',
            [[('location_id', 'child_of', ubicacion_central['id'])]]
        )
        print(f"\n   📦 stock.picking (transferencias):")
        print(f"      Belgrano 1: {picking_belgrano1} registros")
        print(f"      Nakel Central: {picking_central} registros")
        print(f"      ⚠️  El usuario actualmente puede ver {picking_belgrano1 + picking_central} registros")
    
    # 5. Análisis y recomendaciones
    print("\n5️⃣ ANÁLISIS Y RECOMENDACIONES:")
    print("="*80)
    
    print("\n   🔍 PROBLEMA IDENTIFICADO:")
    print("      Los encargados de sucursales están viendo información de todas las ubicaciones")
    print("      porque no hay reglas de registro que filtren por ubicación.")
    
    print("\n   💡 SOLUCIÓN PROPUESTA:")
    print("      Crear reglas de registro (ir.rule) que filtren los modelos de inventario")
    print("      por ubicación según el grupo de usuarios o configuración del usuario.")
    
    print("\n   📋 MODELOS QUE NECESITAN FILTRADO:")
    modelos_criticos = ['stock.picking', 'stock.move', 'stock.quant', 'stock.inventory']
    for modelo in modelos_criticos:
        tiene_reglas = len(reglas_por_modelo.get(modelo, [])) > 0
        estado = "⚠️  Sin filtrado" if not tiene_reglas else "✅ Tiene reglas (revisar)"
        print(f"      {estado} {modelo}")
    
    print("\n   🛠️  OPCIONES DE IMPLEMENTACIÓN:")
    print("\n   Opción 1: REGLAS POR GRUPO DE USUARIOS")
    print("      • Crear un grupo específico para 'Encargados de Sucursales'")
    print("      • Asignar reglas que filtren por ubicación según el grupo")
    print("      • Ventaja: Fácil de mantener, claro en permisos")
    print("      • Desventaja: Requiere crear grupos específicos")
    
    print("\n   Opción 2: REGLAS CON UBICACIÓN EN USUARIO")
    print("      • Agregar un campo 'Ubicación asignada' al usuario (customización)")
    print("      • Crear reglas que filtren usando ese campo")
    print("      • Ventaja: Más flexible para múltiples ubicaciones")
    print("      • Desventaja: Requiere desarrollo custom")
    
    print("\n   Opción 3: REGLAS POR WAREHOUSE DEFAULT")
    print("      • Usar el campo 'warehouse_id' por defecto del usuario")
    print("      • Filtrar por warehouse del usuario")
    print("      • Ventaja: Usa funcionalidad nativa de Odoo")
    print("      • Desventaja: Requiere configurar warehouse por usuario")
    
    print("\n   ✅ RECOMENDACIÓN: OPCIÓN 1 + OPCIÓN 3 (Híbrida)")
    print("      • Crear grupos específicos por sucursal (Belgrano 1, Belgrano 2, etc.)")
    print("      • Crear reglas que filtren por ubicación del warehouse del grupo")
    print("      • Asignar usuarios a sus grupos correspondientes")
    
    print("\n" + "="*80)
    print("📝 PRÓXIMOS PASOS:")
    print("="*80)
    print("1. Crear script para crear grupos de sucursales")
    print("2. Crear reglas de registro por modelo que filtren por ubicación")
    print("3. Asignar usuarios a sus grupos correspondientes")
    print("4. Probar con usuario de Belgrano 1")
    print("="*80)

if __name__ == "__main__":
    main()
