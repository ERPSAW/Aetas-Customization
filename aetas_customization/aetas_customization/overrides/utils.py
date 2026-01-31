import math

import frappe
from frappe.utils import getdate, now_datetime


def get_customers_batch(offset=0, limit=100):
    """Fetch customers in batches."""
    return frappe.get_all(
        "Customer",
        filters={"custom_sales_person": ["is", "set"], "custom_source": ["is", "set"]},
        fields=["name", "creation", "custom_sales_person", "custom_source"],
        start=offset,
        page_length=limit,
    )


def get_total_customers_count():
    """Get total count of customers matching criteria."""
    return frappe.db.count(
        "Customer",
        filters={"custom_sales_person": ["is", "set"], "custom_source": ["is", "set"]},
    )


def bulk_check_existing_creation_journeys(customer_names):
    """Bulk check which customers already have creation journey entries."""
    if not customer_names:
        return set()

    existing = frappe.db.sql(
        """
        SELECT DISTINCT parent 
        FROM `tabCustomer Journey`
        WHERE parent IN %(customers)s 
        AND journey_type = 'Creation'
    """,
        {"customers": customer_names},
        as_dict=False,
    )

    return {row[0] for row in existing}


def set_customer_creation_journey_batch(customers):
    """Set customer journey for a batch of customers."""
    if not customers:
        return 0, 0

    customer_names = [c.name for c in customers]

    # Bulk check existing entries
    existing_customers = bulk_check_existing_creation_journeys(customer_names)

    processed = 0
    errors = 0

    for customer in customers:
        # Skip if creation journey already exists
        if customer.name in existing_customers:
            continue

        try:
            # Use SQL for direct insertion - much faster than ORM
            frappe.db.sql(
                """
                INSERT INTO `tabCustomer Journey` 
                (name, parent, parenttype, parentfield, idx, 
                 journey_date, journey_type, sales_person, description,
                 creation, modified, modified_by, owner, docstatus)
                SELECT 
                    %(entry_name)s,
                    %(customer)s,
                    'Customer',
                    'custom_customer_journey',
                    COALESCE((SELECT MAX(idx) FROM `tabCustomer Journey` WHERE parent = %(customer)s), 0) + 1,
                    %(journey_date)s,
                    'Creation',
                    %(sales_person)s,
                    %(description)s,
                    %(now)s,
                    %(now)s,
                    %(user)s,
                    %(user)s,
                    0
            """,
                {
                    "entry_name": frappe.generate_hash("Customer Journey", 10),
                    "customer": customer.name,
                    "journey_date": customer.creation,
                    "sales_person": customer.custom_sales_person,
                    "description": f"This customer was created on {getdate(customer.creation)} by Sales Person {customer.custom_sales_person} via {customer.custom_source} lead source.",
                    "now": now_datetime(),
                    "user": frappe.session.user,
                },
            )

            processed += 1

        except Exception as e:
            errors += 1
            frappe.log_error(
                message=f"Customer: {customer.name}\nError: {str(e)}",
                title="Customer Creation Journey Error",
            )

    return processed, errors


def get_sales_invoices_for_customers(customer_names):
    """
    Bulk fetch distinct sales invoices and sales persons for multiple customers.
    Returns unique combinations of (Invoice, Sales Person).
    """
    if not customer_names:
        return {}

    # Use DISTINCT to handle cases where an invoice has multiple items
    # for the SAME sales person (we only want one entry per sales person per invoice).
    invoices = frappe.db.sql(
        """
        SELECT DISTINCT
            si.customer,
            si.name,
            si.posting_date,
            sii.sales_person
        FROM `tabSales Invoice` si
        INNER JOIN `tabSales Invoice Item` sii ON si.name = sii.parent
        WHERE si.customer IN %(customers)s
        AND si.docstatus = 1 AND si.is_return = 0
        AND sii.sales_person IS NOT NULL
        ORDER BY si.customer, si.posting_date ASC
    """,
        {"customers": customer_names},
        as_dict=True,
    )

    # Group by customer
    customer_invoices = {}
    for inv in invoices:
        if inv.customer not in customer_invoices:
            customer_invoices[inv.customer] = []
        customer_invoices[inv.customer].append(inv)

    return customer_invoices


