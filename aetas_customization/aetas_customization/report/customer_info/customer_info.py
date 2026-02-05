# Copyright (c) 2026, Akhilam Inc and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{
			"fieldname": "customer",
			"label": "Customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 250,
		},
		{
			"fieldname":"customer_name",
			"label":"Customer Name",
			"fieldtype":"Data",
			"width":250,
		},
		{
			"fieldname":"customer_creation",
			"label":"Customer Creation Datetime",
			"fieldtype":"Data",
			"width":250,
		},
		{
			"fieldname": "sales_person",
			"label": "SA Name",
			"fieldtype": "Link",
			"options": "Sales Person",
			"width": 200,
		},
		{
			"fieldname": "mobile",
			"label": "Mobile",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"fieldname": "email",
			"label": "Email",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"fieldname": "address",
			"label": "Address",
			"fieldtype": "Data",
			"width": 150,
		}
	]


def get_data(filters):
	# Build SQL conditions
	conditions = ["c.disabled = 0"]
	values = {}
	
	if filters.get("customer"):
		conditions.append("c.name = %(customer)s")
		values["customer"] = filters.get("customer")
	
	if filters.get("sales_person"):
		conditions.append("c.custom_sales_person = %(sales_person)s")
		values["sales_person"] = filters.get("sales_person")
	
	where_clause = " AND ".join(conditions)
	
	# Single optimized SQL query to fetch all data
	query = f"""
		SELECT 
			c.name as customer,
			c.customer_name as customer_name,
			DATE_FORMAT(c.creation, '%%b %%d %%Y %%h:%%i%%p') AS customer_creation,
			c.custom_sales_person as sales_person,
			IF(c.custom_contact IS NOT NULL AND c.custom_contact != '', 'Yes', 'No') as mobile,
			IF(c.custom_email IS NOT NULL AND c.custom_email != '', 'Yes', 'No') as email,
			CASE 
				WHEN EXISTS (
					SELECT 1 
					FROM `tabAddress` a
					INNER JOIN `tabDynamic Link` dl ON dl.parent = a.name
					WHERE dl.link_doctype = 'Customer' 
					AND dl.link_name = c.name 
					AND dl.parenttype = 'Address'
					AND a.pincode IS NOT NULL 
					AND a.pincode != ''
				) THEN 'Yes'
				ELSE 'No'
			END as address
		FROM `tabCustomer` c
		WHERE {where_clause}
		ORDER BY c.name
	"""
	
	data = frappe.db.sql(query, values=values, as_dict=1)
	
	return data