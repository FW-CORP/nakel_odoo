# -*- coding: utf-8 -*-

from odoo import models
from odoo.tools.float_utils import float_compare, float_is_zero


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _nakel_is_pick_picking(self, picking=None):
        picking = picking or self
        ptype = picking.picking_type_id
        if not ptype:
            return False
        if getattr(ptype, "sequence_code", None) == "PICK":
            return True
        name = picking.name or ""
        return name.startswith("CEN/PICK/")

    def _nakel_demand_mode_applies_to_picking(self):
        self.ensure_one()
        ICP = self.env["ir.config_parameter"]
        if not ICP.nakel_barcode_wave_demand_mode_is_enabled():
            return False
        apply_on = (ICP.sudo().get_param("nakel_barcode_wave_demand_mode.apply_on") or "pick").strip()
        if apply_on == "pick" and not self._nakel_is_pick_picking():
            return False
        if apply_on == "non_out" and self._nakel_is_out_picking(self):
            return False
        wh_ids = ICP.nakel_barcode_wave_demand_mode_warehouse_ids()
        if wh_ids and self.picking_type_id.warehouse_id.id not in wh_ids:
            return False
        return True

    def _nakel_demand_mode_write_line(self, line, quantity):
        """
        Sube quantity a demanda OV.

        Odoo 18 re-reserva al escribir quantity y capa al stock; stock_move_line
        con contexto nakel_demand_mode_bump evita eso. picked=False para que Barcode
        no muestre la línea verde sin escanear.
        """
        line.with_context(nakel_demand_mode_bump=True).write(
            {
                "quantity": quantity,
                "picked": False,
            }
        )

    def _nakel_barcode_pre_green_lines(self):
        """
        Deja líneas verdes en Barcode (qty_done = tope demanda/reserva).

        - Primera pasada (qty_done=0, sin pickear): marca qty_done=target.
        - Si el operario ya bajó qty_done (< target): no subir (stock real / reabrir Barcode).
        - Si qty_done > target: capa al tope.
        """
        self.ensure_one()
        if self.state in ("done", "cancel"):
            return 0
        if not self._nakel_demand_mode_applies_to_picking():
            return 0

        updated = 0
        for line in self.move_line_ids:
            qty = line.quantity or 0.0
            qd = line.qty_done or 0.0
            rounding = line.product_uom_id.rounding
            move = line.move_id
            if not move:
                continue

            demand = move.product_uom_qty
            move_rounding = move.product_uom.rounding
            target = min(qty, demand) if not float_is_zero(qty, precision_rounding=rounding) else demand

            if float_is_zero(target, precision_rounding=move_rounding):
                continue

            # Operario ya corrigió a la baja: no resetear (reabrir Barcode ni Modo demanda).
            if float_compare(qd, target, precision_rounding=move_rounding) < 0:
                if (
                    float_is_zero(qd, precision_rounding=move_rounding)
                    and not line.picked
                    and not float_is_zero(qty, precision_rounding=rounding)
                ):
                    pass  # línea sin tocar: primer pre-verde
                else:
                    continue

            if (
                float_compare(qd, target, precision_rounding=move_rounding) == 0
                and line.picked
                and float_compare(qty, target, precision_rounding=move_rounding) == 0
            ):
                continue

            vals = {"qty_done": target, "picked": True}
            if float_compare(qty, target, precision_rounding=move_rounding) != 0:
                vals["quantity"] = target
            line.with_context(nakel_barcode_pre_green=True).write(vals)
            updated += 1
        return updated

    def _nakel_apply_demand_mode(self):
        """
        Por cada move pendiente: subir move.line.quantity hasta move.product_uom_qty (demanda OV).

        No sincroniza quants (puente). Tras aplicar en la ola, el batch ejecuta pre-verde Barcode.
        """
        self.ensure_one()
        if self.state in ("done", "cancel"):
            return {"moves": 0, "lines_updated": 0, "lines_created": 0, "skipped": 0}

        stats = {"moves": 0, "lines_updated": 0, "lines_created": 0, "skipped": 0}
        MoveLine = self.env["stock.move.line"]

        for move in self.move_ids.filtered(
            lambda m: m.state not in ("done", "cancel") and not float_is_zero(
                m.product_uom_qty, precision_rounding=m.product_uom.rounding
            )
        ):
            demand = move.product_uom_qty
            rounding = move.product_uom.rounding
            lines = move.move_line_ids
            stats["moves"] += 1

            picked_done = sum(lines.mapped("qty_done"))
            if (
                not float_is_zero(picked_done, precision_rounding=rounding)
                and float_compare(picked_done, demand, precision_rounding=rounding) < 0
            ):
                # Operario ya bajó qty_done (stock real): no re-subir quantity al pedido OV.
                stats["skipped"] += 1
                continue

            if (
                not self.env.context.get("nakel_demand_mode_supervisor_action")
                and lines
                and all(
                    float_is_zero(l.quantity, precision_rounding=l.product_uom_id.rounding)
                    and float_is_zero(l.qty_done, precision_rounding=l.product_uom_id.rounding)
                    for l in lines
                )
            ):
                # Sin stock en piso (0/0): no re-armar quantity al pedido OV.
                stats["skipped"] += 1
                continue

            if not lines:
                vals = move._prepare_move_line_vals(quantity=0)
                vals.update(
                    {
                        "quantity": demand,
                        "picked": False,
                        "picking_id": self.id,
                    }
                )
                MoveLine.with_context(nakel_demand_mode_bump=True).create(vals)
                stats["lines_created"] += 1
                continue

            reserved = sum(lines.mapped("quantity"))
            if float_compare(reserved, demand, precision_rounding=rounding) >= 0:
                stats["skipped"] += 1
                continue

            if len(lines) == 1:
                self._nakel_demand_mode_write_line(lines, demand)
                stats["lines_updated"] += 1
                continue

            # Varios lotes/ubicaciones: sumar el faltante en la línea con mayor quantity.
            line = max(lines, key=lambda ml: ml.quantity or 0.0)
            new_qty = (line.quantity or 0.0) + (demand - reserved)
            self._nakel_demand_mode_write_line(line, new_qty)
            stats["lines_updated"] += 1

        return stats
