#!/usr/bin/env python3
"""
Script para configurar permisos de inventario por sucursal
Crea grupos de usuarios por sucursal y reglas de registro que filtran por ubicación
Autor: Corolla
Fecha: 2025-01-XX

Opciones útiles:
  --incluir-cen-en-tipos-operacion
      Amplía la regla stock.picking.type: tipos de la sucursal O de Nakel Central (code CEN).
      Efecto: encargados pueden elegir p.ej. "Nakel Central: Traslados internos" en el modal.
      Contra: el resumen de inventario puede mostrar también tarjetas de operaciones de Central.

  --incluir-cen-en-stock
      Amplía stock.quant, stock.move, stock.picking y stock.warehouse.orderpoint: ubicación de la
      sucursal O CEN/Existencias (almacén code CEN → lot_stock_id). Así encargados Belgrano ven
      también el stock y movimientos que involucran Nakel Central, sin ver otras sucursales.

  Regla stock.location (siempre al crear/actualizar reglas por sucursal):
      Limita el selector de ubicaciones (p. ej. traslados internos) al árbol del almacén de la
      sucursal (view_location_id) más CEN/Existencias (lot_stock de CEN). Evita ver B2/B3/B4/Nak.

  Regla pos.config (tablero Punto de venta):
      Filtra por picking_type_id.warehouse_id = almacén de la sucursal (no por pos.config.warehouse_id,
      que en esta instalación apunta a Nakel Central para todas las cajas).

  Si ya aplicaron --incluir-cen-en-tipos-operacion o --incluir-cen-en-stock en la base, deben volver
  a pasar esos flags en cada ejecución; si no, las reglas correspondientes vuelven a "solo sucursal".
  --solo-sucursal "Belgrano 1"
      Solo actualiza reglas/usuarios de esa sucursal (piloto).
  Combinación piloto en master_dev:
      python3 configurar_permisos_inventario_por_sucursal_master18.py --master-dev \\
          --incluir-cen-en-tipos-operacion --solo-sucursal "Belgrano 1" --dry-run

  --master-test
      Usa dev.nakel.net.ar y base master_test (credenciales en nakel/.env → ODOO_MASTER_DEV_*).
      Misma URL/prefijo que los scripts de análisis XML-RPC; el DB en .env suele ser master_test.
"""

import sys
import os
import copy
import xmlrpc.client
import argparse

sys.path.insert(0, '/media/klap/raid5/cursor_files')

try:
    from config_nakel import (
        ODOO_CONFIG_MASTER18,
        ODOO_CONFIG_MASTER_DEV,
        ODOO_CONFIG_DEV_MASTER_TEST,
    )
except ImportError:
    print("❌ Error: No se pudo importar config_nakel.py")
    sys.exit(1)


def _get_odoo_config(master_dev=False, master_test=False):
    if master_test:
        cfg = ODOO_CONFIG_DEV_MASTER_TEST
    elif master_dev:
        cfg = ODOO_CONFIG_MASTER_DEV
    else:
        cfg = ODOO_CONFIG_MASTER18
    return {
        'url': cfg['url'],
        'db': cfg['db'],
        'user': cfg['username'],
        'pass': cfg['password'],
    }


