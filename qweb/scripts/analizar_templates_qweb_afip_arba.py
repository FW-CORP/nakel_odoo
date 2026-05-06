#!/usr/bin/env python3
"""
Script para analizar templates QWeb de Facturas, Remitos y Notas de Crédito
y verificar cumplimiento con requisitos AFIP/ARBA/ARCA
Autor: Corolla
Fecha: 2025-12-27
"""

import sys
import os
import re
import json
import xmlrpc.client
from datetime import datetime
from collections import defaultdict

# Agregar ruta del proyecto
sys.path.insert(0, '/media/klap/raid5/cursor_files')

try:
    from config_nakel import ODOO_CONFIG_MASTER_DEV
except ImportError:
    print("❌ Error: No se pudo importar config_nakel.py")
    sys.exit(1)

# Configuración Odoo
ODOO_CONFIG = {
    'url': ODOO_CONFIG_MASTER_DEV['url'],
    'db': ODOO_CONFIG_MASTER_DEV['db'],
    'user': ODOO_CONFIG_MASTER_DEV['username'],
    'pass': ODOO_CONFIG_MASTER_DEV['password']
}

# Requisitos AFIP/ARBA/ARCA para Facturas
REQUISITOS_FACTURA = {
    'campos_obligatorios': [
        'CUIT emisor',
        'CUIT receptor',
        'Condición fiscal emisor',
        'Condición fiscal receptor',
        'Fecha emisión',
        'Número de factura',
        'Detalle productos/servicios',
        'Precios unitarios',
        'Totales',
        'Alicuotas IVA',
        'Importe total',
        'CAE/CAI',
        'Código de barras',
        'Leyenda Consumidor Final'
    ],
    'requisitos_2024': [
        'QR Code con información fiscal',
        'Información de percepciones',
        'Datos de transporte (si aplica)',
        'Leyendas específicas según tipo'
    ],
    'campos_afip_especificos': [
        'l10n_ar_cae',  # CAE
        'l10n_ar_cae_due_date',  # Vencimiento CAE
        'l10n_ar_afip_responsibility_type_id',  # Condición fiscal
        'qr_code_url',  # QR Code
        'l10n_ar_gross_income_number',  # IIBB
        'l10n_ar_afip_start_date'  # Inicio actividades
    ]
}

# Requisitos para Remitos
REQUISITOS_REMITO = {
    'campos_obligatorios': [
        'Datos del emisor',
        'Datos del destinatario',
        'Número de remito',
        'Fecha',
        'Detalle de mercadería',
        'Cantidades',
        'Firma y conformidad',
        'QR Code (según RG AFIP 4294/2024)'
    ]
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

def buscar_templates_por_modelo(models, uid, password, modelo):
    """Busca templates QWeb para un modelo específico"""
    try:
        templates = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.ui.view', 'search_read',
            [[('model', '=', modelo), ('type', '=', 'qweb')]],
            {'fields': ['id', 'name', 'key', 'model', 'arch', 'active']}
        )
        return templates
    except Exception as e:
        print(f"❌ Error buscando templates para {modelo}: {e}")
        return []

def buscar_reportes_por_modelo(models, uid, password, modelo):
    """Busca reportes (ir.actions.report) para un modelo"""
    try:
        reportes = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'ir.actions.report', 'search_read',
            [[('model', '=', modelo), ('report_type', '=', 'qweb-pdf')]],
            {'fields': ['id', 'name', 'model', 'report_name', 'report_file', 'paperformat_id']}
        )
        return reportes
    except Exception as e:
        print(f"❌ Error buscando reportes para {modelo}: {e}")
        return []

