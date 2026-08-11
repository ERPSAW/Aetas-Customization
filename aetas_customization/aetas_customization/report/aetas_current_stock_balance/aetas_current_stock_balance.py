# Copyright (c) 2024, Akhilam Inc and contributors
# For license information, please see license.txt

import frappe
from datetime import datetime
from frappe.utils import getdate


def execute(filters=None):
	columns, data = get_columns(filters), get_data(filters)
	return columns, data


def get_posting_date_map(serial_names):
	"""Return {serial_no: posting_date} for the inward (receipt) voucher of each serial.

	The posting date comes from the Serial and Batch Bundle, whose posting_datetime
	is stamped from the voucher's own posting_date/posting_time — so a backdated
	receipt reports the date the stock actually landed, not when the row was
	inserted. Where several inward bundles exist for one serial (receipt, then a
	repack or transfer), the earliest wins: that is when the serial entered stock.
	"""

	posting_dates = {}

	if not serial_names:
		return posting_dates

	# 1) Serial and Batch Bundle (ERPNext v15 default)
	bundle_rows = frappe.db.sql("""
		SELECT sbe.serial_no AS serial_no, MIN(sbb.posting_datetime) AS posting_datetime
		FROM `tabSerial and Batch Entry` sbe
		INNER JOIN `tabSerial and Batch Bundle` sbb ON sbb.name = sbe.parent
		WHERE sbe.serial_no IN %(serial_names)s
		AND sbb.docstatus = 1
		AND sbb.is_cancelled = 0
		AND sbb.type_of_transaction = 'Inward'
		AND sbb.posting_datetime IS NOT NULL
		GROUP BY sbe.serial_no
	""", {"serial_names": serial_names}, as_dict=True)

	for row in bundle_rows:
		posting_dates[row.serial_no] = getdate(row.posting_datetime)

	# 2) Legacy rows that predate the bundle and still carry the plain serial_no
	# field on the receiving voucher item.
	missing = [sn for sn in serial_names if sn not in posting_dates]

	if missing:
		for child_dt, parent_dt in (
			("Stock Entry Detail", "Stock Entry"),
			("Purchase Invoice Item", "Purchase Invoice"),
			("Purchase Receipt Item", "Purchase Receipt"),
		):
			if not missing:
				break

			legacy_rows = frappe.db.sql("""
				SELECT child.serial_no AS serial_no, parent.posting_date AS posting_date
				FROM `tab{child_dt}` child
				INNER JOIN `tab{parent_dt}` parent ON parent.name = child.parent
				WHERE child.docstatus = 1
				AND child.serial_no IS NOT NULL
				AND child.serial_no != ''
			""".format(child_dt=child_dt, parent_dt=parent_dt), as_dict=True)

			missing_set = set(missing)

			for row in legacy_rows:
				for sn in (row.serial_no or "").split("\n"):
					sn = sn.strip()

					if not sn or sn not in missing_set:
						continue

					posting_date = getdate(row.posting_date)
					existing = posting_dates.get(sn)

					# earliest inward wins, same rule as the bundle query above
					if not existing or posting_date < existing:
						posting_dates[sn] = posting_date

			missing = [sn for sn in missing if sn not in posting_dates]

	return posting_dates


