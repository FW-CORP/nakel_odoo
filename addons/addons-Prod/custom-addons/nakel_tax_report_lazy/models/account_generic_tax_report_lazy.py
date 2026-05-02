# -*- coding: utf-8 -*-
"""
PoC: primer payload del informe fiscal genérico solo con nivel superior (p. ej. Ventas/Compras).
Subniveles vía expand / get_expanded_lines.

La agregación SQL completa sigue ejecutándose en la carga inicial para totales correctos
en el nivel superior; se reduce sobre todo el JSON enviado al navegador.
"""
from odoo import api, models, _
from odoo.exceptions import UserError


class AccountGenericTaxReportHandlerLazy(models.AbstractModel):
    _inherit = 'account.generic.tax.report.handler'

    EXPAND_FN = '_report_expand_unfoldable_line_generic_tax_lazy'
    ICP_DISABLE = 'nakel_tax_report_lazy.disable'

    def _tax_lazy_is_disabled(self):
        param = self.env['ir.config_parameter'].sudo().get_param(self.ICP_DISABLE, 'False')
        return str(param).lower() in ('1', 'true', 'yes')

    def _tax_lazy_report_grouping_mode(self, report):
        name = report.custom_handler_model_name
        if name == 'account.generic.tax.report.handler.tax.account':
            return 'tax_account'
        if name == 'account.generic.tax.report.handler.account.tax':
            return 'account_tax'
        return 'default'

    def _get_dynamic_lines(self, report, options, grouping, warnings=None):
        if (
            self._tax_lazy_is_disabled()
            or options.get('export_mode') is not None
            or options.get('unfold_all')
        ):
            return super()._get_dynamic_lines(report, options, grouping, warnings=warnings)

        options_by_column_group = report._split_options_per_column_group(options)

        if grouping == 'tax_account':
            groupby_fields = [('src_tax', 'type_tax_use'), ('src_tax', 'id'), ('account', 'id')]
            comodels = [None, 'account.tax', 'account.account']
            tax_amount_hierarchy = self._read_generic_tax_report_amounts(
                report, options_by_column_group, groupby_fields)
        elif grouping == 'account_tax':
            groupby_fields = [('src_tax', 'type_tax_use'), ('account', 'id'), ('src_tax', 'id')]
            comodels = [None, 'account.account', 'account.tax']
            tax_amount_hierarchy = self._read_generic_tax_report_amounts(
                report, options_by_column_group, groupby_fields)
        else:
            groupby_fields = [('src_tax', 'type_tax_use'), ('src_tax', 'id')]
            comodels = [None, 'account.tax']
            tax_amount_hierarchy = self._read_generic_tax_report_amounts_no_tax_details(
                report, options, options_by_column_group)

        record_ids_gb = [set() for _dummy in groupby_fields]

        def populate_record_ids_gb_recursively(node, level=0):
            for k, v in node.items():
                if k:
                    record_ids_gb[level].add(k)
                    if v.get('children'):
                        populate_record_ids_gb_recursively(v['children'], level=level + 1)

        populate_record_ids_gb_recursively(tax_amount_hierarchy)

        sorting_map_list = []
        for i, comodel in enumerate(comodels):
            if comodel:
                records = self.env[comodel].with_context(active_test=False).search(
                    [('id', 'in', tuple(record_ids_gb[i]))])
                sorting_map = {r.id: (r, j) for j, r in enumerate(records)}
                sorting_map_list.append(sorting_map)
            else:
                selection = self.env['account.tax']._fields['type_tax_use']._description_selection(self.env)
                sorting_map_list.append({
                    v[0]: (v, j) for j, v in enumerate(selection) if v[0] in record_ids_gb[i]
                })

        lines = []
        self._tax_lazy_append_level(
            report, options, lines, sorting_map_list, groupby_fields,
            tax_amount_hierarchy, child_level_index=0, type_tax_use=None,
            parent_line_id=None, warnings=warnings,
        )
        return [(0, line) for line in lines]

    def _tax_lazy_line_level(self, child_level_index):
        return child_level_index if child_level_index == 0 else child_level_index + 1

    def _tax_lazy_append_level(
            self, report, options, lines, sorting_map_list, groupby_fields,
            values_node, child_level_index, type_tax_use, parent_line_id, warnings,
    ):
        if child_level_index >= len(groupby_fields):
            return

        alias, field = groupby_fields[child_level_index]
        groupby_key = f'{alias}_{field}'
        sorting_map = sorting_map_list[child_level_index]
        sorted_keys = sorted(list(values_node.keys()), key=lambda x: sorting_map[x][1])

        last_idx = len(groupby_fields) - 1

        for key in sorted_keys:
            if groupby_key == 'src_tax_type_tax_use':
                type_tax_use = key
            sign = -1 if type_tax_use == 'sale' else 1

            tax_amount_dict = values_node[key]
            columns = []
            tax_base_amounts = tax_amount_dict['base_amount']
            tax_amounts = tax_amount_dict['tax_amount']

            for column in options['columns']:
                tax_base_amount = tax_base_amounts[column['column_group_key']]
                tax_amount = tax_amounts[column['column_group_key']]
                expr_label = column.get('expression_label')
                col_value = ''

                if expr_label == 'net' and child_level_index == last_idx:
                    col_value = sign * tax_base_amount
                if expr_label == 'tax':
                    col_value = sign * tax_amount

                columns.append(report._build_column_dict(col_value, column, options=options))

                if expr_label == 'tax' and options.get('account_journal_report_tax_deductibility_columns'):
                    for deduct_type in ('tax_non_deductible', 'tax_deductible', 'tax_due'):
                        columns.append(report._build_column_dict(
                            col_value=sign * tax_amount_dict[deduct_type][column['column_group_key']],
                            col_data={
                                'figure_type': 'monetary',
                                'column_group_key': column['column_group_key'],
                                'expression_label': deduct_type,
                            },
                            options=options,
                        ))

            default_vals = {
                'columns': columns,
                'level': self._tax_lazy_line_level(child_level_index),
                'unfoldable': False,
            }

            children = tax_amount_dict.get('children') or {}
            can_unfold = bool(children) and child_level_index < last_idx

            if can_unfold:
                default_vals['unfoldable'] = True
                default_vals['unfolded'] = False
                default_vals['expand_function'] = self.EXPAND_FN

            report_line = self._build_report_line(
                report, options, default_vals, groupby_key, sorting_map[key][0],
                parent_line_id, warnings,
            )

            if groupby_key == 'src_tax_id':
                report_line['caret_options'] = 'generic_tax_report'

            lines.append(report_line)

    def _tax_lazy_parent_node(self, report, tax_amount_hierarchy, line_dict_id):
        """Navega hasta el nodo padre (dict con base_amount, tax_amount, children)."""
        parsed = report._parse_line_id(line_dict_id, markup_as_string=True)
        if not parsed or parsed[0][1] != 'account.report':
            return None
        node = tax_amount_hierarchy
        for markup, model, value in parsed[1:]:
            if model in (None, ''):
                key = markup
            elif model == 'account.tax':
                key = value
            elif model == 'account.account':
                key = value
            else:
                return None
            node = node[key]
        return node

    def _tax_lazy_type_tax_use_from_id(self, report, line_dict_id):
        parsed = report._parse_line_id(line_dict_id, markup_as_string=True)
        if not parsed:
            return None
        for markup, model, value in parsed[1:]:
            if model in (None, '') and markup in ('sale', 'purchase'):
                return markup
        return None

    def _report_expand_unfoldable_line_generic_tax_lazy(
            self, line_dict_id, groupby, options, progress, offset, unfold_all_batch_data=None,
    ):
        report = self.env['account.report'].browse(options['report_id'])
        if self._tax_lazy_is_disabled():
            raise UserError(_('La expansión diferida del informe fiscal está desactivada.'))

        grouping = self._tax_lazy_report_grouping_mode(report)
        warnings = {}

        options_by_column_group = report._split_options_per_column_group(options)
        if grouping == 'tax_account':
            groupby_fields = [('src_tax', 'type_tax_use'), ('src_tax', 'id'), ('account', 'id')]
            comodels = [None, 'account.tax', 'account.account']
            tax_amount_hierarchy = self._read_generic_tax_report_amounts(
                report, options_by_column_group, groupby_fields)
        elif grouping == 'account_tax':
            groupby_fields = [('src_tax', 'type_tax_use'), ('account', 'id'), ('src_tax', 'id')]
            comodels = [None, 'account.account', 'account.tax']
            tax_amount_hierarchy = self._read_generic_tax_report_amounts(
                report, options_by_column_group, groupby_fields)
        else:
            groupby_fields = [('src_tax', 'type_tax_use'), ('src_tax', 'id')]
            comodels = [None, 'account.tax']
            tax_amount_hierarchy = self._read_generic_tax_report_amounts_no_tax_details(
                report, options, options_by_column_group)

        record_ids_gb = [set() for _dummy in groupby_fields]

        def populate_record_ids_gb_recursively(node, level=0):
            for k, v in node.items():
                if k:
                    record_ids_gb[level].add(k)
                    if v.get('children'):
                        populate_record_ids_gb_recursively(v['children'], level=level + 1)

        populate_record_ids_gb_recursively(tax_amount_hierarchy)

        sorting_map_list = []
        for i, comodel in enumerate(comodels):
            if comodel:
                records = self.env[comodel].with_context(active_test=False).search(
                    [('id', 'in', tuple(record_ids_gb[i]))])
                sorting_map = {r.id: (r, j) for j, r in enumerate(records)}
                sorting_map_list.append(sorting_map)
            else:
                selection = self.env['account.tax']._fields['type_tax_use']._description_selection(self.env)
                sorting_map_list.append({
                    v[0]: (v, j) for j, v in enumerate(selection) if v[0] in record_ids_gb[i]
                })

        parent = self._tax_lazy_parent_node(report, tax_amount_hierarchy, line_dict_id)
        if parent is None:
            raise UserError(_('No se pudo resolver la línea del informe fiscal al expandir.'))

        children = parent.get('children') or {}
        if not children:
            return {'lines': [], 'offset_increment': 0, 'has_more': False}

        parsed = report._parse_line_id(line_dict_id, markup_as_string=True)
        child_level_index = len(parsed) - 1
        type_tax_use = self._tax_lazy_type_tax_use_from_id(report, line_dict_id)

        lines = []
        self._tax_lazy_append_level(
            report, options, lines, sorting_map_list, groupby_fields,
            children, child_level_index, type_tax_use, line_dict_id, warnings,
        )
        return {
            'lines': lines,
            'offset_increment': len(lines),
            'has_more': False,
        }
