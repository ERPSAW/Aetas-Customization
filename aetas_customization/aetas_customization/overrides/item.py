import frappe

def validate(doc,method):
    if doc.custom_attribute_3:
        existing_attribute = frappe.get_all("Item",filters={"custom_attribute_3": doc.custom_attribute_3,"name": ("!=", doc.name),"item_group":doc.item_group},
        fields=["name"],limit=1)

        if existing_attribute:
            frappe.throw(
                "Attribute: {0} is already used with this item: {1}".format(
                    doc.custom_attribute_3, existing_attribute[0].name
                )
            )