def get_existing_purchase_journeys(customer_names):
    """
    Bulk fetch existing purchase journey entries.
    Returns a set of (invoice_name, sales_person) tuples for checking existence.
    """
    if not customer_names:
        return {}

    existing = frappe.db.sql(
        """
        SELECT 
            parent as customer,
            description,
            sales_person
        FROM `tabCustomer Journey`
        WHERE parent IN %(customers)s
        AND journey_type = 'Purchase'
    """,
        {"customers": customer_names},
        as_dict=True,
    )

    # Group by customer and extract (invoice_name, sales_person) keys
    customer_existing = {}
    for entry in existing:
        if entry.customer not in customer_existing:
            customer_existing[entry.customer] = set()

        # Extract invoice name from description
        # Assuming format: "...via Sales Invoice INV-XXXXX."
        desc = entry.description
        if "Sales Invoice" in desc:
            parts = desc.split("Sales Invoice")
            if len(parts) > 1:
                # Basic parsing to isolate the invoice number
                invoice_part = parts[1].strip()
                # Split by space to get just the ID in case there is text after it
                invoice_name = invoice_part.split(" ")[0].rstrip(".")

                # Add unique key: (Invoice Name, Sales Person)
                # We normalize sales_person to None if it's missing to match SQL results
                sp = entry.sales_person if entry.sales_person else None
                customer_existing[entry.customer].add((invoice_name, sp))

    return customer_existing


def set_purchase_journey_batch(customers):
    """Set purchase journey for a batch of customers."""
    if not customers:
        return 0, 0

    customer_names = [c.name for c in customers]

    # Bulk fetch distinct (Invoice + SalesPerson) rows
    customer_invoices = get_sales_invoices_for_customers(customer_names)

    # Bulk fetch existing purchase journeys (Invoice + SalesPerson)
    existing_journeys = get_existing_purchase_journeys(customer_names)

    processed = 0
    errors = 0
    total_entries = 0

    # Prepare bulk insert data
    insert_values = []

    for customer in customers:
        try:
            # List of distinct (invoice, sales_person) rows
            invoices = customer_invoices.get(customer.name, [])
            if not invoices:
                continue

            existing_keys = existing_journeys.get(customer.name, set())

            # Get current max idx for this customer
            max_idx = frappe.db.sql(
                """
                SELECT COALESCE(MAX(idx), 0) as max_idx
                FROM `tabCustomer Journey`
                WHERE parent = %(customer)s
            """,
                {"customer": customer.name},
                as_dict=True,
            )[0].max_idx

            new_entries = 0
            for invoice in invoices:
                # Key for duplicate check
                sp_key = invoice.sales_person if invoice.sales_person else None
                check_key = (invoice.name, sp_key)

                # Skip if this specific combination already exists
                if check_key in existing_keys:
                    continue

                max_idx += 1

                # Format description to include Sales Person if available
                desc = f"Purchase recorded on {getdate(invoice.posting_date)} via Sales Invoice {invoice.name}"
                if invoice.sales_person:
                    desc += f" by Sales Person {invoice.sales_person}."
                else:
                    desc += "."

                insert_values.append(
                    {
                        "entry_name": frappe.generate_hash("Customer Journey", 10),
                        "customer": customer.name,
                        "idx": max_idx,
                        "journey_date": invoice.posting_date,
                        "sales_person": invoice.sales_person,
                        "description": desc,
                        "now": now_datetime(),
                        "user": frappe.session.user,
                    }
                )
                new_entries += 1

            if new_entries > 0:
                processed += 1
                total_entries += new_entries

        except Exception as e:
            errors += 1
            frappe.log_error(
                message=f"Customer: {customer.name}\nError: {str(e)}",
                title="Customer Purchase Journey Error",
            )

    # Bulk insert all journey entries
    if insert_values:
        try:
            for entry in insert_values:
                frappe.db.sql(
                    """
                    INSERT INTO `tabCustomer Journey` 
                    (name, parent, parenttype, parentfield, idx, 
                     journey_date, journey_type, sales_person, description,
                     creation, modified, modified_by, owner, docstatus)
                    VALUES (
                        %(entry_name)s, %(customer)s, 'Customer', 'custom_customer_journey', %(idx)s,
                        %(journey_date)s, 'Purchase', %(sales_person)s, %(description)s,
                        %(now)s, %(now)s, %(user)s, %(user)s, 0
                    )
                """,
                    entry,
                )
        except Exception as e:
            frappe.log_error(
                message=f"Bulk insert error: {str(e)}",
                title="Customer Journey Bulk Insert Error",
            )

    return processed, errors


