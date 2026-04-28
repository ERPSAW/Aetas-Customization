import frappe

def run():
    # 1. Inspect
    company = frappe.db.get_default('company')
    print(f"Default Company: {company}")
    
    sg = frappe.db.get_value('Supplier Group', 'All Supplier Groups', 'name')
    print(f"Supplier Group 'All Supplier Groups': {sg}")
    
    mop = frappe.db.get_value('Mode of Payment', 'Razor Pay', 'name')
    print(f"Mode of Payment 'Razor Pay': {mop}")

    # 2. Set default company if missing
    if not company:
        frappe.db.set_default('company', 'Aetas Retail Private Limited')
        print("Set default company to 'Aetas Retail Private Limited'")
    
    # 3. Mode of Payment 'Razor Pay' account row
    if mop:
        mop_doc = frappe.get_doc('Mode of Payment', 'Razor Pay')
        has_account = False
        for row in mop_doc.accounts:
            if row.company == 'Aetas Retail Private Limited':
                has_account = True
                break
        if not has_account:
            mop_doc.append('accounts', {
                'company': 'Aetas Retail Private Limited',
                'default_account': 'Razorpay - ARPL'
            })
            mop_doc.save()
            print("Added account row for 'Razor Pay'")
        else:
            print("Account row for 'Razor Pay' already exists")
    else:
        # Create Razor Pay if it doesn't exist? The instructions say ensure it has an account row.
        # Minimal creation if missing might be needed but let's see if it's there.
        print("Mode of Payment 'Razor Pay' not found. Skipping account row.")

    # 4. Supplier Group 'All Supplier Groups'
    if not sg:
        doc = frappe.get_doc({
            'doctype': 'Supplier Group',
            'supplier_group_name': 'All Supplier Groups',
            'is_group': 1
        })
        doc.insert(ignore_permissions=True)
        print("Created Supplier Group 'All Supplier Groups'")
    
    frappe.db.commit()

run()
