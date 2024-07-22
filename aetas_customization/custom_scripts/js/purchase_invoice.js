frappe.ui.form.on('Purchase Invoice', {
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

