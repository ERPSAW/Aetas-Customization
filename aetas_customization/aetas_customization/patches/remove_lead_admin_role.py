# Copyright (c) 2026, Akhilam Inc and contributors
# For license information, please see license.txt
"""
Remove the 'Lead Admin' role (lead pipeline standardised to Lead User + Store Sales
Person). Cleans up its user assignments (Has Role) and its Custom DocPerm rules on
Lead / Lead Source, then deletes the role. Idempotent — no-op if the role is absent.
"""

import frappe

ROLE = "Lead Admin"


def execute() -> None:
    if not frappe.db.exists("Role", ROLE):
        return

    # 1. Unassign from all users.
    frappe.db.delete("Has Role", {"role": ROLE})

    # 2. Remove its permission rules (e.g. on Lead, Lead Source).
    for name in frappe.get_all("Custom DocPerm", filters={"role": ROLE}, pluck="name"):
        frappe.delete_doc("Custom DocPerm", name, force=True, ignore_permissions=True)

    # 3. Delete the role.
    frappe.delete_doc("Role", ROLE, force=True, ignore_permissions=True)
    frappe.db.commit()
    frappe.clear_cache()
