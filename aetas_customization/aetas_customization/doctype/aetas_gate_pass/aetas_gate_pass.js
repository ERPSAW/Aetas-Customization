// Copyright (c) 2025, Akhilam Inc and contributors
// For license information, please see license.txt

frappe.ui.form.on('AETAS Gate Pass', {
	refresh: function(frm) {
		if(frm.doc.docstatus === 1 && !frm.doc.is_received){ 
			frm.add_custom_button("Received", function() {
				let d = new frappe.ui.Dialog({
					title: 'Receiver details',
					fields: [
						{
							label: 'Receiver Name',
							fieldname: 'receiver_name',
							fieldtype: 'Data'
						},
						
					],
					size: 'small', // small, large, extra-large 
					primary_action_label: 'Submit',
					primary_action(values) {
						if(!values.receiver_name){
							frappe.msgprint(__("Please enter receiver name"));
							return;
						}
						frm.set_value("received_by", values.receiver_name);
						frm.set_value("is_received", 1);
						frm.set_value("date_of_received", frappe.datetime.now_datetime());
						frm.refresh_field("is_received","received_by","date_of_received");
						if(frm.doc.docstatus === 1 ){
							frm.save('Update');
						}else{
							frm.save()
						}
						d.hide();
					}
				});
				
				d.show();
			});
		}
	},
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
