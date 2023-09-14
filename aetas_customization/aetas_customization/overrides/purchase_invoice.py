import frappe
            
def on_submit(self, method):
    for item in self.items:
        if item.serial_no:
            serial_numbers = item.serial_no.split("\n")

            frappe.db.sql("""
                UPDATE `tabSerial No`
                SET mrp = %(mrp)s
                WHERE name IN %(serial_numbers)s
                AND item_code = %(item_code)s
                AND warehouse = %(warehouse)s
            """, {
                'mrp': item.mrp,
                'serial_numbers': serial_numbers,
                'item_code': item.item_code,
                'warehouse':item.warehouse
            })
