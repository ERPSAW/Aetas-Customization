# Copyright (c) 2024, Akhilam Inc and contributors
# For license information, please see license.txt

import frappe
from datetime import datetime
from frappe.utils import getdate


def execute(filters=None):
	columns, data = get_columns(filters), get_data(filters)
	return columns, data


def get_data(filters):
	data = []	

	sn_filters = {"status": "Active"}

	if filters.get("from_date") and filters.get("to_date"):
		from_date = filters.get("from_date")
		to_date = filters.get("to_date")

		if from_date > to_date:
			frappe.throw("From Date cannot be greater than To Date")

		# creation is datetime, convert date → full range
		sn_filters["creation"] = ["between", (f"{from_date} 00:00:00", f"{to_date} 23:59:59")]

	serial_nos = frappe.db.get_all("Serial No", filters=sn_filters, fields=['*'])

	if not serial_nos:
		return data
	
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
		pi_exists = frappe.db.exists(
			"Purchase Invoice Item",
			{
				"item_code": item_code,
				"serial_no": ["like", f"%{sn}%"],
				"docstatus": 1,
			},
		)

		if pi_exists:
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
					status = "Paid"

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

			# 2) PURCHASE INVOICE ITEM (only if still not found)
			if not mrp:
				row = frappe.db.get_value(
					"Purchase Invoice Item",
					{
						"parent": doc_no,
						"item_code": item_code,
						"serial_no": ["like", f"%{sn}%"]
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

		# Calculate stock age
		creation_date = getdate(serial_no.creation)
		today_date = datetime.strptime(frappe.utils.today(), '%Y-%m-%d').date()
		stock_age = (today_date - creation_date).days

		# Build the row for each serial number
		row = {
			"creation_date": getdate(serial_no.creation),
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
			"label": "Creation Date",
			"fieldname": "creation_date",
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