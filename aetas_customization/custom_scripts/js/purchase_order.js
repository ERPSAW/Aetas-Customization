frappe.ui.form.on('Purchase Order', {
	refresh:function(frm){
        // your code here
    }
})

frappe.ui.form.on('Purchase Order Item', {
	item_code:function(frm,cdt,cdn){
        var row = locals[cdt][cdn];
        if(row.item_code){
            frappe.call({
                method: 'aetas_customization.aetas_customization.overrides.warehouse.get_total_stock',
                args: {
                    item_code: row.item_code
                },
                callback: function(r) {   
                    var html = `
                    <style>
                        table {
                            width: 100%;
                            border-collapse: collapse;
                        }
                        th, td {
                            border: 1px solid #ddd;
                            padding: 8px;
                            text-align: left;
                        }
                        th {
                            background-color: #f2f2f2;
                        }
                        tr:nth-child(even) {
                            background-color: #f9f9f9;
                        }
                        tr:hover {
                            background-color: #ddd;
                        }
                    </style>
                    <table>
                        <tr>
                            <th>Item Code</th>
                            <th>Total Balance Quantity</th>
                        </tr>
                        <tr>
                            <td>${row.item_code}</td>
                            <td>${r.message}</td>
                        </tr>
                    </table>`;

                    html += `</table>`;
                    frappe.msgprint({
                        title: 'Item Stock',
                        message: html
                    });

                }    
            });
        }
        else{
            frappe.msgprint("Please select item code")
        }
    }
})