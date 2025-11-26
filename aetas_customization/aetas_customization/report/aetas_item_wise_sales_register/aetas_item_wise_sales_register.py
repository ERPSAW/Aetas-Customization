# Copyright (c) 2023, Akhilam Inc and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.meta import get_field_precision
from frappe.utils import cstr, flt
from frappe.utils.xlsxutils import handle_html

from erpnext.accounts.report.sales_register.sales_register import get_mode_of_payments
from erpnext.selling.report.item_wise_sales_history.item_wise_sales_history import (
	get_customer_details,
	get_item_details,
)
import re

def execute(filters=None):
	return _execute(filters)


def _execute(filters=None, additional_table_columns=None, additional_query_columns=None):
	if not filters:
		filters = {}
	columns = get_columns(additional_table_columns, filters)

	company_currency = frappe.get_cached_value("Company", filters.get("company"), "default_currency")

	item_list = get_items(filters, additional_query_columns)
	if item_list:
		itemised_tax, tax_columns = get_tax_accounts(item_list, columns, company_currency)

	mode_of_payments = get_mode_of_payments(set(d.parent for d in item_list))
	so_dn_map = get_delivery_notes_against_sales_order(item_list)

	data = []
	total_row_map = {}
	skip_total_row = 0
	prev_group_by_value = ""

	if filters.get("group_by"):
		grand_total = get_grand_total(filters, "Sales Invoice")

	customer_details = get_customer_details()
	item_details = get_item_details()

	for d in item_list:
		customer_record = customer_details.get(d.customer)
		item_record = item_details.get(d.item_code)

		delivery_note = None
		if d.delivery_note:
			delivery_note = d.delivery_note
		elif d.so_detail:
			delivery_note = ", ".join(so_dn_map.get(d.so_detail, []))

		if not delivery_note and d.update_stock:
			delivery_note = d.parent

		row = {
			"item_code": d.item_code,
			"item_name": item_record.item_name if item_record else d.item_name,
			"item_group": item_record.item_group if item_record else d.item_group,
			"description": d.description,
			"invoice": d.parent,
			"posting_date": d.posting_date,
			"customer": d.customer,
			"customer_name": customer_record.customer_name,
			"customer_group": customer_record.customer_group,
			"mrp":d.mrp,
			"sales_person":d.sales_person,
			"serial_no":d.serial_no
		}
		# Convert mrp to float safely
		try:
			mrp_value = float(d.mrp)
		except (TypeError, ValueError):
			mrp_value = None  # if not convertible (e.g. empty or invalid)

		# Now check safely
		if mrp_value is not None and mrp_value >= 0:
			row["mrp"] = mrp_value
		else:
			# Fetch from Item master if MRP < 0 or invalid
			item_mrp = frappe.db.get_value("Item", d.item_code, "mrp") or 0
			row["mrp"] = item_mrp


		if additional_query_columns:
			for col in additional_query_columns:
				row.update({col: d.get(col)})

		row.update(
			{
				"debit_to": d.debit_to,
				"mode_of_payment": ", ".join(mode_of_payments.get(d.parent, [])),
				"territory": d.territory,
				"project": d.project,
				"company": d.company,
				"sales_order": d.sales_order,
				"delivery_note": d.delivery_note,
				"income_account": d.unrealized_profit_loss_account
				if d.is_internal_customer == 1
				else d.income_account,
				"cost_center": d.cost_center,
				"stock_qty": d.stock_qty,
				"stock_uom": d.stock_uom,
			}
		)

		if d.stock_uom != d.uom and d.stock_qty:
			row.update({"rate": (d.base_net_rate * d.qty) / d.stock_qty, "amount": d.base_net_amount})
		else:
			row.update({"rate": d.base_net_rate, "amount": d.base_net_amount})

		total_tax = 0
		total_other_charges = 0
		for tax in tax_columns:
			item_tax = itemised_tax.get(d.name, {}).get(tax, {})
			row.update(
				{
					frappe.scrub(tax + " Rate"): item_tax.get("tax_rate", 0),
					frappe.scrub(tax + " Amount"): item_tax.get("tax_amount", 0),
				}
			)
			if item_tax.get("is_other_charges"):
				total_other_charges += flt(item_tax.get("tax_amount"))
			else:
				total_tax += flt(item_tax.get("tax_amount"))

		row.update(
			{
				"total_tax": total_tax,
				"total_other_charges": total_other_charges,
				"total": d.base_net_amount + total_tax,
				"currency": company_currency,
			}
		)

		if filters.get("group_by"):
			row.update({"percent_gt": flt(row["total"] / grand_total) * 100})
			group_by_field, subtotal_display_field = get_group_by_and_display_fields(filters)
			data, prev_group_by_value = add_total_row(
				data,
				filters,
				prev_group_by_value,
				d,
				total_row_map,
				group_by_field,
				subtotal_display_field,
				grand_total,
				tax_columns,
			)
			add_sub_total_row(row, total_row_map, d.get(group_by_field, ""), tax_columns)

		data.append(row)

	if filters.get("group_by") and item_list:
		total_row = total_row_map.get(prev_group_by_value or d.get("item_name"))
		total_row["percent_gt"] = flt(total_row["total"] / grand_total * 100)
		data.append(total_row)
		data.append({})
		add_sub_total_row(total_row, total_row_map, "total_row", tax_columns)
		data.append(total_row_map.get("total_row"))
		skip_total_row = 1
	
	get_purchase_rate(data)
	get_customer_type(data)

	customer_type_filter = filters.get("customer_type")
	if customer_type_filter:
		data = [d for d in data if d.get("customer_type") == customer_type_filter]

	return columns, data, None, None, None, skip_total_row

