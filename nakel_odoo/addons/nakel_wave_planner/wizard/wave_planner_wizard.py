# -*- coding: utf-8 -*-

from datetime import datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression


class NakelWavePlannerWizard(models.TransientModel):
    _name = "nakel.wave.planner.wizard"
    _description = "Armar ola WAVE por zona (etiqueta cliente)"

    zone_tag_ids = fields.Many2many(
        comodel_name="res.partner.category",
        relation="nakel_wave_planner_wizard_zone_tag_rel",
        column1="wizard_id",
        column2="category_id",
        string="Zonas (etiquetas)",
        help=(
            "Zonas de reparto del cliente o de la dirección de entrega "
            "(ej. Zona Norte). Podés marcar varias a la vez."
        ),
    )
    salesperson_ids = fields.Many2many(
        comodel_name="res.users",
        relation="nakel_wave_planner_wizard_salesperson_rel",
        column1="wizard_id",
        column2="user_id",
        string="Vendedores",
        help="Filtrar pedidos por uno o más vendedores. Podés combinarlo con las zonas.",
    )
    date_planned = fields.Date(
        string="Filtrar por día (opcional)",
        help=(
            "Opcional. Si la completás, se usa junto con el criterio de fecha. "
            "Si la dejás vacía, se listan todos los PICK pendientes que cumplan "
            "zona y/o vendedor."
        ),
    )
    date_filter_mode = fields.Selection(
        selection=[
            ("any_pending", "Todos los PICK pendientes"),
            ("picking_scheduled", "Solo PICK de ese día"),
            ("commitment_date", "Solo pedidos con entrega ese día"),
        ],
        string="Criterio de fecha",
        required=True,
        default="any_pending",
        help=(
            "Por defecto no exige fecha. Si más adelante planifican por día, "
            "elegí un criterio y completá el campo de arriba."
        ),
    )
    warehouse_id = fields.Many2one(
        comodel_name="stock.warehouse",
        string="Almacén",
        help="Opcional. Limita la búsqueda a un depósito (ej. Nakel Central).",
    )
    only_without_wave = fields.Boolean(
        string="Solo pedidos sin ola",
        default=True,
        help="Oculta pedidos que ya están en una ola WAVE armada.",
    )
    target_batch_id = fields.Many2one(
        comodel_name="stock.picking.batch",
        string="Agregar a ola existente",
        domain="[('is_wave', '=', True), ('state', 'in', ('draft', 'in_progress'))]",
        help=(
            "Opcional. Si ya tenés una ola abierta, agregá acá los pedidos "
            "nuevos en lugar de crear otra."
        ),
    )
    confirm_wave = fields.Boolean(
        string="Dejar ola lista para pickear",
        default=True,
        help="Recomendado: confirma la ola para que aparezca en Barcode.",
    )
    apply_demand_mode = fields.Boolean(
        string="Ajustar cantidades al pedido (modo demanda)",
        default=True,
        help=(
            "Útil cuando el stock en Odoo no coincide con lo que hay en el piso: "
            "sube las cantidades al pedido del cliente antes de escanear."
        ),
    )
    line_ids = fields.One2many(
        comodel_name="nakel.wave.planner.line",
        inverse_name="wizard_id",
        string="Órdenes de venta",
    )
    summary = fields.Char(string="Resumen", compute="_compute_summary")

    @api.depends("line_ids", "line_ids.selected", "line_ids.picking_count", "line_ids.warning_level")
    def _compute_summary(self):
        for wizard in self:
            lines = wizard.line_ids
            selected = lines.filtered("selected")
            wizard.summary = _(
                "%(so)s pedidos seleccionados · %(pick)s PICK · %(warn)s para revisar"
            ) % {
                "so": len(selected),
                "pick": sum(selected.mapped("picking_count")),
                "warn": len(selected.filtered(lambda l: l.warning_level != "ok")),
            }

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_model = self.env.context.get("active_model")
        active_id = self.env.context.get("active_id")
        if active_model == "stock.picking.batch" and active_id:
            batch = self.env["stock.picking.batch"].browse(active_id)
            if batch.is_wave and batch.state in ("draft", "in_progress"):
                res["target_batch_id"] = batch.id
        return res

    def _nakel_planner_use_date_filter(self):
        self.ensure_one()
        return bool(
            self.date_planned
            and self.date_filter_mode in ("picking_scheduled", "commitment_date")
        )

    def _nakel_planner_day_bounds(self):
        self.ensure_one()
        day = fields.Date.to_date(self.date_planned)
        start = datetime.combine(day, time.min)
        end = datetime.combine(day + timedelta(days=1), time.min)
        return fields.Datetime.to_string(start), fields.Datetime.to_string(end)

    def _nakel_planner_base_sale_domain(self):
        self.ensure_one()
        domain = [("state", "in", ("sale", "done"))]
        if self.zone_tag_ids:
            tag_ids = self.zone_tag_ids.ids
            domain = expression.AND(
                [
                    domain,
                    [
                        "|",
                        ("partner_shipping_id.category_id", "in", tag_ids),
                        ("partner_id.category_id", "in", tag_ids),
                    ],
                ]
            )
        if self.salesperson_ids:
            domain = expression.AND(
                [domain, [("user_id", "in", self.salesperson_ids.ids)]]
            )
        if self.only_without_wave:
            domain = expression.AND([domain, [("nakel_wave_batch_id", "=", False)]])
        if self.warehouse_id:
            domain = expression.AND(
                [domain, [("warehouse_id", "=", self.warehouse_id.id)]]
            )
        return domain

    def _nakel_planner_pick_domain(self, sale=None, apply_date_filter=True):
        self.ensure_one()
        domain = [
            ("state", "not in", ("done", "cancel")),
            "|",
            ("picking_type_id.sequence_code", "=", "PICK"),
            ("name", "ilike", "CEN/PICK/%"),
        ]
        if self.warehouse_id:
            domain = expression.AND(
                [domain, [("picking_type_id.warehouse_id", "=", self.warehouse_id.id)]]
            )
        if sale:
            parts = [[("sale_id", "=", sale.id)]]
            if sale.name:
                parts.append([("origin", "=", sale.name)])
            if sale.procurement_group_id:
                parts.append([("group_id", "=", sale.procurement_group_id.id)])
            domain = expression.AND([domain, expression.OR(parts)])
        if (
            apply_date_filter
            and self._nakel_planner_use_date_filter()
            and self.date_filter_mode == "picking_scheduled"
        ):
            start, end = self._nakel_planner_day_bounds()
            domain = expression.AND(
                [
                    domain,
                    [("scheduled_date", ">=", start), ("scheduled_date", "<", end)],
                ]
            )
        return domain

    def _nakel_planner_pickings_for_sale(self, sale, apply_date_filter=True):
        self.ensure_one()
        return self.env["stock.picking"].search(
            self._nakel_planner_pick_domain(sale, apply_date_filter=apply_date_filter)
        )

    def _nakel_planner_sale_matches_date(self, sale, pickings):
        self.ensure_one()
        if not self._nakel_planner_use_date_filter():
            return bool(pickings) if self.date_filter_mode == "any_pending" else True
        if self.date_filter_mode == "commitment_date":
            if not sale.commitment_date:
                return False
            return fields.Date.to_date(sale.commitment_date) == fields.Date.to_date(
                self.date_planned
            )
        # picking_scheduled
        if pickings:
            day = fields.Date.to_date(self.date_planned)
            for picking in pickings:
                if picking.scheduled_date and fields.Date.to_date(
                    picking.scheduled_date
                ) == day:
                    return True
            return False
        return False

    def _nakel_planner_line_warning(self, sale, pickings):
        self.ensure_one()
        if sale.nakel_wave_batch_id:
            return (
                "blocked",
                _("Este pedido ya está en la ola %(wave)s")
                % {"wave": sale.nakel_wave_batch_id.name},
            )
        if not pickings:
            return ("warn", _("Todavía no hay PICK para este pedido"))
        if self._nakel_planner_use_date_filter() and not self._nakel_planner_sale_matches_date(
            sale, pickings
        ):
            return ("warn", _("El PICK tiene otra fecha o sin fecha programada"))
        blocked_batches = pickings.mapped("batch_id").filtered(
            lambda b: b and b.state not in ("done", "cancel")
        )
        if blocked_batches and (
            not self.target_batch_id
            or any(b.id != self.target_batch_id.id for b in blocked_batches)
        ):
            names = ", ".join(blocked_batches.mapped("name"))
            return (
                "blocked",
                _("Un PICK ya está en otra ola: %(waves)s") % {"waves": names},
            )
        return ("ok", "")

    def action_search_orders(self):
        self.ensure_one()
        if not self.zone_tag_ids and not self.salesperson_ids:
            raise UserError(
                _("Seleccioná al menos una zona (etiqueta) o un vendedor.")
            )

        SaleOrder = self.env["sale.order"]
        sales = SaleOrder.search(self._nakel_planner_base_sale_domain(), order="name asc")

        if (
            self.date_filter_mode == "commitment_date"
            and self._nakel_planner_use_date_filter()
        ):
            day = fields.Date.to_date(self.date_planned)
            sales = sales.filtered(
                lambda so: so.commitment_date
                and fields.Date.to_date(so.commitment_date) == day
            )

        line_vals = []
        for sale in sales:
            pickings = self._nakel_planner_pickings_for_sale(sale)
            if (
                self.date_filter_mode == "picking_scheduled"
                and self._nakel_planner_use_date_filter()
                and not self._nakel_planner_sale_matches_date(sale, pickings)
            ):
                continue
            if self.date_filter_mode == "any_pending" and not pickings:
                continue
            level, message = self._nakel_planner_line_warning(sale, pickings)
            line_vals.append(
                {
                    "sale_order_id": sale.id,
                    "picking_ids": [(6, 0, pickings.ids)],
                    "warning_level": level,
                    "warning_message": message,
                    "selected": level == "ok",
                }
            )

        self.line_ids = [(5, 0, 0)] + [(0, 0, vals) for vals in line_vals]
        if not line_vals:
            raise UserError(
                _(
                    "No encontramos pedidos con esos filtros. "
                    "Probá ampliar zona/vendedor o quitá «Solo pedidos sin ola»."
                )
            )
        return self._nakel_planner_reopen()

    def action_select_all_ok(self):
        self.ensure_one()
        for line in self.line_ids:
            line.selected = line.warning_level == "ok"
        return self._nakel_planner_reopen()

    def action_select_all(self):
        self.ensure_one()
        self.line_ids.filtered(lambda l: l.warning_level != "blocked").write(
            {"selected": True}
        )
        return self._nakel_planner_reopen()

    def action_deselect_all(self):
        self.ensure_one()
        self.line_ids.write({"selected": False})
        return self._nakel_planner_reopen()

    def _nakel_planner_default_picking_type(self, pickings):
        if self.target_batch_id and self.target_batch_id.picking_type_id:
            return self.target_batch_id.picking_type_id
        if pickings:
            ptypes = pickings.mapped("picking_type_id")
            if len(ptypes) == 1:
                return ptypes
        wh = self.warehouse_id or self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1
        )
        if wh:
            ptype = self.env["stock.picking.type"].search(
                [
                    ("warehouse_id", "=", wh.id),
                    ("sequence_code", "=", "PICK"),
                ],
                limit=1,
            )
            if ptype:
                return ptype
        return self.env["stock.picking.type"]

    def action_create_wave(self):
        self.ensure_one()
        selected_lines = self.line_ids.filtered("selected")
        if not selected_lines:
            raise UserError(_("Marcá al menos un pedido para incluir en la ola."))

        blocked = selected_lines.filtered(lambda l: l.warning_level == "blocked")
        if blocked:
            names = ", ".join(blocked.mapped("sale_order_id.name"))
            raise UserError(
                _(
                    "Hay pedidos bloqueados en la selección (%(names)s). "
                    "Desmarcálos o corregí la ola antes de continuar."
                )
                % {"names": names}
            )

        pickings = selected_lines.mapped("picking_ids").filtered(
            lambda p: p.state not in ("done", "cancel")
        )
        if not pickings:
            raise UserError(
                _(
                    "Los pedidos seleccionados no tienen PICK pendientes. "
                    "Revisá que las ventas estén confirmadas."
                )
            )

        conflict = pickings.filtered(
            lambda p: p.batch_id
            and p.batch_id.state not in ("done", "cancel")
            and (
                not self.target_batch_id or p.batch_id.id != self.target_batch_id.id
            )
        )
        if conflict:
            raise UserError(
                _(
                    "Estos PICK ya están en otra ola abierta: %(names)s"
                )
                % {"names": ", ".join(conflict.mapped("name"))}
            )

        batch = self.target_batch_id
        if batch:
            batch.write({"picking_ids": [(4, pid) for pid in pickings.ids]})
        else:
            ptype = self._nakel_planner_default_picking_type(pickings)
            batch = self.env["stock.picking.batch"].create(
                {
                    "is_wave": True,
                    "picking_type_id": ptype.id if ptype else False,
                    "picking_ids": [(6, 0, pickings.ids)],
                }
            )

        if self.confirm_wave and batch.state == "draft":
            batch.action_confirm()

        demand_note = ""
        if (
            self.apply_demand_mode
            and hasattr(batch, "action_nakel_apply_demand_mode")
        ):
            batch.action_nakel_apply_demand_mode()
            demand_note = _("Modo demanda aplicado")

        log_lines = []
        if self.zone_tag_ids:
            log_lines.append(
                _("Zona(s): %(tags)s")
                % {"tags": ", ".join(self.zone_tag_ids.mapped("name"))}
            )
        if self.salesperson_ids:
            log_lines.append(
                _("Vendedor(es): %(users)s")
                % {"users": ", ".join(self.salesperson_ids.mapped("name"))}
            )
        if self._nakel_planner_use_date_filter():
            log_lines.append(_("Día: %(date)s") % {"date": self.date_planned})
        log_lines.append(_("Pedidos: %(n)s") % {"n": len(selected_lines)})
        log_lines.append(_("PICK: %(n)s") % {"n": len(pickings)})
        if demand_note:
            log_lines.append(demand_note)
        if hasattr(batch, "_nakel_message_post_log"):
            batch._nakel_message_post_log(_("Ola armada desde planificador Nakel"), log_lines)
        else:
            batch.message_post(
                body=_("Ola armada desde planificador Nakel\n%s")
                % "\n".join("• %s" % line for line in log_lines)
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("Ola WAVE"),
            "res_model": "stock.picking.batch",
            "view_mode": "form",
            "res_id": batch.id,
            "target": "current",
        }

    def _nakel_planner_reopen(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Armar ola por zona"),
            "res_model": "nakel.wave.planner.wizard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }


class NakelWavePlannerLine(models.TransientModel):
    _name = "nakel.wave.planner.line"
    _description = "Línea del planificador de olas Nakel"
    _order = "warning_level desc, sale_order_id"

    wizard_id = fields.Many2one(
        comodel_name="nakel.wave.planner.wizard",
        required=True,
        ondelete="cascade",
    )
    selected = fields.Boolean(string="Incluir", default=True)
    sale_order_id = fields.Many2one(
        comodel_name="sale.order",
        string="OV",
        required=True,
        ondelete="cascade",
    )
    partner_id = fields.Many2one(
        related="sale_order_id.partner_id",
        string="Cliente",
        readonly=True,
    )
    user_id = fields.Many2one(
        related="sale_order_id.user_id",
        string="Vendedor",
        readonly=True,
    )
    partner_shipping_id = fields.Many2one(
        related="sale_order_id.partner_shipping_id",
        string="Entrega",
        readonly=True,
    )
    commitment_date = fields.Datetime(
        related="sale_order_id.commitment_date",
        readonly=True,
    )
    nakel_wave_batch_id = fields.Many2one(
        related="sale_order_id.nakel_wave_batch_id",
        string="Ola actual",
        readonly=True,
    )
    zone_tag_names = fields.Char(
        string="Zona",
        compute="_compute_zone_tag_names",
    )
    picking_ids = fields.Many2many(
        comodel_name="stock.picking",
        string="PICKs",
        readonly=True,
    )
    picking_count = fields.Integer(
        string="# PICK",
        compute="_compute_picking_count",
    )
    picking_names = fields.Char(
        string="PICK",
        compute="_compute_picking_names",
    )
    warning_level = fields.Selection(
        selection=[
            ("ok", "OK"),
            ("warn", "Revisar"),
            ("blocked", "Bloqueado"),
        ],
        string="Estado",
        default="ok",
        readonly=True,
    )
    warning_message = fields.Char(string="Alerta", readonly=True)

    @api.depends(
        "partner_shipping_id.category_id",
        "partner_id.category_id",
        "wizard_id.zone_tag_ids",
    )
    def _compute_zone_tag_names(self):
        for line in self:
            tags = (
                line.partner_shipping_id.category_id | line.partner_id.category_id
            )
            if line.wizard_id.zone_tag_ids:
                tags = tags.filtered(lambda t: t in line.wizard_id.zone_tag_ids)
            line.zone_tag_names = ", ".join(tags.mapped("name"))

    @api.depends("picking_ids")
    def _compute_picking_count(self):
        for line in self:
            line.picking_count = len(line.picking_ids)

    @api.depends("picking_ids")
    def _compute_picking_names(self):
        for line in self:
            line.picking_names = ", ".join(line.picking_ids.mapped("name"))
