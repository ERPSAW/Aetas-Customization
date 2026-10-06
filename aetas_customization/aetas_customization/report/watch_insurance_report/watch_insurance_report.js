// Copyright (c) 2026, Aetas Retail and contributors
// For license information, please see license.txt

frappe.query_reports["Watch Insurance Report"] = {
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
			fieldname: "store",
			label: __("Store"),
			fieldtype: "Data",
			// TODO: change to "Link" with the correct options (link doctype)
			// once we confirm what custom_boutique on Sales Invoice points to.
		},
		{
			fieldname: "brand",
			label: __("Brand"),
			fieldtype: "Data",
		},
		{
			fieldname: "certificate_sent",
			label: __("Certificate Sent"),
			fieldtype: "Select",
			options: ["", "Yes", "No", "Pending"],
		},
	],
	    formatter: function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        // Bold total_funded / opening premium balance
        if (
            column.fieldname === "premium_balance" &&
            data &&
            data.certificate_no === null
        ) {
            value = `<b>${value}</b>`;
        }

        return value;
    },
};