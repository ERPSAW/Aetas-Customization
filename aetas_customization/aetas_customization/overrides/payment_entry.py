import frappe
from frappe.desk.reportview import get_match_cond


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
            apr.append("payment_details", {
                "payment_entry": self.name,
                "amount": self.paid_amount or 0,
                "sales_invoice": None
            })
            apr.save(ignore_permissions=True)
        except Exception as e:
            frappe.logger().warning(f"Could not insert APR Payment Detail row: {str(e)}")


def on_cancel(self, method=None):
    _set_receipt_status(self.custom_advance_payment_receipt, "To Be Received", "")


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
