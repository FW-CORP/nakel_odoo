#!/usr/bin/env python3
"""
Script URGENTE: Aplica las correcciones de qr_code_url a los templates en Odoo
Corrige el error: AttributeError: 'account.move' object has no attribute 'qr_code_url'
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

def leer_template(archivo):
    """Lee el contenido del template desde archivo"""
    try:
        with open(archivo, 'r', encoding='utf-8') as f:
            contenido = f.read()
        # Extraer desde <t t-name=
        inicio = contenido.find('<t t-name=')
        if inicio == -1:
            return contenido.strip()
        return contenido[inicio:].strip()
    except Exception as e:
        logging.error(f"Error leyendo {archivo}: {e}")
        return None

def actualizar_template(models, uid, password, template_key, archivo):
    """Actualiza un template con el contenido corregido"""
    
    # Leer template corregido
    arch_content = leer_template(archivo)
    if not arch_content:
        return False
    
    # Buscar template en Odoo
    templates = models.execute_kw(
        ODOO_CONFIG['db'], uid, password,
        'ir.ui.view', 'search_read',
        [[('key', '=', template_key), ('type', '=', 'qweb')]],
        {'fields': ['id', 'name', 'key']}
    )
    
    if not templates:
        logging.warning(f"⚠️  Template '{template_key}' no encontrado en Odoo")
        return False
    
    template = templates[0]
    
    try:
        models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.ui.view', 'write',
            [[template['id']], {'arch': arch_content}]
        )
        logging.info(f"✅ Template '{template_key}' actualizado (ID: {template['id']})")
        return True
    except Exception as e:
        logging.error(f"❌ Error actualizando template: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("="*80)
    print("🔧 APLICANDO CORRECCIONES: Templates con qr_code_url")
    print("="*80)
    
    models, uid = conectar_odoo()
    if not models or not uid:
        logging.error("No se pudo conectar a Odoo")
        return
    
    password = ODOO_CONFIG['pass']
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Templates a actualizar
    templates = [
        {
            'key': 'account.report_invoice_document_nakel_2024',
            'archivo': os.path.join(script_dir, '../templates/account.report_invoice_document_nakel_2024_FACTURA_B_MEJORADO.xml'),
            'nombre': 'Factura B Nakel 2024'
        },
        {
            'key': 'account.report_credit_note_document_nakel_2024',
            'archivo': os.path.join(script_dir, '../templates/account.report_invoice_document_nakel_2024_NOTA_CREDITO_MEJORADO.xml'),
            'nombre': 'Nota de Crédito Nakel 2024'
        },
        {
            'key': 'stock.report_delivery_document_nakel_2024',
            'archivo': os.path.join(script_dir, '../templates/stock.report_delivery_document_nakel_2024_MEJORADO.xml'),
            'nombre': 'Remito Nakel 2024'
        },
    ]
    
    resultados = []
    for template in templates:
        logging.info(f"\n📄 Procesando: {template['nombre']}")
        resultado = actualizar_template(models, uid, password, template['key'], template['archivo'])
        resultados.append((template['nombre'], resultado))
    
    # Resumen
    print("\n" + "="*80)
    print("📊 RESUMEN")
    print("="*80)
    
    exitosos = sum(1 for _, r in resultados if r)
    for nombre, resultado in resultados:
        estado = "✅ OK" if resultado else "❌ ERROR"
        logging.info(f"{estado} - {nombre}")
    
    if exitosos == len(resultados):
        print("\n✅ TODOS LOS TEMPLATES CORREGIDOS")
        print("\n💡 Ahora:")
        print("   1. Intenta imprimir la factura de nuevo")
        print("   2. El error de qr_code_url debería estar resuelto")
    else:
        print(f"\n⚠️  Solo {exitosos}/{len(resultados)} templates se actualizaron correctamente")

if __name__ == "__main__":
    main()

