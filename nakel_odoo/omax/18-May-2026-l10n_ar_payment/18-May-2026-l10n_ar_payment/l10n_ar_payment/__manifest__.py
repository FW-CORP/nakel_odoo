# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name' : 'Mass Payment Registration flow including Withholding and Payment Order Histroy - Argentina',
    'version': '18.0.1.1',
    'category': 'Accounting,Sales,Purchases',
    'sequence': 1,
    'author': 'OMAX Informatics',
    'website': 'https://www.omaxinformatics.com',
    'description' : '''
    ''',
    'depends' : ['account', 'l10n_ar','l10n_latam_check', 'l10n_ar_withholding',],
    'data': [
        'security/ir.model.access.csv',
        'report/report_payment_order.xml',
        'data/ir_sequence.xml',
        'data/ir_cron.xml',
        'views/ar_register_payments.xml',
        'views/account_payment_view.xml',
    ],
    'demo': [],
    'test': [],
    'license': 'OPL-1',
    'currency':'USD',
    'installable' : True,
    'auto_install' : False,
    'application' : True,
    'pre_init_hook': 'pre_init_check',
    'summary': '''
        Mass Payment Registration flow including Withholding and Payment Order Histroy
	''',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
