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

	# Fetching data for each cost center individually
	income, expense, cost_center_columns = get_cost_center_wise_data(
		filters, period_list
	)

	net_profit_loss = get_net_profit_loss(
		income, expense, period_list, filters.company, filters.presentation_currency
	)

	# Adding dynamic cost center columns to existing columns
	columns_chart = get_columns(
		filters.periodicity, period_list, filters.accumulated_values, filters.company
	)
	columns = cost_center_columns

	data = []

	# Consolidating all income, expense, and net profit data into the report
	data.extend(income or [])
	data.extend(expense or [])

	if net_profit_loss:
		data.append(net_profit_loss)

	chart = get_chart_data(filters, columns_chart, income, expense, net_profit_loss)

	currency = filters.presentation_currency or frappe.get_cached_value(
		"Company", filters.company, "default_currency"
	)
	report_summary, primitive_summary = get_report_summary(
		period_list,
		filters.periodicity,
		income,
		expense,
		net_profit_loss,
		currency,
		filters,
	)

	return columns, data, None, chart, report_summary, primitive_summary


def get_cost_center_wise_data(filters, period_list):
	"""Fetch cost center-wise income and expense data"""

	# Retrieve cost centers based on filter or all cost centers for the company
	cost_centers = get_cost_centers(filters)

	income_data = get_data(
		filters.company,
		"Income",
		"Credit",
		period_list,
		filters=filters,
		accumulated_values=filters.accumulated_values,
		ignore_closing_entries=True,
		ignore_accumulated_values_for_fy=True,
	)

	expense_data = get_data(
		filters.company,
		"Expense",
		"Debit",
		period_list,
		filters=filters,
		accumulated_values=filters.accumulated_values,
		ignore_closing_entries=True,
		ignore_accumulated_values_for_fy=True,
	)


	# Dynamic columns for each cost center to be added to the report
	cost_center_columns = get_columns(
	filters.periodicity, period_list, filters.accumulated_values, filters.company
	)

	for cc in cost_centers:
		filters["cost_center"] = [cc]

		# Fetching income and expense data for the current cost center
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

		# Iterate over each period to create a separate column for income and expense
		for period in period_list:
			for column in cost_center_columns:
				column_index = int()
				period_key = period.key if isinstance(period, dict) else period

				if column.get('fieldname') == period_key:
					column_index = cost_center_columns.index(column)
					cost_center_columns.insert(column_index + 1,
						{
							"fieldname": f"{cc.lower().replace(' ', '_').replace('-', '_')}_{period_key}",
							"label": f"{cc} ({period_key})",
							"fieldtype": "Currency",
							"options": "currency",
							"width": 200,
						})

					for cc_income in cc_wise_income:
						for row in income_data:
							if row.get("account") and cc_income.get("account") and row.get("account") == cc_income.get("account"):
								row[cost_center_columns[column_index + 1].get('fieldname')] = cc_income[period_key]
								break

					for cc_expense in cc_wise_expense:
						for row in expense_data:
							if row.get("account") and cc_expense.get("account") and row.get("account") == cc_expense.get("account"):
								row[cost_center_columns[column_index + 1].get('fieldname')] = cc_expense[period_key]
								break

	return income_data, expense_data, cost_center_columns



def get_cost_centers(filters):
	cost_center_list = []
	if not filters.cost_center:
		cost_center_list = frappe.db.get_list(
			"Cost Center", {"company": filters.company}, pluck="name"
		)
	else:
		for row in filters.cost_center:
			if frappe.db.get_value("Cost Center", row, "is_group"):
				cost_center_list += frappe.db.get_list(
					"Cost Center", {"parent_cost_center": row}, pluck="name"
				)
			else:
				cost_center_list.append(row)

	return list(set(cost_center_list))


def get_report_summary(
	period_list,
	periodicity,
	income,
	expense,
	net_profit_loss,
	currency,
	filters,
	consolidated=False,
	):
	net_income, net_expense, net_profit = 0.0, 0.0, 0.0

	# From consolidated financial statement
	if filters.get("accumulated_in_group_company"):
		period_list = get_filtered_list_for_consolidated_report(filters, period_list)

	if filters.accumulated_values:
		# When 'accumulated_values' is enabled, periods have running balance.
		# So, last period will have the net amount.
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
		{
			"value": net_income,
			"label": income_label,
			"datatype": "Currency",
			"currency": currency,
		},
		{"type": "separator", "value": "-"},
		{
			"value": net_expense,
			"label": expense_label,
			"datatype": "Currency",
			"currency": currency,
		},
		{"type": "separator", "value": "=", "color": "blue"},
		{
			"value": net_profit,
			"indicator": "Green" if net_profit > 0 else "Red",
			"label": profit_label,
			"datatype": "Currency",
			"currency": currency,
		},
	], net_profit


def get_net_profit_loss(
    income, expense, period_list, company, currency=None, consolidated=False
):
    total = 0
    net_profit_loss = {
        "account_name": "'" + _("Profit for the year") + "'",
        "account": "'" + _("Profit for the year") + "'",
        "warn_if_negative": True,
        "currency": currency
        or frappe.get_cached_value("Company", company, "default_currency"),
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
