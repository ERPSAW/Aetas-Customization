# Copyright (c) 2026, Akhilam Inc and contributors
# For license information, please see license.txt
"""
Remove the obsolete 'Lead Manager' role.

The Lead Pipeline was consolidated to two roles (Lead User, Store Sales Person).
'Lead Manager' was only ever referenced by the workflow (now rewritten without it)
and has no users or permission rules, so it is force-deleted here. 'Lead Admin' is a
client-managed role and is intentionally left untouched.
"""

import frappe


def execute() -> None:
    if frappe.db.exists("Role", "Lead Manager"):
        # No users / DocPerms; workflow no longer references it. force bypasses the
        # generic Role link-guard.
        frappe.delete_doc("Role", "Lead Manager", force=True, ignore_permissions=True)
        frappe.db.commit()
