#!/usr/bin/env python3
"""
Script URGENTE: Corrige los templates para manejar campos opcionales correctamente
Soluciona el error: AttributeError: 'account.move' object has no attribute 'qr_code_url'
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

def corregir_template_factura(models, uid, password):
    """Corrige el template de factura para manejar campos opcionales"""
    
    template_key = 'account.report_invoice_document_nakel_2024'
    
    # Leer template actual
    templates = models.execute_kw(
        ODOO_CONFIG['db'], uid, password,
        'ir.ui.view', 'search_read',
        [[('key', '=', template_key), ('type', '=', 'qweb')]],
        {'fields': ['id', 'arch']}
    )
    
    if not templates:
        logging.error(f"❌ Template '{template_key}' no encontrado")
        return False
    
    template = templates[0]
    arch = template['arch']
    
    # Corregir: reemplazar acceso directo a qr_code_url con verificación segura
    # El problema es que t-att-src se evalúa aunque esté dentro de t-if
    
    # Buscar y reemplazar patrones problemáticos
    import re
    
    # Patrón 1: <img t-att-src="o.qr_code_url" .../> dentro de t-if
    # Necesitamos asegurarnos que el t-if use hasattr o verificación correcta
    patterns_to_fix = [
        # Reemplazar img con qr_code_url directo
        (r'<img\s+t-att-src=["\']o\.qr_code_url["\']([^>]*)/>', 
         r'<t t-if="hasattr(o, \'qr_code_url\') and o.qr_code_url"><img t-att-src="o.qr_code_url"\1/></t>'),
        
        # Si ya hay t-if pero no verifica hasattr
        (r'<t t-if=["\']o\.qr_code_url["\']>', 
         r'<t t-if="hasattr(o, \'qr_code_url\') and o.qr_code_url">'),
    ]
    
    arch_corregido = arch
    cambios = 0
    
    for pattern, replacement in patterns_to_fix:
        matches = re.findall(pattern, arch_corregido)
        if matches:
            arch_corregido = re.sub(pattern, replacement, arch_corregido)
            cambios += len(matches)
            logging.info(f"   🔧 Corregidos {len(matches)} accesos a qr_code_url")
    
    # Si no se encontraron patrones, usar método más seguro:
    # Reemplazar toda la sección de QR code con verificación completa
    if cambios == 0:
        # Buscar la sección del QR code y reemplazarla completamente
        qr_section_pattern = r'(<!-- QR Code.*?-->\s*<div[^>]*>.*?<t t-if=["\']o\.qr_code_url["\']>.*?<img[^>]*t-att-src=["\']o\.qr_code_url["\'][^>]*/>.*?</t>.*?</div>)'
        
        qr_section_replacement = '''<!-- QR Code (OBLIGATORIO desde 2024 - RG AFIP 4294/2024) -->
                <div style="text-align: center; border: 1px solid #ccc; padding: 10px;">
                  <t t-if="hasattr(o, 'qr_code_url') and o.qr_code_url">
                    <img t-att-src="o.qr_code_url" alt="QR Code Factura" style="width: 120px; height: 120px;"/>
                  </t>
                  <t t-else="">
                    <div style="width: 120px; height: 120px; border: 1px dashed #ccc; margin: 0 auto; display: flex; align-items: center; justify-content: center;">
                      <small>QR Code<br/>(disponible en facturación electrónica)</small>
                    </div>
                  </t>
                  <br/>
                  <small>QR Code según RG AFIP 4294/2024</small>
                </div>'''
        
        if re.search(qr_section_pattern, arch_corregido, re.DOTALL):
            arch_corregido = re.sub(qr_section_pattern, qr_section_replacement, arch_corregido, flags=re.DOTALL)
            cambios += 1
            logging.info(f"   🔧 Sección QR code reemplazada completamente")
    
    # Método más simple: reemplazar directamente el string problemático
    if 'o.qr_code_url' in arch_corregido and 'hasattr' not in arch_corregido:
        # Buscar todas las ocurrencias de o.qr_code_url y protegerlas
        # Reemplazar t-att-src="o.qr_code_url" con verificación condicional
        arch_corregido = arch_corregido.replace(
            't-att-src="o.qr_code_url"',
            't-att-src="o.qr_code_url if hasattr(o, \'qr_code_url\') and o.qr_code_url else \'\'"'
        )
        cambios += 1
        logging.info(f"   🔧 Accesos a qr_code_url protegidos con hasattr")
    
    if cambios == 0:
        # Último recurso: envolver toda la sección de QR en un try-except de QWeb
        # O simplemente comentar/remover la sección problemática
        logging.warning("⚠️  No se encontraron patrones específicos, usando método genérico")
        # Reemplazar img problemático con placeholder
        arch_corregido = re.sub(
            r'<img[^>]*t-att-src=["\']o\.qr_code_url["\'][^>]*/>',
            r'<t t-if="hasattr(o, \'qr_code_url\') and getattr(o, \'qr_code_url\', None)"><img t-att-src="o.qr_code_url" alt="QR Code" style="width: 120px; height: 120px;"/></t><t t-else=""><div style="width: 120px; height: 120px; border: 1px dashed #ccc; margin: 0 auto; display: flex; align-items: center; justify-content: center; font-size: 10px;">QR Code<br/>(no disponible)</div></t>',
            arch_corregido
        )
        cambios += 1
    
    # Actualizar template
    try:
        models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.ui.view', 'write',
            [[template['id']], {'arch': arch_corregido}]
        )
        logging.info(f"✅ Template corregido exitosamente (ID: {template['id']})")
        logging.info(f"   {cambios} corrección(es) aplicada(s)")
        return True
    except Exception as e:
        logging.error(f"❌ Error actualizando template: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("="*80)
    print("🔧 CORRECCIÓN URGENTE: Templates con campos opcionales")
    print("="*80)
    
    models, uid = conectar_odoo()
    if not models or not uid:
        logging.error("No se pudo conectar a Odoo")
        return
    
    password = ODOO_CONFIG['pass']
    
    logging.info("📄 Corrigiendo template de Factura B...")
    resultado = corregir_template_factura(models, uid, password)
    
    if resultado:
        print("\n✅ CORRECCIÓN APLICADA")
        print("\n💡 Ahora:")
        print("   1. Intenta imprimir la factura de nuevo")
        print("   2. Si sigue fallando, revisa el log para más detalles")
    else:
        print("\n❌ No se pudo aplicar la corrección")

if __name__ == "__main__":
    main()

