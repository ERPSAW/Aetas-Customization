# Master Phased Implementation Plan (BRD-Complete, AI-Run Ready)

## Objective
Provide a single, BRD-independent execution document for phased delivery of Razorpay integration with partial payments, scoped only to payments and aetas_customization.

## Scope Boundaries
- In scope:
  - payments
  - aetas_customization
- Out of scope:
  - frappe core
  - erpnext core

## BRD Source Summary
This plan fully captures the text BRD requirements for:
1. Boutique-wise Razorpay credentials and auto-selection.
2. Payment link generation from Advance Payment Receipt and Sales Invoice.
3. Partial and multiple payment handling.
4. Webhook-driven success and failure handling.
5. Automated Payment Entry and optional Journal Voucher accounting.
6. Advance adjustment prompt during invoicing.
7. Payment link expiry, one-time reuse policy, and payment mode controls.
8. Customer notifications.
9. APR Payment Details child table populated per successful payment.
10. Linking APR payment rows to Sales Invoices.
11. Auto-populating SI Advance child table from APR payment history.

## Requirement ID Convention
- Payments requirements: PAY-REQ-###
- Aetas requirements: AET-REQ-###
- Cross-app requirements: XAPP-REQ-###
- Test cases: TEST-###

## Requirement Catalog

### Configuration and Security
1. PAY-REQ-001: Maintain Razorpay API Key and Secret per Boutique/Main Office.
  - Acceptance: System stores credentials securely and associates them with Boutique/Main Office context.
2. PAY-REQ-002: Auto-select Razorpay credentials based on Boutique/Main Office.
  - Acceptance: Payment link generation always uses correct boutique-mapped credentials.

### Advance Payment Receipt Payment Links
3. AET-REQ-001: Generate payment link from Advance Payment Receipt.
  - Acceptance: User action on APR generates valid Razorpay payment link.
4. AET-REQ-002: Support full and partial amount link generation from APR.
  - Acceptance: Link amount can be full outstanding or partial user-entered amount.
5. AET-REQ-003: Validate payment-link amount is greater than zero and less than or equal to outstanding.
  - Acceptance: Invalid amounts are blocked with actionable errors.

### Payment Modes and Link Controls
6. PAY-REQ-003: Allow only Credit Card, Debit Card, Net Banking, UPI for this flow.
  - Acceptance: Generated link payload enforces allowed methods.
7. PAY-REQ-004: Payment link expiry is configurable.
  - Acceptance: Expiry can be set and is visible in link metadata.
8. PAY-REQ-005: Payment link is one-time use.
  - Acceptance: Reuse after successful payment is blocked.
9. PAY-REQ-006: Multiple links allowed until outstanding equals zero.
  - Acceptance: Additional links can be created while outstanding remains positive.

### Payment Processing and Status Updates
10. XAPP-REQ-001: On successful Razorpay webhook, auto-create Payment Entry.
  - Acceptance: One successful payment event produces one Payment Entry, and one APR Payment Detail child row is inserted on the source APR document (see AET-REQ-005).
11. XAPP-REQ-002: Link Payment Entry to source document (APR or Sales Invoice flow context).
  - Acceptance: Backlink exists and is queryable from source document.
12. XAPP-REQ-003: Update paid and outstanding amounts after each payment.
  - Acceptance: Paid/outstanding values are consistent after each success event.
13. XAPP-REQ-004: Maintain status states Unpaid, Partially Paid, Paid using amount-based rules.
  - Acceptance: Status transitions match paid vs total.
14. XAPP-REQ-005: Send customer success notification email when email exists.
  - Acceptance: Notification event logged for each successful payment.
15. XAPP-REQ-006: On payment failure, mark status Failed with no financial posting.
  - Acceptance: Failed status updates occur and no Payment Entry/JV is created.
16. XAPP-REQ-007: Send failure notification to customer.
  - Acceptance: Failure communication is attempted and logged.

### Sales Invoice Flow
17. PAY-REQ-007: Generate payment link from Sales Invoice for full or partial amount.
  - Acceptance: Link can be generated from invoice with amount validation.
