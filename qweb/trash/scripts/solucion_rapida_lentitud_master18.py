#!/usr/bin/env python3
"""
SOLUCIÓN RÁPIDA: Revierte cambios problemáticos que están causando lentitud en Odoo
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
    """Conecta a Odoo con timeout corto"""
    try:
        import socket
        socket.setdefaulttimeout(10)  # 10 segundos timeout
        
        common = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/common', timeout=10)
        uid = common.authenticate(ODOO_CONFIG['db'], ODOO_CONFIG['user'], ODOO_CONFIG['pass'], {})
        if not uid:
            return None, None
        models = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/object', timeout=10)
        return models, uid
    except Exception as e:
        logging.error(f"Error conectando (timeout probable): {e}")
        return None, None

def revertir_reportes_rapido(models, uid, password):
    """Revierte rápidamente los reportes problemáticos"""
    
    # Valores originales correctos
    reversiones = {
        'PDF': 'account.report_invoice_with_payments',
        'PDF without Payment': 'account.report_invoice',
        'Original Bills': 'account.report_original_vendor_bill',
        'Delivery Slip': 'stock.report_deliveryslip',
        'Packages': 'stock.report_picking_packages',
        'Picking Operations': 'stock.report_picking',
        'Reception Report': 'stock.report_reception',
        'Return slip': 'stock.report_return_slip',
    }
    
    actualizados = 0
    
    for nombre, report_name_original in reversiones.items():
        try:
            reportes = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'ir.actions.report', 'search',
                [[('name', '=', nombre)]],
                {'limit': 1}
            )
            
            if reportes:
                reporte_actual = models.execute_kw(
                    ODOO_CONFIG['db'], uid, password,
                    'ir.actions.report', 'read',
                    [[reportes[0]]],
                    {'fields': ['report_name']}
                )[0]
                
                if reporte_actual['report_name'] != report_name_original:
                    models.execute_kw(
                        ODOO_CONFIG['db'], uid, password,
                        'ir.actions.report', 'write',
                        [[reportes[0]], {'report_name': report_name_original}]
                    )
                    logging.info(f"✅ '{nombre}' revertido")
                    actualizados += 1
                    
        except Exception as e:
            logging.warning(f"⚠️  Error con '{nombre}': {e}")
    
    return actualizados

def main():
    print("="*80)
    print("🔧 SOLUCIÓN RÁPIDA: Revertir cambios problemáticos")
    print("="*80)
    
    models, uid = conectar_odoo()
    if not models or not uid:
        print("\n❌ No se pudo conectar a Odoo (probablemente está muy lento)")
        print("\n💡 EJECUTA ESTO MANUALMENTE EN EL SERVIDOR:")
        print("="*80)
        print("1. Reinicia Odoo:")
        print("   sudo systemctl restart odoo")
        print("")
        print("2. Si sigue lento, ejecuta este script de nuevo")
        print("   o restaura los backups manualmente desde:")
        print("   /media/klap/raid5/cursor_files/nakel/qweb/backups/")
        return
    
    password = ODOO_CONFIG['pass']
    
    actualizados = revertir_reportes_rapido(models, uid, password)
    
    print(f"\n✅ {actualizados} reportes revertidos")
    print("\n💡 AHORA:")
    print("   1. Reinicia Odoo: sudo systemctl restart odoo")
    print("   2. Limpia caché del navegador")
    print("   3. Los templates personalizados seguirán disponibles como:")
    print("      - 'Factura B Nakel 2024'")
    print("      - 'Remito Nakel 2024'")

if __name__ == "__main__":
    main()