def get_purchase_rate(data):
	if not data:
		return data

	# --- Collect unique item_codes & serial_nos ---
	item_codes = list({d.get("item_code") for d in data if d.get("item_code")})
	serial_nos = list({d.get("serial_no") for d in data if d.get("serial_no")})

	if not item_codes:
		return data

	serial_rate_map = {}
	serial_mrp_map = {}
	sle_rate_map = {}

	# ============================================================
	# ✅ 1) SERIALIZED ITEMS → STOCK ENTRY + PURCHASE INVOICE
	# ============================================================
	if serial_nos:

		regexp_pattern = "(" + "|".join([fr"(^|\n){sn}(\n|$)" for sn in serial_nos]) + ")"

		# ✅ STOCK ENTRY DETAIL (highest priority)
		sed_rows = frappe.db.sql(f"""
			SELECT
				item_code,
				serial_no,
				basic_rate,
				custom_mrp
			FROM `tabStock Entry Detail`
			WHERE item_code IN %(items)s
			AND serial_no REGEXP %(pattern)s
			ORDER BY modified DESC
		""", {"items": item_codes, "pattern": regexp_pattern}, as_dict=True)

		for row in sed_rows:
			for sn in serial_nos:
				if re.search(fr"(^|\n){sn}(\n|$)", row.serial_no or ""):
					key = (row.item_code, sn)
					if key not in serial_rate_map:
						serial_rate_map[key] = row.basic_rate or 0
					if key not in serial_mrp_map:
						serial_mrp_map[key] = row.custom_mrp or 0

		# ✅ PURCHASE INVOICE ITEM (fallback)
		pi_rows = frappe.db.sql(f"""
			SELECT
				item_code,
				serial_no,
				net_rate,
				mrp
			FROM `tabPurchase Invoice Item`
			WHERE item_code IN %(items)s
			AND serial_no REGEXP %(pattern)s
			ORDER BY modified DESC
		""", {"items": item_codes, "pattern": regexp_pattern}, as_dict=True)

		for row in pi_rows:
			for sn in serial_nos:
				if re.search(fr"(^|\n){sn}(\n|$)", row.serial_no or ""):
					key = (row.item_code, sn)
					if key not in serial_rate_map:
						serial_rate_map[key] = row.net_rate or 0
					if key not in serial_mrp_map:
						serial_mrp_map[key] = row.mrp or 0

	# ============================================================
	# ✅ 2) NON-SERIAL ITEMS → SALES INVOICE (SLE rate only)
	# ============================================================
	invoice_item_pairs = [
		(d.get("invoice"), d.get("item_code"))
		for d in data if not d.get("serial_no") and d.get("invoice")
	]

	invoices = list({inv for inv, _ in invoice_item_pairs})

	if invoices:
		sle_rows = frappe.db.sql("""
			SELECT
				item_code,
				voucher_no,
				COALESCE(valuation_rate, incoming_rate, 0) AS rate
			FROM `tabStock Ledger Entry`
			WHERE voucher_type = 'Sales Invoice'
			AND voucher_no IN %(invoices)s
			AND item_code IN %(items)s
			AND (valuation_rate > 0 OR incoming_rate > 0)
			ORDER BY posting_date DESC, posting_time DESC
		""", {"invoices": invoices, "items": item_codes}, as_dict=True)

		for row in sle_rows:
			key = (row.voucher_no, row.item_code)
			if key not in sle_rate_map:
				sle_rate_map[key] = row.rate

	# ============================================================
	# ✅ 3) FETCH ITEM MRP (FINAL FALLBACK FOR BOTH)
	# ============================================================
	item_master = frappe.db.get_all(
		"Item",
		filters={"name": ["in", item_codes]},
		fields=["name", "mrp"]
	)

	item_mrp_map = {row.name: (row.mrp or 0) for row in item_master}

	# ============================================================
	# ✅ 4) APPLY VALUES BACK TO INPUT DATA
	# ============================================================
	for d in data:
		item_code = d.get("item_code")
		if not item_code:
			continue

		serial_no = d.get("serial_no")
		invoice = d.get("invoice")

		# ✅ SERIALIZED ITEMS
		if serial_no:
			d["purchase_rate"] = serial_rate_map.get((item_code, serial_no), 0)
			mrp = serial_mrp_map.get((item_code, serial_no), 0)

		# ✅ NON-SERIAL ITEMS
		else:
			d["purchase_rate"] = sle_rate_map.get((invoice, item_code), 0)
			mrp = 0  # no serial-based MRP

		# ✅ GUARANTEED MRP FALLBACK FOR BOTH CASES
		if not mrp:
			mrp = item_mrp_map.get(item_code, 0)

		d["mrp"] = mrp

	return data





