# Aetas Razorpay Integration: Technical Documentation & User Guide

This document provides a comprehensive overview of the Razorpay integration for Aetas, covering the custom workflow from **Advance Payment Receipt (APR)** to automated **Accounting Settlements**.

## 1. Workflow Architecture

The integration replaces the standard "Payment Link" with a specialized **Aetas Advance Payment Receipt** workflow.

### Sequence Flow
1.  **Lead/Customer Request**: A payment link is generated from an APR.
2.  **Razorpay Checkout**: Customer pays via the hosted link.
3.  **Webhook Notification**: Razorpay sends a `payment.captured` or `order.paid` event.
4.  **Automatic Payment Entry**:
    - The webhook creates a `Payment Entry` in ERPNext.
    - Status of the source APR is updated to `Paid`.
    - **Fees are accounted for automatically** (Phase 6).

---

## 2. Advanced Accounting: Razorpay Fees (Phase 6)

The system automatically calculates and records Razorpay transaction fees to ensure bank reconciliations match net payouts.

### Configuration (`Razorpay Settings`)
Navigate to **Razorpay Settings** to configure these fields:
- **Charge Accounting Option**:
  - **Option A (Deduction)**: Adds a row to the "Deductions" table of the Payment Entry. The customer gets full credit, but the bank debit is net of fees.
  - **Option B (Journal Entry)**: Creates a separate Journal Entry for the fee, keeping the Payment Entry simple.
- **Transaction Fee %**: Default is `2.36` (2% + 18% GST).
- **Charge Account**: The expense ledger for fees (e.g., "Bank Charges").
- **Tax Account**: The input tax ledger for GST on fees.

---

## 3. Sales Invoice Integration (Phase 5)

When creating a **Sales Invoice** for a customer who has paid an advance:
- **Prompt**: A dialog appears if unlinked APRs exist.
- **Auto-Allocation**: Selecting "Apply Advance" automatically fetches the APR and populates the `Advances` table.
- **Validation**: Ensures the same APR isn't applied twice.

---

## 4. Technical Reference for Developers

### Webhook Security
- **Idempotency**: Secured via `X-Razorpay-Event-Id` header to prevent duplicate accounting.
- **Signature Verification**: Standard Razorpay HMAC verification is enforced.

### Custom Hooks
- `aetas_customization.test_setup.py`: Used during development/CI to shield the app from environment-specific validation errors (e.g., `india_compliance` GST checks).

### Key Files
- `aetas_customization/api/webhook.py`: Core logic for Payment Entry and Journal Entry creation.
- `aetas_customization/doctype/aetas_advance_payment_receipt/`: Main document for managing payment links.
- `payments/payment_gateways/doctype/razorpay_settings/`: Extended schema for charges.

---

## 5. Troubleshooting & FAQ

**Q: Why is the Payment Entry amount lower than the APR?**
A: If **Option A** is enabled, the Bank Account debit is the *net* amount after fees, while the Customer credit remains the *gross* amount.

**Q: What happens if a webhook fails?**
A: The `Aetas Advance Payment Receipt` remains in `Unpaid` status. Check the **Error Log** in ERPNext for the specific traceback from `webhook.py`.
