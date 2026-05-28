# -*- coding: utf-8 -*-

from odoo import models


def _nakel_truthy(value):
    return str(value or "").strip().lower() in ("1", "true", "yes", "y", "on")


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        res = super().session_info()
        icp = self.env["ir.config_parameter"].sudo()
        enabled = _nakel_truthy(icp.get_param("nakel_barcode_wave_validate_confirm.enable", "1"))
        res["nakel_barcode_wave_validate_confirm_enabled"] = enabled
        res["nakel_barcode_wave_validate_confirm_message"] = (
            icp.get_param(
                "nakel_barcode_wave_validate_confirm.message",
                "¿Realmente querés validar la OLA?",
            )
            or "¿Realmente querés validar la OLA?"
        )
        res["nakel_barcode_wave_validate_confirm_message_picking"] = (
            icp.get_param(
                "nakel_barcode_wave_validate_confirm.message_picking",
                "¿Realmente querés validar este picking?",
            )
            or "¿Realmente querés validar este picking?"
        )
        return res
