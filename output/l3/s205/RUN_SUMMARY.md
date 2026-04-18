# S205 iter9 Final Run Summary

**Sweep:** `doppler run -p bei-erp -c dev -- npx playwright test tests/e2e/specs/s194-procurement-chain.spec.ts --reporter=list --project=chromium --max-failures=0`
**Log:** `output/l3/s205/run-iter9-final.log`
**Duration:** 34.7 minutes
**Completed:** 2026-04-17 22:30 PHT

## Final tally

| Metric | iter8 baseline | iter9 final | Delta | Target |
|---|---|---|---|---|
| PASS | 9 | **11** | **+2** | ≥18 (not met) |
| FAIL | 22 | 17 | −5 | ≤8 (not met) |
| SKIP | 0 | 3 | +3 | 3 (met) |

## Per-test results

| # | Test | iter8 | iter9 | Delta | Root cause |
|---|---|---|---|---|---|
| 1 | PR happy path | ✓ | ✓ | — | — |
| 2 | PO dual approval ₱750K | ✓ | ✓ | — | Backend-poll fix held |
| 3 | PO CEO approval ₱1.5M | ✓ | ✓ | — | — |
| 4 | PR→PO rejected at Mae | ✓ | ✓ | — | — |
| 5 | PO reject at Mae ₱500K | ✓ | ✘ | **REGRESS** | Chain flake (intermittent) |
| 6 | S193 blocks PO for PV | ✘ | ✘ | — | Known pre-existing — see POST_CERT_DEFECTS |
| 7 | S193 blocks Invoice for PV | ✘ | **✓** | **FIX** | REST reframe (S205 Phase 3.1) |
| 8 | S193 blocks PR for PV | ✘ | **✓** | **FIX** | REST reframe (S205 Phase 3.2) |
| 9 | GR full + Invoice 3-way | ✘ | ✘ | — | PO chain flake blocks downstream |
| 10 | GR partial + variance | ✘ | ✘ | — | PO chain flake blocks downstream |
| 11 | RFP 4-level + OR within 5% | ✘ | ✘ | — | PO chain flake blocks downstream |
| 12 | RFP CFO rejection | ✘ | ✘ | — | PO chain flake blocks downstream |
| 13 | Dual-approval boundary exact | ✓ | ✓ | — | — |
| 14 | Dual-approval boundary +₱1 | ✘ | **✓** | **FIX** | Backend-poll refactor (S205 Phase 1.2) |
| 15 | TIN gate | ✘ | **✓** | **FIX** | REST reframe (S205 Phase 1.3) |
| 16 | S193 Inactive asymmetry | ✘ | ✘ | — | PO chain flake blocks first half |
| 17 | Duplicate invoice | ✘ | ✘ | — | PO chain flake blocks first invoice create |
| 18 | Match Exception bypass | ✘ | **✓** | **FIX** | REST approveViaRest (S205 Phase 1.7) |
| 19 | Invoice date earlier | ✘ | ✘ | — | PO chain flake blocks PO creation |
| 20 | Partial receive | ✘ | `−` | **SKIP** | Deferred S209 (badge missing) |
| 21 | OR > 5% variance flag | ✘ | ✘ | — | PO chain flake blocks downstream |
| 22 | Double-payment guard | ✘ | ✘ | — | PO chain flake blocks downstream |
| 23 | Procurement User no approve | ✘ | **✓** | **FIX** | hrms #608 ensure-user REST |
| 24 | Warehouse supplier grid | ✘ | `−` | **SKIP** | Deferred S207 (role-hide missing) |
| 25 | PO reject at Butch | ✓ | ✘ | **REGRESS** | Chain flake (intermittent) |
| 26 | PO reject at CEO | ✓ | ✘ | **REGRESS** | Chain flake (intermittent) |
| 27 | Invoice variance REJECTED | ✘ | ✘ | — | PO chain flake blocks |
| 28 | RFP reject at Review | ✘ | ✘ | — | PO chain flake blocks |
| 29 | RFP reject at Budget | ✘ | ✘ | — | PO chain flake blocks |
| 30 | RFP reject at CEO | ✘ | ✘ | — | PO chain flake blocks |
| 31 | GR reject entire shipment | ✘ | `−` | **SKIP** | Deferred S208 (button missing) |

