#!/usr/bin/env python3
"""
Script para migrar Lista 1 desde archivo Excel a Odoo master_dev
Lee desde archivo Excel (.xls) y usa la columna "Precio S/IVA" (ya viene sin IVA)
Autor: Corolla
Fecha: 2025-12-28
"""

import os
import sys
import csv
import subprocess
import xmlrpc.client
from datetime import datetime
from collections import defaultdict
import argparse
import re

# Agregar ruta del proyecto
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, '/media/klap/raid5/cursor_files')

try:
    from config_nakel import ODOO_CONFIG_MASTER_DEV
except ImportError:
    print("❌ Error: No se pudo importar config_nakel.py")
    sys.exit(1)

# Configuración Odoo - MASTER_DEV
ODOO_CONFIG = {
    'url': ODOO_CONFIG_MASTER_DEV['url'],
    'db': ODOO_CONFIG_MASTER_DEV['db'],
    'user': ODOO_CONFIG_MASTER_DEV['username'],
    'pass': ODOO_CONFIG_MASTER_DEV['password']
}

# Directorio de listas Excel
DIRECTORIO_LISTAS = '/media/klap/raid5/cursor_files/nakel/ventas/Listas de precios'

def convertir_excel_a_csv_con_libreoffice(archivo_excel):
    """Convierte un archivo Excel a CSV usando LibreOffice"""
    try:
        excel_dir = os.path.dirname(os.path.abspath(archivo_excel))
        excel_name = os.path.splitext(os.path.basename(archivo_excel))[0]
        
        cwd_original = os.getcwd()
        os.chdir(excel_dir)
        
        try:
            cmd = [
                'libreoffice',
                '--headless',
                '--convert-to', 'csv',
                '--outdir', excel_dir,
                os.path.basename(archivo_excel)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=excel_dir)
            
            if result.returncode != 0:
                print(f"⚠️  Error en LibreOffice: {result.stderr}")
                os.chdir(cwd_original)
                return None
            
            csv_generado = os.path.join(excel_dir, f"{excel_name}.csv")
            
            if os.path.exists(csv_generado):
                os.chdir(cwd_original)
                return csv_generado
            else:
                os.chdir(cwd_original)
                return None
                
        finally:
            os.chdir(cwd_original)
        
    except Exception as e:
        print(f"❌ Error convirtiendo Excel a CSV: {e}")
        return None

def leer_lista_precios_excel(archivo_excel):
    """Lee una lista de precios desde un archivo Excel"""
    print(f"\n📋 Leyendo lista de precios desde: {os.path.basename(archivo_excel)}")
    
    if not os.path.exists(archivo_excel):
        print(f"❌ Archivo no encontrado: {archivo_excel}")
        return None
    
    # Convertir a CSV con LibreOffice
    print("   🔄 Convirtiendo Excel a CSV con LibreOffice...")
    archivo_csv = convertir_excel_a_csv_con_libreoffice(archivo_excel)
    
    if not archivo_csv or not os.path.exists(archivo_csv):
        print(f"   ❌ No se pudo generar el CSV")
        return None
    
    print(f"   ✅ CSV generado: {os.path.basename(archivo_csv)}")
    
    # Leer CSV
    productos = []
    try:
        with open(archivo_csv, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Buscar la fila con los encabezados
        header_line_idx = None
        for i, line in enumerate(lines):
            if 'Codigo' in line and 'Descripcion' in line:
                header_line_idx = i
                break
        
        if header_line_idx is None:
            print("❌ No se encontró la fila de encabezados")
            return None
        
        header_line = lines[header_line_idx].strip()
        headers = [h.strip() for h in header_line.split(',')]
        
        # Leer datos
        reader = csv.DictReader(lines[header_line_idx:], fieldnames=headers)
        next(reader, None)  # Saltar encabezados
        
        for row in reader:
            row_limpio = {}
            for key, value in row.items():
                if value:
                    row_limpio[key.strip()] = value.strip()
                else:
                    row_limpio[key.strip()] = None
            
            if row_limpio.get('Codigo') or row_limpio.get('Descripcion'):
                productos.append(row_limpio)
        
        print(f"✅ Archivo leído: {len(productos)} productos encontrados")
        return productos
        
    except Exception as e:
        print(f"❌ Error leyendo CSV: {e}")
        import traceback
        traceback.print_exc()
        return None

def convertir_precio_argentino(precio_str):
    """Convierte un precio en formato argentino (comas como decimales) a float"""
    if not precio_str:
        return None
    
    try:
        precio_limpio = precio_str.strip().replace('.', '').replace(',', '.')
        return float(precio_limpio)
    except (ValueError, AttributeError):
        return None

# NOTA: Ya no se usa convertir_precio_unitario_sin_iva
# El precio de la columna "Precio S/IVA" ya viene sin IVA, así que solo necesitamos convertir_precio_argentino

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
        return None, None

def obtener_lista_odoo(models, uid, password, nombre_lista):
    """Obtiene una lista de precios de Odoo por nombre (case-insensitive si no encuentra exacto)"""
    try:
        # Primero buscar nombre exacto
        listas = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'product.pricelist', 'search_read',
            [[('name', '=', nombre_lista)]],
            {'fields': ['id', 'name', 'currency_id']}
        )
        
        if listas:
            return listas[0]
        
        # Si no encuentra, buscar case-insensitive
        listas = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'product.pricelist', 'search_read',
            [[('name', 'ilike', nombre_lista)]],
            {'fields': ['id', 'name', 'currency_id']}
        )
        
        if listas:
            # Buscar la que más se parezca (ignorando mayúsculas/minúsculas)
            for lista in listas:
                if lista['name'].lower() == nombre_lista.lower():
                    return lista
            # Si no hay coincidencia exacta, tomar la primera
            return listas[0]
        
        return None
    except Exception as e:
        print(f"❌ Error obteniendo lista: {e}")
        return None

