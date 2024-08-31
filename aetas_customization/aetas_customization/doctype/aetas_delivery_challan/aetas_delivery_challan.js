// Copyright (c) 2024, Akhilam Inc and contributors
// For license information, please see license.txt


frappe.ui.form.on('Aetas Delivery Challan', {
	refresh: function(frm) {
		frm.set_query('supplier_address', () => {
			return {
				filters: {
					'link_doctype':'Supplier',
					'link_name': frm.doc.supplier
				}
			}
		})

		frm.set_query('warehouse', 'items', () => {
			return {
				filters: {
					is_group: 0,
					custom_is_reserved:0
				}
			}
		})
		
	},
	supplier_address:function(frm){
		if(frm.doc.supplier_address){
			return frm.call({
			method: "frappe.contacts.doctype.address.address.get_address_display",
			args: {
			   "address_dict": frm.doc.supplier_address
			},
			callback: function(r) {
			  if(r.message)
				  frm.set_value("supplier_address_display", r.message);
				}
		   });
		  }
		  else{
			  frm.set_value("supplier_address_display", "");
		  }
	}
});

frappe.ui.form.on('Aetas Delivery Challan Item', {
	rate:function(frm,cdt,cdn){
        let row = locals[cdt][cdn]
        row.amount = row.qty * row.rate

        frm.refresh_field("items")
    }
	
});