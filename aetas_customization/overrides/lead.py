import frappe
from erpnext.crm.doctype.lead.lead import Lead
from frappe.model.mapper import get_mapped_doc


class CustomLead(Lead):
    def validate(self):
        """
        Override Lead.validate()
        """

        # 🔹 Call core logic FIRST (recommended)
        super().set_full_name()
        super().set_lead_name()
        super().set_title()
        self.custom_set_status()
        super().check_email_id_is_unique()
        super().validate_email_id()

        # 🔥 Your custom logic AFTER core validate
        self.custom_set_status()

    def custom_set_status(self):
        """
        Your overridden status logic
        """

        if self.customer:
            self.status = "Qualified"
        if self.custom_si_ref:
            self.status = "Converted"


def after_insert(doc, method):
    if doc.is_new():
        customer_creation_via_lead(doc)


def on_update(doc, method):
    customer_creation_via_lead(doc)


def validate(doc, method):
    pass
    # if doc.status != "Qualified":
    #     return

    # # Prevent duplicate child rows for same sales person
    # already_exists = any(
    #     row.sales_person == doc.custom_sales_person
    #     for row in doc.custom_bids
    # )

    # if already_exists:
    #     return

    # doc.append("custom_bids", {
    #     "sales_person": doc.custom_sales_person,
    #     "status": "Approved" if doc.type == "Existing Customer" else "Applied",
    #     "applied_on": frappe.utils.nowdate(),
    #     "approved_by": frappe.session.user,
    # })


def customer_creation_via_lead(doc):
    try:
        # Customer may not be created from Lead
        if not doc.lead_name:
            frappe.msgprint("No lead name provided", indicator="orange")
            return

        # Ensure Lead exists
        if not frappe.db.exists("Lead", {"lead_name": doc.lead_name}):
            frappe.msgprint(f"Lead {doc.lead_name} does not exist", indicator="red")
            return

        # Fix: Use doc.lead_name instead of doc.name
        lead = frappe.get_doc("Lead", {"lead_name": doc.lead_name})

        # Only for Qualified + New leads
        if lead.status != "Qualified" or lead.type != "New":
            return

        # ---------- Existing customer check ----------
        existing_customer = frappe.db.get_all(
            "Customer",
            filters={
                "customer_name": lead.lead_name,
                "custom_contact": lead.custom_contact,
            },
            limit_page_length=1,
        )

        if existing_customer:
            frappe.msgprint(
                f"Customer {existing_customer[0].name} already exists for Lead {lead.name}",
                indicator="orange",
            )
            return

        # ---------- Create Customer ----------
        customer = frappe.get_doc(
            {
                "doctype": "Customer",
                "customer_name": lead.lead_name,
                "customer_type": "Individual",
                "customer_group": "All Customer Groups",
                "territory": lead.territory or "All Territories",
                "lead_name": lead.name,
                "custom_source": lead.source,
                "custom_contact": lead.custom_contact,
                "custom_client_tiers": "Potential",
                "custom_sales_person": lead.custom_sales_person,
                "custom_customer_without_sales": 1,
            }
        )

        if lead.custom_sales_person:
            customer.append(
                "sales_team",
                {"sales_person": lead.custom_sales_person, "allocated_percentage": 100},
            )

        customer.insert(ignore_permissions=True)
        frappe.db.commit()  # Ensure the transaction is committed
        doc.db_set("customer", customer.name)
        frappe.msgprint(
            f"Customer {customer.name} created from Lead {lead.name}", indicator="green"
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Customer Creation via Lead")
        frappe.msgprint(f"Error creating customer: {str(e)}", indicator="red")
        raise  # Re-raise to see the full error


@frappe.whitelist()
def make_sales_invoice_from_lead(source_name, target_doc=None):
    def set_missing_values(source, target):
        target.customer = source.customer  # you decide
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
