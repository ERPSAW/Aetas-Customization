# Copyright (c) 2026, Akhilam Inc and contributors
# For license information, please see license.txt

from typing import Any

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, today


class BoutiqueDayEntry(Document):
    def validate(self) -> None:
        self._check_duplicate()

    def _check_duplicate(self) -> None:
        exists = frappe.db.exists(
            "Boutique Day Entry",
            {
                "boutique": self.boutique,
                "date": self.date,
                "name": ("!=", self.name or "new-boutique-day-entry-1"),
            },
        )
        if exists:
            frappe.throw(
                f"A Day Entry for <b>{self.boutique}</b> on <b>{self.date}</b> already exists: <b>{exists}</b>",
                title="Duplicate Entry",
            )


# ─────────────────────────────────────────────────────────────────────────────
# Public API Methods
# ─────────────────────────────────────────────────────────────────────────────


@frappe.whitelist()
def get_current_user_boutique() -> str | None:
    """
    Traverse the User -> Employee -> Sales Person hierarchy to find the assigned boutique.
    Returns None if the user is unauthorized or missing links.
    """
    user = frappe.session.user

    # 1. Must have the exact role
    if "Boutique Manager" not in frappe.get_roles(user):
        return None

    # 2. Must be linked to an Employee record
    employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
    if not employee:
        return None

    # 3. Employee must be linked to a Sales Person, extract custom_botique
    boutique = frappe.db.get_value(
        "Sales Person", 
        {"employee": employee}, 
        "custom_botique"
    )

    return boutique


@frappe.whitelist()
def get_entries_for_page(boutique: str, limit: int | str = 10) -> list[dict[str, Any]]:
    entries = frappe.db.get_all(
        "Boutique Day Entry",
        filters={"boutique": boutique},
        fields=["*"],
        order_by="date desc",
        limit=int(limit),
    )

    metrics = [
        "walk_in", "new_customers", "existing_customers", "total_invoices",
        "cc", "bank_transfer", "cash", "other"
    ]

    for entry in entries:
        if entry.status == "Day Ended":
            doc = frappe.get_doc("Boutique Day Entry", entry.name)
            for m in metrics:
                table_field = f"{m}_attachments"
                entry[table_field] = [row.file for row in doc.get(table_field)]
        else:
            for m in metrics:
                entry[f"{m}_attachments"] = []

    return entries


@frappe.whitelist()
def get_day_status(boutique):
    today_date = today()

    today_entry = frappe.db.get_value(
        "Boutique Day Entry",
        {"boutique": boutique, "date": today_date},
        [
            "name", "date", "status", "day_start_petty_cash", 
            "day_started_at", "day_started_by", 
            "day_ended_at", "day_end_petty_cash", "total_invoices",
            "walk_in", "new_customers", "existing_customers",
            "cc", "bank_transfer", "cash", "other"
        ],
        as_dict=True,
    )

    pending_previous = frappe.db.get_value(
        "Boutique Day Entry",
        {"boutique": boutique, "date": ("<", today_date), "status": ("!=", "Day Ended")},
        ["name", "date", "status", "day_start_petty_cash", "day_started_at", "day_started_by"],
        as_dict=True,
        order_by="date desc",
    )

    return {
        "today_entry": today_entry,
        "pending_previous": pending_previous,
    }

@frappe.whitelist()
def start_day(boutique: str, petty_cash: float | str = 0, remarks: str = "") -> dict[str, Any]:
    today_date = today()
    existing = frappe.db.get_value(
        "Boutique Day Entry",
        {"boutique": boutique, "date": today_date},
        ["name", "status"],
        as_dict=True,
    )

    if existing:
        if existing.status == "Day Started":
            frappe.throw("Day has already been started for today.")
        if existing.status == "Day Ended":
            frappe.throw("Day has already been completed for today.")
        doc = frappe.get_doc("Boutique Day Entry", existing.name)
    else:
        doc = frappe.new_doc("Boutique Day Entry")
        doc.boutique = boutique
        doc.date = today_date

    doc.day_start_petty_cash = float(petty_cash or 0)
    doc.day_start_remarks = remarks or ""
    doc.status = "Day Started"
    doc.day_started_at = now_datetime()
    doc.day_started_by = frappe.session.user
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "name": doc.name,
        "status": doc.status,
        "day_started_at": str(doc.day_started_at),
        "day_started_by": doc.day_started_by,
    }


@frappe.whitelist()
def end_day(entry_name: str, payload: str) -> dict[str, Any]:
    doc = frappe.get_doc("Boutique Day Entry", entry_name)

    if doc.status == "Day Ended":
        frappe.throw("Day has already been ended.")
    if doc.status == "Draft":
        frappe.throw("Day was never started. Please start the day first.")

    data = frappe.parse_json(payload)

    system_count = frappe.db.count(
        "Sales Invoice",
        {"posting_date": doc.date, "docstatus": 1},
    )

    metrics = [
        "walk_in", "new_customers", "existing_customers", "total_invoices",
        "cc", "bank_transfer", "cash", "other"
    ]

    for metric in metrics:
        doc.set(metric, data.get(metric, 0))
        doc.set(f"{metric}_remarks", data.get(f"{metric}_remarks", ""))
        
        table_field = f"{metric}_attachments"
        doc.set(table_field, []) 
        
        for file_id in data.get(table_field, []):
            if file_id:
                doc.append(table_field, {"file": file_id})

    doc.total_invoices_from_system = system_count
    doc.day_end_petty_cash = float(data.get("day_end_petty_cash", 0))
    doc.status = "Day Ended"
    doc.day_ended_at = now_datetime()
    doc.day_ended_by = frappe.session.user
    
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "name": doc.name,
        "status": doc.status,
        "total_invoices_from_system": system_count,
        "day_end_petty_cash": doc.day_end_petty_cash,
        "day_ended_at": str(doc.day_ended_at),
    }


@frappe.whitelist()
def get_previous_petty_cash(boutique: str) -> dict[str, Any]:
    val = frappe.db.get_value(
        "Boutique Day Entry",
        {"boutique": boutique, "status": "Day Ended", "date": ("<", today())},
        "day_end_petty_cash",
        order_by="date desc",
    )
    return {"petty_cash": val or 0}


def validate_sales_invoice(doc: Document, method: str) -> None:
    if "Boutique Manager" not in frappe.get_roles(user):
        return

    started = frappe.db.exists(
        "Boutique Day Entry",
        {"date": today(), "status": ["in", ["Day Started", "Day Ended"]]},
    )
    if not started:
        frappe.throw(
            msg=(
                "You cannot create a Sales Invoice — no Boutique Day has been started for today.<br>"
                "Please go to <b>Boutique Day Entry</b> and start the day first."
            ),
            title="Day Not Started",
        )