def normalizar_codigo_interno(codigo):
    """Normaliza código interno: reemplaza coma por punto
    Ejemplo: '781,3' -> '781.3', '781.3' -> '781.3'
    """
    if not codigo:
        return ''
    return str(codigo).replace(',', '.').strip()

def normalizar_nombre(nombre):
    """Normaliza el nombre para comparación"""
    if not nombre:
        return ""
    
    nombre = nombre.lower().strip()
    
    prefijos = ['zzz', 'zz', 'promo', 'combo']
    for prefijo in prefijos:
        if nombre.startswith(prefijo):
            nombre = nombre[len(prefijo):].strip()
    
    nombre = re.sub(r'[-_\.]+', ' ', nombre)
    nombre = re.sub(r'\s+', ' ', nombre)
    nombre = re.sub(r'\s*\([^)]*\)\s*$', '', nombre)
    nombre = re.sub(r'\s*[0-9]+[gmlx]+\.?\s*$', '', nombre)
    
    return nombre.strip()

def conectar_mssql():
    """Conecta a la base de datos MSSQL"""
    try:
        from config_nakel import MSSQL_CONFIG
        try:
            import pyodbc
        except ImportError:
            print("⚠️  pyodbc no está instalado. El matching por código de barras desde MSSQL no estará disponible.")
            return None
        
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
        print(f"⚠️  No se pudo conectar a MSSQL: {e}")
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
        print(f"⚠️  Error obteniendo códigos de barras de MSSQL: {e}")
        return {}

def extraer_productos_completos_odoo(models, uid, password):
    """Extrae TODOS los productos activos de Odoo"""
    print("\n🔍 Extrayendo productos completos de Odoo...")
    
    try:
        productos = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'product.template', 'search_read',
            [[('active', '=', True)]],
            {'fields': ['id', 'name', 'barcode', 'default_code', 'list_price', 'active']}
        )
        
        productos_con_barcode = sum(1 for p in productos if p.get('barcode'))
        productos_con_codigo = sum(1 for p in productos if p.get('default_code'))
        
        print(f"📊 Productos extraídos de Odoo: {len(productos)}")
        print(f"   • Con código de barras: {productos_con_barcode}")
        print(f"   • Con código interno: {productos_con_codigo}")
        return productos
        
    except Exception as e:
        print(f"❌ Error extrayendo productos de Odoo: {e}")
        return []

