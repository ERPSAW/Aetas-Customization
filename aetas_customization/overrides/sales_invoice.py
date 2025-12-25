import frappe

@frappe.whitelist()
def check_user_has_naming_series(user):
    return frappe.db.count('Userwise naming series mapping', {"user": user})

@frappe.whitelist()
def get_user_naming_series(user):
    return frappe.db.get_all("Userwise naming series mapping", filters={"user": user}, fields=["naming_series"])    