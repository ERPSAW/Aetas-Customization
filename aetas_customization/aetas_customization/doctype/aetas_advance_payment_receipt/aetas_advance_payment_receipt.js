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
							method: "aetas_customization.aetas_customization.doctype.aetas_advance_payment_receipt.aetas_advance_payment_receipt.generate_payment_link_for_apr",
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

		// Phase 5b: Link Payment to SI button
		// Show only if there are unlinked payment rows
		const unlinked_rows = (frm.doc.payment_details || []).filter(row => !row.sales_invoice);
		if (!frm.is_new() && unlinked_rows.length > 0) {
			frm.add_custom_button(__("Link Payment to SI"), function() {
				// Build list of unlinked payment rows
				const payment_options = unlinked_rows
					.map(row => `${row.name} | ${row.payment_entry} (${format_currency(row.amount, "INR")})`)
					.join("\n");
				
				frappe.prompt(
					[
						{
							fieldname: "payment_row",
							fieldtype: "Select",
							label: __("Select Payment"),
							options: payment_options,
							reqd: 1,
						},
						{
							fieldname: "sales_invoice",
							fieldtype: "Link",
							label: __("Sales Invoice"),
							options: "Sales Invoice",
							filters: {
								"customer": frm.doc.customer,
								"docstatus": 0,
							},
							reqd: 1,
						}
					],
					function(values) {
						// Find the selected row name
						const selected_row_name = (values.payment_row || "").split("|")[0].trim();
						const selected_row = unlinked_rows.find(row => row.name === selected_row_name);
						
						if (!selected_row) {
							frappe.msgprint(__("Payment row not found"));
							return;
						}
						
						frappe.call({
							method: "aetas_customization.aetas_customization.aetas_customization.doctype.aetas_advance_payment_receipt.aetas_advance_payment_receipt.link_payment_to_si",
							args: {
								apr_name: frm.doc.name,
								child_row_name: selected_row.name,
								si_name: values.sales_invoice,
							},
							freeze: true,
							freeze_message: __("Linking payment…"),
							callback: function(r) {
								if (r.message && r.message.status === "success") {
									frappe.msgprint(r.message.message);
									frm.reload_doc();
								}
							},
						});
					},
					__("Link Payment to Sales Invoice"),
					__("Link")
				);
			}, __("Advanced"));
		}
	},
    onload:function(frm){
        if(frm.doc.payment_entry && frm.doc.status === "Received"){
            frm.set_read_only()
        }
    }
});