def set_customer_creation_journey():
    """Set customer creation journey with batch processing."""
    total_count = get_total_customers_count()

    if total_count == 0:
        frappe.log_error("No customers found for creation journey update")
        print("No customers found for creation journey update")
        return

    batch_size = 100
    total_batches = math.ceil(total_count / batch_size)

    total_processed = 0
    total_errors = 0

    print(
        f"Processing {total_count} customers in {total_batches} batches for creation journey..."
    )

    for batch_num in range(total_batches):
        offset = batch_num * batch_size

        try:
            customers = get_customers_batch(offset=offset, limit=batch_size)

            if not customers:
                break

            processed, errors = set_customer_creation_journey_batch(customers)

            total_processed += processed
            total_errors += errors

            # Commit after each batch
            frappe.db.commit()

            print(
                f"Batch {batch_num + 1}/{total_batches} completed: {processed} processed, {errors} errors (Total: {total_processed}/{total_count})"
            )

        except Exception as e:
            total_errors += 1
            frappe.log_error(
                message=f"Batch {batch_num + 1} error: {str(e)}",
                title="Customer Creation Journey Batch Error",
            )
            frappe.db.rollback()
            print(f"Batch {batch_num + 1} failed: {str(e)}")
            continue

    print(
        f"\nCreation Journey Completed: {total_processed} customers processed, {total_errors} errors out of {total_count} total"
    )
    return total_processed, total_errors


def set_purchase_journey_of_customers():
    """Set purchase journey for customers with batch processing."""
    total_count = get_total_customers_count()

    if total_count == 0:
        frappe.log_error("No customers found for purchase journey update")
        print("No customers found for purchase journey update")
        return

    batch_size = 50  # Smaller batch size due to more complex operations
    total_batches = math.ceil(total_count / batch_size)

    total_processed = 0
    total_errors = 0

    print(
        f"Processing {total_count} customers in {total_batches} batches for purchase journey..."
    )

    for batch_num in range(total_batches):
        offset = batch_num * batch_size

        try:
            customers = get_customers_batch(offset=offset, limit=batch_size)

            if not customers:
                break

            processed, errors = set_purchase_journey_batch(customers)

            total_processed += processed
            total_errors += errors

            # Commit after each batch
            frappe.db.commit()

            print(
                f"Batch {batch_num + 1}/{total_batches} completed: {processed} processed, {errors} errors (Total: {total_processed}/{total_count})"
            )

        except Exception as e:
            total_errors += 1
            frappe.log_error(
                message=f"Batch {batch_num + 1} error: {str(e)}",
                title="Customer Purchase Journey Batch Error",
            )
            frappe.db.rollback()
            print(f"Batch {batch_num + 1} failed: {str(e)}")
            continue

    print(
        f"\nPurchase Journey Completed: {total_processed} customers processed, {total_errors} errors out of {total_count} total"
    )
    return total_processed, total_errors


def update_customer_journeys():
    """Main function to be called from after_migrate hook."""
    start_time = now_datetime()
    print(f"\n{'=' * 60}")
    print(f"Customer Journey Update Started at {start_time}")
    print(f"{'=' * 60}\n")

    try:
        # Set flag to prevent recursion
        if frappe.flags.in_customer_journey_update:
            print("Customer journey update already in progress, skipping...")
            return

        frappe.flags.in_customer_journey_update = True

        # Disable auto-commit to handle commits manually
        frappe.db.auto_commit_on_many_writes = False

        # Process creation journeys
        print("\n--- Phase 1: Customer Creation Journey ---")
        creation_processed, creation_errors = set_customer_creation_journey()

        # Process purchase journeys
        print("\n--- Phase 2: Customer Purchase Journey ---")
        purchase_processed, purchase_errors = set_purchase_journey_of_customers()

        # Final commit
        frappe.db.commit()

        end_time = now_datetime()
        duration = end_time - start_time

        print(f"\n{'=' * 60}")
        print("Customer Journey Update Completed Successfully!")
        print(f"{'=' * 60}")
        print(f"Start Time: {start_time}")
        print(f"End Time: {end_time}")
        print(f"Duration: {duration}")
        print(
            f"Creation Journeys: {creation_processed} processed, {creation_errors} errors"
        )
        print(
            f"Purchase Journeys: {purchase_processed} processed, {purchase_errors} errors"
        )
        print(f"{'=' * 60}\n")

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(message=str(e), title="Customer Journey Update Failed")
        print(f"\n{'!' * 60}")
        print("CRITICAL ERROR: Customer journey update failed!")
        print(f"Error: {str(e)}")
        print(f"{'!' * 60}\n")
        raise

    finally:
        frappe.flags.in_customer_journey_update = False
        frappe.db.auto_commit_on_many_writes = False
