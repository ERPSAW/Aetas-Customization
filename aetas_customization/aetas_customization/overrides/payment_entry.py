import frappe
from frappe.desk.reportview import get_match_cond

PAYMENT_SPLIT_TABLE_FIELD = "custom_custom_payment_split"

def _set_receipt_status(receipt_name, status, payment_entry=None):
    if not receipt_name:
        return

    if not frappe.db.exists("Aetas Advance Payment Receipt", receipt_name):
        return

    values = {"status": status}
    if payment_entry is not None:
        values["payment_entry"] = payment_entry

    frappe.db.set_value("Aetas Advance Payment Receipt", receipt_name, values)


def on_submit(self, method=None):
    _set_receipt_status(self.custom_advance_payment_receipt, "Received", self.name)
    
    # Insert child row on APR Payment Details (for manually created Payment Entries)
    if self.custom_advance_payment_receipt:
        try:
            apr = frappe.get_doc("Aetas Advance Payment Receipt", self.custom_advance_payment_receipt)
            existing_row = any((row.payment_entry == self.name) for row in (apr.payment_details or []))
            if not existing_row:
                apr.append("payment_details", {
                    "payment_entry": self.name,
                    "amount": self.paid_amount or 0,
                    "sales_invoice": None
                })
                apr.save(ignore_permissions=True)
        except Exception as e:
            frappe.logger().warning(f"Could not insert APR Payment Detail row: {str(e)}")

    add_payment_to_sales_invoice_split(self)


def on_cancel(self, method=None):
    _set_receipt_status(self.custom_advance_payment_receipt, "To Be Received", "")


def add_payment_to_sales_invoice_split(self):
    """
    Reflect this Payment Entry's allocation in the Sales Invoice's Payment
    Split table — covers payments collected after the invoice was already
    submitted (Create > Payment on a Partly Paid invoice), as opposed to
    advances that were linked before the invoice existed.

    Deliberately does NOT call si.save() — saving an already-submitted
    Sales Invoice re-runs its full validate()/on_update_after_submit chain,
    which re-syncs Loyalty Points and creates a spurious delete+recreate
    pair every time. Instead, the child row is inserted directly, bypassing
    the parent document's controller entirely.
    """
    for ref in self.get("references") or []:
        if ref.reference_doctype != "Sales Invoice" or not ref.reference_name:
            continue

        allocated = frappe.utils.flt(ref.allocated_amount)
        if allocated <= 0:
            continue

        if not frappe.get_meta("Sales Invoice").has_field(PAYMENT_SPLIT_TABLE_FIELD):
            continue

        # Guard against this same Payment Entry being processed twice
        # (e.g. if this Payment Entry itself is later amended/resubmitted).
        already_added = frappe.db.exists(
            "Sales Invoice Payment Split",
            {
                "parent": ref.reference_name,
                "parentfield": PAYMENT_SPLIT_TABLE_FIELD,
                "mode_of_payment": self.mode_of_payment,
                "amount": allocated,
            },
        )
        if already_added:
            continue

        existing_count = frappe.db.count(
            "Sales Invoice Payment Split",
            {"parent": ref.reference_name, "parentfield": PAYMENT_SPLIT_TABLE_FIELD},
        )

        new_row = frappe.get_doc({
            "doctype": "Sales Invoice Payment Split",
            "parent": ref.reference_name,
            "parenttype": "Sales Invoice",
            "parentfield": PAYMENT_SPLIT_TABLE_FIELD,
            "idx": existing_count + 1,
            "mode_of_payment": self.mode_of_payment,
            "amount": allocated,
        })
        new_row.insert(ignore_permissions=True)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def custom_query(doctype, txt, searchfield, start, page_len, filters):
    customer = (filters or {}).get("customer")
    if not customer:
        return []

    return frappe.db.sql("""
        SELECT name
        FROM `tabAetas Advance Payment Receipt`
        WHERE customer = %(customer)s and status = "To Be Received"
        {mcond}
    """.format(
        mcond=get_match_cond(doctype)
    ), {
        "customer": customer,
    })