# Por defecto master_18; main() puede sobrescribir con --master-dev / --master-test
ODOO_CONFIG = _get_odoo_config()

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
        # Incluir picking_type_id.warehouse_id para permitir crear desde PDV (el picking se crea con tipo de operación antes de rellenar locations)
        'domain_template': [
            '|', '|',
            ('location_id', 'child_of', '{location_id}'),
            ('location_dest_id', 'child_of', '{location_id}'),
            ('picking_type_id.warehouse_id', '=', '{warehouse_id}')
        ]
    },
    'stock.move': {
        'name_template': 'Encargados {sucursal}: Ver solo movimientos de {sucursal}',
        # Incluir picking_id.picking_type_id.warehouse_id para permitir crear movimientos desde PDV (ej. Control calidad > Customers) que pertenecen a un picking de la sucursal
        'domain_template': [
            '|', '|',
            ('location_id', 'child_of', '{location_id}'),
            ('location_dest_id', 'child_of', '{location_id}'),
            ('picking_id.picking_type_id.warehouse_id', '=', '{warehouse_id}')
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
        # Por defecto: solo sucursal (resumen de inventario sin tarjetas de Central).
        # Con --incluir-cen-en-tipos-operacion: OR con almacén CEN (ver "Nakel Central: Traslados internos", etc.).
        'domain_template': [
            ('warehouse_id', '=', '{warehouse_id}')
        ]
    },
    'stock.warehouse.orderpoint': {
        'name_template': 'Encargados {sucursal}: Ver solo reglas de reabastecimiento de {sucursal}',
        # Reglas de reabastecimiento (máx/mín): cada encargado ve solo las de su ubicación
        'domain_template': [
            ('location_id', 'child_of', '{location_id}')
        ]
    },
    # PDV: pos.config.warehouse_id suele ser CEN en Nakel; la sucursal real del POS va en picking_type_id.warehouse_id
    'pos.config': {
        'name_template': 'Encargados {sucursal}: Ver solo cajas PDV de {sucursal}',
        'domain_template': [
            ('picking_type_id.warehouse_id', '=', '{warehouse_id}')
        ]
    },
}

def conectar_odoo():
    """Conecta a Odoo (usa ODOO_CONFIG fijado en main)"""
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

def obtener_warehouse_por_codigo(models, uid, password, code, extra_fields=None):
    """Busca un warehouse por su código."""
    fields = ['id', 'name', 'code']
    if extra_fields:
        for f in extra_fields:
            if f not in fields:
                fields.append(f)
    try:
        warehouses = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'stock.warehouse', 'search_read',
            [[('code', '=', code)]],
            {'fields': fields}
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
        
        # Permisos de operación: la regla aplica a leer/escribir/crear/eliminar
        # Si no están en True, el encargado no puede crear traslados al facturar (stock.picking)
        permisos_regla = {
            'perm_read': True,
            'perm_write': True,
            'perm_create': True,
            'perm_unlink': True,
        }
        if reglas_existentes:
            # Actualizar regla existente
            models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'ir.rule', 'write',
                [reglas_existentes, {
                    'domain_force': str(dominio),
                    'groups': [(6, 0, [grupo_id])],
                    'active': True,
                    **permisos_regla
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
                'active': True,
                **permisos_regla
            }]
        )
        print(f"         ✅ Regla creada: {nombre} (ID: {regla_id})")
        return regla_id
        
    except Exception as e:
        print(f"         ❌ Error creando regla {nombre}: {e}")
        import traceback
        traceback.print_exc()
        return None

def asignar_grupo_a_usuarios(models, uid, password, grupo_id, logins_usuarios, warehouse_id=None, dry_run=False):
    """Asigna un grupo a una lista de usuarios y fija property_warehouse_id según la sucursal (almacén por defecto en ventas)."""
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
            print(f"         [DRY-RUN] Asignaría grupo a {len(usuarios_ids)} usuario(s)" + (f" y property_warehouse_id={warehouse_id}" if warehouse_id else ""))
            return True
        
        # Asignar grupo y almacén por defecto a usuarios
        for user_id in usuarios_ids:
            usuario = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'res.users', 'read',
                [[user_id]],
                {'fields': ['groups_id']}
            )
            grupos_actuales = list(usuario[0].get('groups_id', []))
            had_group = grupo_id in grupos_actuales
            vals = {}
            if not had_group:
                grupos_actuales.append(grupo_id)
                vals['groups_id'] = [(6, 0, grupos_actuales)]
            if warehouse_id is not None:
                vals['property_warehouse_id'] = warehouse_id
            if vals:
                models.execute_kw(
                    ODOO_CONFIG['db'], uid, password,
                    'res.users', 'write',
                    [[user_id], vals]
                )
            user_info = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'res.users', 'read',
                [[user_id]],
                {'fields': ['name', 'login']}
            )
            if not had_group:
                print(f"         ✅ Grupo asignado a: {user_info[0].get('name')} ({user_info[0].get('login')})")
            else:
                print(f"         ℹ️  Usuario ya tenía el grupo: {user_info[0].get('name')}")
            if warehouse_id is not None:
                print(f"         ✅ Almacén por defecto (property_warehouse_id) = {warehouse_id}")
        
        return True
        
    except Exception as e:
        print(f"         ❌ Error asignando grupo a usuarios: {e}")
        import traceback
        traceback.print_exc()
        return False

