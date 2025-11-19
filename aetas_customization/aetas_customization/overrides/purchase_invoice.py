import frappe
# ERPNext v15
from erpnext.stock.doctype.serial_no.serial_no import get_available_serial_nos as get_serial_nos

def before_validate(self, method):
    try:
        if self.items:
            for item in self.items:

                dynamic_sn_mapping = frappe.db.get_value(
                    "Item", item.item_code, "custom_enable_dynamic_sn_naming"
                )

                # Only create SN if required and missing
                if dynamic_sn_mapping == 1 and not item.serial_no:

                    # Fetch attributes
                    store_code = frappe.db.get_value("Warehouse", item.warehouse, "custom_store_code")
                    attribute_code2 = frappe.db.get_value("Item Group", item.item_group, "custom_attribute_2")
                    unique_code = frappe.db.get_value("Item Group", item.item_group, "custom_unique_code")

                    # Validate
                    if not all([store_code, attribute_code2, unique_code]):
                        missing = []

                        if not store_code:
                            missing.append(
                                f"Store Code (Please set <b>Store Code</b> in Warehouse <b>'{item.warehouse}'</b>)"
                            )
                        if not attribute_code2:
                            missing.append(
                                f"Attribute 2 (Please set <b>Attribute 2</b> in Item Group <b>'{item.item_group}'</b>)"
                            )
                        if not unique_code:
                            missing.append(
                                f"Unique Code (Please set <b>Unique Code</b> in Item Group <b>'{item.item_group}'</b>)"
                            )

                        frappe.throw(
                            f"Missing required attributes for serial number generation for Item: {item.item_code}. "
                            f"Missing: {', '.join(missing)}"
                        )

                    # Serial pattern (v15 compatible)
                    serial_no_series = f"{store_code}{attribute_code2}{unique_code}.###"

                    # v15 → ALWAYS RETURNS LIST
                    try:
                        created_serial_nos = get_serial_nos(serial_no_series, int(item.qty))
                    except TypeError:
                        created_serial_nos = get_serial_nos(
                            item_code=item.item_code,
                            qty=int(item.qty)
                        )

                    if created_serial_nos:

                        # created_serial_nos IS ALWAYS A LIST IN v15
                        clean_serial_nos = [
                            sn.replace("-", "") for sn in created_serial_nos
                        ]

                        # Set as newline-separated format (required by ERPNext)
                        item.serial_no = "\n".join(clean_serial_nos)

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Dynamic Serial No Creation Error")
        raise

          
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