def get_customer_type(data):
	if not data:
		return data

	customers = list({d['customer'] for d in data if d.get('customer')})
	if not customers:
		return data

	# Get invoice counts for all customers at once
	invoice_counts = frappe.db.get_all(
		"Sales Invoice",
		filters={"customer": ["in", customers]},
		fields=["customer", "count(name) as invoice_count"],
		group_by="customer"
	)

	# Convert list of dicts into {customer: count}
	invoice_count_map = {d["customer"]: d["invoice_count"] for d in invoice_counts}

	# Add customer_type to each record
	for d in data:
		customer = d.get("customer")
		if not customer:
			continue
		count = invoice_count_map.get(customer, 0)
		d["customer_type"] = "Repeated" if count > 1 else "New"

	return data



def get_columns(additional_table_columns, filters):
	columns = []

	if filters.get("group_by") != ("Item"):
		columns.extend(
			[
				{
					"label": _("Item Code"),
					"fieldname": "item_code",
					"fieldtype": "Link",
					"options": "Item",
					"width": 120,
				},
				{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 120},
			]
		)

	if filters.get("group_by") not in ("Item", "Item Group"):
		columns.extend(
			[
				{
					"label": _("Item Group"),
					"fieldname": "item_group",
					"fieldtype": "Link",
					"options": "Item Group",
					"width": 120,
				}
			]
		)

	columns.extend(
		[
			{"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 150},
			{
				"label": _("Invoice"),
				"fieldname": "invoice",
				"fieldtype": "Link",
				"options": "Sales Invoice",
				"width": 120,
			},
			{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 120},
		]
	)

	if filters.get("group_by") != "Customer":
		columns.extend(
			[
				{
					"label": _("Customer Group"),
					"fieldname": "customer_group",
					"fieldtype": "Link",
					"options": "Customer Group",
					"width": 120,
				}
			]
		)

	if filters.get("group_by") not in ("Customer", "Customer Group"):
		columns.extend(
			[
				{
					"label": _("Customer"),
					"fieldname": "customer",
					"fieldtype": "Link",
					"options": "Customer",
					"width": 120,
				},
				{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 120},
			]
		)

	if additional_table_columns:
		columns += additional_table_columns

	columns += [
		{
			"label": _("Receivable Account"),
			"fieldname": "debit_to",
			"fieldtype": "Link",
			"options": "Account",
			"width": 80,
		},
		{
			"label": _("Mode Of Payment"),
			"fieldname": "mode_of_payment",
			"fieldtype": "Data",
			"width": 120,
		},
	]

	if filters.get("group_by") != "Territory":
		columns.extend(
			[
				{
					"label": _("Territory"),
					"fieldname": "territory",
					"fieldtype": "Link",
					"options": "Territory",
					"width": 80,
				}
			]
		)

	columns += [
		{
			"label": _("Project"),
			"fieldname": "project",
			"fieldtype": "Link",
			"options": "Project",
			"width": 80,
		},
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 80,
		},
		{
			"label": _("Sales Order"),
			"fieldname": "sales_order",
			"fieldtype": "Link",
			"options": "Sales Order",
			"width": 100,
		},
		{
			"label": _("Delivery Note"),
			"fieldname": "delivery_note",
			"fieldtype": "Link",
			"options": "Delivery Note",
			"width": 100,
		},
		{
			"label": _("Income Account"),
			"fieldname": "income_account",
			"fieldtype": "Link",
			"options": "Account",
			"width": 100,
		},
		{
			"label": _("Cost Center"),
			"fieldname": "cost_center",
			"fieldtype": "Link",
			"options": "Cost Center",
			"width": 100,
		},
		{"label": _("Stock Qty"), "fieldname": "stock_qty", "fieldtype": "Float", "width": 100},
		{
			"label": _("Stock UOM"),
			"fieldname": "stock_uom",
			"fieldtype": "Link",
			"options": "UOM",
			"width": 100,
		},
		{
			"label": _("Customer Type"),
			"fieldname": "customer_type",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("Purchase Rate"),
			"fieldname": "purchase_rate",
			"fieldtype": "Float",
			"options": "currency",
			"width": 100,
		},
		{
			"label": _("Rate"),
			"fieldname": "rate",
			"fieldtype": "Float",
			"options": "currency",
			"width": 100,
		},
		{
			"label": _("Amount"),
			"fieldname": "amount",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 100,
		},
		{
			"fieldname": "mrp",
			"label": _("MRP"),
			"fieldtype": "Currency",
			"width": 80,
		},
		{
			"fieldname": "sales_person",
			"label": _("Sales Person"),
			"fieldtype": "Data",
			"width": 80,
		},
		{
			"fieldname": "serial_no",
			"label": _("Serial No"),
			"fieldtype": "Data",
			"width": 80,
		},
	]

	if filters.get("group_by"):
		columns.append(
			{"label": _("% Of Grand Total"), "fieldname": "percent_gt", "fieldtype": "Float", "width": 80}
		)

	return columns


