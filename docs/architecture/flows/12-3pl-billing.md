# Flow 12: 3PL Billing Cycle
**Departments:** Logistics (trip tracking) → Finance (billing statement) → Store (SOA) | **Scanned:** 2026-02-23 | **Agent:** flow-tracer-4

## Flow Diagram (Mermaid)

```mermaid
sequenceDiagram
    participant LOG as Logistics (BEI Trip Ops)
    participant DT_T as BEI Distribution Trip (docstatus=1)
    participant FIN as Finance (my.bebang.ph)
    participant WH as /dashboard/warehouse/billing/3pl-reconciliation
    participant HK as hooks/use-warehouse.ts
    participant RECON as generate_3pl_reconciliation()
    participant RATE as BEI 3PL Rate
    participant PAY as create_3pl_payment_request()
    participant JE as Journal Entry (Frappe)
    participant FLAG as flag_discrepancy()
    participant DT_B as BEI Billing Schedule (per-trip)
    participant SOA as soa.py / BEI Statement of Account
    participant STORE as Store (SOA recipient)
    Note over DT_B,STORE: BROKEN: BEI Billing Schedule Delivery type is not auto-created from trips
    Note over SOA,STORE: BROKEN: No frontend for SOA generation or viewing

    LOG->>DT_T: Create + submit BEI Distribution Trip (vehicle_owner=partner, cargo_type, route/zone)
    DT_T-->>FIN: Trips accumulate month-end

    FIN->>WH: Opens /dashboard/warehouse/billing/3pl-reconciliation
    WH->>HK: useReconciliationSummary(month, year)
    HK->>RECON: hrms.api.billing.get_reconciliation_summary()
    RECON->>RECON: generate_3pl_reconciliation() per partner [N+1 loop]
    RECON->>RATE: Match trips to BEI 3PL Rate by (zone, cargo_type)
    RECON-->>WH: {partners: [{trip_count, expected_cost, invoice_amount, variance_pct}]}

    FIN->>WH: Clicks partner row → DrillPanel opens
    WH->>HK: use3PLReconciliation(month, year, partner)
    HK->>RECON: generate_3pl_reconciliation() again for trip-level detail
    RECON-->>WH: trip_lines with EWT calculation

    FIN->>WH: Flags discrepancy on a trip
    WH->>FLAG: hrms.api.billing.flag_discrepancy()
    FLAG->>DT_T: Adds Comment to BEI Distribution Trip; sets discrepancy fields

    FIN->>WH: Clicks "Pay" on partner row → PaymentDialog opens
    WH->>PAY: hrms.api.billing.create_3pl_payment_request(month, year, partner, invoice_amount)
    PAY->>RATE: Fetches EWT rate from BEI 3PL Rate
    PAY->>JE: DR Logistics Cost, CR AP-Trade (net, with party), CR EWT Payable
    JE-->>FIN: Journal Entry name returned
    FIN->>FIN: Approval in Frappe workflow (separate)

    Note over DT_B,STORE: Delivery BEI Billing Schedule = separate per-trip billing for stores
    Note over DT_B,STORE: No automated creation of per-trip BEI Billing Schedule from trip completion
    Note over SOA,STORE: SOA backend (soa.py) fully built; NO frontend pages exist
    FIN->>SOA: generate_soa() [Frappe Desk only]
    SOA->>DT_B: Aggregates Monthly Fees + Delivery BEI Billing Schedule by period
    SOA->>STORE: send_soa_to_store() → email (Full Franchise only)
```

## Step-by-Step Trace

