# Copyright (c) 2024, Akhilam Inc and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.accounts.report.financial_statements import (
	get_columns,
	get_data,
	get_filtered_list_for_consolidated_report,
	get_period_list,
)


def execute(filters=None):
	period_list = get_period_list(
		filters.from_fiscal_year,
		filters.to_fiscal_year,
		filters.period_start_date,
		filters.period_end_date,
		filters.filter_based_on,
		filters.periodicity,
		company=filters.company,
	)

	income = get_data(
		filters.company,
		"Income",
		"Credit",
		period_list,
		filters=filters,
		accumulated_values=filters.accumulated_values,
		ignore_closing_entries=True,
		ignore_accumulated_values_for_fy=True,
	)

	expense = get_data(
		filters.company,
		"Expense",
		"Debit",
		period_list,
		filters=filters,
		accumulated_values=filters.accumulated_values,
		ignore_closing_entries=True,
		ignore_accumulated_values_for_fy=True,
	)

	net_profit_loss = get_net_profit_loss(
		income, expense, period_list, filters.company, filters.presentation_currency
	)


	columns = get_columns(filters.periodicity, period_list, filters.accumulated_values, filters.company)

	fy_field_in_columns = ""
	for col in columns:
		if col.get("fieldtype") == "Currency":
			fy_field_in_columns = col.get("fieldname")
			break
	data = []

	if filters.periodicity == "Yearly" and filters.filter_based_on == "Fiscal Year" and filters.from_fiscal_year == filters.to_fiscal_year:
		cost_center = get_cost_conter(filters)

		for cc in cost_center:
			filters["cost_center"] = [cc]
			cc_wise_income = get_data(
				filters.company,
				"Income",
				"Credit",
				period_list,
				filters=filters,
				accumulated_values=filters.accumulated_values,
				ignore_closing_entries=True,
				ignore_accumulated_values_for_fy=True,
			)

			cc_wise_expense = get_data(
				filters.company,
				"Expense",
				"Debit",
				period_list,
				filters=filters,
				accumulated_values=filters.accumulated_values,
				ignore_closing_entries=True,
				ignore_accumulated_values_for_fy=True,
			)

			for cc_income in cc_wise_income:
				for fy_income in income:
					if fy_income.get("account") and cc_income.get("account") and fy_income.get("account") == cc_income.get("account"):
						fy_income[cc.lower().replace(" ","_").replace("-","_")] = cc_income[fy_field_in_columns]
						break

			for cc_expense in cc_wise_expense:
				for fy_expense in expense:
					if fy_expense.get("account") and cc_expense.get("account") and fy_expense.get("account") == cc_expense.get("account"):
						fy_expense[cc.lower().replace(" ","_").replace("-","_")] = cc_expense[fy_field_in_columns]
						break

			cc_net_profit_loss = get_net_profit_loss(
				cc_wise_income, cc_wise_expense, period_list, filters.company, filters.presentation_currency
			)
			net_profit_loss.update({ 
										cc.lower().replace(" ","_").replace("-","_"): cc_net_profit_loss[fy_field_in_columns]
			})

			columns.append({
						'fieldname': cc.lower().replace(" ","_").replace("-","_"),
						'label': cc,
						'fieldtype': 'Currency',
						'options': 'currency',
						'width': 150
			})

	data.extend(income or [])
	data.extend(expense or [])
	if net_profit_loss:
		data.append(net_profit_loss)

	chart = get_chart_data(filters, columns, income, expense, net_profit_loss)

	currency = filters.presentation_currency or frappe.get_cached_value(
		"Company", filters.company, "default_currency"
	)
	report_summary, primitive_summary = get_report_summary(
		period_list, filters.periodicity, income, expense, net_profit_loss, currency, filters
	)

	return columns, data, None, chart, report_summary, primitive_summary


