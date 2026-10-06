// Copyright (c) 2026, Akhilam Inc and contributors
// For license information, please see license.txt

frappe.query_reports["Member Validation Report"] = {
    filters: [
        {
            fieldname: "customer",
            label: "Customer",
            fieldtype: "Link",
            options: "Customer",
            width: "100px",
            get_query: function () {
                return {
                    filters: {
                        disabled: 0
                    }
                };
            }
        },
		        {
            fieldname: "current_tier",
            label: "Current Tier",
            fieldtype: "Link",
            options: "Client Tiers",
            width: "100px"
        },
        {
            fieldname: "boutique",
            label: "Enrollment Store Location",
            fieldtype: "Link",
            options: "Boutique",
            width: "150px"
        }
    ]
};