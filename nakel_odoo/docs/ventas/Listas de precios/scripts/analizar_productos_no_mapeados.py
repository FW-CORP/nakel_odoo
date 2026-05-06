#!/usr/bin/env python3
"""
Script para analizar productos no mapeados entre Excel y Odoo
Identifica por qué no se mapearon y genera un reporte detallado
Autor: Corolla
Fecha: 2025-12-27
"""

import os
import sys
import csv
import subprocess
import xmlrpc.client
from datetime import datetime
import re
from difflib import SequenceMatcher

# Agregar ruta del proyecto
script_dir = os.path.dirname(os.path.abspath(__file__))
# Desde: /media/klap/raid5/cursor_files/nakel/ventas/Listas de precios/scripts/
# Hacia: /media/klap/raid5/cursor_files/
project_root = os.path.join(script_dir, '../../../../..')
sys.path.insert(0, '/media/klap/raid5/cursor_files')

try:
    from config_nakel import ODOO_CONFIG_MASTER18
except ImportError:
    print("❌ Error: No se pudo importar config_nakel.py")
    sys.exit(1)

# Configuración Odoo - MASTER_18 (PRODUCCIÓN)
ODOO_CONFIG = {
    'url': ODOO_CONFIG_MASTER18['url'],
    'db': ODOO_CONFIG_MASTER18['db'],
    'user': ODOO_CONFIG_MASTER18['username'],
    'pass': ODOO_CONFIG_MASTER18['password']
}

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
    if not os.path.exists(archivo_excel):
        return None
    
    archivo_csv = convertir_excel_a_csv_con_libreoffice(archivo_excel)
    if not archivo_csv or not os.path.exists(archivo_csv):
        return None
    
    productos = []
    try:
        with open(archivo_csv, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        header_line_idx = None
        for i, line in enumerate(lines):
            if 'Codigo' in line and 'Descripcion' in line:
                header_line_idx = i
                break
        
        if header_line_idx is None:
            return None
        
        header_line = lines[header_line_idx].strip()
        headers = [h.strip() for h in header_line.split(',')]
        
        reader = csv.DictReader(lines[header_line_idx:], fieldnames=headers)
        next(reader, None)
        
        for row in reader:
            row_limpio = {}
            for key, value in row.items():
                if value:
                    row_limpio[key.strip()] = value.strip()
                else:
                    row_limpio[key.strip()] = None
            
            if row_limpio.get('Codigo') or row_limpio.get('Descripcion'):
                productos.append(row_limpio)
        
        return productos
    except Exception as e:
        print(f"❌ Error leyendo CSV: {e}")
        return None

def conectar_odoo():
    """Conecta a Odoo master_18"""
    try:
        common = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/common')
        uid = common.authenticate(ODOO_CONFIG['db'], ODOO_CONFIG['user'], ODOO_CONFIG['pass'], {})
        if not uid:
            return None, None
        models = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/object')
        return models, uid
    except Exception as e:
        print(f"❌ Error conectando a Odoo: {e}")
        return None, None

def extraer_productos_completos_odoo(models, uid, password):
    """Extrae TODOS los productos activos de Odoo"""
    try:
        productos = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'product.template', 'search_read',
            [[('active', '=', True)]],
            {'fields': ['id', 'name', 'barcode', 'default_code', 'list_price', 'active']}
        )
        return productos
    except Exception as e:
        print(f"❌ Error extrayendo productos de Odoo: {e}")
        return []

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

def buscar_similares(nombre_excel, productos_odoo, umbral=0.7):
    """Busca productos similares en Odoo por nombre"""
    similares = []
    nombre_excel_norm = normalizar_nombre(nombre_excel)
    
    for producto_odoo in productos_odoo:
        nombre_odoo_norm = normalizar_nombre(producto_odoo.get('name', ''))
        if nombre_odoo_norm:
            ratio = SequenceMatcher(None, nombre_excel_norm, nombre_odoo_norm).ratio()
            if ratio >= umbral:
                similares.append({
                    'producto': producto_odoo,
                    'similarity': ratio,
                    'nombre_odoo': producto_odoo.get('name'),
                    'codigo_odoo': producto_odoo.get('default_code')
                })
    
    return sorted(similares, key=lambda x: x['similarity'], reverse=True)[:5]

