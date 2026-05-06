#!/usr/bin/env python3
"""
Script para generar una proforma de ejemplo en master_18 y guardarla como PDF
"""

import sys
import os
import xmlrpc.client
import base64
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

def main():
    print('🔍 Buscando cotizaciones en master_18...\n')

    try:
        common = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/common')
        uid = common.authenticate(ODOO_CONFIG['db'], ODOO_CONFIG['user'], ODOO_CONFIG['pass'], {})
        
        models = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/object')
        password = ODOO_CONFIG['pass']
        db = ODOO_CONFIG['db']
        
        # Buscar cotizaciones - corregir la sintaxis
        cotizaciones = models.execute_kw(
            db, uid, password,
            'sale.order', 'search_read',
            [[('state', 'in', ['draft', 'sent', 'sale'])]],
            {'fields': ['id', 'name', 'partner_id', 'date_order', 'amount_total', 'state'], 
             'limit': 10, 
             'order': 'date_order desc'}
        )
        
        if not cotizaciones:
            print("⚠️  No se encontraron cotizaciones en master_18")
            print("💡 Necesitas crear una cotización primero desde la interfaz de Odoo")
            return
        
        print(f'✅ {len(cotizaciones)} cotizaciones encontradas\n')
        print('Cotizaciones disponibles:')
        for c in cotizaciones:
            partner_name = c['partner_id'][1] if c['partner_id'] else 'Sin cliente'
            print(f"  - {c['name']} | Cliente: {partner_name} | Total: ${c['amount_total']:.2f} | Estado: {c['state']}")
        
        # Buscar S00134 específicamente o usar la primera
        cotizacion_seleccionada = None
        for c in cotizaciones:
            if c['name'] == 'S00134':
                cotizacion_seleccionada = c
                break
        
        if not cotizacion_seleccionada:
            cotizacion_seleccionada = cotizaciones[0]
        
        print(f"\n📄 Generando proforma para: {cotizacion_seleccionada['name']}")
        partner_name = cotizacion_seleccionada['partner_id'][1] if cotizacion_seleccionada['partner_id'] else 'Sin cliente'
        print(f"   Cliente: {partner_name}")
        print(f"   ID: {cotizacion_seleccionada['id']}")
        
        # Obtener el reporte
        report_id = models.execute_kw(
            db, uid, password,
            'ir.actions.report', 'search',
            [[('report_name', '=', 'sale.report_saleorder_pro_forma')]],
            {'limit': 1}
        )
        
        if not report_id:
            print("⚠️  No se encontró el reporte de proforma")
            return
        
        print(f"\n📋 Generando PDF...")
        
        # Generar el PDF usando render_qweb_pdf
        try:
            pdf_result = models.execute_kw(
                db, uid, password,
                'ir.actions.report', 'render_qweb_pdf',
                [report_id[0], [cotizacion_seleccionada['id']]]
            )
            
            if pdf_result:
                # pdf_result suele ser: [Binary(...), 'pdf']  o  (Binary(...), 'pdf')
                pdf_bin = pdf_result[0] if isinstance(pdf_result, (list, tuple)) else pdf_result
                
                # Manejar xmlrpc.client.Binary correctamente
                if isinstance(pdf_bin, xmlrpc.client.Binary):
                    pdf_bytes = pdf_bin.data
                elif hasattr(pdf_bin, 'data'):
                    pdf_bytes = pdf_bin.data
                elif isinstance(pdf_bin, bytes):
                    pdf_bytes = pdf_bin
                elif isinstance(pdf_bin, str):
                    # Si viene como base64 string, decodificar
                    pdf_bytes = base64.b64decode(pdf_bin)
                else:
                    # Último recurso: intentar decodificar como base64
                    pdf_bytes = base64.b64decode(str(pdf_bin))
                
                # Guardar PDF
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                pdf_path = f"/media/klap/raid5/cursor_files/nakel/qweb/reportes/proforma_{cotizacion_seleccionada['name']}_{timestamp}.pdf"
                
                os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
                
                with open(pdf_path, 'wb') as f:
                    f.write(pdf_bytes)
                
                print(f"✅ PDF generado exitosamente ({len(pdf_bytes)} bytes)")
                print(f"📁 Guardado en: {pdf_path}")
                print(f"\n💡 Puedes abrir el archivo para ver cómo se ve el nuevo template mejorado")
            else:
                print("⚠️  No se pudo generar el PDF (datos vacíos)")
        except Exception as e:
            print(f"⚠️  Error generando PDF: {e}")
            import traceback
            traceback.print_exc()
            print(f"\n💡 Alternativa: Ve a Odoo master_18 y genera la proforma manualmente")
            print(f"   - Ir a Ventas > Cotizaciones")
            print(f"   - Seleccionar la cotización {cotizacion_seleccionada['name']}")
            print(f"   - Hacer clic en 'Imprimir' > 'PRO-FORMA Invoice'")
        
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

