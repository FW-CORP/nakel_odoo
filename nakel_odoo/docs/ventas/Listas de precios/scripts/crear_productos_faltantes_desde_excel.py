#!/usr/bin/env python3
"""
Script para crear productos faltantes en Odoo desde archivo Excel
- Crea productos que no existen en Odoo
- Asigna categorías basadas en "Nombre Rubro"
- Establece código de referencia interna (Codigo del Excel)
- Activa para Ventas, Compras y Puntos de Venta
- Agrega precios a la lista de precios
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

def convertir_precio_argentino(precio_str):
    """Convierte un precio en formato argentino (comas como decimales) a float"""
    if not precio_str:
        return None
    try:
        precio_limpio = precio_str.strip().replace('.', '').replace(',', '.')
        return float(precio_limpio)
    except (ValueError, AttributeError):
        return None

def convertir_precio_unitario_sin_iva(precio_str):
    """Convierte precio unitario (con IVA) a precio sin IVA (21%)
    Toma el precio de la columna 'Unitario' y le quita el IVA del 21%
    Fórmula: precio_sin_iva = precio_unitario / 1.21
    """
    precio_con_iva = convertir_precio_argentino(precio_str)
    if precio_con_iva is None:
        return None
    
    # Quitar IVA del 21%: dividir por 1.21
    precio_sin_iva = precio_con_iva / 1.21
    return round(precio_sin_iva, 2)

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

def obtener_o_crear_categoria(models, uid, password, nombre_rubro):
    """Obtiene o crea una categoría de producto basada en el nombre del rubro"""
    if not nombre_rubro or not nombre_rubro.strip():
        nombre_rubro = "Sin Categoría"
    
    nombre_rubro = nombre_rubro.strip()
    
    try:
        # Buscar categoría existente
        categorias = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'product.category', 'search_read',
            [[('name', '=', nombre_rubro)]],
            {'fields': ['id', 'name']}
        )
        
        if categorias:
            return categorias[0]['id']
        
        # Crear nueva categoría
        valores_categoria = {
            'name': nombre_rubro,
            'parent_id': False  # Categoría raíz
        }
        
        categoria_id = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'product.category', 'create',
            [valores_categoria]
        )
        
        print(f"   ✅ Categoría creada: '{nombre_rubro}' (ID: {categoria_id})")
        return categoria_id
        
    except Exception as e:
        print(f"   ⚠️  Error obteniendo/creando categoría '{nombre_rubro}': {e}")
        # Retornar categoría por defecto (All / Todas)
        return 1

def obtener_unidad_compra_por_cxb(models, uid, password, cxb_value, uom_cache={}):
    """Obtiene la unidad de medida de compra basada en CxB (Cantidad por Bulto)"""
    try:
        # Convertir CxB a entero
        if not cxb_value or str(cxb_value).strip() == '':
            return 1  # Units por defecto
        
        try:
            cxb = int(float(str(cxb_value).strip()))
        except (ValueError, TypeError):
            return 1  # Units por defecto
        
        # Si CxB = 1, usar Units
        if cxb == 1:
            return 1  # Units
        
        # Buscar en cache primero
        if cxb in uom_cache:
            return uom_cache[cxb]
        
        # Buscar unidad "Bulto x{cxb}" en Odoo
        nombre_uom = f"Bulto x{cxb}"
        
        uoms = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'uom.uom', 'search_read',
            [[('name', '=', nombre_uom)]],
            {'fields': ['id', 'name']}
        )
        
        if uoms:
            uom_id = uoms[0]['id']
            uom_cache[cxb] = uom_id
            return uom_id
        
        # Si no existe, intentar con variantes del nombre
        # Ejemplo: "Bulto X18" vs "Bulto x18"
        nombre_uom_variantes = [
            f"Bulto X{cxb}",  # Con X mayúscula
            f"Bulto x {cxb}",  # Con espacio
            f"Bulto X {cxb}",  # Con X mayúscula y espacio
        ]
        
        for nombre_var in nombre_uom_variantes:
            uoms = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'uom.uom', 'search_read',
                [[('name', '=', nombre_var)]],
                {'fields': ['id', 'name']}
            )
            if uoms:
                uom_id = uoms[0]['id']
                uom_cache[cxb] = uom_id
                return uom_id
        
        # Si no se encuentra, usar Units por defecto
        # (No creamos la unidad automáticamente, se debe crear manualmente si es necesario)
        print(f"   ⚠️  Unidad 'Bulto x{cxb}' no encontrada, usando Units por defecto")
        return 1  # Units por defecto
        
    except Exception as e:
        print(f"   ⚠️  Error obteniendo unidad de compra para CxB={cxb_value}: {e}")
        return 1  # Units por defecto

def identificar_productos_no_mapeados(productos_excel, productos_odoo):
    """Identifica productos del Excel que no existen en Odoo"""
    # Crear índices de Odoo
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
    productos_faltantes = []
    
    for producto_excel in productos_excel:
        codigo_excel = producto_excel.get('Codigo')
        descripcion_excel = producto_excel.get('Descripcion')
        
        if not codigo_excel and not descripcion_excel:
            continue
        
        # Verificar si existe por código
        existe = False
        if codigo_excel:
            codigo_limpio = codigo_excel.strip()
            if codigo_limpio in odoo_por_codigo:
                existe = True
        
        # Verificar si existe por nombre exacto
        if not existe and descripcion_excel:
            nombre_limpio = descripcion_excel.strip()
            if nombre_limpio in odoo_por_nombre_exacto:
                existe = True
        
        if not existe:
            productos_faltantes.append(producto_excel)
    
    return productos_faltantes

def crear_producto_en_odoo(models, uid, password, producto_excel, categoria_id, uom_po_id):
    """Crea un producto en Odoo"""
    try:
        codigo = producto_excel.get('Codigo', '').strip()
        descripcion = producto_excel.get('Descripcion', '').strip()
        precio_excel_str = producto_excel.get('Unitario', '')
        precio = convertir_precio_unitario_sin_iva(precio_excel_str)
        
        if not descripcion:
            return None
        
        # Valores del producto
        valores_producto = {
            'name': descripcion,
            'default_code': codigo if codigo else False,
            'categ_id': categoria_id,
            'list_price': precio if precio else 0.0,
            'uom_id': 1,  # Unidad de medida (venta) - Units por defecto
            'uom_po_id': uom_po_id,  # Unidad de compra (basada en CxB)
            'sale_ok': True,  # Disponible para ventas
            'purchase_ok': True,  # Disponible para compras
            'available_in_pos': True,  # Disponible en puntos de venta (Odoo 18)
            'type': 'consu',  # Tipo: consumible (producto no almacenable)
            'active': True
        }
        
        # Crear producto
        producto_id = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'product.template', 'create',
            [valores_producto]
        )
        
        return producto_id
        
    except Exception as e:
        print(f"   ❌ Error creando producto '{descripcion[:50]}': {e}")
        import traceback
        traceback.print_exc()
        return None

def agregar_precio_a_lista(models, uid, password, lista_id, producto_id, precio):
    """Agrega un precio a una lista de precios"""
    try:
        valores_item = {
            'pricelist_id': lista_id,
            'product_tmpl_id': producto_id,
            'fixed_price': precio,
            'applied_on': '1_product'
        }
        
        item_id = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'product.pricelist.item', 'create',
            [valores_item]
        )
        
        return item_id
    except Exception as e:
        print(f"   ⚠️  Error agregando precio a lista: {e}")
        return None

def obtener_lista_odoo(models, uid, password, nombre_lista):
    """Obtiene una lista de precios de Odoo por nombre"""
    try:
        listas = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'product.pricelist', 'search_read',
            [[('name', '=', nombre_lista)]],
            {'fields': ['id', 'name']}
        )
        
        if listas:
            return listas[0]
        return None
    except Exception as e:
        print(f"❌ Error obteniendo lista: {e}")
        return None

def main():
    """Función principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Crear productos faltantes desde Excel')
    parser.add_argument('--lista', default='Lista1.xls', help='Nombre del archivo Excel')
    parser.add_argument('--nombre-lista-odoo', default='Lista 1', help='Nombre de la lista en Odoo')
    parser.add_argument('--dry-run', action='store_true', help='Modo dry-run (no realiza cambios)')
    
    args = parser.parse_args()
    
    archivo_excel = os.path.join(DIRECTORIO_LISTAS, args.lista)
    
    print("=" * 80)
    print("🚀 CREACIÓN DE PRODUCTOS FALTANTES DESDE EXCEL")
    print("=" * 80)
    print(f"📁 Archivo Excel: {args.lista}")
    print(f"📋 Lista Odoo: {args.nombre_lista_odoo}")
    print(f"🔍 Modo: {'DRY-RUN' if args.dry_run else 'REAL'}")
    print("=" * 80)
    
    # Leer productos del Excel
    print(f"\n📋 Leyendo productos del Excel...")
    productos_excel = leer_lista_precios_excel(archivo_excel)
    
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
    
    # Extraer productos existentes de Odoo
    print("📦 Extrayendo productos existentes de Odoo...")
    productos_odoo = models.execute_kw(
        ODOO_CONFIG['db'], uid, password,
        'product.template', 'search_read',
        [[('active', '=', True)]],
        {'fields': ['id', 'name', 'default_code', 'active']}
    )
    print(f"✅ {len(productos_odoo)} productos existentes en Odoo")
    
    # Identificar productos faltantes
    print("\n🔍 Identificando productos faltantes...")
    productos_faltantes = identificar_productos_no_mapeados(productos_excel, productos_odoo)
    print(f"📊 Productos faltantes: {len(productos_faltantes)}")
    
    if not productos_faltantes:
        print("\n✅ No hay productos faltantes. Todos los productos ya existen en Odoo.")
        return
    
    # Obtener lista de precios
    lista_odoo = obtener_lista_odoo(models, uid, password, args.nombre_lista_odoo)
    if not lista_odoo:
        print(f"\n❌ No se encontró la lista '{args.nombre_lista_odoo}' en Odoo")
        return
    
    lista_id = lista_odoo['id']
    print(f"✅ Lista encontrada: '{lista_odoo['name']}' (ID: {lista_id})")
    
    if args.dry_run:
        print(f"\n🔍 MODO DRY-RUN - No se realizarán cambios")
    
    # Procesar productos faltantes
    print(f"\n📋 Procesando {len(productos_faltantes)} productos faltantes...")
    
    categorias_creadas = {}
    productos_creados = 0
    precios_agregados = 0
    errores = 0
    uom_cache = {}  # Cache para unidades de medida de compra
    
    for i, producto_excel in enumerate(productos_faltantes, 1):
        descripcion = producto_excel.get('Descripcion', '')[:60]
        codigo = producto_excel.get('Codigo', 'N/A')
        rubro = producto_excel.get('Nombre Rubro', 'Sin Categoría')
        cxb = producto_excel.get('CxB', '')
        precio_excel_str = producto_excel.get('Unitario', '')
        precio = convertir_precio_unitario_sin_iva(precio_excel_str)
        
        if i % 50 == 0 or i <= 5:
            print(f"\n   🔄 [{i}/{len(productos_faltantes)}] {descripcion}...")
        
        # Obtener unidad de compra basada en CxB
        uom_po_id = obtener_unidad_compra_por_cxb(models, uid, password, cxb, uom_cache)
        uom_po_nombre = "Units" if uom_po_id == 1 else f"Bulto x{cxb}" if cxb else "Units"
        
        if args.dry_run:
            print(f"      [DRY-RUN] Se crearía producto: {descripcion}")
            print(f"                Código: {codigo} | Rubro: {rubro} | CxB: {cxb} | UOM Compra: {uom_po_nombre} | Precio: {precio_excel_str}")
            productos_creados += 1
            continue
        
        # Obtener o crear categoría
        if rubro not in categorias_creadas:
            categoria_id = obtener_o_crear_categoria(models, uid, password, rubro)
            categorias_creadas[rubro] = categoria_id
        else:
            categoria_id = categorias_creadas[rubro]
        
        # Crear producto con unidad de compra
        producto_id = crear_producto_en_odoo(models, uid, password, producto_excel, categoria_id, uom_po_id)
        
        if producto_id:
            productos_creados += 1
            
            # Agregar precio a la lista
            if precio and precio > 0:
                item_id = agregar_precio_a_lista(models, uid, password, lista_id, producto_id, precio)
                if item_id:
                    precios_agregados += 1
        else:
            errores += 1
    
    print("\n" + "=" * 80)
    print("📊 RESUMEN")
    print("=" * 80)
    print(f"✅ Productos creados: {productos_creados}")
    print(f"💰 Precios agregados a lista: {precios_agregados}")
    print(f"📁 Categorías procesadas: {len(categorias_creadas)}")
    if uom_cache:
        uom_unicas = set(uom_cache.values())
        print(f"📦 Unidades de compra únicas utilizadas: {len(uom_unicas)}")
    print(f"❌ Errores: {errores}")
    
    if args.dry_run:
        print(f"\n💡 Ejecuta sin --dry-run para crear los productos")
    else:
        print(f"\n✅ Proceso completado")
        print(f"💡 Ahora puedes ejecutar la migración de precios para actualizar la lista completa")

if __name__ == "__main__":
    main()

