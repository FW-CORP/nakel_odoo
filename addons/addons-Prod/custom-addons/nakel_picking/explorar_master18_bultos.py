#!/usr/bin/env python3
"""
Exploración master_18: bultos y UdM configurados en productos.
Conecta a nakel.net.ar / master_18 y analiza la configuración.
"""

import xmlrpc.client
import sys
import os

# Añadir raíz del proyecto para importar config_nakel
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Probar credenciales (nakel.net.ar master_18; si falla, usar master_dev)
def _load_configs():
    configs = []
    try:
        from config_nakel import ODOO_CONFIG_MASTER_18, ODOO_CONFIG_MASTER_DEV
        configs.append({
            'url': ODOO_CONFIG_MASTER_18['url'], 'db': ODOO_CONFIG_MASTER_18['db'],
            'username': ODOO_CONFIG_MASTER_18['username'], 'password': ODOO_CONFIG_MASTER_18['password'],
        })
        configs.append({
            'url': ODOO_CONFIG_MASTER_DEV['url'], 'db': ODOO_CONFIG_MASTER_DEV['db'],
            'username': ODOO_CONFIG_MASTER_DEV['username'], 'password': ODOO_CONFIG_MASTER_DEV['password'],
        })
    except ImportError:
        configs = [
            {'url': 'https://nakel.net.ar', 'db': 'master_18', 'username': 'odoo@nakel.net.ar', 'password': 'REDACTED'},
        ]
    return configs

CONFIGS = _load_configs()

