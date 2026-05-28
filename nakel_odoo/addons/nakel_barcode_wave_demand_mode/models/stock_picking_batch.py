# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools.float_utils import float_compare, float_is_zero


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    nakel_demand_mode_enabled = fields.Boolean(
        compute="_compute_nakel_demand_mode_enabled",
        string="Modo demanda activo (ICP)",
    )
    nakel_demand_coverage_status = fields.Selection(
        selection=[
            ("ok", "Demanda completa"),
            ("needed", "Aplicar modo demanda"),
            ("missing", "Faltan productos OV"),
        ],
        string="Cobertura demanda OV",
        compute="_compute_nakel_demand_coverage",
        help="Semáforo: indica si hace falta Modo demanda OV antes de pickear en Barcode.",
    )
    nakel_demand_gap_count = fields.Integer(
        string="Brechas demanda/reserva",
        compute="_compute_nakel_demand_coverage",
    )
    nakel_demand_gap_caption = fields.Char(
        string="Resumen cobertura demanda",
        compute="_compute_nakel_demand_coverage",
    )
    nakel_wave_barcode_blocked = fields.Boolean(
        string="Barcode bloqueado",
        compute="_compute_nakel_wave_barcode_guard",
    )
    nakel_wave_barcode_block_caption = fields.Char(
        string="Motivo bloqueo Barcode",
        compute="_compute_nakel_wave_barcode_guard",
    )

    @api.depends_context("uid")
    def _compute_nakel_demand_mode_enabled(self):
        enabled = self.env["ir.config_parameter"].nakel_barcode_wave_demand_mode_is_enabled()
        for batch in self:
            batch.nakel_demand_mode_enabled = enabled

    @api.depends(
        "picking_ids",
        "picking_ids.state",
        "picking_ids.move_ids",
        "picking_ids.move_ids.product_uom_qty",
        "picking_ids.move_ids.state",
        "picking_ids.move_ids.move_line_ids.quantity",
        "nakel_wave_sale_ids",
        "nakel_wave_sale_ids.order_line",
        "nakel_wave_sale_ids.order_line.product_uom_qty",
    )
    def _compute_nakel_demand_coverage(self):
        for batch in self:
            if not batch.ids or not batch.is_wave:
                batch.nakel_demand_coverage_status = "ok"
                batch.nakel_demand_gap_count = 0
                batch.nakel_demand_gap_caption = ""
                continue
            report = batch._nakel_demand_coverage_report()
            batch.nakel_demand_coverage_status = report["status"]
            batch.nakel_demand_gap_count = report["gap_count"]
            batch.nakel_demand_gap_caption = report["caption"]

    @api.depends(
        "picking_ids",
        "picking_ids.state",
        "picking_ids.batch_id",
        "nakel_wave_all_pick_ids.state",
        "nakel_wave_all_pick_ids.batch_id",
    )
    def _compute_nakel_wave_barcode_guard(self):
        for batch in self:
            blockers = batch._nakel_wave_barcode_blockers() if batch.ids else []
            batch.nakel_wave_barcode_blocked = bool(blockers)
            batch.nakel_wave_barcode_block_caption = " · ".join(blockers[:2])

    def _nakel_message_post_log(self, title, lines):
        """Chatter legible (texto plano; evita HTML escapado en el hilo)."""
        self.ensure_one()
        body = "%s\n%s" % (title, "\n".join("• %s" % line for line in lines if line))
        self.message_post(body=body)

    def _nakel_official_wave_pickings(self):
        """PICK pendientes que pertenecen al batch oficial de Odoo."""
        self.ensure_one()
        return self.picking_ids.filtered(
            lambda p: p.state not in ("done", "cancel")
            and p._nakel_demand_mode_applies_to_picking()
        )

    def _nakel_barcode_pre_green_official_pickings(self):
        """Marca PICK oficiales de la ola listos para Barcode (restar faltantes)."""
        self.ensure_one()
        pickings = self._nakel_official_wave_pickings()
        lines_updated = 0
        for picking in pickings:
            lines_updated += picking._nakel_barcode_pre_green_lines()
        return {"pickings": len(pickings), "lines_updated": lines_updated}

    def _nakel_maybe_barcode_pre_green(self):
        """
        Pre-verde idempotente antes de Barcode.

        Marca líneas aún sin pickear; no sube qty_done si el operario ya lo bajó (stock real).
        """
        self.ensure_one()
        ICP = self.env["ir.config_parameter"]
        if not ICP.nakel_barcode_wave_demand_mode_is_enabled():
            return {"pickings": 0, "lines_updated": 0}
        if not self.is_wave or self.state in ("done", "cancel"):
            return {"pickings": 0, "lines_updated": 0}
        if self._nakel_wave_barcode_blockers():
            return {"pickings": 0, "lines_updated": 0}
        report = self._nakel_demand_coverage_report()
        if report["status"] == "missing":
            return {"pickings": 0, "lines_updated": 0}
        return self._nakel_barcode_pre_green_official_pickings()

    def _get_stock_barcode_data(self):
        self.ensure_one()
        if self.is_wave:
            self._nakel_maybe_barcode_pre_green()
        return super()._get_stock_barcode_data()

    def _nakel_trace_only_wave_pickings(self):
        """PICK pendientes vinculados por trazabilidad pero fuera del batch oficial."""
        self.ensure_one()
        pickings = self.env["stock.picking"].search(
            [
                ("nakel_wave_batch_id", "=", self.id),
                ("state", "not in", ("done", "cancel")),
            ]
        )
        return pickings.filtered(
            lambda p: p._nakel_demand_mode_applies_to_picking()
            and (not p.batch_id or p.batch_id.id != self.id)
        )

    def _nakel_wave_barcode_blockers(self):
        """Bloqueos por inconsistencia entre trazabilidad y batch oficial."""
        self.ensure_one()
        if not self.is_wave or self.state in ("done", "cancel"):
            return []

        blockers = []
        trace_only = self._nakel_trace_only_wave_pickings()
        if trace_only:
            names = ", ".join(trace_only[:8].mapped("name"))
            if len(trace_only) > 8:
                names = _("%s, ... (+%s)") % (names, len(trace_only) - 8)
            blockers.append(
                _("%s PICK vinculados por trazabilidad fuera del lote oficial: %s")
                % (len(trace_only), names)
            )
        return blockers

    def _nakel_move_from_reservation_gap(self, gap):
        """Move PICK asociado a una brecha de reserva del reporte de cobertura."""
        self.ensure_one()
        pickings = self._nakel_demand_mode_pickings_in_batch()
        pname = (gap.get("picking_names") or "").split(",")[0].strip()
        picking = pickings.filtered(lambda p: p.name == pname)[:1]
        if not picking:
            return self.env["stock.move"]
        domain = [
            ("picking_id", "=", picking.id),
            ("product_id", "=", gap["product_id"]),
            ("state", "not in", ("done", "cancel")),
        ]
        if gap.get("sale_line_id"):
            domain.append(("sale_line_id", "=", gap["sale_line_id"]))
        return self.env["stock.move"].search(domain, limit=1)

    def _nakel_move_operator_picked_real(self, move):
        """
        True si el operario ya fijó cantidad real en piso (parcial o cero).

        Tras bajar qty_done en Barcode, la reserva puede quedar < pedido OV; eso
        no debe exigir Modo demanda supervisor para validar la ola.
        """
        lines = move.move_line_ids
        demand = float(move.product_uom_qty or 0.0)
        rounding = move.product_uom.rounding if move.product_uom else 0.01
        if demand <= 0.0:
            return True
        if not lines:
            return False

        picked_done = sum(float(line.qty_done or 0.0) for line in lines)
        reserved = sum(float(line.quantity or 0.0) for line in lines)
        if float_compare(picked_done, demand, precision_rounding=rounding) > 0:
            return False
        if not float_is_zero(picked_done, precision_rounding=rounding):
            return True
        return float_is_zero(reserved, precision_rounding=rounding)

    def _nakel_partial_picking_allows_validate(self, report):
        """
        Permite validar con semáforo amarillo cuando solo hay brechas de reserva
        ya resueltas en piso (qty_done real ≤ pedido), sin productos OV faltantes.
        """
        self.ensure_one()
        if report["status"] != "needed":
            return False
        if report.get("ov_missing_gaps") or report.get("sibling_outside"):
            return False

        gap_details = report.get("gap_details") or []
        reservation_gaps = [g for g in gap_details if g["gap_reason"] == "reservation"]
        if not reservation_gaps:
            return False
        if any(g["gap_reason"] != "reservation" for g in gap_details):
            return False

        for gap in reservation_gaps:
            move = self._nakel_move_from_reservation_gap(gap)
            if not move or not self._nakel_move_operator_picked_real(move):
                return False
        return True

    def _nakel_wave_validation_blockers(self):
        """Razones por las que no se debe validar la ola todavía."""
        self.ensure_one()
        blockers = list(self._nakel_wave_barcode_blockers())
        report = self._nakel_demand_coverage_report()
        if report["status"] == "missing":
            blockers.append(_("Cobertura OV incompleta: %s") % report["caption"])
        elif report["status"] == "needed":
            if not self._nakel_partial_picking_allows_validate(report):
                blockers.append(_("Falta aplicar Modo demanda OV: %s") % report["caption"])
        return blockers

    def _nakel_raise_if_barcode_blocked(self):
        self.ensure_one()
        ICP = self.env["ir.config_parameter"]
        if not ICP.nakel_barcode_wave_demand_mode_is_enabled():
            return
        if not ICP.nakel_barcode_wave_demand_mode_strict_batch():
            return
        blockers = self._nakel_wave_validation_blockers()
        if blockers:
            raise UserError(
                _(
                    "No se puede validar esta ola todavía.\n\n"
                    "%s\n\n"
                    "Primero usá Ver faltantes / Agregar a la ola / Modo demanda OV "
                    "y luego pedí al operario cerrar y reabrir Barcode."
                )
                % "\n".join("• %s" % blocker for blocker in blockers)
            )

    def action_nakel_show_barcode_blockers(self):
        self.ensure_one()
        blockers = self._nakel_wave_barcode_blockers()
        if not blockers:
            report = self._nakel_demand_coverage_report()
            if report["status"] == "missing":
                return self.action_nakel_open_coverage_gaps()
        message = (
            "\n".join("• %s" % blocker for blocker in blockers)
            if blockers
            else _("La ola no tiene bloqueos para Barcode.")
        )
        return self._nakel_demand_mode_notification(
            _("Control Barcode"),
            message,
            "warning" if blockers else "success",
            sticky=bool(blockers),
        )

    def action_done(self):
        for batch in self:
            batch._nakel_raise_if_barcode_blocked()
        return super().action_done()

    def _nakel_demand_coverage_gap_details(self):
        """Detalle línea a línea: qué falta y por qué."""
        self.ensure_one()
        gaps = []
        pickings = self._nakel_demand_mode_pickings_in_batch()
        Move = self.env["stock.move"]
        sales = (
            self._nakel_wave_sale_order_ids()
            if hasattr(self, "_nakel_wave_sale_order_ids")
            else pickings.mapped("sale_id").filtered(lambda so: so)
        )

        for sale in sales:
            for line in sale.order_line.filtered(lambda l: not l.display_type):
                demand = float(line.product_uom_qty or 0.0)
                if demand <= 0.0:
                    continue
                rounding = line.product_uom.rounding if line.product_uom else 0.01

                moves_wave = Move.search(
                    [
                        ("picking_id.batch_id", "=", self.id),
                        ("sale_line_id", "=", line.id),
                    ]
                )
                if not moves_wave:
                    moves_wave = Move.search(
                        [
                            ("picking_id.batch_id", "=", self.id),
                            ("product_id", "=", line.product_id.id),
                            ("origin", "=", sale.name),
                        ]
                    )
                in_wave = sum(float(m.product_uom_qty or 0.0) for m in moves_wave)

                if float_compare(in_wave, demand, precision_rounding=rounding) >= 0:
                    continue

                moves_all = Move.search(
                    [
                        ("sale_line_id", "=", line.id),
                        ("state", "not in", ("done", "cancel")),
                    ]
                )
                pick_moves = moves_all.filtered(
                    lambda m: m.picking_id
                    and m.picking_id._nakel_demand_mode_applies_to_picking()
                )

                if not pick_moves:
                    gaps.append(
                        {
                            "sale_line_id": line.id,
                            "sale_order_id": sale.id,
                            "product_id": line.product_id.id,
                            "qty_ov": demand,
                            "qty_in_wave": in_wave,
                            "gap_reason": "no_transfer",
                            "picking_names": "",
                            "action_hint": _(
                                "Odoo no generó PICK para este producto. "
                                "Supervisor/ventas: relanzar entrega de la OV."
                            ),
                        }
                    )
                    continue

                outside = pick_moves.filtered(
                    lambda m: not m.picking_id.batch_id
                    or m.picking_id.batch_id.id != self.id
                )
                if outside:
                    gaps.append(
                        {
                            "sale_line_id": line.id,
                            "sale_order_id": sale.id,
                            "product_id": line.product_id.id,
                            "qty_ov": demand,
                            "qty_in_wave": in_wave,
                            "gap_reason": "outside_wave",
                            "picking_names": ", ".join(
                                dict.fromkeys(outside.mapped("picking_id.name"))
                            ),
                            "action_hint": _(
                                "Agregar ese PICK a la ola (planificador o pestaña Traslados)."
                            ),
                        }
                    )
                else:
                    gaps.append(
                        {
                            "sale_line_id": line.id,
                            "sale_order_id": sale.id,
                            "product_id": line.product_id.id,
                            "qty_ov": demand,
                            "qty_in_wave": in_wave,
                            "gap_reason": "partial_wave",
                            "picking_names": ", ".join(
                                dict.fromkeys(moves_wave.mapped("picking_id.name"))
                            ),
                            "action_hint": _(
                                "Revisar cantidades del PICK en la ola o relanzar entrega."
                            ),
                        }
                    )

        for picking in pickings:
            for move in picking.move_ids.filtered(
                lambda m: m.state not in ("done", "cancel") and m.product_uom_qty > 0
            ):
                demand = float(move.product_uom_qty or 0.0)
                reserved = sum(float(ml.quantity or 0.0) for ml in move.move_line_ids)
                rounding = move.product_uom.rounding if move.product_uom else 0.01
                if not move.move_line_ids or float_compare(
                    reserved, demand, precision_rounding=rounding
                ) < 0:
                    sale = move.sale_line_id.order_id if move.sale_line_id else False
                    gaps.append(
                        {
                            "sale_line_id": move.sale_line_id.id if move.sale_line_id else False,
                            "sale_order_id": sale.id if sale else False,
                            "product_id": move.product_id.id,
                            "qty_ov": demand,
                            "qty_in_wave": reserved,
                            "gap_reason": "reservation",
                            "picking_names": picking.name,
                            "action_hint": _(
                                "Usar Modo demanda OV (semáforo amarillo) antes de Barcode."
                            ),
                        }
                    )
        return gaps

    def _nakel_demand_coverage_report(self):
        """Evalúa cobertura OV ↔ ola y reserva ↔ demanda en PICK."""
        self.ensure_one()
        gap_details = self._nakel_demand_coverage_gap_details()
        no_transfer = sum(1 for g in gap_details if g["gap_reason"] == "no_transfer")
        outside_wave = sum(1 for g in gap_details if g["gap_reason"] == "outside_wave")
        partial_wave = sum(1 for g in gap_details if g["gap_reason"] == "partial_wave")
        reservation_gaps = sum(1 for g in gap_details if g["gap_reason"] == "reservation")
        ov_missing_gaps = no_transfer + outside_wave + partial_wave

        pickings = self._nakel_demand_mode_pickings_in_batch()
        sibling_outside = 0
        ICP = self.env["ir.config_parameter"]
        if ICP.nakel_barcode_wave_demand_mode_include_so_sibling_picks() and pickings:
            domain = self._nakel_demand_mode_sibling_pick_domain(pickings)
            if domain != [(0, "=", 1)]:
                candidates = self.env["stock.picking"].search(domain)
                in_batch_ids = set(pickings.ids) | set(self.picking_ids.ids)
                sibling_outside = len(
                    candidates.filtered(
                        lambda p: p.id not in in_batch_ids
                        and p._nakel_demand_mode_applies_to_picking()
                    )
                )

        if ov_missing_gaps:
            status = "missing"
            gap_count = ov_missing_gaps
            parts = []
            if no_transfer:
                parts.append(_("%s sin PICK en Odoo") % no_transfer)
            if outside_wave:
                parts.append(_("%s en PICK fuera de ola") % outside_wave)
            if partial_wave:
                parts.append(_("%s incompletos en ola") % partial_wave)
            caption = " · ".join(parts)
        elif reservation_gaps or sibling_outside:
            status = "needed"
            gap_count = reservation_gaps + sibling_outside
            parts = []
            if reservation_gaps:
                parts.append(_("%s con reserva menor al pedido") % reservation_gaps)
            if sibling_outside:
                parts.append(
                    _("%s PICK hermano fuera de la ola") % sibling_outside
                )
            caption = " · ".join(parts)
        else:
            status = "ok"
            gap_count = 0
            caption = _("Listo para Barcode")

        return {
            "status": status,
            "gap_count": gap_count,
            "caption": caption,
            "reservation_gaps": reservation_gaps,
            "ov_missing_gaps": ov_missing_gaps,
            "sibling_outside": sibling_outside,
            "no_transfer": no_transfer,
            "outside_wave": outside_wave,
            "partial_wave": partial_wave,
            "gap_details": gap_details,
        }

    def _nakel_pick_moves_for_sale_line(self, sale_line):
        Move = self.env["stock.move"]
        moves = Move.search(
            [
                ("sale_line_id", "=", sale_line.id),
                ("state", "not in", ("done", "cancel")),
            ]
        )
        return moves.filtered(
            lambda m: m.picking_id and m.picking_id._nakel_is_pick_picking()
        )

    def _nakel_attach_pickings_to_wave(self, pickings):
        self.ensure_one()
        to_add = pickings.filtered(
            lambda p: p._nakel_is_pick_picking()
            and (not p.batch_id or p.batch_id.id != self.id)
        )
        if to_add:
            self.write({"picking_ids": [(4, pid) for pid in to_add.ids]})
            to_add.invalidate_recordset(["batch_id", "nakel_wave_batch_id"])
            failed = to_add.filtered(lambda p: not p.batch_id or p.batch_id.id != self.id)
            if failed:
                raise UserError(
                    _(
                        "No se pudieron incorporar estos PICK al lote oficial: %s.\n"
                        "Quedaron como trazabilidad, pero Barcode no debe operar la ola así."
                    )
                    % ", ".join(failed.mapped("name"))
                )
        return to_add

    def _nakel_add_coverage_gaps_to_wave(self, gap_lines, apply_demand_mode=False):
        """
        Relanza entrega de líneas OV sin PICK o agrega PICK hermanos a la ola.

        Tras crear moves, opcionalmente aplica modo demanda en los PICK tocados.
        """
        self.ensure_one()
        log_lines = []
        errors = []

        for gap in gap_lines:
            if not gap.sale_line_id:
                errors.append(_("Línea sin referencia de OV: %s") % gap.product_id.display_name)
                continue

            sale_line = gap.sale_line_id
            label = "%s / %s" % (sale_line.order_id.name, sale_line.product_id.display_name)

            if gap.gap_reason == "outside_wave":
                pick_moves = self._nakel_pick_moves_for_sale_line(sale_line)
                outside = pick_moves.filtered(
                    lambda m: not m.picking_id.batch_id
                    or m.picking_id.batch_id.id != self.id
                )
                picks = self._nakel_attach_pickings_to_wave(outside.mapped("picking_id"))
                if picks:
                    log_lines.append(_("%(label)s → PICK agregado: %(picks)s") % {
                        "label": label,
                        "picks": ", ".join(picks.mapped("name")),
                    })
                    if apply_demand_mode:
                        for picking in picks:
                            picking._nakel_apply_demand_mode()
                else:
                    errors.append(_("%(label)s: no hay PICK fuera de la ola") % {"label": label})
                continue

            if gap.gap_reason not in ("no_transfer", "partial_wave"):
                continue

            before_picks = self._nakel_pick_moves_for_sale_line(sale_line).mapped("picking_id")
            sale_line._action_launch_stock_rule()
            pick_moves = self._nakel_pick_moves_for_sale_line(sale_line)

            if not pick_moves:
                errors.append(
                    _("%(label)s: Odoo no generó PICK (revisar producto/ruta/almacén)") % {"label": label}
                )
                continue

            picks = self._nakel_attach_pickings_to_wave(pick_moves.mapped("picking_id"))
            new_picks = picks.filtered(lambda p: p not in before_picks)
            pick_names = ", ".join(pick_moves.mapped("picking_id.name"))
            if new_picks:
                log_lines.append(_("%(label)s → PICK creado/agregado: %(picks)s") % {
                    "label": label,
                    "picks": pick_names,
                })
            else:
                log_lines.append(_("%(label)s → move en PICK: %(picks)s") % {
                    "label": label,
                    "picks": pick_names,
                })

            if apply_demand_mode:
                for picking in pick_moves.mapped("picking_id").filtered(
                    lambda p: p.batch_id and p.batch_id.id == self.id
                ):
                    picking._nakel_apply_demand_mode()

        if log_lines:
            self._nakel_message_post_log(_("Productos agregados a la ola"), log_lines)
        if errors and not log_lines:
            raise UserError("\n".join(errors))
        if errors:
            self._nakel_message_post_log(_("Productos no agregados"), errors)
        if apply_demand_mode:
            pre_green = self._nakel_barcode_pre_green_official_pickings()
            if pre_green["lines_updated"] and self.env["ir.config_parameter"].nakel_barcode_wave_demand_mode_should_log():
                self._nakel_message_post_log(
                    _("Barcode pre-verde"),
                    [
                        _(
                            "%(lines_updated)s líneas en %(pickings)s PICK oficiales "
                            "(qty_done = reserva, listo para bajar faltantes)."
                        )
                        % pre_green
                    ],
                )
        return log_lines

    def action_nakel_open_coverage_gaps(self):
        """Lista clara de productos OV que faltan o están incompletos."""
        self.ensure_one()
        report = self._nakel_demand_coverage_report()
        gap_details = report.get("gap_details") or []
        ov_gaps = [g for g in gap_details if g["gap_reason"] != "reservation"]
        show = ov_gaps if ov_gaps else gap_details

        wizard = self.env["nakel.wave.coverage.gap.wizard"].create(
            {
                "batch_id": self.id,
                "summary": report["caption"],
                "line_ids": [(0, 0, vals) for vals in show],
            }
        )
        return {
            "name": _("Qué falta en la ola"),
            "type": "ir.actions.act_window",
            "res_model": "nakel.wave.coverage.gap.wizard",
            "view_mode": "form",
            "res_id": wizard.id,
            "target": "new",
        }

    def action_nakel_open_demand_coverage(self):
        """Abre detalle de faltantes o PICKs de la ola."""
        self.ensure_one()
        report = self._nakel_demand_coverage_report()
        if report["status"] == "missing" or report.get("ov_missing_gaps"):
            return self.action_nakel_open_coverage_gaps()
        pickings = self._nakel_demand_mode_pickings_in_batch()
        return {
            "name": _("PICK de la ola"),
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": [("id", "in", pickings.ids)] if pickings else [(0, "=", 1)],
            "context": {"create": False},
        }

    def _nakel_demand_mode_pickings_in_batch(self):
        """PICK pendientes que están en el batch oficial de Odoo."""
        self.ensure_one()
        return self._nakel_official_wave_pickings()

    def _nakel_demand_mode_sale_orders(self, wave_pickings):
        """OV de la ola: pickings del batch + campo nakel_wave_batch_id en sale.order."""
        self.ensure_one()
        if hasattr(self, "_nakel_wave_sale_order_ids"):
            return self._nakel_wave_sale_order_ids()
        return wave_pickings.mapped("sale_id").filtered(lambda so: so)

    def _nakel_demand_mode_sibling_pick_domain(self, wave_pickings):
        """Dominio de PICK hermanos (misma OV/grupo/origen) aún fuera del batch."""
        origins = set()
        group_ids = set()
        sale_ids = set()
        for picking in wave_pickings:
            origin = (picking.origin or "").strip()
            if origin:
                origins.add(origin)
            if picking.group_id:
                group_ids.add(picking.group_id.id)
            if picking.sale_id:
                sale_ids.add(picking.sale_id.id)

        sales = self._nakel_demand_mode_sale_orders(wave_pickings)
        sale_ids.update(sales.ids)

        parts = []
        if group_ids:
            parts.append([("group_id", "in", list(group_ids))])
        if sale_ids:
            parts.append([("sale_id", "in", list(sale_ids))])
        if origins:
            parts.append([("origin", "in", list(origins))])
        if not parts:
            return [(0, "=", 1)]

        pick_type = [
            "|",
            ("picking_type_id.sequence_code", "=", "PICK"),
            ("name", "ilike", "CEN/PICK/%"),
        ]
        pending = [("state", "not in", ("done", "cancel"))]
        free_batch = [
            "|",
            ("batch_id", "=", False),
            ("batch_id", "=", self.id),
        ]
        return expression.AND([expression.OR(parts), pick_type, pending, free_batch])

    def _nakel_demand_mode_attach_sibling_pickings(self, wave_pickings):
        """
        Incorpora a la ola los PICK de las mismas OV que quedaron fuera (sin reserva / otro PICK).

        Devuelve recordset de pickings recién agregados al batch.
        """
        self.ensure_one()
        ICP = self.env["ir.config_parameter"]
        if not ICP.nakel_barcode_wave_demand_mode_include_so_sibling_picks():
            return self.env["stock.picking"]

        domain = self._nakel_demand_mode_sibling_pick_domain(wave_pickings)
        if domain == [(0, "=", 1)]:
            return self.env["stock.picking"]

        candidates = self.env["stock.picking"].search(domain)
        in_batch_ids = set(wave_pickings.ids) | set(self.picking_ids.ids)
        to_attach = candidates.filtered(
            lambda p: p.id not in in_batch_ids and p._nakel_demand_mode_applies_to_picking()
        )
        if not to_attach:
            return self.env["stock.picking"]

        return self._nakel_attach_pickings_to_wave(to_attach)

    def _nakel_demand_mode_pickings(self):
        """PICK de la ola + hermanos OV pendientes (opcional vía ICP)."""
        self.ensure_one()
        wave_pickings = self._nakel_demand_mode_pickings_in_batch()
        attached = self._nakel_demand_mode_attach_sibling_pickings(wave_pickings)
        if attached:
            wave_pickings |= attached
        return wave_pickings.filtered(lambda p: p._nakel_demand_mode_applies_to_picking())

    def action_nakel_apply_demand_mode(self):
        """
        Fase 1: sube quantity de líneas al product_uom_qty del move (demanda OV).

        Opcionalmente agrega PICK hermanos de las OV de la ola antes de aplicar.
        Requiere ICP nakel_barcode_wave_demand_mode.enable = 1.
        """
        self.ensure_one()
        ICP = self.env["ir.config_parameter"]
        if not ICP.nakel_barcode_wave_demand_mode_is_enabled():
            return self._nakel_demand_mode_notification(
                _("Modo demanda OV"),
                _(
                    "El modo demanda está desactivado. "
                    "Ajustes → Técnico → Parámetros del sistema → "
                    "nakel_barcode_wave_demand_mode.enable = 1"
                ),
                "warning",
            )

        report = self._nakel_demand_coverage_report()
        if report["status"] == "missing":
            return self.action_nakel_open_coverage_gaps()

        in_batch_before = self._nakel_demand_mode_pickings_in_batch()
        pickings = self._nakel_demand_mode_pickings()
        attached_count = len(pickings) - len(in_batch_before)

        if not pickings:
            return self._nakel_demand_mode_notification(
                _("Modo demanda OV"),
                _("No hay PICK pendientes de esta ola que entren en el modo demanda."),
                "warning",
            )

        totals = {"moves": 0, "lines_updated": 0, "lines_created": 0, "skipped": 0}
        detail_lines = []
        supervisor_ctx = {"nakel_demand_mode_supervisor_action": True}
        for picking in pickings:
            stats = picking.with_context(**supervisor_ctx)._nakel_apply_demand_mode()
            for key in totals:
                totals[key] += stats[key]
            if stats["lines_updated"] or stats["lines_created"]:
                detail_lines.append(
                    _("%(pick)s: %(updated)s líneas ajustadas, %(created)s creadas")
                    % {
                        "pick": picking.name,
                        "updated": stats["lines_updated"],
                        "created": stats["lines_created"],
                    }
                )

        msg = _(
            "PICK: %(pickings)s (+%(attached)s agregados). "
            "Productos: %(moves)s. Líneas ajustadas: %(updated)s. "
            "Creadas: %(created)s. Ya estaban OK: %(skipped)s."
        ) % {
            "pickings": len(pickings),
            "attached": attached_count,
            "moves": totals["moves"],
            "updated": totals["lines_updated"],
            "created": totals["lines_created"],
            "skipped": totals["skipped"],
        }
        pre_green = self.with_context(**supervisor_ctx)._nakel_barcode_pre_green_official_pickings()
        pre_green_msg = _(
            "Barcode pre-verde: %(lines_updated)s líneas en %(pickings)s PICK."
        ) % pre_green
        msg = "%s %s" % (msg, pre_green_msg)

        if ICP.nakel_barcode_wave_demand_mode_should_log():
            log_lines = detail_lines[:30] if detail_lines else [
                _("Sin cambios: la reserva ya coincidía con el pedido.")
            ]
            log_lines.append(msg)
            if pre_green["lines_updated"]:
                log_lines.append(pre_green_msg)
            self._nakel_message_post_log(_("Modo demanda OV aplicado"), log_lines)

        notif_type = "success" if (
            totals["lines_updated"] or totals["lines_created"] or pre_green["lines_updated"]
        ) else "info"
        return self._nakel_demand_mode_notification(_("Modo demanda OV"), msg, notif_type)

    def _nakel_demand_mode_notification(self, title, message, notif_type, sticky=False):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": notif_type,
                "sticky": sticky,
            },
        }
