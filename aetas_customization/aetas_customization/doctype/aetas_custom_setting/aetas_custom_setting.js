// // Copyright (c) 2024, Akhilam Inc and contributors
// // For license information, please see license.txt

// frappe.ui.form.on('Aetas Custom Setting', {
// 	// refresh: function(frm) {

// 	// }
// });


// aetas_custom_setting.js
console.log("script loaded")
frappe.ui.form.on("Aetas Custom Setting", {
    refresh: function(frm) {
        set_fieldname_options(frm);
    }
});

function set_fieldname_options(frm) {
    frappe.model.with_doctype("Customer", () => {
        let meta = frappe.get_meta("Customer");
        let skip_types = ["Section Break", "Column Break", "Tab Break", "HTML", "Button", "Table"];
        let options = meta.fields
            .filter(df => !skip_types.includes(df.fieldtype) && df.label)
            .map(df => df.label);

        frm.fields_dict["customer_validation_field"].grid.update_docfield_property(
            "field_name", "options", options.join("\n")
        );
    });
}

// Mutual exclusivity: Yes/No checkboxes in child table rows
frappe.ui.form.on("Aetas Customer Validation Field", {
    yes: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.yes) frappe.model.set_value(cdt, cdn, "no", 0);
    },
    no: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.no) frappe.model.set_value(cdt, cdn, "yes", 0);
    }
});