import frappe

def validate(doc,method):
    if doc.custom_store_code:
        store_codes = frappe.get_all("Warehouse",filters={"custom_store_code": doc.custom_store_code,"name": ("!=", doc.name)},
        fields=["name"],limit=1)

        if store_codes:
            frappe.throw("The Store Code '{0}' is already associated with another Warehouse: '{1}'. Please use a different Store Code.".format(
            doc.custom_store_code, store_codes[0].name))

@frappe.whitelist()
def get_total_stock(item_code):
    try:
        # Fetch all `actual_qty` for the given item_code
        bins = frappe.db.get_all(
            "Bin",
            filters={"item_code": item_code, "actual_qty": (">", 0)},
            fields=["warehouse","actual_qty"]
        )
        
        if bins:
            return bins
        else:
            frappe.msgprint(f"No stock available for item {item_code}")
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error in get_total_stock")
        frappe.throw(f"An error occurred while fetching stock for item {item_code}: {str(e)}")