def get_conditions(filters):
	conditions = ""

	for opts in (
		("company", " and company=%(company)s"),
		("customer", " and `tabSales Invoice`.customer = %(customer)s"),
		("item_code", " and `tabSales Invoice Item`.item_code = %(item_code)s"),
		("from_date", " and `tabSales Invoice`.posting_date>=%(from_date)s"),
		("to_date", " and `tabSales Invoice`.posting_date<=%(to_date)s"),
	):
		if filters.get(opts[0]):
			conditions += opts[1]

	if filters.get("mode_of_payment"):
		conditions += """ and exists(select name from `tabSales Invoice Payment`
			where parent=`tabSales Invoice`.name
				and ifnull(`tabSales Invoice Payment`.mode_of_payment, '') = %(mode_of_payment)s)"""

	if filters.get("warehouse"):
		conditions += """and ifnull(`tabSales Invoice Item`.warehouse, '') = %(warehouse)s"""

	if filters.get("brand"):
		conditions += """and ifnull(`tabSales Invoice Item`.brand, '') = %(brand)s"""

	if filters.get("item_group"):
		conditions += """and ifnull(`tabSales Invoice Item`.item_group, '') = %(item_group)s"""

	if not filters.get("group_by"):
		conditions += (
			"ORDER BY `tabSales Invoice`.posting_date desc, `tabSales Invoice Item`.item_group desc"
		)
	else:
		conditions += get_group_by_conditions(filters, "Sales Invoice")

	return conditions


