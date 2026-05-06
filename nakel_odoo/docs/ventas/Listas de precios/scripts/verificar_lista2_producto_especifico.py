#!/usr/bin/env python3
"""
Script para verificar específicamente por qué Lista 2 no aparece en la vista del producto
pero sí funciona en ventas
Autor: Corolla
Fecha: 2025-12-29
"""

import sys
sys.path.insert(0, '/media/klap/raid5/cursor_files')

try:
    from config_nakel import ODOO_CONFIG_MASTER_DEV
except ImportError:
    print("❌ Error: No se pudo importar config_nakel.py")
    sys.exit(1)

import xmlrpc.client

ODOO_CONFIG = {
    'url': ODOO_CONFIG_MASTER_DEV['url'],
    'db': ODOO_CONFIG_MASTER_DEV['db'],
    'user': ODOO_CONFIG_MASTER_DEV['username'],
    'pass': ODOO_CONFIG_MASTER_DEV['password']
}

def conectar_odoo():
    common = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/common')
    uid = common.authenticate(ODOO_CONFIG['db'], ODOO_CONFIG['user'], ODOO_CONFIG['pass'], {})
    if not uid:
        return None, None
    models = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG["url"]}/xmlrpc/2/object')
    return models, uid

def main():
    print("="*80)
    print("🔍 VERIFICACIÓN: ¿Por qué Lista 2 no aparece en vista del producto?")
    print("="*80)
    
    models, uid = conectar_odoo()
    if not models or not uid:
        return
    
    password = ODOO_CONFIG['pass']
    db = ODOO_CONFIG['db']
    
    # Buscar producto por nombre o código
    productos = models.execute_kw(db, uid, password, 'product.product', 'search_read',
        [[('name', 'ilike', 'HIG.CAMPANITA SOFT XXL S.H 4U.X100M')]],
        {'fields': ['id', 'name', 'default_code', 'product_tmpl_id'], 'limit': 1})
    
    if not productos:
        # Intentar buscar por código si se proporciona como argumento
        if len(sys.argv) > 1:
            codigo = sys.argv[1]
            productos = models.execute_kw(db, uid, password, 'product.product', 'search_read',
                [[('default_code', '=', codigo)]],
                {'fields': ['id', 'name', 'default_code', 'product_tmpl_id'], 'limit': 1})
        
        if not productos:
            print("❌ Producto no encontrado")
            print("   Uso: python3 verificar_lista2_producto_especifico.py [codigo_producto]")
            return
    
    producto = productos[0]
    product_id = producto['id']
    template_id = producto['product_tmpl_id'][0]
    
    print(f"\n📦 Producto: {producto['name']}")
    print(f"   ID Producto: {product_id}")
    print(f"   ID Template: {template_id}")
    
    # Buscar Lista 2
    lista2 = models.execute_kw(db, uid, password, 'product.pricelist', 'search_read',
        [[('name', 'ilike', 'Lista 2')]],
        {'fields': ['id', 'name']})
    
    if not lista2:
        print("❌ Lista 2 no encontrada")
        return
    
    lista2_id = lista2[0]['id']
    print(f"\n💰 Lista 2: {lista2[0]['name']} (ID: {lista2_id})")
    
    # Buscar TODAS las reglas en Lista 2
    todas_reglas = models.execute_kw(db, uid, password, 'product.pricelist.item', 'search_read',
        [[('pricelist_id', '=', lista2_id)]],
        {'fields': ['id', 'name', 'applied_on', 'product_id', 'product_tmpl_id', 
                   'categ_id', 'compute_price', 'base', 'fixed_price', 
                   'percent_price', 'price_discount', 'price_surcharge', 
                   'min_quantity', 'date_start', 'date_end']})
    
    print(f"\n📋 Total de reglas en Lista 2: {len(todas_reglas)}")
    
    # Buscar reglas que aplican a este producto específico
    reglas_que_aplican = []
    
    for regla in todas_reglas:
        aplica = False
        razon = []
        
        applied_on = regla.get('applied_on', '')
        
        if applied_on == '0_product_variant' and regla.get('product_id'):
            if regla['product_id'][0] == product_id:
                aplica = True
                razon.append("Regla directa al producto (variante)")
        elif applied_on == '1_product' and regla.get('product_tmpl_id'):
            if regla['product_tmpl_id'][0] == template_id:
                aplica = True
                razon.append("Regla al template del producto")
        elif applied_on == '2_product_category':
            # Verificar categoría del producto
            producto_info = models.execute_kw(db, uid, password, 'product.product', 'read',
                [[product_id]], {'fields': ['categ_id']})
            if producto_info and regla.get('categ_id'):
                categ_producto = producto_info[0]['categ_id'][0] if producto_info[0].get('categ_id') else None
                categ_regla = regla['categ_id'][0] if regla.get('categ_id') else None
                if categ_producto == categ_regla:
                    aplica = True
                    razon.append("Regla a nivel de categoría")
        elif applied_on == '3_global':
            aplica = True
            razon.append("Regla global (aplica a todos los productos)")
        
        if aplica:
            reglas_que_aplican.append((regla, razon))
    
    print(f"\n✅ Reglas que APLICAN a este producto: {len(reglas_que_aplican)}")
    print("="*80)
    
    for regla, razon in reglas_que_aplican:
        print(f"\n📌 Regla ID: {regla['id']}")
        print(f"   Razón: {', '.join(razon)}")
        print(f"   Aplicado a: {regla.get('applied_on', 'N/A')}")
        print(f"   Tipo de cálculo: {regla.get('compute_price', 'N/A')}")
        print(f"   Base: {regla.get('base', 'N/A')}")
        
        if regla.get('fixed_price'):
            print(f"   ⭐ Precio fijo: ${regla['fixed_price']}")
        if regla.get('percent_price'):
            print(f"   Porcentaje: {regla['percent_price']}%")
        if regla.get('price_discount'):
            print(f"   Descuento: {regla['price_discount']}%")
        if regla.get('price_surcharge'):
            print(f"   Recargo: ${regla['price_surcharge']}")
        
        print(f"   Cantidad mínima: {regla.get('min_quantity', 1)}")
        if regla.get('date_start'):
            print(f"   Fecha inicio: {regla['date_start']}")
        if regla.get('date_end'):
            print(f"   Fecha fin: {regla['date_end']}")
        
        # Determinar si aparecerá en la vista del producto
        compute_price = regla.get('compute_price', '')
        fixed_price = regla.get('fixed_price')
        
        aparecera_en_vista = False
        motivo_no_aparece = None
        
        if compute_price == 'fixed' and fixed_price:
            aparecera_en_vista = True
        elif compute_price in ['percentage', 'formula']:
            aparecera_en_vista = False
            motivo_no_aparece = f"Tipo '{compute_price}' no se muestra en vista simple"
        elif applied_on == '3_global':
            aparecera_en_vista = False
            motivo_no_aparece = "Regla global no se muestra en vista del producto"
        
        if aparecera_en_vista:
            print(f"   ✅ APARECERÁ en la vista 'Lista de precios' del producto")
        else:
            print(f"   ❌ NO APARECERÁ en la vista 'Lista de precios': {motivo_no_aparece}")
            print(f"      Pero SÍ funcionará en ventas (Odoo calcula el precio dinámicamente)")
    
    print("\n" + "="*80)
    print("💡 EXPLICACIÓN")
    print("="*80)
    print("Odoo solo muestra en la vista 'Lista de precios' del producto:")
    print("  ✅ Reglas con compute_price='fixed' y fixed_price definido")
    print("  ✅ Reglas aplicadas directamente al producto (no globales)")
    print("\nNo muestra:")
    print("  ❌ Reglas con compute_price='formula' o 'percentage'")
    print("  ❌ Reglas globales (applied_on='3_global')")
    print("  ❌ Reglas basadas en categoría si no coinciden exactamente")
    print("\nEsto es NORMAL: Odoo calcula el precio dinámicamente en ventas,")
    print("pero la vista del producto solo muestra reglas de precio fijo directas.")

if __name__ == "__main__":
    main()

