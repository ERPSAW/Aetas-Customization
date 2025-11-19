import frappe
from erpnext.stock.doctype.serial_no.serial_no import get_available_serial_nos as get_auto_serial_nos

def before_validate(self, method):
    try:
        # Only run for Material Receipt
        if self.items and self.stock_entry_type == "Material Receipt":

            for item in self.items:

                dynamic_sn_mapping = frappe.db.get_value(
                    "Item", item.item_code, "custom_enable_dynamic_sn_naming"
                )

                # Only create serial no if enabled & missing
                if dynamic_sn_mapping == 1 and not item.serial_no:

                    # Fetch attributes
                    store_code = frappe.db.get_value("Warehouse", item.t_warehouse, "custom_store_code")
                    attribute_code2 = frappe.db.get_value("Item Group", item.item_group, "custom_attribute_2")
                    unique_code = frappe.db.get_value("Item Group", item.item_group, "custom_unique_code")

                    # Validation
                    if not all([store_code, attribute_code2, unique_code]):
                        missing_attributes = []

                        if not store_code:
                            missing_attributes.append(
                                f"Store Code (Set <b>Store Code</b> in Warehouse <b>'{item.t_warehouse}'</b>)"
                            )
                        if not attribute_code2:
                            missing_attributes.append(
                                f"Attribute 2 (Set <b>Attribute 2</b> in Item Group <b>'{item.item_group}'</b>)"
                            )
                        if not unique_code:
                            missing_attributes.append(
                                f"Unique Code (Set <b>Unique Code</b> in Item Group <b>'{item.item_group}'</b>)"
                            )

                        frappe.throw(
                            f"Missing required attributes for serial number generation for Item: {item.item_code}. "
                            f"Missing: {', '.join(missing_attributes)}"
                        )

                    # Build serial number series  (v15 compatible)
                    serial_no_series = f"{store_code}{attribute_code2}{unique_code}.#####"

                    # v15 → ALWAYS RETURNS LIST
                    created_serial_nos = get_auto_serial_nos(serial_no_series, int(item.qty))

                    if created_serial_nos:

                        # CLEAN & FORMAT SERIAL NUMBERS
                        clean_serial_nos = [
                            sn.replace("-", "")   # remove hyphens
                            for sn in created_serial_nos  # list, no .split()
                            if sn
                        ]

                        # Set newline-separated format (required by ERPNext)
                        item.serial_no = "\n".join(clean_serial_nos)

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Dynamic Serial No Creation Error")
        raise
