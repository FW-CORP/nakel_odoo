#!/usr/bin/env python3
"""
Script para corregir discrepancias de cantidad de embalajes usando UNID_BULTO de MSSQL GESTION
- Identifica productos con discrepancias entre qty (Odoo) y UNID_BULTO (MSSQL)
- Actualiza el qty del embalaje con el valor de UNID_BULTO de MSSQL
- Omite lo que diga el nombre del artículo (solo usa UNID_BULTO de MSSQL)
Autor: Corolla
Fecha: 2025-12-27
"""

import sys
import os
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

def obtener_productos_con_discrepancias(models, uid, password, conn):
    """Identifica productos con discrepancias de cantidad entre Odoo y MSSQL"""
    print("\n🔍 Identificando productos con discrepancias...")
    
    discrepancias = []
    
    # Obtener productos de Odoo con embalajes
    offset = 0
    batch_size = 1000
    
    while True:
        productos_odoo = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'product.template', 'search_read',
            [[('active', '=', True), ('packaging_ids', '!=', False)]],
            {
                'fields': ['id', 'name', 'default_code', 'barcode', 'packaging_ids'],
                'offset': offset,
                'limit': batch_size
            }
        )
        
        if not productos_odoo:
            break
        
        # Obtener códigos de barras de este lote
        barcodes = [p['barcode'] for p in productos_odoo if p.get('barcode')]
        
        if barcodes and conn:
            # Obtener UNID_BULTO de MSSQL para estos productos
            cursor = conn.cursor()
            placeholders = ','.join('?' * len(barcodes))
            query = f"""
            SELECT 
                a.COD_ARTICULO,
                a.UNID_BULTO,
                ap.PLU
            FROM ARTICULOS a
            INNER JOIN ARTICULOPLU ap ON a.ID_ARTICULO = ap.ID_ARTICULO
            WHERE ap.PLU IN ({placeholders})
            AND a.UNID_BULTO IS NOT NULL
            AND a.UNID_BULTO > 0
            """
            cursor.execute(query, *barcodes)
            
            mssql_data = {}
            for row in cursor.fetchall():
                plu = row[2].strip() if row[2] else None
                if plu:
                    mssql_data[plu] = {
                        'codigo': row[0].strip() if row[0] else None,
                        'unid_bulto': int(row[1]) if row[1] else None
                    }
            
            # Comparar con Odoo
            for producto in productos_odoo:
                barcode = producto.get('barcode')
                if not barcode or barcode not in mssql_data:
                    continue
                
                unid_bulto_mssql = mssql_data[barcode]['unid_bulto']
                
                # Obtener embalaje de Odoo
                packaging_ids = producto.get('packaging_ids', [])
                if packaging_ids:
                    try:
                        packagings = models.execute_kw(
                            ODOO_CONFIG['db'], uid, password,
                            'product.packaging', 'read',
                            [packaging_ids[0]],  # Primer embalaje
                            {'fields': ['id', 'name', 'qty']}
                        )
                        
                        if packagings:
                            pack = packagings[0]
                            qty_odoo = pack.get('qty', 0)
                            
                            # Verificar discrepancia
                            if abs(qty_odoo - unid_bulto_mssql) > 0.01:
                                discrepancias.append({
                                    'producto_id': producto['id'],
                                    'nombre': producto['name'],
                                    'codigo': producto.get('default_code'),
                                    'barcode': barcode,
                                    'embalaje_id': pack['id'],
                                    'nombre_embalaje': pack.get('name', ''),
                                    'qty_actual': qty_odoo,
                                    'unid_bulto_mssql': unid_bulto_mssql,
                                    'diferencia': abs(qty_odoo - unid_bulto_mssql)
                                })
                    except Exception as e:
                        pass  # Continuar con siguiente producto
        
        offset += batch_size
        
        if len(productos_odoo) < batch_size:
            break
    
    print(f"✅ {len(discrepancias)} discrepancias encontradas")
    return discrepancias

