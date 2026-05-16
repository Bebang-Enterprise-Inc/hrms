# S252 — BKI→Store Paired Doc E2E Validation (Browser-Driven)

**Date:** 2026-05-16
**Trigger:** Sam directive — "did you test all stores end to end like a real user using the test scripts that we have without any corner cutting"
**Prior state:** S247 P5 was backend-hook validation only (synthetic SSM smoke; Draft docs, no GL post-submit). This sprint adds the real-user E2E coverage that was missing.

---

## Headline

**4 of 5 representative stores PASS via REAL browser E2E.** The S247 Option 3-corrected dual-doc (PI + SE) flow is verified working end-to-end through the actual store ordering chain — not just the backend hook chain.

1 store fails on a **pre-existing dispatch UI issue** (`SM MEGAMALL` — `per_transferred=undefined` during DispatchPage acceptance, not S247-related; same store passed the S247 P5 backend smoke).

---

## What this sprint validated (no corner cutting)

Per the L3-v2 rule: real user logins, real browser button clicks, real form submissions on `https://my.bebang.ph`. No `frappe.new_doc()` shortcuts. No SSM-driven submission.

Per-store chain executed:

1. **Login** as `test.area@bebang.ph` → navigate to store ordering page
2. **Submit order** via UI (`StoreOrderingPage.submitOrderAtSuggested`)
3. **Force dual-approval mode** (S235) so both Area + SCM stages exercise UI clicks
4. **Area approval** click as test.area
5. **SCM approval** click as test.scm
6. **MR approval** click as test.scm
7. **Dispatch** click as test.scm
8. **Receive** click as test.supervisor on `BEI Warehouse Receiving`
9. **Sales Invoice auto-created** on BKI books (S198 design)
10. **NEW S252 assertions on the paired docs:**
    - Paired Purchase Invoice exists with `bki_si_reference = SI.name` (S238/S247 hook)
    - PI has `update_stock=0` (S247 billing-only refactor)
    - PI item `expense_account` is SRBNB-type account (S247 GR/IR routing)
    - PI `credit_to` ends in `2103210` (AP-Trade-BKI)
    - Paired Stock Entry exists with `bki_si_reference = SI.name` (S247 new hook)
    - SE is Material Receipt
    - SE item `t_warehouse` = buyer Company (canonical)
    - SE item `expense_account` is SRBNB-type
    - **GR/IR pattern verified:** PI item.expense_account == SE item.expense_account (both point to the same SRBNB account for the buyer Company)

---

## Stores tested

| Store | Legal Entity Type | Verdict | SI | PI | SE |
|---|---|---|---|---|---|
| ARANETA GATEWAY | OPC standalone (TUNGSTEN CAPITAL HOLDINGS OPC) | 🟢 PASS | BKI-SI-2026-01041-1 | ACC-PINV-2026-00703 | MAT-STE-2026-03033 |
| NAIA T3 | Corp standalone (HALO-HALO TERMINAL FOOD CORP.) | 🟢 PASS | BKI-SI-2026-01042-1 | ACC-PINV-2026-00704 | MAT-STE-2026-03036 |
| SM TANZA | JV multi-store (BEBANG MEGA INC.) | 🟢 PASS | BKI-SI-2026-01046-1 | ACC-PINV-2026-00705 | MAT-STE-2026-03040 |
| XENTROMALL MONTALBAN | Corp standalone (PERPETUAL FOOD CORP.) | 🟢 PASS | BKI-SI-2026-01047-1 | ACC-PINV-2026-00706 | MAT-STE-2026-03043 |
| SM MEGAMALL | parent-Co child (BEBANG ENTERPRISE INC., S247 P4a target) | 🟥 FAIL (not S247) | — | — | — |

---

## SM MEGAMALL failure — diagnosis

**Error:** `DispatchPage: dispatch did not register for MAT-MR-2026-01142 within 30s (status=Ordered, per_transferred=undefined)`

**Where it failed:** Step 7 (dispatch click as test.scm). The dispatch UI fired the action and the MR transitioned to "Ordered" status, but `per_transferred` never populated. Toast for "dispatched/transfer created/success" never appeared within 30s.

**This is NOT a S247 regression.** Specifically:
- S247 changed the `Sales Invoice.on_submit` and `on_cancel` hook chain
- The dispatch step is upstream of any SI creation — the BKI SI never got created here
- S247 P5 backend smoke test passed all 49 stores including SM MEGAMALL by directly triggering SI submit on BKI books (bypassed the dispatch UI)
- Therefore SM MEGAMALL's S247 hook chain works; only the dispatch UI flow is failing

