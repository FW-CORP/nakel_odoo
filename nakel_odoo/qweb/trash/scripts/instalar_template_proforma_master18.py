#!/usr/bin/env python3
"""
Script para instalar template mejorado de Factura Proforma en master_18
Diseño profesional con logo y branding de Nakel
"""

import sys
import os
import xmlrpc.client

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

def conectar_odoo():
    """Conecta a Odoo"""
    try:
        common = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/common')
        uid = common.authenticate(ODOO_CONFIG['db'], ODOO_CONFIG['user'], ODOO_CONFIG['pass'], {})
        if not uid:
            print(f"❌ Error de autenticación")
            return None, None
        models = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/object')
        return models, uid
    except Exception as e:
        print(f"❌ Error conectando a Odoo: {e}")
        return None, None

def leer_template(archivo):
    """Lee un template desde el archivo"""
    try:
        with open(archivo, 'r', encoding='utf-8') as f:
            contenido = f.read()
        
        # Extraer el contenido del template
        inicio = contenido.find('<t t-name=')
        if inicio == -1:
            return contenido.strip()
        
        template_content = contenido[inicio:].strip()
        return template_content
        
    except FileNotFoundError:
        print(f"❌ Error: No se encontró el archivo {archivo}")
        return None
    except Exception as e:
        print(f"❌ Error leyendo template: {e}")
        return None

def verificar_template_existente(models, uid, password, key):
    """Verifica si el template ya existe"""
    try:
        templates = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.ui.view', 'search_read',
            [[('key', '=', key), ('type', '=', 'qweb')]],
            {'fields': ['id', 'name', 'key', 'active']}
        )
        return templates
    except:
        return []

def instalar_template(models, uid, password):
    """Instala o actualiza el template"""
    print("="*80)
    print("📦 INSTALANDO TEMPLATE: Factura Proforma Nakel (Mejorado)")
    print("="*80)
    print(f"📊 Base de datos: {ODOO_CONFIG['db']}")
    print("="*80)
    
    key = 'sale.report_saleorder_pro_forma'
    nombre = 'Factura Proforma Nakel - Template Mejorado'
    archivo = '/media/klap/raid5/cursor_files/nakel/qweb/templates/sale.report_saleorder_pro_forma_NAKEL_MEJORADO.xml'
    modelo = 'sale.order'
    
    # Leer template
    print(f"\n📄 Leyendo template mejorado...")
    arch_content = leer_template(archivo)
    if not arch_content:
        return False
    
    print(f"✅ Template leído ({len(arch_content)} caracteres)")
    
    # Verificar si existe
    print(f"\n🔍 Verificando si el template ya existe...")
    templates_existentes = verificar_template_existente(models, uid, password, key)
    
    if templates_existentes:
        template_existente = templates_existentes[0]
        print(f"⚠️  Template existente encontrado (ID: {template_existente['id']})")
        
        # Actualizar template existente
        print(f"🔄 Actualizando template existente...")
        try:
            models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'ir.ui.view', 'write',
                [[template_existente['id']], {
                    'arch': arch_content,
                    'active': True
                }]
            )
            print(f"✅ Template actualizado exitosamente (ID: {template_existente['id']})")
            return True
        except Exception as e:
            print(f"❌ Error actualizando template: {e}")
            import traceback
            traceback.print_exc()
            return False
    else:
        # Crear nuevo template
        print(f"✨ Creando nuevo template...")
        try:
            template_id = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'ir.ui.view', 'create',
                [{
                    'name': nombre,
                    'type': 'qweb',
                    'key': key,
                    'arch': arch_content,
                    'model': modelo,
                    'priority': 16,
                    'active': True
                }]
            )
            print(f"✅ Template creado exitosamente (ID: {template_id})")
            return True
        except Exception as e:
            print(f"❌ Error creando template: {e}")
            import traceback
            traceback.print_exc()
            return False

def main():
    """Función principal"""
    models, uid = conectar_odoo()
    if not models or not uid:
        return
    
    password = ODOO_CONFIG['pass']
    
    # Instalar template
    if instalar_template(models, uid, password):
        print("\n" + "="*80)
        print("✅ INSTALACIÓN COMPLETADA")
        print("="*80)
        print("\n📋 Para probar el template:")
        print("   1. Ir a Ventas > Cotizaciones")
        print("   2. Seleccionar o crear una cotización")
        print("   3. Hacer clic en 'Imprimir' > 'PRO-FORMA Invoice'")
        print("   4. Se generará el PDF con el nuevo template mejorado")
        print("\n💡 El template incluye:")
        print("   ✅ Logo de la empresa (si está configurado)")
        print("   ✅ Branding 'NAKEL' prominente")
        print("   ✅ Diseño profesional y moderno")
        print("   ✅ Información completa de empresa y cliente")
        print("   ✅ Tabla de productos con mejor formato")
        print("   ✅ Totales destacados")
    else:
        print("\n❌ La instalación falló")

if __name__ == "__main__":
    main()

