#!/usr/bin/env python3
"""
Script para actualizar códigos de barras faltantes o erróneos en master_dev
usando los datos desde MSSQL GESTION
- Obtiene códigos de barras desde MSSQL por código interno
- Compara con productos en Odoo master_dev
- Actualiza códigos de barras faltantes o diferentes
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
    print("❌ Error: pyodbc no está instalado. Instálalo con: pip3 install pyodbc")
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
        return conn
    except Exception as e:
        print(f"❌ Error conectando a MSSQL: {e}")
        return None

def obtener_barcodes_mssql_por_codigo(conn):
    """Obtiene un diccionario de códigos de barras desde MSSQL indexado por código interno normalizado
    Retorna: {codigo_normalizado: barcode}
    """
    if not conn:
        return {}
    
    try:
        cursor = conn.cursor()
        
        query = """
        SELECT 
            a.COD_ARTICULO,
            ap.PLU
        FROM ARTICULOS a
        INNER JOIN ARTICULOPLU ap ON a.ID_ARTICULO = ap.ID_ARTICULO
        WHERE ap.PLU IS NOT NULL
        AND ap.PLU != ''
        AND ap.PLU != '0'
        AND LEN(ap.PLU) >= 8
        AND a.COD_ARTICULO IS NOT NULL
        """
        
        cursor.execute(query)
        barcodes_por_codigo = {}
        
        for row in cursor.fetchall():
            cod_articulo = row[0].strip() if row[0] else None
            plu = row[1].strip() if row[1] else None
            
            if cod_articulo and plu:
                codigo_normalizado = normalizar_codigo_interno(cod_articulo)
                # Si hay múltiples PLU para el mismo código, mantener el primero
                if codigo_normalizado not in barcodes_por_codigo:
                    barcodes_por_codigo[codigo_normalizado] = plu
        
        return barcodes_por_codigo
        
    except Exception as e:
        print(f"❌ Error obteniendo códigos de barras de MSSQL: {e}")
        import traceback
        traceback.print_exc()
        return {}

def obtener_productos_odoo_sin_barcode_o_actualizar(models, uid, password):
    """Obtiene productos de Odoo que no tienen código de barras o que podrían necesitar actualización"""
    print("\n📦 Obteniendo productos de Odoo master_dev...")
    
    try:
        productos = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'product.template', 'search_read',
            [[('active', '=', True)]],
            {'fields': ['id', 'name', 'barcode', 'default_code']}
        )
        
        print(f"✅ {len(productos)} productos encontrados")
        
        productos_sin_barcode = sum(1 for p in productos if not p.get('barcode'))
        productos_con_codigo = sum(1 for p in productos if p.get('default_code'))
        
        print(f"   • Sin código de barras: {productos_sin_barcode}")
        print(f"   • Con código interno: {productos_con_codigo}")
        
        return productos
        
    except Exception as e:
        print(f"❌ Error obteniendo productos de Odoo: {e}")
        import traceback
        traceback.print_exc()
        return []


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description='Actualizar códigos de barras desde MSSQL en master_dev')
    parser.add_argument('--dry-run', action='store_true', help='Modo dry-run (no realiza cambios)')
    parser.add_argument('--solo-faltantes', action='store_true', help='Solo actualizar productos sin código de barras (no actualizar existentes)')
    parser.add_argument('--batch-size', type=int, default=100, help='Tamaño del lote para mostrar progreso (default: 100)')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("🔧 ACTUALIZACIÓN DE CÓDIGOS DE BARRAS DESDE MSSQL")
    print("=" * 80)
    print(f"📊 Base de datos: master_dev")
    print(f"🔍 Modo: {'DRY-RUN' if args.dry_run else 'REAL'}")
    if args.solo_faltantes:
        print(f"⚠️  Solo actualizando productos SIN código de barras")
    else:
        print(f"⚠️  Actualizando productos SIN código de barras y CORRIGIENDO los diferentes")
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
    
    # Obtener códigos de barras desde MSSQL
    print("\n📋 Obteniendo códigos de barras desde MSSQL...")
    barcodes_mssql = obtener_barcodes_mssql_por_codigo(conn_mssql)
    print(f"✅ {len(barcodes_mssql)} códigos de barras obtenidos desde MSSQL")
    
    if conn_mssql:
        conn_mssql.close()
    
    if not barcodes_mssql:
        print("\n⚠️  No se obtuvieron códigos de barras desde MSSQL")
        return
    
    # Obtener productos de Odoo
    productos_odoo = obtener_productos_odoo_sin_barcode_o_actualizar(models, uid, password)
    
    if not productos_odoo:
        print("\n❌ No se encontraron productos en Odoo")
        return
    
    # Procesar productos
    print(f"\n📋 Procesando {len(productos_odoo)} productos...")
    
    productos_actualizados = 0
    productos_sin_codigo = 0
    productos_diferentes = 0
    productos_no_encontrados = 0
    errores = 0
    
    for i, producto in enumerate(productos_odoo, 1):
        producto_id = producto['id']
        nombre = producto.get('name', 'Sin nombre')
        codigo_interno = producto.get('default_code')
        barcode_actual = producto.get('barcode')
        
        if not codigo_interno:
            productos_sin_codigo += 1
            continue
        
        # Normalizar código interno
        codigo_normalizado = normalizar_codigo_interno(codigo_interno)
        
        # Buscar barcode en MSSQL
        barcode_mssql = barcodes_mssql.get(codigo_normalizado)
        
        if not barcode_mssql:
            productos_no_encontrados += 1
            continue
        
        # Verificar si necesita actualización
        necesita_actualizacion = False
        razon = ""
        
        if not barcode_actual:
            # Producto sin código de barras
            necesita_actualizacion = True
            razon = "sin barcode"
            productos_actualizados += 1
        elif barcode_actual != barcode_mssql:
            # Código de barras diferente
            if not args.solo_faltantes:
                necesita_actualizacion = True
                razon = f"diferente ({barcode_actual} -> {barcode_mssql})"
                productos_diferentes += 1
                productos_actualizados += 1
        else:
            # Ya está correcto
            continue
        
        if necesita_actualizacion:
            # Mostrar progreso cada batch_size
            if productos_actualizados % args.batch_size == 0 or productos_actualizados <= 10:
                print(f"   🔄 [{productos_actualizados}] {nombre[:50]}... ({razon})")
            
            # Actualizar en Odoo
            if not args.dry_run:
                try:
                    models.execute_kw(
                        ODOO_CONFIG['db'], uid, password,
                        'product.template', 'write',
                        [[producto_id], {'barcode': barcode_mssql}]
                    )
                except Exception as e:
                    print(f"   ❌ Error actualizando producto '{nombre[:50]}': {e}")
                    errores += 1
                    productos_actualizados -= 1
        
        # Mostrar progreso general cada 1000 productos
        if i % 1000 == 0:
            print(f"   📊 Procesados {i}/{len(productos_odoo)} productos...")
    
    # Resumen final
    print("\n" + "=" * 80)
    print("📊 RESUMEN")
    print("=" * 80)
    print(f"✅ Productos actualizados: {productos_actualizados}")
    if productos_diferentes > 0 and not args.solo_faltantes:
        print(f"   • Sin código de barras: {productos_actualizados - productos_diferentes}")
        print(f"   • Códigos corregidos: {productos_diferentes}")
    print(f"❌ Productos sin código interno: {productos_sin_codigo}")
    print(f"⚠️  Productos no encontrados en MSSQL: {productos_no_encontrados}")
    print(f"❌ Errores: {errores}")
    print(f"📦 Total productos procesados: {len(productos_odoo)}")
    
    if args.dry_run:
        print(f"\n💡 Ejecuta sin --dry-run para aplicar los cambios")
    else:
        print(f"\n✅ Proceso completado")
        print(f"\n📋 Códigos de barras actualizados desde MSSQL GESTION")

if __name__ == "__main__":
    main()

