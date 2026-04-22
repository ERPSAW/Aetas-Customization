# Copyright (c) 2024, Akhilam Inc and contributors
# For license information, please see license.txt

import datetime

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from aetas_customization.aetas_customization.api.razorpay_activity_log import (
	create_activity_log,
	update_activity_log,
)


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

	request_payload = {
		"amount_inr": amount,
		"currency": "INR",
		"customer_name": customer_name,
		"customer_contact": "",
		"customer_email": "",
		"description": "Payment for Advance Receipt " + apr_name,
		"reference_doctype": "Aetas Advance Payment Receipt",
		"reference_docname": apr_name,
	}
	activity_log = create_activity_log(
		direction="Outbound",
		activity_type="payment_link.create",
		processing_status="Received",
		reference_doctype="Aetas Advance Payment Receipt",
		reference_docname=apr_name,
		amount=amount,
		request_payload=request_payload,
	)

	try:
		link = settings_doc.create_payment_link(**request_payload)
	except Exception as e:
		update_activity_log(
			activity_log,
			processing_status="Failed",
			error_message=str(e),
		)
		raise

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

	update_activity_log(
		activity_log,
		processing_status="Processed",
		response_payload=link,
		link_id=link.get("id"),
	)

	return {
		"link_url": link.get("short_url"),
		"link_id": link.get("id"),
		"amount": amount,
		"expire_by": str(expire_by_dt) if expire_by_dt else "",
	}


# ---------------------------------------------------------------------------
# Phase 5b: Link APR Payment to Sales Invoice
# ---------------------------------------------------------------------------

@frappe.whitelist()
def link_payment_to_si(apr_name, child_row_name, si_name):
	"""
	Link an APR Payment Detail row to a Sales Invoice.
	Updates the SI field on the child row and creates an entry in SI Advance child table.
	
	Args:
		apr_name (str): Name of the APR document
		child_row_name (str): Name of the APR Payment Detail child row
		si_name (str): Name of the target Sales Invoice
	
	Returns:
		dict: {status, message}
	"""
	# Validate inputs
	if not apr_name or not child_row_name or not si_name:
		frappe.throw(_("Missing required parameters"))
	
	# Fetch the APR and child row
	apr = frappe.get_doc("Aetas Advance Payment Receipt", apr_name)
	child_row = None
	for row in apr.payment_details:
		if row.name == child_row_name:
			child_row = row
			break
	
	if not child_row:
		frappe.throw(_("Payment Detail row not found"))
	
	# Validate the row is not already linked
	if child_row.sales_invoice:
		frappe.throw(_("This payment row is already linked to Sales Invoice {0}").format(child_row.sales_invoice))
	
	# Validate amount > 0
	if not child_row.amount or child_row.amount <= 0:
		frappe.throw(_("Cannot link payment row with zero or negative amount"))
	
	# Fetch the SI and validate customer match
	si = frappe.get_doc("Sales Invoice", si_name)
	if si.docstatus != 0:
		frappe.throw(_("Sales Invoice must be in Draft status to link an advance payment."))

	if si.customer != apr.customer:
		frappe.throw(_("Sales Invoice customer {0} does not match APR customer {1}").format(si.customer, apr.customer))

	if any(
		row.reference_type == "Payment Entry" and row.reference_name == child_row.payment_entry
		for row in (si.advances or [])
	):
		frappe.throw(_("Payment Entry {0} is already present in Sales Invoice advances.").format(child_row.payment_entry))
	
	# Update the child row's SI field
	child_row.sales_invoice = si_name
	apr.save(ignore_permissions=True)
	
	# Add an entry to the SI Advance child table
	si.append("advances", {
		"reference_type": "Payment Entry",
		"reference_name": child_row.payment_entry,
		"advance_amount": child_row.amount,
		"allocated_amount": 0,
	})
	si.save(ignore_permissions=True)
	
	return {
		"status": "success",
		"message": _("Payment linked to Sales Invoice {0}").format(si_name)
	}


