#!/usr/bin/env python3
"""
Script para verificar qué template se está usando realmente en los reportes de proforma y cotización
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

def main():
    print("="*80)
    print("🔍 VERIFICACIÓN DE TEMPLATES DE PROFORMA Y COTIZACIÓN")
    print("="*80)
    
    try:
        common = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/common')
        uid = common.authenticate(ODOO_CONFIG['db'], ODOO_CONFIG['user'], ODOO_CONFIG['pass'], {})
        if not uid:
            print("❌ Error de autenticación")
            return
        
        models = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/object')
        password = ODOO_CONFIG['pass']
        db = ODOO_CONFIG['db']
        
        print("✅ Conexión exitosa a Odoo\n")
    except Exception as e:
        print(f"❌ Error conectando a Odoo: {e}")
        return
    
    # 1. Verificar templates
    print("="*80)
    print("📋 TEMPLATES DISPONIBLES")
    print("="*80)
    
    templates_keys = [
        'sale.report_saleorder_pro_forma',  # Proforma
        'sale.report_saleorder',  # Cotización normal
        'sale.report_saleorder_document',  # Documento base
    ]
    
    for key in templates_keys:
        templates = models.execute_kw(db, uid, password, 'ir.ui.view', 'search_read', 
            [[('key', '=', key), ('type', '=', 'qweb')]], 
            {'fields': ['id', 'name', 'key', 'priority'], 'order': 'priority desc', 'limit': 1})
        if templates:
            t = templates[0]
            arch = models.execute_kw(db, uid, password, 'ir.ui.view', 'read', 
                [[t['id']]], {'fields': ['arch']})[0].get('arch', '')
            tiene_nakel = 'NAKEL' in arch
            print(f"\n✅ {key}")
            print(f"   ID: {t['id']}, Priority: {t.get('priority', 0)}")
            print(f"   Tiene NAKEL: {'✅ SÍ' if tiene_nakel else '❌ NO'}")
        else:
            print(f"\n❌ {key}: NO ENCONTRADO")
    
    # 2. Verificar reportes
    print("\n" + "="*80)
    print("📄 REPORTES DISPONIBLES PARA SALE.ORDER")
    print("="*80)
    
    reportes = models.execute_kw(db, uid, password, 'ir.actions.report', 'search_read', 
        [[('model', '=', 'sale.order')]], 
        {'fields': ['id', 'name', 'report_name', 'report_type'], 'limit': 10})
    
    for r in reportes:
        print(f"\n📄 {r.get('name', 'N/A')}")
        print(f"   ID: {r['id']}, Report Name: {r.get('report_name', 'N/A')}")
        print(f"   Tipo: {r.get('report_type', 'N/A')}")
        
        # Verificar si el template existe
        report_name = r.get('report_name', '')
        if report_name:
            template_exists = models.execute_kw(db, uid, password, 'ir.ui.view', 'search', 
                [[('key', '=', report_name), ('type', '=', 'qweb')]], {'limit': 1})
            if template_exists:
                template_info = models.execute_kw(db, uid, password, 'ir.ui.view', 'read', 
                    [[template_exists[0]]], {'fields': ['priority', 'arch']})[0]
                tiene_nakel = 'NAKEL' in template_info.get('arch', '')
                print(f"   ✅ Template existe (Priority: {template_info.get('priority', 0)})")
                print(f"   Tiene NAKEL: {'✅ SÍ' if tiene_nakel else '❌ NO'}")
            else:
                print(f"   ❌ Template NO existe")
    
    print("\n" + "="*80)
    print("💡 RECOMENDACIONES")
    print("="*80)
    print("1. Para ver la FACTURA PROFORMA mejorada, usa el reporte 'PRO-FORMA Invoice'")
    print("2. Si estás viendo 'PDF Quote', ese usa el template de cotización normal (sale.report_saleorder)")
    print("3. Si no ves los cambios, prueba:")
    print("   - Limpiar caché del navegador (Ctrl+Shift+R)")
    print("   - Reiniciar Odoo para limpiar caché de templates")
    print("   - Asegurarte de estar usando el reporte correcto")

if __name__ == "__main__":
    main()

