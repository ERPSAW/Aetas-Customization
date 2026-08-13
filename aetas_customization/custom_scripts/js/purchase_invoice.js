// Pull Cost Center / Warehouse / Address from Invoice Series Configuration as
// soon as the series is picked.  The same values are applied server side on
// save; doing it here just means the user sees them before saving.
function apply_series_defaults(frm) {
    if (frm.doc.docstatus !== 0 || !frm.doc.naming_series) return;

    frappe.call({
        method: "aetas_customization.aetas_customization.invoice_series_config.get_series_defaults",
        args: {
            document_type: frm.doc.doctype,
            naming_series: frm.doc.naming_series,
        },
        callback: function (r) {
            // Unconfigured series returns {} — leave the fields alone and let
            // the save-time validation be the thing that reports it.
            Object.entries(r.message || {}).forEach(([fieldname, value]) => {
                frm.set_value(fieldname, value);
            });
        },
    });
}

frappe.ui.form.on('Purchase Invoice', {
    naming_series: function (frm) {
        apply_series_defaults(frm);
    },

	type_of_stocks:function(frm){
        if(frm.doc.type_of_stocks === "Consignment"){
              frm.set_value("update_stock",0)
              frm.refresh_field("update_stock")
          } else{
            frm.set_value("update_stock",1)
            frm.refresh_field("update_stock")
        }
      },
    validate: function (frm) {
        frm.doc.items.forEach(function (item) {
            calculateMargin(frm, item.doctype, item.name);
        });
    }
})


frappe.ui.form.on('Purchase Invoice Item', {
    refresh(frm) {
        // Your code here
    },
    mrp:function (frm, cdt, cdn) {
        calculateMargin(frm, cdt, cdn);
    },
    rate:function (frm, cdt, cdn) {
        calculateMargin(frm, cdt, cdn);
    },

});

function calculateMargin(frm, cdt, cdn){
    var row = locals[cdt][cdn];
    var final_value;
    if (row.mrp !== 0) {
        final_value = (1 - (row.rate / row.mrp)) * 100;
    } else {
        final_value = 0;
    }
    frappe.model.set_value(cdt, cdn, 'margin_custom', final_value);
    refresh_field('items');

}

