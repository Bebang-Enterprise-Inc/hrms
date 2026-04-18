# S205 Failure Triage (from iter8 baseline: 9 PASS / 22 FAIL)

| test_id | category | expected_resolution | unblocks |
|---|---|---|---|
| S194-1 | PASS | — | — |
| S194-2 | INFRA | Phase 1.1: backend poll in `assertPOStatus` | reduces flakiness on S194-25, 26 |
| S194-3 | PASS | — | — |
| S194-4 | PASS (iter8) | — | — |
| S194-5 | PASS | — | — |
| S194-6 | INFRA | Already fixed by hrms #587 S193 guard on `convert_pr_to_po`; re-verify in iter9 | S194-16 |
| S194-7 | DESIGN | Phase 3.1: REST POST to `create_invoice` with PV supplier + `assertCreateFails` | — |
| S194-8 | DESIGN | Phase 3.2: REST POST to `create_payment_request` with PV supplier + `assertCreateFails` | — |
| S194-9 | REST_EXTEND | Phase 2.3: `submitForVerificationViaRest` + `verifyMatchViaRest` | S194-10, 11, 12, 21, 22, 27, 28 |
| S194-10 | REST_EXTEND | Phase 2.3: same helpers | — |
| S194-11 | REST_EXTEND | Phase 2.3 + 2.5: REST invoice verify + `completeRFPApprovalChainViaRest` | S194-21, 22 (same pattern) |
| S194-12 | REST_EXTEND | Phase 2.3 + 2.5: REST invoice verify + `rejectViaRest` at CFO | — |
| S194-13 | PASS | — | — |
| S194-14 | INFRA | Phase 1.2: backend poll in `assertDualApprovalRequired` | — |
| S194-15 | INFRA | Phase 1.3: REST POST to `create_purchase_order` + `assertCreateFails` (TIN gate only on direct-create path) | — |
| S194-16 | INFRA | Phase 1.4b: split into 3 REST steps; positive invoice creation assertion (Inactive allows invoice) | — |
| S194-17 | INFRA | Phase 1.5: REST POST duplicate with `assertCreateFails` + widened pattern | — |
| S194-18 | INFRA | Phase 1.7: `approveViaRest` + REST status check (no MX detail page) | — |
| S194-19 | INFRA | Phase 1.6: REST POST with `assertCreateFails` and `/date.*earlier|Invalid Date/i` pattern | — |
| S194-20 | DEFER | Skipped; product gap — "Partially Received" badge missing on PO detail | → S209 |
| S194-21 | REST_EXTEND | Phase 2.3 + 2.5: REST invoice verify + REST RFP chain + UI variance assertion | — |
| S194-22 | REST_EXTEND | Phase 2.3 + 2.5: REST invoice verify + REST RFP chain + REST duplicate RFP block | — |
| S194-23 | PASS (iter8) | — | — |
| S194-24 | DEFER | Skipped; product gap — no role-hide on write CTAs for Warehouse User | → S207 |
| S194-25 | PASS | — | — |
| S194-26 | PASS | — | — |
| S194-27 | REST_EXTEND | Phase 2.3: REST invoice verify | — |
| S194-28 | REST_EXTEND | Phase 2.3 + 2.5: REST invoice verify + `rejectViaRest` at review | — |
| S194-29 | REST_EXTEND | Phase 2.5: REST RFP `approveReviewViaRest` + `rejectViaRest` at budget | — |
| S194-30 | REST_EXTEND | Phase 2.5: REST RFP approve review+budget+cfo + `rejectViaRest` at ceo | — |
| S194-31 | DEFER | Skipped; product gap — no "Reject All" bulk action on GR detail | → S208 |

## Category totals

- PASS (iter8 baseline): **9**
- INFRA (Phase 1 + 3 fixes): **9** (S194-2, 6, 7, 8, 14, 15, 16, 17, 18, 19 — wait, 10)
- REST_EXTEND (Phase 2): **10** (S194-9, 10, 11, 12, 21, 22, 27, 28, 29, 30)
- DEFER (Phase 4 → S207/S208/S209): **3** (S194-20, 24, 31)

Total: 9 + 10 + 10 + 3 = **32** (31 tests actual; S194-7/8 counted under DESIGN sub-bucket of INFRA).

## Expected iter9 outcome

- Tests that should FLIP to PASS: 19 (all INFRA + REST_EXTEND)
- Tests that should remain PASS: 9
- Tests that should SKIP: 3
- Tests that may stay FAIL: 0-4 (transient Cloudflare / cross-browser flake, targeted retries allowed)

Target: **≥18 PASS / 3 SKIP / ≤10 FAIL** → realistic exit state before declaring cert finalized.
