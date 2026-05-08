#!/usr/bin/env python3
"""
Script para sincronizar embalajes desde MSSQL GESTION a Odoo master_dev
- Usa código interno normalizado para matching mejorado
- Obtiene UNID_BULTO desde MSSQL (unidades por bulto)
- Crea o actualiza embalajes en Odoo master_dev
- Maneja productos con y sin embalajes existentes
Autor: Corolla
Fecha: 2025-12-27
"""

import os
import sys
import xmlrpc.client
from datetime import datetime
import argparse

# Agregar ruta del proyecto
sys.path.insert(0, '/media/klap/raid5/cursor_files')

try:
    from config_nakel import ODOO_CONFIG_MASTER_DEV, MSSQL_CONFIG
except ImportError:
    print("❌ Error: No se pudo importar config_nakel.py")
    sys.exit(1)

try:
    import pyodbc
except ImportError:
    print("❌ Error: pyodbc no está instalado")
    sys.exit(1)

# Configuración Odoo - MASTER_DEV
ODOO_CONFIG = {
    'url': ODOO_CONFIG_MASTER_DEV['url'],
    'db': ODOO_CONFIG_MASTER_DEV['db'],
    'user': ODOO_CONFIG_MASTER_DEV['username'],
    'pass': ODOO_CONFIG_MASTER_DEV['password']
}

def normalizar_codigo_interno(codigo):
    """Normaliza código interno: reemplaza coma por punto"""
    if not codigo:
        return ''
    return str(codigo).replace(',', '.').strip()

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

def conectar_mssql():
    """Conecta a la base de datos MSSQL"""
    try:
        connection_string = (
            f"DRIVER={{ODBC Driver 18 for SQL Server}};"
            f"SERVER={MSSQL_CONFIG['server']};"
            f"DATABASE={MSSQL_CONFIG['database']};"
            f"UID={MSSQL_CONFIG['username']};"
            f"PWD={MSSQL_CONFIG['password']};"
            f"TrustServerCertificate=yes;"
        )
        
        conn = pyodbc.connect(connection_string)
        print("✅ Conexión exitosa a MSSQL")
        return conn
    except Exception as e:
        print(f"❌ Error conectando a MSSQL: {e}")
        return None

def obtener_embalajes_mssql(conn):
    """Obtiene información de embalajes desde MSSQL
    Retorna: {codigo_normalizado: {'unid_bulto': X, 'ctd_unidades': Y, 'unidad_medida': '...'}}
    """
    if not conn:
        return {}
    
    try:
        cursor = conn.cursor()
        
        query = """
        SELECT 
            COD_ARTICULO,
            DESCRIPCION,
            UNID_BULTO,
            CTD_UNIDADES,
            UNIDAD_MEDIDA
        FROM ARTICULOS
        WHERE COD_ARTICULO IS NOT NULL
        AND COD_ARTICULO != ''
        AND (UNID_BULTO IS NOT NULL AND UNID_BULTO > 1)
        AND (VENTA_SUSPENDIDA IS NULL OR VENTA_SUSPENDIDA != 'S')
        """
        
        cursor.execute(query)
        embalajes_mssql = {}
        
        for row in cursor.fetchall():
            cod_articulo = row[0].strip() if row[0] else None
            unid_bulto = int(row[2]) if row[2] else None
            ctd_unidades = int(row[3]) if row[3] else None
            unidad_medida = row[4].strip() if row[4] else None
            
            if cod_articulo and unid_bulto:
                codigo_normalizado = normalizar_codigo_interno(cod_articulo)
                embalajes_mssql[codigo_normalizado] = {
                    'codigo': cod_articulo,
                    'descripcion': row[1].strip() if row[1] else '',
                    'unid_bulto': unid_bulto,
                    'ctd_unidades': ctd_unidades,
                    'unidad_medida': unidad_medida
                }
        
        return embalajes_mssql
        
    except Exception as e:
        print(f"❌ Error obteniendo embalajes de MSSQL: {e}")
        import traceback
        traceback.print_exc()
        return {}

