# -*- coding: utf-8 -*-

from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_is_zero


def _nakel_float_from_vals(vals: dict, key: str):
    if key not in vals:
        return None
    try:
        return float(vals.get(key) or 0.0)
    except Exception:
        return 0.0


def _nakel_adjust_vals_pick_consistency(vals: dict) -> dict:
    """
    Alinear picked con qty_done en writes de Barcode.

    No copiar quantity -> qty_done: tras Modo demanda OV la reserva ya está llena y
    sumar escaneos duplicaba qty_done (24/12). El pre-verde del batch fija qty_done.
    """
    vals = dict(vals)
    qd = _nakel_float_from_vals(vals, "qty_done") if "qty_done" in vals else None
    qt = _nakel_float_from_vals(vals, "quantity") if "quantity" in vals else None

    if qd is not None and qd > 0.0:
        vals["picked"] = True
    elif qd is not None and qd <= 0.0 and (qt is None or qt <= 0.0):
        if "picked" not in vals:
            vals["picked"] = False
    elif qt is not None and qt <= 0.0 and qd is None:
        if "picked" not in vals:
            vals["picked"] = False

    return vals


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    @api.model
    def _nakel_fix_pick_enabled(self):
        # Default OFF: only active if explicitly enabled in System Parameters.
        val = self.env["ir.config_parameter"].sudo().get_param("nakel_fix_pick.enable", "0")
        return str(val).strip().lower() in ("1", "true", "yes", "y", "on")

    @api.model
    def _nakel_block_unlink_open_wave_lines(self):
        val = self.env["ir.config_parameter"].sudo().get_param(
            "nakel_fix_pick.block_unlink_open_wave_lines", "1"
        )
        return str(val).strip().lower() in ("1", "true", "yes", "y", "on")

    @api.model
    def _nakel_skip_fix_pick_sync(self):
        return bool(
            self.env.context.get("nakel_demand_mode_bump")
            or self.env.context.get("nakel_barcode_pre_green")
        )

    def _nakel_cap_vals_to_move_demand(self, vals):
        """Tope qty_done/quantity al pedido OV en líneas de olas WAVE."""
        vals = dict(vals)
        if self._nakel_skip_fix_pick_sync():
            return vals
        if "qty_done" not in vals and "quantity" not in vals:
            return vals

        move = self.move_id
        picking = self.picking_id
        if not move and vals.get("move_id"):
            move = self.env["stock.move"].browse(vals["move_id"])
        if not picking and vals.get("picking_id"):
            picking = self.env["stock.picking"].browse(vals["picking_id"])
        if not picking and move:
            picking = move.picking_id

        batch = picking.batch_id if picking else self.env["stock.picking.batch"]
        if not batch or not getattr(batch, "is_wave", False) or not move:
            return vals

        demand = move.product_uom_qty
        rounding = move.product_uom.rounding
        for key in ("qty_done", "quantity"):
            if key not in vals:
                continue
            raw = _nakel_float_from_vals(vals, key)
            if raw is not None and float_compare(raw, demand, precision_rounding=rounding) > 0:
                vals[key] = demand

        # Flujo invertido: si ya hay qty_done parcial, no dejar sumar quantity por escaneo.
        if len(self) == 1:
            qd_current = self.qty_done or 0.0
            line_rounding = self.product_uom_id.rounding
            if not float_is_zero(qd_current, precision_rounding=line_rounding):
                for key in ("qty_done", "quantity"):
                    if key not in vals:
                        continue
                    raw = _nakel_float_from_vals(vals, key)
                    if raw is not None and float_compare(raw, qd_current, precision_rounding=line_rounding) > 0:
                        vals[key] = qd_current
        return vals

    def _nakel_apply_fix_pick_vals(self, vals):
        vals = self._nakel_cap_vals_to_move_demand(vals)
        return _nakel_adjust_vals_pick_consistency(vals)

    @api.model_create_multi
    def create(self, vals_list):
        if not self._nakel_fix_pick_enabled() or self._nakel_skip_fix_pick_sync():
            return super().create(vals_list)
        keys = ("qty_done", "quantity", "picked")
        new_vals_list = []
        for vals in vals_list:
            vals = dict(vals)
            if any(k in vals for k in keys):
                temp = self.new(vals)
                vals = temp._nakel_apply_fix_pick_vals(vals)
            new_vals_list.append(vals)
        return super().create(new_vals_list)

    def write(self, vals):
        """
        Si está activo, mantiene picked coherente con qty_done y capa cantidades al pedido OV
        en olas WAVE (evita sobrepick 24/12 tras escaneo sobre reserva llena).
        """
        if not self._nakel_fix_pick_enabled() or self._nakel_skip_fix_pick_sync():
            return super().write(vals)

        keys = ("qty_done", "quantity", "picked")
        if not any(k in vals for k in keys):
            return super().write(vals)

        if len(self) == 1:
            vals = self._nakel_apply_fix_pick_vals(dict(vals))
            return super().write(vals)

        if any(k in vals for k in ("qty_done", "quantity")):
            for line in self:
                line_vals = line._nakel_apply_fix_pick_vals(dict(vals))
                super(StockMoveLine, line).write(line_vals)
            return True

        vals = _nakel_adjust_vals_pick_consistency(dict(vals))
        return super().write(vals)

    def unlink(self):
        """
        Evita borrar líneas *ya pickeadas* de una ola en curso (configurable).

        Odoo al validar (`stock.move._action_done`) hace `unlink` de líneas **no pickeadas** y
        `stock.move.line._action_done` borra líneas con cantidad 0: eso debe seguir permitido
        aunque la ola esté `in_progress`, si no Barcode no puede cerrar la ola con un solo operario.

        `stock_barcode.split_uncompleted_moves` hace `unlink` masivo de líneas del movimiento;
        se marca con contexto `nakel_barcode_split_uncompleted` desde `nakel_fix_pick.stock.move`.
        """
        if self.env.context.get("nakel_barcode_split_uncompleted"):
            return super().unlink()
        if self._nakel_block_unlink_open_wave_lines() and not self.env.su:
            if self.env.user.has_group("stock.group_stock_manager"):
                return super().unlink()
            dangerous = self.filtered(
                lambda line: line.picked
                and line.picking_id.batch_id
                and line.picking_id.batch_id.state == "in_progress"
                and not float_is_zero(line.quantity, precision_rounding=line.product_uom_id.rounding)
            )
            if dangerous:
                batches = dangerous.mapped("picking_id.batch_id.name")
                raise UserError(
                    _(
                        "No se pueden eliminar líneas ya recogidas (picked) mientras la ola %(batches)s "
                        "está en curso (in_progress). Si validaba desde Barcode y ve esto, avise a soporte. "
                        "Para una corrección excepcional use un usuario Administrador de inventario."
                    )
                    % {"batches": ", ".join(sorted(set(batches)))}
                )
        return super().unlink()

    @api.model
    def nakel_backfill_picked_for_wave(self, batch_id, limit=None):
        """
        Backfill helper (manual use only): set picked=True where quantity>0 for a given wave.

        - batch_id: stock.picking.batch id (Wave/WAVE/xxxxx)
        - limit: optional int to process in chunks
        """
        if not self._nakel_fix_pick_enabled():
            return {
                "ok": False,
                "reason": "nakel_fix_pick.enable is disabled",
                "updated": 0,
            }

        domain = [
            ("picking_id.batch_id", "=", batch_id),
            ("quantity", ">", 0),
            ("picked", "=", False),
        ]
        lines = self.search(domain, limit=limit)
        lines.write({"picked": True})
        return {
            "ok": True,
            "batch_id": batch_id,
            "updated": len(lines),
            "limited": bool(limit),
        }
