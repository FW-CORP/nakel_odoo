# Nakel - Menu de retenciones argentinas

Agrega accesos de menu para consultar retenciones emitidas por la localizacion argentina (`l10n_ar_tax`).

## Menus

- Contabilidad -> Proveedores -> Retenciones
- Contabilidad -> Clientes -> Retenciones
- Contabilidad -> Contabilidad -> Todas las retenciones

Desde el listado se pueden abrir las retenciones (`l10n_ar.payment.withholding`) e imprimir el reporte existente **Certificado de Retencion**.

## Firma

La firma del certificado se configura en:

`Contabilidad -> Configuracion -> Ajustes -> Firma en reportes`

Campos usados por el reporte:

- `res.company.l10n_ar_report_signature`
- `res.company.l10n_ar_report_signed_by`

## Instalacion

```bash
sudo -u odoo odoo -c /etc/odoo/odoo.conf -d master_dev -i nakel_l10n_ar_withholding_menu --stop-after-init
```

