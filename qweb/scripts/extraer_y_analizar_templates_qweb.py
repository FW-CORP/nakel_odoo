#!/usr/bin/env python3
"""
Script para extraer y analizar templates QWeb desde Odoo master_dev
y verificar cumplimiento con requisitos AFIP/ARBA/ARCA
"""

import sys
import os
import json
import xmlrpc.client
from datetime import datetime

sys.path.insert(0, '/media/klap/raid5/cursor_files')

try:
    from config_nakel import ODOO_CONFIG_MASTER_DEV
except ImportError:
    print("❌ Error: No se pudo importar config_nakel.py")
    sys.exit(1)

ODOO_CONFIG = {
    'url': ODOO_CONFIG_MASTER_DEV['url'],
    'db': ODOO_CONFIG_MASTER_DEV['db'],
    'user': ODOO_CONFIG_MASTER_DEV['username'],
    'pass': ODOO_CONFIG_MASTER_DEV['password']
}

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
        print(f"❌ Error: {e}")
        return None, None

def buscar_templates_por_report_name(models, uid, password, report_name):
    """Busca template por report_name (key)"""
    try:
        templates = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.ui.view', 'search_read',
            [[('key', '=', report_name), ('type', '=', 'qweb')]],
            {'fields': ['id', 'name', 'key', 'arch', 'model', 'active']}
        )
        return templates
    except:
        return []

def obtener_todos_reportes(models, uid, password):
    """Obtiene todos los reportes de facturas, remitos y notas de crédito"""
    try:
        # Reportes de facturas
        reportes_facturas = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.actions.report', 'search_read',
            [[('model', '=', 'account.move'), ('report_type', '=', 'qweb-pdf')]],
            {'fields': ['id', 'name', 'report_name', 'report_file', 'model']}
        )
        
        # Reportes de remitos
        reportes_remitos = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.actions.report', 'search_read',
            [[('model', '=', 'stock.picking'), ('report_type', '=', 'qweb-pdf')]],
            {'fields': ['id', 'name', 'report_name', 'report_file', 'model']}
        )
        
        return reportes_facturas, reportes_remitos
    except Exception as e:
        print(f"❌ Error obteniendo reportes: {e}")
        return [], []

def analizar_campos_afip(arch):
    """Analiza qué campos AFIP están presentes"""
    if not arch:
        return {}
    
    arch_lower = arch.lower()
    campos = {
        'cuit_emisor': 'company_id.vat' in arch,
        'cuit_receptor': 'partner_id.vat' in arch,
        'condicion_fiscal': 'l10n_ar_afip' in arch or 'responsibility_type' in arch_lower,
        'fecha': 'invoice_date' in arch_lower or 'date_done' in arch_lower,
        'numero': 'o.name' in arch,
        'detalle_productos': 'invoice_line_ids' in arch or 'move_ids' in arch,
        'precios': 'price_unit' in arch_lower,
        'totales': 'amount_total' in arch_lower,
        'iva': 'amount_tax' in arch_lower or 'tax' in arch_lower,
        'cae': 'l10n_ar_cae' in arch or 'cae' in arch_lower,
        'qr_code': 'qr_code' in arch_lower or 'qr' in arch_lower,
        'leyenda_consumidor_final': 'consumidor final' in arch_lower,
        'percepciones': 'percepcion' in arch_lower or 'perception' in arch_lower,
        'iibb': 'l10n_ar_gross_income' in arch or 'iibb' in arch_lower,
        'inicio_actividades': 'l10n_ar_afip_start_date' in arch,
        'rg_afip_4294': '4294' in arch or 'rg afip 4294' in arch_lower
    }
    return campos