18. PAY-REQ-008: Allow multiple invoice links until invoice is fully paid.
  - Acceptance: Additional links blocked only when outstanding equals zero.
19. AET-REQ-004: Prompt user to adjust available customer advance during Sales Invoice creation.
  - Acceptance: Prompt shows available advance and options: full adjust, partial adjust, skip.
  - Note: Two sub-flows exist — (a) prompt shown on invoice creation when advance is available; (b) auto-populate from APR payment history when opening an existing SI (covered by AET-REQ-007).
20. AET-REQ-005: Maintain APR Payment Details child table.
  - Acceptance: After each successful payment webhook, one child row is inserted on the source APR with Payment Entry name, amount paid, and SI field left blank. Total row count equals number of successful payments for that APR.
21. AET-REQ-006: "Link Payment to SI" action on APR.
  - Acceptance: User selects a payment row in the APR Payment Details child table, chooses a target Sales Invoice, and the system sets the SI field on that row and creates one corresponding entry in the SI Advance child table. Blocked with a validation error if the selected row already has an SI linked.
22. AET-REQ-007: Auto-populate SI Advance child table when opening an existing Sales Invoice.
  - Acceptance: When a user opens (not creates) a Sales Invoice, the system fetches all APR Payment Detail rows for the same customer where the SI field is blank and adds them to the SI Advance child table without creating duplicates.

### Partial and Multiple Payments (Core)
20. XAPP-REQ-008: Partial payment amount must be greater than zero.
  - Acceptance: Zero/negative amounts rejected.
21. XAPP-REQ-009: Partial payment amount must not exceed outstanding.
  - Acceptance: Overpayments blocked.
22. XAPP-REQ-010: Support multiple partial payments and multiple links per document.
  - Acceptance: System handles repeated cycle until outstanding reaches zero.
23. XAPP-REQ-011: Each successful payment creates separate Payment Entry.
  - Acceptance: No aggregation into a single Payment Entry.
24. XAPP-REQ-012: Notify customer on each payment success.
  - Acceptance: Notification event per successful transaction.

### Razorpay Charges Accounting
25. PAY-REQ-009: Calculate Razorpay charges per transaction (including partial payments).
  - Acceptance: Charges computed transaction-wise.
26. PAY-REQ-010: Accounting Option A supported in Payment Entry:
  - Acceptance: Bank (Net) Dr, Razorpay Charges Dr, Customer Cr.
27. PAY-REQ-011: Accounting Option B supported as automatic Journal Voucher per transaction.
  - Acceptance: JV auto-created when Option B is configured.

## Data and Status Rules
1. Status rules:
  - Unpaid: paid equals 0
  - Partially Paid: paid is greater than 0 and less than total
  - Paid: paid equals total
  - Failed: last payment attempt failed without financial impact
2. Financial integrity:
  - No overpayment beyond outstanding.
  - One successful payment event maps to one Payment Entry.
3. Link lifecycle:
  - Expiry honored.
  - One-time use after success.
  - Multiple links allowed while outstanding greater than zero.

## Ownership Matrix
1. payments owned:
  - PAY-REQ-001, PAY-REQ-002, PAY-REQ-003, PAY-REQ-004, PAY-REQ-005, PAY-REQ-006, PAY-REQ-007, PAY-REQ-008, PAY-REQ-009, PAY-REQ-010, PAY-REQ-011
2. aetas_customization owned:
  - AET-REQ-001, AET-REQ-002, AET-REQ-003, AET-REQ-004, AET-REQ-005, AET-REQ-006, AET-REQ-007
3. cross-app collaboration:
  - XAPP-REQ-001 through XAPP-REQ-012 (XAPP-REQ-001 amended to include APR Payment Detail row insertion)

## Phased Implementation Plan

### Phase 1: Foundation and Validation Hardening
#### Objective
Stabilize APR and Payment Entry synchronization for deterministic downstream payment automation.

#### In Scope
- aetas_customization APR validations and status flow hooks.

#### Primary Tasks
1. Enforce APR validations for amount and status integrity.
2. Ensure Payment Entry submit and cancel keep APR status consistent.
3. Ensure query filters only valid outstanding APR records.

