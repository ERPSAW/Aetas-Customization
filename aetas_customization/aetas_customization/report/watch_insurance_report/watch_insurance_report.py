# # Copyright (c) 2026, Aetas Retail and contributors
# # For license information, please see license.txt

# import frappe
# from frappe import _


# def execute(filters=None):
# 	filters = filters or {}
# 	columns = get_columns()
# 	data = get_data(filters)
# 	return columns, data


# def get_columns():
# 	return [
# 		{
# 			"label": _("Sr. No."),
# 			"fieldname": "sr_no",
# 			"fieldtype": "Int",
# 			"width": 60,
# 		},
# 		{
# 			"label": _("Store Name"),
# 			"fieldname": "store_name",
# 			"fieldtype": "Data",
# 			"width": 160,
# 		},
# 		{
# 			"label": _("Invoice No."),
# 			"fieldname": "invoice_no",
# 			"fieldtype": "Link",
# 			"options": "Sales Invoice",
# 			"width": 140,
# 		},
# 		{
# 			"label": _("Invoice Date"),
# 			"fieldname": "invoice_date",
# 			"fieldtype": "Date",
# 			"width": 100,
# 		},
# 		{
# 			"label": _("Invoice Amount"),
# 			"fieldname": "invoice_amount",
# 			"fieldtype": "Currency",
# 			"width": 130,
# 		},
# 		{
# 			"label": _("Brand"),
# 			"fieldname": "brand",
# 			"fieldtype": "Data",
# 			"width": 120,
# 		},
# 		{
# 			"label": _("Mobile No."),
# 			"fieldname": "mobile_no",
# 			"fieldtype": "Data",
# 			"width": 120,
# 		},
# 		{
# 			"label": _("Email ID"),
# 			"fieldname": "email_id",
# 			"fieldtype": "Data",
# 			"width": 160,
# 		},
# 		{
# 			"label": _("Certificate No."),
# 			"fieldname": "certificate_no",
# 			"fieldtype": "Link",
# 			"options": "Sales Invoice Insurance",
# 			"width": 160,
# 		},
# 		{
# 			"label": _("Premium"),
# 			"fieldname": "premium",
# 			"fieldtype": "Currency",
# 			"width": 110,
# 		},
# 		{
# 			"label": _("Certificate Sent"),
# 			"fieldname": "certificate_sent",
# 			"fieldtype": "Data",
# 			"width": 120,
# 		},
# 	]


# def get_data(filters):
# 	conditions, values = get_conditions(filters)

# 	query = """
# 		SELECT
# 			sii.name AS certificate_no,
# 			si.custom_boutique AS store_name,
# 			sii.sales_invoice AS invoice_no,
# 			sii.invoice_date AS invoice_date,
# 			sii.invoice_amount AS invoice_amount,
# 			sii.brand AS brand,
# 			sii.mobile_no AS mobile_no,
# 			sii.email_id AS email_id,
# 			sii.premium_amount AS premium,
# 			sii.certificate_sent AS certificate_sent
# 		FROM `tabSales Invoice Insurance` sii
# 		LEFT JOIN `tabSales Invoice` si ON si.name = sii.sales_invoice
# 		WHERE 1=1 {conditions}
# 		ORDER BY sii.invoice_date ASC, sii.name ASC
# 	""".format(conditions=conditions)

# 	rows = frappe.db.sql(query, values, as_dict=True)

# 	for idx, row in enumerate(rows, start=1):
# 		row["sr_no"] = idx

# 	return rows


# def get_conditions(filters):
# 	conditions = []
# 	values = {}

# 	if filters.get("from_date"):
# 		conditions.append("sii.invoice_date >= %(from_date)s")
# 		values["from_date"] = filters["from_date"]

# 	if filters.get("to_date"):
# 		conditions.append("sii.invoice_date <= %(to_date)s")
# 		values["to_date"] = filters["to_date"]

# 	if filters.get("store"):
# 		conditions.append("si.custom_boutique = %(store)s")
# 		values["store"] = filters["store"]

# 	if filters.get("brand"):
# 		conditions.append("sii.brand = %(brand)s")
# 		values["brand"] = filters["brand"]

# 	if filters.get("certificate_sent"):
# 		conditions.append("sii.certificate_sent = %(certificate_sent)s")
# 		values["certificate_sent"] = filters["certificate_sent"]

# 	condition_str = ""
# 	if conditions:
# 		condition_str = " AND " + " AND ".join(conditions)

# 	return condition_str, values





# Copyright (c) 2026, Aetas Retail and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		# {
		# 	"label": _("Sr. No."),
		# 	"fieldname": "sr_no",
		# 	"fieldtype": "Int",
		# 	"width": 60,
		# },
		{
			"label": _("Store Name"),
			"fieldname": "store_name",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": _("Invoice No."),
			"fieldname": "invoice_no",
			"fieldtype": "Link",
			"options": "Sales Invoice",
			"width": 140,
		},
		{
			"label": _("Invoice Date"),
			"fieldname": "invoice_date",
			"fieldtype": "Date",
			"width": 100,
		},
		{
			"label": _("Invoice Amount"),
			"fieldname": "invoice_amount",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": _("Brand"),
			"fieldname": "brand",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Mobile No."),
			"fieldname": "mobile_no",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Email ID"),
			"fieldname": "email_id",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": _("Certificate No."),
			"fieldname": "certificate_no",
			"fieldtype": "Link",
			"options": "Sales Invoice Insurance",
			"width": 160,
		},
		{
			"label": _("Premium"),
			"fieldname": "premium",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": _("Certificate Sent"),
			"fieldname": "certificate_sent",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Premium Balance"),
			"fieldname": "premium_balance",
			"fieldtype": "Currency",
			"width": 130,
		},
	]