def crear_mapeo_productos(productos_excel, productos_odoo):
    """Crea mapeo de productos usando múltiples estrategias mejoradas"""
    print("\n🔍 CREANDO MAPEO DE PRODUCTOS (VERSIÓN MEJORADA)...")
    
    # Conectar a MSSQL para obtener códigos de barras
    print("\n🔌 Conectando a MSSQL para obtener códigos de barras...")
    conn_mssql = conectar_mssql()
    barcodes_mssql = obtener_barcodes_mssql_por_codigo(conn_mssql)
    if barcodes_mssql:
        print(f"   ✅ {len(barcodes_mssql)} códigos de barras obtenidos de MSSQL")
    if conn_mssql:
        conn_mssql.close()
    
    # Preparar índices de Odoo
    odoo_por_barcode = {}
    odoo_por_codigo = {}  # Código exacto
    odoo_por_codigo_normalizado = {}  # Código normalizado (punto)
    odoo_por_nombre_exacto = {}
    odoo_por_nombre_normalizado = {}
    
    for producto in productos_odoo:
        if not producto.get('active'):
            continue
        
        # Por código de barras
        if producto.get('barcode'):
            odoo_por_barcode[producto['barcode']] = producto
        
        # Por código interno (exacto y normalizado)
        if producto.get('default_code'):
            codigo_limpio = producto['default_code'].strip()
            if codigo_limpio:
                # Índice por código exacto
                odoo_por_codigo[codigo_limpio] = producto
                # Índice por código normalizado
                codigo_norm = normalizar_codigo_interno(codigo_limpio)
                if codigo_norm not in odoo_por_codigo_normalizado:
                    odoo_por_codigo_normalizado[codigo_norm] = producto
        
        # Por nombre
        if producto.get('name'):
            nombre_exacto = producto['name'].strip()
            if nombre_exacto:
                odoo_por_nombre_exacto[nombre_exacto] = producto
            
            nombre_norm = normalizar_nombre(nombre_exacto)
            if nombre_norm:
                if nombre_norm not in odoo_por_nombre_normalizado:
                    odoo_por_nombre_normalizado[nombre_norm] = []
                odoo_por_nombre_normalizado[nombre_norm].append(producto)
    
    print(f"\n📊 Índices de Odoo creados:")
    print(f"   • Por barcode: {len(odoo_por_barcode)}")
    print(f"   • Por código interno (exacto): {len(odoo_por_codigo)}")
    print(f"   • Por código interno (normalizado): {len(odoo_por_codigo_normalizado)}")
    print(f"   • Por nombre exacto: {len(odoo_por_nombre_exacto)}")
    print(f"   • Por nombre normalizado: {len(odoo_por_nombre_normalizado)}")
    
    # Crear mapeo - usar código o descripción como clave
    mapeo_productos = {}  # Clave: (codigo, descripcion), Valor: info_odoo
    mapeo_reverso = {}  # Mapeo de producto_excel (índice) a clave
    stats = {
        'codigo_interno_exacto': 0,
        'codigo_interno_normalizado': 0,
        'barcode_via_codigo': 0,
        'nombre_exacto': 0,
        'nombre_normalizado': 0,
        'no_mapeados': 0
    }
    
    productos_ya_mapeados = set()
    
    for idx, producto_excel in enumerate(productos_excel):
        codigo_excel = producto_excel.get('Codigo')
        descripcion_excel = producto_excel.get('Descripcion')
        
        if not codigo_excel and not descripcion_excel:
            continue
        
        # Crear clave única
        clave = (codigo_excel or '', descripcion_excel or '')
        mapeo_reverso[idx] = clave
        
        producto_odoo = None
        tipo_mapeo = None
        
        # Estrategia 1: Por código interno exacto (Codigo en Excel = default_code en Odoo)
        if codigo_excel:
            codigo_limpio = codigo_excel.strip()
            if codigo_limpio in odoo_por_codigo:
                producto_odoo = odoo_por_codigo[codigo_limpio]
                tipo_mapeo = 'codigo_interno_exacto'
        
        # Estrategia 2: Por código interno normalizado (convierte coma a punto)
        if not producto_odoo and codigo_excel:
            codigo_norm = normalizar_codigo_interno(codigo_excel)
            if codigo_norm in odoo_por_codigo_normalizado:
                producto_odoo = odoo_por_codigo_normalizado[codigo_norm]
                tipo_mapeo = 'codigo_interno_normalizado'
        
        # Estrategia 3: Por código de barras desde MSSQL (via código interno)
        if not producto_odoo and codigo_excel:
            codigo_norm = normalizar_codigo_interno(codigo_excel)
            barcode_mssql = barcodes_mssql.get(codigo_norm)
            if barcode_mssql and barcode_mssql in odoo_por_barcode:
                producto_odoo = odoo_por_barcode[barcode_mssql]
                tipo_mapeo = 'barcode_via_codigo'
        
        # Estrategia 4: Por nombre exacto
        if not producto_odoo and descripcion_excel:
            nombre_limpio = descripcion_excel.strip()
            if nombre_limpio in odoo_por_nombre_exacto:
                producto_odoo = odoo_por_nombre_exacto[nombre_limpio]
                tipo_mapeo = 'nombre_exacto'
        
        # Estrategia 5: Por nombre normalizado
        if not producto_odoo and descripcion_excel:
            nombre_norm = normalizar_nombre(descripcion_excel)
            if nombre_norm and nombre_norm in odoo_por_nombre_normalizado:
                # Si hay múltiples, tomar el primero
                producto_odoo = odoo_por_nombre_normalizado[nombre_norm][0]
                tipo_mapeo = 'nombre_normalizado'
        
        if producto_odoo and producto_odoo['id'] not in productos_ya_mapeados:
            mapeo_productos[clave] = {
                'odoo_id': producto_odoo['id'],
                'odoo_name': producto_odoo['name'],
                'tipo_mapeo': tipo_mapeo,
                'excel_codigo': codigo_excel,
                'excel_descripcion': descripcion_excel
            }
            productos_ya_mapeados.add(producto_odoo['id'])
            stats[tipo_mapeo] += 1
        else:
            stats['no_mapeados'] += 1
    
    print(f"\n📊 ESTADÍSTICAS DE MAPEO (MEJORADO):")
    print(f"   ✅ Mapeados por código interno (exacto): {stats['codigo_interno_exacto']}")
    print(f"   ✅ Mapeados por código interno (normalizado): {stats['codigo_interno_normalizado']}")
    print(f"   ✅ Mapeados por código de barras (via MSSQL): {stats['barcode_via_codigo']}")
    print(f"   ✅ Mapeados por nombre exacto: {stats['nombre_exacto']}")
    print(f"   ✅ Mapeados por nombre normalizado: {stats['nombre_normalizado']}")
    print(f"   ❌ No mapeados: {stats['no_mapeados']}")
    total_mapeados = sum(v for k, v in stats.items() if k != 'no_mapeados')
    print(f"   📦 Total mapeados: {total_mapeados}/{len(productos_excel)}")
    
    # Retornar ambos mapeos
    return mapeo_productos, mapeo_reverso, stats