def obtener_productos_odoo_con_embalajes(models, uid, password):
    """Obtiene productos de Odoo con información de sus embalajes actuales"""
    print("\n📦 Obteniendo productos de Odoo master_dev...")
    
    try:
        productos = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'product.template', 'search_read',
            [[('active', '=', True)]],
            {'fields': ['id', 'name', 'default_code', 'packaging_ids']}
        )
        
        print(f"✅ {len(productos)} productos encontrados")
        
        # Obtener detalles de embalajes para productos que los tienen
        productos_con_info = {}
        
        for producto in productos:
            codigo_interno = producto.get('default_code')
            if not codigo_interno:
                continue
            
            codigo_normalizado = normalizar_codigo_interno(codigo_interno)
            
            embalajes_actuales = []
            packaging_ids = producto.get('packaging_ids', [])
            
            if packaging_ids:
                try:
                    packagings = models.execute_kw(
                        ODOO_CONFIG['db'], uid, password,
                        'product.packaging', 'read',
                        [packaging_ids],
                        {'fields': ['id', 'name', 'qty', 'product_uom_id']}
                    )
                    
                    for pack in packagings:
                        embalajes_actuales.append({
                            'id': pack['id'],
                            'name': pack.get('name', ''),
                            'qty': pack.get('qty', 1.0)
                        })
                except Exception as e:
                    print(f"   ⚠️  Error obteniendo embalajes para producto {producto['id']}: {e}")
            
            productos_con_info[codigo_normalizado] = {
                'id': producto['id'],
                'name': producto['name'],
                'codigo': codigo_interno,
                'embalajes': embalajes_actuales
            }
        
        productos_con_embalajes = sum(1 for p in productos_con_info.values() if p['embalajes'])
        print(f"   • Con embalajes: {productos_con_embalajes}")
        print(f"   • Sin embalajes: {len(productos_con_info) - productos_con_embalajes}")
        
        return productos_con_info
        
    except Exception as e:
        print(f"❌ Error obteniendo productos de Odoo: {e}")
        import traceback
        traceback.print_exc()
        return {}

def crear_embalaje_odoo(models, uid, password, producto_id, unid_bulto, unidad_medida=None):
    """Crea un embalaje en Odoo para un producto"""
    try:
        # Nombre del embalaje
        nombre_embalaje = f"Bulto x{unid_bulto}"
        if unidad_medida:
            nombre_embalaje += f" ({unidad_medida})"
        
        datos_embalaje = {
            'name': nombre_embalaje,
            'product_id': producto_id,
            'qty': float(unid_bulto),
            'sequence': 1
        }
        
        embalaje_id = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'product.packaging', 'create',
            [datos_embalaje]
        )
        
        return embalaje_id
        
    except Exception as e:
        print(f"   ❌ Error creando embalaje: {e}")
        return None

def actualizar_embalaje_odoo(models, uid, password, embalaje_id, unid_bulto, unidad_medida=None):
    """Actualiza un embalaje existente en Odoo"""
    try:
        nombre_embalaje = f"Bulto x{unid_bulto}"
        if unidad_medida:
            nombre_embalaje += f" ({unidad_medida})"
        
        datos_actualizacion = {
            'name': nombre_embalaje,
            'qty': float(unid_bulto)
        }
        
        models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'product.packaging', 'write',
            [[embalaje_id], datos_actualizacion]
        )
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error actualizando embalaje: {e}")
        return False

