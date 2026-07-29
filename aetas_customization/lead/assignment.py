# Copyright (c) 2026, Akhilam Inc and contributors
# For license information, please see license.txt
"""
Lead assignment engine
=======================
Runs on ``Lead.after_insert`` (see ``overrides/lead.py``). Sets the **Lead Owner**
(``lead_owner``, a User) at creation time:

1. Existing-customer reuse — if the enquirer (matched by mobile OR email) has a
   prior lead **for the same brand**, reuse that lead's ``lead_owner``.
2. Brand round-robin — otherwise pick the next enabled Sales Person from the
   brand's ``custom_sales_persons`` pool (advancing ``custom_last_assigned_sales_person``
   under a row lock), then resolve that Sales Person to its User
   (``Sales Person.employee`` → ``Employee.user_id``) and set it as ``lead_owner``.

Note: ``custom_sales_person`` is NOT set here — it is assigned later, manually, at
the **Lead Allocation** stage (see ``lead/actions.py::allocate_lead``).

Fallbacks (brand missing / empty pool / salesperson has no linked User) leave the
lead owner as-is (the creating user) and log the reason.
"""

import frappe

LOGGER_NS = "lead_assignment"


def assign_lead(doc) -> None:
    """Set ``lead_owner`` on a freshly inserted Lead via reuse or brand round-robin."""
    owner = find_prior_owner(doc)
    if owner:
        doc.db_set("lead_owner", owner)
        return

    brand = doc.custom_brand
    if not brand:
        frappe.logger(LOGGER_NS).info(
            f"Lead {doc.name}: no brand — lead owner left as-is for manual pickup."
        )
        return

    salesperson = next_brand_salesperson(brand)
    if not salesperson:
        frappe.logger(LOGGER_NS).info(
            f"Lead {doc.name}: brand {brand} has no enabled salespersons — "
            "lead owner left as-is for manual pickup."
        )
        return

    user = sales_person_to_user(salesperson)
    if user:
        doc.db_set("lead_owner", user)
    else:
        frappe.logger(LOGGER_NS).info(
            f"Lead {doc.name}: salesperson {salesperson} has no linked User "
            "(Employee.user_id) — lead owner left as-is for manual pickup."
        )


def sales_person_to_user(sales_person: str) -> str | None:
    """Resolve a Sales Person to its login User via ``employee.user_id``."""
    employee = frappe.db.get_value("Sales Person", sales_person, "employee")
    if not employee:
        return None
    return frappe.db.get_value("Employee", employee, "user_id") or None


# Owners that must never be reused as a lead owner (system / non-salesperson users).
NON_ASSIGNABLE_OWNERS = ("Guest", "Administrator")


def find_prior_owner(doc) -> str | None:
    """Return the ``lead_owner`` of this enquirer's most recent lead for the same brand.

    Matches on mobile OR email, scoped to ``custom_brand``. Skips system/disabled
    owners (Guest/Administrator/disabled users) so a bad legacy owner is never
    propagated — the caller then falls back to brand round-robin. Returns ``None``
    when there is no brand, no contact info, or no reusable prior owner.
    """
    if not doc.custom_brand:
        return None
    if not (doc.mobile_no or doc.email_id):
        return None

    or_filters = {}
    if doc.mobile_no:
        or_filters["mobile_no"] = doc.mobile_no
    if doc.email_id:
        or_filters["email_id"] = doc.email_id

    priors = frappe.get_all(
        "Lead",
        filters=[
            ["custom_brand", "=", doc.custom_brand],
            ["name", "!=", doc.name],
            ["lead_owner", "is", "set"],
            ["lead_owner", "not in", NON_ASSIGNABLE_OWNERS],
        ],
        or_filters=or_filters,
        fields=["lead_owner"],
        order_by="creation desc",
        limit=10,
    )
    if not priors:
        return None

    # Newest-first, but only reuse an owner that is still an enabled User.
    owners = [p.lead_owner for p in priors]
    enabled = set(
        frappe.get_all(
            "User",
            filters={"name": ["in", list(set(owners))], "enabled": 1},
            pluck="name",
        )
    )
    for owner in owners:
        if owner in enabled:
            return owner
    return None


def next_brand_salesperson(brand: str) -> str | None:
    """Pick the next enabled salesperson in the brand's rotation and advance the pointer.

    The Brand row is locked ``for update`` so concurrent lead inserts serialise on
    the rotation pointer and cannot both receive the same salesperson.
    """
    # Row lock on the Brand — serialises concurrent assignments for this brand.
    last_assigned = frappe.db.get_value(
        "Brand", brand, "custom_last_assigned_sales_person", for_update=True
    )

    rows = frappe.get_all(
        "Brand Sales Person",
        filters={
            "parent": brand,
            "parentfield": "custom_sales_persons",
            "disabled": 0,
        },
        fields=["sales_person"],
        order_by="added_on asc, idx asc",
    )
    pool = [r.sales_person for r in rows]
    if not pool:
        return None

    if last_assigned in pool:
        nxt = pool[(pool.index(last_assigned) + 1) % len(pool)]
    else:
        # Pointer unset or points at a now-removed/disabled person → start at the top.
        nxt = pool[0]

    frappe.db.set_value("Brand", brand, "custom_last_assigned_sales_person", nxt)
    return nxt


@frappe.whitelist()
def get_salespersons_for_store(store: str) -> list[str]:
    """Salespersons attached to a Boutique store — used by the allocation dialog.

    Sales Person carries the store on ``custom_botique`` (existing field, sic).
    """
    if not store:
        return []
    rows = frappe.get_all(
        "Sales Person",
        filters={"custom_botique": store, "enabled": 1},
        pluck="name",
    )
    return rows