def corregir_discrepancias(models, uid, password, discrepancias, dry_run=True):
    """Corrige las discrepancias actualizando qty con UNID_BULTO de MSSQL"""
    print(f"\n{'🧪 MODO DRY-RUN' if dry_run else '⚠️  MODO REAL'}: Corrigiendo discrepancias...")
    
    corregidos = 0
    errores = 0
    
    # Ordenar por diferencia (mayores primero)
    discrepancias_ordenadas = sorted(discrepancias, key=lambda x: x['diferencia'], reverse=True)
    
    for i, disc in enumerate(discrepancias_ordenadas, 1):
        embalaje_id = disc['embalaje_id']
        qty_actual = disc['qty_actual']
        unid_bulto_mssql = disc['unid_bulto_mssql']
        nombre_producto = disc['nombre']
        
        # Mostrar progreso cada 10 o primeros 10
        if i <= 10 or i % 10 == 0:
            print(f"   [{i}/{len(discrepancias_ordenadas)}] {nombre_producto[:50]}...")
            print(f"      {qty_actual} → {unid_bulto_mssql} unidades (diferencia: {disc['diferencia']})")
        
        if dry_run:
            corregidos += 1
        else:
            try:
                # Actualizar embalaje
                nombre_embalaje = f"Bulto x{unid_bulto_mssql}"
                
                models.execute_kw(
                    ODOO_CONFIG['db'], uid, password,
                    'product.packaging', 'write',
                    [[embalaje_id], {
                        'qty': float(unid_bulto_mssql),
                        'name': nombre_embalaje
                    }]
                )
                corregidos += 1
            except Exception as e:
                print(f"      ❌ Error corrigiendo producto ID {disc['producto_id']}: {e}")
                errores += 1
    
    print(f"\n📊 RESUMEN DE CORRECCIÓN:")
    print(f"   ✅ Corregidos: {corregidos}")
    print(f"   ❌ Errores: {errores}")
    print(f"   📦 Total procesados: {len(discrepancias_ordenadas)}")
    
    return corregidos, errores

def main():
    """Función principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Corregir discrepancias de cantidad de embalajes desde MSSQL')
    parser.add_argument('--dry-run', action='store_true', help='Modo dry-run (no realiza cambios)')
    
    args = parser.parse_args()
    
    print("="*80)
    print("🔧 CORRECCIÓN DE DISCREPANCIAS DE CANTIDAD DE EMBALAJES")
    print("="*80)
    print(f"📊 Base de datos: {ODOO_CONFIG['db']}")
    print(f"🔍 Modo: {'DRY-RUN' if args.dry_run else 'REAL'}")
    print(f"📋 Fuente: UNID_BULTO de MSSQL GESTION")
    print("="*80)
    
    # Conectar a Odoo
    models, uid = conectar_odoo()
    if not models or not uid:
        return
    
    password = ODOO_CONFIG['pass']
    
    # Conectar a MSSQL
    print("\n🔌 Conectando a MSSQL...")
    conn = conectar_mssql()
    if not conn:
        print("\n❌ No se pudo conectar a MSSQL")
        return
    
    # Identificar discrepancias
    discrepancias = obtener_productos_con_discrepancias(models, uid, password, conn)
    
    conn.close()
    
    if not discrepancias:
        print("\n✅ No se encontraron discrepancias. Todos los embalajes coinciden con MSSQL.")
        return
    
    # Mostrar resumen de discrepancias
    print(f"\n📋 DISCREPANCIAS ENCONTRADAS: {len(discrepancias)}")
    print(f"\n📊 Top 10 discrepancias:")
    discrepancias_ordenadas = sorted(discrepancias, key=lambda x: x['diferencia'], reverse=True)
    for i, disc in enumerate(discrepancias_ordenadas[:10], 1):
        print(f"   {i}. {disc['nombre'][:50]}")
        print(f"      Código: {disc.get('codigo', 'N/A')}")
        print(f"      Actual: {disc['qty_actual']} → Correcto: {disc['unid_bulto_mssql']} unidades")
        print(f"      Diferencia: {disc['diferencia']} unidades")
    
    # Corregir
    corregidos, errores = corregir_discrepancias(models, uid, password, discrepancias, dry_run=args.dry_run)
    
    print("\n" + "="*80)
    print("✅ PROCESO COMPLETADO")
    print("="*80)
    
    if args.dry_run:
        print("\n💡 Ejecuta sin --dry-run para aplicar las correcciones")
    else:
        print(f"\n✅ {corregidos} embalajes corregidos usando UNID_BULTO de MSSQL GESTION")

if __name__ == "__main__":
    main()

