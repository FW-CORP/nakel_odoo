#!/usr/bin/env python3
"""
Script para leer listas de precios desde archivos Excel (.xls/.xlsx)
y compararlas con listas en Odoo master_18
Autor: Corolla
Fecha: 2025-12-27
"""

import os
import sys
import csv
import subprocess
import tempfile
import json
import xmlrpc.client
from datetime import datetime

# Agregar ruta del proyecto
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(script_dir, '../../..')
sys.path.insert(0, os.path.abspath(project_root))

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

def convertir_excel_a_csv_con_libreoffice(archivo_excel):
    """Convierte un archivo Excel a CSV usando LibreOffice"""
    try:
        excel_dir = os.path.dirname(os.path.abspath(archivo_excel))
        excel_name = os.path.splitext(os.path.basename(archivo_excel))[0]
        
        # LibreOffice genera el CSV en el directorio actual de trabajo
        # Cambiamos al directorio del Excel para que genere ahí
        cwd_original = os.getcwd()
        os.chdir(excel_dir)
        
        try:
            # Usar LibreOffice para convertir
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
            
            # LibreOffice genera el CSV en el mismo directorio
            csv_generado = os.path.join(excel_dir, f"{excel_name}.csv")
            
            if os.path.exists(csv_generado):
                os.chdir(cwd_original)
                return csv_generado
            else:
                print(f"⚠️  CSV no encontrado en: {csv_generado}")
                print(f"   stdout: {result.stdout}")
                os.chdir(cwd_original)
                return None
                
        finally:
            os.chdir(cwd_original)
        
    except Exception as e:
        print(f"❌ Error convirtiendo Excel a CSV: {e}")
        import traceback
        traceback.print_exc()
        return None

def leer_excel_directo(archivo_excel):
    """Intenta leer el Excel directamente usando pandas si está disponible"""
    try:
        import pandas as pd
        df = pd.read_excel(archivo_excel)
        return df.to_dict('records')
    except ImportError:
        return None
    except Exception as e:
        print(f"⚠️  Error leyendo Excel directo: {e}")
        return None

