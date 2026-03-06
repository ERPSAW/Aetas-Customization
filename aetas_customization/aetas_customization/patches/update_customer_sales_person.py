import frappe
from frappe.utils import nowdate


def execute():
    """
    Ultra-fast implementation with bulk operations
    Use only if you're confident about data integrity
    """
    data = [
        {"old_sa": "Ashish Singh", "new_sa": "Bosco Charles"},
        {"old_sa": "Clifford William", "new_sa": "Joel D'Costa"},
        {"old_sa": "Khushi Vijaywergi", "new_sa": "Barbie Singh"},
        {"old_sa": "Larry Menezes", "new_sa": "Ratan Kate"},
        {"old_sa": "Pratham Puri", "new_sa": "Ashfaq Sayyed"},
        {"old_sa": "Shahbaz Shaikh", "new_sa": "Safwaan Patel"},
    ]
    
    current_date = nowdate()
    batch_size = 100  # Process in batches
    
    for row in data:
        old_sa = row["old_sa"]
        new_sa = row["new_sa"]
        
        # Get customer names
        customer_names = frappe.get_all(
            "Customer",
            filters={"custom_sales_person": old_sa},
            pluck="name"
        )
        
        if not customer_names:
            continue
        
        # Process in batches
        for i in range(0, len(customer_names), batch_size):
            batch = customer_names[i:i + batch_size]
            
            for customer_name in batch:
                # Use db.set_value for faster updates (bypasses ORM overhead)
                frappe.db.set_value("Customer", customer_name, "custom_sales_person", new_sa)
                
                # Insert child table entry
                child_doc = frappe.get_doc({
                    "doctype": "Customer Journey",
                    "parent": customer_name,
                    "parenttype": "Customer",
                    "parentfield": "custom_customer_journey",
                    "journey_date": current_date,
                    "journey_type": "SP Change",
                    "sales_person": new_sa,
                    "description": f"Changed from {old_sa} to {new_sa}"
                })
                child_doc.db_insert()
            
            # Commit after each batch
            frappe.db.commit()
            print(f"Processed batch {i//batch_size + 1} for {old_sa} -> {new_sa}")
        
        print(f"Completed {len(customer_names)} customers from {old_sa} to {new_sa}")
    
    frappe.clear_cache(doctype="Customer")
    print("Patch completed successfully")