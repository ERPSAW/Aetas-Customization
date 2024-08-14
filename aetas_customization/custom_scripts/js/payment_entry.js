frappe.ui.form.on('Payment Entry', {
    refresh:function(frm){
        frm.set_query("custom_advance_payment_receipt",function(){
            return {
                query: 'aetas_customization.aetas_customization.overrides.payment_entry.custom_query',
                filters: {
                    "customer": frm.doc.party
                }
            }
        })
    },
    custom_advance_payment_receipt:async function(frm){
        let amount = await frappe.db.get_value('Aetas Advance Payment Receipt', frm.doc.custom_advance_payment_receipt, 'paid_amount')
        frm.set_value('paid_amount', amount.message.paid_amount);
        frm.refresh_field('paid_amount')

    }
})