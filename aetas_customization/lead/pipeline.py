# Copyright (c) 2026, Akhilam Inc and contributors
# For license information, please see license.txt
"""
Lead pipeline side-effects
==========================
The pipeline itself is a Frappe **Workflow** ("Lead Pipeline") on ``workflow_state``;
the workflow engine enforces the allowed transitions and sets ``custom_probability``
via each state's Update Field/Value.

This module only runs the *side-effects* of entering a state — things a workflow
"Update Field" cannot do — detected from ``Lead.on_update`` by comparing the saved
state with the previous one:

* entering **Qualified** (type New)  → auto-create the Customer
* entering **Closed Won**            → tag the linked Sales Invoice into ``custom_si_ref``

All side-effects use ``db_set`` only. They never call ``apply_workflow`` or ``save``
from within the ``on_update`` path, avoiding transition recursion.
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

    new_state = doc.workflow_state
    if new_state == "Qualified" and doc.type == "New":
        # Non-blocking: a data gap (e.g. missing mandatory Customer field) must not
        # roll back the Qualify transition. Warn and let the user fix the lead.
        try:
            create_customer_from_lead(doc)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Lead: customer creation on Qualify")
            frappe.msgprint(
                _("Lead qualified, but the Customer could not be created automatically. "
                  "Please check the lead's contact/source details."),
                indicator="orange",
                alert=True,
            )
    elif new_state == "Closed Won":
        tag_sales_invoice(doc)


def create_customer_from_lead(doc) -> None:
    """Create a Customer for a newly Qualified lead (idempotent).

    ``ignore_permissions`` is justified: this is a system-driven creation triggered
    by the pipeline, and a Lead User (salesperson) will not normally hold Customer
    create rights.
    """
    if doc.customer:
        return
    if not doc.lead_name:
        return

    # Idempotency: skip if a customer already matches this enquirer.
    existing = frappe.db.get_value(
        "Customer",
        {"customer_name": doc.lead_name, "custom_contact": doc.custom_contact},
        "name",
    )
    if existing:
        doc.db_set("customer", existing)
        return

    customer = frappe.get_doc(
        {
            "doctype": "Customer",
            "customer_name": doc.lead_name,
            "customer_type": "Individual",
            "customer_group": "All Customer Groups",
            "territory": doc.territory or "All Territories",
            "lead_name": doc.name,
            "custom_source": doc.source,
            "custom_contact": doc.custom_contact,
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

    customer.insert(ignore_permissions=True)
    doc.db_set("customer", customer.name)
    frappe.msgprint(
        _("Customer {0} created from Lead {1}").format(customer.name, doc.name),
        indicator="green",
        alert=True,
    )


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
