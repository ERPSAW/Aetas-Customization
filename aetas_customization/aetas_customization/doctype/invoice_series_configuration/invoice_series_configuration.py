# Copyright (c) 2026, Akhilam Inc and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from aetas_customization.aetas_customization.invoice_series_config import (
	clear_series_config_cache,
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

	def validate_duplicate(self):
		"""One entry per (document_type, naming_series).

		Frappe v15 has no declarative composite-unique, so enforce it here.  The
		DB-level index added by the patch is the real guard against races; this
		gives the user a readable message instead of a SQL error.
		"""
		if not (self.document_type and self.naming_series):
			return

		existing = frappe.db.exists(
			"Invoice Series Configuration",
			{
				"document_type": self.document_type,
				"naming_series": self.naming_series,
				"name": ("!=", self.name or ""),
			},
		)
		if existing:
			frappe.throw(
				_("Naming Series {0} is already configured for {1} in {2}.").format(
					frappe.bold(self.naming_series),
					frappe.bold(self.document_type),
					frappe.get_desk_link("Invoice Series Configuration", existing),
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
