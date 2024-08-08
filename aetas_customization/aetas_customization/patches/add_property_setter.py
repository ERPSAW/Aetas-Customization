import frappe

def execute():
    add_property_setter_in_sii()

def add_property_setter_in_sii():
    field_propeties = [
        {
            "doctype": "Sales Invoice Item",
            "fieldname": "sales_person",
            "property": "reqd",
            "value": 1
        },
    ]

    try:
        for prop in field_propeties:
            print("Adding property setter for '{}'".format(prop["fieldname"]))
            if not frappe.db.exists("Property Setter",{"property":prop["property"],"doc_type":prop["doctype"],"field_name":prop["fieldname"]}):
                property_setter = frappe.new_doc("Property Setter")
                property_setter.property = prop["property"]
                property_setter.doctype_or_field = "DocField"
                property_setter.doc_type = prop["doctype"]
                property_setter.field_name = prop["fieldname"]
                property_setter.value = prop["value"]
                property_setter.insert()
                frappe.db.commit()
                print("Property setter '{}' added successfully".format(prop["property"]))
            else:
                print("Property setter '{}' already exists".format(prop["property"]))
    except Exception as e:
        print("Error occurred while adding property setter: ", str(e))