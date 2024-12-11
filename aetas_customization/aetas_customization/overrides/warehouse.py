import frappe

def validate(doc,method):
    if doc.custom_store_code:
        store_codes = frappe.get_all("Warehouse",filters={"custom_store_code": doc.custom_store_code,"name": ("!=", doc.name)},
        fields=["name"],limit=1)

        if store_codes:
            frappe.throw("The Store Code '{0}' is already associated with another Warehouse: '{1}'. Please use a different Store Code.".format(
            doc.custom_store_code, store_codes[0].name))