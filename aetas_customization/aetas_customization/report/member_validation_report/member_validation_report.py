# Copyright (c) 2026, Akhilam Inc and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
    filters = filters or {}

    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns():
    return [
        {
            "fieldname": "customer",
            "label": "Customer ID",
            "fieldtype": "Link",
            "options": "Customer",
            "width": 150,
        },
        {
            "fieldname": "customer_name",
            "label": "Name of Customer",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "fieldname": "boutique",
            "label": "Enrolment Store Location",
            "fieldtype": "Link",
            "options": "Boutique",
            "width": 180,
        },
        {
            "fieldname": "city",
            "label": "City",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "fieldname": "current_tier",
            "label": "Current Tier",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "fieldname": "points_balance",
            "label": "Points Balance",
            "fieldtype": "Float",
            "width": 120,
        },
        {
            "fieldname": "last_transaction_date",
            "label": "Last Transaction Date",
            "fieldtype": "Date",
            "width": 140,
        },
        {
            "fieldname": "customer_creation_date",
            "label": "Customer Creation Date",
            "fieldtype": "Date",
            "width": 140,
        },
        {
            "fieldname": "mobile",
            "label": "Mobile No",
            "fieldtype": "Data",
            "width": 130,
        },
        {
            "fieldname": "mobile_validated",
            "label": "Mobile Validated",
            "fieldtype": "Data",
            "width": 90,
        },
        {
            "fieldname": "email",
            "label": "Email ID",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "fieldname": "email_validated",
            "label": "Email Validated",
            "fieldtype": "Data",
            "width": 90,
        },
        {
            "fieldname": "birthday",
            "label": "Bday",
            "fieldtype": "Date",
            "width": 100,
        },
        {
            "fieldname": "bday_validated",
            "label": "Bday Validated",
            "fieldtype": "Data",
            "width": 90,
        },
        {
            "fieldname": "anniversary",
            "label": "Anniversary",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "fieldname": "anniversary_validated",
            "label": "Anniversary Validated",
            "fieldtype": "Data",
            "width": 110,
        },
    ]


def get_data(filters):
    conditions = []
    values = {}

    # Optional Customer filter
    if filters.get("customer"):
        conditions.append("c.name = %(customer)s")
        values["customer"] = filters.get("customer")

    if filters.get("current_tier"):
        conditions.append("c.custom_client_tiers = %(current_tier)s")
        values["current_tier"] = filters.get("current_tier")

    if filters.get("boutique"):
        conditions.append("first_invoice.boutique = %(boutique)s")
        values["boutique"] = filters.get("boutique")
        	    
    where_clause = ""

    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT
            c.name AS customer,
            c.customer_name AS customer_name,

            first_invoice.boutique AS boutique,

            addr.city AS city,

            c.custom_client_tiers AS current_tier,

            c.mkt_credit_balance AS points_balance,

            last_invoice.last_transaction_date AS last_transaction_date,

            DATE(c.creation) AS customer_creation_date,

            c.custom_contact AS mobile,

            CASE
                WHEN mobile_val.yes = 1 THEN 'Yes'
                WHEN mobile_val.no = 1 THEN 'No'
                ELSE ''
            END AS mobile_validated,

            c.custom_email AS email,

            CASE
                WHEN email_val.yes = 1 THEN 'Yes'
                WHEN email_val.no = 1 THEN 'No'
                ELSE ''
            END AS email_validated,

            c.custom_date_of_birth AS birthday,

            CASE
                WHEN bday_val.yes = 1 THEN 'Yes'
                WHEN bday_val.no = 1 THEN 'No'
                ELSE ''
            END AS bday_validated,

            c.custom_anniversary_date AS anniversary,

            CASE
                WHEN anniv_val.yes = 1 THEN 'Yes'
                WHEN anniv_val.no = 1 THEN 'No'
                ELSE ''
            END AS anniversary_validated

        FROM
            `tabCustomer` c

        LEFT JOIN
            (
                SELECT
                    si.customer,
                    si.custom_boutique AS boutique

                FROM
                    `tabSales Invoice` si

                WHERE
                    si.docstatus = 1
                    AND si.status = 'Paid'

                    AND si.posting_date = (
                        SELECT MIN(si2.posting_date)

                        FROM `tabSales Invoice` si2

                        WHERE
                            si2.customer = si.customer
                            AND si2.docstatus = 1
                            AND si2.status = 'Paid'
                    )

                GROUP BY
                    si.customer
            ) first_invoice
            ON first_invoice.customer = c.name

        LEFT JOIN
            (
                SELECT
                    si_last.customer,
                    MAX(si_last.posting_date) AS last_transaction_date
                FROM
                    `tabSales Invoice` si_last
                WHERE
                    si_last.docstatus = 1
                GROUP BY
                    si_last.customer
            ) last_invoice
            ON last_invoice.customer = c.name

        LEFT JOIN
            `tabBoutique`
            ON `tabBoutique`.name = first_invoice.boutique

        LEFT JOIN
            `tabAddress` addr
            ON addr.name = `tabBoutique`.boutique_location

        LEFT JOIN
            `tabCustomer Validation Detail` mobile_val
            ON mobile_val.parent = c.name
            AND mobile_val.field_name = 'Contact'

        LEFT JOIN
            `tabCustomer Validation Detail` email_val
            ON email_val.parent = c.name
            AND email_val.field_name = 'Email'

        LEFT JOIN
            `tabCustomer Validation Detail` bday_val
            ON bday_val.parent = c.name
            AND bday_val.field_name = 'Date of Birth'

        LEFT JOIN
            `tabCustomer Validation Detail` anniv_val
            ON anniv_val.parent = c.name
            AND anniv_val.field_name = 'Anniversary Date'

        {where_clause}

        ORDER BY
            c.customer_name ASC
    """

    return frappe.db.sql(
        query,
        values=values,
        as_dict=True
    )