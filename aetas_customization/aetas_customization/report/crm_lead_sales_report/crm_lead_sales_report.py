import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"fieldname": "lead_id", "label": _("Lead ID"), "fieldtype": "Data", "width": 240},
		{"fieldname": "month", "label": _("Month"), "fieldtype": "Data", "width": 90},
		{"fieldname": "date", "label": _("Date"), "fieldtype": "Date", "width": 100},
		{"fieldname": "source_of_lead", "label": _("Source of lead"), "fieldtype": "Data", "width": 120},
		{"fieldname": "name_of_enquirer", "label": _("Name of enquirer"), "fieldtype": "Data", "width": 150},
		{"fieldname": "existing_customer", "label": _("Existing customer"), "fieldtype": "Data", "width": 120},
		{"fieldname": "loyalty_status", "label": _("Loyalty status"), "fieldtype": "Data", "width": 120},
		{"fieldname": "lead_brand", "label": _("Brand"), "fieldtype": "Data", "width": 100},
		{"fieldname": "model_no", "label": _("Model no."), "fieldtype": "Data", "width": 120},
		{"fieldname": "contact_no", "label": _("Contact no."), "fieldtype": "Data", "width": 120},
		{"fieldname": "qualified", "label": _("Qualified"), "fieldtype": "Data", "width": 90},
		{"fieldname": "allocated_store", "label": _("Allocated store"), "fieldtype": "Data", "width": 130},
		{"fieldname": "lead_status", "label": _("Lead Status"), "fieldtype": "Data", "width": 120},
		{"fieldname": "closed_won", "label": _("Closed won"), "fieldtype": "Data", "width": 90},
		{"fieldname": "invoice_date", "label": _("Invoice Date"), "fieldtype": "Date", "width": 100},
		{"fieldname": "billing_store", "label": _("Billing store"), "fieldtype": "Data", "width": 130},
		{"fieldname": "invoice_no", "label": _("Invoice No."), "fieldtype": "Data", "width": 140},
		{"fieldname": "cust_name", "label": _("Cust. Name"), "fieldtype": "Data", "width": 150},
		{"fieldname": "cust_contact_no", "label": _("Contact No."), "fieldtype": "Data", "width": 120},
		{"fieldname": "item_brand", "label": _("Brand"), "fieldtype": "Data", "width": 100},
		{"fieldname": "category", "label": _("Category"), "fieldtype": "Data", "width": 120},
		{"fieldname": "model_number", "label": _("Model number"), "fieldtype": "Data", "width": 120},
		{"fieldname": "serial_number", "label": _("Serial number"), "fieldtype": "Data", "width": 140},
		{"fieldname": "qty", "label": _("Qty"), "fieldtype": "Float", "width": 70},
		{"fieldname": "mrp", "label": _("MRP"), "fieldtype": "Currency", "width": 110},
		{"fieldname": "billing_amount", "label": _("Billing amount"), "fieldtype": "Currency", "width": 130},
		{"fieldname": "discount_percent", "label": _("Discount %"), "fieldtype": "Percent", "width": 100},
		{"fieldname": "crm", "label": _("CRM"), "fieldtype": "Data", "width": 120},
		{"fieldname": "store", "label": _("Store"), "fieldtype": "Data", "width": 120},
		{"fieldname": "crm_value", "label": _("CRM (Value)"), "fieldtype": "Data", "width": 120},
		{"fieldname": "mode_of_payment", "label": _("Mode of payment"), "fieldtype": "Data", "width": 320},
		{"fieldname": "store_value", "label": _("Store (Value)"), "fieldtype": "Data", "width": 120},
	]


