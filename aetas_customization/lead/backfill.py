# Copyright (c) 2026, Akhilam Inc and contributors
# For license information, please see license.txt
"""
One-time backfill of ``workflow_state`` + ``custom_probability`` on existing Leads.

Runs as an ``after_migrate`` hook (NOT a patch) because it depends on the custom
fields + the "Lead Pipeline" workflow, which are created by fixtures — and fixtures
sync AFTER patches but BEFORE after_migrate hooks. Idempotent: only touches leads
whose ``workflow_state`` is not yet set, so it is safe to run on every migrate.
"""

import frappe

# legacy native status -> (workflow_state, probability)
STATUS_MAP = {
    "Open": ("Open", 0),
    "Warm": ("In Progress", 10),
    "Assigned": ("In Progress", 10),
    "Qualified": ("Qualified", 20),
    "Converted": ("Closed Won", 100),
    "Cold": ("Unqualified", 0),
    "UnQualified": ("Unqualified", 0),
}

DEFAULT = ("Open", 0)


def backfill_lead_pipeline_state() -> None:
    """Map legacy native ``status`` onto the pipeline state for existing leads."""
    # Guard: only run once the pipeline fields exist (they always do post-fixtures).
    if not (
        frappe.db.has_column("Lead", "workflow_state")
        and frappe.db.has_column("Lead", "custom_probability")
    ):
        return

    # One bulk UPDATE per status group — never clobber an already-set state.
    for status, (state, probability) in STATUS_MAP.items():
        frappe.db.sql(
            """
            UPDATE `tabLead`
            SET workflow_state = %(state)s, custom_probability = %(probability)s
            WHERE (workflow_state IS NULL OR workflow_state = '')
              AND status = %(status)s
            """,
            {"state": state, "probability": probability, "status": status},
        )

    # Anything with an unmapped/blank status falls back to Open.
    frappe.db.sql(
        """
        UPDATE `tabLead`
        SET workflow_state = %(state)s, custom_probability = %(probability)s
        WHERE workflow_state IS NULL OR workflow_state = ''
        """,
        {"state": DEFAULT[0], "probability": DEFAULT[1]},
    )
    frappe.db.commit()


def ensure_lead_crm_settings() -> None:
    """Allow multiple Leads with the same email.

    The pipeline's existing-customer reuse relies on a returning enquirer having
    several leads (same email/mobile), so ERPNext's default email-uniqueness guard
    on Lead must be turned off. Runs as an ``after_migrate`` hook.
    """
    if not frappe.db.get_single_value(
        "CRM Settings", "allow_lead_duplication_based_on_emails"
    ):
        frappe.db.set_single_value(
            "CRM Settings", "allow_lead_duplication_based_on_emails", 1
        )
        frappe.db.commit()
