#!/usr/bin/env python3
"""
Script de diagnóstico: Verifica qué reportes existen y qué templates están usando
Útil para entender por qué los templates personalizados no se aplican
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

def conectar_odoo():
    """Conecta a Odoo"""
    try:
        common = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/common')
        uid = common.authenticate(ODOO_CONFIG['db'], ODOO_CONFIG['user'], ODOO_CONFIG['pass'], {})
        if not uid:
            print(f"❌ Error de autenticación")
            return None, None
        models = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/object')
        print(f"✅ Conexión exitosa a Odoo {ODOO_CONFIG['db']}")
        return models, uid
    except Exception as e:
        print(f"❌ Error conectando a Odoo: {e}")
        return None, None

def obtener_todos_reportes(models, uid, password, modelo=None):
    """Obtiene todos los reportes, opcionalmente filtrados por modelo"""
    try:
        dominio = []
        if modelo:
            dominio.append(('model', '=', modelo))
        
        reportes = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.actions.report', 'search_read',
            [dominio],
            {'fields': ['id', 'name', 'report_name', 'model', 'report_type'], 'order': 'name'}
        )
        return reportes
    except Exception as e:
        print(f"❌ Error obteniendo reportes: {e}")
        return []

def obtener_template_por_key(models, uid, password, key):
    """Obtiene un template por su key"""
    try:
        templates = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.ui.view', 'search_read',
            [[('key', '=', key), ('type', '=', 'qweb')]],
            {'fields': ['id', 'name', 'key', 'inherit_id', 'arch', 'active', 'priority']}
        )
        return templates[0] if templates else None
    except Exception as e:
        print(f"❌ Error buscando template {key}: {e}")
        return None

def diagnosticar_reportes_facturas(models, uid, password):
    """Diagnostica reportes de facturas"""
    print("\n" + "="*80)
    print("📄 DIAGNÓSTICO: REPORTES DE FACTURAS (account.move)")
    print("="*80)
    
    reportes = obtener_todos_reportes(models, uid, password, 'account.move')
    
    if not reportes:
        print("⚠️  No se encontraron reportes para account.move")
        return
    
    print(f"\n✅ {len(reportes)} reportes encontrados:\n")
    
    for reporte in reportes:
        print(f"📋 {reporte['name']}")
        print(f"   ID: {reporte['id']}")
        print(f"   report_name: {reporte['report_name']}")
        # print(f"   Activo: {reporte.get('active', True)}")  # Campo 'active' no existe en ir.actions.report
        print(f"   Tipo: {reporte.get('report_type', 'N/A')}")
        
        # Buscar template asociado
        template_key = reporte['report_name']
        template = obtener_template_por_key(models, uid, password, template_key)
        
        if template:
            print(f"   ✅ Template encontrado: {template['key']} (ID: {template['id']})")
            if template.get('inherit_id'):
                inherit_id = template['inherit_id']
                if isinstance(inherit_id, (list, tuple)):
                    inherit_key = inherit_id[1] if len(inherit_id) > 1 else f"ID {inherit_id[0]}"
                    print(f"   🔗 Hereda de: {inherit_key}")
                else:
                    print(f"   🔗 Hereda de: ID {inherit_id}")
            print(f"   Prioridad: {template.get('priority', 16)}")
        else:
            print(f"   ❌ Template '{template_key}' NO encontrado")
        
        # Verificar si es nuestro template personalizado
        if 'nakel_2024' in template_key or 'nakel' in reporte['name'].lower():
            print(f"   ⭐ Template personalizado de Nakel")
        
        print()

def diagnosticar_reportes_remitos(models, uid, password):
    """Diagnostica reportes de remitos"""
    print("\n" + "="*80)
    print("📦 DIAGNÓSTICO: REPORTES DE REMITOS (stock.picking)")
    print("="*80)
    
    reportes = obtener_todos_reportes(models, uid, password, 'stock.picking')
    
    if not reportes:
        print("⚠️  No se encontraron reportes para stock.picking")
        return
    
    print(f"\n✅ {len(reportes)} reportes encontrados:\n")
    
    for reporte in reportes:
        print(f"📋 {reporte['name']}")
        print(f"   ID: {reporte['id']}")
        print(f"   report_name: {reporte['report_name']}")
        # print(f"   Activo: {reporte.get('active', True)}")  # Campo 'active' no existe en ir.actions.report
        print(f"   Tipo: {reporte.get('report_type', 'N/A')}")
        
        # Buscar template asociado
        template_key = reporte['report_name']
        template = obtener_template_por_key(models, uid, password, template_key)
        
        if template:
            print(f"   ✅ Template encontrado: {template['key']} (ID: {template['id']})")
            if template.get('inherit_id'):
                inherit_id = template['inherit_id']
                if isinstance(inherit_id, (list, tuple)):
                    inherit_key = inherit_id[1] if len(inherit_id) > 1 else f"ID {inherit_id[0]}"
                    print(f"   🔗 Hereda de: {inherit_key}")
                else:
                    print(f"   🔗 Hereda de: ID {inherit_id}")
            print(f"   Prioridad: {template.get('priority', 16)}")
        else:
            print(f"   ❌ Template '{template_key}' NO encontrado")
        
        # Verificar si es nuestro template personalizado
        if 'nakel_2024' in template_key or 'nakel' in reporte['name'].lower():
            print(f"   ⭐ Template personalizado de Nakel")
        
        print()

def diagnosticar_reportes_proformas(models, uid, password):
    """Diagnostica reportes de proformas/cotizaciones"""
    print("\n" + "="*80)
    print("📋 DIAGNÓSTICO: REPORTES DE PROFORMAS (sale.order)")
    print("="*80)
    
    reportes = obtener_todos_reportes(models, uid, password, 'sale.order')
    
    if not reportes:
        print("⚠️  No se encontraron reportes para sale.order")
        return
    
    print(f"\n✅ {len(reportes)} reportes encontrados:\n")
    
    for reporte in reportes:
        print(f"📋 {reporte['name']}")
        print(f"   ID: {reporte['id']}")
        print(f"   report_name: {reporte['report_name']}")
        # print(f"   Activo: {reporte.get('active', True)}")  # Campo 'active' no existe en ir.actions.report
        print(f"   Tipo: {reporte.get('report_type', 'N/A')}")
        
        # Buscar template asociado
        template_key = reporte['report_name']
        template = obtener_template_por_key(models, uid, password, template_key)
        
        if template:
            print(f"   ✅ Template encontrado: {template['key']} (ID: {template['id']})")
            if template.get('inherit_id'):
                inherit_id = template['inherit_id']
                if isinstance(inherit_id, (list, tuple)):
                    inherit_key = inherit_id[1] if len(inherit_id) > 1 else f"ID {inherit_id[0]}"
                    print(f"   🔗 Hereda de: {inherit_key}")
                else:
                    print(f"   🔗 Hereda de: ID {inherit_id}")
            print(f"   Prioridad: {template.get('priority', 16)}")
        else:
            print(f"   ❌ Template '{template_key}' NO encontrado")
        
        # Verificar si es nuestro template personalizado
        if 'nakel' in template_key.lower() or 'nakel' in reporte['name'].lower():
            print(f"   ⭐ Template personalizado de Nakel")
        
        print()

def buscar_templates_personalizados(models, uid, password):
    """Busca todos los templates personalizados de Nakel"""
    print("\n" + "="*80)
    print("🔍 TEMPLATES PERSONALIZADOS DE NAKEL")
    print("="*80)
    
    try:
        templates = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.ui.view', 'search_read',
            [[('key', 'ilike', 'nakel'), ('type', '=', 'qweb')]],
            {'fields': ['id', 'name', 'key', 'inherit_id', 'active', 'priority']}
        )
        
        if not templates:
            print("⚠️  No se encontraron templates personalizados de Nakel")
            return
        
        print(f"\n✅ {len(templates)} templates personalizados encontrados:\n")
        
        for template in templates:
            print(f"📄 {template['key']}")
            print(f"   ID: {template['id']}")
            print(f"   Nombre: {template['name']}")
            print(f"   Activo: {template.get('active', True)}")
            print(f"   Prioridad: {template.get('priority', 16)}")
            
            if template.get('inherit_id'):
                inherit_id = template['inherit_id']
                if isinstance(inherit_id, (list, tuple)):
                    print(f"   🔗 Hereda de: ID {inherit_id[0]}")
                else:
                    print(f"   🔗 Hereda de: ID {inherit_id}")
            
            # Verificar si algún reporte lo usa
            reportes = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'ir.actions.report', 'search_read',
                [[('report_name', '=', template['key'])]],
                {'fields': ['id', 'name', 'model']}
            )
            
            if reportes:
                print(f"   ✅ Usado por {len(reportes)} reporte(s):")
                for r in reportes:
                    print(f"      - {r['name']} (ID: {r['id']}, Modelo: {r['model']})")
            else:
                print(f"   ⚠️  NO está siendo usado por ningún reporte")
            
            print()
            
    except Exception as e:
        print(f"❌ Error buscando templates: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Función principal"""
    print("="*80)
    print("🔍 DIAGNÓSTICO: REPORTES Y TEMPLATES EN MASTER_18")
    print("="*80)
    print(f"📊 Base de datos: {ODOO_CONFIG['db']}")
    print(f"🌐 URL: {ODOO_CONFIG['url']}")
    print("="*80)
    
    models, uid = conectar_odoo()
    if not models or not uid:
        return
    
    password = ODOO_CONFIG['pass']
    
    # Diagnosticar cada tipo de reporte
    diagnosticar_reportes_facturas(models, uid, password)
    diagnosticar_reportes_remitos(models, uid, password)
    diagnosticar_reportes_proformas(models, uid, password)
    buscar_templates_personalizados(models, uid, password)
    
    print("\n" + "="*80)
    print("✅ DIAGNÓSTICO COMPLETADO")
    print("="*80)
    print("\n💡 Resumen:")
    print("   - Si un template personalizado existe pero no está siendo usado por ningún reporte,")
    print("     significa que el ir.actions.report no está apuntando a ese template.")
    print("   - Si un reporte existe pero su template no se encuentra,")
    print("     significa que el template fue eliminado o nunca se creó.")
    print("   - Si un template tiene herencia (inherit_id), está reemplazando el template original.")

if __name__ == "__main__":
    main()

