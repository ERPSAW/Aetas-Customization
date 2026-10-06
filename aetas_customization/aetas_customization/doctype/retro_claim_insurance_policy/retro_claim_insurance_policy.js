frappe.ui.form.on("Retro Claim Insurance Policy", {
    setup(frm) {
        frm.set_query("sales_invoice", () => {
            return {
                filters: {
                    docstatus: 1,
                    custom_apply_insurance: 0
                }
            };
        });
    },

    onload(frm) {
        if (!frm.doc.sales_invoice) {
            frm.set_df_property("boutique", "read_only", 1);
        }
    },

    sales_invoice(frm) {
        if (!frm.doc.sales_invoice) {
            frm.set_value("boutique", "");
            frm.set_df_property("boutique", "read_only", 0);
            frm.set_df_property("boutique", "reqd", 1);
            return;
        }

        frappe.db.get_value(
            "Sales Invoice",
            frm.doc.sales_invoice,
            ["customer", "posting_date", "custom_boutique"],
            (r) => {
                if (!r) {
                    return;
                }

                frm.set_value("customer", r.customer);
                frm.set_value("invoice_date", r.posting_date);

                if (r.custom_boutique) {
                    // Invoice already has a boutique -- lock it, no need to re-pick.
                    frm.set_value("boutique", r.custom_boutique);
                    frm.set_df_property("boutique", "read_only", 1);
                } else {
                    // Invoice has no boutique -- let the user pick one here.
                    frm.set_value("boutique", "");
                    frm.set_df_property("boutique", "read_only", 0);
                    frm.set_df_property("boutique", "reqd", 1);
                }
            }
        );
    },

    validate(frm) {
        if (!frm.doc.boutique) {
            frappe.throw(__("Please select a Boutique before submitting."));
        }
    },
});