def comparar_y_actualizar_lista(models, uid, password, nombre_lista, productos_excel, mapeo_productos, mapeo_reverso, dry_run=True):
    """Compara y actualiza una lista de precios en Odoo"""
    print(f"\n{'='*70}")
    print(f"🔄 PROCESANDO LISTA: {nombre_lista}")
    print(f"{'='*70}")
    
    # Obtener lista de Odoo
    lista_odoo = obtener_lista_odoo(models, uid, password, nombre_lista)
    
    if not lista_odoo:
        print(f"❌ No se encontró la lista '{nombre_lista}' en Odoo")
        return False
    
    lista_id = lista_odoo['id']
    print(f"✅ Lista encontrada en Odoo (ID: {lista_id})")
    
    # Obtener items actuales de la lista
    try:
        items_actuales = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'product.pricelist.item', 'search_read',
            [[('pricelist_id', '=', lista_id)]],
            {'fields': ['id', 'product_tmpl_id', 'fixed_price']}
        )
        
        print(f"📊 Items actuales en la lista: {len(items_actuales)}")
    except Exception as e:
        print(f"❌ Error obteniendo items actuales: {e}")
        return False
    
    if dry_run:
        print(f"\n🔍 MODO DRY-RUN - No se realizarán cambios")
    
    # Contadores
    precios_nuevos = 0
    precios_actualizados = 0
    precios_sin_mapeo = 0
    errores = 0
    
    # Procesar productos del Excel
    print(f"\n📋 Procesando {len(productos_excel)} productos del Excel...")
    
    for i, producto_excel in enumerate(productos_excel):
        # Obtener clave del mapeo
        clave = mapeo_reverso.get(i)
        if not clave or clave not in mapeo_productos:
            precios_sin_mapeo += 1
            continue
        
        mapeo = mapeo_productos[clave]
        # Usar columna "Precio S/IVA" que ya viene sin IVA
        precio_excel_str = producto_excel.get('Precio S/IVA') or producto_excel.get('Precio S/IVA ')
        precio_excel = convertir_precio_argentino(precio_excel_str)
        
        if precio_excel is None:
            continue
        
        producto_odoo_id = mapeo['odoo_id']
        
        # Buscar si ya existe un item para este producto
        item_existente = None
        for item in items_actuales:
            if item['product_tmpl_id'] and item['product_tmpl_id'][0] == producto_odoo_id:
                item_existente = item
                break
        
        if not dry_run:
            try:
                valores_item = {
                    'pricelist_id': lista_id,
                    'product_tmpl_id': producto_odoo_id,
                    'fixed_price': precio_excel,
                    'applied_on': '1_product'
                }
                
                if item_existente:
                    # Actualizar item existente
                    models.execute_kw(
                        ODOO_CONFIG['db'], uid, password,
                        'product.pricelist.item', 'write',
                        [[item_existente['id']], valores_item]
                    )
                    precios_actualizados += 1
                else:
                    # Crear nuevo item
                    models.execute_kw(
                        ODOO_CONFIG['db'], uid, password,
                        'product.pricelist.item', 'create',
                        [valores_item]
                    )
                    precios_nuevos += 1
                    
            except Exception as e:
                print(f"⚠️  Error procesando producto {mapeo['excel_descripcion']}: {e}")
                errores += 1
        else:
            # En dry-run solo contar
            if item_existente:
                if abs(item_existente.get('fixed_price', 0) - precio_excel) > 0.01:
                    precios_actualizados += 1
            else:
                precios_nuevos += 1
        
        # Mostrar progreso cada 100 productos
        if i % 100 == 0:
            print(f"   🔄 Procesados {i}/{len(productos_excel)} productos...")
    
    print(f"\n📊 RESUMEN:")
    print(f"   ✅ Precios nuevos: {precios_nuevos}")
    print(f"   🔄 Precios actualizados: {precios_actualizados}")
    print(f"   ❌ Sin mapeo: {precios_sin_mapeo}")
    print(f"   ⚠️  Errores: {errores}")
    
    if dry_run:
        print(f"\n💡 Ejecuta sin --dry-run para aplicar los cambios")
    
    return True