def analizar_productos_no_mapeados(archivo_excel='Lista1.xls'):
    """Analiza los productos no mapeados"""
    print("=" * 80)
    print("🔍 ANÁLISIS DE PRODUCTOS NO MAPEADOS")
    print("=" * 80)
    
    archivo_excel_path = os.path.join(DIRECTORIO_LISTAS, archivo_excel)
    
    # Leer productos del Excel
    print(f"\n📋 Leyendo productos del Excel: {archivo_excel}")
    productos_excel = leer_lista_precios_excel(archivo_excel_path)
    
    if not productos_excel:
        print("❌ No se pudieron leer los productos del Excel")
        return
    
    print(f"✅ {len(productos_excel)} productos encontrados en Excel")
    
    # Conectar a Odoo
    print("\n🔌 Conectando a Odoo...")
    models, uid = conectar_odoo()
    if not models or not uid:
        print("❌ No se pudo conectar a Odoo")
        return
    
    password = ODOO_CONFIG['pass']
    
    # Extraer productos de Odoo
    print("📦 Extrayendo productos de Odoo...")
    productos_odoo = extraer_productos_completos_odoo(models, uid, password)
    print(f"✅ {len(productos_odoo)} productos encontrados en Odoo")
    
    # Preparar índices de Odoo
    print("\n🔍 Creando índices de Odoo...")
    odoo_por_codigo = {}
    odoo_por_nombre_exacto = {}
    
    for producto in productos_odoo:
        if not producto.get('active'):
            continue
        if producto.get('default_code'):
            codigo_limpio = producto['default_code'].strip()
            if codigo_limpio:
                odoo_por_codigo[codigo_limpio] = producto
        if producto.get('name'):
            nombre_exacto = producto['name'].strip()
            if nombre_exacto:
                odoo_por_nombre_exacto[nombre_exacto] = producto
    
    # Identificar productos no mapeados
    print("\n🔍 Identificando productos no mapeados...")
    no_mapeados = []
    productos_ya_mapeados = set()
    
    for idx, producto_excel in enumerate(productos_excel):
        codigo_excel = producto_excel.get('Codigo')
        descripcion_excel = producto_excel.get('Descripcion')
        
        if not codigo_excel and not descripcion_excel:
            continue
        
        producto_odoo = None
        
        # Intentar mapeo por código
        if codigo_excel:
            codigo_limpio = codigo_excel.strip()
            if codigo_limpio in odoo_por_codigo:
                producto_odoo = odoo_por_codigo[codigo_limpio]
        
        # Intentar mapeo por nombre exacto
        if not producto_odoo and descripcion_excel:
            nombre_limpio = descripcion_excel.strip()
            if nombre_limpio in odoo_por_nombre_exacto:
                producto_odoo = odoo_por_nombre_exacto[nombre_limpio]
        
        # Intentar mapeo por nombre normalizado
        if not producto_odoo and descripcion_excel:
            nombre_norm_excel = normalizar_nombre(descripcion_excel)
            for producto in productos_odoo:
                if not producto.get('active'):
                    continue
                nombre_norm_odoo = normalizar_nombre(producto.get('name', ''))
                if nombre_norm_excel == nombre_norm_odoo and nombre_norm_excel:
                    producto_odoo = producto
                    break
        
        if producto_odoo and producto_odoo['id'] not in productos_ya_mapeados:
            productos_ya_mapeados.add(producto_odoo['id'])
        else:
            # No se pudo mapear
            precio_excel = producto_excel.get('Precio C/IVA', '')
            rubro = producto_excel.get('Nombre Rubro', '')
            no_mapeados.append({
                'codigo': codigo_excel,
                'descripcion': descripcion_excel,
                'precio': precio_excel,
                'rubro': rubro,
                'index': idx
            })
    
    print(f"\n📊 PRODUCTOS NO MAPEADOS: {len(no_mapeados)} de {len(productos_excel)}")
    
    # Analizar por qué no se mapearon
    print("\n🔍 Analizando razones de no mapeo...")
    
    categorias = {
        'sin_codigo_ni_nombre_valido': [],
        'codigo_no_existe': [],
        'nombre_no_existe': [],
        'posibles_similares': []
    }
    
    for producto in no_mapeados:
        codigo = producto['codigo']
        descripcion = producto['descripcion']
        
        # Categorizar
        if not codigo or codigo.strip() == '':
            if not descripcion or descripcion.strip() == '':
                categorias['sin_codigo_ni_nombre_valido'].append(producto)
            else:
                # Buscar similares por nombre
                similares = buscar_similares(descripcion, productos_odoo, umbral=0.7)
                if similares:
                    producto['similares'] = similares
                    categorias['posibles_similares'].append(producto)
                else:
                    categorias['nombre_no_existe'].append(producto)
        else:
            codigo_limpio = codigo.strip()
            if codigo_limpio not in odoo_por_codigo:
                categorias['codigo_no_existe'].append(producto)
            else:
                # Tiene código pero no se mapeó por otro motivo (probablemente ya estaba mapeado)
                categorias['codigo_no_existe'].append(producto)
    
    # Mostrar resumen por categoría
    print("\n" + "=" * 80)
    print("📊 RESUMEN DE ANÁLISIS")
    print("=" * 80)
    
    print(f"\n1️⃣  Sin código ni nombre válido: {len(categorias['sin_codigo_ni_nombre_valido'])}")
    print(f"2️⃣  Código no existe en Odoo: {len(categorias['codigo_no_existe'])}")
    print(f"3️⃣  Nombre no existe (sin similares): {len(categorias['nombre_no_existe'])}")
    print(f"4️⃣  Posibles similares encontrados: {len(categorias['posibles_similares'])}")
    
    # Generar reporte detallado
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    reporte_file = os.path.join(DIRECTORIO_LISTAS, f"reporte_no_mapeados_{timestamp}.txt")
    
    with open(reporte_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("REPORTE DE PRODUCTOS NO MAPEADOS\n")
        f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Archivo Excel: {archivo_excel}\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"TOTAL DE PRODUCTOS EN EXCEL: {len(productos_excel)}\n")
        f.write(f"PRODUCTOS MAPEADOS: {len(productos_excel) - len(no_mapeados)}\n")
        f.write(f"PRODUCTOS NO MAPEADOS: {len(no_mapeados)}\n\n")
        
        # Sección 1: Sin código ni nombre válido
        if categorias['sin_codigo_ni_nombre_valido']:
            f.write("\n" + "=" * 80 + "\n")
            f.write("1. PRODUCTOS SIN CÓDIGO NI NOMBRE VÁLIDO\n")
            f.write("=" * 80 + "\n\n")
            for producto in categorias['sin_codigo_ni_nombre_valido']:
                f.write(f"Código: {producto['codigo'] or '(vacío)'}\n")
                f.write(f"Descripción: {producto['descripcion'] or '(vacío)'}\n")
                f.write(f"Rubro: {producto['rubro'] or '(vacío)'}\n")
                f.write("-" * 80 + "\n")
        
        # Sección 2: Código no existe
        if categorias['codigo_no_existe']:
            f.write("\n" + "=" * 80 + "\n")
            f.write("2. PRODUCTOS CON CÓDIGO QUE NO EXISTE EN ODOO\n")
            f.write("=" * 80 + "\n\n")
            for producto in categorias['codigo_no_existe'][:100]:  # Primeros 100
                f.write(f"Código: {producto['codigo']}\n")
                f.write(f"Descripción: {producto['descripcion']}\n")
                f.write(f"Precio C/IVA: {producto['precio']}\n")
                f.write(f"Rubro: {producto['rubro']}\n")
                f.write("-" * 80 + "\n")
        
        # Sección 3: Nombre no existe
        if categorias['nombre_no_existe']:
            f.write("\n" + "=" * 80 + "\n")
            f.write("3. PRODUCTOS CON NOMBRE QUE NO EXISTE EN ODOO (sin similares)\n")
            f.write("=" * 80 + "\n\n")
            for producto in categorias['nombre_no_existe'][:100]:  # Primeros 100
                f.write(f"Descripción: {producto['descripcion']}\n")
                f.write(f"Precio C/IVA: {producto['precio']}\n")
                f.write(f"Rubro: {producto['rubro']}\n")
                f.write("-" * 80 + "\n")
        
        # Sección 4: Posibles similares
        if categorias['posibles_similares']:
            f.write("\n" + "=" * 80 + "\n")
            f.write("4. PRODUCTOS CON POSIBLES SIMILARES EN ODOO\n")
            f.write("=" * 80 + "\n\n")
            for producto in categorias['posibles_similares'][:50]:  # Primeros 50
                f.write(f"Descripción Excel: {producto['descripcion']}\n")
                f.write(f"Precio C/IVA: {producto['precio']}\n")
                f.write(f"Rubro: {producto['rubro']}\n")
                f.write("Similares encontrados:\n")
                for similar in producto.get('similares', [])[:3]:
                    f.write(f"  • {similar['nombre_odoo']} (Similaridad: {similar['similarity']:.2%}, Código: {similar['codigo_odoo'] or 'N/A'})\n")
                f.write("-" * 80 + "\n")
    
    print(f"\n✅ Reporte guardado en: {reporte_file}")
    
    # Mostrar algunos ejemplos de cada categoría
    print("\n" + "=" * 80)
    print("📋 EJEMPLOS DE PRODUCTOS NO MAPEADOS")
    print("=" * 80)
    
    if categorias['codigo_no_existe']:
        print("\n🔴 Ejemplos de productos con código que no existe en Odoo:")
        for producto in categorias['codigo_no_existe'][:5]:
            print(f"   • Código: {producto['codigo']} | {producto['descripcion'][:60]}")
    
    if categorias['posibles_similares']:
        print("\n🟡 Ejemplos de productos con posibles similares:")
        for producto in categorias['posibles_similares'][:3]:
            print(f"   • Excel: {producto['descripcion'][:50]}")
            if producto.get('similares'):
                mejor = producto['similares'][0]
                print(f"     → Odoo: {mejor['nombre_odoo'][:50]} (Similaridad: {mejor['similarity']:.1%})")
    
    print("\n✅ Análisis completado")

def main():
    """Función principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Analizar productos no mapeados')
    parser.add_argument('--lista', default='Lista1.xls', help='Nombre del archivo Excel')
    
    args = parser.parse_args()
    
    analizar_productos_no_mapeados(args.lista)

if __name__ == "__main__":
    main()

