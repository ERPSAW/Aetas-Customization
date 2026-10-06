// // Copyright (c) 2026, Akhilam Inc and contributors
// // For license information, please see license.txt

// frappe.query_reports["CRM Lead Sales Report"] = {
// 	filters: [
// 		{
// 			fieldname: "from_date",
// 			label: __("From Date"),
// 			fieldtype: "Date",
// 			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
// 		},
// 		{
// 			fieldname: "to_date",
// 			label: __("To Date"),
// 			fieldtype: "Date",
// 			default: frappe.datetime.get_today(),
// 		},
// 	],
// 	tree: true,
// 	name_field: "lead_id",
// 	parent_field: "parent_lead_id",
// 	initial_depth: 0,

// };

// frappe.query_reports["CRM Lead Sales Report"] = {
// 	filters: [
// 		{
// 			fieldname: "from_date",
// 			label: __("From Date"),
// 			fieldtype: "Date",
// 			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
// 		},
// 		{
// 			fieldname: "to_date",
// 			label: __("To Date"),
// 			fieldtype: "Date",
// 			default: frappe.datetime.get_today(),
// 		},
// 	],
// 	tree: true,
// 	name_field: "lead_id",
// 	parent_field: "parent_lead_id",
// 	initial_depth: 0,
// 	formatter: function (value, row, column, data, default_formatter) {
// 		value = default_formatter(value, row, column, data);

// 		if (column.fieldname === "mode_of_payment" && data && data.mode_of_payment) {
// 			return `<span class="mode-of-payment-cell" style="cursor:pointer; text-decoration: underline dotted;" 
// 				data-full-text="${frappe.utils.escape_html(data.mode_of_payment)}">${value}</span>`;
// 		}
// 		return value;
// 	},
// 	onload: function (report) {
// 		report.page.wrapper.on("click", ".mode-of-payment-cell", function () {
// 			frappe.msgprint({
// 				title: __("Mode of Payment"),
// 				message: $(this).attr("data-full-text"),
// 			});
// 		});
// 	},
// };

frappe.query_reports["CRM Lead Sales Report"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "MultiSelectList",
			get_data: function (txt) {
				return frappe.db.get_link_options("Customer", txt);
			},
		},
		{
			fieldname: "lead_status",
			label: __("Lead Status"),
			fieldtype: "MultiSelectList",
			get_data: function (txt) {
				return frappe.db.get_list("Lead", {
					filters: { workflow_state: ["like", `%${txt || ""}%`] },
					fields: ["distinct workflow_state as value"],
					limit: 20,
				}).then((r) => r.map((d) => ({ value: d.value, description: "" })).filter((d) => d.value));
			},
		},
		{
			fieldname: "lead_id",
			label: __("Lead ID"),
			fieldtype: "MultiSelectList",
			get_data: function (txt) {
				return frappe.db.get_link_options("Lead", txt);
			},
		},
		{
			fieldname: "invoice_number",
			label: __("Invoice Number"),
			fieldtype: "MultiSelectList",
			get_data: function (txt) {
				return frappe.db.get_link_options("Sales Invoice", txt);
			},
		},
	],
	tree: true,
	name_field: "lead_id",
	parent_field: "parent_lead_id",
	initial_depth: 1,
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname === "mode_of_payment" && data && data.mode_of_payment) {
			return `<span class="mode-of-payment-cell" style="cursor:pointer; text-decoration: underline dotted;" 
				data-full-text="${frappe.utils.escape_html(data.mode_of_payment)}">${value}</span>`;
		}
		return value;
	},
	onload: function (report) {
		report.page.wrapper.on("click", ".mode-of-payment-cell", function () {
			frappe.msgprint({
				title: __("Mode of Payment"),
				message: $(this).attr("data-full-text"),
			});
		});
	},
};