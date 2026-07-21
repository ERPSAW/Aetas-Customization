import frappe


def execute():
    """Backfill Serial No.custom_purchase_invoice_no for serials invoiced before
    the Purchase Invoice on_submit hook existed.

    Serials are read from the Serial and Batch Bundle (ERPNext v15) and, for
    older rows, from the plain serial_no field on Purchase Invoice Item.
    """

    # 1) Serial and Batch Bundle (v15 default)
    frappe.db.sql("""
        UPDATE `tabSerial No` sn
        INNER JOIN `tabSerial and Batch Entry` sbe ON sbe.serial_no = sn.name
        INNER JOIN `tabSerial and Batch Bundle` sbb ON sbb.name = sbe.parent
        SET sn.custom_purchase_invoice_no = sbb.voucher_no
        WHERE sbb.voucher_type = 'Purchase Invoice'
        AND sbb.docstatus = 1
        AND sn.custom_purchase_invoice_no IS NULL
    """)

    # 2) Legacy rows that still carry the plain serial_no field
    legacy_items = frappe.db.sql("""
        SELECT pii.parent, pii.serial_no
        FROM `tabPurchase Invoice Item` pii
        WHERE pii.docstatus = 1
        AND pii.serial_no IS NOT NULL
        AND pii.serial_no != ''
    """, as_dict=True)

    for item in legacy_items:
        serial_numbers = [sn.strip() for sn in item.serial_no.split("\n") if sn and sn.strip()]
        if not serial_numbers:
            continue

        frappe.db.sql("""
            UPDATE `tabSerial No`
            SET custom_purchase_invoice_no = %(purchase_invoice)s
            WHERE name IN %(serial_numbers)s
            AND custom_purchase_invoice_no IS NULL
        """, {
            "purchase_invoice": item.parent,
            "serial_numbers": serial_numbers,
        })

    frappe.db.commit()