def get_cost_conter(filters):
	cost_center_list = []
	if not filters.cost_center:
		cost_center_list = frappe.db.get_list("Cost Center",{"company": filters.company}, pluck="name")

	else:
		for row in filters.cost_center:
			if frappe.db.get_value("Cost Center",row, "is_group"):
				cost_center_list += frappe.db.get_list("Cost Center",{"parent_cost_center": row}, pluck="name")
			else:
				cost_center_list.append(row)

	return list(set(cost_center_list))


def get_report_summary(
	period_list, periodicity, income, expense, net_profit_loss, currency, filters, consolidated=False
):
	net_income, net_expense, net_profit = 0.0, 0.0, 0.0

	# from consolidated financial statement
	if filters.get("accumulated_in_group_company"):
		period_list = get_filtered_list_for_consolidated_report(filters, period_list)

	if filters.accumulated_values:
		# when 'accumulated_values' is enabled, periods have running balance.
		# so, last period will have the net amount.
		key = period_list[-1].key
		if income:
			net_income = income[-2].get(key)
		if expense:
			net_expense = expense[-2].get(key)
		if net_profit_loss:
			net_profit = net_profit_loss.get(key)
	else:
		for period in period_list:
			key = period if consolidated else period.key
			if income:
				net_income += income[-2].get(key)
			if expense:
				net_expense += expense[-2].get(key)
			if net_profit_loss:
				net_profit += net_profit_loss.get(key)

	if len(period_list) == 1 and periodicity == "Yearly":
		profit_label = _("Profit This Year")
		income_label = _("Total Income This Year")
		expense_label = _("Total Expense This Year")
	else:
		profit_label = _("Net Profit")
		income_label = _("Total Income")
		expense_label = _("Total Expense")

	return [
		{"value": net_income, "label": income_label, "datatype": "Currency", "currency": currency},
		{"type": "separator", "value": "-"},
		{"value": net_expense, "label": expense_label, "datatype": "Currency", "currency": currency},
		{"type": "separator", "value": "=", "color": "blue"},
		{
			"value": net_profit,
			"indicator": "Green" if net_profit > 0 else "Red",
			"label": profit_label,
			"datatype": "Currency",
			"currency": currency,
		},
	], net_profit


def get_net_profit_loss(income, expense, period_list, company, currency=None, consolidated=False):
	total = 0
	net_profit_loss = {
		"account_name": "'" + _("Profit for the year") + "'",
		"account": "'" + _("Profit for the year") + "'",
		"warn_if_negative": True,
		"currency": currency or frappe.get_cached_value("Company", company, "default_currency"),
	}

	has_value = False

	for period in period_list:
		key = period if consolidated else period.key
		total_income = flt(income[-2][key], 3) if income else 0
		total_expense = flt(expense[-2][key], 3) if expense else 0

		net_profit_loss[key] = total_income - total_expense

		if net_profit_loss[key]:
			has_value = True

		total += flt(net_profit_loss[key])
		net_profit_loss["total"] = total

	if has_value:
		return net_profit_loss


def get_chart_data(filters, columns, income, expense, net_profit_loss):
	labels = [d.get("label") for d in columns[2:]]

	income_data, expense_data, net_profit = [], [], []

	for p in columns[2:]:
		if income:
			income_data.append(income[-2].get(p.get("fieldname")))
		if expense:
			expense_data.append(expense[-2].get(p.get("fieldname")))
		if net_profit_loss:
			net_profit.append(net_profit_loss.get(p.get("fieldname")))

	datasets = []
	if income_data:
		datasets.append({"name": _("Income"), "values": income_data})
	if expense_data:
		datasets.append({"name": _("Expense"), "values": expense_data})
	if net_profit:
		datasets.append({"name": _("Net Profit/Loss"), "values": net_profit})

	chart = {"data": {"labels": labels, "datasets": datasets}}

	if not filters.accumulated_values:
		chart["type"] = "bar"
	else:
		chart["type"] = "line"

	chart["fieldtype"] = "Currency"

	return chart
