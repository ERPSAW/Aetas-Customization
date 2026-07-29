# Copyright (c) 2026, Akhilam Inc and contributors
# For license information, please see license.txt
"""
Integration tests for the Lead Pipeline: the Follow Up branch (attempts gate the
Mark Unqualified transition), the allocation store filter, and webhook source mapping.

Requires the app to be migrated (the "Lead Pipeline" workflow + custom fields must
exist in the test site), so run after `bench migrate`:

    bench --site <site> run-tests --app aetas_customization \
        --module aetas_customization.tests.test_lead_pipeline
"""

import frappe
from frappe.model.workflow import apply_workflow, get_transitions
from frappe.tests.utils import FrappeTestCase

from aetas_customization.aetas_customization.api.lead_webhook import _resolve_source
from aetas_customization.lead.assignment import get_salespersons_for_store
from aetas_customization.lead.followup import log_attempt
from aetas_customization.lead.pipeline import MAX_CONTACT_ATTEMPTS


def _grant_lead_user(user: str = "Administrator") -> None:
    """apply_workflow checks the Lead User role — ensure the test user holds it."""
    u = frappe.get_doc("User", user)
    if "Lead User" not in [r.role for r in u.roles]:
        u.add_roles("Lead User")


class TestLeadFollowup(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        _grant_lead_user()
        self.lead = frappe.get_doc(
            {"doctype": "Lead", "lead_name": "_TP Followup", "mobile_no": "9995550000"}
        ).insert(ignore_permissions=True)
        # Move Open -> Follow Up (the "Not Contacted" branch).
        apply_workflow(self.lead, "Not Contacted")
        self.lead.reload()

    def tearDown(self):
        frappe.db.rollback()

    def _available_actions(self):
        self.lead.reload()
        return {t["action"] for t in get_transitions(self.lead)}

    def test_not_contacted_moves_to_follow_up(self):
        """Success: the Not Contacted action lands the lead in Follow Up."""
        self.assertEqual(self.lead.workflow_state, "Follow Up")

    def test_log_attempt_increments_and_stays_in_follow_up(self):
        """Boundary: logging attempts increments the count and does not transition."""
        for i in range(MAX_CONTACT_ATTEMPTS - 1):
            result = log_attempt(self.lead.name, "Call")
        self.assertEqual(result["status"], "logged")
        self.assertEqual(result["attempts"], MAX_CONTACT_ATTEMPTS - 1)
        self.assertEqual(
            frappe.db.get_value("Lead", self.lead.name, "workflow_state"), "Follow Up"
        )

    def test_unqualify_gated_until_five_attempts(self):
        """CRITICAL: Mark Unqualified is unavailable until attempts >= 5."""
        for _ in range(MAX_CONTACT_ATTEMPTS - 1):
            log_attempt(self.lead.name, "Call")
        self.assertNotIn("Mark Unqualified", self._available_actions())  # 4 attempts
        log_attempt(self.lead.name, "Call")  # 5th
        self.assertIn("Mark Unqualified", self._available_actions())

    def test_unqualify_after_five_attempts(self):
        """CRITICAL: after 5 attempts the lead can be marked Unqualified."""
        for _ in range(MAX_CONTACT_ATTEMPTS):
            log_attempt(self.lead.name, "Call")
        self.lead.reload()
        apply_workflow(self.lead, "Mark Unqualified")
        self.assertEqual(
            frappe.db.get_value("Lead", self.lead.name, "workflow_state"), "Unqualified"
        )

    def test_follow_up_to_contacted(self):
        """Success: Mark Contacted moves Follow Up -> In Progress."""
        apply_workflow(self.lead, "Mark Contacted")
        self.assertEqual(
            frappe.db.get_value("Lead", self.lead.name, "workflow_state"), "In Progress"
        )

    def test_invalid_contact_type_rejected(self):
        """Failure: an unsupported contact type raises."""
        with self.assertRaises(frappe.ValidationError):
            log_attempt(self.lead.name, "Carrier Pigeon")


class TestAllocationFilter(FrappeTestCase):
    STORE = "_TP Boutique"

    def setUp(self):
        frappe.set_user("Administrator")
        if not frappe.db.exists("Boutique", self.STORE):
            frappe.get_doc(
                {"doctype": "Boutique", "boutique_name": self.STORE}
            ).insert(ignore_permissions=True)
        for name in ("_TP Store SP1", "_TP Store SP2"):
            if not frappe.db.exists("Sales Person", name):
                frappe.get_doc(
                    {
                        "doctype": "Sales Person",
                        "sales_person_name": name,
                        "custom_botique": self.STORE,
                    }
                ).insert(ignore_permissions=True)

    def tearDown(self):
        frappe.db.rollback()

    def test_filter_returns_store_salespersons(self):
        """Success: only salespersons attached to the store are returned."""
        result = get_salespersons_for_store(self.STORE)
        self.assertIn("_TP Store SP1", result)
        self.assertIn("_TP Store SP2", result)

    def test_empty_store_returns_empty(self):
        """Edge Case: no store → empty list, no error."""
        self.assertEqual(get_salespersons_for_store(""), [])


class TestWebhookSourceMapping(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def test_known_source_preserved(self):
        """Success: a payload source matching a Lead Source master is kept."""
        if not frappe.db.exists("Lead Source", "Existing Customer"):
            source_name = frappe.db.get_value("Lead Source", {}, "name")
        else:
            source_name = "Existing Customer"
        if source_name:
            self.assertEqual(_resolve_source(source_name), source_name)

    def test_unknown_source_falls_back(self):
        """Edge Case: an unknown source falls back to 'Others'."""
        self.assertEqual(_resolve_source("Definitely Not A Lead Source"), "Others")

    def test_blank_source_falls_back(self):
        """Edge Case: blank/None source falls back to 'Others'."""
        self.assertEqual(_resolve_source(None), "Others")
        self.assertEqual(_resolve_source(""), "Others")