def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description='Migrar Lista 1 desde Excel a Odoo')
    parser.add_argument('--lista', default='Lista1.xls', help='Nombre del archivo Excel (default: Lista1.xls)')
    parser.add_argument('--nombre-lista-odoo', default='Lista 1', help='Nombre de la lista en Odoo (default: Lista 1)')
    parser.add_argument('--dry-run', action='store_true', help='Modo dry-run (no realiza cambios)')
    parser.add_argument('--directorio', default=DIRECTORIO_LISTAS, help='Directorio de archivos Excel')
    
    args = parser.parse_args()
    
    archivo_excel = os.path.join(args.directorio, args.lista)
    
    print("=" * 70)
    print("🚀 MIGRACIÓN DE LISTA DE PRECIOS DESDE EXCEL A ODOO")
    print("=" * 70)
    print(f"📊 Base de datos: {ODOO_CONFIG['db']}")
    print(f"📁 Archivo Excel: {args.lista}")
    print(f"📋 Lista Odoo: {args.nombre_lista_odoo}")
    print(f"💰 Columna de precio: Precio S/IVA (sin IVA)")
    print(f"🔍 Modo: {'DRY-RUN' if args.dry_run else 'REAL'}")
    print("=" * 70)
    
    # Leer productos del Excel
    productos_excel = leer_lista_precios_excel(archivo_excel)
    
    if not productos_excel:
        print("\n❌ No se pudieron leer los productos del Excel")
        return
    
    # Conectar a Odoo
    models, uid = conectar_odoo()
    if not models or not uid:
        print("\n❌ No se pudo conectar a Odoo")
        return
    
    password = ODOO_CONFIG['pass']
    
    # Extraer productos de Odoo
    productos_odoo = extraer_productos_completos_odoo(models, uid, password)
    
    if not productos_odoo:
        print("\n❌ No se pudieron obtener productos de Odoo")
        return
    
    # Crear mapeo
    mapeo_productos, mapeo_reverso, stats = crear_mapeo_productos(productos_excel, productos_odoo)
    
    if not mapeo_productos:
        print("\n❌ No se pudo crear el mapeo de productos")
        return
    
    # Comparar y actualizar
    comparar_y_actualizar_lista(
        models, uid, password,
        args.nombre_lista_odoo,
        productos_excel,
        mapeo_productos,
        mapeo_reverso,
        dry_run=args.dry_run
    )
    
    print("\n✅ Proceso completado")

if __name__ == "__main__":
    main()

