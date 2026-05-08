#!/usr/bin/env python3
"""
Analiza vía XML-RPC qué reportes de factura están en uso y qué templates usan.
Útil antes de aplicar cambios (ej. fix de líneas de nota).
Soporta master_18 y master_dev.
"""

import sys
import os
import argparse

sys.path.insert(0, '/media/klap/raid5/cursor_files')

try:
    from config_nakel import ODOO_CONFIG_MASTER18, ODOO_CONFIG_MASTER_DEV
except ImportError:
    print("❌ Error: No se pudo importar config_nakel.py")
    sys.exit(1)

def conectar(config):
    """Conecta a Odoo"""
    import xmlrpc.client
    try:
        common = xmlrpc.client.ServerProxy(f"{config['url']}/xmlrpc/2/common")
        uid = common.authenticate(config['db'], config['username'], config['password'], {})
        if not uid:
            return None, None, None
        models = xmlrpc.client.ServerProxy(f"{config['url']}/xmlrpc/2/object")
        return models, uid, config['password']
    except Exception as e:
        print(f"❌ Error: {e}")
        return None, None, None

def analizar_reportes_facturas(models, uid, password, db_name, config):
    """Analiza reportes de account.move y sus templates"""
    import xmlrpc.client
    
    reportes = models.execute_kw(
        db_name, uid, password,
        'ir.actions.report', 'search_read',
        [[('model', '=', 'account.move'), ('report_type', '=', 'qweb-pdf')]],
        {'fields': ['id', 'name', 'report_name', 'model'], 'order': 'name'}
    )
    
    if not reportes:
        print("   ⚠️  No se encontraron reportes para account.move")
        return []
    
    resultados = []
    for r in reportes:
        key = r['report_name']
        templates = models.execute_kw(
            db_name, uid, password,
            'ir.ui.view', 'search_read',
            [[('key', '=', key), ('type', '=', 'qweb')]],
            {'fields': ['id', 'name', 'key', 'priority'], 'limit': 1}
        )
        
        template = templates[0] if templates else None
        tiene_line_note = False
        arch_preview = ""
        
        if template:
            # Obtener arch para verificar si tiene line_note
            full = models.execute_kw(
                db_name, uid, password,
                'ir.ui.view', 'read',
                [[template['id']]],
                {'fields': ['arch']}
            )
            if full and full[0].get('arch'):
                arch = full[0]['arch']
                tiene_line_note = "line_note" in arch
                # Preview de primeras líneas relevantes
                if "invoice_line" in arch or "invoice_line_ids" in arch:
                    idx = arch.find("t-foreach")
                    if idx >= 0:
                        arch_preview = arch[idx:idx+200].replace('\n', ' ')
        
        resultados.append({
            'reporte': r,
            'template': template,
            'tiene_line_note': tiene_line_note,
            'arch_preview': arch_preview[:80] + "..." if len(arch_preview) > 80 else arch_preview
        })
    
    return resultados

def main():
    parser = argparse.ArgumentParser(description="Analiza reportes de factura en uso vía XML-RPC")
    parser.add_argument('--instancia', choices=['master18', 'master_dev'], default='master18',
                        help='Instancia a analizar (default: master18)')
    args = parser.parse_args()
    
    config = ODOO_CONFIG_MASTER18 if args.instancia == 'master18' else ODOO_CONFIG_MASTER_DEV
    db_name = config['db']
    
    print("="*80)
    print("📊 ANÁLISIS DE REPORTES DE FACTURA EN USO (XML-RPC)")
    print("="*80)
    print(f"📌 Instancia: {args.instancia} ({db_name})")
    print(f"🌐 URL: {config['url']}")
    print("="*80)
    
    models, uid, password = conectar(config)
    if not models or not uid:
        print("❌ No se pudo conectar")
        return 1
    
    print("✅ Conexión exitosa\n")
    
    resultados = analizar_reportes_facturas(models, uid, password, db_name, config)
    
    for r in resultados:
        rep = r['reporte']
        tpl = r['template']
        print(f"📋 {rep['name']}")
        print(f"   ID reporte: {rep['id']}")
        print(f"   report_name: {rep['report_name']}")
        
        if tpl:
            print(f"   ✅ Template: {tpl['key']} (ID: {tpl['id']}, prioridad: {tpl.get('priority', 'N/A')})")
            if r['tiene_line_note']:
                print(f"   ✅ Soporta line_note (notas) en PDF")
            else:
                print(f"   ⚠️  NO incluye line_note → las notas no se imprimen en PDF")
        else:
            print(f"   ❌ Sin template asociado (key: {rep['report_name']})")
        print()
    
    # Resumen para facturas Nakel
    nakel = [r for r in resultados if 'nakel' in r['reporte']['report_name'].lower() or 
             (r['template'] and 'nakel' in r['template'].get('key', '').lower())]
    
    if nakel:
        print("="*80)
        print("📌 TEMPLATES NAKEL (los que aplicamos)")
        print("="*80)
        for r in nakel:
            fix = "✅ Con fix notas" if r['tiene_line_note'] else "❌ Falta fix notas"
            print(f"   {r['reporte']['report_name']} → {fix}")
    
    print("\n" + "="*80)
    print("💡 Para aplicar el fix de notas: ejecutar aplicar_templates_master_dev_desde_master18.py")
    print("   (o instalar_templates_todos_master18.py para master_18)")
    print("="*80)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
