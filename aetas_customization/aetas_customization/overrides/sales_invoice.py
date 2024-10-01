import frappe

def validate(self,method):

    if self.cost_center:
        letter_head = frappe.db.get_value("Cost Center",self.cost_center,"custom_letter_head")
        if letter_head and letter_head != self.letter_head:
            frappe.msgprint(f"Letter Head must be <b>{letter_head}</b> for Cost Center - {self.cost_center}")

	
    update_mrp_values(self)

def update_mrp_values(self):

    for item in self.items:
        if item.item_code and item.serial_no:
            
            mrp_value_from_pii = frappe.db.sql("""
            select mrp
            from`tabPurchase Invoice Item`
            where item_code = %s and (serial_no = %s or serial_no like %s or serial_no like %s or serial_no like %s)
            """,(item.item_code, item.serial_no, item.serial_no + "\n%", "%\n" + item.serial_no, "%\n" + item.serial_no + "\n%"),as_dict=1)

            mrp_value_from_se = frappe.db.sql("""
            select custom_mrp as mrp
            from`tabStock Entry Detail`
            where item_code = %s and (serial_no = %s or serial_no like %s or serial_no like %s or serial_no like %s)
            """,(item.item_code, item.serial_no, item.serial_no + "\n%", "%\n" + item.serial_no, "%\n" + item.serial_no + "\n%"),as_dict=1)

            if mrp_value_from_pii:
                item.mrp = mrp_value_from_pii[0].mrp
            elif mrp_value_from_se:
                item.mrp = mrp_value_from_se[0].mrp
            else:
                item.mrp = 0