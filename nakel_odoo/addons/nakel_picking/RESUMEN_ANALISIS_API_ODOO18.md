# Análisis API Odoo 18 Enterprise - nakel_picking

**Fecha:** 2025-03-19  
**Fuente:** XML-RPC a dev.nakel.net.ar / master_dev  
**Versión Odoo:** 18.0+e-20250205

---

## ✅ Campos validados (correctos en el módulo)

### stock.picking.batch
| Campo | Tipo | Uso en nakel_picking |
|-------|------|----------------------|
| picking_ids | one2many | ✅ batch.picking_ids |
| name | char | ✅ batch.name |
| user_id | many2one | ✅ batch.user_id |
| state | selection | ✅ batch.state |

### stock.move.line
| Campo | Tipo | Uso en nakel_picking |
|-------|------|----------------------|
| product_id | many2one | ✅ move_line.product_id |
| quantity | float | ✅ move_line.quantity |
| product_uom_id | many2one | ✅ move_line.product_uom_id |
| location_id | many2one | ✅ move_line.location_id |
| location_dest_id | many2one | ✅ move_line.location_dest_id |
| lot_id | many2one | ✅ move_line.lot_id |
| package_id | many2one | ✅ move_line.package_id |
| result_package_id | many2one | ✅ move_line.result_package_id |

### stock.move
| Campo | Tipo | Uso en nakel_picking |
|-------|------|----------------------|
| product_id | many2one | ✅ move.product_id |
| product_uom_qty | float | ✅ move.product_uom_qty |
| product_uom | many2one | ✅ move.product_uom |
| location_id | many2one | ✅ move.location_id |
| location_dest_id | many2one | ✅ move.location_dest_id |
| lot_ids | many2many | ✅ move.lot_ids |

### product.template
| Campo | Tipo | Uso en nakel_picking |
|-------|------|----------------------|
| uom_id | many2one | ✅ pt.uom_id |
| uom_po_id | many2one | ✅ pt.uom_po_id (UdM compra, ej. Bulto x40) |
| packaging_ids | one2many | ✅ pt.packaging_ids |
| name | char | ✅ product.display_name |
| default_code | char | ✅ product.default_code |

### product.product
| Campo | Tipo | Uso en nakel_picking |
|-------|------|----------------------|
| product_tmpl_id | many2one | ✅ product.product_tmpl_id |
| packaging_ids | one2many | ✅ (heredado/relacionado) |
| barcode | char | ✅ line['product'].barcode |
| default_code | char | ✅ product.default_code |

### uom.uom
| Campo | Tipo | Uso en nakel_picking |
|-------|------|----------------------|
| name | char | ✅ uom.name |
| factor_inv | float | ✅ factor_inv (1 bulto = N unidades) |
| factor | float | ✅ factor |
| category_id | many2one | ✅ category_id |

**Ejemplo UdM en sistema:** Bulto x2 (factor_inv=2), Bulto x3 (factor_inv=3), Bulto x5 (factor_inv=5).

---

## ⚠️ product.packaging (Odoo 18)

| Campo | Estado | Nota |
|-------|--------|------|
| name | ✅ | Nombre del embalaje |
| qty | ✅ | Cantidad contenida |
| product_tmpl_id | ❌ NO EXISTE | En Odoo 18 usa **product_id** |
| product_id | ✅ | Alternativa (puede apuntar a template o variante) |
| product_uom_id | ✅ | UdM del embalaje |

**Impacto en nakel_picking:** El módulo usa `product.product_tmpl_id.packaging_ids` para obtener embalajes. Esa relación existe en product.template (one2many) y funciona. No accedemos directamente a product.packaging.product_tmpl_id, así que **no hay cambio necesario**.

---

## Ejecutar análisis

```bash
cd inventario/nakel_picking
python3 analizar_odoo18_api.py dev --batch-id 45    # dev.nakel.net.ar / master_test
python3 analizar_odoo18_api.py prod --batch-id 45   # nakel.net.ar / master_18 (según .env)
```

Las credenciales se leen desde el `.env` del vault:

- `/media/klap/raid5/cursor_files/nakel/.env`

Usa variables `ODOO_MASTER_DEV_*` (dev) y `ODOO_MASTER18_*` (prod).
