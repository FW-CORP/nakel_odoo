#!/usr/bin/env python3
"""
Hace backup de los templates Nakel actuales en Odoo (master_18 o master_dev)
antes de aplicar cambios. Guarda en nakel/qweb/backups/

Uso:
  python3 backup_templates_master18.py
  python3 backup_templates_master18.py --instancia master_dev
"""

import sys
import os
import argparse
import xmlrpc.client
from datetime import datetime

sys.path.insert(0, '/media/klap/raid5/cursor_files')

try:
    from config_nakel import (
        ODOO_CONFIG_MASTER18,
        ODOO_CONFIG_MASTER_DEV,
        ODOO_CONFIG_DEV_MASTER_TEST,
    )
except ImportError:
    print("❌ Error: No se pudo importar config_nakel.py")
    sys.exit(1)

TEMPLATES_A_BACKUP = [
    'account.report_invoice_document_nakel_2024',
    'account.report_credit_note_document_nakel_2024',
    'stock.report_delivery_document_nakel_2024',
    'sale.report_saleorder_pro_forma',
]

def main():
    parser = argparse.ArgumentParser(description="Backup de templates Nakel vía XML-RPC")
    parser.add_argument(
        '--instancia',
        choices=['master18', 'master_dev', 'master_test'],
        default='master18',
        help='Base destino (default: master18)',
    )
    args = parser.parse_args()

    if args.instancia == 'master18':
        cfg, label = ODOO_CONFIG_MASTER18, 'master18'
    elif args.instancia == 'master_test':
        cfg, label = ODOO_CONFIG_DEV_MASTER_TEST, 'master_test'
    else:
        cfg, label = ODOO_CONFIG_MASTER_DEV, 'master_dev'

    script_dir = os.path.dirname(os.path.abspath(__file__))
    backup_dir = os.path.join(script_dir, '../backups')
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    print("="*80)
    print(f"💾 BACKUP DE TEMPLATES ({label})")
    print("="*80)
    
    try:
        common = xmlrpc.client.ServerProxy(f"{cfg['url']}/xmlrpc/2/common")
        uid = common.authenticate(
            cfg['db'],
            cfg['username'],
            cfg['password'],
            {}
        )
        if not uid:
            print("❌ Error de autenticación")
            return 1
        
        models = xmlrpc.client.ServerProxy(f"{cfg['url']}/xmlrpc/2/object")
        password = cfg['password']
        db = cfg['db']
        
        print(f"✅ Conectado a {db}\n")
        
        for key in TEMPLATES_A_BACKUP:
            templates = models.execute_kw(
                db, uid, password,
                'ir.ui.view', 'search_read',
                [[('key', '=', key), ('type', '=', 'qweb')]],
                {'fields': ['id', 'name', 'key', 'arch']}
            )
            
            if templates:
                t = templates[0]
                arch = t.get('arch', '')
                safe_name = key.replace('.', '_')
                backup_file = os.path.join(backup_dir, f"{safe_name}_{label}_{timestamp}.xml")
                
                # Envolver en formato XML legible
                content = f'<?xml version="1.0" encoding="utf-8"?>\n<!-- Backup: {t["name"]} - {timestamp} -->\n<!-- Key: {key} -->\n\n{arch}\n'
                
                with open(backup_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                print(f"✅ {key}")
                print(f"   → {backup_file}")
            else:
                print(f"⚠️  {key} - No existe en Odoo (se creará nuevo)")
        
        print(f"\n💾 Backups guardados en: {os.path.abspath(backup_dir)}")
        print("="*80)
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
