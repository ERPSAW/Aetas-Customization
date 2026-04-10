# Copyright (c) 2024, Akhilam Inc and contributors
# For license information, please see license.txt

import datetime

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class AetasAdvancePaymentReceipt(Document):
	def validate(self):
		if not self.customer:
			frappe.throw(_("Customer is required."))

		if not self.boutique:
			frappe.throw(_("Boutique is required for payment processing."))

		if not self.paid_amount or self.paid_amount <= 0:
			frappe.throw(_("Paid Amount must be greater than zero."))

		if self.utr_no:
			duplicate_name = frappe.db.exists(
				"Aetas Advance Payment Receipt",
				{
					"name": ["!=", self.name],
					"customer": self.customer,
					"utr_no": self.utr_no,
				},
			)
			if duplicate_name:
				frappe.throw(_("UTR No must be unique for the same customer."))

		if self.status == "Received" and not self.payment_entry:
			frappe.throw(_("Payment Entry is required when status is Received."))

	def get_outstanding_amount(self):
		"""Return the amount still outstanding on this receipt (paid_amount minus submitted PEs)."""
		paid = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(paid_amount), 0)
			FROM `tabPayment Entry`
			WHERE custom_advance_payment_receipt = %s
			  AND docstatus = 1
			""",
			self.name,
		)[0][0]
		return flt(self.paid_amount) - flt(paid)


@frappe.whitelist()
def generate_payment_link_for_apr(apr_name, amount):
	"""
	Generate a Razorpay payment link for an Advance Payment Receipt.

	Args:
		apr_name (str): Name of the Aetas Advance Payment Receipt document.
		amount (float): Amount in INR to generate the link for.

	Returns:
		dict: {link_url, link_id, amount, expire_by}
	"""
	from payments.payment_gateways.doctype.razorpay_settings.razorpay_settings import (
		RazorpaySettings,
	)

	amount = flt(amount)
	apr = frappe.get_doc("Aetas Advance Payment Receipt", apr_name)
	outstanding = apr.get_outstanding_amount()

	if frappe.db.exists(
		"Aetas Razorpay Payment Link",
		{"reference_docname": apr_name, "status": "Paid"},
	):
		frappe.throw(
			_("A payment has already been completed for this Advance Payment Receipt.")
		)

	if amount <= 0:
		frappe.throw(_("Payment amount must be greater than zero."))
	if amount > outstanding:
		frappe.throw(
			_("Payment amount {0} exceeds outstanding amount {1}.").format(
				frappe.format_value(amount, {"fieldtype": "Currency"}),
				frappe.format_value(outstanding, {"fieldtype": "Currency"}),
			)
		)

	settings_dict = RazorpaySettings.get_settings_for_boutique(apr.boutique)
	settings_doc = frappe.get_doc("Razorpay Settings", settings_dict["doc_name"])
	settings_doc.init_client()

	customer_name = (
		frappe.db.get_value("Customer", apr.customer, "customer_name") or apr.customer
	)

	link = settings_doc.create_payment_link(
		amount_inr=amount,
		currency="INR",
		customer_name=customer_name,
		customer_contact="",
		customer_email="",
		description="Payment for Advance Receipt " + apr_name,
		reference_doctype="Aetas Advance Payment Receipt",
		reference_docname=apr_name,
	)

	expire_by_dt = None
	if link.get("expire_by"):
		expire_by_dt = datetime.datetime.utcfromtimestamp(link["expire_by"])

	tracker = frappe.new_doc("Aetas Razorpay Payment Link")
	tracker.reference_doctype = "Aetas Advance Payment Receipt"
	tracker.reference_docname = apr_name
	tracker.boutique = apr.boutique
	tracker.amount = amount
	tracker.currency = "INR"
	tracker.link_id = link.get("id")
	tracker.link_url = link.get("short_url")
	tracker.status = "Created"
	if expire_by_dt:
		tracker.expire_by = expire_by_dt
	tracker.insert(ignore_permissions=True)

	return {
		"link_url": link.get("short_url"),
		"link_id": link.get("id"),
		"amount": amount,
		"expire_by": str(expire_by_dt) if expire_by_dt else "",
	}

