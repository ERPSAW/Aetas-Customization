// Copyright (c) 2025, Akhilam Inc and contributors
// For license information, please see license.txt



frappe.ui.form.on('AETAS Material Receipt Note', {
    refresh(frm) {
        if (frm.doc.location) {
            frm.add_custom_button('Get MRN Items', () => {
                frappe.call({
                    method: 'frappe.client.get_value',
                    args: {
                        doctype: 'Boutique',
                        filters: { name: frm.doc.location },
                        fieldname: 'boutique_warehouse'
                    },
                    callback(r) {
                        if (r.message?.boutique_warehouse) {
                            show_po_dialog(frm, r.message.boutique_warehouse);
                        } else {
                            frappe.msgprint('Warehouse not found for selected location');
                        }
                    }
                });
            });
        }
    },

	location:function(frm){
			frm.add_custom_button('Get MRN Items', () => {
                frappe.call({
                    method: 'frappe.client.get_value',
                    args: {
                        doctype: 'Boutique',
                        filters: { name: frm.doc.location },
                        fieldname: 'boutique_warehouse'
                    },
                    callback(r) {
                        if (r.message?.boutique_warehouse) {
                            show_po_dialog(frm, r.message.boutique_warehouse);
                        } else {
                            frappe.msgprint('Location not found for selected location');
                        }
                    }
                });
            });
		}
});

frappe.ui.form.on('MRN Item', {
	// qty and rate field change event
	mrn_item_add(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		row.amount = row.qty_ordered * row.rate;
		frm.refresh_field('mrn_item');
	},
	qty_ordered(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		row.amount = row.qty_ordered * row.rate;
		frm.refresh_field('mrn_item');
	},
	rate(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		row.amount = row.qty_ordered * row.rate;
		frm.refresh_field('mrn_item');
	}
})


function show_po_dialog(frm, warehouse) {
    const d = new frappe.ui.Dialog({
        title: 'Select Purchase Order',
        size: 'large',
        fields: [
            {
                label: 'Location',
                fieldname: 'location',
                fieldtype: 'Link',
                options: 'Boutique',
                default: frm.doc.location,
                onchange() {
                    reload_data(d);
                }
            },
            // {
            //     label: 'Supplier',
            //     fieldname: 'supplier',
            //     fieldtype: 'Link',
            //     options: 'Supplier',
            //     onchange() {
            //         reload_data(d);
            //     }
            // },
            {
                fieldtype: 'Column Break'
            },
            {
                label: 'Cost Center',
                fieldname: 'cost_center',
                fieldtype: 'Link',
                options: 'Cost Center',
                onchange() {
                    reload_data(d);
                }
            },
            { fieldtype: 'Section Break' },
            {
                label: 'Select Purchase Order Item',
                fieldname: 'select_po_item',
                fieldtype: 'Check',
                onchange() {
                    toggle_tables(d);
                    reload_data(d);
                }
            },
            { fieldtype: 'Section Break' },

            // ===== PO TABLE =====
            {
                label: 'Purchase Orders',
                fieldname: 'purchase_orders',
                fieldtype: 'Table',
                cannot_add_rows: true,
                cannot_delete_rows: true,
                in_place_edit: false,
                fields: [
                    {
                        fieldname: 'name',
                        fieldtype: 'Link',
                        label: 'Purchase Order',
                        options: 'Purchase Order',
                        in_list_view: 1,
						columns: 3,
                        read_only: 1
                    },
                    {
                        fieldname: 'supplier',
                        fieldtype: 'Link',
                        label: 'Supplier',
                        options: 'Supplier',
                        in_list_view: 1,
						columns: 2,
                        read_only: 1
                    }
                ]
            },

            // ===== ITEM TABLE =====
            {
                label: 'Purchase Order Items',
                fieldname: 'purchase_order_items',
                fieldtype: 'Table',
                hidden: 1,
                cannot_add_rows: true,
                cannot_delete_rows: true,
                in_place_edit: false,
                fields: [
                    {
                        fieldname: 'purchase_order',
                        fieldtype: 'Link',
                        label: 'Purchase Order',
                        options: 'Purchase Order',
                        in_list_view: 1,
						columns: 2,
                        read_only: 1
                    },
                    {
                        fieldname: 'item_code',
                        fieldtype: 'Link',
                        label: 'Item',
                        options: 'Item',
                        in_list_view: 1,
						columns: 2,
                        read_only: 1
                    },
                    {
                        fieldname: 'qty',
                        fieldtype: 'Float',
                        label: 'Qty',
                        in_list_view: 1,
						columns: 2,
                        read_only: 1
                    },
                    {
                        fieldname: 'amount',
                        fieldtype: 'Currency',
                        label: 'Amount',
                        in_list_view: 1,
						columns: 2,
                        read_only: 1
                    }
                ]
            }
        ],
        primary_action_label: 'Get Items',
        primary_action(values) {
            if (values.select_po_item) {
                handle_item_selection(frm, d);
            } else {
                handle_po_selection(frm, d);
            }
        }
    });

    toggle_tables(d);
    reload_data(d);
    d.show();
}

