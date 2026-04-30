# -*- coding: utf-8 -*-

from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        res = super().session_info()
        icp = self.env["ir.config_parameter"].sudo()
        soft = str(icp.get_param("nakel_fix_pick.barcode_soft_missing", "0")).strip().lower() in (
            "1",
            "true",
            "yes",
            "y",
            "on",
        )
        res["nakel_fix_pick_soft_missing"] = bool(soft)
        return res
