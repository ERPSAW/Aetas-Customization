import frappe
from erpnext.accounts.doctype.payment_reconciliation.payment_reconciliation import PaymentReconciliation
from frappe.utils import flt


class CustomPaymentReconciliation(PaymentReconciliation):
	def add_invoice_entries(self, non_reconciled_invoices):
		# Populate 'invoices' with JVs and Invoices to reconcile against
		self.set("invoices", [])
		for entry in non_reconciled_invoices:
			inv = self.append("invoices", {})
			inv.invoice_type = entry.get("voucher_type")
			inv.invoice_number = entry.get("voucher_no")
			inv.custom_bill_no = entry.get("custom_bill_no")
			inv.invoice_date = entry.get("posting_date")
			inv.amount = flt(entry.get("invoice_amount"))
			inv.currency = entry.get("currency")
			inv.outstanding_amount = flt(entry.get("outstanding_amount"))
			if entry.get("voucher_type") == "Purchase Invoice":
				inv.custom_bill_no = frappe.get_value(entry.get("voucher_type"), entry.get("voucher_no"), "bill_no")