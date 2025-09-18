// Copyright (c) 2025, Akhilam Inc and contributors
// For license information, please see license.txt

frappe.ui.form.on("AETAS Coupon Configuration", {
	
    // whenever parent item_group changes, update existing child rows
    item_group: function(frm) {
        if (!frm.doc.item_group) return;
        if (frm.doc.discount_configuration && frm.doc.discount_configuration.length) {
            frm.doc.discount_configuration.forEach(function(row) {
                row.item_group = frm.doc.item_group;
            });
            refresh_field("discount_configuration");
        }
    }
});

// Child doctype name (change "AETAS Coupon Configuration Item" to your child doctype name)
frappe.ui.form.on("Item Group Coupon Configuration", {
    // before a new row is inserted into child table, set its item_group
    discount_configuration_add: function(frm, cdt, cdn) {
		console.log("Adding new row to discount_configuration");
		
        const row = locals[cdt][cdn];
        if (frm.doc.item_group) {
            row.item_group = frm.doc.item_group;
            // update the grid display
            refresh_field("discount_configuration");
        }
    },
});