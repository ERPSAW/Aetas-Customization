frappe.ui.form.on('Payment Entry', {
    refresh:function(frm){
        console.log("refresh event")
        frm.set_query("custom_advance_payment_receipt",function(){
            console.log("in function")
            return {
                query: 'aetas_customization.aetas_customization.overrides.payment_entry.custom_query',
                filters: {
                    "customer": frm.doc.party
                }
            }
        })
    }
})