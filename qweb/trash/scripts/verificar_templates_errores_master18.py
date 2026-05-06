#!/usr/bin/env python3
"""
Script para verificar si hay errores en los templates instalados
Revisa si los templates tienen problemas de sintaxis o referencias rotas
"""

import sys
import os
import xmlrpc.client
import logging

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

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def conectar_odoo():
    """Conecta a Odoo"""
    try:
        common = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/common')
        uid = common.authenticate(ODOO_CONFIG['db'], ODOO_CONFIG['user'], ODOO_CONFIG['pass'], {})
        if not uid:
            return None, None
        models = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/object')
        return models, uid
    except Exception as e:
        logging.error(f"Error conectando: {e}")
        return None, None

def verificar_template(models, uid, password, template_key):
    """Verifica si un template tiene errores"""
    try:
        templates = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.ui.view', 'search_read',
            [[('key', '=', template_key), ('type', '=', 'qweb')]],
            {'fields': ['id', 'name', 'key', 'arch', 'inherit_id', 'active']}
        )
        
        if not templates:
            return None, f"Template '{template_key}' no encontrado"
        
        template = templates[0]
        
        # Intentar leer el arch para ver si hay errores obvios
        arch = template.get('arch', '')
        
        problemas = []
        
        # Verificar elementos básicos
        if not arch.strip():
            problemas.append("Template vacío")
        
        # Verificar referencias a otros templates
        if 't-call="' in arch and 'web.external_layout' not in arch and 'web.html_container' not in arch:
            # Puede estar llamando a templates que no existen
            import re
            t_calls = re.findall(r't-call=["\']([^"\']+)["\']', arch)
            for call in t_calls:
                if call not in ['web.external_layout', 'web.html_container', 'l10n_ar.custom_header']:
                    # Verificar si el template existe
                    template_llamado = models.execute_kw(
                        ODOO_CONFIG['db'], uid, password,
                        'ir.ui.view', 'search',
                        [[('key', '=', call), ('type', '=', 'qweb')]],
                        {'limit': 1}
                    )
                    if not template_llamado:
                        problemas.append(f"Template llamado '{call}' no existe")
        
        # Verificar sintaxis XML básica
        if arch.count('<t ') != arch.count('</t>'):
            problemas.append("Desbalance de tags <t>")
        
        # Verificar herencia
        inherit_id = template.get('inherit_id')
        if inherit_id:
            if isinstance(inherit_id, (list, tuple)):
                inherit_id_val = inherit_id[0]
            else:
                inherit_id_val = inherit_id
            
            template_padre = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'ir.ui.view', 'search_read',
                [[('id', '=', inherit_id_val)]],
                {'fields': ['id', 'key']}
            )
            if not template_padre:
                problemas.append(f"Template padre (ID: {inherit_id_val}) no encontrado")
        
        return template, problemas if problemas else None
        
    except xmlrpc.client.Fault as e:
        return None, f"Error de Odoo: {e}"
    except Exception as e:
        return None, f"Error verificando: {e}"

def main():
    print("="*80)
    print("🔍 VERIFICANDO TEMPLATES POR ERRORES")
    print("="*80)
    
    models, uid = conectar_odoo()
    if not models or not uid:
        return
    
    password = ODOO_CONFIG['pass']
    
    # Templates a verificar
    templates_a_verificar = [
        'account.report_invoice_document_nakel_2024',
        'stock.report_delivery_document_nakel_2024',
        'sale.report_saleorder_pro_forma',
        'account.report_invoice_document',  # Original
        'stock.report_delivery_document',  # Original
    ]
    
    resultados = {}
    
    for template_key in templates_a_verificar:
        print(f"\n📄 Verificando: {template_key}")
        template, problemas = verificar_template(models, uid, password, template_key)
        
        if template is None:
            print(f"   ❌ {problemas}")
            resultados[template_key] = {'status': 'error', 'problema': problemas}
        elif problemas:
            print(f"   ⚠️  Problemas encontrados:")
            for p in problemas:
                print(f"      - {p}")
            resultados[template_key] = {'status': 'warning', 'problemas': problemas}
        else:
            print(f"   ✅ Template OK (ID: {template['id']}, Activo: {template.get('active', True)})")
            resultados[template_key] = {'status': 'ok'}
    
    # Resumen
    print("\n" + "="*80)
    print("📊 RESUMEN")
    print("="*80)
    
    ok = sum(1 for r in resultados.values() if r['status'] == 'ok')
    warnings = sum(1 for r in resultados.values() if r['status'] == 'warning')
    errors = sum(1 for r in resultados.values() if r['status'] == 'error')
    
    print(f"✅ OK: {ok}")
    print(f"⚠️  Warnings: {warnings}")
    print(f"❌ Errores: {errors}")
    
    if errors > 0 or warnings > 0:
        print("\n💡 Si hay errores, considera:")
        print("   1. Revisar los backups en nakel/qweb/backups/")
        print("   2. Restaurar los templates originales si es necesario")
        print("   3. Verificar los logs de Odoo para más detalles")

if __name__ == "__main__":
    main()