#new
def get_total_premium_credit(): 
	"""
	Sum of Total Credit across all submitted Journal Entries created from the
	'Watch Insurance Policy Premium' template — this is the total premium
	amount ever funded, before any certificate's premium is deducted from it.
	"""
	total = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(total_credit), 0)
		FROM `tabJournal Entry`
		WHERE from_template = %(template)s
		AND docstatus = 1
		""",
		{"template": "Watch Insurance Policy Premium"},
	)
	return flt(total[0][0]) if total else 0.0

# def get_data(filters):
# 	conditions, values = get_conditions(filters)

# 	query = """
# 		SELECT
# 			sii.name AS certificate_no,
# 			si.custom_boutique AS store_name,
# 			sii.sales_invoice AS invoice_no,
# 			sii.invoice_date AS invoice_date,
# 			sii.invoice_amount AS invoice_amount,
# 			sii.brand AS brand,
# 			sii.mobile_no AS mobile_no,
# 			sii.email_id AS email_id,
# 			sii.premium_amount AS premium,
# 			sii.certificate_sent AS certificate_sent
# 		FROM `tabSales Invoice Insurance` sii
# 		LEFT JOIN `tabSales Invoice` si ON si.name = sii.sales_invoice
# 		WHERE 1=1 {conditions}
# 		ORDER BY sii.invoice_date ASC, sii.name ASC
# 	""".format(conditions=conditions)

# 	rows = frappe.db.sql(query, values, as_dict=True)

# 	# Running balance: start from the total premium ever funded (sum of
# 	# Total Credit on Journal Entries made off the "Watch Insurance Policy
# 	# Premium" template), then subtract each certificate's premium in the
# 	# same order the report is already sorted — so the last row shows what's
# 	# actually left.
# 	balance = get_total_premium_credit()

# 	for idx, row in enumerate(rows, start=1):
# 		row["sr_no"] = idx
# 		balance -= flt(row.get("premium"))
# 		row["premium_balance"] = balance

# 	return rows

def get_data(filters):
	conditions, values = get_conditions(filters)

	query = """
		SELECT
			sii.name AS certificate_no,
			si.custom_boutique AS store_name,
			sii.sales_invoice AS invoice_no,
			sii.invoice_date AS invoice_date,
			sii.invoice_amount AS invoice_amount,
			sii.brand AS brand,
			sii.mobile_no AS mobile_no,
			sii.email_id AS email_id,
			sii.premium_amount AS premium,
			sii.certificate_sent AS certificate_sent
		FROM `tabSales Invoice Insurance` sii
		LEFT JOIN `tabSales Invoice` si ON si.name = sii.sales_invoice
		WHERE 1=1 {conditions}
		ORDER BY sii.invoice_date ASC, sii.name ASC
	""".format(conditions=conditions)

	rows = frappe.db.sql(query, values, as_dict=True)

	# Running balance: start from the total premium ever funded (sum of
	# Total Credit on Journal Entries made off the "Watch Insurance Policy
	# Premium" template), then subtract each certificate's premium in the
	# same order the report is already sorted — so the last row shows what's
	# actually left.
	total_funded = get_total_premium_credit()
	balance = total_funded

	for idx, row in enumerate(rows, start=1):
		# row["sr_no"] = idx
		balance -= flt(row.get("premium"))
		row["premium_balance"] = balance

	opening_row = {
		"sr_no": None,
		"store_name": "",
		"invoice_no": None,
		"invoice_date": None,
		"invoice_amount": None,
		"brand": "",
		"mobile_no": "",
		"email_id": "",
		"certificate_no": None,
		"premium": None,
		"premium_balance": total_funded,
		"certificate_sent": "",
	}

	return [opening_row] + rows

def get_conditions(filters):
	conditions = []
	values = {}

	if filters.get("from_date"):
		conditions.append("sii.invoice_date >= %(from_date)s")
		values["from_date"] = filters["from_date"]

	if filters.get("to_date"):
		conditions.append("sii.invoice_date <= %(to_date)s")
		values["to_date"] = filters["to_date"]

	if filters.get("store"):
		conditions.append("si.custom_boutique = %(store)s")
		values["store"] = filters["store"]

	if filters.get("brand"):
		conditions.append("sii.brand = %(brand)s")
		values["brand"] = filters["brand"]

	if filters.get("certificate_sent"):
		conditions.append("sii.certificate_sent = %(certificate_sent)s")
		values["certificate_sent"] = filters["certificate_sent"]

	condition_str = ""
	if conditions:
		condition_str = " AND " + " AND ".join(conditions)

	return condition_str, values