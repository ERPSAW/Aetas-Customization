# Copyright (c) 2026, Akhilam Inc and contributors
# For license information, please see license.txt
"""
Test-data setup for the Lead Pipeline (dev/UAT only — safe to delete later).

Creates:
* Boutique "Test Boutique A"
* Sales Persons TSP-A1 / TSP-A2 / TSP-A3 (all attached to that boutique)
* Brand "Test Brand X" with a round-robin pool = [TSP-A1, TSP-A2, TSP-A3(disabled)]
* Grants the "Lead User" role to Administrator so workflow transitions pass.

Idempotent — safe to re-run. Run with:

    bench --site <site> execute aetas_customization.lead.demo_data.setup_lead_test_data
"""

import frappe
from frappe import _

BOUTIQUE = "Test Boutique A"
BRAND = "Test Brand X"


def _require_dev_site() -> None:
    """Refuse to seed test data on a non-developer (production) site."""
    if not frappe.conf.get("developer_mode"):
        frappe.throw(
            _("Refusing to seed Lead test data: this site is not in developer_mode.")
        )
# (sales_person_name, disabled_in_pool, employee_with_linked_user)
# Employees are wired so each salesperson resolves to a User for Lead Owner
# assignment (Sales Person.employee -> Employee.user_id).
POOL = [
    ("TSP-A1", 0, "_T-Employee-00001"),
    ("TSP-A2", 0, "_T-Employee-00002"),
    ("TSP-A3", 1, "_T-Employee-00003"),
]


def _root_sales_person() -> str:
    """Return an existing group Sales Person to parent leaves under (create if none)."""
    root = frappe.get_all(
        "Sales Person", filters={"is_group": 1}, order_by="lft asc", limit=1
    )
    if root:
        return root[0].name
    doc = frappe.get_doc(
        {"doctype": "Sales Person", "sales_person_name": "All Sales Persons", "is_group": 1}
    ).insert(ignore_permissions=True)
    return doc.name


def _ensure_boutique(name: str) -> str:
    if not frappe.db.exists("Boutique", name):
        frappe.get_doc({"doctype": "Boutique", "boutique_name": name}).insert(
            ignore_permissions=True
        )
    return name


def _ensure_sales_person(name: str, boutique: str, employee: str | None = None) -> str:
    # Only link an employee that actually exists (skip gracefully otherwise).
    emp = employee if employee and frappe.db.exists("Employee", employee) else None
    if not frappe.db.exists("Sales Person", name):
        frappe.get_doc(
            {
                "doctype": "Sales Person",
                "sales_person_name": name,
                "parent_sales_person": _root_sales_person(),
                "is_group": 0,
                "custom_botique": boutique,
                "employee": emp,
            }
        ).insert(ignore_permissions=True)
    else:
        frappe.db.set_value(
            "Sales Person", name, {"custom_botique": boutique, "employee": emp}
        )
    return name


def setup_lead_test_data() -> dict:
    _require_dev_site()
    boutique = _ensure_boutique(BOUTIQUE)
    for name, _disabled, employee in POOL:
        _ensure_sales_person(name, boutique, employee)

    if frappe.db.exists("Brand", BRAND):
        brand = frappe.get_doc("Brand", BRAND)
        brand.set("custom_sales_persons", [])
    else:
        brand = frappe.get_doc({"doctype": "Brand", "brand": BRAND})

    for idx, (name, disabled, _employee) in enumerate(POOL):
        brand.append(
            "custom_sales_persons",
            {
                "sales_person": name,
                "disabled": disabled,
                # Stagger so rotation order is deterministic.
                "added_on": frappe.utils.add_to_date(frappe.utils.now(), seconds=idx),
            },
        )
    brand.custom_last_assigned_sales_person = None
    brand.save(ignore_permissions=True)

    admin = frappe.get_doc("User", "Administrator")
    if "Lead User" not in [r.role for r in admin.roles]:
        admin.add_roles("Lead User")

    frappe.db.commit()
    return {
        "boutique": boutique,
        "brand": BRAND,
        "pool": [p[0] for p in POOL],
        "note": "TSP-A3 is disabled in the pool (tests skip-disabled).",
    }


def teardown_lead_test_data() -> dict:
    """Remove the Lead test scaffolding (brand, salespersons, boutique, and any
    leads on the test brand). Run when done testing:

        bench --site <site> execute aetas_customization.lead.demo_data.teardown_lead_test_data
    """
    removed = {"leads": 0, "brand": False, "sales_persons": [], "boutique": False}

    # 1. Leads on the test brand (force — ignore link checks).
    for name in frappe.get_all("Lead", filters={"custom_brand": BRAND}, pluck="name"):
        frappe.delete_doc("Lead", name, force=True, ignore_permissions=True, delete_permanently=True)
        removed["leads"] += 1

    # 2. The test brand.
    if frappe.db.exists("Brand", BRAND):
        frappe.delete_doc("Brand", BRAND, force=True, ignore_permissions=True)
        removed["brand"] = True

    # 3. Test salespersons (nested-set leaves).
    for name, *_rest in POOL:
        if frappe.db.exists("Sales Person", name):
            frappe.delete_doc("Sales Person", name, force=True, ignore_permissions=True)
            removed["sales_persons"].append(name)

    # 4. Test boutique.
    if frappe.db.exists("Boutique", BOUTIQUE):
        frappe.delete_doc("Boutique", BOUTIQUE, force=True, ignore_permissions=True)
        removed["boutique"] = True

    frappe.db.commit()
    return removed


def verify_lead_setup() -> dict:
    """Read-only sanity check that migrate + fixtures + demo data are all in place."""
    from frappe.model.workflow import get_workflow_name

    lead_fields = frappe.get_meta("Lead").get_valid_columns()
    brand = (
        frappe.get_doc("Brand", BRAND) if frappe.db.exists("Brand", BRAND) else None
    )
    admin_roles = [r.role for r in frappe.get_doc("User", "Administrator").roles]
    result = {
        "workflow_active": get_workflow_name("Lead"),
        "workflow_is_active": frappe.db.get_value("Workflow", "Lead Pipeline", "is_active")
        if frappe.db.exists("Workflow", "Lead Pipeline")
        else None,
        "lead_has_workflow_state": "workflow_state" in lead_fields,
        "lead_has_custom_probability": "custom_probability" in lead_fields,
        "lead_has_custom_allocated_store": "custom_allocated_store" in lead_fields,
        "brand_sales_person_doctype": frappe.db.exists("DocType", "Brand Sales Person"),
        "lead_user_role_exists": frappe.db.exists("Role", "Lead User"),
        "admin_has_lead_user": "Lead User" in admin_roles,
        "boutique_exists": frappe.db.exists("Boutique", BOUTIQUE),
        "brand_pool": [
            {"sp": r.sales_person, "disabled": r.disabled}
            for r in (brand.custom_sales_persons if brand else [])
        ],
        "unqualified_reason_options": frappe.get_meta("Lead")
        .get_field("custom_unqualified_reason")
        .options,
    }
    return result
