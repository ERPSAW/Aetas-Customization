# Copyright (c) 2026, Akhilam Inc and Contributors
# See license.txt

import frappe
from frappe.model.document import Document


class AetasAPRPaymentDetail(Document):
	"""
	Child table for Aetas Advance Payment Receipt.
	Tracks payment entries linked to an APR, including the amount paid and the Sales Invoice it was allocated to.
	"""
	pass