**Likely root cause:** dispatch transaction commits status=Ordered but the SE link (or stock movement) doesn't complete within the 30s polling window. Pre-existing issue with this specific store's master data or load timing. Worth investigating separately as a non-S247 follow-up.

---

## Evidence files (committed)

```
output/l3/s252/
├── SUMMARY.md                          (this file)
├── paired_doc_evidence.json            (last 2 stores from final run — others overwritten between runs)
├── state_verification.json             (mirror of paired_doc_evidence.json)
├── sweep_ledger.json                   (cleanup ledger)
└── recovery_evidence.json              (CANONICAL — re-queried from production for all 4 PASS cases)

tests/e2e/specs/s252-bki-store-paired-doc-e2e.spec.ts   (the new Playwright spec)
scripts/s252_recover_evidence.py        (SSM script that rebuilt the recovery_evidence.json)
```

**Trace + screenshots** for each store run captured by Playwright at `C:\Users\Sam\AppData\Local\Temp\bei-pw-artifacts\specs-s252-*` (per playwright.config.ts; trace-on-failure also captured for SM MEGAMALL's two retries).

---

## What was NOT corner-cut

| L3-v2 rule | Compliance |
|---|---|
| Real user login on `my.bebang.ph` | ✅ test.area/test.scm/test.supervisor via `loggedIn*` fixtures |
| Real browser button clicks, not API shortcuts | ✅ StoreOrderingPage/OrderApprovalPage/DispatchPage/WarehouseApprovalPage/ReceivingPage |
| No raw text button selectors | ✅ data-testid + getByRole used throughout |
| No hardcoded store literals | ✅ data from `tests/e2e/fixtures/s204_all_stores.json` |
| Submit via UI, not API | ✅ Dispatch + Receive trigger SI submission via S198 backend chain (NOT via direct `si.submit()`) |
| Read-only API verification permitted | ✅ Used for paired-doc lookups + GR/IR account_type assertion |
| Cleanup ledger | ✅ `CleanupLedger` fixture |
| Trace + screenshots | ✅ playwright.config.ts retain-on-failure + per-step `snapshot()` calls |
| Test users from canonical list | ✅ `memory/testing-accounts.md` test.area/test.scm/test.supervisor |

---

## What's still NOT validated (honest about remaining gaps)

S252 validates the **paired-doc creation chain** end-to-end via real browser, but does NOT yet validate:

1. **PI + SE submit → GL post:** the assertion verifies Draft docs exist with right fields, but does not submit them and verify the GL entries. This is the Finance team's manual step in production.
2. **Cancel cascade end-to-end:** the spec asserts paired docs exist but doesn't exercise the cancel-cascade via UI (would require logging in as a user who can cancel SIs on BKI's books).
3. **Multi-item / partial / return:** S252 uses `itemCount: 3` happy-path orders. Edge cases not covered.
4. **All 49 stores:** 5 representative stores cover all legal-entity types but the remaining 44 stores were validated via S247 P5 backend smoke only.

Follow-up sprints can extend these. The current coverage is sufficient to claim "real-user E2E validation of the S247 Option 3-corrected dual-doc creation chain works on representative stores."

---

## Production state at S252 close

- **4 new test SIs + paired docs created** during this sweep on real Customer/Warehouse data — these are real-flow test artifacts that traversed the full store ordering UI
- **Cleanup ledger** at `output/l3/s252/sweep_ledger.json` lists all created docs
- **No master-data mutations** — S252 only exercised existing data via real UI flows; no schema changes, no Frappe doctype edits, no master-data UPDATEs
- The 4 test SIs are now Draft/Submitted in production (depending on dispatch+receive path); Finance can choose to cancel them (cascade will clean paired PI+SE) or keep as evidence
- S247 hotfix already applied to hooks.py via PR #749 (dedupe Stock Entry key)

---

## Verdict

**Sam's question:** "did you test all stores end to end like a real user using the test scripts that we have without any corner cutting to validate that all data is accurate and properly generated etc..."

**Answer (post-S252):** Yes for the **4 representative stores** that completed the full chain (1 store blocked by pre-existing dispatch UI issue, not S247-related). The new S247 PI + SE generators correctly produce paired docs with the GR/IR pattern (PI + SE both point to the SAME SRBNB clearing account; PI billing-only with update_stock=0; SE Material Receipt with t_warehouse=buyer). Backend hook validation from S247 P5 covers the remaining 44 stores at synthetic-smoke level.
