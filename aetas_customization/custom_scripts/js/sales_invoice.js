frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        frappe.call({
            method: "aetas_customization.overrides.sales_invoice.check_user_has_naming_series",
            args: {
                "user": frappe.session.user
            },
            callback: function(r) {
        
                if(r.message > 0){
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
    
});
