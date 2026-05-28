# -*- coding: utf-8 -*-

from odoo import fields, models, tools


class NakelSalesDashboardReport(models.Model):
    _name = "nakel.sales.dashboard.report"
    _description = "Nakel - Tablero Ventas + POS"
    _auto = False
    _order = "date_order desc, source_type, document_name"

    source_type = fields.Selection(
        selection=[
            ("sale", "Ventas estándar"),
            ("pos", "Punto de venta"),
        ],
        string="Canal",
        readonly=True,
    )
    source_model = fields.Char(string="Modelo origen", readonly=True)
    source_res_id = fields.Integer(string="ID origen", readonly=True)
    document_name = fields.Char(string="Documento", readonly=True)
    date_order = fields.Datetime(string="Fecha", readonly=True)
    company_id = fields.Many2one("res.company", string="Compañía", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Moneda", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Cliente", readonly=True)
    salesperson_id = fields.Many2one("res.users", string="Vendedor", readonly=True)
    team_id = fields.Many2one("crm.team", string="Equipo de ventas", readonly=True)
    warehouse_id = fields.Many2one("stock.warehouse", string="Sucursal / almacén", readonly=True)
    pos_config_id = fields.Many2one("pos.config", string="Punto de venta", readonly=True)
    journal_id = fields.Many2one("account.journal", string="Diario POS", readonly=True)
    pricelist_id = fields.Many2one("product.pricelist", string="Lista de precios", readonly=True)
    product_id = fields.Many2one("product.product", string="Producto", readonly=True)
    product_tmpl_id = fields.Many2one("product.template", string="Plantilla producto", readonly=True)
    categ_id = fields.Many2one("product.category", string="Categoría producto", readonly=True)
    source_state = fields.Char(string="Estado origen", readonly=True)

    amount_total = fields.Monetary(string="Total", currency_field="currency_id", readonly=True)
    amount_untaxed = fields.Monetary(string="Base imponible", currency_field="currency_id", readonly=True)
    amount_tax = fields.Monetary(string="Impuestos", currency_field="currency_id", readonly=True)
    margin = fields.Monetary(string="Margen", currency_field="currency_id", readonly=True)
    qty = fields.Float(string="Cantidad", readonly=True)
    line_count = fields.Integer(string="Líneas", readonly=True)
    document_count = fields.Integer(string="Documentos", readonly=True)

    def action_open_source(self):
        self.ensure_one()
        if not self.source_model or not self.source_res_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": self.document_name or self.display_name,
            "res_model": self.source_model,
            "res_id": self.source_res_id,
            "view_mode": "form",
            "target": "current",
        }

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            """
            CREATE OR REPLACE VIEW %s AS (
                WITH pos_line_totals AS (
                    SELECT
                        pol.order_id,
                        SUM(pol.qty) AS qty,
                        COUNT(pol.id) AS line_count
                    FROM pos_order_line pol
                    GROUP BY pol.order_id
                ),
                sale_rows AS (
                    SELECT
                        (sol.id * 2)::bigint AS id,
                        'sale'::varchar AS source_type,
                        'sale.order'::varchar AS source_model,
                        so.id AS source_res_id,
                        so.name::varchar AS document_name,
                        so.date_order AS date_order,
                        so.company_id,
                        so.currency_id,
                        so.partner_id,
                        so.user_id AS salesperson_id,
                        so.team_id,
                        so.warehouse_id,
                        NULL::integer AS pos_config_id,
                        NULL::integer AS journal_id,
                        so.pricelist_id,
                        sol.product_id,
                        product.product_tmpl_id,
                        template.categ_id,
                        so.state::varchar AS source_state,
                        sol.price_total AS amount_total,
                        sol.price_subtotal AS amount_untaxed,
                        (sol.price_total - sol.price_subtotal) AS amount_tax,
                        sol.margin AS margin,
                        sol.product_uom_qty AS qty,
                        1 AS line_count,
                        CASE
                            WHEN row_number() OVER (
                                PARTITION BY so.id
                                ORDER BY sol.id
                            ) = 1
                            THEN 1
                            ELSE 0
                        END AS document_count
                    FROM sale_order_line sol
                    JOIN sale_order so
                        ON so.id = sol.order_id
                    LEFT JOIN product_product product
                        ON product.id = sol.product_id
                    LEFT JOIN product_template template
                        ON template.id = product.product_tmpl_id
                    WHERE so.state IN ('sale', 'done')
                      AND sol.display_type IS NULL
                ),
                pos_rows AS (
                    SELECT
                        (po.id * 2 + 1)::bigint AS id,
                        'pos'::varchar AS source_type,
                        'pos.order'::varchar AS source_model,
                        po.id AS source_res_id,
                        po.name::varchar AS document_name,
                        po.date_order AS date_order,
                        po.company_id,
                        company.currency_id,
                        po.partner_id,
                        po.user_id AS salesperson_id,
                        po.crm_team_id AS team_id,
                        picking_type.warehouse_id,
                        po.config_id AS pos_config_id,
                        po.sale_journal AS journal_id,
                        po.pricelist_id,
                        NULL::integer AS product_id,
                        NULL::integer AS product_tmpl_id,
                        NULL::integer AS categ_id,
                        po.state::varchar AS source_state,
                        po.amount_total AS amount_total,
                        (po.amount_total - po.amount_tax) AS amount_untaxed,
                        po.amount_tax AS amount_tax,
                        0.0 AS margin,
                        COALESCE(pos_line_totals.qty, 0.0) AS qty,
                        COALESCE(pos_line_totals.line_count, 0) AS line_count,
                        1 AS document_count
                    FROM pos_order po
                    LEFT JOIN pos_config config
                        ON config.id = po.config_id
                    LEFT JOIN stock_picking_type picking_type
                        ON picking_type.id = config.picking_type_id
                    LEFT JOIN res_company company
                        ON company.id = po.company_id
                    LEFT JOIN pos_line_totals
                        ON pos_line_totals.order_id = po.id
                    WHERE po.state IN ('paid', 'done', 'invoiced')
                )
                SELECT * FROM sale_rows
                UNION ALL
                SELECT * FROM pos_rows
            )
            """
            % self._table
        )