def get_data(filters):
	leads = get_leads(filters)
	if not leads:
		return []

	si_names = list({d.custom_si_ref for d in leads if d.custom_si_ref})
	invoices = get_invoices(si_names)
	items_by_invoice = get_items_by_invoice(si_names)
	payments_by_invoice = get_payment_split_by_invoice(si_names)
	customer_info = get_customer_info(leads, invoices)

	rows = []
	for lead in leads:
		si_name = lead.custom_si_ref
		payments = payments_by_invoice.get(si_name, []) if si_name else []
		mode_of_payment_str = build_mode_of_payment_string(payments)
		items = items_by_invoice.get(si_name, []) if si_name else []

		lead_row = build_lead_row(lead, invoices, customer_info, mode_of_payment_str, items)
		rows.append(lead_row)

		for idx, item in enumerate(items):
			item_row_id = f"{lead_row['lead_id']} / Item {idx + 1}"
			rows.append(build_item_row(item, lead_row["lead_id"], item_row_id))

	return rows


def build_mode_of_payment_string(payments):
	parts = [
		f"{p.mode_of_payment or 'Balance'}: {frappe.format_value(p.amount, {'fieldtype': 'Currency'})}"
		for p in payments
	]
	return ", ".join(parts)


def build_item_totals(items):
	total_qty = sum(flt(i.qty) for i in items)
	total_mrp = sum(flt(i.mrp) for i in items)
	total_amount = sum(flt(i.amount) for i in items)

	# Discount % doesn't sum meaningfully across rows — use a billing-amount
	# weighted average instead, so a big-ticket item's discount dominates
	# the summary the way it dominates the actual bill.
	if total_amount > 0:
		weighted_discount = sum(flt(i.amount) * flt(i.discount_percentage) for i in items) / total_amount
	else:
		weighted_discount = 0

	return {
		"qty": total_qty,
		"mrp": total_mrp,
		"billing_amount": total_amount,
		"discount_percent": weighted_discount,
	}

def get_leads(filters):
	conditions = []
	values = {}

	if filters.get("from_date"):
		conditions.append("DATE(creation) >= %(from_date)s")
		values["from_date"] = filters["from_date"]

	if filters.get("to_date"):
		conditions.append("DATE(creation) <= %(to_date)s")
		values["to_date"] = filters["to_date"]

	customers = as_list(filters.get("customer"))
	if customers:
		conditions.append("customer IN %(customers)s")
		values["customers"] = tuple(customers)

	lead_statuses = as_list(filters.get("lead_status"))
	if lead_statuses:
		conditions.append("workflow_state IN %(lead_statuses)s")
		values["lead_statuses"] = tuple(lead_statuses)

	lead_ids = as_list(filters.get("lead_id"))
	if lead_ids:
		conditions.append("name IN %(lead_ids)s")
		values["lead_ids"] = tuple(lead_ids)

	invoice_numbers = as_list(filters.get("invoice_number"))
	if invoice_numbers:
		conditions.append("custom_si_ref IN %(invoice_numbers)s")
		values["invoice_numbers"] = tuple(invoice_numbers)

	where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

	return frappe.db.sql(
		f"""
		SELECT
			name,
			custom_date,
			creation,
			source,
			first_name,
			type,
			customer,
			custom_brand,
			custom_model,
			mobile_no,
			qualification_status,
			custom_allocated_store,
			workflow_state,
			lead_owner,
			custom_si_ref
		FROM `tabLead`
		{where_clause}
		ORDER BY creation DESC
		""",
		values,
		as_dict=True,
	)


def as_list(value):
	"""MultiSelectList filters can arrive as a list, a JSON-encoded string,
	or a plain comma-separated string depending on how the report was
	triggered (UI vs API/scheduled). Normalize all of those to a clean list."""
	if not value:
		return []
	if isinstance(value, list):
		return [v for v in value if v]
	if isinstance(value, str):
		try:
			parsed = frappe.parse_json(value)
			if isinstance(parsed, list):
				return [v for v in parsed if v]
		except Exception:
			pass
		return [v.strip() for v in value.split(",") if v.strip()]
	return [value]


