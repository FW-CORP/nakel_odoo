# -*- coding: utf-8 -*-

from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"

    # Por defecto mail.thread exige permiso de *escritura* para seguidores/chatter;
    # con solo lectura en account.move Odoo muestra "no puede modificar". Lectura
    # alcanza para abrir facturas/listas sin dar perm_write masivo.
    _mail_post_access = "read"

    @api.model
    def action_clientes_cc_open_my_sales_pivot(self):
        """Facturas/NC de cliente posteadas con comercial = usuario actual.

        Delega en la acción persistida (vistas pivote/gráfico/lista + contexto pivot_*).
        """
        return self.env["ir.actions.actions"]._for_xml_id(
            "clientes_cc_detalle.action_act_window_clientes_cc_my_sales"
        )
