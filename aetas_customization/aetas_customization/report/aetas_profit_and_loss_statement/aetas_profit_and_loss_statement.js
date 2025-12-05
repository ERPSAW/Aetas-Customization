// Copyright (c) 2024, Akhilam Inc and contributors
// For license information, please see license.txt


// frappe.require("assets/erpnext/js/financial_statements.js", function () {
// 	frappe.query_reports["Aetas Profit and Loss Statement"] = $.extend({}, erpnext.financial_statements);

// 	erpnext.utils.add_dimensions("Aetas Profit and Loss Statement", 10);

// 	frappe.query_reports["Aetas Profit and Loss Statement"]["filters"].push({
// 		fieldname: "selected_view",
// 		label: __("Select View"),
// 		fieldtype: "Select",
// 		options: [
// 			{ value: "Report", label: __("Report View") },
// 			{ value: "Growth", label: __("Growth View") },
// 			{ value: "Margin", label: __("Margin View") },
// 		],
// 		default: "Report",
// 		reqd: 1,
// 	});

// 	frappe.query_reports["Aetas Profit and Loss Statement"]["filters"].push({
// 		fieldname: "include_default_book_entries",
// 		label: __("Include Default Book Entries"),
// 		fieldtype: "Check",
// 		default: 1,
// 	});
// });

// frappe.query_reports["Aetas Profit and Loss Statement"]["filters"].push({
// 	fieldname: "include_default_book_entries",
// 	label: __("Include Default FB Entries"),
// 	fieldtype: "Check",
// 	default: 1,
// });


frappe.query_reports["Aetas Profit and Loss Statement"] = $.extend({}, erpnext.financial_statements);

erpnext.utils.add_dimensions("Aetas Profit and Loss Statement", 10);

frappe.query_reports["Aetas Profit and Loss Statement"]["filters"].push(
	{
		fieldname: "selected_view",
		label: __("Select View"),
		fieldtype: "Select",
		options: [
			{ value: "Report", label: __("Report View") },
			{ value: "Growth", label: __("Growth View") },
			{ value: "Margin", label: __("Margin View") },
		],
		default: "Report",
		reqd: 1,
	},
	{
		fieldname: "accumulated_values",
		label: __("Accumulated Values"),
		fieldtype: "Check",
		default: 1,
	},
	{
		fieldname: "include_default_book_entries",
		label: __("Include Default FB Entries"),
		fieldtype: "Check",
		default: 1,
	},
	{
		fieldname: "show_zero_values",
		label: __("Show zero values"),
		fieldtype: "Check",
	}
);
