# import frappe
# from frappe.model.document import Document

# from aetas_customization.aetas_customization.api.insurance_certificate import (
#     enqueue_insurance_certificate_generation,
# )

# class RetroClaimInsurancePolicy(Document):

#     def on_submit(self):
#         invoice = frappe.get_doc(
#             "Sales Invoice",
#             self.sales_invoice
#         )

#         enqueue_insurance_certificate_generation(invoice)

#         frappe.db.set_value(
#             "Sales Invoice",
#             invoice.name,
#             "custom_apply_insurance",
#             1,
#             update_modified=True
#         )


import frappe
from frappe.model.document import Document

from aetas_customization.aetas_customization.api.insurance_certificate import (
    enqueue_insurance_certificate_generation,
)

class RetroClaimInsurancePolicy(Document):

    def validate(self):
        if not self.get("boutique"):
            frappe.throw(frappe._("Please select a Boutique before submitting."))

    def on_submit(self):
        invoice = frappe.get_doc(
            "Sales Invoice",
            self.sales_invoice
        )

        # If the invoice didn't have a boutique set, propagate the one
        # picked here so the certificate job can resolve the naming series.
        if not invoice.get("custom_boutique"):
            frappe.db.set_value(
                "Sales Invoice",
                invoice.name,
                "custom_boutique",
                self.boutique,
                update_modified=True,
            )
            invoice.reload()

        enqueue_insurance_certificate_generation(invoice)

        frappe.db.set_value(
            "Sales Invoice",
            invoice.name,
            "custom_apply_insurance",
            1,
            update_modified=True
        )