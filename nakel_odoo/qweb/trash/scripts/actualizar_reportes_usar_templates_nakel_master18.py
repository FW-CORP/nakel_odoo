#!/usr/bin/env python3
"""
Script simple: Actualiza los reportes para que usen nuestros templates personalizados
Los templates ya están creados, solo necesitamos que los reportes los usen
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

def actualizar_reporte_para_template(models, uid, password, config):
    """
    Actualiza el report_name de los reportes para que usen nuestro template personalizado
    """
    logging.info(f"\n{'='*80}")
    logging.info(f"📄 PROCESANDO: {config['nombre']}")
    logging.info(f"{'='*80}")
    
    # Buscar reportes que usan el template original
    reportes = models.execute_kw(
        ODOO_CONFIG['db'], uid, password,
        'ir.actions.report', 'search_read',
        [[('report_name', '=', config['key_original'])]],
        {'fields': ['id', 'name', 'report_name', 'model']}
    )
    
    if not reportes:
        logging.warning(f"⚠️  No se encontraron reportes con report_name='{config['key_original']}'")
        # Buscar por modelo
        reportes = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.actions.report', 'search_read',
            [[('model', '=', config['modelo']), ('report_type', '=', 'qweb-pdf')]],
            {'fields': ['id', 'name', 'report_name', 'model']}
        )
        if reportes:
            logging.info(f"   Encontrados {len(reportes)} reportes para modelo {config['modelo']}")
            # Mostrar todos para referencia
            for r in reportes[:5]:  # Mostrar primeros 5
                logging.info(f"      - {r['name']} (report_name: {r['report_name']})")
    
    # Verificar que nuestro template personalizado existe
    template = models.execute_kw(
        ODOO_CONFIG['db'], uid, password,
        'ir.ui.view', 'search_read',
        [[('key', '=', config['key_personalizado']), ('type', '=', 'qweb')]],
        {'fields': ['id', 'name', 'key']}
    )
    
    if not template:
        logging.error(f"❌ Template personalizado '{config['key_personalizado']}' NO existe")
        logging.error(f"   Necesitas ejecutar primero el script de instalación de templates")
        return False
    
    logging.info(f"✅ Template personalizado encontrado: {config['key_personalizado']} (ID: {template[0]['id']})")
    
    # Actualizar reportes
    actualizados = 0
    for reporte in reportes:
        logging.info(f"🔄 Actualizando reporte '{reporte['name']}' (ID: {reporte['id']})")
        logging.info(f"   Cambiando report_name: {reporte['report_name']} → {config['key_personalizado']}")
        
        try:
            models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'ir.actions.report', 'write',
                [[reporte['id']], {
                    'report_name': config['key_personalizado']
                }]
            )
            logging.info(f"   ✅ Reporte actualizado")
            actualizados += 1
        except Exception as e:
            logging.error(f"   ❌ Error actualizando reporte: {e}")
    
    if actualizados == 0:
        logging.warning(f"⚠️  No se actualizaron reportes")
        logging.info(f"   Verifica manualmente qué reporte se está usando al imprimir")
        return False
    
    logging.info(f"✅ {actualizados} reporte(s) actualizado(s)")
    return True

def main():
    logging.info("="*80)
    logging.info("🔧 ACTUALIZANDO REPORTES PARA USAR TEMPLATES PERSONALIZADOS")
    logging.info("   Los templates ya están creados, solo actualizamos los reportes")
    logging.info("="*80)
    
    models, uid = conectar_odoo()
    if not models or not uid:
        return
    
    password = ODOO_CONFIG['pass']
    
    # Configuración: qué templates usar
    templates_config = [
        {
            'key_original': 'account.report_invoice_document',  # Template original
            'key_personalizado': 'account.report_invoice_document_nakel_2024',  # Nuestro template
            'nombre': 'Factura B',
            'modelo': 'account.move'
        },
        {
            'key_original': 'stock.report_delivery_document',  # O stock.report_deliveryslip
            'key_personalizado': 'stock.report_delivery_document_nakel_2024',
            'nombre': 'Remito',
            'modelo': 'stock.picking'
        },
    ]
    
    resultados = []
    for config in templates_config:
        resultado = actualizar_reporte_para_template(models, uid, password, config)
        resultados.append((config['nombre'], resultado))
    
    # Resumen
    logging.info("\n" + "="*80)
    logging.info("📊 RESUMEN")
    logging.info("="*80)
    
    exitosos = sum(1 for _, r in resultados if r)
    for nombre, resultado in resultados:
        estado = "✅ OK" if resultado else "❌ ERROR"
        logging.info(f"{estado} - {nombre}")
    
    logging.info(f"\n✅ {exitosos}/{len(resultados)} reportes actualizados")
    
    if exitosos > 0:
        logging.info("\n💡 IMPORTANTE:")
        logging.info("   1. Reinicia Odoo (o recarga workers)")
        logging.info("   2. Limpia caché del navegador")
        logging.info("   3. Prueba generando un NUEVO documento")
        logging.info("   4. Si sigues viendo el formato antiguo, verifica:")
        logging.info("      - Qué reporte se está usando al imprimir")
        logging.info("      - Si hay múltiples reportes para el mismo modelo")

if __name__ == "__main__":
    main()

