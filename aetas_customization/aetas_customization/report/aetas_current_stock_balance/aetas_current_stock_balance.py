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
		mrp = 0
		if serial_no.purchase_document_type == "Stock Entry":
			mrp = frappe.db.get_value("Stock Entry Detail", {"parent": serial_no.purchase_document_no,"item_code": serial_no.item_code,"serial_no": ["like", f"%{serial_no.name}%"]}, "custom_mrp") or 0
		elif serial_no.purchase_document_type == "Purchase Invoice":
			mrp = frappe.db.get_value("Purchase Invoice Item", {"parent": serial_no.purchase_document_no,"item_code": serial_no.item_code,"serial_no": ["like", f"%{serial_no.name}%"]}, "mrp") or 0
		elif serial_no.purchase_document_type == "Sales Invoice":
			mrp = frappe.db.get_value("Sales Invoice Item", {"parent": serial_no.purchase_document_no,"item_code": serial_no.item_code,"serial_no": ["like", f"%{serial_no.name}%"]}, "mrp") or 0
		
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
			"name": serial_no.name,
			"item_code": serial_no.item_code,
			"item_name": serial_no.item_name,
			"item_group": item_group,
			"stock_uom": stock_uom,
			"warehouse": serial_no.warehouse,
			"available_qty": 1,
			"purchase_rate": serial_no.purchase_rate,
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