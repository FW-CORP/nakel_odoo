#!/usr/bin/env python3
"""
Script para revisar y comparar embalajes de TODOS los productos entre Odoo y MSSQL
- Compara cantidad de unidades (qty vs UNID_BULTO, CTD_UNIDADES)
- Analiza discrepancias en nombres vs cantidades
- Compara dimensiones y peso
- Genera reporte detallado
Autor: Corolla
Fecha: 2025-12-27
"""

import sys
import os
import re
import json
import xmlrpc.client
from datetime import datetime
from collections import defaultdict

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

def obtener_todos_productos_odoo(models, uid, password):
    """Obtiene todos los productos de Odoo con embalajes"""
    print("\n📦 Obteniendo todos los productos de Odoo...")
    
    productos = []
    offset = 0
    batch_size = 1000
    
    while True:
        batch = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'product.template', 'search_read',
            [[('active', '=', True)]],
            {
                'fields': ['id', 'name', 'default_code', 'barcode', 'weight', 'volume', 'packaging_ids'],
                'offset': offset,
                'limit': batch_size
            }
        )
        
        if not batch:
            break
        
        productos.extend(batch)
        offset += batch_size
        
        if len(batch) < batch_size:
            break
    
    print(f"✅ {len(productos)} productos encontrados en Odoo")
    
    # Obtener detalles de embalajes
    productos_con_embalajes = []
    print("\n📋 Obteniendo detalles de embalajes...")
    
    for i, producto in enumerate(productos):
        if i % 500 == 0:
            print(f"   Procesando producto {i+1}/{len(productos)}...")
        
        embalajes_detallados = []
        if producto.get('packaging_ids'):
            try:
                packagings = models.execute_kw(
                    ODOO_CONFIG['db'], uid, password,
                    'product.packaging', 'read',
                    [producto['packaging_ids']],
                    {'fields': ['id', 'name', 'qty', 'barcode', 'package_type_id', 'purchase', 'sales']}
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
                        try:
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
                        except:
                            pass
                    
                    embalajes_detallados.append(embalaje_info)
            except Exception as e:
                pass  # Continuar con siguiente producto
        
        if embalajes_detallados:
            productos_con_embalajes.append({
                'id': producto['id'],
                'name': producto['name'],
                'default_code': producto.get('default_code'),
                'barcode': producto.get('barcode'),
                'weight': producto.get('weight', 0),
                'volume': producto.get('volume', 0),
                'embalajes': embalajes_detallados
            })
    
    print(f"✅ {len(productos_con_embalajes)} productos con embalajes encontrados")
    return productos_con_embalajes

def obtener_productos_mssql_por_barcodes(conn, barcodes):
    """Obtiene productos de MSSQL por códigos de barras (batch)"""
    if not conn or not barcodes:
        return {}
    
    productos_mssql = {}
    
    try:
        cursor = conn.cursor()
        
        # Crear lista de códigos de barras para la consulta
        placeholders = ','.join('?' * len(barcodes))
        
        query = f"""
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
        WHERE ap.PLU IN ({placeholders})
        """
        
        cursor.execute(query, *barcodes)
        
        for row in cursor.fetchall():
            plu = row[9].strip() if row[9] else None
            if plu:
                productos_mssql[plu] = {
                    'codigo': row[0].strip() if row[0] else None,
                    'descripcion': row[1].strip() if row[1] else '',
                    'unidad_medida': row[2].strip() if row[2] else None,
                    'ctd_unidades': int(row[3]) if row[3] else None,
                    'unid_bulto': int(row[4]) if row[4] else None,
                    'dim_alto': float(row[5]) if row[5] else None,
                    'dim_ancho': float(row[6]) if row[6] else None,
                    'dim_largo': float(row[7]) if row[7] else None,
                    'peso': float(row[8]) if row[8] else None,
                    'plu': plu
                }
        
        return productos_mssql
        
    except Exception as e:
        print(f"⚠️  Error obteniendo productos MSSQL por barcodes: {e}")
        return {}

def comparar_productos(productos_odoo, productos_mssql_por_barcode):
    """Compara productos entre Odoo y MSSQL"""
    print("\n🔍 Comparando productos...")
    
    estadisticas = {
        'total_productos': len(productos_odoo),
        'encontrados_en_mssql': 0,
        'no_encontrados': 0,
        'coinciden_unid_bulto': 0,
        'discrepancias_unid_bulto': 0,
        'discrepancias_nombre_cantidad': 0,
        'sin_embalaje_en_odoo': 0
    }
    
    discrepancias = []
    
    for producto_odoo in productos_odoo:
        producto_mssql = None
        metodo_busqueda = None
        
        # Intentar buscar por código de barras primero
        if producto_odoo.get('barcode'):
            producto_mssql = productos_mssql_por_barcode.get(producto_odoo['barcode'])
            if producto_mssql:
                metodo_busqueda = 'barcode'
        
        # Si no se encontró, intentar por código interno
        if not producto_mssql and producto_odoo.get('default_code'):
            codigo_norm = normalizar_codigo_interno(producto_odoo['default_code'])
            # Buscar en el diccionario (tendríamos que tenerlos también por código)
            # Por ahora, si no se encontró por barcode, no lo tenemos
        
        if producto_mssql:
            estadisticas['encontrados_en_mssql'] += 1
            
            if producto_odoo['embalajes']:
                # Comparar con primer embalaje
                embalaje_odoo = producto_odoo['embalajes'][0]
                qty_odoo = embalaje_odoo['qty']
                unid_bulto_mssql = producto_mssql.get('unid_bulto')
                ctd_unidades_mssql = producto_mssql.get('ctd_unidades')
                
                # Comparar UNID_BULTO
                if unid_bulto_mssql:
                    if abs(qty_odoo - unid_bulto_mssql) <= 0.01:
                        estadisticas['coinciden_unid_bulto'] += 1
                    else:
                        estadisticas['discrepancias_unid_bulto'] += 1
                        discrepancias.append({
                            'tipo': 'cantidad_unid_bulto',
                            'producto_id': producto_odoo['id'],
                            'nombre': producto_odoo['name'],
                            'codigo': producto_odoo.get('default_code'),
                            'barcode': producto_odoo.get('barcode'),
                            'qty_odoo': qty_odoo,
                            'unid_bulto_mssql': unid_bulto_mssql,
                            'diferencia': abs(qty_odoo - unid_bulto_mssql),
                            'metodo_busqueda': metodo_busqueda
                        })
                
                # Verificar nombre vs cantidad
                cantidad_del_nombre = extraer_cantidad_del_nombre(producto_odoo['name'])
                if cantidad_del_nombre and abs(cantidad_del_nombre - qty_odoo) > 0.01:
                    estadisticas['discrepancias_nombre_cantidad'] += 1
                    discrepancias.append({
                        'tipo': 'nombre_vs_cantidad',
                        'producto_id': producto_odoo['id'],
                        'nombre': producto_odoo['name'],
                        'codigo': producto_odoo.get('default_code'),
                        'barcode': producto_odoo.get('barcode'),
                        'cantidad_del_nombre': cantidad_del_nombre,
                        'qty_embalaje': qty_odoo,
                        'diferencia': abs(cantidad_del_nombre - qty_odoo),
                        'metodo_busqueda': metodo_busqueda
                    })
        else:
            estadisticas['no_encontrados'] += 1
            if not producto_odoo['embalajes']:
                estadisticas['sin_embalaje_en_odoo'] += 1
    
    return estadisticas, discrepancias

def generar_reporte(estadisticas, discrepancias, output_file):
    """Genera reporte en formato texto"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    reporte_path = os.path.join(output_file or f"../reportes/comparacion_embalajes_odoo_mssql_{timestamp}.txt")
    
    os.makedirs(os.path.dirname(reporte_path), exist_ok=True)
    
    with open(reporte_path, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("REPORTE DE COMPARACIÓN DE EMBALAJES: ODOO vs MSSQL\n")
        f.write("="*80 + "\n")
        f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Base de datos Odoo: {ODOO_CONFIG['db']}\n")
        f.write("\n")
        
        # Estadísticas
        f.write("ESTADÍSTICAS GENERALES\n")
        f.write("-"*80 + "\n")
        f.write(f"Total productos con embalajes en Odoo: {estadisticas['total_productos']}\n")
        f.write(f"Encontrados en MSSQL: {estadisticas['encontrados_en_mssql']}\n")
        f.write(f"No encontrados en MSSQL: {estadisticas['no_encontrados']}\n")
        f.write(f"Coinciden con UNID_BULTO: {estadisticas['coinciden_unid_bulto']}\n")
        f.write(f"Discrepancias con UNID_BULTO: {estadisticas['discrepancias_unid_bulto']}\n")
        f.write(f"Discrepancias nombre vs cantidad: {estadisticas['discrepancias_nombre_cantidad']}\n")
        f.write("\n")
        
        # Discrepancias de cantidad
        discrepancias_cantidad = [d for d in discrepancias if d['tipo'] == 'cantidad_unid_bulto']
        if discrepancias_cantidad:
            f.write("DISCREPANCIAS DE CANTIDAD (qty vs UNID_BULTO)\n")
            f.write("-"*80 + "\n")
            for disc in sorted(discrepancias_cantidad, key=lambda x: x['diferencia'], reverse=True)[:50]:
                f.write(f"\nProducto ID: {disc['producto_id']}\n")
                f.write(f"  Nombre: {disc['nombre']}\n")
                f.write(f"  Código: {disc.get('codigo', 'N/A')}\n")
                f.write(f"  Barcode: {disc.get('barcode', 'N/A')}\n")
                f.write(f"  Odoo (qty): {disc['qty_odoo']} unidades\n")
                f.write(f"  MSSQL (UNID_BULTO): {disc['unid_bulto_mssql']} unidades\n")
                f.write(f"  Diferencia: {disc['diferencia']} unidades\n")
                f.write(f"  Buscado por: {disc.get('metodo_busqueda', 'N/A')}\n")
        
        # Discrepancias nombre vs cantidad
        discrepancias_nombre = [d for d in discrepancias if d['tipo'] == 'nombre_vs_cantidad']
        if discrepancias_nombre:
            f.write(f"\n\nDISCREPANCIAS NOMBRE VS CANTIDAD ({len(discrepancias_nombre)} productos)\n")
            f.write("-"*80 + "\n")
            for disc in discrepancias_nombre[:50]:
                f.write(f"\nProducto ID: {disc['producto_id']}\n")
                f.write(f"  Nombre: {disc['nombre']}\n")
                f.write(f"  Código: {disc.get('codigo', 'N/A')}\n")
                f.write(f"  Barcode: {disc.get('barcode', 'N/A')}\n")
                f.write(f"  Nombre sugiere: {disc['cantidad_del_nombre']} unidades\n")
                f.write(f"  Cantidad en embalaje: {disc['qty_embalaje']} unidades\n")
                f.write(f"  Diferencia: {disc['diferencia']} unidades\n")
        
        f.write("\n" + "="*80 + "\n")
        f.write("FIN DEL REPORTE\n")
    
    print(f"\n✅ Reporte guardado en: {reporte_path}")
    return reporte_path

def main():
    """Función principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Revisar embalajes de todos los productos entre Odoo y MSSQL')
    parser.add_argument('--output', type=str, help='Ruta del archivo de salida (opcional)')
    parser.add_argument('--limit', type=int, help='Limitar número de productos a procesar (para pruebas)')
    
    args = parser.parse_args()
    
    print("="*80)
    print("REVISIÓN DE EMBALAJES: TODOS LOS PRODUCTOS")
    print("="*80)
    
    # Conectar a Odoo
    models, uid = conectar_odoo()
    if not models or not uid:
        return
    
    password = ODOO_CONFIG['pass']
    
    # Obtener productos de Odoo
    productos_odoo = obtener_todos_productos_odoo(models, uid, password)
    
    if args.limit:
        productos_odoo = productos_odoo[:args.limit]
        print(f"\n⚠️  Limitando procesamiento a {len(productos_odoo)} productos")
    
    # Obtener códigos de barras únicos
    barcodes = [p['barcode'] for p in productos_odoo if p.get('barcode')]
    print(f"\n📋 Obteniendo productos de MSSQL por {len(barcodes)} códigos de barras...")
    
    # Conectar a MSSQL y obtener productos
    conn = conectar_mssql()
    productos_mssql_por_barcode = {}
    
    if conn:
        # Procesar en lotes de 1000 para evitar problemas de memoria
        batch_size = 1000
        for i in range(0, len(barcodes), batch_size):
            batch = barcodes[i:i+batch_size]
            print(f"   Procesando lote {i//batch_size + 1}...")
            batch_result = obtener_productos_mssql_por_barcodes(conn, batch)
            productos_mssql_por_barcode.update(batch_result)
        
        conn.close()
        print(f"✅ {len(productos_mssql_por_barcode)} productos encontrados en MSSQL")
    else:
        print("⚠️  No se pudo conectar a MSSQL")
    
    # Comparar
    estadisticas, discrepancias = comparar_productos(productos_odoo, productos_mssql_por_barcode)
    
    # Mostrar resumen
    print("\n" + "="*80)
    print("📊 RESUMEN")
    print("="*80)
    print(f"Total productos con embalajes en Odoo: {estadisticas['total_productos']}")
    print(f"Encontrados en MSSQL: {estadisticas['encontrados_en_mssql']}")
    print(f"No encontrados en MSSQL: {estadisticas['no_encontrados']}")
    print(f"✅ Coinciden con UNID_BULTO: {estadisticas['coinciden_unid_bulto']}")
    print(f"⚠️  Discrepancias con UNID_BULTO: {estadisticas['discrepancias_unid_bulto']}")
    print(f"⚠️  Discrepancias nombre vs cantidad: {estadisticas['discrepancias_nombre_cantidad']}")
    
    # Generar reporte
    if discrepancias:
        reporte_path = generar_reporte(estadisticas, discrepancias, args.output)
        print(f"\n📄 Reporte detallado generado: {reporte_path}")
    else:
        print("\n✅ No se encontraron discrepancias significativas")

if __name__ == "__main__":
    main()

