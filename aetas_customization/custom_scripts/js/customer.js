let exempt_sales_persons_cache = null;
let mandatory_unless_exempt_fields_cache = null;

frappe.ui.form.on("Customer", {
    refresh: function(frm) {
        if (frm.doc.__islocal) return;

        frm.add_custom_button("Validate Customer", function() {
            open_validation_dialog(frm);
        });
    },
        custom_sales_person: function(frm) {
        toggle_exempt_mandatory(frm);
        }
});

function toggle_exempt_mandatory(frm) {
    Promise.all([fetch_exempt_sales_persons(), fetch_mandatory_unless_exempt_fields()]).then(function(results) {
        const exempt_list = results[0];
        const mandatory_fields = results[1];
        const is_exempt = exempt_list.includes(frm.doc.custom_sales_person);

        mandatory_fields.forEach(function(fieldname) {
            if (!frm.fields_dict[fieldname]) return;
            frm.set_df_property(fieldname, "reqd", is_exempt ? 0 : 1);
        });

        frm.refresh_fields();
    });
}

function fetch_exempt_sales_persons() {
    if (exempt_sales_persons_cache) return Promise.resolve(exempt_sales_persons_cache);
    return frappe.call({
        method: "aetas_customization.aetas_customization.overrides.customer.get_exempt_sales_persons"
    }).then(function(r) {
        exempt_sales_persons_cache = r.message || [];
        return exempt_sales_persons_cache;
    });
}

function fetch_mandatory_unless_exempt_fields() {
    if (mandatory_unless_exempt_fields_cache) return Promise.resolve(mandatory_unless_exempt_fields_cache);
    return frappe.call({
        method: "aetas_customization.aetas_customization.overrides.customer.get_mandatory_unless_exempt_fields"
    }).then(function(r) {
        mandatory_unless_exempt_fields_cache = r.message || [];
        return mandatory_unless_exempt_fields_cache;
    });
}

function open_validation_dialog(frm) {
    frappe.call({
        method: "aetas_customization.aetas_customization.overrides.customer.get_customer_validation_data",
        args: {
            customer: frm.doc.name
        },
        callback: function(r) {
            if (!r.message || !r.message.length) {
                frappe.msgprint("No validation fields configured in Aetas Custom Setting.");
                return;
            }
            render_validation_dialog(frm, r.message);
        }
    });
}

function render_validation_dialog(frm, fields) {
    let dialog_fields = [];
    let dialog; 

    fields.forEach((row, idx) => {
        dialog_fields.push({
            fieldtype: "Section Break",
            label: row.field_name + " *"  
        });
        dialog_fields.push({
            fieldtype: "Check",
            fieldname: "yes_" + idx,
            label: "Yes",
            default: row.yes,
            onchange: function() {
                if (dialog.get_value("yes_" + idx)) {
                    dialog.set_value("no_" + idx, 0);
                }
            }
        });
        dialog_fields.push({
            fieldtype: "Column Break"
        });
        dialog_fields.push({
            fieldtype: "Check",
            fieldname: "no_" + idx,
            label: "No",
            default: row.no,
            onchange: function() {
                if (dialog.get_value("no_" + idx)) {
                    dialog.set_value("yes_" + idx, 0);
                }
            }
        });
    });

    dialog = new frappe.ui.Dialog({
        title: "Validate Customer",
        fields: dialog_fields,
        primary_action_label: "Validate",
        primary_action: function(values) {

            // mandatory check: every field must have exactly one of yes/no ticked
            for (let idx = 0; idx < fields.length; idx++) {
                let yes = values["yes_" + idx] ? 1 : 0;
                let no = values["no_" + idx] ? 1 : 0;
                if (!yes && !no) {
                    frappe.msgprint(`Please mark Yes or No for "${fields[idx].field_name}"`);
                    return; // stop, don't call server
                }
            }

            let payload = fields.map((row, idx) => {
                return {
                    field_name: row.field_name,
                    yes: values["yes_" + idx] ? 1 : 0,
                    no: values["no_" + idx] ? 1 : 0
                };
            });

            frappe.call({
                method: "aetas_customization.aetas_customization.overrides.customer.validate_customer_fields",
                args: {
                    customer: frm.doc.name,
                    fields: payload
                },
                freeze: true,
                freeze_message: "Validating...",
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert({ message: "Customer validated successfully", indicator: "green" });
                        dialog.hide();
                        frm.reload_doc();
                    }
                }
            });
        }
    });

    dialog.show();
}