def _reglas_efectivas(
    incluir_cen_tipos_operacion,
    cen_warehouse_id,
    incluir_cen_stock=False,
    cen_location_id=None,
):
    """Copia de REGLAS_POR_MODELO; opcionalmente CEN en tipos de operación y/o en stock/movimientos."""
    reglas = copy.deepcopy(REGLAS_POR_MODELO)
    if incluir_cen_tipos_operacion and cen_warehouse_id is not None:
        reglas['stock.picking.type'] = {
            'name_template': REGLAS_POR_MODELO['stock.picking.type']['name_template'],
            'domain_template': [
                '|',
                ('warehouse_id', '=', '{warehouse_id}'),
                ('warehouse_id', '=', '{cen_warehouse_id}'),
            ],
        }
    if incluir_cen_stock and cen_location_id is not None:
        # Mismo name_template que REGLAS_POR_MODELO para que ir.rule existente se actualice (no duplicar).
        # 5 vías OR: origen/dest sucursal, origen/dest CEN, o tipo de operación de la sucursal (PDV)
        reglas['stock.picking'] = {
            'name_template': REGLAS_POR_MODELO['stock.picking']['name_template'],
            'domain_template': [
                '|', '|', '|', '|',
                ('location_id', 'child_of', '{location_id}'),
                ('location_dest_id', 'child_of', '{location_id}'),
                ('location_id', 'child_of', '{cen_location_id}'),
                ('location_dest_id', 'child_of', '{cen_location_id}'),
                ('picking_type_id.warehouse_id', '=', '{warehouse_id}'),
            ],
        }
        reglas['stock.move'] = {
            'name_template': REGLAS_POR_MODELO['stock.move']['name_template'],
            'domain_template': [
                '|', '|', '|', '|',
                ('location_id', 'child_of', '{location_id}'),
                ('location_dest_id', 'child_of', '{location_id}'),
                ('location_id', 'child_of', '{cen_location_id}'),
                ('location_dest_id', 'child_of', '{cen_location_id}'),
                ('picking_id.picking_type_id.warehouse_id', '=', '{warehouse_id}'),
            ],
        }
        reglas['stock.quant'] = {
            'name_template': REGLAS_POR_MODELO['stock.quant']['name_template'],
            'domain_template': [
                '|',
                ('location_id', 'child_of', '{location_id}'),
                ('location_id', 'child_of', '{cen_location_id}'),
            ],
        }
        reglas['stock.warehouse.orderpoint'] = {
            'name_template': REGLAS_POR_MODELO['stock.warehouse.orderpoint']['name_template'],
            'domain_template': [
                '|',
                ('location_id', 'child_of', '{location_id}'),
                ('location_id', 'child_of', '{cen_location_id}'),
            ],
        }
    return reglas


