// Copyright (c) 2024, Akhilam Inc and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Aetas Current Stock Balance"] = {
	"filters": [
		{
			"fieldname":"as_on_date",
			"label": __("As On Date"),
			"fieldtype": "Date",
			"width": "60px"
		},
		{
			"fieldname":"serial_no",
			"label": __("Serial No"),
			"fieldtype": "Link",
			"options": "Serial No",
			"width": "80px"
		},
	],

	onload: function(report) {
		report.page.add_inner_button(__("Clear Filter"), function() {
			report.set_filter_value({
				as_on_date: "",
				serial_no: ""
			});
		});
	}
};