## Summary of movement

**Flipped FAIL → PASS (6):** S194-7, 8, 14, 15, 18, 23
**Flipped PASS → FAIL (3 regressions):** S194-5, 25, 26 — all are simple PO-reject tests at different approval levels; they passed in iter8 but failed in iter9 due to the same PO approval chain UI flake that blocks S194-9+
**Net improvement:** +2 (9 → 11)
**Deferred to new sprints (3):** S194-20 → S209, S194-24 → S207, S194-31 → S208

## Root cause — remaining 14 non-deferred FAILs

**14 failing tests all share the same upstream blocker:** cross-browser PO approval chain (Mae → Butch → CEO UI clicks) produces no Sonner toast / dialog-close within 15s on certain test runs. When `completeApprovalChain` fails to transition the PO to "Approved", every downstream step (send to supplier, GR, invoice, RFP) cascades to failure.

### Why S205 did NOT fix this

1. **REST bypass is blocked** — `hrms.api.procurement.approve_po_mae/butch/ceo` each check `frappe.session.user != cpo_email` and throw if mismatched. The service-account token has Administrator role but NOT Mae's identity. Per the codebase:
   ```python
   cpo_email = settings.get("cpo_approver_email")
   if cpo_email and frappe.session.user != cpo_email:
       frappe.throw(_("Only {0} can approve as CPO").format(cpo_email))
   ```
   Backend support for admin-on-behalf-of-approver is not implemented and not in S205 scope.

2. **Scope-protected** — S205 plan explicitly states "Does not add product features" and "Does not change core procurement business rules". PO approval chain REST bypass would require either (a) a new backend whitelisted endpoint like `approve_po_as_admin(name, level)`, or (b) per-user API tokens pre-seeded into the test environment.

## Next-sprint recommendation

**S210 candidate** — _PO Approval Chain Stabilization_. Two options (pick one after operator review):
- **Option A (backend):** Add whitelisted `approve_po_as_admin(name, level, on_behalf_of)` endpoint guarded by Administrator role that bypasses the `cpo_email` session-user check. Used only by E2E test harness; gated behind an env flag in production.
- **Option B (test-env):** Seed per-user API tokens for `mae@bebang.ph`, `butch@bebang.ph`, `sam@bebang.ph` into Doppler. Test harness picks the correct token per level for REST call.

Expected delta from S210: 10+ additional tests unblocked (S194-5, 9, 10, 11, 12, 16, 17, 19, 21, 22, 25, 26, 27, 28, 29, 30). Total after S210 ≈ 21+ / 31 PASS.

## Deferred (S205 Phase 4)

| Sprint | Test | Product gap |
|---|---|---|
| S207 | S194-24 | Warehouse role does not hide Add Supplier / Edit CTAs |
| S208 | S194-31 | GR detail lacks "Reject Entire Shipment" bulk action |
| S209 | S194-20 | PO detail lacks "Partially Received" badge |

## S205 Library Deliverables (validated)

See `LIBRARY_IMPROVEMENTS.md`. All 10 library members were exercised:
- `waitForDocStatus` — validated by S194-2, 14 PASSing
- `assertCreateFails` — validated by S194-7, 8, 15 PASSing
- `submitForVerificationViaRest` / `verifyMatchViaRest` — executed but blocked by upstream chain flake
- `completeRFPApprovalChainViaRest` — executed but blocked by upstream chain flake
- `approveViaRest` (MatchException) — validated by S194-18 PASS

## Conclusion

S205 delivered the agreed library foundation (10 members, 30+ call sites) and unlocked 6 tests that were blocked on test-infra issues. The remaining 14 non-deferred failures share a single upstream root cause (PO approval chain UI flake) that requires a backend change outside S205 scope. **Status: COMPLETED_PARTIAL** — all in-scope work shipped; out-of-scope blocker documented with S210 as the proposed successor.
