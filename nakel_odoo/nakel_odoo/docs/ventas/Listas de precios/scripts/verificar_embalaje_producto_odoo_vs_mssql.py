#!/usr/bin/env python3
"""
Script para verificar y comparar embalajes de un producto específico entre Odoo y MSSQL
- Compara cantidad de unidades
- Compara nombre vs cantidad
- Analiza discrepancias
Autor: Corolla
Fecha: 2025-12-27
"""

import sys
import os
import re
import xmlrpc.client
from datetime import datetime

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

# Configuración Odoo
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

def extraer_cantidad_del_nombre(nombre):
    """Extrae cantidad del nombre del producto (ej: '18X4U' -> 72)"""
    if not nombre:
        return None
    
    # Buscar patrones como "18X4U", "18x4", "18X4", etc.
    patrones = [
        r'(\d+)\s*[xX]\s*(\d+)',  # 18x4, 18X4
        r'(\d+)\s*X\s*(\d+)U',     # 18X4U
        r'(\d+)\s*[xX]\s*(\d+)U',  # 18x4U
    ]
    
    for patron in patrones:
        match = re.search(patron, nombre)
        if match:
            num1 = int(match.group(1))
            num2 = int(match.group(2))
            return num1 * num2
    
    return None

def conectar_odoo():
    """Conecta a Odoo"""
    try:
        common = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/common')
        uid = common.authenticate(ODOO_CONFIG['db'], ODOO_CONFIG['user'], ODOO_CONFIG['pass'], {})
        
        if not uid:
            print(f"❌ Error de autenticación")
            return None, None
        
        models = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/object')
        return models, uid
        
    except Exception as e:
        print(f"❌ Error conectando a Odoo: {e}")
        return None, None

def conectar_mssql():
    """Conecta a MSSQL"""
    try:
        connection_string = (
            f"DRIVER={{ODBC Driver 18 for SQL Server}};"
            f"SERVER={MSSQL_CONFIG['server']};"
            f"DATABASE={MSSQL_CONFIG['database']};"
            f"UID={MSSQL_CONFIG['username']};"
            f"PWD={MSSQL_CONFIG['password']};"
            f"TrustServerCertificate=yes;"
        )
        return pyodbc.connect(connection_string)
    except Exception as e:
        print(f"❌ Error conectando a MSSQL: {e}")
        return None

def obtener_producto_odoo(models, uid, password, producto_id=None, codigo_interno=None):
    """Obtiene información completa de un producto de Odoo"""
    try:
        dominio = []
        if producto_id:
            dominio = [[('id', '=', producto_id)]]
        elif codigo_interno:
            codigo_norm = normalizar_codigo_interno(codigo_interno)
            dominio = [[('default_code', '=', codigo_norm)]]
        else:
            print("❌ Debes proporcionar producto_id o codigo_interno")
            return None
        
        producto = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'product.template', 'search_read',
            dominio,
            {'fields': ['id', 'name', 'default_code', 'barcode', 'weight', 'volume', 'packaging_ids'], 'limit': 1}
        )
        
        if not producto:
            return None
        
        p = producto[0]
        
        # Obtener detalles de embalajes
        embalajes_detallados = []
        if p.get('packaging_ids'):
            packagings = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'product.packaging', 'read',
                [p['packaging_ids']],
                {'fields': ['id', 'name', 'qty', 'barcode', 'product_uom_id', 'package_type_id', 'purchase', 'sales']}
            )
            
            for pack in packagings:
                embalaje_info = {
                    'id': pack['id'],
                    'name': pack.get('name', ''),
                    'qty': pack.get('qty', 0),
                    'barcode': pack.get('barcode'),
                    'purchase': pack.get('purchase', False),
                    'sales': pack.get('sales', False),
                    'package_type': None
                }
                
                # Obtener tipo de paquete si existe
                if pack.get('package_type_id'):
                    package_type = models.execute_kw(
                        ODOO_CONFIG['db'], uid, password,
                        'stock.package.type', 'read',
                        [[pack['package_type_id'][0]]],
                        {'fields': ['id', 'name', 'packaging_length', 'width', 'height', 'max_weight']}
                    )
                    if package_type:
                        pt = package_type[0]
                        embalaje_info['package_type'] = {
                            'name': pt.get('name', ''),
                            'length': pt.get('packaging_length', 0),
                            'width': pt.get('width', 0),
                            'height': pt.get('height', 0),
                            'max_weight': pt.get('max_weight', 0)
                        }
                
                embalajes_detallados.append(embalaje_info)
        
        return {
            'id': p['id'],
            'name': p['name'],
            'default_code': p.get('default_code'),
            'barcode': p.get('barcode'),
            'weight': p.get('weight', 0),
            'volume': p.get('volume', 0),
            'embalajes': embalajes_detallados
        }
        
    except Exception as e:
        print(f"❌ Error obteniendo producto de Odoo: {e}")
        import traceback
        traceback.print_exc()
        return None