| Step | Actor | Action | Frontend Page | API Endpoint | DocType Created/Updated | Status |
|------|-------|--------|---------------|--------------|------------------------|--------|
| 1 | Logistics | Creates and submits distribution trips throughout the month | Frappe Desk (or separate logistics module) | Frappe native / `BEI Distribution Trip` controller | BEI Distribution Trip (docstatus=1, vehicle_owner=3PL partner) | LIVE (DocType exists) |
| 2 | Finance | Navigates to 3PL reconciliation page | `/dashboard/warehouse/billing/3pl-reconciliation/page.tsx` | — | — | LIVE |
| 3 | Finance | Views monthly summary across all 4 partners (RCS, 3MD, COOLITZ, PINNACLE) | `/dashboard/warehouse/billing/3pl-reconciliation` | `hrms.api.billing.get_reconciliation_summary(month, year)` | BEI Distribution Trip + BEI 3PL Rate (read) | LIVE |
| 4 | Backend | For each partner: counts trips, calls `generate_3pl_reconciliation()` internally, matches trips to rates by (zone, cargo_type) with cascade fallback | `billing.py:957–998` | `generate_3pl_reconciliation()` (internal) | BEI Distribution Trip + BEI 3PL Rate (read) | LIVE — **N+1: calls `generate_3pl_reconciliation` per partner in Python loop** |
| 5 | Finance | Clicks partner row to drill into trip-level detail | `/dashboard/warehouse/billing/3pl-reconciliation` | `hrms.api.billing.generate_3pl_reconciliation(month, year, partner)` | BEI Distribution Trip + BEI 3PL Rate (read) | LIVE — **duplicate call (step 4 already called this)** |
| 6 | Backend | For each trip: computes base_cost + overtime_cost + surcharge_cost; calculates EWT (default WC110, 1%); marks `has_discrepancy=True` if no rate match found | `billing.py:733–798` | — | — | LIVE |
| 7 | Finance | Flags a specific trip as discrepant | `/dashboard/warehouse/billing/3pl-reconciliation` (FlagDialog) | `hrms.api.billing.flag_discrepancy(trip_name, reason, amount)` | BEI Distribution Trip (Comment added; `billing_discrepancy=1`, `discrepancy_reason`, `discrepancy_amount` set via `db.set_value`) | LIVE |
| 8 | Finance | Opens payment dialog for a partner | `/dashboard/warehouse/billing/3pl-reconciliation` (PaymentDialog) | `hrms.api.billing.get_3pl_rates(partner)` (via `use3PLRates`) | BEI 3PL Rate (read; EWT rate fetched) | LIVE |
| 9 | Finance | Enters gross invoice amount, reviews EWT breakdown | PaymentDialog (client state) | — | — | LIVE |
| 10 | Finance | Clicks "Create Journal Entry" | PaymentDialog | `hrms.api.billing.create_3pl_payment_request(month, year, partner, invoice_amount)` | Journal Entry: DR Logistics Cost, CR AP-Trade (net), CR EWT Payable | LIVE |
| 11 | Backend | Validates EWT rate within 0.5–15% range; creates JE with `cheque_no = "3PL-{partner}-{YYYY-MM}"` for idempotency tracking | `billing.py:876–916` | — | Journal Entry (submitted) | LIVE |
| 12 | Finance | Views reconciliation summary with invoice_amount now populated (from JE `total_debit` by cheque_no) | `/dashboard/warehouse/billing/3pl-reconciliation` | `get_reconciliation_summary()` again | Journal Entry (read by cheque_no pattern) | LIVE |
| 13 | Finance | Manages delivery rate schedule | `/dashboard/billing/rates/page.tsx` | `billing.get_delivery_rates`, `set_delivery_rate`, `submit_rate_for_review`, `approve_rate` | BEI Delivery Rate (Draft→Pending Review→Active) | LIVE |
| 14 | Finance | Generates monthly franchise billing (auto or manual) | Scheduled cron / Frappe Desk trigger | `billing.generate_monthly_billing(billing_period)` | BEI Billing Schedule (billing_type=Monthly Fees) | LIVE — no frontend trigger button; cron only |
| 15 | Finance | Approves pending billings | `/dashboard/billing/approval/page.tsx` | `billing.get_pending_billings`, `billing.approve_billing` | BEI Billing Schedule (Pending→Approved) | LIVE |
| 16 | Finance | Sends approved billing to store | `/dashboard/billing/page.tsx` (action) | `billing.send_billing_to_store` | BEI Billing Schedule (Approved→Sent); email sent for Full Franchise | LIVE |
| 17 | Store | Views billing detail and records payment | `/dashboard/billing/my-billings/[id]/page.tsx` | `billing.get_billing_detail`, `billing.record_payment` | BEI Billing Schedule (amount_paid, balance_due, auto→Paid) | LIVE |
| 18 | Finance | Generates Statement of Account for store | **Frappe Desk only** | `hrms.api.soa.generate_soa(store, period)` | BEI Statement of Account (aggregates Monthly Fees + Delivery billings) | LIVE — **NO frontend page** |
| 19 | Finance | Sends SOA to store | **Frappe Desk only** | `hrms.api.soa.send_soa_to_store(soa_name)` | BEI Statement of Account (status=Sent); email sent for Full Franchise | LIVE — **NO frontend page** |
| 20 | Store | Receives SOA via email | Email (Full Franchise only) | — | — | LIVE for Full Franchise; internal stores just marked Sent |

## Handoff Points