#### Exit Criteria
1. Submit marks APR as Received and links Payment Entry.
2. Cancel reverts APR to To Be Received and clears backlink.
3. Validation rejects invalid amounts.

#### Functional Validations
| # | Scenario | Expected Result | Pass Condition | Test ID |
|---|----------|-----------------|----------------|---------|
| 1 | Save APR with paid_amount = 0 | Blocked with validation error | frappe.ValidationError raised | TEST-001 |
| 2 | Save APR with paid_amount < 0 | Blocked with validation error | frappe.ValidationError raised | TEST-001 |
| 3 | Save APR with no customer set | Blocked with validation error | frappe.ValidationError raised | TEST-001 |
| 4 | Save APR with status Received and no payment_entry | Blocked with validation error | frappe.ValidationError raised | TEST-001 |
| 5 | Submit Payment Entry linked to APR | APR status → Received, backlink set | APR.status == "Received" and APR.payment_entry == PE.name | TEST-002 |
| 6 | Cancel submitted Payment Entry | APR status → To Be Received, backlink cleared | APR.status == "To Be Received" and not APR.payment_entry | TEST-002 |
| 7 | Query for outstanding APR without customer filter | Returns empty or raises graceful error (no crash) | No unhandled exception | TEST-001 |

### Phase 2: Boutique Configuration and Razorpay Selection
#### Objective
Enable boutique-wise credentials and deterministic credential selection.

#### In Scope
- payments Razorpay settings and credential resolution path.

#### Primary Tasks
1. Add or finalize boutique credential mapping model.
2. Resolve credentials per document boutique context.
3. Prevent payment link creation if mapping missing.

#### Exit Criteria
1. Correct key/secret selected for each boutique.  
2. Misconfigured boutique fails with user-facing validation message.

#### Functional Validations
| # | Scenario | Expected Result | Pass Condition | Test ID |
|---|----------|-----------------|----------------|---------|
| 1 | Boutique A and Boutique B each have distinct credentials saved | Each credential set retrieved by boutique name lookup | Resolved key/secret matches boutique record | TEST-003 |
| 2 | Two boutiques with different credentials — request link for each | Each request resolves its own key/secret, not the other | key_a != key_b in resolved payloads | TEST-003 |
| 3 | Boutique with missing Razorpay key | Link generation blocked, user-facing error returned | frappe.ValidationError or equivalent raised before API call | TEST-003 |
| 4 | Boutique with missing Razorpay secret | Link generation blocked, user-facing error returned | No external HTTP request sent | TEST-003 |
| 5 | No boutique field set on source document | Falls back to default/main office credentials or raises clear error | Behaviour is deterministic and documented | TEST-003 |

### Phase 3: Payment Link Generation Controls
#### Objective
Implement link generation for APR and Sales Invoice with amount/mode/expiry controls.

#### In Scope
- payments link generation logic.
- aetas_customization APR action to request links.

#### Primary Tasks
1. Link generation endpoints for APR and Sales Invoice. Applies whether the document is newly created or opened from the list.
2. Enforce amount rules and allowed payment modes.
3. Enforce configurable expiry and one-time-use semantics.
4. Allow multiple links until outstanding equals zero.
5. Add `link_expiry_hours` (Int, default 24) to Razorpay Settings doctype.
6. Add `create_payment_link()` instance method to `RazorpaySettings` — calls `/v1/payment_links`, enforces allowed modes (Card Credit/Debit, Net Banking, UPI), sets `accept_partial=False` and `expire_by`.
7. Create `Aetas Razorpay Payment Link` doctype (autoname `ARPL-.#####`) as audit-trail tracker per generated link.
8. Add `Sales Invoice-custom_boutique` (Link→Boutique) custom field via fixtures.

#### Exit Criteria
1. Valid links generated for full and partial amounts.
2. Invalid amounts and blocked modes rejected.
3. Link controls applied consistently.
4. Each generated link produces one `Aetas Razorpay Payment Link` tracker record.
5. `bench migrate` completes cleanly after schema additions.

