import frappe

def validate(doc,method):
    if doc.custom_attribute_2:
        existing_attribute_2 = frappe.get_all("Item Group",filters={"custom_attribute_2": doc.custom_attribute_2,"name": ("!=", doc.name)},
        fields=["name"],limit=1)
        if existing_attribute_2:
            frappe.throw(
                "The attribute '{0}' is already associated with another item group: '{1}'. ""Please use a different attribute.".format(
                doc.custom_attribute_2, existing_attribute_2[0].name))

    if doc.custom_unique_code:
        existing_unique_code = frappe.get_all("Item Group",filters={"custom_unique_code": doc.custom_unique_code,"name": ("!=", doc.name)},
        fields=["name"],limit=1)
        if existing_unique_code:
            frappe.throw(
                "The unique code '{0}' is already associated with another item group: '{1}'. ""Please use a different unique code.".format(
                doc.custom_unique_code, existing_unique_code[0].name))
            
    if doc.custom_attribute_2 and doc.custom_unique_code:
        existing_attribute_codes = frappe.get_all("Item Group",filters={"custom_unique_code": doc.custom_unique_code,"name": ("!=", doc.name),"custom_attribute_2":doc.custom_attribute_2},
        fields=["name"],limit=1)

        if existing_attribute_codes:
            frappe.throw("The attribute '{0}' with unique code '{1}' is already associated with another item group: '{2}'. Please use a different attribute or code.".format(
            doc.custom_attribute_2, doc.custom_unique_code, existing_attribute_codes[0].name))