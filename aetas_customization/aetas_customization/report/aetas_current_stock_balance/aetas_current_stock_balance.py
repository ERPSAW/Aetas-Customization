# Copyright (c) 2024, Akhilam Inc and contributors
# For license information, please see license.txt

import frappe
from datetime import datetime
from frappe.utils import getdate


def execute(filters=None):
	columns, data = get_columns(filters), get_data(filters)
	return columns, data


def get_posting_date_map(serial_names):
	"""Return {serial_no: posting_date} for the start of each serial's current stint in stock.

	The posting date comes from the Serial and Batch Bundle, whose posting_datetime
	is stamped from the voucher's own posting_date/posting_time — so a backdated
	receipt reports the date the stock actually landed, not when the row was
	inserted.

	A serial can enter stock more than once: sold or consumed, then bought back in.
	What the balance is asking about is the stock on hand *now*, so the query
	replays every movement and keeps the last inward that took the serial from zero
	qty to positive — not the first receipt, which may be several owners ago.

	Netting per posting_datetime is what stops an internal transfer from resetting
	the age. ERPNext writes two bundles for a Material Transfer — Outward from the
	source warehouse, Inward to the target (see get_sle_for_target_warehouse in
	erpnext/stock/doctype/stock_entry/stock_entry.py) — both stamped with the same
	posting_datetime. Summed together they net to zero, the running qty never dips,
	and the serial keeps ageing from its original receipt.
	"""

	posting_dates = {}

	if not serial_names:
		return posting_dates

	# 1) Serial and Batch Bundle (ERPNext v15 default)
	bundle_rows = frappe.db.sql("""
		WITH moves AS (
			SELECT
				sbe.serial_no AS serial_no,
				sbb.posting_datetime AS posting_datetime,
				SUM(CASE WHEN sbb.type_of_transaction = 'Inward' THEN 1 ELSE -1 END) AS net_qty
			FROM `tabSerial and Batch Entry` sbe
			INNER JOIN `tabSerial and Batch Bundle` sbb ON sbb.name = sbe.parent
			WHERE sbe.serial_no IN %(serial_names)s
			AND sbb.docstatus = 1
			AND sbb.is_cancelled = 0
			AND sbb.type_of_transaction IN ('Inward', 'Outward')
			AND sbb.posting_datetime IS NOT NULL
			GROUP BY sbe.serial_no, sbb.posting_datetime
		),
		walk AS (
			SELECT
				serial_no,
				posting_datetime,
				COALESCE(SUM(net_qty) OVER (
					PARTITION BY serial_no ORDER BY posting_datetime
					ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
				), 0) AS qty_before,
				SUM(net_qty) OVER (
					PARTITION BY serial_no ORDER BY posting_datetime
					ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
				) AS qty_after
			FROM moves
		)
		SELECT serial_no, MAX(posting_datetime) AS posting_datetime
		FROM walk
		WHERE qty_after > 0 AND qty_before <= 0
		GROUP BY serial_no
	""", {"serial_names": serial_names}, as_dict=True)

	for row in bundle_rows:
		posting_dates[row.serial_no] = getdate(row.posting_datetime)

	# 2) Legacy rows that predate the bundle and still carry the plain serial_no
	# field on the receiving voucher item. These vouchers record only receipts, so
	# there is no outward side to replay — the earliest receipt is the best guess
	# available for a serial with no bundle at all.
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


