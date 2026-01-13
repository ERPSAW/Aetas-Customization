import frappe
from erpnext.selling.doctype.customer.customer import Customer

class CustomCustomer(Customer):
    def update_lead_status(self):
        frappe.msgprint("Custom update_lead_status called")
        """If Customer created from Lead, update lead status to "Converted"
        update Customer link in Quotation, Opportunity"""
        if self.lead_name:
            pass
            # frappe.db.set_value("Lead", self.lead_name, "status", "Converted")