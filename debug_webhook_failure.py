import frappe
import json
from aetas_customization.aetas_customization.api.webhook import _handle_payment_link_paid

def simulate_webhook_processing():
    # Payload from ARAL-00018
    raw_payload_str = """{"account_id": "acc_SabAvj4ik6sbRe", "contains": ["payment_link", "order", "payment"], "created_at": 1776929679, "entity": "event", "event": "payment_link.paid", "payload": {"order": {"entity": {"amount": 150000, "amount_due": 0, "amount_paid": 150000, "attempts": 1, "checkout": null, "created_at": 1776929684, "currency": "INR", "description": null, "entity": "order", "id": "order_SgqymrXereENJu", "notes": {"reference_docname": "AAPR-00127", "reference_doctype": "Aetas Advance Payment Receipt"}, "offer_id": null, "receipt": null, "status": "paid"}}, "payment": {"entity": {"acquirer_data": {"auth_code": null}, "amount": 150000, "amount_captured": 150000, "amount_refunded": 0, "amount_transferred": 0, "authentication": {"authentication_channel": "browser", "version": ""}, "bank": null, "base_amount": 150000, "captured": true, "card": {"emi": false, "entity": "card", "id": "card_SgqzGAIFCT8Tzm", "international": false, "issuer": "DCBL", "last4": "1007", "name": "", "network": "Visa", "sub_type": "consumer", "type": "debit"}, "card_id": "card_SgqzGAIFCT8Tzm", "contact": "+919887787677", "created_at": 1776929711, "currency": "INR", "description": "#SgqyhBcD0h8VpC", "email": "void@razorpay.com", "entity": "payment", "error_code": null, "error_description": null, "error_reason": null, "error_source": null, "error_step": null, "fee": 3300, "fee_bearer": "platform", "id": "pay_SgqzGAIFCT8Tzm", "international": false, "invoice_id": null, "method": "card", "notes": {"reference_docname": "AAPR-00127", "reference_doctype": "Aetas Advance Payment Receipt"}, "order_id": "order_SgqymrXereENJu", "refund_status": null, "status": "captured", "tax": 0, "vpa": null, "wallet": null}}, "payment_link": {"entity": {"accept_partial": false, "amount": 150000, "amount_paid": 150000, "cancelled_at": 0, "created_at": 1776929679, "currency": "INR", "customer": {"name": "Aetas Retail Private Limited"}, "description": "Payment for Advance Receipt AAPR-00127", "expire_by": 1776988800, "expired_at": 0, "first_min_partial_amount": 0, "id": "plink_SgqyhBcD0h8VpC", "notes": {"reference_docname": "AAPR-00127", "reference_doctype": "Aetas Advance Payment Receipt"}, "notify": {"email": false, "sms": false, "whatsapp": false}, "order_id": "order_SgqymrXereENJu", "reference_id": "", "reminder_enable": false, "reminders": {}, "short_url": "https://rzp.io/rzp/6bFFZ7V", "status": "paid", "updated_at": 1776929756, "upi_link": false, "user_id": "", "whatsapp_link": false}}}}"""
    payload = json.loads(raw_payload_str)
    
    frappe.connect()
    try:
        frappe.set_user("Administrator")
        result = _handle_payment_link_paid(payload)
        print(f"Result: {result}")
        frappe.db.commit()
    except Exception:
        print(frappe.get_traceback())
    finally:
        frappe.destroy()

if __name__ == "__main__":
    simulate_webhook_processing()
