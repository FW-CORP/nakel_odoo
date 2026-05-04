# -*- coding: utf-8 -*-
"""
Ventas netas desde facturas Odoo (account.move / account.move.line).

- Cuenta **facturas de cliente** (`out_invoice`) y resta **notas de crédito**
  (`out_refund`) según `quantity` en líneas de producto, con `invoice_date`
  en el rango y movimientos **posted**.
- Así el informe refleja **venta / facturación neta**, no el pedido bruto
  (`sale.order.line.product_uom_qty`), que no refleja devoluciones por NC.

No incluye otros tipos de asiento salvo `out_invoice` / `out_refund` (p. ej. tickets POS
sin factura de cliente no pasan por este criterio).

Uso interno desde `rellenar_promo_cantidades_odoo_master_dev.py` y
`rellenar_ventas_stock_odoo_master_dev.py`.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def _aml_base_domain(
    d0: str,
    d1: str,
    partner_id: int | None,
    product_id: int | None,
) -> list[Any]:
    dom: list[Any] = [
        ("move_id.state", "=", "posted"),
        ("move_id.invoice_date", ">=", d0),
        ("move_id.invoice_date", "<", d1),
        ("product_id", "!=", False),
    ]
    # Partner exacto: evita duplicar ventas del comercial en cada sucursal del informe promo.
    if partner_id is not None:
        dom.append(("partner_id", "=", partner_id))
    if product_id is not None:
        dom.append(("product_id", "=", product_id))
    return dom


def _accumulate_aml_qty(
    models: Any,
    uid: int,
    db: str,
    pwd: str,
    base: list[Any],
    move_type: str,
    sign: float,
    acc: dict[int, float],
) -> None:
    dom = base + [("move_id.move_type", "=", move_type)]
    aml_ids = models.execute_kw(
        db,
        uid,
        pwd,
        "account.move.line",
        "search",
        [dom],
        {"limit": 80000},
    )
    for i in range(0, len(aml_ids), 500):
        batch = aml_ids[i : i + 500]
        lines = models.execute_kw(
            db,
            uid,
            pwd,
            "account.move.line",
            "read",
            [batch],
            {"fields": ["product_id", "quantity"]},
        )
        for ln in lines:
            pid = ln.get("product_id")
            if isinstance(pid, (list, tuple)) and pid:
                pi = int(pid[0])
            elif isinstance(pid, int):
                pi = pid
            else:
                continue
            q = float(ln.get("quantity") or 0.0) * sign
            acc[pi] += q


def aml_net_qty_by_product_partner(
    models: Any,
    uid: int,
    db: str,
    pwd: str,
    partner_id: int,
    d0: str,
    d1: str,
    line_cache: dict[tuple[int, str, str], dict[int, float]],
) -> dict[int, float]:
    """
    Suma neta por product_id para el contacto facturado (`partner_id` exacto en líneas AML).
    """
    key = (partner_id, d0, d1)
    if key in line_cache:
        return line_cache[key]
    base = _aml_base_domain(d0, d1, partner_id, None)
    acc: dict[int, float] = defaultdict(float)
    _accumulate_aml_qty(models, uid, db, pwd, base, "out_invoice", 1.0, acc)
    _accumulate_aml_qty(models, uid, db, pwd, base, "out_refund", -1.0, acc)
    line_cache[key] = dict(acc)
    return line_cache[key]


def aml_net_qty_by_product_global(
    models: Any,
    uid: int,
    db: str,
    pwd: str,
    product_id: int,
    d0: str,
    d1: str,
    line_cache: dict[tuple[str, int, str, str], float],
) -> float:
    """Cantidad neta facturada (ventas − NC) de un producto en el periodo, todos los clientes."""
    key = ("g", product_id, d0, d1)
    if key in line_cache:
        return float(line_cache[key])
    base = _aml_base_domain(d0, d1, None, product_id)
    acc = 0.0
    for move_type, sign in (("out_invoice", 1.0), ("out_refund", -1.0)):
        dom = base + [("move_id.move_type", "=", move_type)]
        aml_ids = models.execute_kw(
            db,
            uid,
            pwd,
            "account.move.line",
            "search",
            [dom],
            {"limit": 50000},
        )
        for i in range(0, len(aml_ids), 500):
            batch = aml_ids[i : i + 500]
            lines = models.execute_kw(
                db,
                uid,
                pwd,
                "account.move.line",
                "read",
                [batch],
                {"fields": ["quantity"]},
            )
            for ln in lines:
                acc += float(ln.get("quantity") or 0.0) * sign
    line_cache[key] = acc
    return acc