def procesar_sucursal(
    models, uid, password, sucursal_nombre, config, categoria_id,
    dry_run=False,
    incluir_cen_tipos_operacion=False,
    cen_warehouse_id=None,
    incluir_cen_stock=False,
    cen_location_id=None,
):
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
    
    # Obtener warehouse (view_location_id = árbol completo B1/B2… para reglas stock.location)
    print(f"\n🏭 Obteniendo warehouse...")
    warehouse = obtener_warehouse_por_codigo(
        models, uid, password, config['warehouse_code'], extra_fields=['view_location_id']
    )
    if not warehouse:
        print(f"   ❌ No se pudo encontrar el warehouse: {config['warehouse_code']}")
        return False
    
    warehouse_id = warehouse['id']
    wv = warehouse.get('view_location_id')
    warehouse_view_location_id = wv[0] if isinstance(wv, (list, tuple)) else wv
    if not warehouse_view_location_id:
        print(f"   ❌ El warehouse no tiene view_location_id.")
        return False
    print(f"   ✅ Warehouse encontrado: {warehouse.get('name')} (ID: {warehouse_id}, view_location_id={warehouse_view_location_id})")

    # CEN/Existencias para regla stock.location (y ya pasada desde main si --incluir-cen-en-stock)
    cen_loc_para_ubicaciones = cen_location_id
    if not cen_loc_para_ubicaciones:
        cen_wh_loc = obtener_warehouse_por_codigo(
            models, uid, password, 'CEN', extra_fields=['lot_stock_id']
        )
        if cen_wh_loc and cen_wh_loc.get('lot_stock_id'):
            ls = cen_wh_loc['lot_stock_id']
            cen_loc_para_ubicaciones = ls[0] if isinstance(ls, (list, tuple)) else ls
    
    # Crear grupo
    nombre_grupo = f"Encargados {sucursal_nombre}"
    print(f"\n👥 Creando/obteniendo grupo...")
    grupo_id = crear_o_obtener_grupo(models, uid, password, nombre_grupo, categoria_id)
    if not grupo_id:
        return False
    
    # Crear reglas de registro
    print(f"\n📋 Creando reglas de registro...")
    if incluir_cen_tipos_operacion and cen_warehouse_id is not None:
        print(f"   ℹ️  stock.picking.type: dominio sucursal OR warehouse CEN (id={cen_warehouse_id})")
    if incluir_cen_stock and cen_location_id is not None:
        print(f"   ℹ️  stock (quant/move/picking/orderpoint): sucursal OR CEN/Existencias (location_id={cen_location_id})")
    reglas_loop = _reglas_efectivas(
        incluir_cen_tipos_operacion,
        cen_warehouse_id,
        incluir_cen_stock=incluir_cen_stock,
        cen_location_id=cen_location_id,
    )
    # stock.location: restringe listas "Ubicación origen/destino" (p. ej. traslados internos)
    nombre_loc = 'Encargados {sucursal}: Ver ubicaciones de sucursal y CEN/Existencias'
    if cen_loc_para_ubicaciones:
        reglas_loop['stock.location'] = {
            'name_template': nombre_loc,
            'domain_template': [
                '|',
                ('id', 'child_of', '{warehouse_view_location_id}'),
                ('id', 'child_of', '{cen_location_id}'),
            ],
        }
        print(f"   ℹ️  stock.location: child_of sucursal view={warehouse_view_location_id} OR CEN Existencias={cen_loc_para_ubicaciones}")
    else:
        reglas_loop['stock.location'] = {
            'name_template': nombre_loc,
            'domain_template': [
                ('id', 'child_of', '{warehouse_view_location_id}'),
            ],
        }
        print(f"   ⚠️  stock.location: solo sucursal (view={warehouse_view_location_id}); sin CEN (no hay lot_stock CEN).")

    for modelo, regla_config in reglas_loop.items():
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
                elif valor == '{cen_warehouse_id}':
                    valor = cen_warehouse_id
                elif valor == '{cen_location_id}':
                    valor = cen_loc_para_ubicaciones if modelo == 'stock.location' else cen_location_id
                elif valor == '{warehouse_view_location_id}':
                    valor = warehouse_view_location_id
                dominio.append((campo, operador, valor))
            else:
                # Otros tipos (listas anidadas, etc.)
                dominio.append(item)
        
        crear_regla_registro(
            models, uid, password,
            modelo, nombre_regla, dominio, grupo_id, dry_run
        )
    
    # Asignar grupo y almacén por defecto a usuarios
    print(f"\n👤 Asignando grupo y almacén por defecto a usuarios...")
    asignar_grupo_a_usuarios(
        models, uid, password,
        grupo_id, config['usuarios'], warehouse_id=warehouse_id, dry_run=dry_run
    )
    
    return True

