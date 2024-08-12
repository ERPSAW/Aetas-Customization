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
        })
	}
});
