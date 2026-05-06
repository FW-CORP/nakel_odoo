#!/usr/bin/env python3
"""
Script para actualizar el template de Remito en master_18
Cambia la columna "Lote" por "Cant. Bultos"
"""

import sys
import os
import xmlrpc.client

sys.path.insert(0, '/media/klap/raid5/cursor_files')

try:
    from config_nakel import ODOO_CONFIG_MASTER18
except ImportError:
    print("❌ Error: No se pudo importar config_nakel.py")
    sys.exit(1)

ODOO_CONFIG = {
    'url': ODOO_CONFIG_MASTER18['url'],
    'db': ODOO_CONFIG_MASTER18['db'],
    'user': ODOO_CONFIG_MASTER18['username'],
    'pass': ODOO_CONFIG_MASTER18['password']
}

def leer_template():
    """Lee el template actualizado desde el archivo"""
    template_path = '/media/klap/raid5/cursor_files/nakel/qweb/templates/stock.report_delivery_document_nakel_2024_MEJORADO.xml'
    
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            contenido = f.read()
        
        # Extraer solo el contenido del template (sin comentarios iniciales)
        inicio = contenido.find('<t t-name="stock.report_delivery_document_nakel_2024">')
        if inicio == -1:
            print("❌ No se encontró el inicio del template")
            return None
        
        arch_content = contenido[inicio:].strip()
        return arch_content
    except Exception as e:
        print(f"❌ Error leyendo template: {e}")
        return None

def actualizar_template():
    """Actualiza el template en Odoo"""
    print("="*80)
    print("📝 ACTUALIZACIÓN DE TEMPLATE REMITO - CAMBIO A CANT. BULTOS")
    print("="*80)
    print(f"📊 Base de datos: {ODOO_CONFIG['db']}")
    print("="*80)
    
    # Conectar a Odoo
    try:
        common = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/common')
        uid = common.authenticate(ODOO_CONFIG['db'], ODOO_CONFIG['user'], ODOO_CONFIG['pass'], {})
        if not uid:
            print("❌ Error de autenticación")
            return False
        
        models = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/object')
        password = ODOO_CONFIG['pass']
        db = ODOO_CONFIG['db']
        
        print("✅ Conexión exitosa a Odoo")
    except Exception as e:
        print(f"❌ Error conectando a Odoo: {e}")
        return False
    
    # Leer template actualizado
    arch_content = leer_template()
    if not arch_content:
        return False
    
    # Buscar template en Odoo
    template_key = 'stock.report_delivery_document_nakel_2024'
    templates = models.execute_kw(
        db, uid, password,
        'ir.ui.view', 'search_read',
        [[('key', '=', template_key), ('type', '=', 'qweb')]],
        {'fields': ['id', 'name', 'key']}
    )
    
    if not templates:
        print(f"❌ Template '{template_key}' no encontrado en Odoo")
        print("💡 Ejecuta primero instalar_templates_todos_master18.py para crear el template")
        return False
    
    template = templates[0]
    print(f"📋 Template encontrado: {template['name']} (ID: {template['id']})")
    
    # Actualizar template
    try:
        models.execute_kw(
            db, uid, password,
            'ir.ui.view', 'write',
            [[template['id']], {'arch': arch_content}]
        )
        print("✅ Template actualizado correctamente")
        print("📝 Cambios aplicados:")
        print("   • Columna 'Lote' eliminada")
        print("   • Columna 'Cant. Bultos' agregada")
        print("   • Calcula cantidad de bultos desde product_packaging_qty o product_packaging_id.qty")
        return True
    except Exception as e:
        print(f"❌ Error actualizando template: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = actualizar_template()
    if success:
        print("\n" + "="*80)
        print("✅ ACTUALIZACIÓN COMPLETADA")
        print("="*80)
        print("💡 Los próximos remitos generados mostrarán 'Cant. Bultos' en lugar de 'Lote'")
    else:
        print("\n" + "="*80)
        print("❌ ACTUALIZACIÓN FALLIDA")
        print("="*80)
        sys.exit(1)