def get_group_by_conditions(filters, doctype):
	if filters.get("group_by") == "Invoice":
		return "ORDER BY `tab{0} Item`.parent desc".format(doctype)
	elif filters.get("group_by") == "Item":
		return "ORDER BY `tab{0} Item`.`item_code`".format(doctype)
	elif filters.get("group_by") == "Item Group":
		return "ORDER BY `tab{0} Item`.{1}".format(doctype, frappe.scrub(filters.get("group_by")))
	elif filters.get("group_by") in ("Customer", "Customer Group", "Territory", "Supplier"):
		return "ORDER BY `tab{0}`.{1}".format(doctype, frappe.scrub(filters.get("group_by")))


def get_items(filters, additional_query_columns):
	conditions = get_conditions(filters)

	if additional_query_columns:
		additional_query_columns = ", " + ", ".join(additional_query_columns)
	else:
		additional_query_columns = ""

	return frappe.db.sql(
		"""
		select
			`tabSales Invoice Item`.name, `tabSales Invoice Item`.parent,
			`tabSales Invoice`.posting_date, `tabSales Invoice`.debit_to,
			`tabSales Invoice`.unrealized_profit_loss_account,
			`tabSales Invoice`.is_internal_customer,
			`tabSales Invoice`.project, `tabSales Invoice`.customer, `tabSales Invoice`.remarks,
			`tabSales Invoice`.territory, `tabSales Invoice`.company, `tabSales Invoice`.base_net_total,
			`tabSales Invoice Item`.item_code, `tabSales Invoice Item`.description,
			`tabSales Invoice Item`.`item_name`, `tabSales Invoice Item`.`item_group`,
			`tabSales Invoice Item`.sales_order, `tabSales Invoice Item`.delivery_note,
			`tabSales Invoice Item`.income_account, `tabSales Invoice Item`.cost_center,
			`tabSales Invoice Item`.stock_qty, `tabSales Invoice Item`.stock_uom,
			`tabSales Invoice Item`.base_net_rate, `tabSales Invoice Item`.base_net_amount,
			`tabSales Invoice`.customer_name, `tabSales Invoice`.customer_group, `tabSales Invoice Item`.so_detail,
			`tabSales Invoice`.update_stock, `tabSales Invoice Item`.uom, `tabSales Invoice Item`.qty, `tabSales Invoice Item`.mrp,`tabSales Invoice Item`.sales_person,`tabSales Invoice Item`.serial_no {0}
		from `tabSales Invoice`, `tabSales Invoice Item`
		where `tabSales Invoice`.name = `tabSales Invoice Item`.parent
			and `tabSales Invoice`.docstatus = 1 {1}
		""".format(
			additional_query_columns or "", conditions
		),
		filters,
		as_dict=1,
	)  # nosec


def get_delivery_notes_against_sales_order(item_list):
	so_dn_map = frappe._dict()
	so_item_rows = list(set([d.so_detail for d in item_list]))

	if so_item_rows:
		delivery_notes = frappe.db.sql(
			"""
			select parent, so_detail
			from `tabDelivery Note Item`
			where docstatus=1 and so_detail in (%s)
			group by so_detail, parent
		"""
			% (", ".join(["%s"] * len(so_item_rows))),
			tuple(so_item_rows),
			as_dict=1,
		)

		for dn in delivery_notes:
			so_dn_map.setdefault(dn.so_detail, []).append(dn.parent)

	return so_dn_map


