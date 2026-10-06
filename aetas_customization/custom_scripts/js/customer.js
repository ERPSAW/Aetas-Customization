let exempt_sales_persons_cache = null;
let mandatory_unless_exempt_fields_cache = null;

frappe.ui.form.on("Customer", {
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