def main():
    print("="*80)
    print("🔍 EXTRACCIÓN Y ANÁLISIS DE TEMPLATES QWEB")
    print("="*80)
    
    models, uid = conectar_odoo()
    if not models or not uid:
        return
    
    password = ODOO_CONFIG['pass']
    
    # Obtener reportes
    print("\n📄 Obteniendo reportes...")
    reportes_facturas, reportes_remitos = obtener_todos_reportes(models, uid, password)
    
    print(f"✅ {len(reportes_facturas)} reportes de facturas")
    print(f"✅ {len(reportes_remitos)} reportes de remitos\n")
    
    resultados = {
        'fecha': datetime.now().isoformat(),
        'facturas': [],
        'remitos': []
    }
    
    # Analizar reportes de facturas
    print("📄 ANALIZANDO REPORTES DE FACTURAS\n")
    for reporte in reportes_facturas:
        report_name = reporte.get('report_name', '')
        print(f"  Reporte: {reporte['name']}")
        print(f"    Report Name: {report_name}")
        
        # Buscar template
        templates = buscar_templates_por_report_name(models, uid, password, report_name)
        
        if not templates and reporte.get('report_file'):
            # Intentar con report_file como key
            templates = buscar_templates_por_report_name(models, uid, password, reporte['report_file'])
        
        if templates:
            template = templates[0]
            arch = template.get('arch', '')
            campos = analizar_campos_afip(arch)
            
            print(f"    ✅ Template encontrado: {template['name']}")
            print(f"    Campos presentes: {sum(campos.values())}/{len(campos)}")
            
            # Guardar template
            resultados['facturas'].append({
                'reporte': reporte['name'],
                'report_name': report_name,
                'template_id': template['id'],
                'template_name': template['name'],
                'template_key': template.get('key'),
                'campos_afip': campos,
                'arch_length': len(arch),
                'arch': arch  # Guardar el arch completo
            })
            
            # Guardar template a archivo
            os.makedirs('/media/klap/raid5/cursor_files/nakel/qweb/templates', exist_ok=True)
            template_file = f"/media/klap/raid5/cursor_files/nakel/qweb/templates/{template.get('key', 'template')}_{template['id']}.xml"
            with open(template_file, 'w', encoding='utf-8') as f:
                f.write(f"<!-- Template: {template['name']} -->\n")
                f.write(f"<!-- Key: {template.get('key', 'N/A')} -->\n")
                f.write(f"<!-- ID: {template['id']} -->\n\n")
                f.write(arch)
            print(f"    💾 Template guardado en: {template_file}")
        else:
            print(f"    ⚠️  No se encontró template asociado")
            resultados['facturas'].append({
                'reporte': reporte['name'],
                'report_name': report_name,
                'template_encontrado': False
            })
        print()
    
    # Analizar reportes de remitos
    print("📦 ANALIZANDO REPORTES DE REMITOS\n")
    for reporte in reportes_remitos:
        report_name = reporte.get('report_name', '')
        print(f"  Reporte: {reporte['name']}")
        print(f"    Report Name: {report_name}")
        
        templates = buscar_templates_por_report_name(models, uid, password, report_name)
        
        if not templates and reporte.get('report_file'):
            templates = buscar_templates_por_report_name(models, uid, password, reporte['report_file'])
        
        if templates:
            template = templates[0]
            arch = template.get('arch', '')
            campos = analizar_campos_afip(arch)
            
            print(f"    ✅ Template encontrado: {template['name']}")
            print(f"    Campos presentes: {sum(campos.values())}/{len(campos)}")
            
            resultados['remitos'].append({
                'reporte': reporte['name'],
                'report_name': report_name,
                'template_id': template['id'],
                'template_name': template['name'],
                'template_key': template.get('key'),
                'campos_afip': campos,
                'arch_length': len(arch),
                'arch': arch
            })
            
            template_file = f"/media/klap/raid5/cursor_files/nakel/qweb/templates/{template.get('key', 'template')}_{template['id']}.xml"
            with open(template_file, 'w', encoding='utf-8') as f:
                f.write(f"<!-- Template: {template['name']} -->\n")
                f.write(f"<!-- Key: {template.get('key', 'N/A')} -->\n")
                f.write(f"<!-- ID: {template['id']} -->\n\n")
                f.write(arch)
            print(f"    💾 Template guardado en: {template_file}")
        else:
            print(f"    ⚠️  No se encontró template asociado")
            resultados['remitos'].append({
                'reporte': reporte['name'],
                'report_name': report_name,
                'template_encontrado': False
            })
        print()
    
    # Guardar reporte JSON
    os.makedirs('/media/klap/raid5/cursor_files/nakel/qweb/reportes', exist_ok=True)
    reporte_file = f"/media/klap/raid5/cursor_files/nakel/qweb/reportes/extraccion_templates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(reporte_file, 'w', encoding='utf-8') as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)
    
    print("="*80)
    print("✅ EXTRACCIÓN COMPLETADA")
    print(f"📊 Reporte guardado en: {reporte_file}")
    print(f"📁 Templates guardados en: /media/klap/raid5/cursor_files/nakel/qweb/templates/")

if __name__ == "__main__":
    main()

