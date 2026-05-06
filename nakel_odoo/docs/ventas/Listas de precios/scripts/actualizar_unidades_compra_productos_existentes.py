#!/usr/bin/env python3
"""
Script para actualizar unidades de compra en productos existentes desde Excel
Actualiza productos que ya fueron creados pero no tienen unidad de compra asignada
Autor: Corolla
Fecha: 2025-12-27
"""

import os
import sys
import csv
import subprocess
import xmlrpc.client
from datetime import datetime

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

# Importar funciones compartidas del script principal
sys.path.insert(0, script_dir)
from crear_productos_faltantes_desde_excel import (
    convertir_excel_a_csv_con_libreoffice,
    leer_lista_precios_excel,
    obtener_unidad_compra_por_cxb,
    conectar_odoo
)

def main():
    """Función principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Actualizar unidades de compra en productos existentes')
    parser.add_argument('--lista', default='Lista1.xls', help='Nombre del archivo Excel')
    parser.add_argument('--dry-run', action='store_true', help='Modo dry-run (no realiza cambios)')
    
    args = parser.parse_args()
    
    archivo_excel = os.path.join(DIRECTORIO_LISTAS, args.lista)
    
    print("=" * 80)
    print("🔧 ACTUALIZACIÓN DE UNIDADES DE COMPRA EN PRODUCTOS EXISTENTES")
    print("=" * 80)
    print(f"📁 Archivo Excel: {args.lista}")
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
    
    # Crear diccionario de productos Excel por código
    productos_excel_por_codigo = {}
    for producto in productos_excel:
        codigo = producto.get('Codigo', '').strip()
        if codigo:
            productos_excel_por_codigo[codigo] = producto
    
    print(f"✅ {len(productos_excel_por_codigo)} productos con código en Excel")
    
    # Buscar productos en Odoo que necesitan actualización
    print("\n🔍 Buscando productos que necesitan actualización...")
    
    # Obtener todos los productos activos
    productos_odoo = models.execute_kw(
        ODOO_CONFIG['db'], uid, password,
        'product.template', 'search_read',
        [[('active', '=', True)]],
        {'fields': ['id', 'name', 'default_code', 'uom_po_id']}
    )
    
    productos_a_actualizar = []
    uom_cache = {}
    
    for producto_odoo in productos_odoo:
        codigo_raw = producto_odoo.get('default_code')
        if not codigo_raw or codigo_raw is False:
            continue
        codigo = str(codigo_raw).strip()
        if not codigo or codigo not in productos_excel_por_codigo:
            continue
        
        producto_excel = productos_excel_por_codigo[codigo]
        cxb = producto_excel.get('CxB', '')
        
        if not cxb or str(cxb).strip() == '':
            continue
        
        # Obtener unidad de compra esperada
        uom_po_esperada = obtener_unidad_compra_por_cxb(models, uid, password, cxb, uom_cache)
        
        # Verificar unidad actual
        uom_po_actual = producto_odoo.get('uom_po_id')
        uom_po_actual_id = uom_po_actual[0] if uom_po_actual else 1
        
        if uom_po_actual_id != uom_po_esperada:
            productos_a_actualizar.append({
                'producto_id': producto_odoo['id'],
                'codigo': codigo,
                'nombre': producto_odoo['name'],
                'uom_actual_id': uom_po_actual_id,
                'uom_esperada_id': uom_po_esperada,
                'cxb': cxb
            })
    
    print(f"📊 Productos a actualizar: {len(productos_a_actualizar)}")
    
    if not productos_a_actualizar:
        print("\n✅ No hay productos que necesiten actualización.")
        return
    
    if args.dry_run:
        print(f"\n🔍 MODO DRY-RUN - No se realizarán cambios")
        print(f"\n📋 Primeros 20 productos que se actualizarían:")
        for i, p in enumerate(productos_a_actualizar[:20], 1):
            # Obtener nombres de unidades
            uom_actual = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'uom.uom', 'search_read',
                [[('id', '=', p['uom_actual_id'])]],
                {'fields': ['name']}
            )
            uom_esperada = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'uom.uom', 'search_read',
                [[('id', '=', p['uom_esperada_id'])]],
                {'fields': ['name']}
            )
            uom_actual_name = uom_actual[0]['name'] if uom_actual else 'N/A'
            uom_esperada_name = uom_esperada[0]['name'] if uom_esperada else 'N/A'
            
            print(f"   {i:3d}. [{p['codigo']}] {p['nombre'][:50]}")
            print(f"        CxB: {p['cxb']} | Actual: {uom_actual_name} → Nueva: {uom_esperada_name}")
        
        if len(productos_a_actualizar) > 20:
            print(f"   ... y {len(productos_a_actualizar) - 20} más")
        
        print(f"\n💡 Ejecuta sin --dry-run para actualizar {len(productos_a_actualizar)} productos")
        return
    
    # Actualizar productos
    print(f"\n📋 Actualizando {len(productos_a_actualizar)} productos...")
    
    actualizados = 0
    errores = 0
    
    for i, p in enumerate(productos_a_actualizar, 1):
        if i % 50 == 0:
            print(f"   🔄 Procesados {i}/{len(productos_a_actualizar)}...")
        
        try:
            # Actualizar unidad de compra
            models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'product.template', 'write',
                [[p['producto_id']], {'uom_po_id': p['uom_esperada_id']}]
            )
            actualizados += 1
        except Exception as e:
            print(f"   ⚠️  Error actualizando producto {p['codigo']}: {e}")
            errores += 1
    
    print("\n" + "=" * 80)
    print("📊 RESUMEN")
    print("=" * 80)
    print(f"✅ Productos actualizados: {actualizados}")
    print(f"❌ Errores: {errores}")
    print(f"\n✅ Proceso completado")

if __name__ == "__main__":
    main()

