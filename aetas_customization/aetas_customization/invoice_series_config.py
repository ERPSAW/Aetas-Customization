# Copyright (c) 2026, Akhilam Inc and contributors
# For license information, please see license.txt

"""Naming-series driven defaults for Sales and Purchase Invoices.

Cost Center, Warehouse and Addresses used to be set by a Client Script holding a
hardcoded switch over ~50 naming series, so every new boutique needed a code
change.  They now come from the `Invoice Series Configuration` DocType: adding a
series is a data entry, not a deployment.

Matching is exact — the stored `naming_series` string is looked up verbatim, so
`BN/.FY./.#####` and `BN/25-26/.#####` are separate entries.
"""

import frappe
from frappe import _

CACHE_KEY = "aetas_invoice_series_config"

# invoice fieldname -> Invoice Series Configuration fieldname
FIELD_MAP = {
	"Sales Invoice": {
		"cost_center": "cost_center",
		"set_warehouse": "set_warehouse",
		"company_address": "billing_address",
		"dispatch_address_name": "shipping_address",
	},
	"Purchase Invoice": {
		"cost_center": "cost_center",
		"set_warehouse": "set_warehouse",
		"billing_address": "billing_address",
		"shipping_address": "shipping_address",
	},
}

CONFIG_FIELDS = [
	"document_type",
	"naming_series",
	"cost_center",
	"set_warehouse",
	"billing_address",
	"shipping_address",
]


def _cache_key(document_type: str, naming_series: str) -> str:
	return f"{document_type}||{(naming_series or '').strip()}"


def _build_index() -> dict:
	"""All enabled entries keyed by document type + naming series."""
	rows = frappe.get_all(
		"Invoice Series Configuration",
		filters={"enabled": 1},
		fields=CONFIG_FIELDS,
		ignore_permissions=True,
	)
	return {_cache_key(row.document_type, row.naming_series): row for row in rows}


def get_config(document_type: str, naming_series: str):
	"""Return the configuration row for a series, or None if not configured."""
	index = frappe.cache().get_value(CACHE_KEY)
	if index is None:
		index = _build_index()
		# The TTL only bounds staleness if a row is changed via frappe.db.set_value,
		# which skips the controller's on_update invalidation.
		frappe.cache().set_value(CACHE_KEY, index, expires_in_sec=3600)

	return index.get(_cache_key(document_type, naming_series))


def clear_series_config_cache():
	frappe.cache().delete_value(CACHE_KEY)


def apply_series_config(doc, method=None):
	"""Set Cost Center / Warehouse / Addresses from the series configuration.

	Hooked on Sales Invoice `validate` and Purchase Invoice `before_validate`.
	"""
	field_map = FIELD_MAP.get(doc.doctype)
	if not field_map:
		return

	# Submitted and cancelled documents keep whatever they were posted with —
	# re-deriving them would rewrite accounting on historical entries.
	if doc.docstatus != 0:
		return

	config = get_config(doc.doctype, doc.naming_series)
	if not config:
		frappe.throw(
			_(
				"No configuration entry found for this Naming Series. "
				"Please create an entry in Invoice Series Configuration first."
			),
			title=_("Missing Invoice Series Configuration"),
		)

	for doc_field, config_field in field_map.items():
		value = config.get(config_field)
		if value:
			doc.set(doc_field, value)


@frappe.whitelist()
def get_unconfigured_series(from_date: str | None = None) -> dict:
	"""Series in use on invoices that have no enabled configuration entry.

	Run this before enabling the hook on a live site: every series listed here
	would start throwing at save time.
	"""
	frappe.only_for("System Manager")

	from_date = from_date or frappe.utils.add_years(frappe.utils.today(), -1)
	report = {}

	for doctype in FIELD_MAP:
		used = frappe.get_all(
			doctype,
			fields=["naming_series", "count(name) as count"],
			filters={"creation": (">", from_date), "naming_series": ("is", "set")},
			group_by="naming_series",
			order_by="count desc",
		)
		configured = {
			row.naming_series
			for row in frappe.get_all(
				"Invoice Series Configuration",
				filters={"document_type": doctype, "enabled": 1},
				fields=["naming_series"],
			)
		}
		report[doctype] = [
			{"naming_series": row.naming_series, "count": row.count}
			for row in used
			if row.naming_series not in configured
		]

	return report
