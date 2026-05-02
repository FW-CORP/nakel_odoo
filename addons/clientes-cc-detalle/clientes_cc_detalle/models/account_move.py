# -*- coding: utf-8 -*-

from odoo import _, api, models


class AccountMove(models.Model):
    _inherit = "account.move"

    # Por defecto mail.thread exige permiso de *escritura* para seguidores/chatter;
    # con solo lectura en account.move Odoo muestra "no puede modificar". Lectura
    # alcanza para abrir facturas/listas sin dar perm_write masivo.
    _mail_post_access = "read"

    @api.model
    def action_clientes_cc_open_my_sales_pivot(self):
        """Facturas/NC de cliente posteadas con comercial = usuario actual.

        Misma semántica que el smart button en contacto. Sirve para lista/pivote
        y como origen de datos para tableros (Spreadsheet) enlazando esta acción.
        """
        return {
            "type": "ir.actions.act_window",
            "name": _("Cuentas corrientes — mis ventas"),
            "res_model": "account.move",
            "view_mode": "pivot,list,graph,form",
            "views": [
                (False, "pivot"),
                (False, "list"),
                (False, "graph"),
                (False, "form"),
            ],
            "domain": [
                ("move_type", "in", ("out_invoice", "out_refund")),
                ("state", "=", "posted"),
                ("invoice_user_id", "=", self.env.uid),
            ],
            "context": {
                **self.env.context,
                "search_default_posted": 1,
            },
            "target": "current",
        }
