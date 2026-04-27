# Copyright (c) 2026, Akhilam Inc and Contributors
# See license.txt

import json
import frappe
from frappe.model.document import Document
from frappe import _


class AetasRazorpayActivityLog(Document):
	@frappe.whitelist()
	def retry_processing(self):
		"""
		Retry processing for a failed inbound webhook.
		"""
		if self.direction != "Inbound":
			frappe.throw(_("Can only retry Inbound activities"))
		
		if not self.request_payload:
			frappe.throw(_("Request payload is missing"))

		from aetas_customization.aetas_customization.api.webhook import (
			_handle_payment_link_paid,
			_handle_payment_link_cancelled,
			_handle_payment_failed,
			update_activity_log
		)

		try:
			payload = json.loads(self.request_payload)
			event = payload.get("event")
			
			# Increment retry count
			self.retry_count = (self.retry_count or 0) + 1
			self.save()
			frappe.db.commit()

			frappe.set_user("Administrator")
			
			result = None
			if event == "payment_link.paid":
				result = _handle_payment_link_paid(payload)
			elif event == "payment_link.cancelled":
				result = _handle_payment_link_cancelled(payload)
			elif event == "payment.failed":
				result = _handle_payment_failed(payload)
			else:
				frappe.throw(_("Unhandled event type: {0}").format(event))

			if result:
				update_activity_log(
					self.name,
					processing_status="Processed",
					response_payload=result,
					link_id=(result or {}).get("link_id"),
					payment_id=(result or {}).get("payment_id"),
					reference_doctype=(result or {}).get("reference_doctype"),
					reference_docname=(result or {}).get("reference_docname"),
				)
				return {"status": "success", "message": _("Successfully retried activity log {0}").format(self.name)}
			
		except Exception as e:
			error_details = frappe.get_traceback()
			update_activity_log(
				self.name,
				processing_status="Failed",
				error_message=f"Retry Failed: {str(e)}\n{error_details}"
			)
			frappe.throw(_("Retry failed: {0}").format(str(e)))