def get_grand_total(filters, doctype):

	return frappe.db.sql(
		""" SELECT
		SUM(`tab{0}`.base_grand_total)
		FROM `tab{0}`
		WHERE `tab{0}`.docstatus = 1
		and posting_date between %s and %s
	""".format(
			doctype
		),
		(filters.get("from_date"), filters.get("to_date")),
	)[0][
		0
	]  # nosec


def get_tax_accounts(
	item_list,
	columns,
	company_currency,
	doctype="Sales Invoice",
	tax_doctype="Sales Taxes and Charges",
):
	import json

	item_row_map = {}
	tax_columns = []
	invoice_item_row = {}
	itemised_tax = {}
	add_deduct_tax = "charge_type"

	tax_amount_precision = (
		get_field_precision(
			frappe.get_meta(tax_doctype).get_field("tax_amount"), currency=company_currency
		)
		or 2
	)

	for d in item_list:
		invoice_item_row.setdefault(d.parent, []).append(d)
		item_row_map.setdefault(d.parent, {}).setdefault(d.item_code or d.item_name, []).append(d)

	conditions = ""
	if doctype == "Purchase Invoice":
		conditions = " and category in ('Total', 'Valuation and Total') and base_tax_amount_after_discount_amount != 0"
		add_deduct_tax = "add_deduct_tax"

	tax_details = frappe.db.sql(
		"""
		select
			name, parent, description, item_wise_tax_detail, account_head,
			charge_type, {add_deduct_tax}, base_tax_amount_after_discount_amount
		from `tab%s`
		where
			parenttype = %s and docstatus = 1
			and (description is not null and description != '')
			and parent in (%s)
			%s
		order by description
	""".format(
			add_deduct_tax=add_deduct_tax
		)
		% (tax_doctype, "%s", ", ".join(["%s"] * len(invoice_item_row)), conditions),
		tuple([doctype] + list(invoice_item_row)),
	)

	account_doctype = frappe.qb.DocType("Account")

	query = (
		frappe.qb.from_(account_doctype)
		.select(account_doctype.name)
		.where((account_doctype.account_type == "Tax"))
	)

	tax_accounts = query.run()

	for (
		name,
		parent,
		description,
		item_wise_tax_detail,
		account_head,
		charge_type,
		add_deduct_tax,
		tax_amount,
	) in tax_details:
		description = handle_html(description)
		if description not in tax_columns and tax_amount:
			# as description is text editor earlier and markup can break the column convention in reports
			tax_columns.append(description)

		if item_wise_tax_detail:
			try:
				item_wise_tax_detail = json.loads(item_wise_tax_detail)

				for item_code, tax_data in item_wise_tax_detail.items():
					itemised_tax.setdefault(item_code, frappe._dict())

					if isinstance(tax_data, list):
						tax_rate, tax_amount = tax_data
					else:
						tax_rate = tax_data
						tax_amount = 0

					if charge_type == "Actual" and not tax_rate:
						tax_rate = "NA"

					item_net_amount = sum(
						[flt(d.base_net_amount) for d in item_row_map.get(parent, {}).get(item_code, [])]
					)

					for d in item_row_map.get(parent, {}).get(item_code, []):
						item_tax_amount = (
							flt((tax_amount * d.base_net_amount) / item_net_amount) if item_net_amount else 0
						)
						if item_tax_amount:
							tax_value = flt(item_tax_amount, tax_amount_precision)
							tax_value = (
								tax_value * -1
								if (doctype == "Purchase Invoice" and add_deduct_tax == "Deduct")
								else tax_value
							)

							itemised_tax.setdefault(d.name, {})[description] = frappe._dict(
								{
									"tax_rate": tax_rate,
									"tax_amount": tax_value,
									"is_other_charges": 0 if tuple([account_head]) in tax_accounts else 1,
								}
							)

			except ValueError:
				continue
		elif charge_type == "Actual" and tax_amount:
			for d in invoice_item_row.get(parent, []):
				itemised_tax.setdefault(d.name, {})[description] = frappe._dict(
					{
						"tax_rate": "NA",
						"tax_amount": flt((tax_amount * d.base_net_amount) / d.base_net_total, tax_amount_precision),
					}
				)

	tax_columns.sort()
	for desc in tax_columns:
		columns.append(
			{
				"label": _(desc + " Rate"),
				"fieldname": frappe.scrub(desc + " Rate"),
				"fieldtype": "Float",
				"width": 100,
			}
		)

		columns.append(
			{
				"label": _(desc + " Amount"),
				"fieldname": frappe.scrub(desc + " Amount"),
				"fieldtype": "Currency",
				"options": "currency",
				"width": 100,
			}
		)

	columns += [
		{
			"label": _("Total Tax"),
			"fieldname": "total_tax",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 100,
		},
		{
			"label": _("Total Other Charges"),
			"fieldname": "total_other_charges",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 100,
		},
		{
			"label": _("Total"),
			"fieldname": "total",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 100,
		},
		{
			"fieldname": "currency",
			"label": _("Currency"),
			"fieldtype": "Currency",
			"width": 80,
			"hidden": 1,
		},
	]

	return itemised_tax, tax_columns


