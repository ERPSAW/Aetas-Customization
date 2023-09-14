// Copyright (c) 2023, Akhilam Inc and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Customer Acquisition and Loyalty Details"] = {
	"filters": [
		{
			"fieldname":"company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
			"reqd": 1
		},
		{
			"fieldname":"from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.defaults.get_user_default("year_start_date"),
			"reqd": 1
		},
		{
			"fieldname":"to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.defaults.get_user_default("year_end_date"),
			"reqd": 1
		},
		{
			"fieldname":"report_type",
			"label": __("Report Type"),
			"fieldtype": "Select",
			"options": 'New\nRepeated',
			"default": "New",
		}
	]
};