def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description='Sincronizar embalajes desde MSSQL a master_dev')
    parser.add_argument('--dry-run', action='store_true', help='Modo dry-run (no realiza cambios)')
    parser.add_argument('--solo-faltantes', action='store_true', help='Solo crear embalajes faltantes (no actualizar existentes)')
    parser.add_argument('--batch-size', type=int, default=100, help='Tamaño del lote para mostrar progreso (default: 100)')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("📦 SINCRONIZACIÓN DE EMBALAJES DESDE MSSQL A MASTER_DEV")
    print("=" * 80)
    print(f"📊 Base de datos: master_dev")
    print(f"🔍 Modo: {'DRY-RUN' if args.dry_run else 'REAL'}")
    if args.solo_faltantes:
        print(f"⚠️  Solo creando embalajes faltantes (no actualizando existentes)")
    else:
        print(f"⚠️  Creando embalajes faltantes y actualizando existentes")
    print("=" * 80)
    
    # Conectar a Odoo
    models, uid = conectar_odoo()
    if not models or not uid:
        print("\n❌ No se pudo conectar a Odoo")
        return
    
    password = ODOO_CONFIG['pass']
    
    # Conectar a MSSQL
    print("\n🔌 Conectando a MSSQL...")
    conn_mssql = conectar_mssql()
    if not conn_mssql:
        print("\n❌ No se pudo conectar a MSSQL")
        return
    
    # Obtener embalajes desde MSSQL
    print("\n📋 Obteniendo embalajes desde MSSQL...")
    embalajes_mssql = obtener_embalajes_mssql(conn_mssql)
    print(f"✅ {len(embalajes_mssql)} productos con embalajes encontrados en MSSQL")
    
    if conn_mssql:
        conn_mssql.close()
    
    if not embalajes_mssql:
        print("\n⚠️  No se obtuvieron embalajes desde MSSQL")
        return
    
    # Obtener productos de Odoo
    productos_odoo = obtener_productos_odoo_con_embalajes(models, uid, password)
    
    if not productos_odoo:
        print("\n❌ No se encontraron productos en Odoo")
        return
    
    # Procesar productos
    print(f"\n📋 Procesando productos...")
    
    embalajes_creados = 0
    embalajes_actualizados = 0
    productos_sin_codigo = 0
    productos_no_encontrados = 0
    productos_ya_correctos = 0
    errores = 0
    
    productos_procesados = 0
    
    for codigo_norm, datos_mssql in embalajes_mssql.items():
        productos_procesados += 1
        
        if codigo_norm not in productos_odoo:
            productos_no_encontrados += 1
            continue
        
        producto_odoo = productos_odoo[codigo_norm]
        producto_id = producto_odoo['id']
        nombre_producto = producto_odoo['name']
        unid_bulto_mssql = datos_mssql['unid_bulto']
        unidad_medida = datos_mssql.get('unidad_medida')
        
        embalajes_actuales = producto_odoo['embalajes']
        
        # Verificar si necesita crear o actualizar
        necesita_crear = len(embalajes_actuales) == 0
        necesita_actualizar = False
        
        if embalajes_actuales:
            # Verificar si el primer embalaje tiene la cantidad correcta
            primer_embalaje = embalajes_actuales[0]
            if abs(primer_embalaje['qty'] - unid_bulto_mssql) > 0.01:
                necesita_actualizar = True
        
        if necesita_crear:
            embalajes_creados += 1
            
            # Mostrar progreso
            if embalajes_creados % args.batch_size == 0 or embalajes_creados <= 10:
                print(f"   🔄 [{embalajes_creados}] Creando embalaje: {nombre_producto[:50]}... (Bulto x{unid_bulto_mssql})")
            
            # Crear embalaje
            if not args.dry_run:
                embalaje_id = crear_embalaje_odoo(models, uid, password, producto_id, unid_bulto_mssql, unidad_medida)
                if not embalaje_id:
                    errores += 1
                    embalajes_creados -= 1
        
        elif necesita_actualizar and not args.solo_faltantes:
            embalajes_actualizados += 1
            
            # Mostrar progreso
            if embalajes_actualizados % args.batch_size == 0 or embalajes_actualizados <= 10:
                print(f"   🔄 [{embalajes_actualizados}] Actualizando embalaje: {nombre_producto[:50]}... ({primer_embalaje['qty']} -> {unid_bulto_mssql})")
            
            # Actualizar embalaje
            if not args.dry_run:
                if not actualizar_embalaje_odoo(models, uid, password, primer_embalaje['id'], unid_bulto_mssql, unidad_medida):
                    errores += 1
                    embalajes_actualizados -= 1
        
        else:
            productos_ya_correctos += 1
        
        # Mostrar progreso general cada 1000 productos
        if productos_procesados % 1000 == 0:
            print(f"   📊 Procesados {productos_procesados}/{len(embalajes_mssql)} productos desde MSSQL...")
    
    # Resumen final
    print("\n" + "=" * 80)
    print("📊 RESUMEN")
    print("=" * 80)
    print(f"✅ Embalajes creados: {embalajes_creados}")
    print(f"🔄 Embalajes actualizados: {embalajes_actualizados}")
    print(f"✓  Productos ya correctos: {productos_ya_correctos}")
    print(f"❌ Productos sin código interno en Odoo: {productos_sin_codigo}")
    print(f"⚠️  Productos no encontrados en Odoo: {productos_no_encontrados}")
    print(f"❌ Errores: {errores}")
    print(f"📦 Total productos procesados desde MSSQL: {len(embalajes_mssql)}")
    
    if args.dry_run:
        print(f"\n💡 Ejecuta sin --dry-run para aplicar los cambios")
    else:
        print(f"\n✅ Proceso completado")
        print(f"\n📋 Embalajes sincronizados desde MSSQL GESTION usando código interno normalizado")

if __name__ == "__main__":
    main()