def get_invoices(si_names):
	if not si_names:
		return {}
	rows = frappe.db.get_all(
		"Sales Invoice",
		filters={"name": ["in", si_names]},
		fields=["name", "posting_date", "custom_boutique", "customer", "customer_name"],
	)
	return {r.name: r for r in rows}


def get_items_by_invoice(si_names):
	if not si_names:
		return {}
	rows = frappe.db.get_all(
		"Sales Invoice Item",
		filters={"parent": ["in", si_names]},
		fields=[
			"parent", "item_code", "brand", "item_group",
			"serial_no", "qty", "mrp", "amount",
			"discount_percentage", "sales_person",
		],
		order_by="parent, idx",
	)
	result = {}
	for r in rows:
		result.setdefault(r.parent, []).append(r)
	return result


def get_payment_split_by_invoice(si_names):
	if not si_names:
		return {}
	rows = frappe.db.get_all(
		"Sales Invoice Payment Split",
		filters={"parent": ["in", si_names]},
		fields=["parent", "mode_of_payment", "amount"],
		order_by="parent, idx",
	)
	result = {}
	for r in rows:
		result.setdefault(r.parent, []).append(r)
	return result


def get_customer_info(leads, invoices):
	customer_names = set()
	for lead in leads:
		if lead.customer:
			customer_names.add(lead.customer)
	for inv in invoices.values():
		if inv.customer:
			customer_names.add(inv.customer)

	if not customer_names:
		return {}

	rows = frappe.db.get_all(
		"Customer",
		filters={"name": ["in", list(customer_names)]},
		fields=["name", "custom_client_tiers", "custom_contact"],
	)
	return {r.name: r for r in rows}


def build_lead_row(lead, invoices, customer_info, mode_of_payment_str, items):
	invoice = invoices.get(lead.custom_si_ref) if lead.custom_si_ref else None
	lead_customer = customer_info.get(lead.customer) if lead.customer else None
	inv_customer = customer_info.get(invoice.customer) if invoice and invoice.customer else None
	lead_date = getdate(lead.custom_date) if lead.custom_date else None
	totals = build_item_totals(items)

	return {
		"lead_id": lead.name,
		"parent_lead_id": "",
		"indent": 0,
		"month": lead_date.strftime("%B %Y") if lead_date else "",
		"date": lead.custom_date,
		"source_of_lead": lead.source,
		"name_of_enquirer": lead.first_name,
		"existing_customer": lead.type,
		"loyalty_status": lead_customer.custom_client_tiers if lead_customer else "",
		"lead_brand": lead.custom_brand,
		"model_no": lead.custom_model,
		"contact_no": lead.mobile_no,
		"qualified": "Yes" if lead.qualification_status == "Qualified" else "No",
		"allocated_store": lead.custom_allocated_store,
		"lead_status": lead.workflow_state,
		"closed_won": "Yes" if lead.workflow_state == "Closed Won" else "No",
		"invoice_date": invoice.posting_date if invoice else None,
		"billing_store": invoice.custom_boutique if invoice else "",
		"invoice_no": invoice.name if invoice else "",
		"cust_name": invoice.customer_name if invoice else "",
		"cust_contact_no": inv_customer.custom_contact if inv_customer else "",
		"crm": lead.lead_owner,
		"crm_value": lead.lead_owner,
		"mode_of_payment": mode_of_payment_str,
		"qty": totals["qty"],
		"mrp": totals["mrp"],
		"billing_amount": totals["billing_amount"],
		"discount_percent": totals["discount_percent"],
	}


def build_item_row(item, lead_id, item_row_id):
	return {
		"lead_id": item_row_id,
		"parent_lead_id": lead_id,
		"indent": 1,
		"item_brand": item.brand,
		"category": item.item_group,
		"model_number": "",  # left blank — fill in once the Item field is confirmed
		"serial_number": item.serial_no,
		"qty": item.qty,
		"mrp": item.mrp,
		"billing_amount": item.amount,
		"discount_percent": item.discount_percentage,
		"store": item.sales_person,
		"store_value": item.sales_person,
	}