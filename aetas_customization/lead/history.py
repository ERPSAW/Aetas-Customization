# Copyright (c) 2026, Akhilam Inc and contributors
# For license information, please see license.txt
"""
Customer history + invoice rendering for the Lead form.

Whitelisted helpers that return ready-to-inject HTML for:
* the Customer History tab — purchase history (submitted Sales Invoices with item
  lines) and lead history (prior leads for the same Customer);
* the Closed Won "Won Invoice Details" section — the lines of the tagged invoice.

All queries are batched (no ORM calls inside loops).
"""

import frappe
from frappe import _
from frappe.utils import escape_html, flt


def _fmt(value: float) -> str:
    return frappe.utils.fmt_money(flt(value))


def _empty(msg: str) -> str:
    return f'<div class="text-muted" style="padding:8px 0;">{escape_html(msg)}</div>'


def _lines_table(rows: list[dict], *, with_date: bool = False) -> str:
    """Render invoice item rows as an HTML table (Brand, Item, Qty, Rate, Disc %, Amount)."""
    head = (
        "<tr>"
        + ("<th>Date</th><th>Invoice</th>" if with_date else "")
        + "<th>Brand</th><th>Item</th><th style='text-align:right'>Qty</th>"
        "<th style='text-align:right'>Rate</th><th style='text-align:right'>Disc %</th>"
        "<th style='text-align:right'>Amount</th></tr>"
    )
    body = []
    for r in rows:
        lead_cols = ""
        if with_date:
            inv = escape_html(r.get("invoice") or "")
            lead_cols = (
                f"<td>{escape_html(str(r.get('posting_date') or ''))}</td>"
                f"<td><a href='/app/sales-invoice/{inv}'>{inv}</a></td>"
            )
        body.append(
            "<tr>"
            + lead_cols
            + f"<td>{escape_html(r.get('brand') or '')}</td>"
            f"<td>{escape_html(r.get('item_name') or r.get('item_code') or '')}</td>"
            f"<td style='text-align:right'>{flt(r.get('qty')):g}</td>"
            f"<td style='text-align:right'>{_fmt(r.get('rate'))}</td>"
            f"<td style='text-align:right'>{flt(r.get('discount_percentage')):g}</td>"
            f"<td style='text-align:right'>{_fmt(r.get('amount'))}</td>"
            "</tr>"
        )
    return (
        "<div class='table-responsive'><table class='table table-bordered table-condensed'>"
        f"<thead>{head}</thead><tbody>{''.join(body)}</tbody></table></div>"
    )


@frappe.whitelist()
def get_customer_purchase_history(customer: str) -> str:
    """HTML of the customer's submitted Sales Invoice lines (brand/item/discount/price)."""
    if not customer:
        return _empty(_("No customer linked."))

    invoices = frappe.get_all(
        "Sales Invoice",
        filters={"customer": customer, "docstatus": 1},
        fields=["name", "posting_date"],
        order_by="posting_date desc",
    )
    if not invoices:
        return _empty(_("No purchases found for this customer."))

    date_map = {i.name: i.posting_date for i in invoices}
    items = frappe.get_all(
        "Sales Invoice Item",
        filters={"parent": ["in", list(date_map)]},
        fields=[
            "parent", "item_code", "item_name", "brand",
            "qty", "rate", "discount_percentage", "amount",
        ],
    )
    # Preserve newest-invoice-first ordering.
    order = {name: idx for idx, name in enumerate(date_map)}
    items.sort(key=lambda r: order.get(r.parent, 0))
    for r in items:
        r["invoice"] = r["parent"]
        r["posting_date"] = date_map.get(r["parent"])

    return _lines_table(items, with_date=True)


@frappe.whitelist()
def get_customer_lead_history(customer: str, exclude_lead: str | None = None) -> str:
    """HTML of prior leads for the linked customer, showing pipeline stage + brand + date."""
    if not customer:
        return _empty(_("No customer linked."))

    filters = {"customer": customer}
    if exclude_lead:
        filters["name"] = ["!=", exclude_lead]
    leads = frappe.get_all(
        "Lead",
        filters=filters,
        fields=["name", "workflow_state", "custom_brand", "creation"],
        order_by="creation desc",
    )
    if not leads:
        return _empty(_("No previous leads for this customer."))

    body = []
    for lead in leads:
        name = escape_html(lead.name)
        body.append(
            "<tr>"
            f"<td><a href='/app/lead/{name}'>{name}</a></td>"
            f"<td>{escape_html(lead.workflow_state or '')}</td>"
            f"<td>{escape_html(lead.custom_brand or '')}</td>"
            f"<td>{escape_html(str(lead.creation)[:10])}</td>"
            "</tr>"
        )
    return (
        "<div class='table-responsive'><table class='table table-bordered table-condensed'>"
        "<thead><tr><th>Lead</th><th>Stage</th><th>Brand</th><th>Date</th></tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table></div>"
    )


@frappe.whitelist()
def get_invoice_lines_html(invoice: str) -> str:
    """HTML of a single invoice's lines — for the Closed Won 'Won Invoice Details' section."""
    if not invoice or not frappe.db.exists("Sales Invoice", invoice):
        return _empty(_("No invoice tagged."))
    items = frappe.get_all(
        "Sales Invoice Item",
        filters={"parent": invoice},
        fields=["item_code", "item_name", "brand", "qty", "rate", "discount_percentage", "amount"],
        order_by="idx asc",
    )
    if not items:
        return _empty(_("Invoice has no line items."))
    header = f"<div style='margin-bottom:6px'><b>{escape_html(invoice)}</b></div>"
    return header + _lines_table(items)
