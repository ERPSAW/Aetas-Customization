import frappe

def fix_lead_source():
    if not frappe.db.exists("Lead Source", "Others"):
        frappe.get_doc({
            "doctype": "Lead Source",
            "source_name": "Others"
        }).insert(ignore_permissions=True)