#### Functional Validations
| # | Scenario | Expected Result | Pass Condition | Test ID |
|---|----------|-----------------|----------------|---------|
| 1 | Generate link from APR for full outstanding amount | Valid Razorpay link returned | Link URL present, amount == outstanding | TEST-004 |
| 2 | Generate link from APR for valid partial amount (0 < amount < outstanding) | Valid Razorpay link returned | Link URL present, amount == requested partial | TEST-004 |
| 3 | Generate link from Sales Invoice for full invoice amount | Valid link returned | Link URL present, amount == invoice total | TEST-004 |
| 4 | Generate link from Sales Invoice for valid partial amount | Valid link returned | Link URL present, amount == requested partial | TEST-004 |
| 5 | Request link with amount = 0 | Blocked | frappe.ValidationError raised before API call | TEST-001, TEST-004 |
| 6 | Request link with amount > outstanding | Blocked | frappe.ValidationError raised before API call | TEST-001, TEST-004 |
| 7 | Inspect generated link payload | Only Credit Card, Debit Card, Net Banking, UPI present | No disallowed methods in payload | TEST-005 |
| 8 | Inspect generated link expiry | Expiry timestamp matches configured value | expiry_time == now + configured_offset | TEST-005 |
| 9 | Use same link after successful payment | Reuse blocked | Razorpay returns expired/used status, system handles gracefully | TEST-005 |
| 10 | Generate additional link while outstanding > 0 | Link created successfully | New link URL returned | TEST-006 |
| 11 | Attempt link generation when outstanding == 0 | Blocked | frappe.ValidationError raised | TEST-006 |

### Phase 4: Webhook Processing and Financial Posting
#### Objective
Complete success/failure event processing with automatic accounting artifacts.

#### In Scope
- payments webhook handlers and posting logic.
- cross-linking back to APR or Sales Invoice context.

#### Primary Tasks
1. On success: create Payment Entry per transaction.
2. Update paid/outstanding and status rules.
3. On failure: mark Failed without financial impact.
4. Send success/failure notifications where email exists.
5. After creating Payment Entry, insert one APR Payment Detail child row on the source APR (Payment Entry name, amount, SI field blank).

#### Exit Criteria
1. One success event produces one Payment Entry.
2. Failure produces no posting.
3. Status and outstanding values match transaction ledger.
4. APR Payment Details child table has exactly one row per successful payment; no row added on failure or duplicate webhook.

#### Functional Validations
| # | Scenario | Expected Result | Pass Condition | Test ID |
|---|----------|-----------------|----------------|---------|
| 1 | Simulate success webhook for a full payment | Exactly one Payment Entry created | count(PE where source == doc.name) == 1 | TEST-007 |
| 2 | Simulate success webhook for a partial payment | One Payment Entry with partial amount, APR status → Partially Paid | PE.paid_amount == webhook.amount, APR.status == "Partially Paid" | TEST-007 |
| 3 | Replay the same success webhook (duplicate) | No duplicate Payment Entry created | count(PE) unchanged after replay | TEST-007 |
| 4 | Simulate failure webhook | Status → Failed, no Payment Entry or JV created | APR.status == "Failed", count(PE) == 0 | TEST-008 |
| 5 | Simulate second partial payment after first success | Second Payment Entry created, outstanding decremented | outstanding == total - sum(paid_amounts) | TEST-007 |
| 6 | Final partial payment brings outstanding to zero | Status → Paid | APR.status == "Paid" and outstanding == 0 | TEST-007 |
| 7 | Success webhook for customer with email| Success notification event logged | Notification record or email log entry exists | TEST-009 |
| 8 | Failure webhook for customer with email | Failure notification event logged | Notification record or email log entry exists | TEST-009 |
| 9 | Success webhook for customer without email | No notification error raised | Process completes without exception | TEST-009 |
| 10 | Successful webhook: APR Payment Detail row inserted | One child row with correct PE name and amount | child_table.count == payments_count, row.payment_entry == PE.name | TEST-014 |
| 11 | Replay duplicate successful webhook | No second child row inserted | APR Payment Details row count unchanged | TEST-014 |
| 12 | Failure webhook received | No APR Payment Detail row inserted | child_table.count unchanged | TEST-014 |

