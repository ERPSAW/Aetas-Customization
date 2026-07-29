import frappe
from erpnext.crm.doctype.lead.lead import Lead
from frappe.model.mapper import get_mapped_doc

from aetas_customization.lead import assignment, pipeline


class CustomLead(Lead):
    def validate(self):
        """Override Lead.validate() — core logic first, then custom status logic."""
        super().set_full_name()
        super().set_lead_name()
        super().set_title()
        self.custom_set_status()
        super().check_email_id_is_unique()
        super().validate_email_id()

        # Custom logic after core validate.
        self.custom_set_status()

    def custom_set_status(self):
        """Legacy native-status derivation.

        Kept INDEPENDENT of the pipeline: the Lead Pipeline workflow drives
        ``workflow_state``/``custom_probability``; the native ``status`` field is
        left to this legacy behaviour (workflow has ``dont_override_status = 1``).
        """
        if self.customer and not self.custom_cold_description:
            self.status = "Qualified"
        if self.custom_si_ref:
            self.status = "Converted"


def validate(doc, method):
    """doc_events validate — seed initial state + keep the attempt count in sync."""
    pipeline.set_initial_state(doc)
    # Recompute from the Lead Journey rows so MANUAL grid additions are counted too
    # (not only attempts logged via the Log Attempt button).
    doc.custom_contact_attempts = len(doc.get("custom_lead_journey") or [])


def after_insert(doc, method):
    """Assign the owning salesperson (existing-customer reuse or round-robin)."""
    assignment.assign_lead(doc)


def on_update(doc, method):
    """Run pipeline side-effects when the workflow state changes."""
    pipeline.handle_state_change(doc)


@frappe.whitelist()
def make_sales_invoice_from_lead(source_name, target_doc=None):
    def set_missing_values(source, target):
        target.customer = source.customer
        target.custom_source = source.source
        target.custom_lead_ref = source.name
        target.due_date = frappe.utils.add_days(frappe.utils.nowdate(), 7)

    doc = get_mapped_doc(
        "Lead",
        source_name,
        {
            "Lead": {
                "doctype": "Sales Invoice",
                "field_map": {
                    "name": "lead",
                },
            }
        },
        target_doc,
        set_missing_values,
    )

    return doc
