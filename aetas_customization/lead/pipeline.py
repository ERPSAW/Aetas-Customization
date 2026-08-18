# Copyright (c) 2026, Akhilam Inc and contributors
# For license information, please see license.txt
"""
Lead pipeline side-effects
==========================
The pipeline itself is a Frappe **Workflow** ("Lead Pipeline") on ``workflow_state``;
the workflow engine enforces the allowed transitions and sets ``custom_probability``
via each state's Update Field/Value.

This module runs:
* ``resolve_customer`` at ``Lead.after_insert`` — link/create the Customer at creation.
* state-change *side-effects* from ``Lead.on_update`` (comparing saved vs previous state):
  entering **Closed Won** → tag the linked Sales Invoice into ``custom_si_ref``.

State-change side-effects use ``db_set`` only. They never call ``apply_workflow`` or
``save`` from within the ``on_update`` path, avoiding transition recursion.
"""

import frappe
from frappe import _

INITIAL_STATE = "Open"

# Number of failed contact attempts after which a lead auto-moves to Unqualified.
MAX_CONTACT_ATTEMPTS = 5


def set_initial_state(doc) -> None:
    """Seed ``workflow_state``/``custom_probability`` on a new Lead (before insert)."""
    if not doc.get("workflow_state"):
        doc.workflow_state = INITIAL_STATE
        doc.custom_probability = 0


def handle_state_change(doc) -> None:
    """Run side-effects when ``workflow_state`` changes (called from ``on_update``)."""
    previous = doc.get_doc_before_save()
    if not previous:
        return
    if previous.workflow_state == doc.workflow_state:
        return

    if doc.workflow_state == "Closed Won":
        tag_sales_invoice(doc)


def resolve_customer(doc) -> None:
    """Link or create the Customer at lead CREATION (called from ``after_insert``).

    Match priority: (1) ``Customer.custom_contact == Lead.mobile_no``,
    (2) ``Customer.custom_email == Lead.email_id``. If matched → link + mark the lead
    ``Existing Customer``; otherwise create a new Customer now + mark ``New``.

    Non-blocking: a data gap must never roll back lead creation (important for the
    webhook path). ``ignore_permissions`` is justified — system-driven creation and a
    Lead User will not normally hold Customer create rights.
    """
    if doc.customer:
        return
    try:
        match = None
        if doc.mobile_no:
            match = frappe.db.get_value(
                "Customer", {"custom_contact": doc.mobile_no}, "name"
            )
        if not match and doc.email_id:
            match = frappe.db.get_value(
                "Customer", {"custom_email": doc.email_id}, "name"
            )

        if match:
            doc.db_set("customer", match)
            doc.db_set("type", "Existing Customer")
            return

        if not doc.lead_name:
            return
        customer = _build_customer(doc)
        customer.insert(ignore_permissions=True)
        doc.db_set("customer", customer.name)
        doc.db_set("type", "New")
        frappe.msgprint(
            _("Customer {0} created from Lead {1}").format(customer.name, doc.name),
            indicator="green",
            alert=True,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Lead: customer resolution at creation")


def _default_lead_source() -> str | None:
    """Fallback source when a lead has none (Customer.custom_source is mandatory).
    Prefer 'Others', else any existing Lead Source."""
    if frappe.db.exists("Lead Source", "Others"):
        return "Others"
    return frappe.db.get_value("Lead Source", {}, "name")


def _build_customer(doc):
    """Build (unsaved) a Customer document from a Lead.

    Customer.custom_contact is a mandatory, validated Phone field. Webhook input is
    phone-validated up front (see api/lead_webhook.py), so a created lead's mobile is
    a valid number; a manually-entered invalid mobile will fail here and is handled
    non-blockingly by resolve_customer (logged; lead still created).
    """
    customer = frappe.get_doc(
        {
            "doctype": "Customer",
            "customer_name": doc.lead_name,
            "customer_type": "Individual",
            "customer_group": "All Customer Groups",
            "territory": doc.territory or "All Territories",
            "lead_name": doc.name,
            # custom_source is mandatory on Customer — default to 'Others' if the lead
            # has no source, so customer creation never silently fails on source.
            "custom_source": doc.source or _default_lead_source(),
            "custom_contact": doc.mobile_no,
            "custom_email": doc.email_id,
            "custom_client_tiers": "Potential",
            "custom_sales_person": doc.custom_sales_person,
            "custom_customer_without_sales": 1,
        }
    )
    if doc.custom_sales_person:
        customer.append(
            "sales_team",
            {"sales_person": doc.custom_sales_person, "allocated_percentage": 100},
        )
    return customer


def update_customer_salesperson(doc) -> None:
    """Sync the allocated salesperson onto the lead's Customer (if one exists).

    The Customer is created earlier (at Qualify) without a salesperson, because the
    salesperson is only chosen later at Lead Allocation. This closes that gap by
    writing the allocated ``custom_sales_person`` onto the Customer + its sales team.
    """
    if not (doc.customer and doc.custom_sales_person):
        return
    if frappe.db.get_value("Customer", doc.customer, "custom_sales_person") == doc.custom_sales_person:
        return

    customer = frappe.get_doc("Customer", doc.customer)
    customer.custom_sales_person = doc.custom_sales_person
    # Only seed the sales team when empty — never wipe an existing customer's team.
    if not customer.get("sales_team"):
        customer.append(
            "sales_team",
            {"sales_person": doc.custom_sales_person, "allocated_percentage": 100},
        )
    customer.save(ignore_permissions=True)


def tag_sales_invoice(doc) -> None:
    """On Closed Won, tag the most recent submitted linked Sales Invoice."""
    if doc.custom_si_ref:
        return
    invoice = frappe.db.get_value(
        "Sales Invoice",
        {"custom_lead_ref": doc.name, "docstatus": 1},
        "name",
        order_by="creation desc",
    )
    if invoice:
        doc.db_set("custom_si_ref", invoice)
