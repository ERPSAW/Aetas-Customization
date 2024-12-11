import frappe
from erpnext.stock.doctype.serial_no.serial_no import get_auto_serial_nos

def before_validate(self, method):
    try:
        if self.items and self.stock_entry_type == "Material Receipt":
            for item in self.items:
                dynamic_sn_mapping = frappe.db.get_value("Item", item.item_code, "custom_enable_dynamic_sn_naming")
                if dynamic_sn_mapping == 1 and not item.serial_no:
                    
                    store_code = frappe.db.get_value("Warehouse", item.t_warehouse, "custom_store_code")
                    attribute_code2 = frappe.db.get_value("Item Group", item.item_group, "custom_attribute_2")
                    unique_code = frappe.db.get_value("Item Group", item.item_group, "custom_unique_code")
                    attribute_code3 = frappe.db.get_value("Item", item.item_code, "custom_attribute_3")

                    if not all([store_code, attribute_code2, unique_code, attribute_code3]):
                        missing_attributes = []
                        if not store_code:
                            missing_attributes.append(f"Store Code (Please set <b>Store Code</b> in the Warehouse <b>'{item.t_warehouse}'</b>)")
                        if not attribute_code2:
                            missing_attributes.append(f"Attribute 2 (Please set <b>Attribute 2</b> in the Item Group <b>'{item.item_group}'</b>)")
                        if not unique_code:
                            missing_attributes.append(f"Unique Code (Please set <b>Unique Code</b> in the Item Group <b>'{item.item_group}'</b>)")
                        if not attribute_code3:
                            missing_attributes.append(f"Attribute 3 (Please set <b>Attribute 3</b> in the Item <b>'{item.item_code}'</b>)")
                        
                        frappe.throw(
                            f"Missing required attributes for serial number generation for Item: {item.item_code}. "
                            f"Missing: {', '.join(missing_attributes)}"
                        )
    
                    # serial_no_series = f"{store_code}-{attribute_code2}-{unique_code}{attribute_code3}-.####"
                    serial_no_series = f"{store_code}{attribute_code2}{unique_code}{attribute_code3}.###"
                    
                    created_serial_nos = get_auto_serial_nos(serial_no_series, int(item.qty))
                    if created_serial_nos:
                        # item.serial_no = created_serial_nos
                        clean_serial_nos = [serial_no.replace("-", "") for serial_no in created_serial_nos.split("\n") if serial_no]
                        item.serial_no = "\n".join(clean_serial_nos)

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Dynamic Serial No Creation Error")
        raise