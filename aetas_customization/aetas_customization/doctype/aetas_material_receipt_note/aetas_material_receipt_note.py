# Copyright (c) 2025, Akhilam Inc and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import json
from frappe import _

class AETASMaterialReceiptNote(Document):
	pass


import frappe
import json
from frappe import _

@frappe.whitelist()
def get_purchase_orders(warehouse, supplier='', cost_center='', select_po_items=0):
    """Get Purchase Orders or PO Items based on warehouse and optional filters"""
    
    select_po_items = int(select_po_items)
    
    if select_po_items:
        # Return PO items instead of POs
        return get_po_items_for_selection(warehouse, supplier, cost_center)
    else:
        # Return POs as before
        return get_pos_for_selection(warehouse, supplier, cost_center)

def get_pos_for_selection(warehouse, supplier='', cost_center=''):
    """Get Purchase Orders based on warehouse and optional filters"""
    
    # Base filters
    filters = {
        'set_warehouse': warehouse,
        'docstatus': 1,
        'status': ['in', ['To Receive', 'To Receive and Bill']]
    }
    
    # Add optional supplier filter
    if supplier:
        filters['supplier'] = supplier
    
    # If cost_center is provided, filter by PO cost_center OR PO items cost_center
    if cost_center:
        # First get POs with matching cost_center at header level
        header_pos = frappe.get_all('Purchase Order',
            filters={**filters, 'cost_center': cost_center},
            fields=['name', 'supplier', 'transaction_date', 'status'],
            order_by='transaction_date desc'
        )
        
        # Then get POs that have items with matching cost_center
        item_pos = frappe.db.sql("""
            SELECT DISTINCT po.name, po.supplier, po.transaction_date, po.status
            FROM `tabPurchase Order` po
            INNER JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
            WHERE po.set_warehouse = %(warehouse)s
            AND po.docstatus = 1
            AND po.status IN ('To Receive', 'To Receive and Bill')
            AND poi.cost_center = %(cost_center)s
            {supplier_filter}
            ORDER BY po.transaction_date DESC
        """.format(
            supplier_filter=f"AND po.supplier = '{supplier}'" if supplier else ""
        ), {
            'warehouse': warehouse,
            'cost_center': cost_center
        }, as_dict=1)
        
        # Combine and remove duplicates
        po_names = set([po.name for po in header_pos] + [po.name for po in item_pos])
        pos = [po for po in (header_pos + item_pos) if po.name in po_names]
        
        # Remove duplicates while maintaining order
        seen = set()
        unique_pos = []
        for po in pos:
            if po.name not in seen:
                seen.add(po.name)
                unique_pos.append(po)
        
        return unique_pos
    else:
        # No cost_center filter, just return based on warehouse and supplier
        pos = frappe.get_all('Purchase Order',
            filters=filters,
            fields=['name', 'supplier', 'transaction_date', 'status'],
            order_by='transaction_date desc'
        )
        return pos

def get_po_items_for_selection(warehouse, supplier='', cost_center=''):
    """Get PO Items for selection based on filters"""
    
    # Build SQL query dynamically
    conditions = ["po.set_warehouse = %(warehouse)s"]
    conditions.append("po.docstatus = 1")
    conditions.append("po.status IN ('To Receive', 'To Receive and Bill')")
    
    if supplier:
        conditions.append("po.supplier = %(supplier)s")
    
    if cost_center:
        conditions.append("(po.cost_center = %(cost_center)s OR poi.cost_center = %(cost_center)s)")
    
    query = f"""
        SELECT 
            po.name as purchase_order,
            po.supplier,
            poi.item_code,
            poi.item_name,
            poi.uom,
            poi.qty,
            poi.rate,
            poi.amount
        FROM `tabPurchase Order` po
        INNER JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
        WHERE {' AND '.join(conditions)}
        ORDER BY po.transaction_date DESC, poi.idx
    """
    
    items = frappe.db.sql(query, {
        'warehouse': warehouse,
        'supplier': supplier,
        'cost_center': cost_center
    }, as_dict=1)
    
    return items

@frappe.whitelist()
def get_mrn_items(purchase_orders, select_po_items=0):
    """Get items from selected Purchase Orders"""
    if isinstance(purchase_orders, str):
        purchase_orders = json.loads(purchase_orders)
    
    items = []
    for po in purchase_orders:
        po_items = frappe.get_all('Purchase Order Item',
            filters={
                'parent': po,
                'docstatus': 1
            },
            fields=[
                'item_code', 
                'item_name', 
                'description', 
                'uom', 
                'qty as quantity', 
                'rate', 
                'amount', 
                'parent as purchase_order'
            ]
        )
        items.extend(po_items)
    
    return items
