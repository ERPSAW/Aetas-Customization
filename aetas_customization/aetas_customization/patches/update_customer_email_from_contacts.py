import frappe


def execute():
    add_custom_contact_email()
    update_contact_email()


def add_custom_contact_email():
    field_propeties = [
        {
            "doctype": "Customer",
            "fieldname": "custom_email",
            "label": "Email",
            "options": "Email",
        }
    ]

    try:
        for prop in field_propeties:
            print("Adding custom field for '{}'".format(prop["fieldname"]))
            if not frappe.db.exists(
                "Custom Field",
                {"dt": prop["doctype"], "fieldname": prop["fieldname"]},
            ):
                custom_field = frappe.new_doc("Custom Field")
                custom_field.doctype_or_field = "DocField"
                custom_field.label = prop["label"]
                custom_field.dt = prop["doctype"]
                custom_field.fieldname = prop["fieldname"]
                custom_field.fieldtype = "Data"
                custom_field.options = prop["options"]
                custom_field.insert_after = "custom_contact"
                custom_field.insert()
                frappe.db.commit()
                print("Custom Field '{}' added successfully".format(prop["fieldname"]))
            else:
                print("Custom Field '{}' already exists".format(prop["fieldname"]))
    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title="Error in adding custom field")
        print("Error occurred while adding custom field: ", str(e))


def update_contact_email():
    frappe.db.sql(
        """
        UPDATE `tabCustomer` cust
        INNER JOIN `tabDynamic Link` dl
            ON dl.link_name = cust.name
            AND dl.link_doctype = 'Customer'
        INNER JOIN (
            SELECT
                ce.parent,
                MIN(ce.email_id) AS email_id
            FROM `tabContact Email` ce
            WHERE ce.email_id IS NOT NULL
            GROUP BY ce.parent
        ) ce ON ce.parent = dl.parent
        SET cust.custom_email = ce.email_id
        """
    )
    print(f"Updated customer records with email.")