### Phase 5: Advance Adjustment Prompt in Sales Invoice
#### Objective
Provide user choice for full, partial, or skipped advance adjustment during invoice creation, and auto-populate SI Advance child table from APR payment history when opening an existing invoice.

#### In Scope
- aetas_customization invoice prompt behavior and adjustment actions.
- aetas_customization Sales Invoice override: "Get Advances Received" on document open.

#### Primary Tasks
##### Sub-flow A: Advance adjustment prompt on SI creation
1. Detect customer advance at invoice creation.
2. Render prompt with amount and three options.
3. Apply selected adjustment deterministically.
##### Sub-flow B: Auto-populate SI Advance child table on opening existing SI
4. On Sales Invoice `onload`/`refresh`, fetch all APR Payment Detail rows for the same customer where SI field is blank.
5. Add each fetched row to the SI Advance child table, skipping rows already present (by Payment Entry reference) to prevent duplicates.

#### Exit Criteria
1. Prompt appears only when advance is available on creation.
2. Each prompt option behaves as expected and is auditable.
3. Opening an existing SI automatically populates the SI Advance child table from APR payment history without duplicates.

#### Functional Validations
| # | Scenario | Expected Result | Pass Condition | Test ID |
|---|----------|-----------------|----------------|---------|
| 1 | Create Sales Invoice for customer with advance balance > 0 | Prompt displayed with correct advance amount | prompt.amount == customer_advance_balance | TEST-010 |
| 2 | Create Sales Invoice for customer with no advance | Prompt not displayed | No prompt dialog shown | TEST-010 |
| 3 | Select full adjust | Full eligible advance applied to invoice | adjustment == min(advance_balance, invoice_total) | TEST-010 |
| 4 | Select partial adjust with valid partial amount | Entered amount applied | adjustment == entered_partial_amount | TEST-010 |
| 5 | Select partial adjust with amount > advance balance | Blocked | frappe.ValidationError raised | TEST-010 |
| 6 | Select skip | No adjustment applied, invoice unchanged | invoice.advance_adjustment == 0 | TEST-010 |
| 7 | Verify adjustment is auditable | Adjustment reflected in invoice and linked entry | Journal or allocation entry traceable to invoice | TEST-010 |
| 8 | Open existing SI with same-customer APR payments where SI field is blank | SI Advance child table auto-populated | Rows match APR Payment Detail entries for that customer | TEST-016 |
| 9 | Open SI where APR row already linked to this SI | Existing row not duplicated in SI Advance child table | SI Advance row count unchanged | TEST-016 |
| 10 | Open SI with no matching APR payment rows | SI Advance child table remains empty | No rows added, no error raised | TEST-016 |

### Phase 5b: Link APR Payment to Sales Invoice
#### Objective
Allow users to associate an APR payment row with a Sales Invoice directly from the APR document, completing the payment-to-invoice traceability chain.

#### In Scope
- aetas_customization APR doctype: new action button and backend endpoint.
- aetas_customization Sales Invoice override: write SI Advance child table entry.

#### Primary Tasks
1. Add "Link Payment to SI" action button on the APR Payment Details child table.
2. On action: prompt user to select a target Sales Invoice (same customer).
3. Validate the selected row has an amount > 0 and no SI already linked.
4. Set the SI field on the selected APR Payment Detail row.
5. Write one entry to the target SI Advance child table referencing this Payment Entry.

#### Exit Criteria
1. Selected APR Payment Detail row has its SI field set to the chosen invoice.
2. Target SI Advance child table contains exactly one new entry referencing the Payment Entry.
3. Re-linking an already-linked row is blocked with a validation error.

#### Functional Validations
| # | Scenario | Expected Result | Pass Condition | Test ID |
|---|----------|-----------------|----------------|---------|
| 1 | Link payment row to a valid Sales Invoice | SI field set on row; SI Advance entry created | row.sales_invoice == si_name and si.advances has row | TEST-015 |
| 2 | Link payment row already linked to an SI | Blocked | frappe.ValidationError raised, no change to SI | TEST-015 |
| 3 | Link payment row with amount = 0 | Blocked | frappe.ValidationError raised before any write | TEST-015 |
| 4 | Link payment row to SI for a different customer | Blocked | frappe.ValidationError raised | TEST-015 |
| 5 | Replay linking action for same row and same SI | Idempotent or blocked | SI Advance entry count unchanged | TEST-015 |

