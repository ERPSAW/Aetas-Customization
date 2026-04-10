import hashlib
import json

import frappe
from frappe.utils import now_datetime


def _to_json(data):
	if data is None:
		return ""
	if isinstance(data, str):
		return data
	try:
		return json.dumps(data, default=str)
	except Exception:
		return str(data)


def create_activity_log(
	direction,
	activity_type,
	processing_status="Received",
	reference_doctype=None,
	reference_docname=None,
	event_id=None,
	payload_hash=None,
	link_id=None,
	payment_id=None,
	amount=None,
	source_ip=None,
	request_payload=None,
	response_payload=None,
	error_message=None,
	signature_valid=None,
	duplicate_of=None,
):
	log = frappe.new_doc("Aetas Razorpay Activity Log")
	log.direction = direction
	log.activity_type = activity_type
	log.processing_status = processing_status
	log.received_at = now_datetime()
	log.reference_doctype = reference_doctype
	log.reference_docname = reference_docname
	log.event_id = event_id
	log.payload_hash = payload_hash
	log.link_id = link_id
	log.payment_id = payment_id
	log.amount = amount
	log.source_ip = source_ip
	log.request_payload = _to_json(request_payload)
	log.response_payload = _to_json(response_payload)
	log.error_message = error_message or ""
	if signature_valid is not None:
		log.signature_valid = 1 if signature_valid else 0
	if duplicate_of:
		log.duplicate_of = duplicate_of
	log.insert(ignore_permissions=True)
	return log.name


def update_activity_log(log_name, **kwargs):
	if not log_name:
		return

	updates = {}
	for key, value in kwargs.items():
		if key in {"request_payload", "response_payload"}:
			updates[key] = _to_json(value)
		elif key == "signature_valid" and value is not None:
			updates[key] = 1 if value else 0
		else:
			updates[key] = value

	updates["processed_at"] = now_datetime()
	frappe.db.set_value("Aetas Razorpay Activity Log", log_name, updates)


def get_duplicate_inbound_log(event_id=None, payload_hash=None, exclude_name=None):
	filters = {"direction": "Inbound"}
	if event_id:
		filters["event_id"] = event_id
	elif payload_hash:
		filters["payload_hash"] = payload_hash
	else:
		return None

	match = frappe.db.get_value("Aetas Razorpay Activity Log", filters, "name")
	if match and exclude_name and match == exclude_name:
		return None
	return match


def compute_payload_hash(payload_text):
	return hashlib.sha256((payload_text or "").encode("utf-8")).hexdigest()


def cleanup_old_activity_logs(days=30):
	frappe.db.sql(
		"""
		DELETE FROM `tabAetas Razorpay Activity Log`
		WHERE received_at < DATE_SUB(NOW(), INTERVAL %s DAY)
		""",
		(days,),
	)
	frappe.db.commit()
