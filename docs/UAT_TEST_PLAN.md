# Aetas Razorpay Integration: Functional Testing & UAT Guide

This document provides step-by-step instructions for a **non-developer** to test the new Razorpay multi-boutique and automated accounting features.

---

## Prerequisites
- Access to the **ERPNext Desk** (Frappe Cloud or local site).
- Razorpay Dashboard access (Test Mode) or a test API Key configured in **Razorpay Settings**.
- **Crucial**: Configure the **Webhook Secret** in `Razorpay Settings` for each boutique. This secret must match the one provided in the Razorpay Dashboard's Webhook configuration.
- At least one **Boutique** record configured with a linked **Razorpay Account**.

---

## Test Scenario 1: Generate and Pay an Advance Receipt
**Goal**: Verify the customer can receive a link and the payment is recorded automatically.

1.  **Create Receipt**:
    - Go to **Aetas Advance Payment Receipt** > New.
    - Select a **Customer** and a **Boutique**.
    - Set an **Amount** (e.g., ₹100).
    - Save and **Submit**.
2.  **Generate Link**:
    - Click **Create Razorpay Link** button.
    - Status should change to **Unpaid**.
    - Copy the **Razorpay Payment URL** from the link section.
3.  **Simulate Payment**:
    - Open the URL in a browser. 
    - Complete the payment using "Netbanking" or "Card" (Use Razorpay Test Mode success credentials).
4.  **Verify Result**:
    - Wait 30-60 seconds for the webhook to process.
    - Refresh the **Aetas Advance Payment Receipt**.
    - **Status** should now be **Paid**.
    - Open the **Connections** (Dashboard icon) and verify a **Payment Entry** has been created.

---

## Test Scenario 2: Accounting for Razorpay Fees (Option A)
**Goal**: Verify that the bank receives the net amount and fees are logged.

1.  **Configure Settings**:
    - Go to **Razorpay Settings**.
    - Set **Charge Accounting Option** to **Option A (Deduction)**.
    - Ensure **Transaction Fee %** is set (e.g., 2.36).
    - Save.
2.  **Repeat Scenario 1** (Create, Link, Pay).
3.  **Verify Accounting**:
    - Open the resulting **Payment Entry**.
    - Go to the **Deductions or Loss** table.
    - You should see a row for your **Charge Account** with the fee amount.
    - **Received Amount** (Bank Debit) should be exactly: *Total Paid - Fees*.
    - **Allocated Amount** (Customer Credit) should be the *Full Total*.

---

## Test Scenario 3: Accounting for Razorpay Fees (Option B)
**Goal**: Verify that a separate Journal Entry is created for fees.

1.  **Configure Settings**:
    - Go to **Razorpay Settings**.
    - Set **Charge Accounting Option** to **Option B (Journal Entry)**.
    - Save.
2.  **Repeat Scenario 1**.
3.  **Verify Accounting**:
    - Open the resulting **Payment Entry**. The amount should be the *Gross* amount.
    - Check the **Journal Entry** list.
    - There should be a new **Journal Entry** linked to this specific transaction for the fee amount.

---

## Test Scenario 4: Applying Advance to a Sales Invoice
**Goal**: Verify that the payment link is easily applied to the final bill.

1.  **Create Invoice**:
    - Go to **Sales Invoice** > New.
    - Select the **same Customer** used in Test Scenario 1.
2.  **Check for Prompt**:
    - Upon selecting the customer, a popup should appear: *"Existing Advances found for this customer. Would you like to apply them?"*
    - Click **Apply**.
3.  **Verify Allocation**:
    - Scroll down to the **Advances** table.
    - Your **Aetas Advance Payment Receipt** should be listed there.
    - The "Grand Total" of the invoice should be reduced by the advance amount.

---

## Troubleshooting for Testers

| Issue | What to check |
| :--- | :--- |
| **Status stays "Unpaid" after payment** | Check **Error Log** list for entries titled "Razorpay Webhook". |
| **No "Apply Advance" popup** | Ensure the **Aetas Advance Payment Receipt** status is exactly "Paid". |
| **Fees are wrong** | Check the **Transaction Fee %** and **Taxes and Charges** table in the Receipt. |