def analizar_campos_template(arch, tipo='factura'):
    """Analiza qué campos están presentes en el template"""
    campos_encontrados = {
        'cuit_emisor': False,
        'cuit_receptor': False,
        'condicion_fiscal': False,
        'fecha': False,
        'numero': False,
        'detalle_productos': False,
        'precios': False,
        'totales': False,
        'iva': False,
        'cae': False,
        'qr_code': False,
        'leyenda_consumidor_final': False,
        'percepciones': False,
        'iibb': False,
        'inicio_actividades': False
    }
    
    arch_lower = arch.lower() if arch else ''
    
    # Verificar campos
    if 'company_id.vat' in arch or 'company_id.vat' in arch_lower:
        campos_encontrados['cuit_emisor'] = True
    
    if 'partner_id.vat' in arch or 'partner_id.vat' in arch_lower:
        campos_encontrados['cuit_receptor'] = True
    
    if 'l10n_ar_afip_responsibility_type_id' in arch or 'l10n_ar_afip' in arch_lower:
        campos_encontrados['condicion_fiscal'] = True
    
    if 'invoice_date' in arch_lower or 'date' in arch_lower:
        campos_encontrados['fecha'] = True
    
    if 'o.name' in arch or '.name' in arch:
        campos_encontrados['numero'] = True
    
    if 'invoice_line_ids' in arch or 'move_ids' in arch or 'move_list' in arch:
        campos_encontrados['detalle_productos'] = True
    
    if 'price_unit' in arch_lower or 'price_subtotal' in arch_lower:
        campos_encontrados['precios'] = True
    
    if 'amount_total' in arch_lower or 'amount_untaxed' in arch_lower:
        campos_encontrados['totales'] = True
    
    if 'amount_tax' in arch_lower or 'tax' in arch_lower:
        campos_encontrados['iva'] = True
    
    if 'l10n_ar_cae' in arch or 'cae' in arch_lower:
        campos_encontrados['cae'] = True
    
    if 'qr_code' in arch_lower or 'qr' in arch_lower:
        campos_encontrados['qr_code'] = True
    
    if 'consumidor final' in arch_lower or 'consumidor' in arch_lower:
        campos_encontrados['leyenda_consumidor_final'] = True
    
    if 'percepcion' in arch_lower or 'perception' in arch_lower:
        campos_encontrados['percepciones'] = True
    
    if 'l10n_ar_gross_income' in arch or 'iibb' in arch_lower:
        campos_encontrados['iibb'] = True
    
    if 'l10n_ar_afip_start_date' in arch or 'inicio' in arch_lower:
        campos_encontrados['inicio_actividades'] = True
    
    return campos_encontrados

def verificar_cumplimiento_afip(campos_encontrados, tipo='factura'):
    """Verifica cumplimiento con requisitos AFIP"""
    if tipo == 'factura':
        requisitos = REQUISITOS_FACTURA
    else:
        requisitos = REQUISITOS_REMITO
    
    cumplimiento = {
        'cumplidos': [],
        'faltantes': [],
        'porcentaje': 0
    }
    
    # Mapeo de campos
    mapeo_campos = {
        'cuit_emisor': 'CUIT emisor',
        'cuit_receptor': 'CUIT receptor',
        'condicion_fiscal': 'Condición fiscal',
        'fecha': 'Fecha emisión',
        'numero': 'Número de factura',
        'detalle_productos': 'Detalle productos/servicios',
        'precios': 'Precios unitarios',
        'totales': 'Totales',
        'iva': 'Alicuotas IVA',
        'cae': 'CAE/CAI',
        'qr_code': 'QR Code con información fiscal',
        'leyenda_consumidor_final': 'Leyenda Consumidor Final',
        'percepciones': 'Información de percepciones',
        'iibb': 'IIBB',
        'inicio_actividades': 'Inicio de actividades'
    }
    
    total_requisitos = 0
    cumplidos = 0
    
    for campo_key, campo_nombre in mapeo_campos.items():
        if campo_key in campos_encontrados:
            total_requisitos += 1
            if campos_encontrados[campo_key]:
                cumplimiento['cumplidos'].append(campo_nombre)
                cumplidos += 1
            else:
                cumplimiento['faltantes'].append(campo_nombre)
    
    if total_requisitos > 0:
        cumplimiento['porcentaje'] = round((cumplidos / total_requisitos) * 100, 1)
    
    return cumplimiento

