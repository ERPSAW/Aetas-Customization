
import frappe
from frappe.desk.reportview import get_filters_cond, get_match_cond


def on_submit(self,method):
    if self.custom_advance_payment_receipt:
        frappe.db.set_value("Aetas Advance Payment Receipt",self.custom_advance_payment_receipt,"status","Received")
        frappe.db.set_value("Aetas Advance Payment Receipt",self.custom_advance_payment_receipt,"payment_entry",self.name)

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def custom_query(doctype, txt, searchfield, start, page_len, filters):
    return frappe.db.sql("""
        SELECT name
        FROM `tabAetas Advance Payment Receipt`
        WHERE customer = %(customer)s and status = "To Be Received"
        {mcond}
    """.format(
        mcond=get_match_cond(doctype)
    ), {
        "customer": filters.get("customer"),
    })
