# Copyright (c) 2024, Akhilam Inc and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class AetasDeliveryChallan(Document):
	pass
	def on_submit(self):
		if self.items:
			try:
				company = frappe.db.get_single_value("Global Defaults","default_company")
				difference_account = frappe.db.get_value("Company",company,"stock_received_but_not_billed")

				se_doc = frappe.new_doc("Stock Entry")
				se_doc.stock_entry_type = "Material Issue"
				se_doc.type_of_stocks = "Consignment"
				se_doc.posting_date = frappe.utils.today()
				se_doc.posting_time = frappe.utils.nowtime()
				se_doc.company = company

				for item in self.items:
					se_doc.append("items", {
						"item_code": item.item_code,
						"qty":item.qty,
						"s_warehouse":item.warehouse,
						"expense_account":difference_account,
						"serial_no":item.serial_no
					})
				
				se_doc.insert(ignore_permissions = 1)
				se_doc.submit()
			
				frappe.msgprint(f"Stock Entry {se_doc.name} created and submitted.")
			except Exception:
				frappe.log_error(title="Stock Entry Creation Failed From Aetas Delivery Challan",message=frappe.get_traceback())
				frappe.msgprint("Error While Creating Stock Entry From Aetas Delivery Challan!")
				