#!/usr/bin/env python3
"""
Script para CORREGIR los reportes predeterminados en master_18
Hereda los templates originales y los reemplaza con nuestros templates personalizados
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
    """Lee el contenido completo del template"""
    try:
        with open(archivo, 'r', encoding='utf-8') as f:
            contenido = f.read()
        # Extraer solo el contenido del template (desde <t t-name=)
        inicio = contenido.find('<t t-name=')
        if inicio == -1:
            return contenido.strip()
        return contenido[inicio:].strip()
    except Exception as e:
        logging.error(f"Error leyendo {archivo}: {e}")
        return None

def heredar_template_original(models, uid, password, config):
    """
    ESTRATEGIA CORRECTA: Hereda el template original y lo reemplaza completamente
    
    Esto es mejor que crear un template nuevo porque:
    1. Odoo automáticamente usará nuestro template en vez del original
    2. No necesitamos cambiar los reportes
    3. Funciona con todos los reportes que usan el template original
    """
    logging.info(f"\n{'='*80}")
    logging.info(f"📄 PROCESANDO: {config['nombre']}")
    logging.info(f"{'='*80}")
    
    # Paso 1: Encontrar template original
    original_template = models.execute_kw(
        ODOO_CONFIG['db'], uid, password,
        'ir.ui.view', 'search_read',
        [[('key', '=', config['key_original']), ('type', '=', 'qweb')]],
        {'fields': ['id', 'name', 'key']}
    )
    
    if not original_template:
        logging.warning(f"⚠️  Template original '{config['key_original']}' no encontrado")
        logging.info(f"   Intentando buscar variantes...")
        
        # Buscar variantes (ej: con l10n_ar)
        variantes = [
            f"l10n_ar.{config['key_original']}",
            f"account.report_invoice_document",  # Sin sufijo
        ]
        
        for variante in variantes:
            original_template = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'ir.ui.view', 'search_read',
                [[('key', '=', variante), ('type', '=', 'qweb')]],
                {'fields': ['id', 'name', 'key']}
            )
            if original_template:
                logging.info(f"   ✅ Encontrado: {variante}")
                config['key_original'] = variante
                break
    
    if not original_template:
        logging.error(f"❌ No se pudo encontrar template original para {config['nombre']}")
        return False
    
    original_id = original_template[0]['id']
    logging.info(f"✅ Template original encontrado: {config['key_original']} (ID: {original_id})")
    
    # Paso 2: Leer nuestro template personalizado
    arch_content = leer_template(config['archivo_template'])
    if not arch_content:
        return False
    
    logging.info(f"✅ Template personalizado leído ({len(arch_content)} caracteres)")
    
    # Paso 3: Crear template heredado que REEMPLAZA el original
    # Usamos inherit_id para heredar, pero con xpath que reemplaza todo el contenido
    try:
        # Primero verificar si ya existe nuestro template personalizado
        template_existente = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.ui.view', 'search_read',
            [[('key', '=', config['key_personalizado']), ('type', '=', 'qweb')]],
            {'fields': ['id', 'inherit_id']}
        )
        
        if template_existente:
            template_id = template_existente[0]['id']
            logging.info(f"🔄 Actualizando template existente (ID: {template_id})...")
            
            models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'ir.ui.view', 'write',
                [[template_id], {
                    'arch': arch_content,
                    'inherit_id': original_id,
                    'priority': 999  # Alta prioridad para que tenga precedencia
                }]
            )
            logging.info(f"✅ Template actualizado")
        else:
            logging.info(f"✨ Creando template heredado...")
            
            template_id = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'ir.ui.view', 'create',
                [{
                    'name': config['nombre'],
                    'type': 'qweb',
                    'key': config['key_personalizado'],
                    'arch': arch_content,
                    'model': config['modelo'],
                    'inherit_id': original_id,
                    'priority': 999,  # Alta prioridad
                }]
            )
            logging.info(f"✅ Template creado (ID: {template_id})")
        
        # Paso 4: ACTUALIZAR el reporte original para que use nuestro template
        # Esto es clave: actualizamos el report_name del reporte original
        reportes = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.actions.report', 'search_read',
            [[('report_name', '=', config['key_original'])]],
            {'fields': ['id', 'name', 'report_name']}
        )
        
        if reportes:
            for reporte in reportes:
                logging.info(f"🔄 Actualizando reporte '{reporte['name']}' (ID: {reporte['id']})")
                logging.info(f"   Cambiando report_name: {config['key_original']} → {config['key_personalizado']}")
                
                models.execute_kw(
                    ODOO_CONFIG['db'], uid, password,
                    'ir.actions.report', 'write',
                    [[reporte['id']], {
                        'report_name': config['key_personalizado']
                    }]
                )
                logging.info(f"✅ Reporte actualizado")
        else:
            logging.warning(f"⚠️  No se encontró reporte para '{config['key_original']}'")
            logging.info(f"   Creando nuevo reporte...")
            
            modelo_id = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'ir.model', 'search',
                [[('model', '=', config['modelo'])]],
                {'limit': 1}
            )
            
            a4_paperformat_ids = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'report.paperformat', 'search',
                [[('name', '=', 'A4')]],
                {'limit': 1}
            )
            
            report_id = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'ir.actions.report', 'create',
                [{
                    'name': config['nombre'],
                    'model': config['modelo'],
                    'report_type': 'qweb-pdf',
                    'report_name': config['key_personalizado'],
                    'paperformat_id': a4_paperformat_ids[0] if a4_paperformat_ids else False,
                }]
            )
            logging.info(f"✅ Nuevo reporte creado (ID: {report_id})")
        
        return True
        
    except Exception as e:
        logging.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    logging.info("="*80)
    logging.info("🔧 CORRIGIENDO REPORTES PREDETERMINADOS EN MASTER_18")
    logging.info("   Hereda templates originales y actualiza reportes")
    logging.info("="*80)
    
    models, uid = conectar_odoo()
    if not models or not uid:
        return
    
    password = ODOO_CONFIG['pass']
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Configuración
    templates_config = [
        {
            'key_original': 'account.report_invoice_document',  # Template original
            'key_personalizado': 'account.report_invoice_document_nakel_2024',
            'archivo_template': os.path.join(script_dir, '../templates/account.report_invoice_document_nakel_2024_FACTURA_B_MEJORADO.xml'),
            'nombre': 'Factura B Nakel 2024',
            'modelo': 'account.move'
        },
        {
            'key_original': 'stock.report_delivery_document',  # O puede ser stock.report_deliveryslip
            'key_personalizado': 'stock.report_delivery_document_nakel_2024',
            'archivo_template': os.path.join(script_dir, '../templates/stock.report_delivery_document_nakel_2024_MEJORADO.xml'),
            'nombre': 'Remito Nakel 2024',
            'modelo': 'stock.picking'
        },
    ]
    
    resultados = []
    for config in templates_config:
        resultado = heredar_template_original(models, uid, password, config)
        resultados.append((config['nombre'], resultado))
    
    # Resumen
    logging.info("\n" + "="*80)
    logging.info("📊 RESUMEN")
    logging.info("="*80)
    
    exitosos = sum(1 for _, r in resultados if r)
    for nombre, resultado in resultados:
        estado = "✅ OK" if resultado else "❌ ERROR"
        logging.info(f"{estado} - {nombre}")
    
    logging.info(f"\n✅ {exitosos}/{len(resultados)} templates corregidos")
    logging.info("\n💡 IMPORTANTE:")
    logging.info("   1. Reinicia Odoo (o recarga el worker)")
    logging.info("   2. Limpia caché del navegador")
    logging.info("   3. Prueba generando un NUEVO documento (no uno en caché)")

if __name__ == "__main__":
    main()

