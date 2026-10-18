frappe.ui.form.on('Journal Entry', {
    refresh: function (frm) {
        // ERPNext locks every field of a Reverse Journal Entry via
        // erpnext.journal_entry.lock_reversal_entry(). Unlock the accounts
        // child table so the reversal can be adjusted before submitting.
        if (frm.doc.reversal_of && frm.doc.docstatus === 0) {
            frm.set_df_property('accounts', 'read_only', 0);
            frm.refresh_field('accounts');
        }
    }
})
