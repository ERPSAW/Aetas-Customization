# Copyright (c) 2026, Akhilam Inc and Contributors
# See license.txt

import hashlib
import hmac
import json
import frappe
from frappe.utils import flt, now_datetime
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

		# Resolve Boutique from payload to get the correct secret
		boutique_name = _get_boutique_from_payload(payload)
		razorpay_settings = None
		webhook_secret = None
		bypass_signature = False
		
		if boutique_name:
			from payments.payment_gateways.doctype.razorpay_settings.razorpay_settings import RazorpaySettings
			try:
				settings_doc = RazorpaySettings.get_settings_for_boutique(boutique_name)
				# get_settings_for_boutique returns a dict with api_key, api_secret. 
				# We need the webhook_secret from the actual document.
				settings_data = frappe.db.get_value(
					"Razorpay Settings", 
					boutique_name, 
					["webhook_secret", "bypass_webhook_signature"],
					as_dict=True
				)
				if settings_data:
					webhook_secret = settings_data.webhook_secret
					bypass_signature = bool(settings_data.bypass_webhook_signature)
			except Exception:
				pass

		signature = headers.get("X-Razorpay-Signature")
		is_signature_valid = False
		
		if bypass_signature:
			is_signature_valid = True
			frappe.logger().warning(f"Razorpay webhook: Signature validation bypassed for {boutique_name}")
		elif signature and webhook_secret:
			try:
				_validate_webhook_signature(body, signature, webhook_secret)
				is_signature_valid = True
			except Exception:
				is_signature_valid = False

		activity_log = create_activity_log(
			direction="Inbound",
			activity_type=event,
			processing_status="Received",
			event_id=event_id,
			payload_hash=payload_hash,
			source_ip=source_ip,
			request_payload=payload,
			signature_valid=is_signature_valid,
		)

		if not is_signature_valid and webhook_secret:
			update_activity_log(
				activity_log,
				processing_status="Failed",
				error_message="Invalid Webhook Signature",
			)
			return {"status": "error", "message": "Invalid Signature"}, 401

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

		# Run as Administrator to bypass all permission checks during financial document creation
		frappe.set_user("Administrator")

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
		error_details = frappe.get_traceback()
		frappe.logger().error(f"Razorpay webhook handler error: {str(e)}\nTraceback: {error_details}")
		if activity_log:
			update_activity_log(
				activity_log,
				processing_status="Failed",
				error_message=f"{str(e)}\n\n{error_details}",
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
	
	validated_via_library = False
	try:
		import razorpay
		client = razorpay.Client(auth=("ANY", "ANY"))
		client.utility.verify_webhook_signature(payload_str, signature, webhook_secret)
		validated_via_library = True
		frappe.logger().info("Razorpay webhook: Signature validated via razorpay library")
	except ImportError:
		pass
	except Exception as e:
		frappe.logger().warning(f"Razorpay library signature validation failed: {str(e)}")

	if not hmac.compare_digest(expected_signature, signature) and not validated_via_library:
		frappe.logger().error("Razorpay webhook: Signature validation failed (Manual and Library)")
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
			[
				"name",
				"reference_doctype",
				"reference_docname",
				"status",
				"amount",
				"boutique",
				"razorpay_payment_id",
			],
			as_dict=True
		)
		arpl = frappe._dict(arpl or {})
		
		if not arpl.get("name"):
			frappe.logger().warning(f"Razorpay webhook: No ARPL found for link_id {razorpay_link_id}")
			frappe.throw(_("No payment link record found for link ID {0}").format(razorpay_link_id))
		
		# Idempotency guard — if already paid, skip
		if arpl.get("status") == "Paid":
			frappe.logger().info(f"Razorpay webhook: ARPL {arpl.name} already paid, skipping")
			return {
				"status": "already_paid",
				"link_id": razorpay_link_id,
				"payment_id": arpl.razorpay_payment_id,
				"reference_doctype": arpl.reference_doctype,
				"reference_docname": arpl.reference_docname,
			}

		# Business-level idempotency guard: this payment id is already posted.
		if razorpay_payment_id and frappe.db.exists(
			"Payment Entry",
			{"reference_no": razorpay_payment_id, "docstatus": 1},
		):
			frappe.logger().info(
				f"Razorpay webhook: Payment Entry already exists for payment_id {razorpay_payment_id}, skipping"
			)
			frappe.db.set_value(
				"Aetas Razorpay Payment Link",
				arpl.name,
				{"status": "Paid", "razorpay_payment_id": razorpay_payment_id},
			)
			return {
				"status": "already_paid",
				"link_id": razorpay_link_id,
				"payment_id": razorpay_payment_id,
				"reference_doctype": arpl.reference_doctype,
				"reference_docname": arpl.reference_docname,
			}
		
		# Create Payment Entry
		source_doctype = arpl.reference_doctype
		source_docname = arpl.reference_docname
		source_doc = frappe.get_doc(source_doctype, source_docname)
		
		resolved_amount = amount or int((arpl.amount or 0) * 100)
		
		# Extract fee from payment entity if available
		payment_fee = 0
		payment_data = payload.get("payload", {}).get("payment", {}).get("entity", {})
		if payment_data and payment_data.get("fee"):
			payment_fee = payment_data.get("fee")
			
		pe = _create_payment_entry(arpl, source_doc, resolved_amount, razorpay_payment_id, payment_fee)
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
			# Payment Entry submit hooks may already have updated the APR. Reload to avoid
			# saving a stale document copy and triggering TimestampMismatchError.
			source_doc = frappe.get_doc(source_doctype, source_docname)

			# Payment Entry on_submit hook normally appends this row. Keep a fallback append
			# in case hook execution is bypassed for any reason.
			existing_row = any((row.payment_entry == pe.name) for row in (source_doc.payment_details or []))
			if not existing_row:
				source_doc.append("payment_details", {
					"payment_entry": pe.name,
					"amount": resolved_amount / 100.0,
					"sales_invoice": None,
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
			["name", "reference_doctype", "reference_docname", "status"],
			as_dict=True
		)
		arpl = frappe._dict(arpl or {})
		
		if not arpl.get("name"):
			return {"status": "missing_tracker", "link_id": razorpay_link_id}

		if arpl.get("status") == "Paid":
			return {
				"status": "already_paid",
				"link_id": razorpay_link_id,
				"reference_doctype": arpl.reference_doctype,
				"reference_docname": arpl.reference_docname,
			}

		if arpl.get("status") == "Cancelled":
			return {
				"status": "cancelled",
				"link_id": razorpay_link_id,
				"reference_doctype": arpl.reference_doctype,
				"reference_docname": arpl.reference_docname,
			}
		
		# Update ARPL status
		frappe.db.set_value(
			"Aetas Razorpay Payment Link",
			arpl.name,
			{"status": "Cancelled"}
		)
		frappe.logger().info(f"Razorpay webhook: Marked ARPL {arpl.name} as Cancelled")
		
		# Update source document status to Failed (if APR)
		if arpl.reference_doctype == "Aetas Advance Payment Receipt":
			current_status = frappe.db.get_value(
				arpl.reference_doctype,
				arpl.reference_docname,
				"status",
			)
			if current_status == "Paid":
				return {
					"status": "already_paid",
					"reference_doctype": arpl.reference_doctype,
					"reference_docname": arpl.reference_docname,
				}

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
		payment_notes = payment_data.get("notes") or {}
		
		if not razorpay_payment_id and not payment_notes:
			frappe.logger().error("Razorpay webhook: Missing payment.id in failed event")
			return {"status": "ignored"}
		
		# Find ARPL by razorpay_payment_id
		arpl = frappe.db.get_value(
			"Aetas Razorpay Payment Link",
			{"razorpay_payment_id": razorpay_payment_id},
			["name", "reference_doctype", "reference_docname", "status"],
			as_dict=True
		)
		arpl = frappe._dict(arpl or {})

		if not arpl.get("name"):
			fallback_reference_doctype = payment_notes.get("reference_doctype")
			fallback_reference_docname = payment_notes.get("reference_docname")
			if fallback_reference_doctype and fallback_reference_docname:
				arpl = frappe.db.get_value(
					"Aetas Razorpay Payment Link",
					{
						"reference_doctype": fallback_reference_doctype,
						"reference_docname": fallback_reference_docname,
						"status": ["in", ["Created", "Failed", "Cancelled"]],
					},
					["name", "reference_doctype", "reference_docname", "status"],
					as_dict=True,
				)
				arpl = frappe._dict(arpl or {})
		
		if not arpl.get("name"):
			# Payment failed before link capture — nothing to update
			frappe.logger().warning(f"Razorpay webhook: No ARPL found for payment {razorpay_payment_id}")
			return {"status": "missing_tracker", "payment_id": razorpay_payment_id}

		if arpl.get("status") == "Paid":
			return {
				"status": "already_paid",
				"payment_id": razorpay_payment_id,
				"reference_doctype": arpl.reference_doctype,
				"reference_docname": arpl.reference_docname,
			}

		if arpl.get("status") == "Failed":
			return {
				"status": "failed",
				"payment_id": razorpay_payment_id,
				"reference_doctype": arpl.reference_doctype,
				"reference_docname": arpl.reference_docname,
			}
		
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


def _create_payment_entry(arpl, source_doc, amount, razorpay_payment_id, payment_fee=0):
	"""
	Create a Payment Entry for the successful payment.
	
	Handles charge accounting (Option A or Option B) based on boutique settings.
	"""
	from erpnext.accounts.doctype.journal_entry.journal_entry import get_default_bank_cash_account
	from erpnext.accounts.party import get_party_account
	from erpnext.accounts.utils import get_account_currency
	from payments.payment_gateways.doctype.razorpay_settings.razorpay_settings import RazorpaySettings

	amount_in_inr = flt(amount) / 100.0  # Razorpay returns amount in paise
	customer = source_doc.get("customer")
	if not customer:
		frappe.throw(
			_("Customer is required on {0} {1} for Payment Entry creation.").format(
				arpl.reference_doctype,
				arpl.reference_docname,
			)
		)

	company = (
		source_doc.get("company")
		or frappe.defaults.get_user_default("Company")
		or frappe.defaults.get_global_default("company")
	)
	if not company:
		frappe.throw(_("Default company is not configured for webhook payment posting."))

	party_account = get_party_account("Customer", customer, company)
	if not party_account:
		frappe.throw(
			_("Could not resolve receivable account for customer {0} in company {1}.").format(
				customer,
				company,
			)
		)

	# Resolve bank account as Administrator to bypass balance permission checks
	bank = frappe.get_all(
		"Account",
		filters={"company": company, "account_type": ["in", ["Bank", "Cash"]], "is_group": 0},
		limit=1
	)
	
	# Try specific mode of payment mapping if available in ERPNext
	if source_doc.get("mode_of_payment"):
		mop_bank = frappe.db.get_value("Mode of Payment Account", 
			{"parent": source_doc.get("mode_of_payment"), "company": company}, "default_account")
		if mop_bank:
			bank = [{"account": mop_bank}]

	if not bank:
		frappe.throw(
			_("Could not resolve default Bank/Cash account for company {0}.").format(company)
		)
	
	bank_account = bank[0].account if hasattr(bank[0], "account") else bank[0].get("account")
	bank = {"account": bank_account}

	# Fetch boutique settings for charge accounting
	boutique = source_doc.get("boutique")
	from payments.payment_gateways.doctype.razorpay_settings.razorpay_settings import RazorpaySettings
	
	# Get settings as document to ensure we have all fields including charge_account
	razorpay_settings_data = RazorpaySettings.get_settings_for_boutique(boutique)
	razorpay_settings = frappe.get_doc("Razorpay Settings", razorpay_settings_data.get("doc_name"))
	
	total_fee = flt(payment_fee) / 100.0  # Convert paise to INR
	charge_account = razorpay_settings.get("charge_account")
	accounting_option = razorpay_settings.get("charge_accounting_option")

	frappe.logger().info(f"Razorpay webhook: Accounting Option={accounting_option}, Charge Account={charge_account}, Payload Fee={total_fee}")

	posting_date = source_doc.get("date") or now_datetime().date()

	pe = frappe.new_doc("Payment Entry")

	# Logic for total_fee is now directly from payload
	pe.posting_date = posting_date

	pe.payment_type = "Receive"
	pe.party_type = "Customer"
	pe.party = customer
	pe.mode_of_payment = source_doc.get("mode_of_payment")
	pe.paid_from = party_account
	pe.paid_to = bank.get("account")
	pe.paid_from_account_currency = get_account_currency(party_account)
	pe.paid_to_account_currency = get_account_currency(bank.get("account"))
	pe.paid_amount = amount_in_inr
	pe.received_amount = amount_in_inr
	
	# Option A: Deduction in Payment Entry
	if accounting_option == "Option A" and total_fee > 0 and charge_account:
		pe.received_amount = flt(amount_in_inr - total_fee, pe.precision("received_amount"))
		
		# Resolve Cost Center from Boutique
		cost_center = None
		if boutique:
			cost_center = frappe.db.get_value("Boutique", boutique, "boutique_cost_center")
		
		if not cost_center:
			cost_center = frappe.get_cached_value("Company", company, "cost_center")

		pe.append("deductions", {
			"account": charge_account,
			"cost_center": cost_center,
			"amount": total_fee
		})

	pe.reference_no = razorpay_payment_id
	pe.reference_date = now_datetime().date()
	pe.remarks = f"Razorpay Payment Link: {arpl.link_id}"
	
	# Keep APR backlink for later traceability and APR status synchronization hooks.
	pe.custom_advance_payment_receipt = arpl.reference_docname if arpl.reference_doctype == "Aetas Advance Payment Receipt" else None
	
	pe.insert(ignore_permissions=True)
	pe.submit()

	# Option B: Separate Journal Entry (Post-Submit)
	if accounting_option == "Option B" and total_fee > 0 and charge_account:
		_create_fee_journal_entry(pe, total_fee, charge_account, boutique)
	
	return pe


def _create_fee_journal_entry(pe, total_fee, charge_account, boutique):
	"""Creates a separate Journal Entry for Razorpay fees (Option B)."""
	cost_center = None
	if boutique:
		cost_center = frappe.db.get_value("Boutique", boutique, "boutique_cost_center")
	
	if not cost_center:
		cost_center = frappe.get_cached_value("Company", pe.company, "cost_center")

	je = frappe.new_doc("Journal Entry")
	je.company = pe.company
	je.posting_date = pe.posting_date
	je.voucher_type = "Journal Entry"
	je.multi_currency = 1
	
	je.append("accounts", {
		"account": charge_account,
		"debit_in_account_currency": total_fee,
		"cost_center": cost_center
	})
	
	je.append("accounts", {
		"account": pe.paid_to,
		"credit_in_account_currency": total_fee,
		"cost_center": cost_center
	})

	je.user_remark = f"Razorpay Transaction Fee for {pe.name} ({pe.reference_no})"
	je.insert(ignore_permissions=True)
	je.submit()
	
	return je


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
	
	# Determine status based on amounts
	if paid_amount >= total_amount:
		source_doc.status = "Received" if source_doc.doctype == "Aetas Advance Payment Receipt" else "Paid"
	elif paid_amount > 0:
		source_doc.status = "Partially Received" if source_doc.doctype == "Aetas Advance Payment Receipt" else "Partially Paid"
	else:
		source_doc.status = "To Be Received" if source_doc.doctype == "Aetas Advance Payment Receipt" else "Created"
	
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


def _get_boutique_from_payload(payload):
	"""
	Extract the boutique name from the Razorpay webhook payload notes.
	"""
	notes = {}
	# Check order notes, payment_link notes, or payment notes
	payload_data = payload.get("payload", {})
	for entity_key in ["order", "payment_link", "payment"]:
		entity_notes = payload_data.get(entity_key, {}).get("entity", {}).get("notes", {})
		if entity_notes:
			notes.update(entity_notes)
	
	ref_doctype = notes.get("reference_doctype")
	ref_docname = notes.get("reference_docname")
	
	if ref_doctype and ref_docname:
		# Cross-reference with ARPL to get the boutique
		boutique = frappe.db.get_value(
			"Aetas Razorpay Payment Link",
			{"reference_doctype": ref_doctype, "reference_docname": ref_docname},
			"boutique"
		)
		return boutique
	
	# Fallback: check link_id directly
	link_id = payload_data.get("payment_link", {}).get("entity", {}).get("id")
	if link_id:
		return frappe.db.get_value("Aetas Razorpay Payment Link", {"link_id": link_id}, "boutique")
		
	return None
