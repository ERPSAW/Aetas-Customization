import json

import frappe
from frappe import _


def validate(self, method):
    if self.cost_center:
        letter_head = frappe.db.get_value(
            "Cost Center", self.cost_center, "custom_letter_head"
        )
        if letter_head and letter_head != self.letter_head:
            frappe.msgprint(
                f"Letter Head must be <b>{letter_head}</b> for Cost Center - {self.cost_center}"
            )

    update_mrp_values(self)
    if self.custom_aetas_coupon_code:
        total = (
            self.grand_total if self.disable_rounded_total == 1 else self.rounded_total
        )
        coupon_data = validate_coupon_code(
            self.custom_aetas_coupon_code,
            json.dumps(
                list(
                    map(
                        lambda x: {
                            "item_code": x.item_code,
                            "base_amount": x.base_amount,
                        },
                        self.items,
                    )
                )
            ),
            total,
        )
        if coupon_data.get("status") == "Valid":
            self.discount_amount = coupon_data.get("total_discount", 0.0)
            self.apply_discount_on = "Grand Total"
            frappe.msgprint(
                f"Coupon code applied , Amount: {frappe.format_value(coupon_data.get('total_discount', 0.0), dict(fieldtype='Currency'))}"
            )
        else:
            self.custom_aetas_coupon_code = None
            self.discount_amount = 0.0
            self.apply_discount_on = "Grand Total"
            frappe.msgprint(
                f"Coupon code not applicable, Reason: {coupon_data.get('message')}"
            )
        self.calculate_taxes_and_totals()


def on_submit(self, method):
    """
    Called when Sales Invoice is submitted. Marks coupon as Used and updates redeemed amount.
    """
    if self.custom_lead_ref:
        frappe.db.set_value(
            "Lead",
            self.custom_lead_ref,
            {"custom_si_ref": self.name, "status": "Converted"},
            update_modified=False,
        )

    customer = frappe.db.get_value(
        "Customer", self.customer, "custom_customer_without_sales"
    )
    if customer:
        frappe.db.set_value(
            "Customer",
            self.customer,
            "custom_customer_without_sales",
            0,
            update_modified=False,
        )

    if not getattr(self, "custom_aetas_coupon_code", None):
        return

    applied = True
    coupon_name = frappe.db.get_value(
        "AETAS Coupon Code", {"coupon_code": self.custom_aetas_coupon_code}
    )
    if not coupon_name:
        applied = False
        # This shouldn't happen because we validated earlier, but guard anyway
        frappe.throw(
            _("Coupon code not found: {0}").format(self.custom_aetas_coupon_code)
        )

    coupon = frappe.get_doc("AETAS Coupon Code", coupon_name)

    # Prevent double-redemption if coupon already used. Adjust logic if coupon can be reused.
    if coupon.get("status") == "Used":
        applied = False
        frappe.throw(
            _("Coupon {0} is already used.").format(self.custom_aetas_coupon_code)
        )
    if applied:
        # Increase redeemed amount and mark used
        coupon.redeemed_amount = float(self.discount_amount or 0.0)
        coupon.status = "Used"
        # store references - create these fields on AETAS Coupon Code selftype if not present:
        # redeemed_from_si (Data / Link to Sales Invoice), redeemed_customer, redeemed_on
        coupon.sales_invoice_reference = self.name
        coupon.customer_reference = self.customer
        coupon.flags.ignore_permissions = True
        coupon.save()
        frappe.msgprint(_("Coupon Code marked as 'Used'"))


def on_cancel(self, method):
    """
    Called when Sales Invoice is cancelled. Revert redeemed_amount and coupon status.
    """
    if self.custom_lead_ref:
        frappe.db.set_value(
            "Lead", self.custom_lead_ref, "custom_si_ref", None, update_modified=False
        )

    if not getattr(self, "custom_aetas_coupon_code", None):
        return

    coupon_name = frappe.db.get_value(
        "AETAS Coupon Code", {"coupon_code": self.custom_aetas_coupon_code}
    )
    if not coupon_name:
        return

    coupon = frappe.get_doc("AETAS Coupon Code", coupon_name)
    # Subtract redeemed amount — ensure not negative
    coupon.redeemed_amount = 0.0
    coupon.status = "Active"
    coupon.sales_invoice_reference = None
    coupon.customer_reference = None
    coupon.flags.ignore_permissions = True
    coupon.save()
    frappe.msgprint(_("Coupon Code marked as 'Active'"))


