import frappe

def validate(self,method):
    for item in self.items:
        if item.serial_no:
            mrp_value = frappe.db.get_value("Serial No",item.serial_no,'mrp')
            mrp_value_from_item = frappe.db.get_value("Item",item.item_code,'mrp')
            if mrp_value:
                item.mrp = mrp_value
            elif mrp_value_from_item:
                item.mrp = mrp_value_from_item
            else:
                item.mrp = 0
        else:
            mrp_value_from_non_serialize_item = frappe.db.get_value("Item",item.item_code,'mrp')
            if mrp_value_from_non_serialize_item:
                item.mrp = mrp_value_from_non_serialize_item
            else:
                item.mrp = 0    

            
