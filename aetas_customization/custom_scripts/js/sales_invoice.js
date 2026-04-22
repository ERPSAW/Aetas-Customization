const PRORATE_TO_LINES = true;

function get_existing_advance_keys(frm) {
	return new Set((frm.doc.advances || [])
		.filter(row => row.reference_type && row.reference_name)
		.map(row => `${row.reference_type}::${row.reference_name}`));
}

function apply_customer_advances_to_form(frm, rows, targetAmount) {
	let remaining = frappe.utils.flt(targetAmount || 0);
	if (remaining <= 0) {
		return 0;
	}

	const existingKeys = get_existing_advance_keys(frm);
	let applied = 0;

	(rows || []).forEach(row => {
		if (remaining <= 0) return;
		const paymentEntry = row.payment_entry;
		const amount = frappe.utils.flt(row.amount || 0);
		if (!paymentEntry || amount <= 0) return;

		const key = `Payment Entry::${paymentEntry}`;
		if (existingKeys.has(key)) return;

		const allocate = Math.min(amount, remaining);
		frm.add_child("advances", {
			reference_type: "Payment Entry",
			reference_name: paymentEntry,
			advance_amount: amount,
			allocated_amount: allocate,
		});

		existingKeys.add(key);
		applied += allocate;
		remaining -= allocate;
	});

	if (applied > 0) {
		frm.refresh_field("advances");
	}

	return applied;
}

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

        });

		// Phase 5 Sub-flow A: Advance adjustment prompt on SI creation.
		if (frm.is_new() && frm.doc.customer && !frm.__advance_prompt_done) {
			frm.__advance_prompt_done = true;
			frappe.call({
				method: "aetas_customization.aetas_customization.overrides.sales_invoice.get_customer_advance_balance",
				args: {
					customer: frm.doc.customer
				},
				callback: function(r) {
					if (r.message && r.message.balance > 0) {
						const advance_balance = frappe.utils.flt(r.message.balance || 0);
						const invoiceTotal = frappe.utils.flt(frm.doc.grand_total || frm.doc.rounded_total || 0);
						const maxFullAdjust = invoiceTotal > 0 ? Math.min(advance_balance, invoiceTotal) : advance_balance;
						frappe.prompt(
							[{
								fieldname: "adjustment_option",
								fieldtype: "Select",
								label: __("Advance Adjustment"),
								options: "Skip\nFull Adjust\nPartial Adjust",
								default: "Skip",
								reqd: 1,
							}],
							function(values) {
								let adjustment_amount = 0;

								if (values.adjustment_option === "Full Adjust") {
									adjustment_amount = maxFullAdjust;
									frappe.call({
										method: "aetas_customization.aetas_customization.overrides.sales_invoice.get_unlinked_customer_advances",
										args: {
											customer: frm.doc.customer
										},
										callback: function(r) {
											const applied = apply_customer_advances_to_form(frm, r.message || [], adjustment_amount);
											if (applied > 0) {
												frappe.msgprint(__("Advance of {0} applied", [format_currency(applied, "INR")]));
											}
										}
									});
								} else if (values.adjustment_option === "Partial Adjust") {
									frappe.prompt(
										[{
											fieldname: "amount",
											fieldtype: "Currency",
											label: __("Adjustment Amount"),
											description: __("Available advance: {0}", [format_currency(advance_balance, "INR")]),
											reqd: 1,
										}],
										function(partial_values) {
											const partialAmount = frappe.utils.flt(partial_values.amount || 0);
											if (partialAmount <= 0) {
												frappe.msgprint(__("Amount must be greater than zero"));
												return;
											}
											if (partialAmount > advance_balance) {
												frappe.msgprint(__("Amount exceeds available advance"));
												return;
											}
											if (invoiceTotal > 0 && partialAmount > invoiceTotal) {
												frappe.msgprint(__("Amount exceeds invoice total"));
												return;
											}
											frappe.call({
												method: "aetas_customization.aetas_customization.overrides.sales_invoice.get_unlinked_customer_advances",
												args: {
													customer: frm.doc.customer
												},
												callback: function(r) {
													const applied = apply_customer_advances_to_form(frm, r.message || [], partialAmount);
													if (applied > 0) {
														frappe.msgprint(__("Advance of {0} applied", [format_currency(applied, "INR")]));
													}
												}
											});
										},
										__("Enter Adjustment Amount"),
										__("Apply")
									);
								}
								// else: Skip — do nothing
							},
							__("Advance Adjustment Available"),
							__("Continue")
						);
					}
				}
			});
		}

		// Phase 5 Sub-flow B: auto-populate SI advances when opening existing SI.
		if (!frm.is_new() && frm.doc.docstatus === 0 && frm.doc.customer && !frm.__si_advances_autofill_done) {
			frm.__si_advances_autofill_done = true;
			frappe.call({
				method: "aetas_customization.aetas_customization.overrides.sales_invoice.get_advances_received_for_si",
				args: {
					si_name: frm.doc.name
				},
				callback: function(r) {
					if (r.message && r.message.length > 0) {
						const existingKeys = get_existing_advance_keys(frm);
						let added = 0;
						
						r.message.forEach(adv_row => {
							const key = `Payment Entry::${adv_row.payment_entry}`;
							if (existingKeys.has(key)) return;
							frm.add_child("advances", {
								reference_type: "Payment Entry",
								reference_name: adv_row.payment_entry,
								advance_amount: adv_row.amount,
								allocated_amount: 0,
							});
							existingKeys.add(key);
							added += 1;
						});
						
						if (added > 0) {
							frm.refresh_field("advances");
							frappe.msgprint(__("Advances populated from customer payment history"));
						}
					}
				}
			});
		}

		if (!frm.is_new() && frm.doc.docstatus === 1 && frm.doc.outstanding_amount > 0) {
			frm.add_custom_button(__("Generate Payment Link"), function() {
				frappe.prompt(
					[{
						fieldname: "amount",
						fieldtype: "Currency",
						label: __("Amount (INR)"),
						reqd: 1,
					}],
					function(values) {
						frappe.call({
							method: "aetas_customization.aetas_customization.overrides.sales_invoice.generate_payment_link_for_invoice",
							args: {
								si_name: frm.doc.name,
								amount: values.amount,
							},
							freeze: true,
							freeze_message: __("Generating payment link…"),
							callback: function(r) {
								if (r.message && r.message.link_url) {
									frappe.msgprint({
										title: __("Payment Link Generated"),
										message: __(
											"<b>Link:</b> <a href='{0}' target='_blank'>{0}</a><br>"
											+ "<b>Amount:</b> {1}<br>"
											+ "<b>Expires:</b> {2}",
											[
												r.message.link_url,
												format_currency(r.message.amount, "INR"),
												r.message.expire_by || "—",
											]
										),
										indicator: "green",
									});
								}
							},
						});
					},
					__("Generate Payment Link"),
					__("Generate")
				);
			}, __("Razorpay"));
		}
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