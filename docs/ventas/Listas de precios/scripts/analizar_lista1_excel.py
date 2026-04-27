#!/usr/bin/env python3
"""
Script para analizar la estructura del archivo Excel Lista1.xls
Autor: Corolla
Fecha: 2025-12-27
"""

import os
import sys

# Agregar ruta del proyecto
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(script_dir, '../../..')
sys.path.insert(0, os.path.abspath(project_root))

# Intentar importar pandas
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    print("⚠️  pandas no está instalado. Intentando con openpyxl...")
    try:
        import openpyxl
        HAS_OPENPYXL = True
    except ImportError:
        HAS_OPENPYXL = False
        print("❌ No se encontraron librerías para leer Excel. Instalando pandas...")
        os.system("python3 -m pip install pandas openpyxl --quiet")
        try:
            import pandas as pd
            HAS_PANDAS = True
        except ImportError:
            print("❌ Error: No se pudo instalar pandas")
            sys.exit(1)

def analizar_excel_con_pandas(archivo):
    """Analizar Excel usando pandas"""
    print(f"📋 Analizando {archivo} con pandas...\n")
    
    try:
        # Intentar leer el archivo
        df = pd.read_excel(archivo)
        
        print(f"✅ Archivo leído correctamente")
        print(f"📊 Total filas: {len(df)}")
        print(f"📊 Total columnas: {len(df.columns)}")
        
        print(f"\n📋 COLUMNAS ENCONTRADAS:")
        for i, col in enumerate(df.columns, 1):
            print(f"   {i:2d}. {col}")
        
        print(f"\n📋 PRIMERAS 10 FILAS (muestra):")
        print(df.head(10).to_string())
        
        print(f"\n📊 INFORMACIÓN DE TIPOS:")
        print(df.dtypes)
        
        print(f"\n📊 ESTADÍSTICAS BÁSICAS:")
        print(df.describe())
        
        # Buscar columnas relevantes
        print(f"\n🔍 BUSCANDO COLUMNAS RELEVANTES:")
        columnas_precio = [col for col in df.columns if 'precio' in col.lower() or 'iva' in col.lower() or 'c/iva' in col.lower()]
        columnas_rubro = [col for col in df.columns if 'rubro' in col.lower() or 'categoria' in col.lower()]
        columnas_producto = [col for col in df.columns if 'producto' in col.lower() or 'nombre' in col.lower() or 'descripcion' in col.lower()]
        columnas_codigo = [col for col in df.columns if 'codigo' in col.lower() or 'barcode' in col.lower() or 'plu' in col.lower()]
        
        if columnas_precio:
            print(f"   💰 Columnas de precio: {columnas_precio}")
        if columnas_rubro:
            print(f"   📁 Columnas de rubro/categoría: {columnas_rubro}")
        if columnas_producto:
            print(f"   📦 Columnas de producto: {columnas_producto}")
        if columnas_codigo:
            print(f"   🔢 Columnas de código: {columnas_codigo}")
        
        return df
        
    except Exception as e:
        print(f"❌ Error leyendo archivo: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Función principal"""
    archivo = '/media/klap/raid5/cursor_files/nakel/ventas/Listas de precios/Lista1.xls'
    
    if not os.path.exists(archivo):
        print(f"❌ Archivo no encontrado: {archivo}")
        return
    
    print("=" * 70)
    print("🔍 ANÁLISIS DE ESTRUCTURA - Lista1.xls")
    print("=" * 70)
    
    if HAS_PANDAS:
        df = analizar_excel_con_pandas(archivo)
        if df is not None:
            print("\n✅ Análisis completado exitosamente")
    else:
        print("❌ No se pudo analizar el archivo")

if __name__ == "__main__":
    main()

