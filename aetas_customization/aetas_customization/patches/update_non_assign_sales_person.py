import frappe
def execute():
    """Assign 'Not Assigned' to Customers without a Sales Person."""
    
    # Using direct SQL for a fast bulk update
    frappe.db.sql("""
        UPDATE `tabCustomer`
        SET custom_sales_person = 'Not Assigned'
        WHERE custom_sales_person IS NULL OR custom_sales_person = ''
    """)