def get_serial_entries_map(serial_nos):
	"""Return {serial_no: [entry, ...]} for every Purchase Invoice, Debit Note and
	Consignment Material Receipt the serial appears on, oldest first.

	Entries are ordered by the voucher's own posting_date/posting_time, so a
	backdated document sits where it happened, not where it was keyed in.
	creation only breaks a tie between two vouchers posted at the same moment.

	A serial can sit on a voucher through the plain serial_no field (older rows,
	and Purchase Invoices that do not update stock) or through a Serial and Batch
	Bundle, so both are read.
	"""

	# Keyed in upper case: the serial_no text field on a voucher row is free text,
	# and MariaDB matched it case-insensitively when the serial was received.
	serials_by_key = {serial_no.name.upper(): serial_no for serial_no in serial_nos}
	entries = {}

	bundle_serials = {}
	for row in frappe.db.sql("""
		SELECT parent, serial_no
		FROM `tabSerial and Batch Entry`
		WHERE serial_no IN %(serial_names)s
	""", {"serial_names": [serial_no.name for serial_no in serial_nos]}, as_dict=True):
		bundle_serials.setdefault(row.parent, []).append(row.serial_no)

	purchase_rows = frappe.db.sql("""
		SELECT
			pi.name AS voucher_no,
			IF(pi.is_return = 1, 'Return', 'Purchase') AS entry_type,
			pi.update_stock AS is_inward,
			TIMESTAMP(pi.posting_date, pi.posting_time) AS posting_datetime,
			pi.creation AS creation,
			pii.item_code AS item_code,
			pii.serial_no AS serial_no,
			pii.serial_and_batch_bundle AS bundle,
			pii.net_rate AS rate,
			pii.mrp AS mrp
		FROM `tabPurchase Invoice Item` pii
		INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
		WHERE pi.docstatus = 1
		AND (IFNULL(pii.serial_no, '') != '' OR IFNULL(pii.serial_and_batch_bundle, '') != '')
	""", as_dict=True)

	receipt_rows = frappe.db.sql("""
		SELECT
			se.name AS voucher_no,
			IF(se.type_of_stocks = 'Consignment', 'Consignment', 'Own Purchase') AS entry_type,
			1 AS is_inward,
			TIMESTAMP(se.posting_date, se.posting_time) AS posting_datetime,
			se.creation AS creation,
			sed.item_code AS item_code,
			sed.serial_no AS serial_no,
			sed.serial_and_batch_bundle AS bundle,
			sed.basic_rate AS rate,
			sed.custom_mrp AS mrp
		FROM `tabStock Entry Detail` sed
		INNER JOIN `tabStock Entry` se ON se.name = sed.parent
		WHERE se.docstatus = 1
		AND se.stock_entry_type = 'Material Receipt'
		AND se.type_of_stocks IN ('Consignment', 'Own Purchase goods')
		AND (IFNULL(sed.serial_no, '') != '' OR IFNULL(sed.serial_and_batch_bundle, '') != '')
	""", as_dict=True)

	for row in purchase_rows + receipt_rows:
		row_serials = {sn.strip().upper() for sn in (row.serial_no or "").split("\n") if sn.strip()}
		row_serials.update(sn.upper() for sn in bundle_serials.get(row.bundle, []))

		for key in row_serials:
			serial_no = serials_by_key.get(key)
			if serial_no and serial_no.item_code == row.item_code:
				entries.setdefault(serial_no.name, []).append(row)

	for serial_entries in entries.values():
		serial_entries.sort(key=lambda entry: (entry.posting_datetime, entry.creation))

	return entries


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
	serial_entries_map = get_serial_entries_map(serial_nos)

	for serial_no in serial_nos:
		entries = serial_entries_map.get(serial_no.name, [])

		# Status, value and MRP follow the latest voucher by posting date: a
		# Purchase Invoice makes the serial Paid, but a Debit Note followed by a
		# fresh Consignment receipt hands it back to the supplier's stock.
		serial_no.latest_entry = entries[-1] if entries else None
		serial_no.latest_inward = next((entry for entry in reversed(entries) if entry.is_inward), None)
		serial_no.latest_purchase = next((entry for entry in reversed(entries) if entry.entry_type == "Purchase"), None)

		posting_date = posting_date_map.get(serial_no.name)

		# The bundle replay misses a serial whose first receipt predates bundles
		# and was then returned and received again, so a later inward voucher wins.
		if serial_no.latest_inward:
			inward_date = getdate(serial_no.latest_inward.posting_datetime)
			if not posting_date or inward_date > posting_date:
				posting_date = inward_date

		serial_no.posting_date = posting_date or getdate(serial_no.creation)

	if from_date and to_date:
		serial_nos = [
			serial_no for serial_no in serial_nos
			if getdate(from_date) <= serial_no.posting_date <= getdate(to_date)
		]

		if not serial_nos:
			return data

	serial_nos.sort(key=lambda serial_no: serial_no.posting_date, reverse=True)

	item_codes = [serial_no.item_code for serial_no in serial_nos]

	item_details = frappe.db.get_all("Item", filters={"item_code": ["in", item_codes]}, fields=["name", "item_group", "stock_uom", "mrp", "brand"])
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

		# MontBlanc stock is always Paid, whatever voucher brought it in.
		# Otherwise the latest voucher by posting date decides: Purchase Invoice or
		# Own Purchase Material Receipt → Paid, Consignment Material Receipt →
		# Consignment, Debit Note → returned, no status.
		latest_entry = serial_no.latest_entry
		brand = (item_map.get(item_code, {}).get("brand") or "").lower()

		if brand == "montblanc":
			status = "Paid"
		elif latest_entry and latest_entry.entry_type in ("Purchase", "Own Purchase"):
			status = "Paid"
		elif latest_entry and latest_entry.entry_type == "Consignment":
			status = "Consignment"

		# -------------------------
		# RATE & MRP LOGIC
		# -------------------------

		# 1) LATEST INWARD VOUCHER (highest priority) — the receipt that brought the
		# serial into stock this time, not purchase_document_no, which still points
		# at the first receipt after a return and a fresh receipt.
		if serial_no.latest_inward:
			purchase_rate = serial_no.latest_inward.rate or 0
			mrp = serial_no.latest_inward.mrp or 0

		elif doc_no:
			# Inward through some other Stock Entry type (not Consignment)
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

		# 2) PURCHASE INVOICE ITEM (only if still not found, and only while Paid —
		# a returned invoice no longer prices the serial)
		if not mrp and status == "Paid" and serial_no.latest_purchase:
			purchase_rate = serial_no.latest_purchase.rate or 0
			mrp = serial_no.latest_purchase.mrp or 0

		# Get item details from pre-fetched data
		item_data = item_map.get(serial_no.item_code, {})

		#3) FALLBACK — ITEM MASTER MRP
		if not mrp:
			mrp = item_data.get("mrp") or 0

		#4) FINAL RATE FALLBACK
		if not purchase_rate:
			purchase_rate = serial_no.purchase_rate or 0

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