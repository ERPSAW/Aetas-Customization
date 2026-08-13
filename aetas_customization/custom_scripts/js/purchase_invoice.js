// Pull Cost Center / Warehouse / Address from Invoice Series Configuration as
// soon as the series is known.  The same values are applied server side on
// save; doing it here just means the user sees them before saving.
//
// `overwrite` is true only when the user actively changed the series — then the
// old series' values are stale and must be replaced.  On refresh it is false:
// the series was pre-filled from the field default rather than chosen, so we
// only fill blanks and never clobber what the user (or a mapped document) set.
function apply_series_defaults(frm, overwrite) {
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
                if (overwrite || !frm.doc[fieldname]) {
                    frm.set_value(fieldname, value);
                }
            });
        },
    });
}

// Keep every item row on the invoice's Cost Center.  The server does the same on
// validate and stays the authority; this just means the grid doesn't sit showing
// the company default (Main - AOT) until the user saves.
function propagate_cost_center_to_items(frm) {
    if (frm.doc.docstatus !== 0 || !frm.doc.cost_center) return;

    let changed = false;
    (frm.doc.items || []).forEach(row => {
        if (row.cost_center !== frm.doc.cost_center) {
            frappe.model.set_value(row.doctype, row.name, "cost_center", frm.doc.cost_center);
            changed = true;
        }
    });

    if (changed) {
        frm.refresh_field("items");
    }
}

frappe.ui.form.on('Purchase Invoice', {
    naming_series: function (frm) {
        apply_series_defaults(frm, true);
    },

    cost_center: function (frm) {
        propagate_cost_center_to_items(frm);
    },

    items_add: function (frm, cdt, cdn) {
        // A fresh row starts blank; fill it straight away.
        const row = locals[cdt][cdn];
        if (frm.doc.cost_center && row.cost_center !== frm.doc.cost_center) {
            frappe.model.set_value(cdt, cdn, "cost_center", frm.doc.cost_center);
        }
    },

    refresh: function (frm) {
        // The series is pre-filled from the field default on a new invoice, so
        // the naming_series event never fires — fill the blanks here instead.
        apply_series_defaults(frm, false);
        propagate_cost_center_to_items(frm);
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

