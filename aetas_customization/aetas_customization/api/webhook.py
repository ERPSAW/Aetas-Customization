# Copyright (c) 2026, Akhilam Inc and Contributors
# See license.txt

import hashlib
import hmac
import json
import frappe
from frappe.utils import now_datetime
from frappe import _

from aetas_customization.aetas_customization.api.razorpay_activity_log import (
	compute_payload_hash,
	create_activity_log,
	get_duplicate_inbound_log,
	update_activity_log,
)


@frappe.whitelist(allow_guest=True)
def handle_razorpay_webhook():
	"""
	Webhook endpoint for Razorpay payment link events.
	Handles payment.captured, payment_link.paid, and payment_link.cancelled events.
	
	Expected webhook signature validation via HMAC-SHA256.
	"""
	activity_log = None
	try:
		request = frappe.request
		body = request.get_data(as_text=True)
		headers = request.headers or {}
		event_id = headers.get("X-Razorpay-Event-Id")
		payload_hash = compute_payload_hash(body)
		source_ip = headers.get("X-Forwarded-For") or getattr(request, "remote_addr", "")

		payload = json.loads(body) if body else {}
		event = payload.get("event") or "unknown"

		activity_log = create_activity_log(
			direction="Inbound",
			activity_type=event,
			processing_status="Received",
			event_id=event_id,
			payload_hash=payload_hash,
			source_ip=source_ip,
			request_payload=payload,
		)

		dedup_log = get_duplicate_inbound_log(
			event_id=event_id,
			payload_hash=payload_hash,
			exclude_name=activity_log,
		)
		if dedup_log:
			update_activity_log(
				activity_log,
				processing_status="Duplicate",
				duplicate_of=dedup_log,
				response_payload={"status": "duplicate", "duplicate_of": dedup_log},
			)
			frappe.logger().info(
				f"Razorpay webhook duplicate detected: {event_id or payload_hash}"
			)
			return {"status": "success", "duplicate": True}, 200

		if event == "unknown":
			update_activity_log(
				activity_log,
				processing_status="Failed",
				error_message="Missing event type",
			)
			return {"status": "error", "message": "Missing event type"}, 400

		frappe.logger().info(f"Razorpay webhook received: {event}")

		if event == "payment_link.paid":
			result = _handle_payment_link_paid(payload)
		elif event == "payment_link.cancelled":
			result = _handle_payment_link_cancelled(payload)
		elif event == "payment.failed":
			result = _handle_payment_failed(payload)
		else:
			result = {"status": "ignored", "message": f"Unhandled event: {event}"}
			frappe.logger().warning(f"Razorpay webhook: Unhandled event type: {event}")

		update_activity_log(
			activity_log,
			processing_status="Processed",
			response_payload=result,
			link_id=(result or {}).get("link_id"),
			payment_id=(result or {}).get("payment_id"),
			reference_doctype=(result or {}).get("reference_doctype"),
			reference_docname=(result or {}).get("reference_docname"),
		)
		return {"status": "success"}, 200

	except Exception as e:
		frappe.logger().error(f"Razorpay webhook handler error: {str(e)}")
		if activity_log:
			update_activity_log(
				activity_log,
				processing_status="Failed",
				error_message=str(e),
			)
		return {"status": "error", "message": str(e)}, 500


def _validate_webhook_signature(payload_str, signature, webhook_secret):
	"""
	Validate Razorpay webhook signature using HMAC-SHA256.
	"""
	if not webhook_secret:
		frappe.logger().warning("Razorpay webhook: No webhook secret configured")
		frappe.throw(_("Razorpay webhook secret not configured for this boutique"))
	
	expected_signature = hmac.new(
		webhook_secret.encode(),
		payload_str.encode(),
		hashlib.sha256
	).hexdigest()
	
	if not hmac.compare_digest(expected_signature, signature):
		frappe.logger().error("Razorpay webhook: Signature validation failed")
		frappe.throw(_("Webhook signature validation failed"))


