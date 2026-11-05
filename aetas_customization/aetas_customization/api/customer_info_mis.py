# Copyright (c) 2026, Akhilam Inc and contributors
# For license information, please see license.txt

"""Daily Customer Info MIS email, configured in Customer Info MIS Settings."""

import frappe
from frappe.utils import get_time, now_datetime

SETTINGS_DOCTYPE = "Customer Info MIS Settings"
REPORT_NAME = "Customer Info"
MAX_ROWS = 100000
SENT_CACHE_EXPIRY_SEC = 90000  # 25 h, clears before the next day's window

# Attachment Format option -> (Auto Email Report format, file extension)
FORMATS = {
	"CSV": ("CSV", "csv"),
}



def check_and_send_customer_info_mis():
	"""Hourly job: send once a day, in the hour set in Send Time."""
	try:
		settings = frappe.get_single(SETTINGS_DOCTYPE)
		if not is_ready(settings):
			return

		now = now_datetime()
		if now.hour != get_time(settings.send_time).hour:
			return

		cache_key = f"customer_info_mis_sent_{now.date()}"
		if frappe.cache().get_value(cache_key):
			return

		send_mail(settings)
		frappe.cache().set_value(cache_key, 1, expires_in_sec=SENT_CACHE_EXPIRY_SEC)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Customer Info MIS Email")


@frappe.whitelist()
def send_customer_info_mis():
	"""Send the email now. Used by the Send Now button."""
	frappe.only_for("System Manager")
	settings = frappe.get_single(SETTINGS_DOCTYPE)
	if not get_recipients(settings):
		frappe.throw("Add at least one email in Email Recipients.")
	if settings.attachment_format not in FORMATS:
		frappe.throw("Select an Attachment Format.")

	send_mail(settings)


def is_ready(settings):
	return (
		settings.enabled
		and settings.send_time
		and settings.attachment_format in FORMATS
		and get_recipients(settings)
	)


def send_mail(settings):
	subject = settings.email_subject or REPORT_NAME
	frappe.sendmail(
		recipients=get_recipients(settings),
		subject=subject,
		message=settings.email_message or "",
		attachments=[build_attachment(settings, subject)],
	)


def build_attachment(settings, subject):
	"""Reuse Frappe's Auto Email Report code to build the attachment file."""
	report_format, extension = FORMATS[settings.attachment_format]
	report = frappe.get_doc(
		{
			"doctype": "Auto Email Report",
			"name": subject,
			"report": REPORT_NAME,
			"report_type": "Script Report",
			"user": "Administrator",
			"format": report_format,
			"no_of_rows": MAX_ROWS,
		}
	)
	file_name = f"{REPORT_NAME.replace(' ', '-')}-{now_datetime().date()}.{extension}"
	return {"fname": file_name, "fcontent": report.get_report_content()}


def get_recipients(settings):
	return [row.email for row in settings.email_recipients or [] if row.email]
