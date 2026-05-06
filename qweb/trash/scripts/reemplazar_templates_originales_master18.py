#!/usr/bin/env python3
"""
Script para REEMPLAZAR directamente los templates originales con nuestros templates mejorados
Esto es más directo: simplemente reemplaza el contenido del template original
"""

import sys
import os
import xmlrpc.client
import logging
from datetime import datetime

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

def leer_template(archivo, key_original):
    """
    Lee el template y ajusta el t-name para que coincida con el original
    """
    try:
        with open(archivo, 'r', encoding='utf-8') as f:
            contenido = f.read()
        
        # Extraer el contenido del template
        inicio = contenido.find('<t t-name=')
        if inicio == -1:
            return contenido.strip()
        
        template_content = contenido[inicio:].strip()
        
        # Reemplazar el t-name para que coincida con el original
        # Ejemplo: cambiar "account.report_invoice_document_nakel_2024" por "account.report_invoice_document"
        import re
        # Buscar el t-name actual
        pattern = r'<t t-name=["\']([^"\']+)["\']'
        match = re.search(pattern, template_content)
        if match:
            current_name = match.group(1)
            # Reemplazar con el key_original
            template_content = re.sub(
                pattern,
                f'<t t-name="{key_original}"',
                template_content,
                count=1
            )
            logging.info(f"   🔄 Ajustado t-name: {current_name} → {key_original}")
        
        return template_content
        
    except Exception as e:
        logging.error(f"Error leyendo {archivo}: {e}")
        return None

def hacer_backup_template(models, uid, password, template_id, template_key):
    """Hace backup del template antes de modificarlo"""
    try:
        template_data = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.ui.view', 'read',
            [[template_id]],
            {'fields': ['id', 'name', 'key', 'arch']}
        )[0]
        
        backup_dir = os.path.join(os.path.dirname(__file__), '../backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(backup_dir, f"template_{template_key.replace('.', '_')}_{timestamp}.xml")
        
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(template_data['arch'])
        
        logging.info(f"   💾 Backup guardado: {backup_file}")
        return backup_file
    except Exception as e:
        logging.warning(f"   ⚠️  No se pudo hacer backup: {e}")
        return None

def reemplazar_template_original(models, uid, password, config):
    """
    REEMPLAZA directamente el contenido del template original
    Esto es más directo y funciona mejor con Odoo
    """
    logging.info(f"\n{'='*80}")
    logging.info(f"📄 PROCESANDO: {config['nombre']}")
    logging.info(f"{'='*80}")
    
    # Buscar template original
    templates = models.execute_kw(
        ODOO_CONFIG['db'], uid, password,
        'ir.ui.view', 'search_read',
        [[('key', '=', config['key_original']), ('type', '=', 'qweb')]],
        {'fields': ['id', 'name', 'key', 'arch']}
    )
    
    if not templates:
        logging.warning(f"⚠️  Template original '{config['key_original']}' no encontrado")
        logging.info(f"   Intentando buscar variantes...")
        
        # Buscar variantes comunes
        variantes = [
            f"l10n_ar.{config['key_original']}",
            config['key_original'].replace('account.', 'l10n_ar_account.'),
        ]
        
        for variante in variantes:
            templates = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'ir.ui.view', 'search_read',
                [[('key', '=', variante), ('type', '=', 'qweb')]],
                {'fields': ['id', 'name', 'key', 'arch']}
            )
            if templates:
                logging.info(f"   ✅ Encontrado: {variante}")
                config['key_original'] = variante
                break
    
    if not templates:
        logging.error(f"❌ No se pudo encontrar template original")
        return False
    
    template_original = templates[0]
    template_id = template_original['id']
    logging.info(f"✅ Template original encontrado: {config['key_original']} (ID: {template_id})")
    
    # Hacer backup
    hacer_backup_template(models, uid, password, template_id, config['key_original'])
    
    # Leer nuestro template y ajustarlo
    arch_content = leer_template(config['archivo_template'], config['key_original'])
    if not arch_content:
        return False
    
    logging.info(f"✅ Template personalizado leído y ajustado ({len(arch_content)} caracteres)")
    
    # Reemplazar el contenido del template original
    try:
        models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.ui.view', 'write',
            [[template_id], {
                'arch': arch_content
            }]
        )
        logging.info(f"✅ Template original reemplazado exitosamente")
        
        # Verificar que el reporte apunte al template correcto
        reportes = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.actions.report', 'search_read',
            [[('report_name', '=', config['key_original'])]],
            {'fields': ['id', 'name', 'report_name']}
        )
        
        if reportes:
            logging.info(f"✅ {len(reportes)} reporte(s) asociado(s) al template:")
            for r in reportes:
                logging.info(f"   - {r['name']} (ID: {r['id']})")
        
        return True
        
    except Exception as e:
        logging.error(f"❌ Error reemplazando template: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    logging.info("="*80)
    logging.info("🔧 REEMPLAZANDO TEMPLATES ORIGINALES EN MASTER_18")
    logging.info("   Reemplaza directamente el contenido de los templates originales")
    logging.info("="*80)
    
    models, uid = conectar_odoo()
    if not models or not uid:
        return
    
    password = ODOO_CONFIG['pass']
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Configuración
    templates_config = [
        {
            'key_original': 'account.report_invoice_document',
            'archivo_template': os.path.join(script_dir, '../templates/account.report_invoice_document_nakel_2024_FACTURA_B_MEJORADO.xml'),
            'nombre': 'Factura B',
            'modelo': 'account.move'
        },
        {
            'key_original': 'stock.report_delivery_document',
            'archivo_template': os.path.join(script_dir, '../templates/stock.report_delivery_document_nakel_2024_MEJORADO.xml'),
            'nombre': 'Remito',
            'modelo': 'stock.picking'
        },
        {
            'key_original': 'sale.report_saleorder_pro_forma',
            'archivo_template': os.path.join(script_dir, '../templates/sale.report_saleorder_pro_forma_NAKEL_MEJORADO_V2.xml'),
            'nombre': 'Proforma',
            'modelo': 'sale.order'
        },
    ]
    
    resultados = []
    for config in templates_config:
        resultado = reemplazar_template_original(models, uid, password, config)
        resultados.append((config['nombre'], resultado))
    
    # Resumen
    logging.info("\n" + "="*80)
    logging.info("📊 RESUMEN")
    logging.info("="*80)
    
    exitosos = sum(1 for _, r in resultados if r)
    for nombre, resultado in resultados:
        estado = "✅ OK" if resultado else "❌ ERROR"
        logging.info(f"{estado} - {nombre}")
    
    logging.info(f"\n✅ {exitosos}/{len(resultados)} templates reemplazados")
    logging.info("\n💡 IMPORTANTE:")
    logging.info("   1. Reinicia Odoo completamente (sudo systemctl restart odoo)")
    logging.info("   2. Limpia la caché del navegador (Ctrl+Shift+Del)")
    logging.info("   3. Prueba generando un NUEVO documento (no uses uno en caché)")
    logging.info("   4. Los backups están en: nakel/qweb/backups/")

if __name__ == "__main__":
    main()

