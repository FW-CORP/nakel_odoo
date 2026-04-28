# Análisis consultivo: `.deb` Odoo vs instalación productiva

**Tipo de trabajo:** solo lectura / comparación de listados. No se ejecutó instalación ni cambios en el sistema.

| Dato | Valor |
|------|--------|
| Fecha del análisis | 2026-04-22 (aprox., según entorno) |
| Paquete nuevo (archivo) | `/tmp/odoo_update/odoo_18.0+e.20260424_all.deb` |
| Versión en el `.deb` | **18.0+e.20260424** |
| Versión instalada (`dpkg`) | **18.0+e.20250205** |
| Tamaño aprox. del `.deb` | ~286 MB |

## Metodología

1. **Control del .deb:** `dpkg-deb -I` → `Version: 18.0+e.20260424`.
2. **Versión productiva:** `dpkg-query -W odoo` → `18.0+e.20250205`.
3. **Módulos “oficiales” en el .deb:** listado de rutas `*/odoo/addons/<nombre>/__manifest__.py` dentro del `.deb`, nombre = carpeta del módulo → **1356 nombres únicos** (tras normalizar).
4. **Módulos en disco (productivo):** directorios bajo `/usr/lib/python3/dist-packages/odoo/addons/` que contienen `__manifest__.py` → **1267 módulos**.
5. **Comparación:** ordenar ambas listas y usar `comm` (intersección / solo en uno u otro).

**Importante:** esto compara **contenido del paquete Debian** vs **árbol actual en disco**. No sustituye a un entorno de prueba ni al changelog oficial de Odoo.

## Resumen de impacto en módulos ( addons estándar )

| Concepto | Cantidad | Significado |
|----------|----------|-------------|
| En **ambos** (.deb y productivo) | **1260** | Al instalar/actualizar el `.deb`, estos módulos **se desplegarán con la versión del paquete 20260424** (sustituyen archivos incluidos en el deb). |
| **Solo en el .deb** | **96** | Tras la actualización del paquete, **aparecerán como carpetas nuevas** bajo `odoo/addons` (módulos nuevos en este build respecto a lo que tenías en 20250205 en esa ruta). |
| **Solo en productivo** (bajo `odoo/addons`, con `__manifest__.py`) | **7** | Carpetas **no listadas** en el `.deb`; suelen ser **personalizaciones** mezcladas en la ruta del paquete. |

### Módulos que solo están en el `.deb` (96) — nuevos en el paquete respecto a tu árbol actual

```
account_add_gln
account_intrastat_services
account_no_followup
account_peppol_response
account_peppol_selfbilling
appointment_google_reserve
cloud_storage_migration
delivery_dhl_rest
delivery_usps_rest
hr_recruitment_sms
l10n_account_withholding_tax
l10n_account_withholding_tax_pos
l10n_be_codaclean
l10n_be_hr_payroll_acerta
l10n_be_hr_payroll_dmfa_sftp
l10n_be_hr_payroll_prisma
l10n_be_intrastat_services
l10n_bg_ledger
l10n_bg_reports_ledger
l10n_br_edi_fiscal_reform
l10n_br_edi_pos
l10n_br_edi_sale_fiscal_reform
l10n_br_website_sale_fiscal_reform
l10n_ch_hr_payroll_elm_transmission
l10n_ch_hr_payroll_elm_transmission_5_3
l10n_ch_hr_payroll_elm_transmission_account
l10n_cn_reports
l10n_co_edi_mandate
l10n_co_edi_pos
l10n_cz_reports_2025
l10n_din5008_expense
l10n_dk_fik
l10n_dk_nemhandel
l10n_dk_nemhandel_response
l10n_dk_rsu
l10n_do_check_printing
l10n_ee_intrastat
l10n_es_edi_verifactu
l10n_es_edi_verifactu_pos
l10n_eu_iot_scale_cert
l10n_fr_intrastat_services
l10n_gr_edi
l10n_gt_edi
l10n_hr_edi
l10n_id_efaktur_coretax
l10n_in_ewaybill_port
l10n_in_reports_gstr_document_summary
l10n_it_edi_ndd_account_dn
l10n_it_edi_sale
l10n_it_xml_export
l10n_jo_edi_extended
l10n_jo_edi_pos
l10n_kh
l10n_kh_reports
l10n_mr
l10n_mr_reports
l10n_my_edi_pos
l10n_my_hr_payroll
l10n_my_hr_payroll_account
l10n_nl_reports_vat_pay_wizard
l10n_om
l10n_pe_reports_lib
l10n_pl_edi
l10n_pl_reports_account_saft
l10n_pl_reports_jpk_fa
l10n_pl_taxable_supply_date
l10n_ro_cpv_code
l10n_ro_edi_stock
l10n_ro_edi_stock_batch
l10n_ro_efactura_synchronize
l10n_ro_saft_stock
l10n_rs_edi
l10n_se_bban
l10n_se_sie4_export
l10n_se_sie4_import
l10n_tr_nilvera_edispatch
l10n_tr_nilvera_einvoice_extended
l10n_tw_edi_ecpay
l10n_tw_edi_ecpay_website_sale
l10n_uy_edi_stock
l10n_uy_pos
l10n_uy_website_sale
l10n_vn_edi_viettel_pos
payment_nuvei
pos_edi_ubl
pos_event_sale
pos_mobile
pos_no_followup
pos_pine_labs
pos_tyro
sale_amazon_channel_management
sale_gelato
sale_gelato_stock
sms_twilio
website_sale_gelato
website_sale_mrp
```

### Módulos solo en productivo bajo `.../odoo/addons/` (no aparecen en el `.deb`)

Probable **código custom o terceros** copiado junto al core:

- `droggol_theme_common`
- `modulo_rg5329`
- `nakel_fix_pick`
- `nakel_picking`
- `nakel_wave_picking_link`
- `purchase_flete_markup`
- `theme_prime`

**Nota:** al actualizar con `dpkg`, los archivos **incluidos en el nuevo paquete** se reemplazan; las carpetas **no propiedad del paquete** suelen quedar en disco, pero **mezclar custom con `dist-packages/odoo/addons` es frágil**. Lo recomendable es mantener custom en `addons_path` dedicado (p. ej. `/opt/odoo/custom-addons`).

## `addons_path` en `odoo.conf` (referencia)

En la configuración actual del servidor aparece:

```text
/opt/odoo/custom-addons
```

Módulos con `__manifest__.py` detectados allí (solo consulta):

- `nakel_otel`
- `nakel_sale_margin`

Estos **no forman parte del .deb** estándar; una actualización del paquete `odoo` **no los sobrescribe** mientras sigan solo en esa ruta.

## Conclusiones

1. **Salto de versión de paquete:** `20250205` → `20260424` (~2,5 meses de builds enterprise en el nombre de versión).
2. **La mayoría de los módulos instalados vía deb** se alinean con el `.deb`: **1260** nombres coinciden y **recibirán el código del build nuevo** al actualizar el paquete.
3. **96 módulos** son **añadidos** en el paquete nuevo respecto a lo que había en tu árbol bajo `addons` al momento del análisis (muchas localizaciones / EDI / POS).
4. **Riesgo operativo principal** sigue siendo **custom bajo la misma ruta que el core** y el **postinst / conffiles** del deb; conviene **backup de BD**, **backup de filesystem** (`addons` custom) y prueba en clon si es posible.

---

*Documento generado en modo consulta; no implica ejecución de `apt`, `dpkg -i` ni reinicios.*
