import hmac
import hashlib
import json

# Data provided by the user in previous context
webhook_secret = "tcYXdPOd9y1J0rYg6fEmGVPV"
razorpay_signature = "69e160a0006734c31168926d56637b587a32fc451458e0a7e5836480b4570094"

# Raw payload (must be the exact byte-for-byte string received from Razorpay)
raw_payload_str = '{"account_id":"acc_SabAvj4ik6sbRe","contains":["payment_link","order","payment"],"created_at":1776864334,"entity":"event","event":"payment_link.paid","payload":{"order":{"entity":{"amount":150000,"amount_due":0,"amount_paid":150000,"attempts":1,"checkout":null,"created_at":1776864339,"currency":"INR","description":null,"entity":"order","id":"order_SgYQLXxCU1kOIj","notes":{"reference_docname":"AAPR-00127","reference_doctype":"Aetas Advance Payment Receipt"},"offer_id":null,"receipt":null,"status":"paid"}},"payment":{"entity":{"acquirer_data":{"auth_code":null},"amount":150000,"amount_captured":150000,"amount_refunded":0,"amount_transferred":0,"authentication":{"authentication_channel":"browser","version":""},"bank":null,"base_amount":150000,"captured":true,"card":{"emi":false,"entity":"card","id":"card_SgYRBRT0VGe6cn","international":false,"issuer":"DCBL","last4":"1007","name":"","network":"Visa","sub_type":"consumer","type":"debit"},"card_id":"card_SgYRBRT0VGe6cn","contact":"+919887787673","created_at":1776864386,"currency":"INR","description":"#SgYQFaEkFrQDUB","email":"void@razorpay.com","entity":"payment","error_code":null,"error_description":null,"error_reason":null,"error_source":null,"error_step":null,"fee":3300,"fee_bearer":"platform","id":"pay_SgYRBRT0VGe6cn","international":false,"invoice_id":null,"method":"card","notes":{"reference_docname":"AAPR-00127","reference_doctype":"Aetas Advance Payment Receipt"},"order_id":"order_SgYQLXxCU1kOIj","refund_status":null,"status":"captured","tax":0,"vpa":null,"wallet":null}},"payment_link":{"entity":{"accept_partial":false,"amount":150000,"amount_paid":150000,"cancelled_at":0,"created_at":1776864334,"currency":"INR","customer":{"name":"Aetas Retail Private Limited"},"description":"Payment for Advance Receipt AAPR-00127","expire_by":1776902400,"expired_at":0,"first_min_partial_amount":0,"id":"plink_SgYQFaEkFrQDUB","notes":{"reference_docname":"AAPR-00127","reference_doctype":"Aetas Advance Payment Receipt"},"notify":{"email":false,"sms":false,"whatsapp":false},"order_id":"order_SgYQLXxCU1kOIj","reference_id":"","reminder_enable":false,"reminders":{},"short_url":"https://rzp.io/rzp/2MIkY7TP","status":"paid","updated_at":1776864400,"upi_link":false,"user_id":"","whatsapp_link":false}}}}'

def verify_signature(body, signature, secret):
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    print(f"Expected: {expected_signature}")
    print(f"Received: {signature}")
    
    return hmac.compare_digest(expected_signature, signature)

try:
    # Test with razorpay library if available, otherwise use hmac
    import razorpay
    client = razorpay.Client(auth=("ANY", "ANY"))
    # verify_webhook_signature raises SignatureVerificationError if fails
    client.utility.verify_webhook_signature(raw_payload_str, razorpay_signature, webhook_secret)
    print("SUCCESS: Razorpay library validated the signature.")
except ImportError:
    print("Razorpay library not found, using native hmac check.")
    if verify_signature(raw_payload_str, razorpay_signature, webhook_secret):
        print("SUCCESS: Manual HMAC check passed.")
    else:
        print("FAILED: Manual HMAC check failed.")
except Exception as e:
    print(f"FAILED: {str(e)}")
