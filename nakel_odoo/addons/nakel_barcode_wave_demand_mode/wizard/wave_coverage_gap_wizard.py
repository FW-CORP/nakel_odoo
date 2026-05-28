# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class NakelWaveCoverageGapWizard(models.TransientModel):
    _name = "nakel.wave.coverage.gap.wizard"
    _description = "Productos OV faltantes o incompletos en la ola"

    batch_id = fields.Many2one(
        comodel_name="stock.picking.batch",
        string="Ola",
        required=True,
        ondelete="cascade",
    )
    line_ids = fields.One2many(
        comodel_name="nakel.wave.coverage.gap.line",
        inverse_name="wizard_id",
        string="Detalle",
    )
    summary = fields.Char(string="Resumen", readonly=True)
    apply_demand_mode = fields.Boolean(
        string="Aplicar modo demanda después",
        default=True,
        help="Sube quantity al pedido OV en los PICK agregados (recomendado para Barcode).",
    )

    def action_add_selected_to_wave(self):
        self.ensure_one()
        lines = self.line_ids.filtered(lambda l: l.selected and l.fixable)
        if not lines:
            raise UserError(
                _("Marcá al menos una línea que se pueda agregar (sin PICK generado o PICK fuera de ola).")
            )
        self.batch_id._nakel_add_coverage_gaps_to_wave(
            lines,
            apply_demand_mode=self.apply_demand_mode,
        )
        return self.batch_id.action_nakel_open_coverage_gaps()

    def action_select_all_fixable(self):
        self.ensure_one()
        for line in self.line_ids:
            line.selected = line.fixable
        return self._nakel_reopen()

    def action_deselect_all(self):
        self.ensure_one()
        self.line_ids.write({"selected": False})
        return self._nakel_reopen()

    def _nakel_reopen(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Qué falta en la ola"),
            "res_model": "nakel.wave.coverage.gap.wizard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }


class NakelWaveCoverageGapLine(models.TransientModel):
    _name = "nakel.wave.coverage.gap.line"
    _description = "Línea faltante en cobertura OV de la ola"
    _order = "sale_order_id, product_id"

    wizard_id = fields.Many2one(
        comodel_name="nakel.wave.coverage.gap.wizard",
        required=True,
        ondelete="cascade",
    )
    selected = fields.Boolean(string="Agregar", default=True)
    fixable = fields.Boolean(
        string="Se puede agregar",
        compute="_compute_fixable",
        readonly=True,
    )
    sale_line_id = fields.Many2one(
        comodel_name="sale.order.line",
        string="Línea OV",
        readonly=True,
    )
    sale_order_id = fields.Many2one(
        comodel_name="sale.order",
        string="OV",
        readonly=True,
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Producto",
        readonly=True,
    )
    qty_ov = fields.Float(string="Pide OV", readonly=True, digits="Product Unit of Measure")
    qty_in_wave = fields.Float(
        string="En ola",
        readonly=True,
        digits="Product Unit of Measure",
    )
    gap_reason = fields.Selection(
        selection=[
            ("no_transfer", "Sin PICK generado"),
            ("outside_wave", "PICK fuera de la ola"),
            ("partial_wave", "Cantidad incompleta en ola"),
            ("reservation", "Reserva menor al pedido"),
        ],
        string="Motivo",
        readonly=True,
    )
    picking_names = fields.Char(string="PICK relacionado", readonly=True)
    action_hint = fields.Char(string="Qué hacer", readonly=True)

    @api.depends("gap_reason")
    def _compute_fixable(self):
        for line in self:
            line.fixable = line.gap_reason in (
                "no_transfer",
                "outside_wave",
                "partial_wave",
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("gap_reason") == "reservation":
                vals["selected"] = False
        return super().create(vals_list)
