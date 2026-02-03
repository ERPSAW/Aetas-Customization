import frappe

def after_insert(doc, method):
    if doc.custom_sales_person:
        doc.append("custom_customer_journey", {
            "journey_date": frappe.utils.now_datetime(),
            "journey_type": "Creation",
            "description": f"This customer was created on {doc.creation} by Sales Person {doc.custom_sales_person} via {doc.custom_source} lead source.",
            "sales_person": doc.custom_sales_person,
        })