def conectar(config):
    common = xmlrpc.client.ServerProxy(f"{config['url']}/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(config['db'], config['username'], config['password'], {})
    if not uid:
        return None, None
    uid = uid[0] if isinstance(uid, list) else uid
    models = xmlrpc.client.ServerProxy(f"{config['url']}/xmlrpc/2/object", allow_none=True)
    return models, uid

def main():
    print("🔍 Exploración master_18 - Bultos/UdM en productos\n")
    
    config = None
    models = uid = None
    for c in CONFIGS:
        print(f"Intentando {c['url']} / {c['db']} con {c['username']}...")
        try:
            common = xmlrpc.client.ServerProxy(f"{c['url']}/xmlrpc/2/common", allow_none=True)
            version = common.version()
            print(f"   Odoo {version.get('server_version', '?')}")
            models, uid = conectar(c)
            if models and uid:
                config = c
                print(f"✅ Conectado\n")
                break
            else:
                print(f"   ❌ authenticate devolvió: uid={uid}")
        except Exception as e:
            import traceback
            print(f"   ❌ {type(e).__name__}: {e}")
            traceback.print_exc()
    
    if not models or not config:
        print("❌ No se pudo conectar a master_18. Verifica credenciales.")
        sys.exit(1)

    db, pwd = config['db'], config['password']

    # 1. Estadísticas generales
    print("="*60)
    print("📊 ESTADÍSTICAS GENERALES")
    print("="*60)
    
    total_products = models.execute_kw(db, uid, pwd, 'product.template', 'search_count', [[('active', '=', True)]])
    print(f"  Productos activos (template): {total_products}")

    # Productos con uom_po_id != uom_id (UdM compra diferente)
    with_uom_po = models.execute_kw(db, uid, pwd, 'product.template', 'search', [
        [('active', '=', True), ('uom_po_id', '!=', False)]
    ])
    # Leer y comparar
    if with_uom_po:
        tmpls = models.execute_kw(db, uid, pwd, 'product.template', 'read', [with_uom_po[:500]],
            {'fields': ['uom_id', 'uom_po_id']})
        uom_po_different = sum(1 for t in tmpls if t.get('uom_po_id') and t.get('uom_id') and t['uom_po_id'][0] != t['uom_id'][0])
        print(f"  Con uom_po_id configurado: {len(with_uom_po)}")
        print(f"  Con uom_po_id != uom_id (bulto): {uom_po_different}")
    else:
        print(f"  Con uom_po_id != uom_id: 0")

    # Productos con packaging
    with_packaging = models.execute_kw(db, uid, pwd, 'product.template', 'search_count', [
        [('active', '=', True), ('packaging_ids', '!=', False)]
    ])
    print(f"  Con packaging_ids: {with_packaging}")

    # 2. Productos del reporte (ALF.CACHAFAZ, GUAYMALLEN, etc.)
    print("\n" + "="*60)
    print("📦 PRODUCTOS DEL REPORTE (ej. ALF.CACHAFAZ, GUAYMALLEN)")
    print("="*60)
    
    for term in ['CACHAFAZ', 'GUAYMALLEN', '2815', '24.10']:
        ids = models.execute_kw(db, uid, pwd, 'product.template', 'search',
            [[('active', '=', True), '|', ('name', 'ilike', term), ('default_code', 'ilike', term)]],
            {'limit': 5})
        if ids:
            tmpls = models.execute_kw(db, uid, pwd, 'product.template', 'read', [ids],
                {'fields': ['name', 'default_code', 'uom_id', 'uom_po_id', 'packaging_ids']})
            for t in tmpls[:3]:
                uom_id = t.get('uom_id')
                uom_po = t.get('uom_po_id')
                uom_po_ok = uom_po and uom_id and uom_po[0] != uom_id[0]
                pkgs = len(t.get('packaging_ids') or [])
                print(f"\n  [{t.get('default_code', '')}] {t.get('name', '')[:45]}...")
                print(f"      uom_id: {uom_id}")
                print(f"      uom_po_id: {uom_po} {'✅ diferente' if uom_po_ok else '❌'}")
                print(f"      packaging_ids: {pkgs} embalajes")

    # 3. Lotes disponibles
    print("\n" + "="*60)
    print("📋 LOTES (stock.picking.batch)")
    print("="*60)
    batches = models.execute_kw(db, uid, pwd, 'stock.picking.batch', 'search_read', [[]],
        {'fields': ['id', 'name', 'state', 'picking_ids'], 'limit': 5, 'order': 'id desc'})
    if batches:
        for b in batches:
            print(f"  ID {b['id']}: {b['name']} - {b['state']} - {len(b.get('picking_ids', []))} traslados")
    else:
        print("  No hay lotes")

    # 4. UdMs tipo bulto en el sistema
    print("\n" + "="*60)
    print("📐 UdMs TIPO BULTO EN EL SISTEMA")
    print("="*60)
    uom_bultos = models.execute_kw(db, uid, pwd, 'uom.uom', 'search_read',
        [[('name', 'ilike', 'bulto')]],
        {'fields': ['name', 'factor_inv', 'factor'], 'limit': 15})
    if uom_bultos:
        for u in uom_bultos:
            print(f"  {u['name']}: factor_inv={u.get('factor_inv')}, factor={u.get('factor')}")
    else:
        print("  No hay UdMs con 'bulto' en el nombre")

    # 5. Muestra de productos con packaging
    if with_packaging > 0:
        print("\n" + "="*60)
        print("📦 MUESTRA: Productos con packaging")
        print("="*60)
        pkg_ids = models.execute_kw(db, uid, pwd, 'product.template', 'search',
            [[('active', '=', True), ('packaging_ids', '!=', False)]], {'limit': 5})
        tmpls = models.execute_kw(db, uid, pwd, 'product.template', 'read', [pkg_ids],
            {'fields': ['name', 'default_code', 'packaging_ids']})
        for t in tmpls:
            pkg_ids = t.get('packaging_ids') or []
            if pkg_ids:
                pkgs = models.execute_kw(db, uid, pwd, 'product.packaging', 'read', [pkg_ids[:3]],
                    {'fields': ['name', 'qty']})
                print(f"\n  [{t.get('default_code')}] {t.get('name', '')[:40]}...")
                for p in pkgs:
                    print(f"      → {p.get('name')} (qty={p.get('qty')})")

    print("\n✅ Exploración completada")

if __name__ == '__main__':
    main()
