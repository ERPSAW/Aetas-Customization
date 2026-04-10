// Copyright (c) 2024, Akhilam Inc and contributors
// For license information, please see license.txt

frappe.ui.form.on('Aetas Advance Payment Receipt', {
	refresh: function(frm) {
		frm.set_query("cost_center",function(){
            return {
                "filters": {
                    "is_group":["=",0]
                }
            }
        });

		if (!frm.is_new() && frm.doc.status !== "Received") {
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
							method: "aetas_customization.aetas_customization.aetas_customization.doctype.aetas_advance_payment_receipt.aetas_advance_payment_receipt.generate_payment_link_for_apr",
							args: {
								apr_name: frm.doc.name,
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
    onload:function(frm){
        if(frm.doc.payment_entry && frm.doc.status === "Received"){
            frm.set_read_only()
        }
    }
});

