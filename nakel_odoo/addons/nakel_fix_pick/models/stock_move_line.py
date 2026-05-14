# -*- coding: utf-8 -*-

from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero


def _nakel_float_from_vals(vals: dict, key: str):
    if key not in vals:
        return None
    try:
        return float(vals.get(key) or 0.0)
    except Exception:
        return 0.0


def _nakel_adjust_vals_pick_consistency(vals: dict) -> dict:
    """
    Align picked (and qty_done when the ORM exposes it) with positive quantity / qty_done
    coming from Barcode create/write payloads.
    """
    vals = dict(vals)
    qd = _nakel_float_from_vals(vals, "qty_done") if "qty_done" in vals else None
    qt = _nakel_float_from_vals(vals, "quantity") if "quantity" in vals else None

    positives = [v for v in (qd, qt) if v is not None and v > 0.0]
    max_positive = max(positives) if positives else None

    if max_positive is not None and max_positive > 0.0:
        vals["picked"] = True
        if qt is not None and qt > 0.0 and (qd is None or qd <= 0.0):
            vals["qty_done"] = qt
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

    @api.model_create_multi
    def create(self, vals_list):
        if not self._nakel_fix_pick_enabled():
            return super().create(vals_list)
        keys = ("qty_done", "quantity", "picked")
        new_vals_list = []
        for vals in vals_list:
            vals = dict(vals)
            if any(k in vals for k in keys):
                vals = _nakel_adjust_vals_pick_consistency(vals)
            new_vals_list.append(vals)
        return super().create(new_vals_list)

    def write(self, vals):
        """
        If enabled, keep `picked` (and often `qty_done`) consistent when Barcode writes quantities.

        Rationale (observed in Nakel):
        - Barcode puede mandar `picked: False` junto con cantidad > 0; la guarda antigua
          (`if "picked" not in vals`) saltaba y dejaba datos incoherentes.
        - A veces solo llega `quantity`; si queda `qty_done` en 0, la UI puede mostrar 0 / … tras refresh.

        Nota: `quantity` es la reserva operativa; `qty_done` es lo hecho. Solo copiamos
        `quantity` -> `qty_done` cuando hay cantidad > 0 y `qty_done` no viene positivo en `vals`.
        """
        if not self._nakel_fix_pick_enabled():
            return super().write(vals)

        keys = ("qty_done", "quantity", "picked")
        if not any(k in vals for k in keys):
            return super().write(vals)

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
