const PRORATE_TO_LINES = true;
frappe.ui.form.on('Sales Invoice', {
    refresh: function (frm) {
         frm.set_query('custom_aetas_coupon_code', function() {
            return {
                filters: {
                    status: 'Active'
                }
            };
        });
        frappe.call({
            method: "aetas_customization.overrides.sales_invoice.check_user_has_naming_series",
            args: {
                "user": frappe.session.user
            },
            callback: function (r) {

                if (r.message > 0) {
                    frappe.call({
                        method: 'aetas_customization.overrides.sales_invoice.get_user_naming_series',
                        args: {
                            "user": frappe.session.user
                        },
                        freeze: true,
                        callback: (r) => {
                            if (r.message && r.message.length > 0) {
                                let final_options = r.message.map(series => series.naming_series).join("\n");

                                frm.set_df_property('naming_series', 'options', final_options);
                            }
                        },
                    });

                }
            }

        })
    },
    custom_aetas_coupon_code: function (frm) {
            frm.trigger("apply_coupon_code");
    },
    apply_coupon_code: function (frm) {
        if (!frm.doc.custom_aetas_coupon_code) {
            frm.set_value("discount_amount", 0);
            frm.refresh_field("discount_amount");
            return;
        }

        if (frm.doc.items.length == 0) {
            frappe.msgprint("Please add items to the invoice before applying the coupon code.");
            frm.set_value("custom_aetas_coupon_code", "");
            return;
        }


        if (frm.doc.items.filter(i => !i.item_code).length >= 1) {
            frappe.msgprint("One or more items do not have an item code. Please correct this before applying the coupon code.");
            frm.set_value("custom_aetas_coupon_code", "");
            return;
        }

        if (frm.doc.items.filter(i => i.base_amount == 0.0).length >= 1) {
            frappe.msgprint("One or more items having 0 amount. Please correct this before applying the coupon code.");
            frm.set_value("custom_aetas_coupon_code", "");
            return;
        }

        if (frm.doc.custom_aetas_coupon_code && frm.doc.items.length > 0) {
            frappe.call({
                method: "aetas_customization.aetas_customization.overrides.sales_invoice.validate_coupon_code",
                args: {
                    "coupon_code": frm.doc.custom_aetas_coupon_code,
                    "items": JSON.stringify(frm.doc.items.filter(i => i.base_amount > 0.0).map(i => ({
                        item_code: i.item_code,
                        base_amount: i.base_amount,
                    }))),
                    "grand_total": frm.doc.disable_rounded_total == 1 ? frm.doc.grand_total : frm.doc.rounded_total
                },
                freeze: true,
                freeze_message: "Validating coupon, please wait...",
                callback: function (res) {
                    if (!res || !res.message) {
                        // frappe.msgprint(__("No response from server"));
                        return;
                    }

                    const data = res.message;
                    // Log for debugging
                    console.log("coupon validation result:", data);

                    // Handle different statuses from server
                    if (data.status === "Invalid") {
                        frm.set_value("discount_amount", 0);
                        // frappe.msgprint({ title: __('Coupon'), message: data.message, indicator: 'red' });
                        // optionally clear coupon_code
                        // frm.set_value("coupon_code", null);
                        return;
                    }

                    if (data.status === "Inactive") {
                        frm.set_value("discount_amount", 0);
                        // frappe.msgprint({ title: __('Coupon'), message: data.message, indicator: 'orange' });
                        return;
                    }

                    if (data.status === "Not Applicable") {
                        frm.set_value("discount_amount", 0);
                        // frappe.msgprint({ title: __('Coupon'), message: data.message, indicator: 'orange' });
                        // you may still want to show breakdown:
                        console.log("breakdown:", data.breakdown);
                        return;
                    }

                    if (data.status === "Valid") {
                        const totalDiscount = Number(data.total_discount) || 0;
                        // 1) Save total discount to parent field (as requested)
                        frm.set_value("discount_amount", totalDiscount);
                        frm.refresh_field("discount_amount");
                        // Visual confirmation
                        // frappe.msgprint({ title: __('Coupon'), message: __("Coupon applied. Discount: {0}", [format_currency(frm.doc.discount_amount || 0)]), indicator: 'green' });
                        
                    } else {
                        // unknown status -> show message and dump response
                        frm.set_value("discount_amount", 0);
                        // frappe.msgprint({ title: __('Coupon'), message: __("Unhandled response: {0}", [JSON.stringify(data)]), indicator: 'orange' });
                    }

                }
            })
        }
    }
});

// frappe.ui.form.on('Sales Invoice Item', {
//     item_code: function (frm, cdt, cdn) {
//         const row = locals[cdt][cdn];
//         if (row.item_code && frm.doc.custom_aetas_coupon_code) {
//             frm.trigger("apply_coupon_code");
//         }
//     }
// });