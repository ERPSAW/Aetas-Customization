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
	]
};
