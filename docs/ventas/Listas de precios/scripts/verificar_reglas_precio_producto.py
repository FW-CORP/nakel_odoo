#!/usr/bin/env python3
"""
Script para verificar todas las reglas de precio de un producto específico
Incluye reglas directas del producto y reglas de listas de precios
Autor: Corolla
Fecha: 2025-12-29
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
        print(f"✅ Conexión exitosa a Odoo {ODOO_CONFIG['db']}")
        return models, uid
    except Exception as e:
        print(f"❌ Error conectando a Odoo: {e}")
        return None, None

def buscar_producto(models, uid, password, nombre_producto):
    """Busca un producto por nombre o código interno"""
    try:
        # Buscar por código interno
        productos = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'product.product', 'search_read',
            [[('default_code', '=', nombre_producto)]],
            {'fields': ['id', 'name', 'default_code', 'product_tmpl_id']}
        )
        
        if not productos:
            # Buscar por nombre
            productos = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'product.product', 'search_read',
                [[('name', 'ilike', nombre_producto)]],
                {'fields': ['id', 'name', 'default_code', 'product_tmpl_id']}
            )
        
        return productos[0] if productos else None
    except Exception as e:
        print(f"❌ Error buscando producto: {e}")
        return None

def obtener_reglas_precio_producto(models, uid, password, product_id, template_id):
    """Obtiene todas las reglas de precio para un producto"""
    reglas = []
    
    try:
        # Buscar reglas directas del producto (product_id)
        reglas_producto = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'product.pricelist.item', 'search_read',
            [[('product_id', '=', product_id)]],
            {'fields': ['id', 'pricelist_id', 'name', 'fixed_price', 'percent_price', 
                       'price_discount', 'price_surcharge', 'price_round', 
                       'price_min_margin', 'price_max_margin', 'base', 'compute_price',
                       'min_quantity', 'date_start', 'date_end', 'categ_id',
                       'product_tmpl_id', 'product_id']}
        )
        reglas.extend(reglas_producto)
        
        # Buscar reglas del template (product_tmpl_id)
        reglas_template = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'product.pricelist.item', 'search_read',
            [[('product_tmpl_id', '=', template_id), ('product_id', '=', False)]],
            {'fields': ['id', 'pricelist_id', 'name', 'fixed_price', 'percent_price', 
                       'price_discount', 'price_surcharge', 'price_round', 
                       'price_min_margin', 'price_max_margin', 'base', 'compute_price',
                       'min_quantity', 'date_start', 'date_end', 'categ_id',
                       'product_tmpl_id', 'product_id']}
        )
        reglas.extend(reglas_template)
        
        return reglas
    except Exception as e:
        print(f"❌ Error obteniendo reglas de precio: {e}")
        import traceback
        traceback.print_exc()
        return []

def obtener_listas_precio_producto(models, uid, password, product_id):
    """Obtiene las listas de precio que tienen reglas para este producto"""
    try:
        # Buscar todas las listas de precio activas
        listas = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'product.pricelist', 'search_read',
            [[('active', '=', True)]],
            {'fields': ['id', 'name', 'currency_id']}
        )
        
        listas_con_reglas = []
        for lista in listas:
            lista_id = lista['id']
            
            # Buscar reglas en esta lista que afecten a este producto
            reglas = models.execute_kw(
                ODOO_CONFIG['db'], uid, password,
                'product.pricelist.item', 'search_read',
                [[('pricelist_id', '=', lista_id), 
                  '|', '|',
                  ('product_id', '=', product_id),
                  ('product_tmpl_id', '=', product_id),  # Esto buscará por template también
                  ('applied_on', '=', '3_product_variant')]],
                {'fields': ['id', 'name', 'fixed_price', 'compute_price', 'base',
                           'percent_price', 'price_discount', 'price_surcharge',
                           'min_quantity']},
                {'limit': 1}
            )
            
            if not reglas:
                # Buscar también por template
                producto_info = models.execute_kw(
                    ODOO_CONFIG['db'], uid, password,
                    'product.product', 'read',
                    [[product_id]], {'fields': ['product_tmpl_id']}
                )
                if producto_info:
                    template_id = producto_info[0]['product_tmpl_id'][0]
                    reglas = models.execute_kw(
                        ODOO_CONFIG['db'], uid, password,
                        'product.pricelist.item', 'search_read',
                        [[('pricelist_id', '=', lista_id),
                          ('product_tmpl_id', '=', template_id)]],
                        {'fields': ['id', 'name', 'fixed_price', 'compute_price', 'base',
                                   'percent_price', 'price_discount', 'price_surcharge',
                                   'min_quantity']},
                        {'limit': 1}
                    )
            
            if reglas:
                listas_con_reglas.append((lista, reglas))
        
        return listas_con_reglas
    except Exception as e:
        print(f"❌ Error obteniendo listas de precio: {e}")
        import traceback
        traceback.print_exc()
        return []

def main():
    if len(sys.argv) < 2:
        print("Uso: python3 verificar_reglas_precio_producto.py 'nombre_o_codigo_producto'")
        print("Ejemplo: python3 verificar_reglas_precio_producto.py 'HIG.CAMPANITA SOFT XXL S.H 4U.X100M.-016-'")
        sys.exit(1)
    
    nombre_producto = sys.argv[1]
    
    print("="*80)
    print("🔍 VERIFICACIÓN DE REGLAS DE PRECIO")
    print("="*80)
    print(f"📦 Producto: {nombre_producto}")
    print(f"📊 Base de datos: {ODOO_CONFIG['db']}")
    print("="*80)
    
    models, uid = conectar_odoo()
    if not models or not uid:
        return
    
    password = ODOO_CONFIG['pass']
    
    # Buscar producto
    print(f"\n🔎 Buscando producto...")
    producto = buscar_producto(models, uid, password, nombre_producto)
    
    if not producto:
        print(f"❌ Producto no encontrado: {nombre_producto}")
        return
    
    product_id = producto['id']
    template_id = producto['product_tmpl_id'][0] if producto.get('product_tmpl_id') else None
    
    print(f"✅ Producto encontrado:")
    print(f"   ID: {product_id}")
    print(f"   Nombre: {producto.get('name')}")
    print(f"   Código: {producto.get('default_code', 'N/A')}")
    print(f"   Template ID: {template_id}")
    
    # Obtener reglas de precio
    print(f"\n📋 Obteniendo reglas de precio...")
    reglas = obtener_reglas_precio_producto(models, uid, password, product_id, template_id)
    
    print(f"\n📊 REGLAS DE PRECIO ENCONTRADAS: {len(reglas)}")
    print("="*80)
    
    if not reglas:
        print("⚠️  No se encontraron reglas de precio directas")
    else:
        for i, regla in enumerate(reglas, 1):
            lista_nombre = regla.get('pricelist_id', [False, 'N/A'])[1] if regla.get('pricelist_id') else 'N/A'
            lista_id = regla.get('pricelist_id', [False])[0] if regla.get('pricelist_id') else None
            
            print(f"\n{i}. Lista: {lista_nombre} (ID: {lista_id})")
            print(f"   Regla ID: {regla['id']}")
            print(f"   Nombre: {regla.get('name', 'N/A')}")
            print(f"   Tipo de cálculo: {regla.get('compute_price', 'N/A')}")
            
            if regla.get('fixed_price'):
                print(f"   Precio fijo: ${regla['fixed_price']}")
            if regla.get('percent_price'):
                print(f"   Porcentaje: {regla['percent_price']}%")
            if regla.get('price_discount'):
                print(f"   Descuento: {regla['price_discount']}%")
            if regla.get('price_surcharge'):
                print(f"   Recargo: ${regla['price_surcharge']}")
            
            print(f"   Base: {regla.get('base', 'N/A')}")
            print(f"   Cantidad mínima: {regla.get('min_quantity', 0)}")
            print(f"   Fecha inicio: {regla.get('date_start', 'N/A')}")
            print(f"   Fecha fin: {regla.get('date_end', 'N/A')}")
            
            if regla.get('product_id'):
                print(f"   Producto específico: {regla['product_id'][1]}")
            elif regla.get('product_tmpl_id'):
                print(f"   Template: {regla['product_tmpl_id'][1]}")
    
    # Buscar en todas las listas de precio
    print(f"\n🔍 Buscando en todas las listas de precio activas...")
    listas_con_reglas = obtener_listas_precio_producto(models, uid, password, product_id)
    
    print(f"\n📊 LISTAS DE PRECIO CON REGLAS PARA ESTE PRODUCTO: {len(listas_con_reglas)}")
    print("="*80)
    
    listas_encontradas = set()
    for lista, reglas_lista in listas_con_reglas:
        lista_nombre = lista.get('name', 'N/A')
        lista_id = lista['id']
        listas_encontradas.add(lista_nombre)
        print(f"\n✅ {lista_nombre} (ID: {lista_id})")
        for regla in reglas_lista:
            print(f"   Regla ID: {regla['id']}")
            print(f"   Tipo: {regla.get('compute_price', 'N/A')}")
            if regla.get('fixed_price'):
                print(f"   Precio: ${regla['fixed_price']}")
    
    # Verificar específicamente Lista 2
    print(f"\n🔎 Verificando específicamente 'Lista 2' o 'LISTA 2'...")
    lista2 = models.execute_kw(
        ODOO_CONFIG['db'], uid, password,
        'product.pricelist', 'search_read',
        [[('name', 'ilike', 'Lista 2')]],
        {'fields': ['id', 'name']}
    )
    
    if lista2:
        lista2_id = lista2[0]['id']
        lista2_nombre = lista2[0]['name']
        print(f"✅ {lista2_nombre} encontrada (ID: {lista2_id})")
        
        # Buscar reglas en Lista 2 para este producto
        reglas_lista2 = models.execute_kw(
            ODOO_CONFIG['db'], uid, password,
            'product.pricelist.item', 'search_read',
            [[('pricelist_id', '=', lista2_id)]],
            {'fields': ['id', 'name', 'pricelist_id', 'applied_on', 'product_id', 
                       'product_tmpl_id', 'categ_id', 'fixed_price', 'compute_price', 
                       'base', 'percent_price', 'price_discount', 'price_surcharge',
                       'min_quantity', 'date_start', 'date_end']}
        )
        
        print(f"\n📋 Reglas en {lista2_nombre}: {len(reglas_lista2)}")
        for regla in reglas_lista2:
            print(f"   Regla ID: {regla['id']}")
            print(f"   Aplicado a: {regla.get('applied_on', 'N/A')}")
            if regla.get('product_id'):
                print(f"   Producto: {regla['product_id'][1]} (ID: {regla['product_id'][0]})")
            if regla.get('product_tmpl_id'):
                print(f"   Template: {regla['product_tmpl_id'][1]} (ID: {regla['product_tmpl_id'][0]})")
            print(f"   Tipo: {regla.get('compute_price', 'N/A')}")
            if regla.get('fixed_price'):
                print(f"   Precio fijo: ${regla['fixed_price']}")
        
        # Verificar si hay alguna regla que afecte a este producto específico
        reglas_que_aplican = []
        for regla in reglas_lista2:
            aplica = False
            if regla.get('product_id') and regla['product_id'][0] == product_id:
                aplica = True
            elif regla.get('product_tmpl_id') and regla['product_tmpl_id'][0] == template_id:
                aplica = True
            elif regla.get('applied_on') in ['1_product', '2_product_category', '0_product_variant']:
                # Regla general que podría aplicar
                aplica = True
            
            if aplica:
                reglas_que_aplican.append(regla)
        
        if reglas_que_aplican:
            print(f"\n✅ Reglas que APLICAN a este producto: {len(reglas_que_aplican)}")
            for regla in reglas_que_aplican:
                print(f"   Regla ID: {regla['id']}, Tipo: {regla.get('compute_price', 'N/A')}")
        else:
            print(f"\n⚠️  No se encontraron reglas en {lista2_nombre} que apliquen directamente a este producto")
            print(f"   Esto podría explicar por qué no aparece en la vista 'Lista de precios'")
    else:
        print("❌ No se encontró 'Lista 2'")
    
    print("\n" + "="*80)
    print("💡 CONCLUSIÓN")
    print("="*80)
    print("Si la Lista 2 funciona en ventas pero no aparece en la vista del producto,")
    print("probablemente la regla está configurada con:")
    print("- Una fórmula o condición especial (compute_price = 'formula')")
    print("- Aplicada a nivel de categoría o global, no directamente al producto")
    print("- Una fecha de inicio/fin que afecta su visualización")

if __name__ == "__main__":
    main()

