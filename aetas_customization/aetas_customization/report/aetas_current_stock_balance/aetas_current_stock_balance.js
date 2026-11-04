// Copyright (c) 2024, Akhilam Inc and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Aetas Current Stock Balance"] = {
	"filters": [
		{
			"fieldname":"from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"width": "60px"
		},
		{
			"fieldname":"to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"width": "60px"
		},
		{
			"fieldname":"serial_no",
			"label": __("Serial No"),
			"fieldtype": "Link",
			"options": "Serial No",
			"width": "80px",
			"get_query": function() {
				return {
					filters: { "status": "Active" }
				};
			}
		},
	],

	onload: function(report) {
		report.page.add_inner_button(__("Clear Filter"), function() {
			report.set_filter_value({
				from_date: "",
				to_date: "",
				serial_no: ""
			});
		});
	}
};
