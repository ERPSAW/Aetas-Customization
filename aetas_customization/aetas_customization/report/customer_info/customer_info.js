// Copyright (c) 2026, Akhilam Inc and contributors
// For license information, please see license.txt

frappe.query_reports["Customer Info"] = {
	"filters": [
		{
			"fieldname":"customer",
			"label": "Customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": "100px",
			get_query: function() {
				return {
					filters: {
						"disabled": 0,
					}
				}
			}
		},
		{
			"fieldname":"sales_person",
			"label": "Sales Person",
			"fieldtype": "Link",
			"options": "Sales Person",
			"width": "100px",

		}
	]
};