| From Dept | To Dept | Trigger | Mechanism | Status |
|-----------|---------|---------|-----------|--------|
| Logistics → Finance | Finance (3PL recon) | End of month: trips accumulated | Finance opens 3PL reconciliation page; pulls trips via `generate_3pl_reconciliation` | LIVE — **manual trigger; no auto-alert when month closes** |
| Finance (reconciliation) → Finance (payment JV) | Within Finance | Rate match confirms expected cost; invoice amount entered | `create_3pl_payment_request()` creates JE; cheque_no links JE to period for summary reconciliation | LIVE |
| Finance (JV) → AP workflow | Frappe native AP | Journal Entry submitted | JE enters Frappe approval workflow (posting/accounting); not tracked in BEI billing layer | LIVE (Frappe native) — **not surfaced in my.bebang.ph** |
| Finance (billing) → Store | Store sees billing | `send_billing_to_store` called | Email (Full Franchise) or status=Sent (internal) | LIVE — email only; no in-app notification to Store |
| Finance (SOA generation) → Store | Store receives monthly statement | `send_soa_to_store` called | Email to `department_email` (Full Franchise) or mark Sent (internal) | LIVE — **Finance has no app page to trigger this** |
| Per-trip delivery → BEI Billing Schedule | Finance creating delivery billing | **Not automated** — per-trip `BEI Billing Schedule (billing_type=Delivery)` must be manually created | No automated creation from `BEI Distribution Trip` completion | **BROKEN — manual only** |

## Broken Links / Gaps

| ID | Location | Problem | Impact | Severity |
|----|----------|---------|--------|----------|
| BL-12-01 | `soa.py` + `hrms/api/soa.py` | 3 complete SOA endpoints (`generate_soa`, `get_soa_list`, `send_soa_to_store`) have zero frontend pages. Finance cannot generate, list, or send SOA from my.bebang.ph. | Finance must use Frappe Desk for the final step of the billing cycle. Stores receive no consolidated monthly statement from the app. | HIGH |
| BL-12-02 | Per-trip delivery billing automation | `BEI Billing Schedule` supports `billing_type="Delivery"` with `trip_reference` field and is aggregated by `generate_soa`. But no code auto-creates a `BEI Billing Schedule` record when a `BEI Distribution Trip` is submitted. Delivery billings must be created manually or via Frappe Desk. | Delivery billing line items may be missing from SOAs if not manually created. Finance has to reconcile trips to billing manually. | HIGH |
| BL-12-03 | `get_reconciliation_summary` (billing.py:957–998) | For each of 4 partners, `generate_3pl_reconciliation()` is called in a Python loop (lines 981–982). Each `generate_3pl_reconciliation` call runs 2 SQL queries (trips + rates). Total: up to 8 queries, but the trip count batch query (lines 958–964) is already pre-fetched. The redundancy is: `generate_3pl_reconciliation` re-fetches trips+rates data that the summary already counted. For large months (100+ trips) this may cause slow page loads. | Performance degradation on summary page load. For months with many trips per partner, each `generate_3pl_reconciliation` call may time out. | MEDIUM |
| BL-12-04 | `create_3pl_payment_request` — no idempotency guard | `cheque_no = "3PL-{partner}-{YYYY-MM}"` is used to look up the JE in reconciliation summary. But `create_3pl_payment_request` does NOT check if a JE with this `cheque_no` already exists before inserting. | Finance can accidentally create duplicate JEs for the same partner-period. The reconciliation summary will still only surface the first JE (by the cheque_no lookup) but duplicate JEs clutter the GL. | MEDIUM |
| BL-12-05 | `generate_monthly_billing` — no frontend trigger | The scheduled billing runs via cron at 6 AM on 1st of each month (`scheduled_monthly_billing`). There is no "Generate Now" button in the UI for Finance to manually trigger billing outside the schedule or re-run for a specific store. | Finance cannot re-run billing for a corrected period or manually generate for a missed month without Frappe Desk access or SSH. | MEDIUM |
| BL-12-06 | `get_stores_without_rates` uses `BEI Store Type` not `Warehouse` | `get_stores_without_rates` queries `BEI Store Type` for all stores (billing.py:119). However, `BEI Delivery Rate.store` is a Link to `Department`, not a `BEI Store Type`. If the store list in `BEI Store Type` is out of sync with actual stores, rates may appear missing for valid stores or present for decommissioned ones. | Finance sees false "missing rate" alerts or misses actual gaps in rate configuration | MEDIUM |
| BL-12-07 | JE AP row hardcoded account string | `create_3pl_payment_request` (billing.py:896) hardcodes `"2101101 - ACCOUNTS PAYABLE - TRADE - BEI"` and `"2102202 - EWT PAYABLE - BEI"` as string literals. If the company code or account name changes, the JE will fail to post with an "Account not found" error. | GL posting breaks silently on account name change; no config-driven account lookup | LOW |
| BL-12-08 | `flag_discrepancy` — no status gate | `flag_discrepancy` flags any submitted trip, including trips that have already been paid. A trip with a completed JE can still be flagged after payment, creating a confusing audit trail. | Discrepancy flags on paid trips are misleading; no enforcement of flag-before-pay ordering | LOW |
| BL-12-09 | No in-app notification to Store when billing is sent | `send_billing_to_store` sends email for Full Franchise stores and marks internal stores as Sent. No push notification, no Google Chat message, and no in-app badge is shown to the store user. | Store staff do not know billing has arrived unless they check email or log into the billing module | LOW |

