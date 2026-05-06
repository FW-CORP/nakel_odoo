#!/usr/bin/env python3
"""
Script para actualizar los templates de Factura B y Nota de Crédito en master_18
Cambia la sección de totales para usar amount_by_group en lugar de calcular manualmente
Esto muestra TODOS los impuestos, percepciones y retenciones que Odoo ya calculó
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

def leer_template(template_path):
    """Lee un template desde el archivo"""
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            contenido = f.read()
        
        # Extraer solo el contenido del template (sin comentarios iniciales)
        # Buscar cualquier t-name que comience con account.report
        inicio = contenido.find('<t t-name="account.report')
        if inicio == -1:
            # Si no se encuentra, buscar cualquier t-name
            inicio = contenido.find('<t t-name=')
        
        if inicio == -1:
            print(f"❌ No se encontró el inicio del template en {template_path}")
            return None
        
        arch_content = contenido[inicio:].strip()
        return arch_content
    except Exception as e:
        print(f"❌ Error leyendo template {template_path}: {e}")
        return None

def actualizar_template(models, uid, password, db, template_key, template_path, template_name):
    """Actualiza un template en Odoo"""
    print(f"\n📝 Actualizando {template_name}...")
    
    # Leer template actualizado
    arch_content = leer_template(template_path)
    if not arch_content:
        return False
    
    # Buscar template en Odoo
    templates = models.execute_kw(
        db, uid, password,
        'ir.ui.view', 'search_read',
        [[('key', '=', template_key), ('type', '=', 'qweb')]],
        {'fields': ['id', 'name', 'key']}
    )
    
    if not templates:
        print(f"   ⚠️  Template '{template_key}' no encontrado en Odoo")
        return False
    
    template = templates[0]
    print(f"   📋 Template encontrado: {template['name']} (ID: {template['id']})")
    
    # Actualizar template
    try:
        models.execute_kw(
            db, uid, password,
            'ir.ui.view', 'write',
            [[template['id']], {'arch': arch_content}]
        )
        print(f"   ✅ {template_name} actualizado correctamente")
        return True
    except Exception as e:
        print(f"   ❌ Error actualizando template: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("="*80)
    print("📝 ACTUALIZACIÓN DE TEMPLATES FACTURA B Y NOTA DE CRÉDITO")
    print("   Usando amount_by_group para mostrar todos los impuestos")
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
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Templates a actualizar
    templates_config = [
        {
            'key': 'account.report_invoice_document_nakel_2024',
            'path': os.path.join(script_dir, '../templates/account.report_invoice_document_nakel_2024_FACTURA_B_MEJORADO.xml'),
            'name': 'Factura B'
        },
        {
            'key': 'account.report_credit_note_document_nakel_2024',
            'path': os.path.join(script_dir, '../templates/account.report_invoice_document_nakel_2024_NOTA_CREDITO_MEJORADO.xml'),
            'name': 'Nota de Crédito'
        }
    ]
    
    resultados = []
    for config in templates_config:
        resultado = actualizar_template(
            models, uid, password, db,
            config['key'],
            config['path'],
            config['name']
        )
        resultados.append(resultado)
    
    print("\n" + "="*80)
    if all(resultados):
        print("✅ ACTUALIZACIÓN COMPLETADA")
        print("="*80)
        print("📝 Cambios aplicados:")
        print("   • Se elimina el cálculo manual de 'IVA 21%' y 'Percepciones'")
        print("   • Se usa tax_totals que contiene TODOS los impuestos que Odoo ya calculó")
        print("   • IMPORTANTE: En Factura B NO se muestran percepciones de IIBB (solo IVA)")
        print("   • En Factura A SÍ se muestran percepciones de IIBB")
        print("   • Se mostrarán automáticamente:")
        print("     - IVA (con su porcentaje exacto)")
        print("     - Percepciones municipales (IIBB) - SOLO en Factura A")
        print("     - Retenciones")
        print("     - Impuestos internos")
        print("     - Cualquier otro impuesto/percepción/retención")
        print("   • Los nombres se muestran tal como están configurados en Odoo")
        print("\n💡 Los próximos reportes mostrarán los impuestos según el tipo de factura:")
        print("   - Factura A: IVA + Percepciones IIBB + otros impuestos")
        print("   - Factura B: IVA únicamente (sin percepciones IIBB)")
        return True
    else:
        print("❌ ACTUALIZACIÓN FALLIDA")
        print("="*80)
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

