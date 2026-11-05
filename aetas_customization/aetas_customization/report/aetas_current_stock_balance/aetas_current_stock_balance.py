# Copyright (c) 2024, Akhilam Inc and contributors
# For license information, please see license.txt

import frappe
from datetime import datetime
from frappe.utils import getdate


def execute(filters=None):
	columns, data = get_columns(filters), get_data(filters)
	return columns, data


def get_stock_in_range_map(from_date, to_date):
	"""Return {SERIAL_NO: {"warehouse", "in_stock_until"}} for every serial that was in
	stock on at least one day from from_date to to_date.

	Replays the Stock Ledger up to to_date, the same source ERPNext's own Stock
	Ledger report reads. A serial counts when it was in stock as the range opened,
	or came in during it — so one sold after to_date counts, and so does one bought
	and sold inside the range. Keys are upper case because the legacy serial_no text
	field is free text and MariaDB matched it case-insensitively.

	warehouse is where the serial last landed; in_stock_until is to_date when it is
	still in stock then, else the day it last went out, so its age stops there.

	A serial sits on a ledger row in one of two ways, never both: entries posted
	before Serial and Batch Bundles carry the serial in the plain serial_no text
	field, later ones through the bundle. Each serial moves one unit, in the
	direction of actual_qty.

	A Material Transfer posts an outward and an inward row at the same moment; they
	net to zero, and the warehouse is taken from the inward side.
	"""

	moves = []

	for row in frappe.db.sql("""
		SELECT
			sbe.serial_no AS serial_no,
			sle.warehouse AS warehouse,
			sle.actual_qty AS actual_qty,
			TIMESTAMP(sle.posting_date, sle.posting_time) AS posting_datetime,
			sle.creation AS creation
		FROM `tabStock Ledger Entry` sle
		INNER JOIN `tabSerial and Batch Entry` sbe ON sbe.parent = sle.serial_and_batch_bundle
		WHERE sle.is_cancelled = 0
		AND sle.posting_date <= %(to_date)s
		AND IFNULL(sle.serial_and_batch_bundle, '') != ''
		AND sle.actual_qty != 0
	""", {"to_date": to_date}, as_dict=True):
		moves.append((row.posting_datetime, row.creation, row.serial_no.upper(), row.actual_qty, row.warehouse))

	for row in frappe.db.sql("""
		SELECT
			serial_no AS serial_nos,
			warehouse,
			actual_qty,
			TIMESTAMP(posting_date, posting_time) AS posting_datetime,
			creation
		FROM `tabStock Ledger Entry`
		WHERE is_cancelled = 0
		AND posting_date <= %(to_date)s
		AND IFNULL(serial_no, '') != ''
		AND actual_qty != 0
	""", {"to_date": to_date}, as_dict=True):
		for sn in row.serial_nos.split("\n"):
			if sn.strip():
				moves.append((row.posting_datetime, row.creation, sn.strip().upper(), row.actual_qty, row.warehouse))

	moves.sort(key=lambda move: (move[0], move[1]))

	from_date, to_date = getdate(from_date), getdate(to_date)
	qty, warehouses, last_move_dates, in_range = {}, {}, {}, set()

	for posting_datetime, _creation, sn, actual_qty, warehouse in moves:
		move_date = getdate(posting_datetime)
		qty_before = qty.get(sn, 0)
		qty[sn] = qty_before + (1 if actual_qty > 0 else -1)
		last_move_dates[sn] = move_date

		if actual_qty > 0:
			warehouses[sn] = warehouse

		# In stock as this in-range day began, or after this move
		if move_date >= from_date and (qty_before > 0 or qty[sn] > 0):
			in_range.add(sn)

	stock = {}
	for sn, balance in qty.items():
		# Still in stock at the end: it was in stock through the whole range
		if balance > 0 or sn in in_range:
			stock[sn] = frappe._dict(
				warehouse=warehouses.get(sn),
				in_stock_until=to_date if balance > 0 else last_move_dates[sn],
				left_stock=balance <= 0,
			)

	return stock


