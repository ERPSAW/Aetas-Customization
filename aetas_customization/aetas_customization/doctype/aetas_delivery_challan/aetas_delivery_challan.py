# Copyright (c) 2024, Akhilam Inc and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class AetasDeliveryChallan(Document):
	def validate(self):
		if self.items:
			self.total_amount = sum([item.amount for item in self.items])
			self.total_qty = sum([item.qty for item in self.items])