def add_total_row(
	data,
	filters,
	prev_group_by_value,
	item,
	total_row_map,
	group_by_field,
	subtotal_display_field,
	grand_total,
	tax_columns,
):
	if prev_group_by_value != item.get(group_by_field, ""):
		if prev_group_by_value:
			total_row = total_row_map.get(prev_group_by_value)
			data.append(total_row)
			data.append({})
			add_sub_total_row(total_row, total_row_map, "total_row", tax_columns)

		prev_group_by_value = item.get(group_by_field, "")

		total_row_map.setdefault(
			item.get(group_by_field, ""),
			{
				subtotal_display_field: get_display_value(filters, group_by_field, item),
				"stock_qty": 0.0,
				"amount": 0.0,
				"bold": 1,
				"total_tax": 0.0,
				"total": 0.0,
				"percent_gt": 0.0,
			},
		)

		total_row_map.setdefault(
			"total_row",
			{
				subtotal_display_field: "Total",
				"stock_qty": 0.0,
				"amount": 0.0,
				"bold": 1,
				"total_tax": 0.0,
				"total": 0.0,
				"percent_gt": 0.0,
			},
		)

	return data, prev_group_by_value


def get_display_value(filters, group_by_field, item):
	if filters.get("group_by") == "Item":
		if item.get("item_code") != item.get("item_name"):
			value = (
				cstr(item.get("item_code"))
				+ "<br><br>"
				+ "<span style='font-weight: normal'>"
				+ cstr(item.get("item_name"))
				+ "</span>"
			)
		else:
			value = item.get("item_code", "")
	elif filters.get("group_by") in ("Customer", "Supplier"):
		party = frappe.scrub(filters.get("group_by"))
		if item.get(party) != item.get(party + "_name"):
			value = (
				item.get(party)
				+ "<br><br>"
				+ "<span style='font-weight: normal'>"
				+ item.get(party + "_name")
				+ "</span>"
			)
		else:
			value = item.get(party)
	else:
		value = item.get(group_by_field)

	return value


def get_group_by_and_display_fields(filters):
	if filters.get("group_by") == "Item":
		group_by_field = "item_code"
		subtotal_display_field = "invoice"
	elif filters.get("group_by") == "Invoice":
		group_by_field = "parent"
		subtotal_display_field = "item_code"
	else:
		group_by_field = frappe.scrub(filters.get("group_by"))
		subtotal_display_field = "item_code"

	return group_by_field, subtotal_display_field


def add_sub_total_row(item, total_row_map, group_by_value, tax_columns):
	total_row = total_row_map.get(group_by_value)
	total_row["stock_qty"] += item["stock_qty"]
	total_row["amount"] += item["amount"]
	total_row["total_tax"] += item["total_tax"]
	total_row["total"] += item["total"]
	total_row["percent_gt"] += item["percent_gt"]

	for tax in tax_columns:
		total_row.setdefault(frappe.scrub(tax + " Amount"), 0.0)
		total_row[frappe.scrub(tax + " Amount")] += flt(item[frappe.scrub(tax + " Amount")])
