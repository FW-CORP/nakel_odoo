#!/usr/bin/env python3
"""
Script CORREGIDO para instalar templates QWeb en master_18
SOLUCIONA: Crea/actualiza los ir.actions.report para que apunten a nuestros templates

ENFOQUE: Hereda los templates originales en lugar de crear nuevos
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

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def conectar_odoo():
    """Conecta a Odoo"""
    try:
        common = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/common')
        uid = common.authenticate(ODOO_CONFIG['db'], ODOO_CONFIG['user'], ODOO_CONFIG['pass'], {})
        if not uid:
            logging.error(f"❌ Error de autenticación")
            return None, None
        models = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/object')
        logging.info(f"✅ Conexión exitosa a Odoo {ODOO_CONFIG['db']}")
        return models, uid
    except Exception as e:
        logging.error(f"❌ Error conectando a Odoo: {e}")
        return None, None

def obtener_reporte_por_name(models, uid, password, report_name):
    """Obtiene un ir.actions.report por su report_name"""
    try:
        reports = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.actions.report', 'search_read',
            [[('report_name', '=', report_name)]],
            {'fields': ['id', 'name', 'report_name', 'model', 'report_type', 'active']}
        )
        return reports[0] if reports else None
    except Exception as e:
        logging.error(f"❌ Error buscando reporte {report_name}: {e}")
        return None

def obtener_template_por_key(models, uid, password, template_key):
    """Obtiene un template por su key"""
    try:
        templates = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.ui.view', 'search_read',
            [[('key', '=', template_key), ('type', '=', 'qweb')]],
            {'fields': ['id', 'name', 'key', 'inherit_id', 'arch', 'active']}
        )
        return templates[0] if templates else None
    except Exception as e:
        logging.error(f"❌ Error buscando template {template_key}: {e}")
        return None

def encontrar_template_original_para_reporte(models, uid, password, report_name):
    """Encuentra qué template está usando realmente un reporte"""
    report = obtener_reporte_por_name(models, uid, password, report_name)
    if not report:
        logging.warning(f"⚠️  Reporte '{report_name}' no encontrado")
        return None, None
    
    # Intentar buscar template con el mismo nombre que report_name
    template = obtener_template_por_key(models, uid, password, report['report_name'])
    
    if template:
        logging.info(f"✅ Template encontrado: {template['key']} (ID: {template['id']})")
        return template, report
    else:
        logging.warning(f"⚠️  No se encontró template para reporte '{report_name}'")
        return None, report

def leer_template_completo(archivo):
    """Lee el contenido completo del template"""
    try:
        with open(archivo, 'r', encoding='utf-8') as f:
            contenido = f.read()
        return contenido.strip()
    except FileNotFoundError:
        logging.error(f"❌ Error: No se encontró el archivo {archivo}")
        return None
    except Exception as e:
        logging.error(f"❌ Error leyendo template: {e}")
        return None

def instalar_template_con_herencia(models, uid, password, config):
    """
    Instala template heredando el original (OPCIÓN A - Recomendada)
    
    config = {
        'key_original': 'stock.report_delivery_document',  # Template original de Odoo
        'key_personalizado': 'stock.report_delivery_document_nakel_2024',  # Nuestro template
        'archivo_template': '/ruta/al/template.xml',
        'nombre': 'Remito Nakel 2024',
        'modelo': 'stock.picking'
    }
    """
    logging.info(f"\n{'='*80}")
    logging.info(f"📄 PROCESANDO: {config['nombre']}")
    logging.info(f"{'='*80}")
    
    # Paso 1: Verificar que el template original existe
    template_original = obtener_template_por_key(models, uid, password, config['key_original'])
    if not template_original:
        logging.warning(f"⚠️  Template original '{config['key_original']}' no encontrado")
        logging.info(f"   Intentando crear template nuevo sin herencia...")
        # Fallback: crear template nuevo
        return instalar_template_nuevo(models, uid, password, config)
    
    logging.info(f"✅ Template original encontrado: {config['key_original']} (ID: {template_original['id']})")
    
    # Paso 2: Leer nuestro template personalizado
    arch_content = leer_template_completo(config['archivo_template'])
    if not arch_content:
        return False
    
    logging.info(f"✅ Template personalizado leído ({len(arch_content)} caracteres)")
    
    # Paso 3: Verificar si ya existe nuestro template personalizado
    template_personalizado = obtener_template_por_key(models, uid, password, config['key_personalizado'])
    
    if template_personalizado:
        logging.info(f"⚠️  Template personalizado ya existe (ID: {template_personalizado['id']})")
        logging.info(f"   Actualizando template personalizado...")
        try:
            models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'ir.ui.view', 'write',
                [[template_personalizado['id']], {
                    'arch': arch_content,
                    'active': True,
                    'inherit_id': template_original['id'],  # Asegurar herencia
                    'priority': 999  # Alta prioridad para que tenga precedencia
                }]
            )
            logging.info(f"✅ Template personalizado actualizado (ID: {template_personalizado['id']})")
        except Exception as e:
            logging.error(f"❌ Error actualizando template: {e}")
            import traceback
            traceback.print_exc()
            return False
    else:
        # Crear template heredado
        logging.info(f"✨ Creando template heredado...")
        try:
            template_id = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'ir.ui.view', 'create',
                [{
                    'name': config['nombre'],
                    'type': 'qweb',
                    'key': config['key_personalizado'],
                    'arch': arch_content,
                    'model': config['modelo'],
                    'inherit_id': template_original['id'],
                    'priority': 999,  # Alta prioridad
                    'active': True
                }]
            )
            logging.info(f"✅ Template heredado creado (ID: {template_id})")
        except Exception as e:
            logging.error(f"❌ Error creando template: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # Paso 4: ACTUALIZAR el ir.actions.report para que use nuestro template
    # Buscar reporte que use el template original
    reportes = models.execute_kw(
        ODOO_CONFIG['db'], uid, password,
        'ir.actions.report', 'search_read',
        [[('report_name', '=', config['key_original'])]],
        {'fields': ['id', 'name', 'report_name', 'model', 'active']}
    )
    
    if not reportes:
        logging.warning(f"⚠️  No se encontró ir.actions.report para '{config['key_original']}'")
        logging.info(f"   Creando nuevo reporte...")
        # Crear nuevo reporte
        try:
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
                    'report_name': config['key_personalizado'],  # Usar nuestro template
                    # Nombre descargado del PDF (print_report_name en ir.actions.report).
                    # Para facturas usamos: "Factura Nakel - FA-A <numero>" (sin punto/establecimiento).
                    'print_report_name': (
                        f"'{config['nombre']} - %s %s' % ("
                        f"object.name.split(' ')[0], "
                        f"(object.name.split('-')[-1] if '-' in object.name else object.name)"
                        f")"
                        if config.get('key_personalizado') == 'account.report_invoice_document_nakel_2024'
                        else f"'{config['nombre']} - %s' % (object.name)"
                    ),
                    'paperformat_id': a4_paperformat_ids[0] if a4_paperformat_ids else False,
                    'binding_model_id': modelo_id[0] if modelo_id else False,
                    'binding_type': 'report',
                    'active': True
                }]
            )
            logging.info(f"✅ Nuevo reporte creado (ID: {report_id})")
            return True
        except Exception as e:
            logging.error(f"❌ Error creando reporte: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # Actualizar reporte existente para que use nuestro template
    for reporte in reportes:
        logging.info(f"🔄 Actualizando reporte '{reporte['name']}' (ID: {reporte['id']})")
        logging.info(f"   Cambiando report_name de '{reporte['report_name']}' a '{config['key_personalizado']}'")
        try:
            models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'ir.actions.report', 'write',
                [[reporte['id']], {
                    'report_name': config['key_personalizado'],  # Cambiar a nuestro template
                        # También actualizar el nombre del archivo descargado si el reporte ya existía.
                        'print_report_name': (
                            f"'{config['nombre']} - %s %s' % ("
                            f"object.name.split(' ')[0], "
                            f"(object.name.split('-')[-1] if '-' in object.name else object.name)"
                            f")"
                            if config.get('key_personalizado') == 'account.report_invoice_document_nakel_2024'
                            else f"'{config['nombre']} - %s' % (object.name)"
                        ),
                    'active': True
                }]
            )
            logging.info(f"✅ Reporte actualizado exitosamente")
        except Exception as e:
            logging.error(f"❌ Error actualizando reporte: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return True

def instalar_template_nuevo(models, uid, password, config):
    """Fallback: Crear template nuevo sin herencia (OPCIÓN B)"""
    logging.info(f"\n⚠️  Creando template nuevo (sin herencia)...")
    
    arch_content = leer_template_completo(config['archivo_template'])
    if not arch_content:
        return False
    
    try:
        template_id = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.ui.view', 'create',
            [{
                'name': config['nombre'],
                'type': 'qweb',
                'key': config['key_personalizado'],
                'arch': arch_content,
                'model': config['modelo'],
                'priority': 999,
                'active': True
            }]
        )
        logging.info(f"✅ Template nuevo creado (ID: {template_id})")
        return True
    except Exception as e:
        logging.error(f"❌ Error: {e}")
        return False

def verificar_instalacion(models, uid, password, config):
    """Verifica que el template y reporte están correctamente instalados"""
    logging.info(f"\n🔍 Verificando instalación de {config['nombre']}...")
    
    # Verificar template
    template = obtener_template_por_key(models, uid, password, config['key_personalizado'])
    if not template:
        logging.error(f"❌ Template '{config['key_personalizado']}' NO encontrado")
        return False
    else:
        logging.info(f"✅ Template encontrado (ID: {template['id']}, Activo: {template.get('active', False)})")
    
    # Verificar reporte
    reporte = obtener_reporte_por_name(models, uid, password, config['key_personalizado'])
    if not reporte:
        # Intentar con el nombre original
        reporte = obtener_reporte_por_name(models, uid, password, config['key_original'])
        if reporte and reporte['report_name'] == config['key_personalizado']:
            logging.info(f"✅ Reporte encontrado y usando nuestro template (ID: {reporte['id']})")
            return True
        else:
            logging.warning(f"⚠️  Reporte no está usando nuestro template personalizado")
            return False
    else:
        logging.info(f"✅ Reporte encontrado (ID: {reporte['id']}, Activo: {reporte.get('active', False)})")
        return True

def main():
    """Función principal"""
    logging.info("="*80)
    logging.info("📦 INSTALACIÓN CORREGIDA DE TEMPLATES QWEB EN MASTER_18")
    logging.info("   Hereda templates originales y actualiza ir.actions.report")
    logging.info("="*80)
    logging.info(f"📊 Base de datos: {ODOO_CONFIG['db']}")
    logging.info(f"🌐 URL: {ODOO_CONFIG['url']}")
    logging.info("="*80)
    
    models, uid = conectar_odoo()
    if not models or not uid:
        return
    
    password = ODOO_CONFIG['pass']
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Configuración de templates
    templates_config = [
        {
            'key_original': 'stock.report_delivery_document',  # Template original de Odoo
            'key_personalizado': 'stock.report_delivery_document_nakel_2024',
            'archivo_template': os.path.join(script_dir, '../templates/stock.report_delivery_document_nakel_2024_MEJORADO.xml'),
            'nombre': 'Remito Nakel 2024',
            'modelo': 'stock.picking'
        },
        {
            'key_original': 'account.report_invoice_document',  # Template original de Odoo
            'key_personalizado': 'account.report_invoice_document_nakel_2024',
            'archivo_template': os.path.join(script_dir, '../templates/account.report_invoice_document_nakel_2024_FACTURA_B_MEJORADO.xml'),
            'nombre': 'Factura Nakel',
            'modelo': 'account.move'
        },
        {
            'key_original': 'account.report_credit_note_document',  # O el que use Odoo para NC
            'key_personalizado': 'account.report_credit_note_document_nakel_2024',
            'archivo_template': os.path.join(script_dir, '../templates/account.report_invoice_document_nakel_2024_NOTA_CREDITO_MEJORADO.xml'),
            'nombre': 'Nota de Crédito Nakel 2024',
            'modelo': 'account.move'
        }
    ]
    
    resultados = []
    for config in templates_config:
        resultado = instalar_template_con_herencia(models, uid, password, config)
        resultados.append((config['nombre'], resultado))
        
        # Verificar instalación
        if resultado:
            verificar_instalacion(models, uid, password, config)
    
    # Resumen
    logging.info("\n" + "="*80)
    logging.info("📊 RESUMEN DE INSTALACIÓN")
    logging.info("="*80)
    
    exitosos = sum(1 for _, r in resultados if r)
    total = len(resultados)
    
    for nombre, resultado in resultados:
        estado = "✅ OK" if resultado else "❌ ERROR"
        logging.info(f"{estado} - {nombre}")
    
    logging.info(f"\n✅ {exitosos}/{total} templates instalados correctamente")
    
    if exitosos == total:
        logging.info("\n" + "="*80)
        logging.info("✅ INSTALACIÓN COMPLETADA")
        logging.info("="*80)
        logging.info("\n💡 IMPORTANTE:")
        logging.info("   1. Reinicia Odoo para que los cambios se apliquen completamente")
        logging.info("   2. Limpia la caché del navegador")
        logging.info("   3. Prueba generando un nuevo documento (no uno antiguo en caché)")
        logging.info("   4. Verifica que el formato mejorado aparezca en el PDF")
    else:
        logging.warning("\n⚠️  Algunos templates no se pudieron instalar. Revisa los errores arriba.")

if __name__ == "__main__":
    main()

