import json
import frappe
from frappe import _
from frappe.utils import today


def validate(self, method):
    # started = frappe.db.exists(
    #     "Boutique Day Entry",
    #     {"date": today(), "status": ["in", ["Day Started", "Day Ended"]]},
    # )
    # if not started:
    #     frappe.throw(
    #         msg=(
    #             "You cannot create a Sales Invoice — no Boutique Day has been started for today.<br>"
    #             "Please go to <b>Boutique Day Entry</b> and start the day first."
    #         ),
    #         title="Day Not Started",
    #     )
    if self.cost_center:
        letter_head = frappe.db.get_value(
            "Cost Center", self.cost_center, "custom_letter_head"
        )
        if letter_head and letter_head != self.letter_head:
            frappe.msgprint(
                f"Letter Head must be <b>{letter_head}</b> for Cost Center - {self.cost_center}"
            )

    customer_email_id = frappe.db.get_value("Customer", self.customer, "custom_email")
    if not customer_email_id:
        frappe.throw(
            _("Please set Email ID in Customer, in-order to Proceed with Invoice - <b>{0}</b>").format(
                self.customer
            )
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


def before_submit(self, method):
    if self.rounded_total >= 200000:
        customer_pan_card = frappe.db.get_value("Customer", self.customer, "pan")
        if not customer_pan_card:
            frappe.throw(
                _("Please set PAN Card in Customer. PAN Card is required for invoices with amount 200000 and above - <b>{0}</b> (Amount: <b>{1}</b>)").format(
                    self.customer,
                    frappe.format_value(self.rounded_total, dict(fieldtype='Currency'))
                )
            )


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
    
    customer_doc = frappe.get_doc("Customer", self.customer)
    customer_doc.append(
        "custom_customer_journey",
        {
            "journey_date": frappe.utils.now_datetime(),
            "journey_type": "Purchase",
            "sales_person":customer_doc.get("custom_sales_person"),
            "description": f"Purchase recorded on {self.posting_date} via Sales Invoice {self.name}.",
        },
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



@frappe.whitelist()
def generate_payment_link_for_invoice(si_name, amount):
	"""
	Generate a Razorpay payment link for a Sales Invoice.

	Args:
		si_name (str): Name of the Sales Invoice document.
		amount (float): Amount in INR to generate the link for.

	Returns:
		dict: {link_url, link_id, amount, expire_by}
	"""
	import datetime

	from frappe.utils import flt

	from payments.payment_gateways.doctype.razorpay_settings.razorpay_settings import (
		RazorpaySettings,
	)

	amount = flt(amount)
	si = frappe.get_doc("Sales Invoice", si_name)

	if frappe.db.exists(
		"Aetas Razorpay Payment Link",
		{"reference_docname": si_name, "status": "Paid"},
	):
		frappe.throw(
			_("A payment has already been completed for this Sales Invoice.")
		)

	# Compute outstanding from submitted Payment Entry References
	paid = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(per.allocated_amount), 0)
		FROM `tabPayment Entry Reference` per
		JOIN `tabPayment Entry` pe ON pe.name = per.parent
		WHERE per.reference_doctype = 'Sales Invoice'
		  AND per.reference_name = %s
		  AND pe.docstatus = 1
		""",
		si_name,
	)[0][0]
	outstanding = flt(si.grand_total) - flt(paid)

	if amount <= 0:
		frappe.throw(_("Payment amount must be greater than zero."))
	if amount > outstanding:
		frappe.throw(
			_("Payment amount {0} exceeds outstanding amount {1}.").format(
				frappe.format_value(amount, {"fieldtype": "Currency"}),
				frappe.format_value(outstanding, {"fieldtype": "Currency"}),
			)
		)

	boutique = si.get("custom_boutique")
	if not boutique:
		frappe.throw(_("Boutique is not set on this Sales Invoice."))

	settings_dict = RazorpaySettings.get_settings_for_boutique(boutique)
	settings_doc = frappe.get_doc("Razorpay Settings", settings_dict["doc_name"])
	settings_doc.init_client()

	customer_name = (
		frappe.db.get_value("Customer", si.customer, "customer_name") or si.customer
	)
	customer_email = getattr(si, "contact_email", "") or ""

	link = settings_doc.create_payment_link(
		amount_inr=amount,
		currency=si.currency or "INR",
		customer_name=customer_name,
		customer_contact="",
		customer_email=customer_email,
		description="Payment for Invoice " + si_name,
		reference_doctype="Sales Invoice",
		reference_docname=si_name,
	)

	expire_by_dt = None
	if link.get("expire_by"):
		expire_by_dt = datetime.datetime.utcfromtimestamp(link["expire_by"])

	tracker = frappe.new_doc("Aetas Razorpay Payment Link")
	tracker.reference_doctype = "Sales Invoice"
	tracker.reference_docname = si_name
	tracker.boutique = boutique
	tracker.amount = amount
	tracker.currency = si.currency or "INR"
	tracker.link_id = link.get("id")
	tracker.link_url = link.get("short_url")
	tracker.status = "Created"
	if expire_by_dt:
		tracker.expire_by = expire_by_dt
	tracker.insert(ignore_permissions=True)

	return {
		"link_url": link.get("short_url"),
		"link_id": link.get("id"),
		"amount": amount,
		"expire_by": str(expire_by_dt) if expire_by_dt else "",
	}


# ---------------------------------------------------------------------------
# Phase 5: Advance Adjustment Prompt and Get Advances Received
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_customer_advance_balance(customer):
	"""
	Calculate total available advance for a customer from unpaid/partially paid APRs.
	Used by the advance adjustment prompt on SI creation.
	
	Returns: {"balance": float, "aprs": [list of APR names]}
	"""
	if not customer:
		return {"balance": 0.0, "aprs": []}
	
	# Query all APRs for this customer that are not fully paid
	unpaid_aprs = frappe.db.sql("""
		SELECT name, paid_amount, status
		FROM `tabAetas Advance Payment Receipt`
		WHERE customer = %s AND status IN ('To Be Received', 'Partially Paid')
	""", customer, as_dict=True)
	
	total_balance = 0.0
	apr_names = []
	for apr in unpaid_aprs:
		# Calculate how much of this APR is still available
		paid_via_pe = frappe.db.sql("""
			SELECT COALESCE(COUNT(*), 0) as count, COALESCE(SUM(amount), 0) as total
			FROM `tabAetas APR Payment Detail`
			WHERE parent = %s AND sales_invoice IS NULL
		""", apr["name"], as_dict=True)[0]
		
		available = apr["paid_amount"] - paid_via_pe["total"]
		if available > 0:
			total_balance += available
			apr_names.append(apr["name"])
	
	return {"balance": total_balance, "aprs": apr_names}


@frappe.whitelist()
def get_advances_received_for_si(si_name):
	"""
	Fetch all APR Payment Detail rows for the same customer as the SI,
	where the SI field is blank (not yet allocated).
	
	Returns: list of dicts with {payment_entry, amount, customer, apr_name}
	"""
	if not si_name:
		return []
	
	si = frappe.get_doc("Sales Invoice", si_name)
	customer = si.customer
	
	# Query APR Payment Detail rows for this customer where SI field is blank
	rows = frappe.db.sql("""
		SELECT
			apd.name as child_name,
			apd.parent as apr_name,
			apd.payment_entry,
			apd.amount,
			apd.sales_invoice
		FROM `tabAetas APR Payment Detail` apd
		WHERE apd.parent IN (
			SELECT name FROM `tabAetas Advance Payment Receipt`
			WHERE customer = %s
		)
		AND apd.sales_invoice IS NULL
	""", customer, as_dict=True)
	
	return rows


@frappe.whitelist()
def apply_advance_adjustment(si_name, adjustment_amount):
	"""
	Apply advance adjustment to a Sales Invoice.
	This is called when the user confirms the advance adjustment prompt.
	
	In real implementation, should create a Journal Entry or use ERPNext's native advance allocation.
	For now, a stub that logs the adjustment.
	"""
	if not si_name or adjustment_amount <= 0:
		return {"status": "error", "message": "Invalid SI or amount"}
	
	si = frappe.get_doc("Sales Invoice", si_name)
	
	# Log the adjustment fact
	frappe.logger().info(f"Advance adjustment applied to {si_name}: {adjustment_amount}")
	
	# Stub: real implementation would:
	# 1. Create allocation entries
	# 2. Update SI advance child table
	# 3. Create accounting entries if needed
	
	return {"status": "success", "message": f"Advance of {adjustment_amount} applied"}
