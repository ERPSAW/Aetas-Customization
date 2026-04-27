frappe.ui.form.on("Aetas Razorpay Activity Log", {
	refresh: function(frm) {
		if (frm.doc.direction === "Inbound" && frm.doc.processing_status === "Failed" && !frm.doc.__islocal) {
			frm.add_custom_button(__("Retry Processing"), function() {
				frm.call({
					method: "retry_processing",
					doc: frm.doc,
					callback: function(r) {
						if (!r.exc) {
							frappe.show_alert({
								message: __("Processing successful"),
								indicator: "green"
							});
							frm.reload_doc();
						}
					}
				});
			}).addClass("btn-primary");
		}
	}
});
