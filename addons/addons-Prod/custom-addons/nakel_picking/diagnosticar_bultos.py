#!/usr/bin/env python3
"""
Diagnóstico: por qué BULTO aparece vacío en el reporte.
Analiza productos de un lote para ver uom_po_id, packaging, etc.
Uso: python3 diagnosticar_bultos.py [batch_id]
"""

import os
import sys
import xmlrpc.client

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")))

try:
    from config_nakel import ODOO_CONFIG_MASTER18 as _CFG  # type: ignore
except ImportError:
    _CFG = {
        "url": os.environ.get("ODOO_URL", "https://nakel.net.ar"),
        "db": os.environ.get("ODOO_DB", "master_18"),
        "username": os.environ.get("ODOO_USERNAME", ""),
        "password": os.environ.get("ODOO_PASSWORD", ""),
    }

CONFIG = {
    "url": _CFG["url"],
    "db": _CFG["db"],
    "username": _CFG["username"],
    "password": _CFG["password"],
}

def conectar(config):
    common = xmlrpc.client.ServerProxy(f"{config['url']}/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(config['db'], config['username'], config['password'], {})
    if not uid:
        raise Exception("Autenticación fallida")
    uid = uid[0] if isinstance(uid, list) else uid
    models = xmlrpc.client.ServerProxy(f"{config['url']}/xmlrpc/2/object", allow_none=True)
    return models, uid

def main():
    args = [a for a in sys.argv[1:] if a != '--dev']
    if '--dev' in sys.argv:
        CONFIG['url'] = 'https://dev.nakel.net.ar'
        CONFIG['db'] = 'master_dev'
    if args and args[0] == 'list':
        batch_id = 'list'
    elif args:
        try:
            batch_id = int(args[0])
        except (ValueError, IndexError):
            batch_id = None
    else:
        batch_id = None
    if not batch_id:
        print("Uso: python3 diagnosticar_bultos.py <batch_id> [--dev]")
        print("      python3 diagnosticar_bultos.py list [--dev]  (listar lotes)")
        print("Ejemplo: python3 diagnosticar_bultos.py 5")
        sys.exit(1)

    try:
        models, uid = conectar(CONFIG)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    if batch_id == 'list':
        batches = models.execute_kw(CONFIG['db'], uid, CONFIG['password'],
            'stock.picking.batch', 'search_read', [[]],
            {'fields': ['id', 'name', 'state'], 'limit': 10, 'order': 'id desc'})
        print("\n📦 Últimos lotes:")
        for b in batches:
            print(f"   ID {b['id']}: {b['name']} - {b['state']}")
        return

    # Obtener batch y sus pickings
    batch = models.execute_kw(CONFIG['db'], uid, CONFIG['password'],
        'stock.picking.batch', 'read', [batch_id],
        {'fields': ['name', 'picking_ids']})[0]
    print(f"\n📦 Lote: {batch['name']} (ID: {batch_id})")
    print(f"   Traslados: {batch['picking_ids']}")

    # Obtener move lines de los pickings
    moves = models.execute_kw(CONFIG['db'], uid, CONFIG['password'],
        'stock.move', 'search_read',
        [[('picking_id', 'in', batch['picking_ids'])]],
        {'fields': ['product_id', 'product_uom_qty', 'product_uom', 'product_id']})
    
    product_ids = list(set(m['product_id'][0] for m in moves if m.get('product_id')))
    print(f"\n📋 Productos únicos en el lote: {len(product_ids)}")

    # Por cada producto, verificar config de bulto
    products = models.execute_kw(CONFIG['db'], uid, CONFIG['password'],
        'product.product', 'read', [product_ids],
        {'fields': ['name', 'default_code', 'product_tmpl_id', 'barcode']})

    tmpl_ids = list(set(p['product_tmpl_id'][0] for p in products))
    templates = models.execute_kw(CONFIG['db'], uid, CONFIG['password'],
        'product.template', 'read', [tmpl_ids],
        {'fields': ['name', 'uom_id', 'uom_po_id', 'packaging_ids']})

    # Leer UdMs
    uom_ids = set()
    for t in templates:
        if t.get('uom_id'):
            uom_ids.add(t['uom_id'][0])
        if t.get('uom_po_id'):
            uom_ids.add(t['uom_po_id'][0])
    
    uoms = {}
    if uom_ids:
        uom_recs = models.execute_kw(CONFIG['db'], uid, CONFIG['password'],
            'uom.uom', 'read', [list(uom_ids)],
            {'fields': ['name', 'factor_inv', 'factor']})
        uoms = {u['id']: u for u in uom_recs}

    # Leer packagings
    pkg_ids = []
    for t in templates:
        pkg_ids.extend(t.get('packaging_ids') or [])
    packagings = {}
    if pkg_ids:
        pkgs = models.execute_kw(CONFIG['db'], uid, CONFIG['password'],
            'product.packaging', 'read', [pkg_ids],
            {'fields': ['name', 'qty', 'product_id']})
        packagings = {p['id']: p for p in pkgs}

    tmpl_by_id = {t['id']: t for t in templates}
    prod_by_id = {p['id']: p for p in products}

    print("\n" + "="*70)
    print("DIAGNÓSTICO POR PRODUCTO")
    print("="*70)

    for p in products[:15]:  # Primeros 15
        pt = tmpl_by_id.get(p['product_tmpl_id'][0], {})
        uom_id = pt.get('uom_id')
        uom_po_id = pt.get('uom_po_id')
        pkg_ids = pt.get('packaging_ids') or []

        uom_po_ok = uom_po_id and uom_po_id != uom_id
        uom_po_factor = uoms.get(uom_po_id[0], {}).get('factor_inv', 0) if uom_po_id else 0
        uom_po_name = uoms.get(uom_po_id[0], {}).get('name', '') if uom_po_id else ''

        pkgs_info = []
        for pid in pkg_ids[:2]:
            pk = packagings.get(pid, {})
            pkgs_info.append(f"{pk.get('name', '?')} (qty={pk.get('qty', 0)})")

        print(f"\n📌 {p.get('default_code', '')} - {p.get('name', '')[:50]}")
        print(f"   uom_id: {uom_id} -> {uoms.get(uom_id[0], {}).get('name', '?') if uom_id else '-'}")
        print(f"   uom_po_id: {uom_po_id} -> {uom_po_name} (factor_inv={uom_po_factor})")
        print(f"   uom_po != uom_id: {uom_po_ok} {'✅' if uom_po_ok and uom_po_factor > 1 else '❌'}")
        print(f"   packaging_ids: {pkg_ids[:3]}... {pkgs_info if pkgs_info else '❌ vacío'}")

    print("\n" + "="*70)
    print("RESUMEN")
    print("="*70)
    con_uom_po = sum(1 for t in templates if t.get('uom_po_id') and t['uom_po_id'] != t.get('uom_id'))
    con_packaging = sum(1 for t in templates if t.get('packaging_ids'))
    print(f"  Productos con uom_po_id != uom_id: {con_uom_po}/{len(templates)}")
    print(f"  Productos con packaging_ids: {con_packaging}/{len(templates)}")
    print("\n  Si ambos son 0, el bulto no está configurado en el producto.")
    print("  Configurar: Producto → pestaña Compras → 'Unidad de medida de compra'")
    print("  O: Producto → Embalajes (packaging)")

if __name__ == '__main__':
    main()