/* ---------------- HELPERS ---------------- */

function toggle_tables(dialog) {
    const select_items = dialog.get_value('select_po_item');

    dialog.set_df_property('purchase_orders', 'hidden', select_items);
    dialog.set_df_property('purchase_order_items', 'hidden', !select_items);
}

function reload_data(dialog) {
    const values = dialog.get_values();
    if (!values.location) return;

    frappe.call({
        method: 'frappe.client.get_value',
        args: {
            doctype: 'Boutique',
            filters: { name: values.location },
            fieldname: 'boutique_warehouse'
        },
        callback(r) {
            if (!r.message?.boutique_warehouse) return;

            frappe.call({
                method: 'aetas_customization.aetas_customization.doctype.aetas_material_receipt_note.aetas_material_receipt_note.get_purchase_orders',
                args: {
                    warehouse: r.message.boutique_warehouse,
                    supplier: values.supplier || '',
                    cost_center: values.cost_center || '',
                    select_po_items: values.select_po_item ? 1 : 0
                },
                callback(res) {
                    const table = values.select_po_item
                        ? dialog.fields_dict.purchase_order_items
                        : dialog.fields_dict.purchase_orders;

                    table.df.data = res.message || [];
                    table.grid.refresh();
                }
            });
        }
    });
}

function handle_item_selection(frm, dialog) {
    const rows = dialog.fields_dict.purchase_order_items.df.data;
    let selected = [];
    let po = null;
    let supplier = null;

    rows.forEach(r => {
        if (r.__checked) {
            if (!po) {
                po = r.purchase_order;
                supplier = r.supplier;   // must come from backend
            } else if (po !== r.purchase_order) {
                frappe.throw('Select items from only one Purchase Order');
            }
            selected.push(r);
        }
    });

    if (!selected.length) {
        frappe.msgprint('Please select at least one item');
        return;
    }

    // ✅ SET DOC LEVEL FIELDS (IMPORTANT)
    frm.set_value('po_number', po);
    frm.set_value('supplier_name', supplier);
	frm.set_value('location', dialog.get_value('location'));

    // Clear & add items
    frm.clear_table('mrn_item');

    selected.forEach(i => {
        let row = frm.add_child('mrn_item');
        row.item = i.item_code;
        row.uom = i.uom;
        row.qty_ordered = i.qty;
        row.rate = i.rate;
        row.amount = i.amount;
    });

    frm.refresh_field('mrn_item');
    dialog.hide();
}


function handle_po_selection(frm, dialog) {
    const rows = dialog.fields_dict.purchase_orders.df.data;
    const selected = rows.filter(r => r.__checked);

    if (!selected.length) {
        frappe.msgprint('Please select one Purchase Order');
        return;
    }

    if (selected.length > 1) {
        frappe.msgprint('Select only one Purchase Order');
        return;
    }

    frappe.call({
        method: 'aetas_customization.aetas_customization.doctype.aetas_material_receipt_note.aetas_material_receipt_note.get_mrn_items',
        args: {
            purchase_orders: [selected[0].name],
            select_po_items: 0
        },
        callback(r) {
            frm.clear_table('mrn_item');
            (r.message || []).forEach(i => {
                let row = frm.add_child('mrn_item');
                row.item = i.item_code;
                row.qty_ordered = i.quantity;
                row.rate = i.rate;
				row.uom = i.uom;
                row.amount = i.amount;
            });
            frm.refresh_field('mrn_item');
			frm.set_value('supplier_name', selected[0].supplier);
			frm.set_value('po_number', selected[0].name);
			frm.set_value('location', dialog.get_value('location'));
            dialog.hide();
        }
    });
}