def update_mrp_values(self):
    for item in self.items:
        if item.item_code and item.serial_no:
            mrp_value_from_pii = frappe.db.sql(
                """
            select mrp
            from`tabPurchase Invoice Item`
            where item_code = %s and (serial_no = %s or serial_no like %s or serial_no like %s or serial_no like %s)
            """,
                (
                    item.item_code,
                    item.serial_no,
                    item.serial_no + "\n%",
                    "%\n" + item.serial_no,
                    "%\n" + item.serial_no + "\n%",
                ),
                as_dict=1,
            )

            mrp_value_from_se = frappe.db.sql(
                """
            select custom_mrp as mrp
            from`tabStock Entry Detail`
            where item_code = %s and (serial_no = %s or serial_no like %s or serial_no like %s or serial_no like %s)
            """,
                (
                    item.item_code,
                    item.serial_no,
                    item.serial_no + "\n%",
                    "%\n" + item.serial_no,
                    "%\n" + item.serial_no + "\n%",
                ),
                as_dict=1,
            )

            if mrp_value_from_pii:
                item.mrp = mrp_value_from_pii[0].mrp
            elif mrp_value_from_se:
                item.mrp = mrp_value_from_se[0].mrp
            else:
                item.mrp = 0


@frappe.whitelist()
def validate_coupon_code(coupon_code, items, grand_total):
    """
    Validate and apply coupon.

    Args:
        coupon_code (str): coupon code to validate
        items (str): JSON string list of item rows. Each row MUST include:
                      - item_code
                      - base_amount (numeric)
        grand_total (numeric or str): original invoice grand total

    Returns:
        dict: {
            status: "Valid" | "Not Applicable" | "Invalid" | "Inactive",
            message: str,
            total_discount: float,
            final_total: float,
            breakdown: [ { item_group, group_total, applied_rule, discount, message }, ... ]
        }
    """

    def to_number(v):
        try:
            return float(v)
        except Exception:
            return 0.0

    # Basic checks
    if not coupon_code:
        return {
            "status": "Invalid",
            "message": "Coupon code is required.",
            "total_discount": 0.0,
            "final_total": grand_total,
            "breakdown": [],
        }

    try:
        items_list = json.loads(items)
    except Exception:
        return {
            "status": "Invalid",
            "message": "Invalid items payload (must be JSON).",
            "total_discount": 0.0,
            "final_total": grand_total,
            "breakdown": [],
        }

    # 1. Verify coupon exists and is active
    coupon = frappe.db.get_value(
        "AETAS Coupon Code", {"coupon_code": coupon_code}, ["name", "status"], as_dict=1
    )
    if not coupon:
        return {
            "status": "Invalid",
            "message": "Invalid Coupon Code",
            "total_discount": 0.0,
            "final_total": grand_total,
            "breakdown": [],
        }
    if coupon.get("status") != "Active":
        return {
            "status": "Inactive",
            "message": "Coupon Code is not Active",
            "total_discount": 0.0,
            "final_total": grand_total,
            "breakdown": [],
        }

    # 2. Build list of item_codes and ensure base_amount present (per your assumption)
    item_rows = []
    item_codes = set()
    for row in items_list:
        item_code = row.get("item_code") or row.get("item")
        base_amount = row.get("base_amount")
        if item_code is None or base_amount is None:
            # Fail fast if required fields missing
            return {
                "status": "Invalid",
                "message": "Each item must include item_code and base_amount",
                "total_discount": 0.0,
                "final_total": grand_total,
                "breakdown": [],
            }
        item_rows.append(
            {"item_code": item_code, "base_amount": to_number(base_amount)}
        )
        item_codes.add(item_code)

    if not item_rows:
        return {
            "status": "Invalid",
            "message": "No items provided",
            "total_discount": 0.0,
            "final_total": grand_total,
            "breakdown": [],
        }

    # 3. Resolve item_code -> item_group in one DB call
    item_group_map = {}
    item_codes_list = list(item_codes)
    # Use get_all for efficiency
    fetched_items = frappe.get_all(
        "Item", filters=[["name", "in", item_codes_list]], fields=["name", "item_group"]
    )
    for it in fetched_items:
        item_group_map[it["name"]] = it.get("item_group")

    # For any item not found in Item table, set group to None (we will handle below)
    for r in item_rows:
        if r["item_code"] not in item_group_map:
            item_group_map[r["item_code"]] = None

    # 4. Sum base_amount per item_group
    group_totals = {}
    for r in item_rows:
        grp = item_group_map.get(r["item_code"]) or "UNASSIGNED"
        group_totals.setdefault(grp, 0.0)
        group_totals[grp] += to_number(r["base_amount"])

    # 5. For each group, find config and matching child rule
    total_discount = 0.0
    breakdown = []

    for group, group_total in group_totals.items():
        if group == "UNASSIGNED":
            # breakdown.append({
            #     "item_group": None,
            #     "group_total": group_total,
            #     "applied_rule": None,
            #     "discount": 0.0,
            #     "message": "Item(s) not found in Item master"
            # })
            continue

        # Find AETAS Coupon Configuration for this item_group (expect at most one)
        configs = frappe.get_all(
            "AETAS Coupon Configuration",
            filters=[["item_group", "=", group]],
            fields=["name"],
            limit_page_length=1,
            as_list=False,
        )

        if not configs:
            breakdown.append(
                {
                    "item_group": group,
                    "group_total": group_total,
                    "applied_rule": None,
                    "discount": 0.0,
                    "message": "No coupon configuration for this item group",
                }
            )
            continue

        config_name = configs[0]["name"]

        # Fetch child rows (assumed child doctype name) and iterate for matching range
        rules = frappe.get_all(
            "Item Group Coupon Configuration",
            filters=[["parent", "=", config_name]],
            fields=["name", "idx", "from", "to", "discount_amount"],
            order_by="idx asc",
            as_list=False,
        )

        applied_rule = None
        applied_discount = 0.0
        applied_message = "No matching rule"

        for r in rules:
            fr_raw = r.get("from")
            to_raw = r.get("to")
            fr = to_number(fr_raw)
            to_val = to_number(to_raw) if to_raw not in (None, "") else 0.0
            disc = to_number(r.get("discount_amount") or 0.0)

            # Requested logic:
            # - if to == 0 -> match when group_total >= from
            # - if from != 0 and to != 0 -> match when from <= group_total <= to
            # fallback: if from == 0 and to != 0 -> match when group_total <= to
            match = False
            if to_val == 0.0:
                # open upper bound
                match = group_total >= fr
            elif fr != 0.0 and to_val != 0.0:
                match = (group_total >= fr) and (group_total <= to_val)
            else:
                # fallback: from == 0 and to != 0
                match = group_total <= to_val

            if match:
                applied_rule = {
                    "parent_config": config_name,
                    "rule_name": r.get("name"),
                    "from": fr,
                    "to": (None if to_val == 0.0 else to_val),
                    "discount_amount": disc,
                }
                applied_discount = disc
                applied_message = "Rule applied"
                break

        total_discount += applied_discount
        breakdown.append(
            {
                "item_group": group,
                "group_total": group_total,
                "applied_rule": applied_rule,
                "discount": applied_discount,
                "message": applied_message,
            }
        )

    # 6) finalize totals
    grand_total_num = to_number(grand_total)
    final_total = grand_total_num - total_discount
    if final_total < 0:
        final_total = 0.0

    any_applied = any(b.get("applied_rule") for b in breakdown)
    if not any_applied:
        return {
            "status": "Not Applicable",
            "message": "Coupon not applicable for provided items",
            "total_discount": 0.0,
            "final_total": grand_total_num,
            "breakdown": breakdown,
        }

    return {
        "status": "Valid",
        "message": "Coupon applied",
        "total_discount": total_discount,
        "final_total": final_total,
        "breakdown": breakdown,
    }
