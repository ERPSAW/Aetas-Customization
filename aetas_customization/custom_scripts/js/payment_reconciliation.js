frappe.ui.form.on("Payment Reconciliation", {
	party_type:function(frm){
		let payment_recon_inv = {
			"Payment Reconciliation Invoice": [
					{fieldname: "invoice_type", columns: 3 },
					{fieldname: "invoice_number", columns: 3 },
					{fieldname: "invoice_date", columns: 2 },
					{fieldname: "outstanding_amount", columns: 2 },
				]
		}
		frappe.model.user_settings.save("Payment Reconciliation", 'GridView', payment_recon_inv).then((r) => {
			frappe.model.user_settings["Payment Reconciliation"] = r.message || r;
			 cur_frm.fields_dict["invoices"].grid.reset_grid()
		});
		if(frm.doc.party_type === "Supplier"){
			let payment_recon_inv = {
				"Payment Reconciliation Invoice": [
						{fieldname: "invoice_type", columns: 2 },
						{fieldname: "invoice_number", columns: 2 },
						{fieldname: "custom_bill_no", columns: 2 },
						{fieldname: "invoice_date", columns: 2 },
						{fieldname: "outstanding_amount", columns: 2 },
					]
			}
			frappe.model.user_settings.save("Payment Reconciliation", 'GridView', payment_recon_inv).then((r) => {
				frappe.model.user_settings["Payment Reconciliation"] = r.message || r;
				 cur_frm.fields_dict["invoices"].grid.reset_grid()
			});
		}
	}
});