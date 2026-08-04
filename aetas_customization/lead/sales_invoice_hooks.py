# Copyright (c) 2026, Akhilam Inc and contributors
# For license information, please see license.txt
"""
Sales Invoice → Lead pipeline glue.

On submit of an invoice that references a Lead (``custom_lead_ref``), if that lead is
sitting at **Lead Allocation**, tag the invoice and auto-advance the lead to
**Closed Won** (the store-person path — no manual Close Won click needed).

Best-effort / non-blocking: any failure is logged and swallowed so it can never roll
back the invoice submission.
"""

import frappe
from frappe.model.workflow import apply_workflow


def on_invoice_submit(doc, method=None) -> None:
    lead = doc.get("custom_lead_ref")
    if not lead or not frappe.db.exists("Lead", lead):
        return
    if frappe.db.get_value("Lead", lead, "workflow_state") != "Lead Allocation":
        return
    try:
        lead_doc = frappe.get_doc("Lead", lead)
        lead_doc.db_set("custom_si_ref", doc.name)
        apply_workflow(lead_doc, "Close Won")
    except Exception:
        frappe.log_error(
            frappe.get_traceback(), "Lead: auto Close Won on Sales Invoice submit"
        )