def main():
    """Función principal"""
    print("="*80)
    print("🔍 ANÁLISIS DE TEMPLATES QWEB - CUMPLIMIENTO AFIP/ARBA/ARCA")
    print("="*80)
    print(f"📊 Base de datos: {ODOO_CONFIG['db']}")
    print("="*80)
    
    # Conectar a Odoo
    models, uid = conectar_odoo()
    if not models or not uid:
        return
    
    password = ODOO_CONFIG['pass']
    
    # Analizar Facturas (account.move)
    print("\n📄 ANALIZANDO TEMPLATES DE FACTURAS (account.move)...")
    print("="*80)
    
    templates_facturas = buscar_templates_por_modelo(models, uid, password, 'account.move')
    reportes_facturas = buscar_reportes_por_modelo(models, uid, password, 'account.move')
    
    print(f"✅ {len(templates_facturas)} templates encontrados")
    print(f"✅ {len(reportes_facturas)} reportes encontrados\n")
    
    analisis_facturas = []
    for template in templates_facturas:
        arch = template.get('arch', '')
        campos = analizar_campos_template(arch, 'factura')
        cumplimiento = verificar_cumplimiento_afip(campos, 'factura')
        
        analisis_facturas.append({
            'template': template,
            'campos': campos,
            'cumplimiento': cumplimiento
        })
        
        print(f"  Template: {template['name']}")
        print(f"    Key: {template.get('key', 'N/A')}")
        print(f"    Cumplimiento: {cumplimiento['porcentaje']}%")
        print(f"    ✅ Campos presentes: {len(cumplimiento['cumplidos'])}")
        print(f"    ⚠️  Campos faltantes: {len(cumplimiento['faltantes'])}")
        if cumplimiento['faltantes']:
            print(f"    Faltantes: {', '.join(cumplimiento['faltantes'][:5])}")
        print()
    
    # Analizar Remitos (stock.picking)
    print("\n📦 ANALIZANDO TEMPLATES DE REMITOS (stock.picking)...")
    print("="*80)
    
    templates_remitos = buscar_templates_por_modelo(models, uid, password, 'stock.picking')
    reportes_remitos = buscar_reportes_por_modelo(models, uid, password, 'stock.picking')
    
    print(f"✅ {len(templates_remitos)} templates encontrados")
    print(f"✅ {len(reportes_remitos)} reportes encontrados\n")
    
    analisis_remitos = []
    for template in templates_remitos:
        arch = template.get('arch', '')
        campos = analizar_campos_template(arch, 'remito')
        cumplimiento = verificar_cumplimiento_afip(campos, 'remito')
        
        analisis_remitos.append({
            'template': template,
            'campos': campos,
            'cumplimiento': cumplimiento
        })
        
        print(f"  Template: {template['name']}")
        print(f"    Key: {template.get('key', 'N/A')}")
        print(f"    Cumplimiento: {cumplimiento['porcentaje']}%")
        print(f"    ✅ Campos presentes: {len(cumplimiento['cumplidos'])}")
        print(f"    ⚠️  Campos faltantes: {len(cumplimiento['faltantes'])}")
        print()
    
    # Generar reporte
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    reporte_path = f"/media/klap/raid5/cursor_files/nakel/qweb/reportes/analisis_templates_afip_{timestamp}.json"
    
    os.makedirs(os.path.dirname(reporte_path), exist_ok=True)
    
    reporte = {
        'fecha_analisis': datetime.now().isoformat(),
        'base_datos': ODOO_CONFIG['db'],
        'facturas': {
            'total_templates': len(templates_facturas),
            'total_reportes': len(reportes_facturas),
            'templates': [
                {
                    'id': a['template']['id'],
                    'nombre': a['template']['name'],
                    'key': a['template'].get('key'),
                    'cumplimiento_porcentaje': a['cumplimiento']['porcentaje'],
                    'campos_cumplidos': a['cumplimiento']['cumplidos'],
                    'campos_faltantes': a['cumplimiento']['faltantes']
                } for a in analisis_facturas
            ]
        },
        'remitos': {
            'total_templates': len(templates_remitos),
            'total_reportes': len(reportes_remitos),
            'templates': [
                {
                    'id': a['template']['id'],
                    'nombre': a['template']['name'],
                    'key': a['template'].get('key'),
                    'cumplimiento_porcentaje': a['cumplimiento']['porcentaje'],
                    'campos_cumplidos': a['cumplimiento']['cumplidos'],
                    'campos_faltantes': a['cumplimiento']['faltantes']
                } for a in analisis_remitos
            ]
        },
        'requisitos_afip': REQUISITOS_FACTURA
    }
    
    with open(reporte_path, 'w', encoding='utf-8') as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)
    
    print("\n" + "="*80)
    print("📊 RESUMEN")
    print("="*80)
    print(f"Facturas: {len(templates_facturas)} templates, {len(reportes_facturas)} reportes")
    print(f"Remitos: {len(templates_remitos)} templates, {len(reportes_remitos)} reportes")
    print(f"\n✅ Reporte guardado en: {reporte_path}")

if __name__ == "__main__":
    main()