def obtener_producto_mssql(conn, codigo_interno=None, codigo_barras=None):
    """Obtiene información de un producto desde MSSQL por código interno o código de barras"""
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        
        if codigo_barras:
            # Buscar por código de barras (PLU)
            query = """
            SELECT 
                a.COD_ARTICULO,
                a.DESCRIPCION,
                a.UNIDAD_MEDIDA,
                a.CTD_UNIDADES,
                a.UNID_BULTO,
                a.DIMBULTO_ALTO,
                a.DIMBULTO_ANCHO,
                a.DIMBULTO_LARGO,
                a.PESO_UMEDIDA,
                ap.PLU
            FROM ARTICULOS a
            INNER JOIN ARTICULOPLU ap ON a.ID_ARTICULO = ap.ID_ARTICULO
            WHERE ap.PLU = ?
            """
            cursor.execute(query, codigo_barras)
        elif codigo_interno:
            # Normalizar código (buscar con punto y coma, y con espacios)
            codigo_norm = normalizar_codigo_interno(codigo_interno)
            
            # Buscar con punto o coma, y con/sin espacios
            query = """
            SELECT 
                COD_ARTICULO,
                DESCRIPCION,
                UNIDAD_MEDIDA,
                CTD_UNIDADES,
                UNID_BULTO,
                DIMBULTO_ALTO,
                DIMBULTO_ANCHO,
                DIMBULTO_LARGO,
                PESO_UMEDIDA,
                NULL as PLU
            FROM ARTICULOS
            WHERE (LTRIM(RTRIM(COD_ARTICULO)) = ? OR LTRIM(RTRIM(COD_ARTICULO)) = ? OR COD_ARTICULO LIKE ?)
            AND COD_ARTICULO IS NOT NULL
            """
            cursor.execute(query, codigo_norm, codigo_interno.replace('.', ','), f'%{codigo_norm}%')
        else:
            return None
        
        row = cursor.fetchone()
        
        if row:
            return {
                'codigo': row[0].strip() if row[0] else None,
                'descripcion': row[1].strip() if row[1] else '',
                'unidad_medida': row[2].strip() if row[2] else None,
                'ctd_unidades': int(row[3]) if row[3] else None,
                'unid_bulto': int(row[4]) if row[4] else None,
                'dim_alto': float(row[5]) if row[5] else None,
                'dim_ancho': float(row[6]) if row[6] else None,
                'dim_largo': float(row[7]) if row[7] else None,
                'peso': float(row[8]) if row[8] else None,
                'plu': row[9].strip() if row[9] else None
            }
        
        return None
        
    except Exception as e:
        print(f"❌ Error obteniendo producto de MSSQL: {e}")
        import traceback
        traceback.print_exc()
        return None

