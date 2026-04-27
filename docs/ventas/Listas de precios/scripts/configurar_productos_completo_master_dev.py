#!/usr/bin/env python3
"""
Script para configurar todos los productos en master_dev:
- Activar Ventas (sale_ok)
- Activar Compras (purchase_ok)
- Activar Puntos de Venta (available_in_pos)
- Configurar rutas de suministro (route_ids):
  * Belgrano 1: suministrar producto de Nakel Central
  * Belgrano 2: suministrar producto de Nakel Central
  * Belgrano 3: suministrar producto de Nakel Central
  * Belgrano 4: suministrar producto de Nakel Central
  * Nak: suministrar producto de Nakel Central
  * Buy (Comprar)
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

def obtener_rutas_requeridas(models, uid, password):
    """Obtiene los IDs de las rutas requeridas"""
    print("\n🛣️  Obteniendo rutas requeridas...")
    
    rutas_requeridas = [
        "Belgrano 1: suministrar producto de Nakel Central",
        "Belgrano 2: suministrar producto de Nakel Central",
        "Belgrano 3: suministrar producto de Nakel Central",
        "Belgrano 4: suministrar producto de Nakel Central",
        "Nak: suministrar producto de Nakel Central",
        "Buy"  # "Comprar" en Odoo se llama "Buy"
    ]
    
    rutas_ids = []
    
    for ruta_nombre in rutas_requeridas:
        try:
            route_ids = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'stock.route', 'search',
                [[('name', '=', ruta_nombre)]]
            )
            if route_ids:
                rutas_ids.append(route_ids[0])
                print(f"  ✅ {ruta_nombre} (ID: {route_ids[0]})")
            else:
                print(f"  ❌ {ruta_nombre} no encontrada")
        except Exception as e:
            print(f"  ❌ Error obteniendo ruta {ruta_nombre}: {e}")
    
    if len(rutas_ids) != len(rutas_requeridas):
        print(f"\n⚠️  ADVERTENCIA: Solo se encontraron {len(rutas_ids)} de {len(rutas_requeridas)} rutas requeridas")
    
    return rutas_ids

def obtener_todos_los_productos(models, uid, password):
    """Obtiene todos los productos activos de Odoo"""
    print("\n📦 Obteniendo todos los productos activos...")
    
    try:
        productos = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'product.template', 'search_read',
            [[('active', '=', True)]],
            {'fields': ['id', 'name', 'sale_ok', 'purchase_ok', 'available_in_pos', 'route_ids']}
        )
        
        print(f"✅ {len(productos)} productos encontrados")
        return productos
        
    except Exception as e:
        print(f"❌ Error obteniendo productos: {e}")
        import traceback
        traceback.print_exc()
        return []

def actualizar_producto(models, uid, password, producto, rutas_requeridas, dry_run=False):
    """Actualiza un producto con las configuraciones requeridas"""
    producto_id = producto['id']
    nombre = producto['name']
    
    # Verificar si necesita actualización
    necesita_actualizacion = False
    cambios = []
    
    # Verificar flags
    if not producto.get('sale_ok', False):
        necesita_actualizacion = True
        cambios.append('Ventas')
    
    if not producto.get('purchase_ok', False):
        necesita_actualizacion = True
        cambios.append('Compras')
    
    if not producto.get('available_in_pos', False):
        necesita_actualizacion = True
        cambios.append('Punto de Venta')
    
    # Verificar rutas
    rutas_actuales = set(producto.get('route_ids', []))
    rutas_requeridas_set = set(rutas_requeridas)
    
    rutas_faltantes = rutas_requeridas_set - rutas_actuales
    
    if rutas_faltantes:
        necesita_actualizacion = True
        cambios.append(f'Rutas faltantes: {len(rutas_faltantes)}')
    
    if not necesita_actualizacion:
        return False, None
    
    if dry_run:
        return True, {
            'nombre': nombre[:60],
            'cambios': cambios,
            'rutas_faltantes': len(rutas_faltantes)
        }
    
    # Realizar actualización
    try:
        # Combinar rutas actuales con las requeridas
        rutas_finales = list(rutas_actuales | rutas_requeridas_set)
        
        valores_actualizacion = {
            'sale_ok': True,
            'purchase_ok': True,
            'available_in_pos': True,
            'route_ids': [(6, 0, rutas_finales)]  # (6, 0, [ids]) reemplaza todas las rutas
        }
        
        models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'product.template', 'write',
            [[producto_id], valores_actualizacion]
        )
        
        return True, {
            'nombre': nombre[:60],
            'cambios': cambios,
            'rutas_faltantes': len(rutas_faltantes)
        }
        
    except Exception as e:
        print(f"   ❌ Error actualizando producto '{nombre[:50]}': {e}")
        return False, {'error': str(e)}

def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description='Configurar productos completos en master_dev')
    parser.add_argument('--dry-run', action='store_true', help='Modo dry-run (no realiza cambios)')
    parser.add_argument('--batch-size', type=int, default=100, help='Tamaño del lote para procesar (default: 100)')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("🚀 CONFIGURACIÓN COMPLETA DE PRODUCTOS EN MASTER_DEV")
    print("=" * 80)
    print(f"🔍 Modo: {'DRY-RUN' if args.dry_run else 'REAL'}")
    print("=" * 80)
    
    # Conectar a Odoo
    models, uid = conectar_odoo()
    if not models or not uid:
        print("\n❌ No se pudo conectar a Odoo")
        return
    
    password = ODOO_CONFIG['pass']
    
    # Obtener rutas requeridas
    rutas_requeridas = obtener_rutas_requeridas(models, uid, password)
    
    if not rutas_requeridas:
        print("\n❌ No se pudieron obtener las rutas requeridas")
        return
    
    if len(rutas_requeridas) < 6:
        print(f"\n⚠️  ADVERTENCIA: Se esperaban 6 rutas, se encontraron {len(rutas_requeridas)}")
        respuesta = input("¿Deseas continuar de todos modos? (s/n): ")
        if respuesta.lower() != 's':
            print("❌ Operación cancelada")
            return
    
    # Obtener todos los productos
    productos = obtener_todos_los_productos(models, uid, password)
    
    if not productos:
        print("\n❌ No se encontraron productos")
        return
    
    # Estadísticas iniciales
    productos_actualizados = 0
    productos_sin_cambios = 0
    errores = 0
    
    print(f"\n📋 Procesando {len(productos)} productos...")
    
    if args.dry_run:
        print("\n🔍 MODO DRY-RUN - No se realizarán cambios\n")
    
    # Procesar productos por lotes
    for i, producto in enumerate(productos, 1):
        necesita_actualizacion, resultado = actualizar_producto(
            models, uid, password, producto, rutas_requeridas, dry_run=args.dry_run
        )
        
        if necesita_actualizacion:
            productos_actualizados += 1
            
            # Mostrar progreso cada batch_size productos
            if productos_actualizados % args.batch_size == 0 or productos_actualizados <= 10:
                if resultado and 'error' not in resultado:
                    print(f"   🔄 [{productos_actualizados}] {resultado['nombre']}...")
                    if resultado.get('rutas_faltantes', 0) > 0:
                        print(f"      → Agregando {resultado['rutas_faltantes']} rutas")
                elif resultado and 'error' in resultado:
                    errores += 1
        else:
            productos_sin_cambios += 1
        
        # Mostrar progreso general cada 500 productos
        if i % 500 == 0:
            print(f"   📊 Procesados {i}/{len(productos)} productos...")
    
    # Resumen final
    print("\n" + "=" * 80)
    print("📊 RESUMEN")
    print("=" * 80)
    print(f"✅ Productos actualizados: {productos_actualizados}")
    print(f"✓  Productos sin cambios (ya configurados): {productos_sin_cambios}")
    print(f"❌ Errores: {errores}")
    print(f"📦 Total productos procesados: {len(productos)}")
    
    if args.dry_run:
        print(f"\n💡 Ejecuta sin --dry-run para aplicar los cambios")
    else:
        print(f"\n✅ Proceso completado")
        print(f"\n📋 Configuraciones aplicadas:")
        print(f"   • Ventas (sale_ok): ✅")
        print(f"   • Compras (purchase_ok): ✅")
        print(f"   • Puntos de Venta (available_in_pos): ✅")
        print(f"   • Rutas de suministro: {len(rutas_requeridas)} rutas configuradas")

if __name__ == "__main__":
    main()

