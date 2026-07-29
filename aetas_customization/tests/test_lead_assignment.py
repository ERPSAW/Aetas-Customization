# Copyright (c) 2026, Akhilam Inc and contributors
# For license information, please see license.txt
"""
Tests for the lead assignment engine (aetas_customization/lead/assignment.py).

Run:
    bench --site <site> run-tests --app aetas_customization \
        --module aetas_customization.tests.test_lead_assignment
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from aetas_customization.lead.assignment import (
    find_prior_owner,
    next_brand_salesperson,
)

BRAND = "_Test Pipeline Brand"


def _ensure_sales_person(name: str) -> str:
    if not frappe.db.exists("Sales Person", name):
        frappe.get_doc(
            {"doctype": "Sales Person", "sales_person_name": name}
        ).insert(ignore_permissions=True)
    return name


def _make_brand(pool: list[tuple[str, int]]) -> frappe.Document:
    """pool = [(sales_person_name, disabled), ...] in intended rotation order."""
    if frappe.db.exists("Brand", BRAND):
        frappe.delete_doc("Brand", BRAND, force=True)
    brand = frappe.get_doc({"doctype": "Brand", "brand": BRAND})
    for idx, (sp, disabled) in enumerate(pool):
        _ensure_sales_person(sp)
        brand.append(
            "custom_sales_persons",
            {
                "sales_person": sp,
                "disabled": disabled,
                # Stagger timestamps so ``added_on`` ordering is deterministic.
                "added_on": frappe.utils.add_to_date(frappe.utils.now(), seconds=idx),
            },
        )
    brand.insert(ignore_permissions=True)
    return brand


class TestLeadAssignment(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.db.rollback()

    def test_round_robin_advances_and_wraps(self):
        """Success: rotation picks the next SP each call and wraps to the top."""
        _make_brand([("_TP SP A", 0), ("_TP SP B", 0), ("_TP SP C", 0)])
        picks = [next_brand_salesperson(BRAND) for _ in range(4)]
        self.assertEqual(picks, ["_TP SP A", "_TP SP B", "_TP SP C", "_TP SP A"])

    def test_round_robin_skips_disabled(self):
        """Boundary: a disabled pool member is never selected."""
        _make_brand([("_TP SP A", 0), ("_TP SP B", 1), ("_TP SP C", 0)])
        picks = [next_brand_salesperson(BRAND) for _ in range(4)]
        self.assertNotIn("_TP SP B", picks)
        self.assertEqual(picks, ["_TP SP A", "_TP SP C", "_TP SP A", "_TP SP C"])

    def test_empty_pool_returns_none(self):
        """Failure: a brand with no enabled salespersons assigns nobody."""
        _make_brand([("_TP SP A", 1)])
        self.assertIsNone(next_brand_salesperson(BRAND))

    def test_single_member_pool_repeats(self):
        """Boundary: a one-member pool always returns that member."""
        _make_brand([("_TP SP A", 0)])
        self.assertEqual(
            [next_brand_salesperson(BRAND) for _ in range(3)],
            ["_TP SP A", "_TP SP A", "_TP SP A"],
        )

    def test_pointer_at_removed_member_restarts_at_top(self):
        """Edge Case: pointer referencing a now-absent SP restarts rotation at top."""
        _make_brand([("_TP SP A", 0), ("_TP SP B", 0)])
        frappe.db.set_value(
            "Brand", BRAND, "custom_last_assigned_sales_person", "_TP SP GONE"
        )
        self.assertEqual(next_brand_salesperson(BRAND), "_TP SP A")

    def test_prior_owner_reused_for_same_brand(self):
        """Success: a returning enquirer reuses their last lead owner for that brand."""
        _make_brand([("_TP SP A", 0), ("_TP SP B", 0)])
        prior = frappe.get_doc(
            {
                "doctype": "Lead",
                "lead_name": "_TP Returning",
                "mobile_no": "9990001111",
                "custom_brand": BRAND,
                "lead_owner": "Administrator",
            }
        ).insert(ignore_permissions=True)

        new_lead = frappe.get_doc(
            {
                "doctype": "Lead",
                "lead_name": "_TP Returning 2",
                "mobile_no": "9990001111",
                "custom_brand": BRAND,
            }
        )
        new_lead.name = "NEW-TEMP"
        self.assertEqual(find_prior_owner(new_lead), "Administrator")
        self.assertTrue(prior.name)

    def test_prior_owner_scoped_to_brand(self):
        """Edge Case: prior lead on a different brand does not leak an owner."""
        _make_brand([("_TP SP A", 0)])
        frappe.get_doc(
            {
                "doctype": "Lead",
                "lead_name": "_TP OtherBrand",
                "mobile_no": "9990002222",
                "custom_brand": "_TP Some Other Brand",
                "lead_owner": "Administrator",
            }
        ).insert(ignore_permissions=True)

        new_lead = frappe.get_doc(
            {
                "doctype": "Lead",
                "lead_name": "_TP OtherBrand 2",
                "mobile_no": "9990002222",
                "custom_brand": BRAND,
            }
        )
        new_lead.name = "NEW-TEMP-2"
        self.assertIsNone(find_prior_owner(new_lead))