def _handle_payment_link_paid(payload):
	"""
	Handle payment_link.paid event — create Payment Entry and update APR.
	"""
	try:
		payment_link_data = payload.get("payload", {}).get("payment_link", {}).get("entity", {})
		razorpay_link_id = payment_link_data.get("id")
		razorpay_payment_id = payload.get("payload", {}).get("payment", {}).get("entity", {}).get("id")
		amount = payment_link_data.get("amount")
		
		if not razorpay_link_id:
			frappe.logger().error("Razorpay webhook: Missing payment_link.id")
			frappe.throw(_("Missing payment link ID in webhook payload"))
		
		# Look up the ARPL tracker record
		arpl = frappe.db.get_value(
			"Aetas Razorpay Payment Link",
			{"link_id": razorpay_link_id},
			["name", "reference_doctype", "reference_docname", "status", "amount", "boutique"],
			as_dict=True
		)
		
		if not arpl:
			frappe.logger().warning(f"Razorpay webhook: No ARPL found for link_id {razorpay_link_id}")
			frappe.throw(_("No payment link record found for link ID {0}").format(razorpay_link_id))
		
		# Idempotency guard — if already paid, skip
		if arpl.status == "Paid":
			frappe.logger().info(f"Razorpay webhook: ARPL {arpl.name} already paid, skipping")
			return {
				"status": "already_paid",
				"link_id": razorpay_link_id,
				"reference_doctype": arpl.reference_doctype,
				"reference_docname": arpl.reference_docname,
			}
		
		# Create Payment Entry
		source_doctype = arpl.reference_doctype
		source_docname = arpl.reference_docname
		
		resolved_amount = amount or int((arpl.amount or 0) * 100)
		pe = _create_payment_entry(arpl, resolved_amount, razorpay_payment_id)
		frappe.logger().info(f"Razorpay webhook: Created Payment Entry {pe.name} for {source_doctype} {source_docname}")
		
		# Update ARPL status
		frappe.db.set_value(
			"Aetas Razorpay Payment Link",
			arpl.name,
			{
				"status": "Paid",
				"razorpay_payment_id": razorpay_payment_id
			}
		)
		
		# Insert APR Payment Detail child row (only if source is APR)
		if source_doctype == "Aetas Advance Payment Receipt":
			source_doc = frappe.get_doc(source_doctype, source_docname)
			source_doc.append("payment_details", {
				"payment_entry": pe.name,
				"amount": resolved_amount / 100.0,  # Razorpay returns amount in paise
				"sales_invoice": None
			})
			source_doc.save(ignore_permissions=True)
			
			# Update source document status
			_update_source_status(source_doc)
			frappe.logger().info(f"Razorpay webhook: Updated APR {source_docname} payment details and status")
		
		# Queue notification if customer has email
		_queue_success_notification(source_doctype, source_docname, pe.name)
		return {
			"status": "paid",
			"link_id": razorpay_link_id,
			"payment_id": razorpay_payment_id,
			"reference_doctype": source_doctype,
			"reference_docname": source_docname,
		}
		
	except Exception as e:
		frappe.logger().error(f"Razorpay webhook: Error handling payment_link.paid: {str(e)}")
		raise


def _handle_payment_link_cancelled(payload):
	"""
	Handle payment_link.cancelled event — mark ARPL as failed.
	"""
	try:
		payment_link_data = payload.get("payload", {}).get("payment_link", {}).get("entity", {})
		razorpay_link_id = payment_link_data.get("id")
		
		if not razorpay_link_id:
			frappe.logger().error("Razorpay webhook: Missing payment_link.id in cancelled event")
			return {"status": "ignored"}
		
		# Look up ARPL
		arpl = frappe.db.get_value(
			"Aetas Razorpay Payment Link",
			{"link_id": razorpay_link_id},
			["name", "reference_doctype", "reference_docname"],
			as_dict=True
		)
		
		if not arpl:
			return {"status": "missing_tracker", "link_id": razorpay_link_id}
		
		# Update ARPL status
		frappe.db.set_value(
			"Aetas Razorpay Payment Link",
			arpl.name,
			{"status": "Cancelled"}
		)
		frappe.logger().info(f"Razorpay webhook: Marked ARPL {arpl.name} as Cancelled")
		
		# Update source document status to Failed (if APR)
		if arpl.reference_doctype == "Aetas Advance Payment Receipt":
			frappe.db.set_value(
				arpl.reference_doctype,
				arpl.reference_docname,
				{"status": "Failed"}
			)
			_queue_failure_notification(arpl.reference_doctype, arpl.reference_docname)
			frappe.logger().info(f"Razorpay webhook: Updated {arpl.reference_doctype} {arpl.reference_docname} status to Failed")

		return {
			"status": "cancelled",
			"link_id": razorpay_link_id,
			"reference_doctype": arpl.reference_doctype,
			"reference_docname": arpl.reference_docname,
		}
		
	except Exception as e:
		frappe.logger().error(f"Razorpay webhook: Error handling payment_link.cancelled: {str(e)}")
		raise


