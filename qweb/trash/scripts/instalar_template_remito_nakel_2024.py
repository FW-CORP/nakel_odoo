#!/usr/bin/env python3
"""
Script para instalar el template mejorado de Remito Nakel 2024
Cumple con RG AFIP 4294/2024 incluyendo QR Code obligatorio
"""

import sys
import os
import xmlrpc.client

sys.path.insert(0, '/media/klap/raid5/cursor_files')

try:
    from config_nakel import ODOO_CONFIG_MASTER_DEV
except ImportError:
    print("❌ Error: No se pudo importar config_nakel.py")
    sys.exit(1)

ODOO_CONFIG = {
    'url': ODOO_CONFIG_MASTER_DEV['url'],
    'db': ODOO_CONFIG_MASTER_DEV['db'],
    'user': ODOO_CONFIG_MASTER_DEV['username'],
    'pass': ODOO_CONFIG_MASTER_DEV['password']
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

def leer_template_mejorado():
    """Lee el template mejorado desde el archivo"""
    template_path = '/media/klap/raid5/cursor_files/nakel/qweb/templates/stock.report_delivery_document_nakel_2024_MEJORADO.xml'
    
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            contenido = f.read()
        
        # Extraer solo el contenido del template (sin comentarios iniciales)
        # Buscar el inicio del template
        inicio = contenido.find('<t t-name="stock.report_delivery_document_nakel_2024">')
        if inicio == -1:
            # Si no encuentra, intentar sin el namespace
            inicio = contenido.find('<t t-name=')
            if inicio == -1:
                return contenido.strip()
        
        # Extraer desde el inicio del template
        template_content = contenido[inicio:].strip()
        return template_content
        
    except FileNotFoundError:
        print(f"❌ Error: No se encontró el archivo {template_path}")
        return None
    except Exception as e:
        print(f"❌ Error leyendo template: {e}")
        return None

def verificar_template_existente(models, uid, password):
    """Verifica si el template ya existe"""
    try:
        templates = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.ui.view', 'search_read',
            [[('key', '=', 'stock.report_delivery_document_nakel_2024'), ('type', '=', 'qweb')]],
            {'fields': ['id', 'name', 'key', 'active']}
        )
        return templates
    except:
        return []

def instalar_template(models, uid, password):
    """Instala o actualiza el template"""
    print("="*80)
    print("📦 INSTALANDO TEMPLATE: Remito Nakel 2024 (Mejorado)")
    print("="*80)
    
    # Leer template
    print("\n📄 Leyendo template mejorado...")
    arch_content = leer_template_mejorado()
    if not arch_content:
        return False
    
    print(f"✅ Template leído ({len(arch_content)} caracteres)")
    
    # Verificar si existe
    print("\n🔍 Verificando si el template ya existe...")
    templates_existentes = verificar_template_existente(models, uid, password)
    
    if templates_existentes:
        template_existente = templates_existentes[0]
        print(f"⚠️  Template existente encontrado (ID: {template_existente['id']})")
        print(f"   Nombre: {template_existente.get('name', 'N/A')}")
        print(f"   Activo: {template_existente.get('active', True)}")
        
        # Actualizar template existente
        print("\n🔄 Actualizando template existente...")
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
            return False
    else:
        # Crear nuevo template
        print("\n✨ Creando nuevo template...")
        try:
            template_id = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'ir.ui.view', 'create',
                [{
                    'name': 'Remito Nakel 2024 - Template Mejorado',
                    'type': 'qweb',
                    'key': 'stock.report_delivery_document_nakel_2024',
                    'arch': arch_content,
                    'model': 'stock.picking',
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

def verificar_reporte_asociado(models, uid, password):
    """Verifica que el reporte esté asociado al template"""
    print("\n🔍 Verificando reporte asociado...")
    try:
        reportes = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.actions.report', 'search_read',
            [[('report_name', '=', 'stock.report_delivery_document_nakel_2024')]],
            {'fields': ['id', 'name', 'report_name', 'model', 'active']}
        )
        
        if reportes:
            reporte = reportes[0]
            print(f"✅ Reporte encontrado:")
            print(f"   ID: {reporte['id']}")
            print(f"   Nombre: {reporte['name']}")
            print(f"   Modelo: {reporte['model']}")
            print(f"   Activo: {reporte.get('active', True)}")
            return True
        else:
            print("⚠️  No se encontró reporte 'stock.report_delivery_document_nakel_2024'")
            print("   El template se creó pero debe asociarse manualmente al reporte")
            return False
    except Exception as e:
        print(f"⚠️  Error verificando reporte: {e}")
        return False

def main():
    """Función principal"""
    models, uid = conectar_odoo()
    if not models or not uid:
        return
    
    password = ODOO_CONFIG['pass']
    
    # Instalar template
    if instalar_template(models, uid, password):
        # Verificar reporte
        verificar_reporte_asociado(models, uid, password)
        
        print("\n" + "="*80)
        print("✅ INSTALACIÓN COMPLETADA")
        print("="*80)
        print("\n📋 Para probar el template:")
        print("   1. Ir a Inventario > Operaciones > Remitos")
        print("   2. Seleccionar un remito (o crear uno nuevo)")
        print("   3. Hacer clic en 'Imprimir' > 'Remito Nakel 2024'")
        print("   4. Se generará el PDF con el nuevo template")
        print("\n💡 Si no ves el reporte 'Remito Nakel 2024' en el menú de impresión:")
        print("   - Verificar que el reporte esté activo")
        print("   - Verificar permisos de usuario")
    else:
        print("\n❌ La instalación falló")

if __name__ == "__main__":
    main()

