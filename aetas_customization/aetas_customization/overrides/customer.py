import frappe
import json
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


@frappe.whitelist()
def get_customer_validation_data(customer):
    """Fetch all configured validation fields + any existing saved state for this customer."""
    frappe.only_for("Customer Validation")
    settings = frappe.get_single("Aetas Custom Setting")
    customer_doc = frappe.get_doc("Customer", customer)

    existing = {row.field_name: row for row in customer_doc.get("custom_customer_validation_detail")}

    fields = []
    for row in settings.customer_validation_field:
        saved = existing.get(row.field_name)
        fields.append({
            "field_name": row.field_name,
            "yes": saved.yes if saved else 0,
            "no": saved.no if saved else 0,
        })
    return fields


@frappe.whitelist()
def validate_customer_fields(customer, fields):
    """Check Yes-marked fields have values, then save the validation table (overwrite)."""
    frappe.only_for("Customer Validation")
    
    if isinstance(fields, str):
        fields = json.loads(fields)

    customer_doc = frappe.get_doc("Customer", customer)
    fieldname_map = get_fieldname_from_label_map("Customer")

    for row in fields:
        if row.get("yes"):
            actual_fieldname = fieldname_map.get(row["field_name"])
            value = customer_doc.get(actual_fieldname) if actual_fieldname else None
            if not value:
                frappe.throw(f"'{row['field_name']}' is marked Yes but has no value on this Customer.")

    customer_doc.set("custom_customer_validation_detail", [])
    for row in fields:
        customer_doc.append("custom_customer_validation_detail", {
            "field_name": row["field_name"],
            "yes": row.get("yes", 0),
            "no": row.get("no", 0),
        })
    customer_doc.save(ignore_permissions=True)
    return {"success": True}


def get_fieldname_from_label_map(doctype):
    meta = frappe.get_meta(doctype)
    return {df.label: df.fieldname for df in meta.fields if df.label}
