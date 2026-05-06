#!/usr/bin/env python3
"""
Script para instalar TODOS los templates mejorados (Remito, Factura B y Nota de Crédito)
en Odoo master_18
Cumple con RG AFIP 4294/2024 incluyendo QR Code obligatorio

Tras las vistas, enlaza paperformat y ir.actions.report vía nakel_qweb_sync_lib
(búsqueda dinámica, sin IDs fijos).
"""

import sys
import os
import xmlrpc.client

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)
sys.path.insert(0, '/media/klap/raid5/cursor_files')

from nakel_qweb_sync_lib import sincronizar_paperformat_y_acciones_factura

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

def instalar_template(models, uid, password, key, nombre, archivo, modelo='account.move'):
    """Instala o actualiza un template"""
    print(f"\n📄 Procesando: {nombre}")
    print(f"   Key: {key}")
    
    # Leer template
    arch_content = leer_template(archivo)
    if not arch_content:
        print(f"   ❌ No se pudo leer el template")
        return False
    
    print(f"   ✅ Template leído ({len(arch_content)} caracteres)")
    
    # Verificar si existe
    templates_existentes = verificar_template_existente(models, uid, password, key)
    
    if templates_existentes:
        template_existente = templates_existentes[0]
        print(f"   ⚠️  Template existente encontrado (ID: {template_existente['id']})")
        
        # Actualizar template existente
        print(f"   🔄 Actualizando template existente...")
        try:
            models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'ir.ui.view', 'write',
                [[template_existente['id']], {
                    'arch': arch_content,
                    'active': True
                }]
            )
            print(f"   ✅ Template actualizado exitosamente (ID: {template_existente['id']})")
            return True
        except Exception as e:
            print(f"   ❌ Error actualizando template: {e}")
            import traceback
            traceback.print_exc()
            return False
    else:
        # Crear nuevo template
        print(f"   ✨ Creando nuevo template...")
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
            print(f"   ✅ Template creado exitosamente (ID: {template_id})")
            return True
        except Exception as e:
            print(f"   ❌ Error creando template: {e}")
            import traceback
            traceback.print_exc()
            return False

def main():
    """Función principal"""
    print("="*80)
    print("📦 INSTALANDO TEMPLATES EN MASTER_18")
    print("   Remito, Factura B y Nota de Crédito Nakel 2024")
    print("="*80)
    print(f"📊 Base de datos: {ODOO_CONFIG['db']}")
    print(f"🌐 URL: {ODOO_CONFIG['url']}")
    print("="*80)
    
    models, uid = conectar_odoo()
    if not models or not uid:
        return
    
    password = ODOO_CONFIG['pass']
    
    # Templates a instalar
    templates = [
        {
            'key': 'stock.report_delivery_document_nakel_2024',
            'nombre': 'Remito Nakel 2024 - Template Mejorado',
            'archivo': '/media/klap/raid5/cursor_files/nakel/qweb/templates/stock.report_delivery_document_nakel_2024_MEJORADO.xml',
            'modelo': 'stock.picking'
        },
        {
            'key': 'account.report_invoice_document_nakel_2024',
            'nombre': 'Factura B Nakel 2024 - Template Mejorado',
            'archivo': '/media/klap/raid5/cursor_files/nakel/qweb/templates/account.report_invoice_document_nakel_2024_FACTURA_B_MEJORADO.xml',
            'modelo': 'account.move'
        },
        {
            'key': 'account.report_credit_note_document_nakel_2024',
            'nombre': 'Nota de Crédito Nakel 2024 - Template Mejorado',
            'archivo': '/media/klap/raid5/cursor_files/nakel/qweb/templates/account.report_invoice_document_nakel_2024_NOTA_CREDITO_MEJORADO.xml',
            'modelo': 'account.move'
        }
    ]
    
    resultados = []
    for template in templates:
        resultado = instalar_template(
            models, uid, password,
            template['key'],
            template['nombre'],
            template['archivo'],
            template['modelo']
        )
        resultados.append((template['nombre'], resultado))
    
    # Resumen
    print("\n" + "="*80)
    print("📊 RESUMEN DE INSTALACIÓN")
    print("="*80)
    
    exitosos = sum(1 for _, r in resultados if r)
    total = len(resultados)
    
    for nombre, resultado in resultados:
        estado = "✅ OK" if resultado else "❌ ERROR"
        print(f"{estado} - {nombre}")
    
    print(f"\n✅ {exitosos}/{total} templates instalados correctamente en master_18")

    # Paperformat A4 Portrait + acciones de reporte (factura / NC) por búsqueda
    if exitosos == total:
        print("\n" + "=" * 80)
        print("📎 Enlazando paperformat y reportes de factura / nota de crédito...")
        print("=" * 80)
        for etiqueta, ok, msg in sincronizar_paperformat_y_acciones_factura(
            models, uid, password, ODOO_CONFIG['db']
        ):
            estado = "✅" if ok else "⚠️"
            print(f"{estado} {etiqueta}: {msg}")
    
    if exitosos == total:
        print("\n" + "="*80)
        print("✅ INSTALACIÓN COMPLETADA EN MASTER_18")
        print("="*80)
        print("\n📋 Para probar los templates:")
        print("\n   REMITO:")
        print("   1. Ir a Inventario > Operaciones > Remitos")
        print("   2. Seleccionar o crear un remito")
        print("   3. Hacer clic en 'Imprimir' > 'Remito Nakel 2024'")
        print("\n   FACTURA B:")
        print("   1. Ir a Contabilidad > Facturas de Cliente")
        print("   2. Seleccionar o crear una factura (tipo Factura B)")
        print("   3. Hacer clic en 'Imprimir' > 'Factura B Nakel 2024'")
        print("\n   NOTA DE CRÉDITO:")
        print("   1. Ir a Contabilidad > Facturas de Cliente")
        print("   2. Seleccionar o crear una nota de crédito")
        print("   3. Hacer clic en 'Imprimir' > 'Nota de Crédito Nakel 2024'")
        print("\n💡 Si no ves los reportes en el menú de impresión:")
        print("   - Verificar que los reportes estén activos en master_18")
        print("   - Verificar permisos de usuario")
        print("   - Los reportes deben tener las keys correctas")
    else:
        print("\n⚠️  Algunos templates no se pudieron instalar. Revisa los errores arriba.")

if __name__ == "__main__":
    main()

