# Copyright (c) 2026, Akhilam Inc and contributors
# For license information, please see license.txt
"""
Lead workflow actions that need extra input
===========================================
These transitions collect a value in the desk dialog (``lead.js``) and then apply
the workflow action server-side, so the field write and the state change happen in
one request. Each is a discrete whitelisted action → ``apply_workflow`` (which saves
the doc); no ``apply_workflow`` is ever called from Lead's own ``on_update``/``validate``.
"""

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow

from aetas_customization.lead.assignment import (
    get_salespersons_for_store,
    sales_person_to_user,
)
from aetas_customization.lead.pipeline import update_customer_salesperson

# NOTE: frappe.model.workflow.apply_workflow() reloads the doc via load_from_db()
# before applying the transition, so any in-memory field assignments made here would
# be discarded. We therefore persist the extra fields with db_set() FIRST (same
# transaction), so the reloaded doc carries them through the workflow save.


@frappe.whitelist()
def allocate_lead(lead: str, store: str, salesperson: str) -> dict:
    """Manual allocation at Visit Planned → Lead Allocation (80%)."""
    if not (store and salesperson):
        frappe.throw(_("Both store and salesperson are required to allocate."))

    if salesperson not in get_salespersons_for_store(store):
        frappe.throw(
            _("Salesperson {0} is not attached to store {1}.").format(salesperson, store)
        )

    doc = frappe.get_doc("Lead", lead)
    doc.db_set("custom_allocated_store", store)
    doc.db_set("custom_sales_person", salesperson)
    apply_workflow(doc, "Allocate")
    # Close the gap: push the allocated salesperson onto the Customer created at Qualify.
    doc.reload()
    update_customer_salesperson(doc)
    return {"status": "allocated", "salesperson": salesperson, "store": store}


@frappe.whitelist()
def close_lost(lead: str, lost_reason: str) -> dict:
    """Lead Allocation → Closed Lost, capturing the lost reason."""
    if not lost_reason:
        frappe.throw(_("A lost reason is required to close this lead as lost."))

    doc = frappe.get_doc("Lead", lead)
    doc.db_set("custom_lost_reason", lost_reason)
    apply_workflow(doc, "Close Lost")
    return {"status": "closed_lost"}


@frappe.whitelist()
def mark_unqualified(lead: str, reason: str) -> dict:
    """Move a lead to Unqualified from any state that allows it, capturing the reason."""
    if not reason:
        frappe.throw(_("An unqualified reason is required."))

    doc = frappe.get_doc("Lead", lead)
    doc.db_set("custom_unqualified_reason", reason)
    apply_workflow(doc, "Mark Unqualified")
    return {"status": "unqualified"}


@frappe.whitelist()
def close_won_route(lead: str) -> str:
    """Decide the Closed Won path for the acting user: 'store' | 'owner' | 'choose'.

    By exact person: the allocated salesperson's User → store path (create invoice);
    the lead_owner → owner path (enter existing invoice number). Neither/both → choose.
    """
    doc = frappe.get_doc("Lead", lead)
    user = frappe.session.user
    is_owner = bool(doc.lead_owner) and user == doc.lead_owner
    sp_user = sales_person_to_user(doc.custom_sales_person) if doc.custom_sales_person else None
    is_store = bool(sp_user) and user == sp_user

    if is_store and not is_owner:
        return "store"
    if is_owner and not is_store:
        return "owner"
    return "choose"


@frappe.whitelist()
def close_won_with_invoice(lead: str, invoice: str) -> dict:
    """Owner path: tag an existing submitted Sales Invoice, then apply Close Won."""
    if not invoice:
        frappe.throw(_("An invoice is required."))
    inv = frappe.db.get_value(
        "Sales Invoice", invoice, ["customer", "docstatus"], as_dict=True
    )
    if not inv:
        frappe.throw(_("Sales Invoice {0} not found.").format(invoice))
    if inv.docstatus != 1:
        frappe.throw(_("Sales Invoice {0} is not submitted.").format(invoice))

    doc = frappe.get_doc("Lead", lead)
    if doc.customer and inv.customer != doc.customer:
        frappe.throw(
            _("Invoice customer {0} does not match the lead's customer {1}.").format(
                inv.customer, doc.customer
            )
        )
    doc.db_set("custom_si_ref", invoice)
    apply_workflow(doc, "Close Won")
    return {"status": "closed_won", "invoice": invoice}
