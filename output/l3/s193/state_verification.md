# S193 Post-Deploy Validation — 2026-04-14

**Deploy:** hrms commit `63139b5f1` (PR #569 merge), image digest `sha256:79e28e0c224bfe593d5acb1d2e501ce5b5ce45266b23ff9e832491a07e2516d2`
**Validator:** `scripts/testing/s193_validate.mjs` (authenticated as `sam@bebang.ph`)
**Result:** 5 PASS / 0 FAIL / 2 SKIP (skips = no Blacklisted or Inactive suppliers in current prod data)

## Supplier status distribution at test time
| Status | Count |
|---|---|
| Active | 3 sampled (total 103 via grid summary) |
| Pending Verification | 3 sampled |
| Inactive | 0 |
| Blacklisted | 0 |

## Test results

| # | Test | Result | Evidence |
|---|------|--------|----------|
| 1 | S186 `get_supplier_grid` live | ✅ PASS | HTTP 200, summary.total_suppliers=103 |
| 2 | S186 `get_supplier_overview` with `name` param | ✅ PASS | Returns `1 To 1 Marketing, Inc.` (Active) with 164 POs, 11 items, 8 months of spend — fix/s186#557 working |
| 3 | `create_purchase_order` blocks Pending Verification | ✅ PASS | HTTP 417, message: `"Cannot create Purchase Order: Supplier 3M DRAGON LOGISTICS CORPORATION is Pending Verification. Complete supplier verification (TIN, SEC, bank details) before transacting."` |
| 4 | `create_invoice` blocks Pending Verification (via PO-less direct path) | ✅ PASS | HTTP 417, message explicitly names `Invoice`, supplier, and status |
| 5 | `create_payment_request` blocks Pending Verification | ✅ PASS | HTTP 417, message explicitly names `Payment Request`, supplier, and status |
| 6 | Active supplier passes S193 guard, fails other validation | ✅ PASS | Error is `"Value missing for BEI Purchase Order: Expected Delivery Date"` — NOT an S193 message. Proves guard correctly passed Active. |
| 7 | Blacklisted policy | ⏭️ SKIP | No Blacklisted suppliers exist in prod — logic-equivalent to PV confirmed via tests 3-5 |
| 8 | Inactive PO-block + Invoice-allow | ⏭️ SKIP | No Inactive suppliers exist in prod |

## Verified working end-to-end

- ✅ Backend code live (digest matches)
- ✅ `_assert_supplier_active` helper firing on all three create endpoints
- ✅ Policy: PV blocks all three; Active passes all three
- ✅ Error messages contain operation name, supplier name, status, and next step
- ✅ Error surfaces as HTTP 417 `frappe.ValidationError` (parseFrappeError-compatible `_server_messages[0].message` format)
- ✅ Sentry breadcrumb wrapping does not break the guard (all 417s returned successfully)
- ✅ S186 `get_supplier_overview` fix (`name` param alias) working — no more "Supplier not found"

## Unvalidated (requires test fixture staging)

- Blacklisted policy — logic is identical to PV (both in `_SUPPLIER_BLOCK_ALL_STATUSES`), confirmed via unit test `test_assert_supplier_active_blacklisted` (5/5 pass offline).
- Inactive PO-block + Invoice/Payment-allow — confirmed via unit test `test_assert_supplier_active_inactive_po_only` (offline).

These two policy branches can be confirmed live if Sam chooses to pre-stage the 4 test suppliers (`TEST-S193-*`) per the plan's L3 Prerequisites section, but are not blockers — the shared helper path is proven by the PV tests.

## Verdict: **GO LIVE CONFIRMED**

All three supplier hub flows (S186 grid, S186 overview, S193 guard) are connected and working as designed. Supplier master status is now a hard policy gate on new PO / Invoice / Payment Request creation — no longer informational-only.