## Error Paths

| Trigger | What Happens | User Experience | Status |
|---------|-------------|----------------|--------|
| Trip has no matching rate in `BEI 3PL Rate` | `generate_3pl_reconciliation` marks trip as `has_discrepancy=True`, adds to `discrepancies` list with reason "No matching rate for partner=..., zone=..., cargo_type=..." | Reconciliation table shows red row + "No rate" label; discrepancy callout at bottom of DrillPanel | HANDLED |
| EWT rate on `BEI 3PL Rate` is outside 0.5–15% range | `create_3pl_payment_request` throws `frappe.throw("EWT rate X% is outside valid range")` | PaymentDialog shows error toast from `result.error` | HANDLED |
| Invoice amount is 0 or negative | `create_3pl_payment_request` throws `frappe.throw("Invoice amount must be greater than zero")` | PaymentDialog toast.error | HANDLED |
| `generate_monthly_billing` finds no sales data for a store | Store is skipped (skipped counter incremented); no BEI Billing Schedule created for that store | Return value includes `skipped` count; no user-facing alert for skipped stores | POOR UX — Finance has no way to know which stores were skipped |
| `generate_soa` called when no billings exist for period | Throws `frappe.throw("No billings found for X in period Y")` | Frappe Desk error dialog | HANDLED (Frappe Desk only; no frontend anyway) |
| `send_soa_to_store` when store has no `department_email` | `recipients` list is empty; no email sent; SOA still marked Sent | SOA transitions to Sent status with `emailed=False` in response. No warning that email was not sent. | POOR UX — silent email failure |
| `create_3pl_payment_request` when JE insert fails (validation error) | `frappe.db.rollback(save_point=sp_name)` called; JE creation rolled back; `frappe.throw` re-raised | PaymentDialog shows error toast with backend error message | HANDLED |

## Improvement Suggestions

1. **SOA Frontend (HIGH):** Create `/dashboard/billing/soa/` module with 3 pages: list (using `get_soa_list`), generate (form for store + period → `generate_soa`), and detail with send button (`send_soa_to_store`). This is the final missing frontend for the complete billing cycle.

2. **Auto-create Delivery Billing from Trip (HIGH):** Add a `doc_events` hook in `hooks.py` for `BEI Distribution Trip.on_submit`: call a function that creates `BEI Billing Schedule (billing_type=Delivery)` for each store in the trip's stop list. This closes the gap between logistics completion and Finance billing.

3. **Manual Billing Trigger (MEDIUM):** Add a "Generate Billing" button in `/dashboard/billing/page.tsx` visible to Finance managers that calls `generate_monthly_billing` with a period picker. Also add a per-store override to regenerate a single store.

4. **Idempotency Guard on JE (MEDIUM):** Add a check at the top of `create_3pl_payment_request`: `frappe.db.exists("Journal Entry", {"cheque_no": f"3PL-{partner}-{period_label}", "docstatus": ["!=", 2]})`. If found, return the existing JE name instead of creating a duplicate.

5. **Reduce N+1 in Summary (MEDIUM):** Refactor `get_reconciliation_summary` to fetch all trips and rates for all partners in 2 queries, then compute the reconciliation in Python — eliminating the per-partner `generate_3pl_reconciliation` call loop. This reduces DB round-trips from 8+ to 2 for a 4-partner summary.

6. **Store Notification on Billing Sent (LOW):** After `send_billing_to_store`, send a Google Chat notification to the store's supervisor (via `send_notification(store_supervisor_email, message)`) so stores know to check billing.

7. **Config-driven GL Accounts (LOW):** Move `"2101101 - ACCOUNTS PAYABLE - TRADE - BEI"` and `"2102202 - EWT PAYABLE - BEI"` to `bei_config.py` constants or a `BEI Finance Settings` DocType. Use these constants in `create_3pl_payment_request` instead of hardcoded strings.

8. **Department email validation (LOW):** In `send_soa_to_store`, if `recipients` is empty after Department lookup, log a warning and return `{"emailed": False, "warning": "No department_email configured for store X"}` so Finance knows the SOA was not emailed.
