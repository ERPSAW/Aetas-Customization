import frappe


def after_insert(doc, method):
    customer_creation_via_lead(doc, method)

def on_update(doc, method):
    customer_creation_via_lead(doc, method)
    
def customer_creation_via_lead(doc, method):
    if not doc.lead_name:
        return

    lead = frappe.get_doc("Lead", doc.lead_name)

    # Only for Qualified + New leads
    if lead.status != "Qualified" and lead.type != "New":
        return

    # ---------- Mandatory field validation ----------
    contact = lead.mobile_no or lead.phone
    if not contact:
        frappe.throw("Lead must have Mobile No or Phone to create Customer")

    if not lead.source:
        frappe.throw("Lead Source is mandatory to create Customer")

    # ---------- Existing customer check ----------
    or_filters = []
    if lead.mobile_no:
        or_filters.append({"custom_contact": lead.mobile_no})
    if lead.phone:
        or_filters.append({"custom_contact": lead.phone})

    existing_customer = frappe.db.exists(
        "Customer",
        {"customer_name": lead.lead_name},
        or_filters=or_filters
    )

    if existing_customer:
        return

    # ---------- Create Customer ----------
    customer = frappe.get_doc({
        "doctype": "Customer",
        "customer_name": lead.lead_name,
        "customer_type": "Individual",
        "customer_group": "All Customer Groups",
        "territory": "All Territories",

        # Mandatory custom fields
        "lead_name": lead.name,
        "custom_source": lead.source,
        "custom_contact": contact,
    })

    # Sales person
    if lead.custom_sales_person:
        customer.append("sales_team", {
            "sales_person": lead.custom_sales_person,
            "allocation_percentage": 100
        })

    customer.insert(ignore_permissions=True)