def main():
    global ODOO_CONFIG
    parser = argparse.ArgumentParser(description='Configurar permisos de inventario por sucursal')
    parser.add_argument('--dry-run', action='store_true', help='Ejecutar en modo dry-run (sin hacer cambios)')
    amb = parser.add_mutually_exclusive_group()
    amb.add_argument(
        '--master-dev',
        action='store_true',
        help='Usar base productiva master_dev (nakel.net.ar) en lugar de master_18',
    )
    amb.add_argument(
        '--master-test',
        action='store_true',
        help='Usar dev.nakel.net.ar + master_test (ODOO_MASTER_DEV_* en nakel/.env)',
    )
    parser.add_argument(
        '--incluir-cen-en-tipos-operacion',
        action='store_true',
        help='Regla stock.picking.type: sucursal OR almacén CEN (tipos de operación de Nakel Central visibles)',
    )
    parser.add_argument(
        '--solo-sucursal',
        metavar='NOMBRE',
        default=None,
        help='Solo procesar una sucursal, ej. "Belgrano 1"',
    )
    parser.add_argument(
        '--incluir-cen-en-stock',
        action='store_true',
        help='Reglas stock.quant / stock.move / stock.picking / orderpoint: sucursal OR CEN/Existencias',
    )
    args = parser.parse_args()

    ODOO_CONFIG = _get_odoo_config(master_dev=args.master_dev, master_test=args.master_test)
    
    modo = "DRY-RUN" if args.dry_run else "REAL"
    
    print("="*80)
    print("🔧 CONFIGURACIÓN DE PERMISOS DE INVENTARIO POR SUCURSAL")
    print("="*80)
    print(f"📊 Base de datos: {ODOO_CONFIG['db']}")
    print(f"🔍 Modo: {modo}")
    if args.incluir_cen_en_tipos_operacion:
        print("📌 Tipos de operación: sucursal + Nakel Central (CEN)")
    if args.incluir_cen_en_stock:
        print("📌 Stock y movimientos: sucursal + CEN/Existencias (ubicación lot_stock de almacén CEN)")
    if args.solo_sucursal:
        print(f"📌 Solo sucursal: {args.solo_sucursal!r}")
    if args.master_test:
        print("📌 Host: dev (master_test)")
    elif args.master_dev:
        print("📌 Host: producción master_dev")
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

    cen_warehouse_id = None
    cen_location_id = None
    if args.incluir_cen_en_tipos_operacion or args.incluir_cen_en_stock:
        cen_wh = obtener_warehouse_por_codigo(
            models, uid, password, 'CEN', extra_fields=['lot_stock_id']
        )
        if not cen_wh:
            print("\n   ❌ No se encontró almacén con code='CEN'.")
            return
        cen_warehouse_id = cen_wh['id']
        lot = cen_wh.get('lot_stock_id')
        if isinstance(lot, (list, tuple)):
            cen_location_id = lot[0]
        else:
            cen_location_id = lot
        print(f"\n🏭 Nakel Central: {cen_wh.get('name')} (warehouse_id={cen_warehouse_id}, code=CEN)")
        if args.incluir_cen_en_stock:
            if not cen_location_id:
                print("   ❌ El almacén CEN no tiene lot_stock_id. No se puede usar --incluir-cen-en-stock.")
                return
            print(f"   📍 CEN/Existencias (lot_stock_id) para reglas de stock: location_id={cen_location_id}")
        if args.incluir_cen_en_tipos_operacion:
            print(f"   ℹ️  Regla stock.picking.type usará warehouse CEN id={cen_warehouse_id}")

    sucursales_iter = list(SUCURSALES_CONFIG.items())
    if args.solo_sucursal:
        sk = args.solo_sucursal.strip()
        if sk not in SUCURSALES_CONFIG:
            print(f"\n❌ Sucursal desconocida: {sk!r}. Valores: {list(SUCURSALES_CONFIG.keys())}")
            return
        sucursales_iter = [(sk, SUCURSALES_CONFIG[sk])]
    
    # Procesar cada sucursal
    resultados = {}
    for sucursal_nombre, config in sucursales_iter:
        resultado = procesar_sucursal(
            models, uid, password,
            sucursal_nombre, config, categoria_id,
            dry_run=args.dry_run,
            incluir_cen_tipos_operacion=args.incluir_cen_en_tipos_operacion,
            cen_warehouse_id=cen_warehouse_id,
            incluir_cen_stock=args.incluir_cen_en_stock,
            cen_location_id=cen_location_id,
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
