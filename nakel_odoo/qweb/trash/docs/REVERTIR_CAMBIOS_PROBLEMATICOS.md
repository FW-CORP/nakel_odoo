# 🔧 Instrucciones para Revertir Cambios Problemáticos

## ⚠️ Problema Detectado

Odoo está muy lento (504 Gateway Timeout) después de actualizar los reportes. Esto probablemente se debe a que forzamos TODOS los reportes a usar templates personalizados, lo cual puede causar problemas.

## 🛠️ Solución: Revertir Reportes a Valores Originales

### Opción 1: Script Automático (Cuando Odoo responda)

```bash
cd /media/klap/raid5/cursor_files/nakel/qweb/scripts
python3 revertir_cambios_problematicos_master18.py
```

### Opción 2: SQL Directo (Más Rápido)

Si Odoo no responde, ejecuta esto en PostgreSQL:

```sql
-- Conectar a PostgreSQL
sudo -u postgres psql master_18

-- Revertir reportes de Facturas
UPDATE ir_actions_report 
SET report_name = 'account.report_invoice_with_payments' 
WHERE name = 'PDF' AND model = 'account.move';

UPDATE ir_actions_report 
SET report_name = 'account.report_invoice' 
WHERE name = 'PDF without Payment' AND model = 'account.move';

UPDATE ir_actions_report 
SET report_name = 'account.report_original_vendor_bill' 
WHERE name = 'Original Bills' AND model = 'account.move';

-- Revertir reportes de Remitos
UPDATE ir_actions_report 
SET report_name = 'stock.report_deliveryslip' 
WHERE name = 'Delivery Slip' AND model = 'stock.picking';

UPDATE ir_actions_report 
SET report_name = 'stock.report_picking_packages' 
WHERE name = 'Packages' AND model = 'stock.picking';

UPDATE ir_actions_report 
SET report_name = 'stock.report_picking' 
WHERE name = 'Picking Operations' AND model = 'stock.picking';

UPDATE ir_actions_report 
SET report_name = 'stock.report_reception' 
WHERE name = 'Reception Report' AND model = 'stock.picking';

UPDATE ir_actions_report 
SET report_name = 'stock.report_return_slip' 
WHERE name = 'Return slip' AND model = 'stock.picking';
```

### Opción 3: Restaurar Templates desde Backups

Si los templates están dañados:

```bash
# Los backups están en:
/media/klap/raid5/cursor_files/nakel/qweb/backups/

# Para restaurar, usa el script:
cd /media/klap/raid5/cursor_files/nakel/qweb/scripts
python3 restaurar_template_desde_backup.py
```

## ✅ Después de Revertir

1. **Reinicia Odoo:**
   ```bash
   sudo systemctl restart odoo
   ```

2. **Verifica que responde:**
   ```bash
   curl http://localhost:8069/web/health
   ```

3. **Limpia caché del navegador**

## 📋 Estado Final Deseado

- ✅ Los reportes **originales** funcionan normalmente
- ✅ Los templates **personalizados** están disponibles como opciones separadas:
  - "Factura B Nakel 2024" → usa `account.report_invoice_document_nakel_2024`
  - "Remito Nakel 2024" → usa `stock.report_delivery_document_nakel_2024`
  - "PRO-FORMA Invoice" → usa `sale.report_saleorder_pro_forma` (ya actualizado)

## 🎯 Lección Aprendida

**NO** forzar todos los reportes a usar templates personalizados. En su lugar:
- Dejar los reportes originales intactos
- Crear reportes nuevos con nombres específicos que usen nuestros templates
- O usar herencia correcta de templates (con xpath) en lugar de reemplazar completamente

