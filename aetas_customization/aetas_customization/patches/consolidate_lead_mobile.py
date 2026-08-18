# Copyright (c) 2026, Akhilam Inc and contributors
# For license information, please see license.txt
"""
Consolidate the Lead's mobile to a single field.

The Lead previously had both the standard ``mobile_no`` and a redundant custom
``custom_contact`` (Phone). This copies any ``custom_contact`` value into
``mobile_no`` where the latter is empty, then removes the ``custom_contact``
custom field from Lead (Customer.custom_contact is untouched — the mobile app
depends on it).
"""

import frappe


def execute() -> None:
    if frappe.db.has_column("Lead", "custom_contact"):
        # 1. Preserve data: fill mobile_no from custom_contact where missing.
        frappe.db.sql(
            """
            UPDATE `tabLead`
            SET mobile_no = custom_contact
            WHERE (mobile_no IS NULL OR mobile_no = '')
              AND custom_contact IS NOT NULL AND custom_contact != ''
            """
        )
        frappe.db.commit()

    # 2. Drop the redundant Lead custom field (removes the column).
    if frappe.db.exists("Custom Field", "Lead-custom_contact"):
        frappe.delete_doc("Custom Field", "Lead-custom_contact", ignore_permissions=True)
        frappe.db.commit()
