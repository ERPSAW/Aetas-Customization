// Copyright (c) 2025, Akhilam Inc and contributors
// For license information, please see license.txt

frappe.ui.form.on('AETAS Gate Pass', {
	// refresh: function(frm) {

	// }
	sender_boutique:function(frm){
		if(frm.doc.sender_boutique){
			frappe.db.get_value("Boutique", frm.doc.sender_boutique, "boutique_location_display", function(r){
				if(r.boutique_location_display){
					let location_display = r.boutique_location_display.replace(/<br>/g, '\n').replace(/<\/?[^>]+(>|$)/g, "");
					console.log(location_display);
					frm.set_value("sender_or_issuers_details", location_display);
				}
				else{
					frappe.msgprint(__("Boutique Location not found"));
					frm.set_value("sender_or_issuers_details", "");
				}
			});
			  
		}

	},
	destination:function(frm){
		if(frm.doc.destination){
			frappe.db.get_value("Boutique", frm.doc.destination, "boutique_location_display", function(r){
				if(r.boutique_location_display){
					let location_display = r.boutique_location_display.replace(/<br>/g, '\n').replace(/<\/?[^>]+(>|$)/g, "");
					console.log(location_display);
					frm.set_value("recipient_details", location_display);
				}
				else{
					frappe.msgprint(__("Boutique Location not found"));
					frm.set_value("recipient_details", "");
				}
			});
			  
		}
	}
});
