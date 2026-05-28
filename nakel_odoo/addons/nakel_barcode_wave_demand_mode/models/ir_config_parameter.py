# -*- coding: utf-8 -*-

from odoo import api, models

ICP_PREFIX = "nakel_barcode_wave_demand_mode"


class IrConfigParameter(models.Model):
    _inherit = "ir.config_parameter"

    @api.model
    def nakel_barcode_wave_demand_mode_ensure_default_parameters(self):
        defaults = (
            (f"{ICP_PREFIX}.enable", "0"),
            (f"{ICP_PREFIX}.apply_on", "pick"),
            (f"{ICP_PREFIX}.warehouses", ""),
            (f"{ICP_PREFIX}.log", "1"),
            (f"{ICP_PREFIX}.include_so_sibling_picks", "1"),
            (f"{ICP_PREFIX}.strict_batch", "1"),
        )
        for key, value in defaults:
            if not self.search_count([("key", "=", key)]):
                self.create({"key": key, "value": value})

    @api.model
    def nakel_barcode_wave_demand_mode_is_enabled(self):
        return self.sudo().get_param(f"{ICP_PREFIX}.enable", "0") in ("1", "True", "true")

    @api.model
    def nakel_barcode_wave_demand_mode_warehouse_ids(self):
        raw = (self.sudo().get_param(f"{ICP_PREFIX}.warehouses") or "").strip()
        if not raw:
            return []
        ids = []
        for part in raw.split(","):
            part = part.strip()
            if part.isdigit():
                ids.append(int(part))
        return ids

    @api.model
    def nakel_barcode_wave_demand_mode_should_log(self):
        return self.sudo().get_param(f"{ICP_PREFIX}.log", "1") in ("1", "True", "true")

    @api.model
    def nakel_barcode_wave_demand_mode_include_so_sibling_picks(self):
        return self.sudo().get_param(f"{ICP_PREFIX}.include_so_sibling_picks", "1") in (
            "1",
            "True",
            "true",
        )

    @api.model
    def nakel_barcode_wave_demand_mode_strict_batch(self):
        return self.sudo().get_param(f"{ICP_PREFIX}.strict_batch", "1") in (
            "1",
            "True",
            "true",
        )