### Phase 6: Razorpay Charges Accounting Options
#### Objective
Support transaction-wise charge accounting using configurable posting strategy.

#### In Scope
- payments charge calculation and posting logic.

#### Primary Tasks
1. Compute charges per transaction.
2. Implement Option A posting in Payment Entry.
3. Implement Option B automatic JV creation.
4. Allow configuration to select option.

#### Exit Criteria
1. Charges reflected correctly for full and partial payments.
2. Posting follows configured option without double booking.

#### Functional Validations
| # | Scenario | Expected Result | Pass Condition | Test ID |
|---|----------|-----------------|----------------|---------|
| 1 | Configure Option A; post full payment | Payment Entry has Bank Dr (net), Razorpay Charges Dr, Customer Cr | All three ledger lines present with correct values | TEST-011 |
| 2 | Configure Option A; post partial payment | Same three-line structure with partial amounts | Charge proportional to partial amount | TEST-011 |
| 3 | Configure Option B; post full payment | One JV auto-created with correct Dr/Cr | count(JV for transaction) == 1 | TEST-012 |
| 4 | Configure Option B; post partial payment | One JV with partial charge amount | JV.charge == computed partial charge | TEST-012 |
| 5 | Replay same transaction with Option B active | No duplicate JV created | count(JV for transaction) remains 1 | TEST-012 |
| 6 | Switch option mid-run (A then B for separate transactions) | Each transaction follows its configured option | No cross-contamination of posting strategies | TEST-011, TEST-012 |

### Phase 7: Reconciliation, Reporting, and Production Readiness
#### Objective
Ensure reconciliation integrity and deployment safety.

#### In Scope
- cross-app verification, reporting outputs, operational checks.

#### Primary Tasks
1. Build reconciliation views for payment-to-entry matching.
2. Validate edge cases: duplicate webhooks, retries, partial series.
3. Final UAT, rollback notes, and release checklist.

#### Exit Criteria
1. Finance can reconcile without manual workaround.
2. No orphaned statuses or posting mismatches in test runs.

#### Functional Validations
| # | Scenario | Expected Result | Pass Condition | Test ID |
|---|----------|-----------------|----------------|---------|
| 1 | Run reconciliation across full payment sequence | All Payment Entries match source documents with no gaps | reconciliation_view shows 0 unmatched rows | TEST-013 |
| 2 | Run reconciliation across multiple partial payments | Each partial amount traced to its Payment Entry | sum(PE.paid_amount for doc) == doc.total_paid | TEST-013 |
| 3 | Inject duplicate webhook for an already-processed transaction | No duplicate Payment Entry or JV; idempotency confirmed | count(PE/JV) unchanged | TEST-007, TEST-013 |
| 4 | Simulate webhook retry after transient failure | Transaction processed exactly once on retry | No double posting | TEST-007, TEST-013 |
| 5 | Leave one partial series incomplete (outstanding > 0) | Doc status remains Partially Paid; no orphaned entries | status == "Partially Paid", no dangling Payment Entry | TEST-008, TEST-013 |
| 6 | Execute rollback procedure on staging | All changes reverted cleanly with no data residue | Post-rollback state matches pre-deployment snapshot | TEST-013 |
| 7 | Run full UAT checklist across Phases 1–6 | All TEST-001 through TEST-013 pass | Zero blockers in UAT sign-off matrix | TEST-001 through TEST-013 |

