# Copyright (c) 2026, Akhilam Inc and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.contacts.doctype.address.address import get_address_display
from frappe.model.document import Document

from aetas_customization.aetas_customization.invoice_series_config import (
	clear_series_config_cache,
	normalize_series,
)


class InvoiceSeriesConfiguration(Document):
	def autoname(self):
		"""Same scheme as the JSON's `format:` expression, but strips first.

		Naming runs before before_validate, so without this the docname would
		keep whitespace that the stored field no longer has.  Setting self.name
		here means the JSON expression is skipped (see frappe.model.naming).
		"""
		self.naming_series = (self.naming_series or "").strip()
		self.name = f"{self.document_type}-{self.naming_series}"

	def before_validate(self):
		if self.naming_series:
			self.naming_series = self.naming_series.strip()

	def validate(self):
		self.validate_duplicate()
		self.set_address_displays()

	def set_address_displays(self):
		"""Keep the read-only address text in step with its Link field.

		The form script already does this as the user picks an address, but that
		only covers the desk.  Repeating it here means an import, an API write or
		an edited Address row can't leave stale text behind.
		"""
		for address_field, display_field in (
			("billing_address", "billing_address_display"),
			("shipping_address", "shipping_address_display"),
		):
			address = self.get(address_field)
			self.set(display_field, get_address_display(address) if address else None)

	def validate_duplicate(self):
		"""One entry per document type + series, comparing normalised forms.

		The docname already blocks an exact repeat.  This additionally catches
		fiscal-year variants of the same series — `BN/.FY./.#####` and
		`BN/25-26/.#####` are different strings but resolve to the same key, so
		allowing both would make the lookup depend on row order.
		"""
		if not (self.document_type and self.naming_series):
			return

		mine = normalize_series(self.naming_series)
		if not mine:
			return

		for row in frappe.get_all(
			"Invoice Series Configuration",
			filters={
				"document_type": self.document_type,
				"name": ("!=", self.name or ""),
			},
			fields=["name", "naming_series"],
		):
			if normalize_series(row.naming_series) != mine:
				continue

			same = row.naming_series == self.naming_series
			frappe.throw(
				_("Naming Series {0} is already configured for {1} in {2}.").format(
					frappe.bold(self.naming_series), frappe.bold(self.document_type),
					frappe.get_desk_link("Invoice Series Configuration", row.name),
				)
				if same
				else _(
					"Naming Series {0} resolves to the same series as {1}, already "
					"configured for {2} in {3}. Only the fiscal year differs, and that "
					"is matched automatically — a single entry covers every year."
				).format(
					frappe.bold(self.naming_series), frappe.bold(row.naming_series),
					frappe.bold(self.document_type),
					frappe.get_desk_link("Invoice Series Configuration", row.name),
				),
				title=_("Duplicate Configuration"),
			)

	def on_update(self):
		clear_series_config_cache()

	def after_delete(self):
		clear_series_config_cache()


@frappe.whitelist()
def get_naming_series_options(document_type: str) -> list[str]:
	"""Naming series options for the given invoice doctype.

	Used by the form so the user picks from a list instead of typing the series
	by hand — a typo here silently breaks the lookup for a whole boutique.
	"""
	if document_type not in ("Sales Invoice", "Purchase Invoice"):
		return []

	return frappe.get_meta(document_type).get_naming_series_options()
