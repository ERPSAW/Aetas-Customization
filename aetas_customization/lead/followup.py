# Copyright (c) 2026, Akhilam Inc and contributors
# For license information, please see license.txt
"""
Lead follow-up attempts
=======================
Reuses the ``Lead Journey`` child table (``custom_lead_journey``) to record contact
attempts while the lead is in **Follow Up**. Logging an attempt is NOT a workflow
transition — it appends a journey row and refreshes ``custom_contact_attempts``.

The lead reaches Follow Up via the ``Not Contacted`` action (Open → Follow Up).
Once ``custom_contact_attempts`` reaches ``MAX_CONTACT_ATTEMPTS``, the workflow's
``Mark Unqualified`` transition from Follow Up becomes available (its condition is
``doc.custom_contact_attempts >= 5``); the rep then applies it and picks a reason.
"""

import frappe
from frappe import _

ALLOWED_TYPES = ("Call", "Whatsapp")


@frappe.whitelist()
def log_attempt(lead: str, contact_type: str = "Call", mobile_number: str | None = None) -> dict:
    """Append a contact attempt (Lead Journey row) and refresh the attempt count."""
    if contact_type not in ALLOWED_TYPES:
        frappe.throw(_("Invalid contact type: {0}").format(contact_type))

    doc = frappe.get_doc("Lead", lead)
    doc.append(
        "custom_lead_journey",
        {
            "by_user": frappe.session.user,
            # to_customer is a Link → Customer; only set it once the lead has one.
            "to_customer": doc.customer or None,
            "initiated_at": frappe.utils.now(),
            "mobile_number": mobile_number or doc.mobile_no,
            "type": contact_type,
        },
    )
    # custom_contact_attempts is recomputed from the journey rows in Lead.validate.
    doc.save()
    attempts = doc.custom_contact_attempts

    return {
        "status": "logged",
        "attempts": attempts,
        "message": _("Attempt {0} logged.").format(attempts),
    }
