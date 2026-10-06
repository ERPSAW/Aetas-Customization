import frappe
MANDATORY_UNLESS_EXEMPT_FIELDS = ["custom_source", "custom_contact"]

def validate(doc, method):
    """Enforce mandatory fields for Customer, skipping the configured list
    entirely for sales persons marked exempt in Aetas Custom Setting."""
    if is_exempt_sales_person(doc.custom_sales_person):
        return

    meta = frappe.get_meta("Customer")
    missing = []
    for fieldname in MANDATORY_UNLESS_EXEMPT_FIELDS:
        if not doc.get(fieldname):
            label = meta.get_label(fieldname) or fieldname
            missing.append(label)

    if missing:
        frappe.throw(
            "Mandatory fields required in Customer:<br>" +
            "<br>".join(f"- {label}" for label in missing)
        )


def is_exempt_sales_person(sales_person):
    if not sales_person:
        return False

    settings = frappe.get_single("Aetas Custom Setting")
    exempt_list = {row.sales_person for row in settings.get("exempt_sales_person")}
    return sales_person in exempt_list

def after_insert(doc, method):
    if doc.custom_sales_person:
        if doc.custom_source:
            description = f"This customer was created on {doc.creation} by Sales Person {doc.custom_sales_person} via {doc.custom_source} lead source."
        else:
            description = f"This customer was created on {doc.creation} by Sales Person {doc.custom_sales_person}.",
        doc.append("custom_customer_journey", {
            "journey_date": frappe.utils.now_datetime(),
            "journey_type": "Creation",
            "description": description,
            "sales_person": doc.custom_sales_person,
        })

@frappe.whitelist()
def get_exempt_sales_persons():
    """Used by client script to toggle mandatory fields live in the browser."""
    settings = frappe.get_single("Aetas Custom Setting")
    return [row.sales_person for row in settings.get("exempt_sales_person")]


@frappe.whitelist()
def get_mandatory_unless_exempt_fields():
    """Used by client script to know which fields to toggle."""
    return MANDATORY_UNLESS_EXEMPT_FIELDS