def get_data(filters):
	data = []

	from_date = filters.get("from_date")
	to_date = filters.get("to_date")

	if from_date and to_date and from_date > to_date:
		frappe.throw("From Date cannot be greater than To Date")

	serial_nos = frappe.db.get_all("Serial No", filters={"status": "Active"}, fields=['*'], order_by="creation asc")

	if not serial_nos:
		return data

	# Posting date drives this report — both the date shown and the date range
	# filtered on. Serials with no resolvable inward voucher fall back to
	# creation so they are never silently dropped from the balance.
	posting_date_map = get_posting_date_map([serial_no.name for serial_no in serial_nos])

	for serial_no in serial_nos:
		serial_no.posting_date = posting_date_map.get(serial_no.name) or getdate(serial_no.creation)

	if from_date and to_date:
		serial_nos = [
			serial_no for serial_no in serial_nos
			if getdate(from_date) <= serial_no.posting_date <= getdate(to_date)
		]

		if not serial_nos:
			return data

	serial_nos.sort(key=lambda serial_no: serial_no.posting_date)

	item_codes = [serial_no.item_code for serial_no in serial_nos]

	item_details = frappe.db.get_all("Item", filters={"item_code": ["in", item_codes]}, fields=["name", "item_group", "stock_uom"])
	item_map = {item['name']: item for item in item_details}

	for serial_no in serial_nos:

		# if serial_no.purchase_document_type == "Stock Entry":
		# 	mrp = frappe.db.get_value("Stock Entry Detail", {"parent": serial_no.purchase_document_no,"item_code": serial_no.item_code,"serial_no": ["like", f"%{serial_no.name}%"]}, "custom_mrp") or 0
		# elif serial_no.purchase_document_type == "Purchase Invoice":
		# 	mrp = frappe.db.get_value("Purchase Invoice Item", {"parent": serial_no.purchase_document_no,"item_code": serial_no.item_code,"serial_no": ["like", f"%{serial_no.name}%"]}, "mrp") or 0
		# elif serial_no.purchase_document_type == "Sales Invoice":
		# 	mrp = frappe.db.get_value("Sales Invoice Item", {"parent": serial_no.purchase_document_no,"item_code": serial_no.item_code,"serial_no": ["like", f"%{serial_no.name}%"]}, "mrp") or 0

		mrp = 0
		purchase_rate = 0

		doc_no = serial_no.purchase_document_no
		status = ""
		sn = serial_no.name
		item_code = serial_no.item_code

		# -------------------------
		# STATUS LOGIC
		# -------------------------

		# 1) PURCHASE INVOICE → PAID
		# custom_purchase_invoice_no is stamped on the Serial No when a Purchase
		# Invoice is submitted against it (see overrides/purchase_invoice.py),
		# so no lookup into Purchase Invoice Item is needed.
		purchase_invoice = serial_no.get("custom_purchase_invoice_no")

		if purchase_invoice:
			status = "Paid"

		# 2) STOCK ENTRY → MATERIAL RECEIPT → CONSIGNMENT → PAID
		if not status:
			se_details = frappe.db.get_all(
				"Stock Entry Detail",
				filters={
					"item_code": item_code,
					"serial_no": ["like", f"%{sn}%"],
				},
				pluck="parent"
			)

			if se_details:
				stock_entries = frappe.db.get_all(
					"Stock Entry",
					filters={
						"name": ["in", se_details],
						"docstatus": 1,
						"stock_entry_type": "Material Receipt",
						"type_of_stocks": "Consignment",
					},
					fields=["name"]
				)

				if stock_entries:
					status = "Consignment"

		# -------------------------
		# RATE & MRP LOGIC
		# -------------------------
		if doc_no:

			# 1) STOCK ENTRY DETAIL (highest priority)
			row = frappe.db.get_value(
				"Stock Entry Detail",
				{
					"parent": doc_no,
					"item_code": item_code,
					"serial_no": ["like", f"%{sn}%"]
				},
				["basic_rate", "custom_mrp"],
				as_dict=True
			)
			if row:
				purchase_rate = row.basic_rate or 0
				mrp = row.custom_mrp or 0

		# 2) PURCHASE INVOICE ITEM (only if still not found).
		# Keyed on custom_purchase_invoice_no, not purchase_document_no — when the
		# serial was received through a Stock Entry, purchase_document_no holds
		# that Stock Entry and can never match a Purchase Invoice Item.
		if not mrp and purchase_invoice:
			row = frappe.db.get_value(
				"Purchase Invoice Item",
				{
					"parent": purchase_invoice,
					"item_code": item_code,
				},
				["net_rate", "mrp"],
				as_dict=True
			)
			if row:
				purchase_rate = row.net_rate or 0
				mrp = row.mrp or 0

		#3) FALLBACK — ITEM MASTER MRP
		if not mrp:
			mrp = frappe.db.get_value("Item", item_code, "mrp") or 0

		#4) FINAL RATE FALLBACK
		if not purchase_rate:
			purchase_rate = serial_no.purchase_rate or 0


		
		# Get item details from pre-fetched data
		item_data = item_map.get(serial_no.item_code, {})
		item_group = item_data.get("item_group", "")
		stock_uom = item_data.get("stock_uom", "")

		# Calculate stock age from the posting date, so backdated receipts age
		# from when the stock actually arrived
		posting_date = serial_no.posting_date
		today_date = datetime.strptime(frappe.utils.today(), '%Y-%m-%d').date()
		stock_age = (today_date - posting_date).days

		# Build the row for each serial number
		row = {
			"posting_date": posting_date,
			"status": status,
			"name": serial_no.name,
			"item_code": serial_no.item_code,
			"item_name": serial_no.item_name,
			"item_group": item_group,
			"stock_uom": stock_uom,
			"warehouse": serial_no.warehouse,
			"available_qty": 1,
			"purchase_rate": purchase_rate,
			"mrp": mrp,
			"stock_age": stock_age,
			"company": serial_no.company
		}
		data.append(row)
	
	return data



def get_columns(filters):
	columns = [
		{
			"label": "Posting Date",
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 100
		},
		{
			"label":"Status",
			"fieldname":"status",
			"fieldtype":"Data",
			"width":100
		},
		{
			"label": "Item Code",
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 100
		},
		{
			"label": "Item Name",
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 100
		},
		{
			"label": "Item Group",
			"fieldname": "item_group",
			"fieldtype": "Link",
			"options": "Item Group",
			"width": 100
		},
		{
			"label": "Stock UOM",
			"fieldname": "stock_uom",
			"fieldtype": "Link",
			"options": "UOM",
			"width": 100
		},
		{
			"label": "Warehouse",
			"fieldname": "warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 100
		},
		{
			"label": "Available Qty",
			"fieldname": "available_qty",
			"fieldtype": "Float",
			"width": 100
		},
		{
			"label": "Value",
			"fieldname": "purchase_rate",
			"fieldtype": "Currency",
			"width": 140
		},
		{
			"label": "MRP",
			"fieldname": "mrp",
			"fieldtype": "Currency",
			"width": 140
		},
		{
			"label": "Stock Age",
			"fieldname": "stock_age",
			"fieldtype": "Int",
			"width": 140
		},
		{
			"label": "Serial No",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Serial No",
			"width": 180
		},
		{
			"label": "Company",
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 220
		},
	]
	return columns