#!/usr/bin/env python3
"""
Script para REVERTIR los cambios problemáticos que están causando lentitud
Reverte los reportes a sus valores originales y deja solo los templates personalizados como opciones separadas
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

def revertir_reportes_a_originales(models, uid, password):
    """
    Revierte los reportes a sus valores originales
    Solo deja los reportes personalizados de Nakel como opciones separadas
    """
    logging.info("="*80)
    logging.info("🔄 REVIRTIENDO REPORTES A VALORES ORIGINALES")
    logging.info("="*80)
    
    # Mapeo de reportes a sus valores originales
    reportes_a_revertir = {
        # Facturas - dejar solo "Factura B Nakel 2024" con el template personalizado
        'PDF': 'account.report_invoice_with_payments',
        'PDF without Payment': 'account.report_invoice',
        'Original Bills': 'account.report_original_vendor_bill',
        
        # Remitos - dejar solo "Remito Nakel 2024" con el template personalizado
        'Delivery Slip': 'stock.report_deliveryslip',
        'Packages': 'stock.report_picking_packages',
        'Picking Operations': 'stock.report_picking',
        'Reception Report': 'stock.report_reception',
        'Return slip': 'stock.report_return_slip',
    }
    
    actualizados = 0
    errores = 0
    
    for nombre_reporte, report_name_original in reportes_a_revertir.items():
        try:
            # Buscar reporte por nombre
            reportes = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'ir.actions.report', 'search_read',
                [[('name', '=', nombre_reporte)]],
                {'fields': ['id', 'name', 'report_name']}
            )
            
            if not reportes:
                logging.warning(f"⚠️  Reporte '{nombre_reporte}' no encontrado")
                continue
            
            reporte = reportes[0]
            
            # Solo revertir si está usando nuestro template personalizado
            if 'nakel_2024' in reporte.get('report_name', ''):
                logging.info(f"🔄 Revirtiendo '{nombre_reporte}' (ID: {reporte['id']})")
                logging.info(f"   {reporte['report_name']} → {report_name_original}")
                
                models.execute_kw(
                    ODOO_CONFIG['db'], uid, password,
                    'ir.actions.report', 'write',
                    [[reporte['id']], {
                        'report_name': report_name_original
                    }]
                )
                logging.info(f"   ✅ Revertido")
                actualizados += 1
            else:
                logging.info(f"⏭️  '{nombre_reporte}' ya está usando template original")
                
        except Exception as e:
            logging.error(f"❌ Error revirtiendo '{nombre_reporte}': {e}")
            errores += 1
    
    logging.info("\n" + "="*80)
    logging.info("📊 RESUMEN")
    logging.info("="*80)
    logging.info(f"✅ {actualizados} reportes revertidos")
    logging.info(f"❌ {errores} errores")
    
    logging.info("\n💡 Ahora los reportes originales funcionarán normalmente")
    logging.info("   Los templates personalizados 'Nakel 2024' seguirán disponibles como opciones separadas")

def main():
    models, uid = conectar_odoo()
    if not models or not uid:
        logging.error("No se pudo conectar a Odoo")
        return
    
    password = ODOO_CONFIG['pass']
    
    revertir_reportes_a_originales(models, uid, password)
    
    logging.info("\n⚠️  IMPORTANTE:")
    logging.info("   1. Reinicia Odoo para aplicar cambios")
    logging.info("   2. Limpia la caché del navegador")
    logging.info("   3. Los templates personalizados seguirán disponibles")
    logging.info("      pero solo se usarán si seleccionas explícitamente:")
    logging.info("      - 'Factura B Nakel 2024'")
    logging.info("      - 'Remito Nakel 2024'")

if __name__ == "__main__":
    main()