## Requirement to Phase Traceability
1. Phase 1: AET-REQ-003, XAPP-REQ-003, XAPP-REQ-004, XAPP-REQ-008, XAPP-REQ-009
2. Phase 2: PAY-REQ-001, PAY-REQ-002
3. Phase 3: AET-REQ-001, AET-REQ-002, PAY-REQ-003, PAY-REQ-004, PAY-REQ-005, PAY-REQ-006, PAY-REQ-007, PAY-REQ-008
4. Phase 4: XAPP-REQ-001, XAPP-REQ-002, XAPP-REQ-003, XAPP-REQ-004, XAPP-REQ-005, XAPP-REQ-006, XAPP-REQ-007, XAPP-REQ-011, XAPP-REQ-012, AET-REQ-005
5. Phase 5: AET-REQ-004, AET-REQ-007
6. Phase 5b: AET-REQ-006
7. Phase 6: PAY-REQ-009, PAY-REQ-010, PAY-REQ-011
8. Phase 7: Consolidated validation for all requirements

## Verification Matrix
1. TEST-001: APR partial amount validation rejects zero, negative, and above outstanding.
2. TEST-002: Payment Entry submit and cancel maintain APR status consistency.
3. TEST-003: Boutique credential auto-selection uses correct key/secret.
4. TEST-004: APR and Sales Invoice payment links generate for valid full/partial amounts.
5. TEST-005: Link expiry and one-time-use constraints enforced.
6. TEST-006: Multiple links allowed while outstanding greater than zero.
7. TEST-007: Successful webhook creates one Payment Entry and updates status/outstanding.
8. TEST-008: Failed webhook updates failure status without financial posting.
9. TEST-009: Customer notifications sent on success and failure when email exists.
10. TEST-010: Advance adjustment prompt supports full, partial, skip.
11. TEST-011: Charges accounting Option A posts correct Dr/Cr.
12. TEST-012: Charges accounting Option B creates one JV per transaction.
13. TEST-013: Reconciliation report confirms no mismatch for partial/multiple payments.
14. TEST-014: APR Payment Details child table populated with one row per successful payment; no row on failure or duplicate webhook.
15. TEST-015: "Link Payment to SI" sets SI field on APR row and creates SI Advance entry; blocked on re-link, zero amount, or customer mismatch.
16. TEST-016: Opening an existing SI auto-populates SI Advance child table from APR payment history without duplicates.

## Key File Anchors
- payments/payments/payment_gateways/doctype/razorpay_settings/razorpay_settings.py
- payments/payments/payment_gateways/doctype/razorpay_settings/razorpay_settings.json
- payments/payments/templates/pages/razorpay_checkout.py
- payments/payments/public/js/razorpay.js
- aetas_customization/aetas_customization/aetas_customization/doctype/aetas_advance_payment_receipt/aetas_advance_payment_receipt.json
- aetas_customization/aetas_customization/aetas_customization/doctype/aetas_advance_payment_receipt/aetas_advance_payment_receipt.py
- aetas_customization/aetas_customization/aetas_customization/doctype/aetas_advance_payment_receipt/aetas_advance_payment_receipt.js
- aetas_customization/aetas_customization/aetas_customization/doctype/aetas_razorpay_payment_link/aetas_razorpay_payment_link.json
- aetas_customization/aetas_customization/aetas_customization/doctype/aetas_razorpay_payment_link/aetas_razorpay_payment_link.py
- aetas_customization/aetas_customization/aetas_customization/doctype/aetas_apr_payment_detail/aetas_apr_payment_detail.json
- aetas_customization/aetas_customization/aetas_customization/doctype/aetas_apr_payment_detail/aetas_apr_payment_detail.py
- aetas_customization/aetas_customization/aetas_customization/overrides/payment_entry.py
- aetas_customization/aetas_customization/aetas_customization/overrides/sales_invoice.py
- aetas_customization/aetas_customization/fixtures/custom_field.json

## AI Execution Template (Per Phase)
Use this template to create a child implementation plan for each phase.

1. Phase Name:
2. Requirements in Scope:
3. Files Allowed to Modify:
4. Implementation Steps:
5. Validation Commands and Tests:
6. Exit Criteria:
7. Rollback Steps:
8. Risks and Mitigations:

## Handoff Checklist
1. Confirm branch names for payments and aetas_customization.
2. Generate child plan for Phase 2 next, since Phase 1 foundations already started.
3. Keep each phase in separate commit set for safer rollback.
4. Run verification tests listed for the active phase before moving ahead.
5. Do not modify frappe or erpnext repositories.
