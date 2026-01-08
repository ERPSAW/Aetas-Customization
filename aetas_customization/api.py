import math

import frappe


@frappe.whitelist()
def search_customers(name=None, email=None, mobile=None, txt=None, page=1, page_len=20):
    # Ensure inputs are integers
    page = int(page) if page else 1
    page_len = int(page_len) if page_len else 20
    offset = (page - 1) * page_len

    # Support 'txt' as fallback for 'name'
    search_name = name or txt

    # Base tables definition
    tables_clause = """
        FROM
            `tabCustomer` cust
        LEFT JOIN
            `tabDynamic Link` dl ON dl.link_name = cust.name AND dl.link_doctype = 'Customer'
        LEFT JOIN
            `tabContact` c ON c.name = dl.parent
    """

    conditions = []
    values = {}

    # 1. Search by Name (Customer Name or ID)
    if search_name:
        conditions.append(
            "(cust.customer_name LIKE %(name)s OR cust.name LIKE %(name)s)"
        )
        values["name"] = f"%{search_name}%"

    # 2. Search by Email (Contact Email)
    if email:
        conditions.append("c.email_id LIKE %(email)s")
        values["email"] = f"%{email}%"

    # 3. Search by Mobile (Contact Mobile)
    if mobile:
        conditions.append(
            "(c.mobile_no LIKE %(mobile)s OR c.phone LIKE %(mobile)s or cust.custom_contact LIKE %(mobile)s)"
        )
        values["mobile"] = f"%{mobile}%"

    where_clause = ""
    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)

    # --- Step 1: Get Total Count ---
    # We use DISTINCT because the joins might multiply rows if a customer has multiple contacts
    count_query = f"SELECT COUNT(DISTINCT cust.name) {tables_clause} {where_clause}"
    total_count = frappe.db.sql(count_query, values)[0][0]

    # If no results, return empty immediately
    if total_count == 0:
        return {
            "data": [],
            "total_count": 0,
            "total_pages": 0,
            "page": page,
            "page_len": page_len,
        }

    # --- Step 2: Fetch Paginated Data ---
    values["page_len"] = page_len
    values["offset"] = offset

    data_query = f"""
        SELECT
            cust.name,
            cust.customer_name,
            cust.custom_sales_person,
            cust.custom_contact
        {tables_clause}
        {where_clause}
        GROUP BY cust.name
        LIMIT %(page_len)s OFFSET %(offset)s
    """

    customers = frappe.db.sql(data_query, values, as_dict=True)

    final_data = []

    for cust in customers:
        # Fetch Primary Contact Details for the found customer
        contact_info = frappe.db.sql(
            """
            SELECT c.email_id, c.mobile_no
            FROM `tabContact` c
            INNER JOIN `tabDynamic Link` dl ON dl.parent = c.name
            WHERE dl.link_doctype = 'Customer'
                AND dl.link_name = %s
                AND c.is_primary_contact = 1
            LIMIT 1
        """,
            cust.name,
            as_dict=True,
        )

        contact_info = contact_info[0] if contact_info else {}

        # Merge contact info into customer data
        cust.update(contact_info)
        final_data.append(cust)

    total_pages = math.ceil(total_count / page_len)

    return {
        "data": final_data,
        "total_count": total_count,
        "total_pages": total_pages,
        "page": page,
        "page_len": page_len,
    }
