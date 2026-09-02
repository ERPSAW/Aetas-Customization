# Copyright (c) 2026, Akhilam Inc and contributors
# For license information, please see license.txt

"""Naming-series driven defaults for Sales and Purchase Invoices.

Cost Center, Warehouse and Addresses used to be set by a Client Script holding a
hardcoded switch over ~50 naming series, so every new boutique needed a code
change.  They now come from the `Invoice Series Configuration` DocType: adding a
series is a data entry, not a deployment.

Cost Center is the one field a hand-picked value survives on: the form fills it
from the series, and whatever is on the invoice at save time is kept.

The fiscal-year segment is normalised away before matching, so one entry per
boutique covers every year: `BN/.FY./.#####`, `BN/25-26/.#####` and next April's
`BN/26-27/.#####` all resolve to the same row.  Counter width is normalised too,
since the sales-return series use `.###` where sales use `.#####`.
"""

import re

import frappe
from frappe import _

CACHE_KEY = "aetas_invoice_series_config"

# Fiscal-year segment in any form Frappe or the site uses:
#   .FY.  .YYYY.  .YY.  25-26  2025-26  2025-2026
_FISCAL_YEAR = re.compile(
	r"(?:\.FY\.)|(?:\.YYYY\.)|(?:\.YY\.)|(?:\b\d{2,4}-\d{2,4}\b)",
	flags=re.IGNORECASE,
)
# The counter: ##### or .#####
_COUNTER = re.compile(r"\.?#+")


def normalize_series(series: str | None) -> str:
	"""Reduce a naming series to a fiscal-year and counter-width agnostic key.

	    'BN/.FY./.#####'   -> 'BN/{FY}/{N}'
	    'BN/25-26/.#####'  -> 'BN/{FY}/{N}'
	    'SRBN/.FY./.###'   -> 'SRBN/{FY}/{N}'

	Note this deliberately eats any `NN-NN` run, so a boutique code containing
	one would collide.  None of the codes in use do; see the test that pins
	every live series through this function.
	"""
	if not series:
		return ""

	key = _FISCAL_YEAR.sub("{FY}", series.strip().upper())
	key = _COUNTER.sub("{N}", key)
	key = re.sub(r"/{2,}", "/", key)  # '.FY./' -> '{FY}/' can leave '//'
	return key.strip("/. ")

# invoice fieldname -> Invoice Series Configuration fieldname
FIELD_MAP = {
	"Sales Invoice": {
		"cost_center": "cost_center",
		"set_warehouse": "set_warehouse",
		"company_address": "billing_address",
	},
	"Purchase Invoice": {
		"cost_center": "cost_center",
		"set_warehouse": "set_warehouse",
		"billing_address": "billing_address",
	},
}

CONFIG_FIELDS = [
	"document_type",
	"naming_series",
	"cost_center",
	"set_warehouse",
	"billing_address",
]


def _cache_key(document_type: str, naming_series: str) -> str:
	return f"{document_type}||{normalize_series(naming_series)}"


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
		if not value:
			continue

		# Cost Center is the one field the user may keep: the form fetches the
		# series value the moment the series is picked, so anything sitting here
		# afterwards was put there deliberately and re-deriving it would throw
		# that away.  Warehouse and Addresses stay series-driven —
		# india_compliance reads GSTIN and place of supply off the addresses.
		if doc_field == "cost_center" and doc.get("cost_center"):
			continue

		doc.set(doc_field, value)


def propagate_cost_center_to_items(doc, method=None):
	"""Keep item rows on the invoice's Cost Center, without burying an override.

	Hooked on `before_validate` right after `apply_series_config`, so the header
	is already resolved and the rows are filled before ERPNext's
	`set_missing_values` runs.  That ordering is what keeps the Item Default /
	company default (`Main - AOT`) off the rows: set_missing_values only fills a
	row's `cost_center` when it is empty, and never overwrites one that is set
	(`accounts_controller`: `elif fieldname in ["cost_center", ...] and not
	item.get(fieldname)`; `cost_center` is not in `force_item_fields` either).

	A row that was carrying the header value follows it when the header moves; a
	row deliberately set to a different Cost Center is left where it is.  The
	previously saved header is what tells the two apart — on a new invoice there
	is none, so whatever the form put on the row stands.
	"""
	if doc.docstatus != 0 or not doc.cost_center:
		return

	previous = doc.get_doc_before_save()
	was_following = previous.cost_center if previous else None

	for row in doc.get("items") or []:
		current = row.get("cost_center")
		if current and current != was_following:
			continue

		row.cost_center = doc.cost_center


@frappe.whitelist()
def get_series_defaults(document_type: str, naming_series: str) -> dict:
	"""The invoice fields a series would set, keyed by invoice fieldname.

	Lets the form fill Cost Center / Warehouse / Address the moment the series is
	picked, instead of leaving them blank until save.  `apply_series_config` still
	runs server side and stays the authority — this only moves the same values
	forward so the user can see and override them.

	Returns an empty dict for an unconfigured series; the form leaves the fields
	alone and the save-time throw remains the thing that reports it.
	"""
	field_map = FIELD_MAP.get(document_type)
	if not field_map:
		return {}

	config = get_config(document_type, naming_series)
	if not config:
		return {}

	return {
		doc_field: config.get(config_field)
		for doc_field, config_field in field_map.items()
		if config.get(config_field)
	}


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