def comparar_producto(producto_odoo, producto_mssql):
    """Compara producto entre Odoo y MSSQL y genera reporte"""
    print("\n" + "="*80)
    print("📊 COMPARACIÓN DE PRODUCTO: ODOO vs MSSQL")
    print("="*80)
    
    print(f"\n📦 PRODUCTO EN ODOO:")
    print(f"   ID: {producto_odoo['id']}")
    print(f"   Nombre: {producto_odoo['name']}")
    print(f"   Código interno: {producto_odoo.get('default_code', 'N/A')}")
    print(f"   Código de barras: {producto_odoo.get('barcode', 'N/A')}")
    print(f"   Peso: {producto_odoo.get('weight', 0)} kg")
    print(f"   Volumen: {producto_odoo.get('volume', 0)} m³")
    
    # Analizar nombre
    cantidad_del_nombre = extraer_cantidad_del_nombre(producto_odoo['name'])
    if cantidad_del_nombre:
        print(f"\n   📝 Análisis del nombre:")
        print(f"      El nombre contiene: {cantidad_del_nombre} unidades (calculado)")
    
    print(f"\n   📋 EMBALAJES EN ODOO ({len(producto_odoo['embalajes'])}):")
    for i, emb in enumerate(producto_odoo['embalajes'], 1):
        print(f"\n      Embalaje {i}:")
        print(f"         Nombre: {emb['name']}")
        print(f"         Cantidad (qty): {emb['qty']} unidades")
        print(f"         Para compra: {emb['purchase']}")
        print(f"         Para venta: {emb['sales']}")
        if emb.get('package_type'):
            pt = emb['package_type']
            print(f"         Tipo de paquete: {pt['name']}")
            print(f"         Dimensiones: {pt['length']} x {pt['width']} x {pt['height']} m")
            print(f"         Peso máximo: {pt['max_weight']} kg")
    
    if producto_mssql:
        print(f"\n📦 PRODUCTO EN MSSQL:")
        print(f"   Código: {producto_mssql['codigo']}")
        print(f"   Descripción: {producto_mssql['descripcion']}")
        print(f"   UNIDAD_MEDIDA: {producto_mssql.get('unidad_medida', 'N/A')}")
        print(f"   CTD_UNIDADES: {producto_mssql.get('ctd_unidades', 'N/A')} (cantidad de unidades)")
        print(f"   UNID_BULTO: {producto_mssql.get('unid_bulto', 'N/A')} (unidades por bulto)")
        if producto_mssql.get('plu'):
            print(f"   Código de barras (PLU): {producto_mssql['plu']}")
        if producto_mssql.get('dim_alto'):
            print(f"   Dimensiones bulto: {producto_mssql.get('dim_alto')} x {producto_mssql.get('dim_ancho')} x {producto_mssql.get('dim_largo')} m (ALTO x ANCHO x LARGO)")
        if producto_mssql.get('peso'):
            print(f"   Peso: {producto_mssql.get('peso')} kg")
    else:
        print(f"\n❌ PRODUCTO NO ENCONTRADO EN MSSQL")
    
    # Análisis de discrepancias
    print(f"\n" + "="*80)
    print("🔍 ANÁLISIS DE DISCREPANCIAS")
    print("="*80)
    
    if producto_mssql:
        unid_bulto_mssql = producto_mssql.get('unid_bulto')
        ctd_unidades_mssql = producto_mssql.get('ctd_unidades')
        
        if producto_odoo['embalajes']:
            qty_odoo = producto_odoo['embalajes'][0]['qty']
            
            print(f"\n📊 Comparación de cantidades:")
            print(f"   Odoo (qty): {qty_odoo} unidades")
            if unid_bulto_mssql:
                print(f"   MSSQL (UNID_BULTO): {unid_bulto_mssql} unidades")
                if abs(qty_odoo - unid_bulto_mssql) > 0.01:
                    print(f"   ⚠️  DISCREPANCIA: Diferencia de {abs(qty_odoo - unid_bulto_mssql)} unidades")
                else:
                    print(f"   ✅ Coincide")
            
            if ctd_unidades_mssql:
                print(f"   MSSQL (CTD_UNIDADES): {ctd_unidades_mssql} unidades")
                if abs(qty_odoo - ctd_unidades_mssql) > 0.01:
                    print(f"   ⚠️  Diferencia con CTD_UNIDADES: {abs(qty_odoo - ctd_unidades_mssql)} unidades")
        
        if cantidad_del_nombre:
            print(f"\n📝 Análisis del nombre vs cantidad:")
            print(f"   Nombre sugiere: {cantidad_del_nombre} unidades")
            if producto_odoo['embalajes']:
                qty_odoo = producto_odoo['embalajes'][0]['qty']
                print(f"   Cantidad en embalaje: {qty_odoo} unidades")
                if abs(cantidad_del_nombre - qty_odoo) > 0.01:
                    print(f"   ⚠️  DISCREPANCIA: El nombre sugiere {cantidad_del_nombre} pero el embalaje dice {qty_odoo}")
                else:
                    print(f"   ✅ El nombre coincide con la cantidad del embalaje")
    
    # Recomendaciones
    print(f"\n" + "="*80)
    print("💡 RECOMENDACIONES")
    print("="*80)
    
    if producto_mssql and producto_odoo['embalajes']:
        unid_bulto_mssql = producto_mssql.get('unid_bulto')
        qty_odoo = producto_odoo['embalajes'][0]['qty']
        
        if unid_bulto_mssql and abs(qty_odoo - unid_bulto_mssql) > 0.01:
            print(f"\n   ⚠️  Considerar actualizar cantidad del embalaje a {unid_bulto_mssql} (valor en MSSQL UNID_BULTO)")
        
        if cantidad_del_nombre and abs(cantidad_del_nombre - qty_odoo) > 0.01:
            print(f"\n   ⚠️  Verificar si el nombre del producto es correcto o si la cantidad del embalaje debería ser {cantidad_del_nombre}")

def main():
    """Función principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Verificar embalaje de un producto entre Odoo y MSSQL')
    parser.add_argument('--producto-id', type=int, help='ID del producto en Odoo')
    parser.add_argument('--codigo', type=str, help='Código interno del producto')
    
    args = parser.parse_args()
    
    if not args.producto_id and not args.codigo:
        print("❌ Debes proporcionar --producto-id o --codigo")
        return
    
    # Conectar a Odoo
    models, uid = conectar_odoo()
    if not models or not uid:
        return
    
    password = ODOO_CONFIG['pass']
    
    # Obtener producto de Odoo
    producto_odoo = obtener_producto_odoo(models, uid, password, args.producto_id, args.codigo)
    
    if not producto_odoo:
        print(f"❌ Producto no encontrado en Odoo")
        return
    
    codigo_para_mssql = producto_odoo.get('default_code') or args.codigo
    codigo_barras_para_mssql = producto_odoo.get('barcode')
    
    # Conectar a MSSQL
    conn = conectar_mssql()
    producto_mssql = None
    if conn:
        # Intentar primero por código de barras (más confiable)
        if codigo_barras_para_mssql:
            producto_mssql = obtener_producto_mssql(conn, codigo_barras=codigo_barras_para_mssql)
        # Si no se encuentra, buscar por código interno
        if not producto_mssql and codigo_para_mssql:
            producto_mssql = obtener_producto_mssql(conn, codigo_interno=codigo_para_mssql)
        conn.close()
    
    # Comparar
    comparar_producto(producto_odoo, producto_mssql)

if __name__ == "__main__":
    main()

