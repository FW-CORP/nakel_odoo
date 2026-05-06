#!/usr/bin/env python3
"""
Script para analizar códigos postales (CP) de clientes en master_18
y su relación con zonas/etiquetas para planificación logística

Analiza:
- Clientes con/sin código postal
- Distribución de CP por zona/etiqueta
- Posibilidad de filtrado por CP para rutas
Autor: Corolla
Fecha: 2025-01-XX
"""

import sys
import os
import xmlrpc.client
import json
from collections import defaultdict
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

def conectar_odoo():
    """Conecta a Odoo master_18"""
    try:
        common = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/common')
        uid = common.authenticate(ODOO_CONFIG['db'], ODOO_CONFIG['user'], ODOO_CONFIG['pass'], {})
        if not uid:
            print(f"❌ Error de autenticación")
            return None, None
        models = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/object')
        print(f"✅ Conexión exitosa a Odoo {ODOO_CONFIG['db']}")
        return models, uid
    except Exception as e:
        print(f"❌ Error conectando a Odoo: {e}")
        return None, None

def obtener_clientes(models, uid, password):
    """Obtiene todos los clientes con información de CP y etiquetas"""
    try:
        print("\n📂 Obteniendo clientes...")
        clientes = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'res.partner', 'search_read',
            [[('customer_rank', '>', 0), ('is_company', '=', True)]],  # Solo clientes activos
            {
                'fields': [
                    'id', 'name', 'zip', 'city', 'state_id', 'country_id',
                    'category_id', 'street', 'street2', 'phone', 'mobile',
                    'customer_rank'
                ]
            }
        )
        print(f"✅ {len(clientes)} clientes encontrados")
        return clientes
    except Exception as e:
        print(f"❌ Error obteniendo clientes: {e}")
        import traceback
        traceback.print_exc()
        return []

def obtener_etiquetas(models, uid, password):
    """Obtiene todas las etiquetas de clientes (res.partner.category)"""
    try:
        etiquetas = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'res.partner.category', 'search_read',
            [[]],
            {'fields': ['id', 'name', 'parent_id']}
        )
        return etiquetas
    except Exception as e:
        print(f"⚠️  Error obteniendo etiquetas: {e}")
        return []

def normalizar_cp(zip_code):
    """Normaliza código postal (elimina espacios, convierte a string)"""
    if not zip_code:
        return None
    zip_str = str(zip_code).strip()
    if not zip_str or zip_str.upper() in ['NULL', 'NONE', '']:
        return None
    return zip_str

def analizar_codigos_postales(clientes, etiquetas):
    """Analiza códigos postales y su relación con zonas"""
    
    # Crear diccionario de etiquetas
    etiquetas_dict = {et['id']: et['name'] for et in etiquetas}
    
    # Estadísticas generales
    total_clientes = len(clientes)
    clientes_con_cp = 0
    clientes_sin_cp = 0
    cps_validos = 0
    cps_invalidos = 0
    
    # Análisis por CP
    cps_unicos = set()
    cp_por_zona = defaultdict(lambda: {'clientes': [], 'count': 0, 'cps_unicos': set()})
    clientes_sin_zona = []
    clientes_por_cp = defaultdict(list)
    
    # Análisis por zona
    zonas_con_cp = defaultdict(lambda: {'total': 0, 'con_cp': 0, 'sin_cp': 0, 'cps_unicos': set()})
    
    for cliente in clientes:
        zip_code = normalizar_cp(cliente.get('zip'))
        categorias_ids = cliente.get('category_id', [])
        categorias_nombres = [etiquetas_dict.get(cat_id, f'ID:{cat_id}') for cat_id in categorias_ids]
        
        # Contar clientes con/sin CP
        if zip_code:
            clientes_con_cp += 1
            cps_unicos.add(zip_code)
            cps_validos += 1
            
            # Agrupar por CP
            clientes_por_cp[zip_code].append(cliente)
        else:
            clientes_sin_cp += 1
            cps_invalidos += 1
        
        # Análisis por zona/etiqueta
        if categorias_ids:
            for cat_id in categorias_ids:
                zona_nombre = etiquetas_dict.get(cat_id, f'ID:{cat_id}')
                zonas_con_cp[zona_nombre]['total'] += 1
                if zip_code:
                    zonas_con_cp[zona_nombre]['con_cp'] += 1
                    zonas_con_cp[zona_nombre]['cps_unicos'].add(zip_code)
                    cp_por_zona[zona_nombre]['clientes'].append({
                        'id': cliente['id'],
                        'name': cliente['name'],
                        'zip': zip_code,
                        'city': cliente.get('city', ''),
                        'state': cliente.get('state_id', [False, ''])[1] if cliente.get('state_id') else ''
                    })
                    cp_por_zona[zona_nombre]['count'] += 1
                    cp_por_zona[zona_nombre]['cps_unicos'].add(zip_code)
                else:
                    zonas_con_cp[zona_nombre]['sin_cp'] += 1
        else:
            clientes_sin_zona.append(cliente)
    
    return {
        'total_clientes': total_clientes,
        'clientes_con_cp': clientes_con_cp,
        'clientes_sin_cp': clientes_sin_cp,
        'cps_validos': cps_validos,
        'cps_invalidos': cps_invalidos,
        'cps_unicos': len(cps_unicos),
        'cp_por_zona': dict(cp_por_zona),
        'zonas_con_cp': dict(zonas_con_cp),
        'clientes_sin_zona': clientes_sin_zona,
        'clientes_por_cp': {k: len(v) for k, v in clientes_por_cp.items()},
        'cps_lista': sorted(list(cps_unicos))
    }

