import calendar

import frappe
from frappe import _
from frappe.utils import cint, cstr, getdate


def execute(filters=None):    
        
    return get_columns(filters),get_data(filters)
    

def get_columns(filters):
    return [
        {
            "label": _("Customer"),
            "fieldname": "customer",
            "fieldtype": "Link",
            "options":"Customer",
            "width": 125,
        },
        {
            "label": _("Number of Invoice"),
            "fieldname": "count",
            "fieldtype": "Int",
            "width": 125,
        },
        {
            "label": _("Total Sales"),
            "fieldname": "total_sales",
            "fieldtype": "Float",
            "width": 125,
        }
    ]


def get_data(filters):

    customers = []

    invoice = frappe.db.sql("""select posting_date, customer, base_grand_total from `tabSales Invoice` where docstatus=1 and posting_date between %(from_date)s and %(to_date)s order by posting_date""",({
        "from_date":filters.get('from_date'),
        "to_date":filters.get('to_date')
    }),as_dict=1)

    return process_customers_for_report(invoice,filters)

 

def process_customers_for_report(customers,filters):
    new_customer_dict = {}
    repeated_customer_dict = {}
    new_customer_list = []
    repeated_customer_list = []
    for customer in customers:
        customer_name = customer['customer']
        if if_existng_customer(customer['posting_date'],customer_name):
            if customer_name not in repeated_customer_dict:
                    repeated_customer_dict[customer_name] = {'customer': customer_name, 'total_sales': customer['base_grand_total'], 'count': 1}
            else:
                repeated_customer_dict[customer_name]['total_sales'] += customer['base_grand_total']
                repeated_customer_dict[customer_name]['count'] += 1
        else:
            if customer_name not in new_customer_dict:
                new_customer_dict[customer_name] = {'customer': customer_name, 'total_sales': customer['base_grand_total'], 'count': 1}
            else:
                if customer_name not in repeated_customer_dict:
                    repeated_customer_dict[customer_name] = {'customer': customer_name, 'total_sales': customer['base_grand_total'], 'count': 1}
                else:
                    repeated_customer_dict[customer_name]['total_sales'] += customer['base_grand_total']
                    repeated_customer_dict[customer_name]['count'] += 1



    if filters.get("report_type") == "New":
        result_list = list(new_customer_dict.values())
    else:
        result_list = list(repeated_customer_dict.values())

    return result_list


def if_existng_customer(from_date,customer):
    
    invoice_data = frappe.db.sql("""select count(name) as invoice_count from `tabSales Invoice` where docstatus=1 and posting_date < %(from_date)s 
    and customer = %(customer)s group by customer""",({
        "from_date":from_date,
        "customer":customer
    }),as_dict=1)
  
    if invoice_data and int(invoice_data[0]['invoice_count']) > 0:
        return True
    else:
        return False

def group_by_customer(data):
    result = {}
    for d in data:
        key = d['customer']
        if key not in result:
            result[key] = {"base_grand_total": d["base_grand_total"], "record_count": 1}
        else:
            result[key]["base_grand_total"] += d["base_grand_total"]
            result[key]["record_count"] += 1
    return result