def _handle_payment_failed(payload):
	"""
	Handle payment.failed event — mark ARPL and source as failed.
	"""
	try:
		payment_data = payload.get("payload", {}).get("payment", {}).get("entity", {})
		razorpay_payment_id = payment_data.get("id")
		
		if not razorpay_payment_id:
			frappe.logger().error("Razorpay webhook: Missing payment.id in failed event")
			return {"status": "ignored"}
		
		# Find ARPL by razorpay_payment_id
		arpl = frappe.db.get_value(
			"Aetas Razorpay Payment Link",
			{"razorpay_payment_id": razorpay_payment_id},
			["name", "reference_doctype", "reference_docname"],
			as_dict=True
		)
		
		if not arpl:
			# Payment failed before link capture — nothing to update
			frappe.logger().warning(f"Razorpay webhook: No ARPL found for payment {razorpay_payment_id}")
			return {"status": "missing_tracker", "payment_id": razorpay_payment_id}
		
		# Update ARPL
		frappe.db.set_value(
			"Aetas Razorpay Payment Link",
			arpl.name,
			{"status": "Failed"}
		)
		frappe.logger().info(f"Razorpay webhook: Marked ARPL {arpl.name} as Failed")
		
		# Update source document status
		if arpl.reference_doctype == "Aetas Advance Payment Receipt":
			frappe.db.set_value(
				arpl.reference_doctype,
				arpl.reference_docname,
				{"status": "Failed"}
			)
			_queue_failure_notification(arpl.reference_doctype, arpl.reference_docname)
			frappe.logger().info(f"Razorpay webhook: Updated {arpl.reference_doctype} {arpl.reference_docname} status to Failed")

		return {
			"status": "failed",
			"payment_id": razorpay_payment_id,
			"reference_doctype": arpl.reference_doctype,
			"reference_docname": arpl.reference_docname,
		}
		
	except Exception as e:
		frappe.logger().error(f"Razorpay webhook: Error handling payment.failed: {str(e)}")
		raise


def _create_payment_entry(arpl, amount, razorpay_payment_id):
	"""
	Create a Payment Entry for the successful payment.
	
	For now, a minimal stub. In production, this should:
	- Resolve GL accounts from boutique configuration.
	- Handle charge accounting (Option A or Option B).
	- Link back to the source document (APR or SI).
	"""
	amount_in_inr = amount / 100.0  # Razorpay returns amount in paise
	
	# Placeholder: minimal PE structure
	pe = frappe.new_doc("Payment Entry")
	pe.payment_type = "Receive"
	pe.party_type = "Customer"
	pe.reference_no = razorpay_payment_id
	pe.reference_date = now_datetime().date()
	pe.remarks = f"Razorpay Payment Link: {arpl.link_id}"
	
	# This is a stub — real implementation needs boutique GL configurations
	pe.custom_advance_payment_receipt = arpl.reference_docname if arpl.reference_doctype == "Aetas Advance Payment Receipt" else None
	
	pe.insert(ignore_permissions=True)
	pe.submit()
	
	return pe


def _update_source_status(source_doc):
	"""
	Update the source document (APR or SI) status based on paid amount vs total.
	
	Status rules:
	- Unpaid: paid == 0
	- Partially Paid: 0 < paid < total
	- Paid: paid == total
	"""
	total_amount = source_doc.paid_amount
	paid_amount = sum([row.amount for row in source_doc.payment_details])
	
	if paid_amount >= total_amount:
		source_doc.status = "Paid"
	elif paid_amount > 0:
		source_doc.status = "Partially Paid"
	else:
		source_doc.status = "Unpaid"
	
	source_doc.save(ignore_permissions=True)


def _queue_success_notification(doctype, docname, pe_name):
	"""
	Queue a notification to the customer for successful payment.
	Stub — real implementation should send email or log notification.
	"""
	try:
		doc = frappe.get_doc(doctype, docname)
		customer = frappe.get_doc("Customer", doc.customer)
		
		if customer.email:
			frappe.logger().info(f"Queue success notification for customer {doc.customer}: PE {pe_name}")
			# In production: frappe.enqueue("aetas_customization...send_success_email", queue='short', ...)
	except Exception as e:
		frappe.logger().warning(f"Could not queue success notification: {str(e)}")


def _queue_failure_notification(doctype, docname):
	"""
	Queue a notification to the customer for payment failure.
	Stub — real implementation should send email or log notification.
	"""
	try:
		doc = frappe.get_doc(doctype, docname)
		customer = frappe.get_doc("Customer", doc.customer)
		
		if customer.email:
			frappe.logger().info(f"Queue failure notification for customer {doc.customer}")
			# In production: frappe.enqueue("aetas_customization...send_failure_email", queue='short', ...)
	except Exception as e:
		frappe.logger().warning(f"Could not queue failure notification: {str(e)}")