def exportar_resultados(resultados, timestamp):
    """Exporta resultados a JSON y CSV"""
    
    # Preparar datos para JSON (convertir sets a listas)
    resultados_json = resultados.copy()
    # Convertir sets en cp_por_zona
    if 'cp_por_zona' in resultados_json:
        resultados_json['cp_por_zona'] = {
            zona: {
                'clientes': datos['clientes'],
                'count': datos['count'],
                'cps_unicos': sorted(list(datos['cps_unicos']))
            }
            for zona, datos in resultados_json['cp_por_zona'].items()
        }
    # Convertir sets en zonas_con_cp
    if 'zonas_con_cp' in resultados_json:
        resultados_json['zonas_con_cp'] = {
            zona: {
                'total': datos['total'],
                'con_cp': datos['con_cp'],
                'sin_cp': datos['sin_cp'],
                'cps_unicos': sorted(list(datos['cps_unicos']))
            }
            for zona, datos in resultados_json['zonas_con_cp'].items()
        }
    
    # JSON completo
    json_file = f"/media/klap/raid5/cursor_files/nakel/ventas/logistica/reportes/analisis_cp_clientes_master18_{timestamp}.json"
    os.makedirs(os.path.dirname(json_file), exist_ok=True)
    
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(resultados_json, f, indent=2, ensure_ascii=False)
    print(f"✅ JSON exportado: {json_file}")
    
    # CSV resumen por zona
    csv_file = f"/media/klap/raid5/cursor_files/nakel/ventas/logistica/reportes/analisis_cp_por_zona_master18_{timestamp}.csv"
    
    import csv
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['Zona', 'Total Clientes', 'Con CP', 'Sin CP', '% Con CP', 'CPs Únicos'])
        
        for zona, datos in sorted(resultados['zonas_con_cp'].items()):
            total = datos['total']
            con_cp = datos['con_cp']
            sin_cp = datos['sin_cp']
            pct = (con_cp / total * 100) if total > 0 else 0
            cps_unicos = len(datos['cps_unicos'])
            writer.writerow([zona, total, con_cp, sin_cp, f"{pct:.1f}%", cps_unicos])
    
    print(f"✅ CSV exportado: {csv_file}")