def get_posting_date_map(serial_names, as_on_date=None):
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

	With as_on_date, movements after that day are ignored, so the stint is the one
	the serial was in on that day.
	"""

	posting_dates = {}

	if not serial_names:
		return posting_dates

	bundle_condition = "AND DATE(sbb.posting_datetime) <= %(as_on_date)s" if as_on_date else ""
	legacy_condition = "AND parent.posting_date <= %(as_on_date)s" if as_on_date else ""

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
			{bundle_condition}
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
	""".format(bundle_condition=bundle_condition), {"serial_names": serial_names, "as_on_date": as_on_date}, as_dict=True)

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
				{legacy_condition}
			""".format(child_dt=child_dt, parent_dt=parent_dt, legacy_condition=legacy_condition), {"as_on_date": as_on_date}, as_dict=True)

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


def get_serial_entries_map(serial_nos, as_on_date=None):
	"""Return {serial_no: [entry, ...]} for every Purchase Invoice, Debit Note and
	Consignment Material Receipt the serial appears on, oldest first. With
	as_on_date, vouchers posted after that day are left out.

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
			IF(pi.is_return = 1, 0, pi.update_stock) AS is_inward,
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
		{as_on_condition}
	""".format(as_on_condition="AND pi.posting_date <= %(as_on_date)s" if as_on_date else ""),
		{"as_on_date": as_on_date}, as_dict=True)

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
		{as_on_condition}
	""".format(as_on_condition="AND se.posting_date <= %(as_on_date)s" if as_on_date else ""),
		{"as_on_date": as_on_date}, as_dict=True)

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

	# With a date range the report shows every serial that was in stock on at least
	# one day of it, whatever the serial's status is today; without one, the stock
	# on hand now. A single date is read as a one-day range, and To Date alone runs
	# to today.
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")

	if from_date and to_date and getdate(from_date) > getdate(to_date):
		frappe.throw("From Date cannot be greater than To Date")

	if from_date and not to_date:
		to_date = frappe.utils.today()
	elif to_date and not from_date:
		from_date = to_date

	# Status, value and dates are read as they stood on To Date
	as_on_date = to_date
	serial_no_filters = {}

	if to_date:
		stock_in_range_map = get_stock_in_range_map(from_date, to_date)

		if not stock_in_range_map:
			return data

		serial_no_filters["name"] = ["in", list(stock_in_range_map)]
	else:
		serial_no_filters["status"] = "Active"

	if filters.get("serial_no"):
		serial_no_filters["name"] = filters.get("serial_no")

	serial_nos = frappe.db.get_all("Serial No", filters=serial_no_filters, fields=['*'], order_by="creation asc")

	if to_date:
		# The Serial No master only knows where the serial is today
		serial_nos = [serial_no for serial_no in serial_nos if serial_no.name.upper() in stock_in_range_map]
		for serial_no in serial_nos:
			stock = stock_in_range_map[serial_no.name.upper()]
			serial_no.warehouse = stock.warehouse
			serial_no.in_stock_until = stock.in_stock_until
			serial_no.left_stock = stock.left_stock

	if not serial_nos:
		return data

	# Posting date is the day the serial last came into stock. Serials with no
	# resolvable inward voucher fall back to creation so they are never silently
	# dropped from the balance.
	posting_date_map = get_posting_date_map([serial_no.name for serial_no in serial_nos], as_on_date)
	serial_entries_map = get_serial_entries_map(serial_nos, as_on_date)

	for serial_no in serial_nos:
		entries = serial_entries_map.get(serial_no.name, [])

		# A serial that left stock inside the range is shown as it was while still
		# in stock: the Debit Note that sent it back, and anything after, is skipped.
		if serial_no.left_stock:
			entries = [
				entry for entry in entries
				if entry.entry_type != "Return" and getdate(entry.posting_datetime) <= serial_no.in_stock_until
			]

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
		# from when the stock actually arrived, up to the end of the range or the
		# day the serial left stock inside it
		posting_date = serial_no.posting_date
		age_until = serial_no.in_stock_until or datetime.strptime(frappe.utils.today(), '%Y-%m-%d').date()
		stock_age = (age_until - posting_date).days

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