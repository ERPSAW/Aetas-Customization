// Copyright (c) 2023, Akhilam Inc and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Customer Acquisition and Loyalty Summarize"] = {
	"filters": [
		{
			"fieldname": "view_type",
			"label": __("View Type"),
			"fieldtype": "Select",
			"options": ["Monthly", "Territory Wise"],
			"default": "Monthly",
			"reqd": 1
		},
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
		}
	],
	onload: function(report) {
		console.log(report.get_filter_values())
		report.page.add_inner_button(__("New Customers"), function() {
			frappe.set_route("query-report","Customer Acquisition and Loyalty Details", { "report_type": "New","from_date":report.get_filter_values()['from_date'],"to_date":report.get_filter_values()['to_date'] });
		});

		report.page.add_inner_button(__("Repeated Customers"), function() {
			frappe.set_route("query-report","Customer Acquisition and Loyalty Details", { "report_type": "Repeated","from_date":report.get_filter_values()['from_date'],"to_date":report.get_filter_values()['to_date'] });
		});
	},
	'formatter': function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (data && data.bold) {
			value = value.bold();
		}
		return value;
	}
};
