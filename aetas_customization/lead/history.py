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

from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import escape_html, flt

# Server-side caps so a customer with thousands of records never ships a huge payload.
# Generous enough that normal histories render in full; a "View all" link covers the rest.
MAX_INVOICES = 500
MAX_LEADS = 200
SCROLL_MAX_HEIGHT = "320px"

# Sticky header cell — stays visible while the container scrolls; theme-aware bg.
_TH = "<th style='position:sticky;top:0;background:var(--card-bg, #fff);z-index:1;{extra}'>{label}</th>"
_TH_R = "<th style='position:sticky;top:0;background:var(--card-bg, #fff);z-index:1;text-align:right;'>{label}</th>"


def _fmt(value: float) -> str:
    return frappe.utils.fmt_money(flt(value))


def _empty(msg: str) -> str:
    return f'<div class="text-muted" style="padding:8px 0;">{escape_html(msg)}</div>'


def _section_empty(title: str, msg: str) -> str:
    return (
        '<div style="margin:0 0 20px;">'
        f'<span style="font-size:1.05em;font-weight:600;">{escape_html(title)}</span>'
        '<span style="font-size:0.9em;color:var(--text-muted, #6c7680);"> — '
        f"{escape_html(msg)}</span></div>"
    )


def _wrap(title: str, count_html: str, table_html: str) -> str:
    """Title + count on one line (trusted HTML) + a fixed-height, scrollable table container."""
    header = (
        '<div style="margin:0 0 6px;">'
        f'<span style="font-size:1.05em;font-weight:600;">{escape_html(title)}</span>'
        '<span style="font-size:0.9em;color:var(--text-muted, #6c7680);"> — '
        f"{count_html}</span></div>"
    )
    box = (
        f'<div style="max-height:{SCROLL_MAX_HEIGHT};overflow:auto;margin:0 0 20px;'
        'border:1px solid var(--border-color, #d1d8dd);border-radius:4px;">'
        f"{table_html}</div>"
    )
    return header + box


def _lines_table(rows: list[dict], *, with_date: bool = False) -> str:
    """Render invoice item rows as an HTML table (Brand, Item, Qty, Rate, Disc %, Amount)."""
    head = (
        "<tr>"
        + (
            _TH.format(label="Date", extra="")
            + _TH.format(label="Invoice", extra="")
            if with_date
            else ""
        )
        + _TH.format(label="Brand", extra="")
        + _TH.format(label="Item", extra="")
        + _TH_R.format(label="Qty")
        + _TH_R.format(label="Rate")
        + _TH_R.format(label="Disc %")
        + _TH_R.format(label="Amount")
        + "</tr>"
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
        "<table class='table table-bordered table-condensed' style='margin:0;'>"
        f"<thead>{head}</thead><tbody>{''.join(body)}</tbody></table>"
    )


@frappe.whitelist()
def get_customer_purchase_history(customer: str) -> str:
    """HTML of the customer's submitted Sales Invoice lines (brand/item/discount/price)."""
    if not customer:
        return _section_empty(_("Purchase History"), _("No customer linked."))

    total = frappe.db.count("Sales Invoice", {"customer": customer, "docstatus": 1})
    invoices = frappe.get_all(
        "Sales Invoice",
        filters={"customer": customer, "docstatus": 1},
        fields=["name", "posting_date"],
        order_by="posting_date desc",
        limit=MAX_INVOICES,
    )
    if not invoices:
        return _section_empty(_("Purchase History"), _("No purchases found for this customer."))

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

    if total > MAX_INVOICES:
        url = f"/app/sales-invoice?customer={quote(customer)}&docstatus=1"
        label = _("Showing latest {0} of {1} invoices").format(MAX_INVOICES, total) + (
            f' — <a href="{url}" target="_blank">{_("View all")}</a>'
        )
    else:
        label = _("{0} invoices").format(total)
    return _wrap(_("Purchase History"), label, _lines_table(items, with_date=True))


@frappe.whitelist()
def get_customer_lead_history(customer: str, exclude_lead: str | None = None) -> str:
    """HTML of prior leads for the linked customer, showing pipeline stage + brand + date."""
    if not customer:
        return _section_empty(_("Lead History"), _("No customer linked."))

    filters = {"customer": customer}
    if exclude_lead:
        filters["name"] = ["!=", exclude_lead]
    total = frappe.db.count("Lead", filters)
    leads = frappe.get_all(
        "Lead",
        filters=filters,
        fields=["name", "workflow_state", "custom_brand", "creation"],
        order_by="creation desc",
        limit=MAX_LEADS,
    )
    if not leads:
        return _section_empty(_("Lead History"), _("No previous leads for this customer."))

    head = (
        "<tr>"
        + _TH.format(label="Lead", extra="")
        + _TH.format(label="Stage", extra="")
        + _TH.format(label="Brand", extra="")
        + _TH.format(label="Date", extra="")
        + "</tr>"
    )
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
    table = (
        "<table class='table table-bordered table-condensed' style='margin:0;'>"
        f"<thead>{head}</thead><tbody>{''.join(body)}</tbody></table>"
    )
    if total > MAX_LEADS:
        url = f"/app/lead?customer={quote(customer)}"
        label = _("Showing latest {0} of {1} leads").format(MAX_LEADS, total) + (
            f' — <a href="{url}" target="_blank">{_("View all")}</a>'
        )
    else:
        label = _("{0} leads").format(total)
    return _wrap(_("Lead History"), label, table)


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
