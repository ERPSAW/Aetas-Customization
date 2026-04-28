import frappe
from frappe.utils import flt


def before_tests():
    """Seed minimal shared-site prerequisites used by app tests."""
    _cleanup_test_item_prices()
    _ensure_lead_source()
    _ensure_services_item_group()
    _ensure_supplier_group()
    _ensure_test_customer()
    _ensure_razorpay_mode_of_payment_account()


def normalize_item_tax_template_for_tests(doc, method=None):
    """
    Avoid india_compliance zero-GST validation failures for framework test records.

    This normalization is test-only and runs before validate.
    """
    if not getattr(frappe.flags, "in_test", False):
        return

    if not hasattr(doc, "gst_treatment") or not hasattr(doc, "gst_rate"):
        return

    if doc.gst_treatment != "Taxable" or flt(doc.gst_rate):
        return

    # Derive a compliant GST rate from the first non-zero tax row when possible.
    inferred_rate = 0.0
    for row in doc.get("taxes") or []:
        row_rate = abs(flt(row.get("tax_rate")))
        if row_rate > 0:
            inferred_rate = max(inferred_rate, row_rate * 2)

    doc.gst_rate = inferred_rate or 1.0


def ensure_item_brand_for_tests(doc, method=None):
    if not getattr(frappe.flags, "in_test", False):
        return

    if getattr(doc, "doctype", None) != "Item" or getattr(doc, "brand", None):
        return

    brand_name = "_Test Brand"
    if not frappe.db.exists("Brand", brand_name):
        frappe.get_doc({"doctype": "Brand", "brand": brand_name}).insert(ignore_permissions=True)

    doc.brand = brand_name


def ensure_customer_mandatory_fields_for_tests(doc, method=None):
    if not getattr(frappe.flags, "in_test", False):
        return

    if getattr(doc, "doctype", None) != "Customer":
        return

    if hasattr(doc, "custom_source") and not doc.custom_source:
        doc.custom_source = "Others"

    if hasattr(doc, "custom_contact") and not doc.custom_contact:
        doc.custom_contact = "+919876543210"

    if hasattr(doc, "custom_email") and not doc.custom_email:
        doc.custom_email = "test-customer@example.com"


def normalize_sales_taxes_template_for_tests(doc, method=None):
    if not getattr(frappe.flags, "in_test", False):
        return

    if getattr(doc, "doctype", None) != "Sales Taxes and Charges Template":
        return

    for row in doc.get("taxes") or []:
        if hasattr(row, "included_in_print_rate"):
            row.included_in_print_rate = 0
        if hasattr(row, "included_in_paid_amount"):
            row.included_in_paid_amount = 0


def ensure_sales_invoice_mandatory_fields_for_tests(doc, method=None):
    if not getattr(frappe.flags, "in_test", False):
        return

    if getattr(doc, "doctype", None) != "Sales Invoice":
        return

    if hasattr(doc, "custom_billing_source") and not doc.custom_billing_source:
        doc.custom_billing_source = "Others"

    # Handle sales_person as a Link field
    if hasattr(doc, "sales_person") and not doc.sales_person:
        _ensure_test_sales_person()
        doc.sales_person = "_Test Sales Person"

    # Handle sales_team as a Table field
    if hasattr(doc, "sales_team") and not doc.get("sales_team"):
        _ensure_test_sales_person()
        doc.append("sales_team", {
            "sales_person": "_Test Sales Person",
            "allocated_percentage": 100
        })


def _ensure_supplier_group():
    if frappe.db.exists("Supplier Group", "All Supplier Groups"):
        return

    frappe.get_doc(
        {
            "doctype": "Supplier Group",
            "supplier_group_name": "All Supplier Groups",
            "is_group": 1,
        }
    ).insert(ignore_permissions=True)


def _ensure_test_customer():
    customer_name = "_Test Customer"
    if frappe.db.exists("Customer", customer_name):
        frappe.db.set_value(
            "Customer",
            customer_name,
            {
                "custom_source": "Others",
                "custom_contact": "+919876543210",
                "custom_email": "test-customer@example.com",
            },
            update_modified=False,
        )
        return

    existing_by_label = frappe.db.get_value(
        "Customer",
        {"customer_name": customer_name},
        "name",
    )
    if existing_by_label and existing_by_label != customer_name:
        frappe.rename_doc(
            "Customer",
            existing_by_label,
            customer_name,
            force=True,
            show_alert=False,
        )
        return

    doc = frappe.get_doc(
        {
            "doctype": "Customer",
            "name": customer_name,
            "customer_name": customer_name,
            "customer_type": "Individual",
            "custom_source": "Others",
            "custom_contact": "+919876543210",
            "custom_email": "test-customer@example.com",
        }
    )
    doc.insert(ignore_permissions=True)

    if doc.name != customer_name:
        frappe.rename_doc(
            "Customer",
            doc.name,
            customer_name,
            force=True,
            show_alert=False,
        )


def _ensure_razorpay_mode_of_payment_account():
    mop_name = "Razor Pay"
    company = frappe.defaults.get_global_default("company")

    if not company or not frappe.db.exists("Mode of Payment", mop_name):
        return

    default_account = frappe.db.get_value(
        "Company", company, "default_cash_account"
    ) or frappe.db.get_value("Company", company, "default_bank_account")

    if not default_account:
        return

    mop = frappe.get_doc("Mode of Payment", mop_name)
    for row in mop.accounts or []:
        if row.company == company:
            if row.default_account != default_account:
                row.default_account = default_account
                mop.save(ignore_permissions=True)
            return

    mop.append(
        "accounts",
        {
            "company": company,
            "default_account": default_account,
        },
    )
    mop.save(ignore_permissions=True)

def _ensure_lead_source():
    if not frappe.db.exists("Lead Source", "Others"):
        frappe.get_doc({
            "doctype": "Lead Source",
            "source_name": "Others"
        }).insert(ignore_permissions=True)


def _cleanup_test_item_prices():
    frappe.db.sql(
        """
        DELETE FROM `tabItem Price`
        WHERE item_code LIKE '_Test%%'
        """
    )


def _ensure_services_item_group():
    if frappe.db.exists("Item Group", "Services"):
        return

    parent_group = (
        "All Item Groups"
        if frappe.db.exists("Item Group", "All Item Groups")
        else None
    )

    doc = frappe.get_doc(
        {
            "doctype": "Item Group",
            "item_group_name": "Services",
            "is_group": 0,
            "parent_item_group": parent_group,
        }
    )
    doc.insert(ignore_permissions=True)


def _ensure_test_sales_person():
    if frappe.db.exists("Sales Person", "_Test Sales Person"):
        return

    parent_name = (
        "All Sales Persons"
        if frappe.db.exists("Sales Person", "All Sales Persons")
        else None
    )

    doc = frappe.get_doc(
        {
            "doctype": "Sales Person",
            "sales_person_name": "_Test Sales Person",
            "is_group": 0,
            "parent_sales_person": parent_name,
            "enabled": 1,
            "commission_rate": 0,
        }
    )
    doc.insert(ignore_permissions=True)