def main():
    print("="*80)
    print("📮 ANÁLISIS DE CÓDIGOS POSTALES DE CLIENTES - master_18")
    print("="*80)
    print("Objetivo: Evaluar uso de CP para planificación logística y rutas")
    print("="*80)
    
    models, uid = conectar_odoo()
    if not models or not uid:
        return
    
    password = ODOO_CONFIG['pass']
    
    # Obtener datos
    etiquetas = obtener_etiquetas(models, uid, password)
    print(f"✅ {len(etiquetas)} etiquetas encontradas")
    
    clientes = obtener_clientes(models, uid, password)
    if not clientes:
        print("❌ No se encontraron clientes")
        return
    
    # Analizar
    print("\n🔍 Analizando códigos postales...")
    resultados = analizar_codigos_postales(clientes, etiquetas)
    
    # Mostrar resultados
    print("\n" + "="*80)
    print("📊 RESULTADOS GENERALES")
    print("="*80)
    print(f"Total de clientes analizados: {resultados['total_clientes']:,}")
    print(f"Clientes con código postal: {resultados['clientes_con_cp']:,} ({resultados['clientes_con_cp']/resultados['total_clientes']*100:.1f}%)")
    print(f"Clientes sin código postal: {resultados['clientes_sin_cp']:,} ({resultados['clientes_sin_cp']/resultados['total_clientes']*100:.1f}%)")
    print(f"Códigos postales únicos: {resultados['cps_unicos']:,}")
    print(f"Clientes sin zona/etiqueta: {len(resultados['clientes_sin_zona']):,}")
    
    # Análisis por zona
    print("\n" + "="*80)
    print("📍 ANÁLISIS POR ZONA/ETIQUETA")
    print("="*80)
    
    zonas_ordenadas = sorted(
        resultados['zonas_con_cp'].items(),
        key=lambda x: x[1]['total'],
        reverse=True
    )
    
    print(f"\n{'Zona':<40} {'Total':>8} {'Con CP':>8} {'Sin CP':>8} {'% Con CP':>10} {'CPs Únicos':>12}")
    print("-" * 90)
    
    for zona, datos in zonas_ordenadas[:30]:  # Top 30
        total = datos['total']
        con_cp = datos['con_cp']
        sin_cp = datos['sin_cp']
        pct = (con_cp / total * 100) if total > 0 else 0
        cps_unicos = len(datos['cps_unicos'])
        print(f"{zona[:38]:<40} {total:>8} {con_cp:>8} {sin_cp:>8} {pct:>9.1f}% {cps_unicos:>12}")
    
    if len(zonas_ordenadas) > 30:
        print(f"\n... y {len(zonas_ordenadas) - 30} zonas más")
    
    # Evaluación para planificación
    print("\n" + "="*80)
    print("🎯 EVALUACIÓN PARA PLANIFICACIÓN LOGÍSTICA")
    print("="*80)
    
    zonas_completas = sum(1 for z, d in resultados['zonas_con_cp'].items() 
                         if d['total'] > 0 and d['con_cp'] / d['total'] >= 0.8)
    zonas_parciales = sum(1 for z, d in resultados['zonas_con_cp'].items() 
                         if d['total'] > 0 and 0.5 <= d['con_cp'] / d['total'] < 0.8)
    zonas_incompletas = sum(1 for z, d in resultados['zonas_con_cp'].items() 
                           if d['total'] > 0 and d['con_cp'] / d['total'] < 0.5)
    
    print(f"\nZonas con CP completo (≥80%): {zonas_completas}")
    print(f"Zonas con CP parcial (50-79%): {zonas_parciales}")
    print(f"Zonas con CP incompleto (<50%): {zonas_incompletas}")
    
    pct_total_con_cp = (resultados['clientes_con_cp'] / resultados['total_clientes'] * 100) if resultados['total_clientes'] > 0 else 0
    
    print(f"\n✅ CONCLUSIÓN:")
    if pct_total_con_cp >= 80:
        print(f"   Los códigos postales están bien completados ({pct_total_con_cp:.1f}%)")
        print(f"   ✅ SÍ se puede usar CP para planificar rutas y logística")
    elif pct_total_con_cp >= 50:
        print(f"   Los códigos postales están parcialmente completados ({pct_total_con_cp:.1f}%)")
        print(f"   ⚠️  Se puede usar CP para planificar, pero conviene completar los faltantes")
    else:
        print(f"   Los códigos postales están incompletos ({pct_total_con_cp:.1f}%)")
        print(f"   ❌ NO se recomienda usar solo CP para planificar sin completar antes")
    
    # Exportar
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    exportar_resultados(resultados, timestamp)
    
    print("\n" + "="*80)
    print("✅ ANÁLISIS COMPLETADO")
    print("="*80)

if __name__ == "__main__":
    main()
