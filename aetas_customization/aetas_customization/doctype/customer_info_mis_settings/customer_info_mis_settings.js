// Copyright (c) 2026, Akhilam Inc and contributors
// For license information, please see license.txt

frappe.ui.form.on("Customer Info MIS Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Send Now"), () => {
			if (frm.is_dirty()) {
				frappe.msgprint(__("Please save first."));
				return;
			}
			frappe.call({
				method: "aetas_customization.aetas_customization.api.customer_info_mis.send_customer_info_mis",
				freeze: true,
				freeze_message: __("Sending..."),
				callback: () => {
					frappe.show_alert({ message: __("Email queued"), indicator: "green" });
				},
			});
		});
	},
});