def leer_csv(archivo_csv):
    """Lee un archivo CSV y retorna lista de diccionarios"""
    productos = []
    
    try:
        with open(archivo_csv, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Buscar la fila con los encabezados (buscar "Codigo" o "Descripcion")
        header_line_idx = None
        for i, line in enumerate(lines):
            if 'Codigo' in line and 'Descripcion' in line:
                header_line_idx = i
                break
        
        if header_line_idx is None:
            print("❌ No se encontró la fila de encabezados en el CSV")
            return None
        
        # Leer encabezados
        header_line = lines[header_line_idx].strip()
        headers = [h.strip() for h in header_line.split(',')]
        
        print(f"   📋 Encabezados encontrados en línea {header_line_idx + 1}: {headers}")
        
        # Leer datos desde la siguiente línea
        reader = csv.DictReader(lines[header_line_idx:], fieldnames=headers)
        
        # Saltar la primera fila (es la de encabezados)
        next(reader, None)
        
        for row in reader:
            # Limpiar valores
            row_limpio = {}
            for key, value in row.items():
                if value:
                    row_limpio[key.strip()] = value.strip()
                else:
                    row_limpio[key.strip()] = None
            
            # Solo agregar si tiene al menos código o descripción
            if row_limpio.get('Codigo') or row_limpio.get('Descripcion'):
                productos.append(row_limpio)
        
        return productos
    except Exception as e:
        print(f"❌ Error leyendo CSV: {e}")
        import traceback
        traceback.print_exc()
        return None

def leer_lista_precios_excel(archivo_excel):
    """Lee una lista de precios desde un archivo Excel"""
    print(f"\n📋 Leyendo lista de precios desde: {os.path.basename(archivo_excel)}")
    
    if not os.path.exists(archivo_excel):
        print(f"❌ Archivo no encontrado: {archivo_excel}")
        return None
    
    # Intentar leer directamente con pandas
    productos = leer_excel_directo(archivo_excel)
    
    if productos is None:
        # Convertir a CSV con LibreOffice
        print("   🔄 Convirtiendo Excel a CSV con LibreOffice...")
        archivo_csv = convertir_excel_a_csv_con_libreoffice(archivo_excel)
        
        if archivo_csv and os.path.exists(archivo_csv):
            print(f"   ✅ CSV generado: {os.path.basename(archivo_csv)}")
            productos = leer_csv(archivo_csv)
            # Mantener el CSV por ahora para debugging (se puede limpiar después)
        else:
            print(f"   ❌ No se pudo generar el CSV")
    
    if productos is None:
        print(f"❌ No se pudo leer el archivo Excel")
        return None
    
    print(f"✅ Archivo leído: {len(productos)} productos encontrados")
    
    # Mostrar estructura
    if productos:
        print(f"\n📊 COLUMNAS ENCONTRADAS:")
        columnas = list(productos[0].keys())
        for i, col in enumerate(columnas, 1):
            print(f"   {i:2d}. {col}")
        
        print(f"\n📋 PRIMERAS 3 FILAS (muestra):")
        for i, producto in enumerate(productos[:3], 1):
            print(f"   Fila {i}:")
            for key, value in producto.items():
                if value:  # Solo mostrar valores no vacíos
                    print(f"      {key}: {value}")
    
    return productos

def identificar_columnas(productos):
    """Identifica las columnas relevantes en los datos"""
    if not productos:
        return None
    
    columnas = list(productos[0].keys())
    
    # Buscar columnas por nombre exacto (ya sabemos la estructura)
    resultado = {}
    
    # Mapeo directo basado en lo que vimos en el CSV
    mapeo_esperado = {
        'Codigo': 'codigo',
        'Descripcion': 'producto',
        'Precio C/IVA': 'precio',
        'Nombre Rubro': 'rubro',
        'CxB': 'cxb',
        'Stock': 'stock'
    }
    
    for col_excel, col_interna in mapeo_esperado.items():
        if col_excel in columnas:
            resultado[col_interna] = col_excel
    
    # También buscar variantes
    for col in columnas:
        col_lower = col.lower()
        
        # Precio C/IVA
        if 'c/iva' in col_lower and 'precio' in col_lower:
            resultado['precio'] = col
        
        # Nombre Rubro
        if 'nombre' in col_lower and 'rubro' in col_lower:
            resultado['rubro'] = col
        
        # Descripción
        if 'descripcion' in col_lower:
            resultado['producto'] = col
        
        # Código
        if 'codigo' in col_lower:
            resultado['codigo'] = col
    
    return resultado

def convertir_precio_argentino(precio_str):
    """Convierte un precio en formato argentino (comas como decimales) a float"""
    if not precio_str:
        return None
    
    try:
        # Remover espacios y reemplazar coma por punto
        precio_limpio = precio_str.strip().replace('.', '').replace(',', '.')
        return float(precio_limpio)
    except (ValueError, AttributeError):
        return None

def main():
    """Función principal - Analizar Lista1.xls"""
    archivo = '/media/klap/raid5/cursor_files/nakel/ventas/Listas de precios/Lista1.xls'
    
    print("=" * 70)
    print("🔍 LECTURA DE LISTA DE PRECIOS DESDE EXCEL")
    print("=" * 70)
    
    # Leer el archivo Excel
    productos = leer_lista_precios_excel(archivo)
    
    if productos is None:
        print("\n❌ No se pudo leer el archivo")
        return
    
    # Identificar columnas
    print("\n🔍 IDENTIFICANDO COLUMNAS RELEVANTES...")
    columnas = identificar_columnas(productos)
    
    if columnas:
        print(f"\n✅ Columnas identificadas:")
        for key, value in columnas.items():
            print(f"   • {key}: '{value}'")
    else:
        print("\n⚠️  No se pudieron identificar todas las columnas necesarias")
    
    print("\n✅ Análisis completado")

if __name__ == "__main__":
    main()

