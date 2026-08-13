// Copyright (c) 2026, Akhilam Inc and contributors
// For license information, please see license.txt

frappe.ui.form.on("Invoice Series Configuration", {
	document_type: function (frm) {
		frm.set_value("naming_series", "");
		set_naming_series_options(frm);
	},

	refresh: function (frm) {
		set_naming_series_options(frm);
	},

	billing_address: function (frm) {
		set_address_display(frm, "billing_address", "billing_address_display");
	},
});

// Mirror the Link field's address into its read-only display field, the same way
// Sales Invoice fills company_address_display from company_address.
function set_address_display(frm, address_field, display_field) {
	if (!frm.doc[address_field]) {
		frm.set_value(display_field, "");
		return;
	}

	frappe.call({
		method: "frappe.contacts.doctype.address.address.get_address_display",
		args: { address_dict: frm.doc[address_field] },
		callback: function (r) {
			frm.set_value(display_field, r.message || "");
		},
	});
}

// Turn the free-text Naming Series field into a picker of the series actually
// configured on the target doctype.  Typing it by hand invites typos like
// "CA./..." vs "CA/...", which silently break the lookup for a whole boutique.
function set_naming_series_options(frm) {
	if (!frm.doc.document_type) {
		frm.set_df_property("naming_series", "options", "");
		return;
	}

	frappe.call({
		method:
			"aetas_customization.aetas_customization.doctype.invoice_series_configuration" +
			".invoice_series_configuration.get_naming_series_options",
		args: { document_type: frm.doc.document_type },
		callback: function (r) {
			if (!r.message || !r.message.length) return;

			frm.set_df_property("naming_series", "fieldtype", "Autocomplete");
			frm.set_df_property("naming_series", "options", r.message.join("\n"));
			frm.refresh_field("naming_series");
		},
	});
}
