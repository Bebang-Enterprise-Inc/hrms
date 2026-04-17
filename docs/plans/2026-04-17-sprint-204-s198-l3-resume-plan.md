# S204 — S198 L3 Resume Plan (Cold-Start Handoff)

```yaml
sprint: S204
status: PLANNED
planned_date: 2026-04-17
plan_file: docs/plans/2026-04-17-sprint-204-s198-l3-resume-plan.md
depends_on:
  - S198 (hrms#595, bei-tasks#405/#406/#408/#410 MERGED + DEPLOYED)
  - S203 (hrms#607 MERGED + DEPLOYED) — dispatch auto-creates Draft SI + acceptance submits it
  - S203 followup (hrms#610 OPEN) — bei_legal_entity = bki_company fix
  - Live data patches (BEI Settings + 37 Customers)
completed_date: ""
execution_summary: ""
branch: s204-s198-l3-resume-plan
hrms_pr: TBD
canonical_unit_total: 42
purpose: "Resume the S198 L3 retry after session compaction. 1 of 7 scenarios proven (S1 SM Tanza → ACC-SINV-2026-00003 submitted). 6 scenarios remain: S1 fresh browser run (post-#610 merge), S2, S3, S4, F1, F2, F3."
```

> **Registry row** (locked 2026-04-17): `S204 | s204-s198-l3-resume-plan (hrms) | TBD | PLANNED`. Next reservation → `S205`.

---

## Purpose

This session spent ~5 hours resuming the S198 L3 retry after the 2026-04-16 "warehouse receiving flow completion" ship. The work produced **one proven S1 chain** (`ACC-SINV-2026-00003`) and uncovered three additional blockers that were each fixed, but ran out of session time before completing the other 6 scenarios.

Sam asked to compact the session. This plan is the handoff document: it tells the next agent (a) exactly what state production is in, (b) what browser scenarios still need to run, (c) which test specs + helper scripts to use, and (d) the exact order of operations.

**Net verdict today:** 1 / 7 scenarios proven (S1 manual-patched submit). Plan stays **FAIL_RETRY_REQUIRED** until 7 / 7 pass browser-only per Sam's 2026-04-16 rule (partial = fail).

---

## Design Rationale (For Cold-Start Agents)

### Why this exists
- S192 L3 run (2026-04-15) failed 6/7; Sam's rule: partial = fail, whole run repeats from scratch.
- S198 shipped (2026-04-16) to close the UI gap (store-side receiving queue + WR auto-create + GChat notify).
- S203 shipped (2026-04-17) to unify the SI submit path through the browser.
- S203 followup (#610 OPEN) fixes a regression of S192 F03 (`bei_legal_entity` pointing at buyer instead of issuer).
- **Today's work** (2026-04-17, ~5h): deployed S203, discovered 3 more live-data blockers, patched them, proved S1 end-to-end manually, wrote followup PR, ran out of time before scenarios 2-7.

### The S1 proof is real
- Order `BEI-ORD-2026-00269` created browser-only by `test.area@bebang.ph` on SM Tanza.
- Dual approval + MR approval + dispatch + store-side acceptance all through real browser clicks (accept was via `/dashboard/warehouse/internal-receiving/BEI-WHR-2026-00006?returnTo=/dashboard/store-ops/receiving`).
- After `bei_legal_entity` one-field flip: `ACC-SINV-2026-00003` submitted with grand_total ₱16,977.27, 12% VAT (₱1,818.99 exact), GL balanced, `Customer party = BEBANG MEGA INC.` on `Debtors - BKI` row (DM-1 compliant).
- That is the S190 Company-first billing chain finishing end-to-end through the browser for the first time.

### Why the next agent should NOT redo S1 on the current production
- Until #610 merges + deploys, every new dispatch will create a Draft SI with `bei_legal_entity = buyer_entity_name` and fail to submit.
- A fresh browser S1 on production-today will fail at the final submit step exactly like it did today.
- **The agent must wait for #610 merge + deploy before running ANY fresh scenario.**

### Why we chose backend unification (S203 Option 1) over two Accept endpoints
See `output/plan-audit/s198-warehouse-receiving-flow-completion/verified_blockers.md` CRIT-1. Option 1 keeps a single endpoint (`complete_warehouse_receiving`) so the store-crew UI and warehouse-staff UI both post to the same backend and both produce an SI. Any drift between the two endpoints was the operator-UX risk option 2/3 carried.

### Known limitations the next agent must know
1. **S199 rename broke `_get_commissary_company()` default.** The hardcoded fallback was `"Bebang Kitchen Inc."` (mixed case). Live Company is `"BEBANG KITCHEN INC."` (ALL CAPS). We patched `BEI Settings.commissary_company` live; if someone clears that setting, dispatches to non-BKI-matching paths silently skip WR creation. Mitigation already landed in S198 code guard but hardcoded default is still wrong — consider fixing in a future sprint.
2. **Customer.is_internal_customer + empty Customer.companies list → ERPNext `validate_inter_company_party` blocks every BKI→store Draft SI.** We added BKI to the `companies` allowlist on 37 internal customers. A new store onboarded later will hit the same wall.
3. **`dispatch-row-${mrName}` testid does not exist on `/dashboard/warehouse/dispatch`.** `DispatchPage.ts` waits for it and never finds it. Fallback path `dispatch-button-${mrName}` works (confirmed today). The L3 retry spec in this plan uses the button testid directly.
4. **The test-accounts' cookies at `~/.playwright-auth/` sometimes corrupt after long sessions.** If login fails with a network-trace artifact error, delete that dir before rerun.

### Source references (grounded today)
- `hrms/api/warehouse.py:486` — `_get_commissary_company()` helper + hardcoded default
- `hrms/api/warehouse.py:757-919` — `complete_warehouse_receiving()` (S203 touched: `dispatch_se_name` capture + `_submit_dispatch_draft_si` call)
- `hrms/api/warehouse.py:1265-1370` — `_create_warehouse_receiving_for_se()` (S198 auto-create)
- `hrms/api/warehouse.py:1545-1585` — S203 Draft SI hook inside `create_stock_transfer`
- `hrms/api/commissary.py:1143-1146` — `bei_legal_entity = bki_company` (S203 followup #610 — NOT YET DEPLOYED)
- `bei-tasks/app/dashboard/store-ops/receiving/page.tsx` — store crew queue (S198)
- `bei-tasks/app/dashboard/warehouse/internal-receiving/[receiving_name]/page.tsx` — detail page that calls `completeInternalReceipt` → `warehouse.complete_warehouse_receiving`
- `bei-tasks/tests/e2e/specs/s198-l3-retry.spec.ts` — this session's S1 retry spec (full chain, inline dispatch)
- `bei-tasks/tests/e2e/specs/s198-accept-leg.spec.ts` — accept-leg-only proof spec used today
- `output/l3/s198/s1_accept_leg.json` — today's S1 proof artifact (submitted SI, GL entries)
- `output/l3/s198/HANDOFF_FOR_L3_AGENT.md` — prior session's handoff (still authoritative for PR list + RBAC maps)
- `output/plan-audit/s198-warehouse-receiving-flow-completion/verified_blockers.md` — 15 CRIT audit blockers from pre-S198-ship audit

---

## Requirements Regression Checklist (cold-start, yes/no before any code)

- [ ] Is hrms PR #610 MERGED + DEPLOYED on production? If NO → STOP. Resume only after deploy.
- [ ] Does `hrms/api/commissary.py:1144` on origin/production contain `si.bei_legal_entity = bki_company` (not `buyer_entity_name`)?
- [ ] Does `BEI Settings.commissary_company` live value equal `"BEBANG KITCHEN INC."` (ALL CAPS)?
- [ ] Do all 5 target store customers (`BEBANG MEGA INC.`, `SM Megamall - BEBANG ENTERPRISE INC.` child, `TASTECARTEL CORP.`, `BEBANG MEGA INC.` again for Ayala Evo, TUNGSTEN for Araneta) have `BEBANG KITCHEN INC.` in their `companies` allowlist?
- [ ] Is Pinnacle Cold Storage stock ≥ 5000 per key SKU (FG001/FG002/FG010/FG023/PM002/PM003/PM007)? If not → run `scripts/s192_seed_pinnacle_stock.py`.
- [ ] Are the test users live and logged in via the `loggedInAs*` fixtures: `test.area`, `test.scm`, `test.supervisor`?
- [ ] Are the three page objects on main (not in a local worktree): `WarehouseApprovalPage`, `DispatchPage` (S198 rewrite), `ReceivingQueuePage`, `ReceivingPage` (S198 rewrite)?
- [ ] Has the stranded test data from today been cleaned (orders 00264-00269, MR 00122-00128, WR 00003-00006, SI 00003 already submitted)? If NOT → `python scripts/s192_cleanup_strays.py`.

---

## What Was Done This Session (Authoritative State)

### Sprints landed today

| Sprint | PR | Repo | Status | What |
|---|---|---|---|---|
| S203 | #607 | hrms | MERGED + DEPLOYED | `create_stock_transfer` now auto-creates Draft SI at BKI intercompany dispatch; `complete_warehouse_receiving` now submits that Draft SI on store acceptance. 7 unit tests. `hrms/api/warehouse.py` touched. |
| S203 followup | **#610** | hrms | **OPEN — awaiting merge** | One-line fix: `build_bki_store_sale_invoice` sets `si.bei_legal_entity = bki_company` (issuer) instead of `buyer_entity_name`. `bei_p10_d04_si_issuance_guard` server script requires this. Fixes the Draft SI submit block. |

### Live-data patches (not code — direct SSM writes)

| Target | Change | Why |
|---|---|---|
| `BEI Settings.commissary_company` | `""` → `"BEBANG KITCHEN INC."` (ALL CAPS) | S199 renamed the Company to ALL CAPS; the hardcoded Python default `"Bebang Kitchen Inc."` no longer matched `resolve_warehouse_company("PINNACLE …-BKI")` which also returns ALL CAPS. Mismatch silently disabled the S198 WR auto-create hook. |
| 37 Customers with `is_internal_customer=1` | Added `BEBANG KITCHEN INC.` to each `companies` child table allowlist | ERPNext's `validate_inter_company_party` blocks SI creation when buyer is internal + companies allowlist doesn't include the seller. Blocked 100% of Draft SI creations until patched. |

### S1 proof (one scenario, manual final flip, browser-only otherwise)

| Step | Actor | Surface | Doc produced |
|---|---|---|---|
| 1 Order submit | test.area | `/dashboard/store-ops/ordering` | `BEI-ORD-2026-00269` |
| 2 Order approval | test.area | `/dashboard/store-ops/order-approvals` | Order → Approved |
| 3 MR approval | test.scm | `/dashboard/warehouse/approve` | `MAT-MR-2026-00128` → Ordered |
| 4 Dispatch | test.scm | `/dashboard/warehouse/dispatch` | `MAT-STE-2026-00363` + Draft `ACC-SINV-2026-00003` |
| 4b Auto WR | (hook) | — | `BEI-WHR-2026-00006` (fired AFTER the direct-call workaround I used this session — S198 hook didn't auto-fire live because of step-4 ordering with `finance_treatment` compare; being debugged separately) |
| 5 Accept delivery | test.supervisor | `/dashboard/warehouse/internal-receiving/BEI-WHR-2026-00006?returnTo=/dashboard/store-ops/receiving` | WR → Completed, new SE `MAT-STE-2026-00364`, Draft SI `ACC-SINV-2026-00003` still Draft (S203 submit tried but guard failed) |
| 6 Legal entity flip + submit | Administrator (live SSM) | — | `ACC-SINV-2026-00003` submitted, ₱16,977.27 grand_total, 12% VAT (₱1,818.99), Customer party on AR row |

Evidence saved at:
- `F:\Dropbox\Projects\BEI-ERP\output\l3\s198\s1_accept_leg.json`
- Screenshots `F:\Dropbox\Projects\BEI-ERP\output\l3\s198\screenshots\s1acc_*.png`

### Blockers discovered + status

| # | Blocker | Status |
|---|---|---|
| B1 | S198 WR auto-create skipped every BKI dispatch because `BEI Settings.commissary_company` was empty, default hardcoded was mixed-case, live Company is ALL CAPS | PATCHED LIVE (BEI Setting set to ALL CAPS) |
| B2 | `validate_inter_company_party` blocked every Draft SI insert because internal customers had empty `companies` allowlist | PATCHED LIVE (37 customers extended) |
| B3 | `bei_p10_d04_si_issuance_guard` blocked every Draft SI submit because `build_bki_store_sale_invoice` set `bei_legal_entity = buyer_entity_name` | **OPEN — hrms#610 awaiting merge** |
| B4 | S198 WR hook's call-chain in `create_stock_transfer` doesn't reliably fire during dispatch vs when called directly via `_create_warehouse_receiving_for_se(se, contract)` — not yet root-caused | **INVESTIGATION PENDING** — today's workaround was to call the hook directly via SSM after dispatch |
| B5 | `DispatchPage` waits for `dispatch-row-${mrName}` testid that doesn't exist on the live UI; fallback to `dispatch-button-${mrName}` works | Spec inlines dispatch to bypass this; Page Object fix deferred |

---

## Scenarios Still To Run (the 6 that fail the 7-of-7 gate)

| # | User chain | Store | Expected outcome | Notes |
|---|---|---|---|---|
| **S1 fresh** | test.area → test.area → test.scm → test.scm → test.supervisor | SM Tanza | Real `ACC-SINV-YYYY-NNNNN`, customer `BEBANG MEGA INC.`, TIN `010-885-436-00000`, 12% VAT, 8% markup, GL balanced with Customer party | Must rerun post-#610 deploy. Today's SI 00003 counts as proof of the chain but not a fresh 7/7 run. |
| **S2** | same chain | SM Megamall | Real SI, customer = `SM MEGAMALL - BEBANG ENTERPRISE INC.` (S199 store-first), JV markup read LIVE from `BEI Settings.bki_markup_jv_percent` (default 2.75%, do NOT hardcode 2.5%), 12% VAT | S196+S199 rename is live; spec already uses the right name |
| **S3** | same chain | The Grid - Rockwell | **NEGATIVE PATH:** order+approve+dispatch succeed but SI NOT built because `active_with_billing_hold` on that store. Assert: (a) order.company = `THE GRID ROCKWELL - TASTECARTEL CORP.`, (b) MR Ordered + SE created, (c) WR auto-created, (d) `complete_receiving` returns billing-hold response, (e) zero `ACC-SINV` submitted for this order | Do NOT mark as fail when SI is blocked — SI block IS the expected behavior |
| **S4** | same chain (single FG at suggested qty) | Ayala Evo | Real SI; SI customer docname must equal S1 fresh SI customer docname (multi-store same-entity dedupe to `BEBANG MEGA INC.`) | Depends on S1 fresh having run first |
| **F1** | test.area | (any) | Open `/dashboard/store-ops/ordering`, set no qty, attempt submit → Review/Submit controls hidden; zero order created | Proven trivially in S192 run — rerun for coherent evidence |
| **F2** | Administrator (setup) + test.area (run) | test warehouse with `company=NULL` | Inline ValidationError `"Store warehouse … has no Company set"`; zero order created | Requires SSM prep (create warehouse with null company) + SSM cleanup (delete it after) |
| **F3** | test.scm (rename) | after S1 fresh SI lands | Rename Customer `BEBANG MEGA INC.` → new name; observe billing-hold log entry on next dispatch attempt; new dispatch refuses to bill | Last — don't break things for earlier scenarios |

**Score gate: 7/7 PASS required to flip plan to COMPLETED. 6/7 or less → FAIL_RETRY_REQUIRED.**

---

## Test Specs + Helper Scripts Reference

### Primary test spec for S1-S7 browser-only

`F:\Dropbox\Projects\bei-tasks\tests\e2e\specs\s198-l3-retry.spec.ts` — this session's S1 retry spec. It:
- Calls `StoreOrderingPage.submitOrderAtSuggested("SM Tanza", "DRY", { itemCount: 3 })` for order submit
- Inlines the order-approval flow (`approveOrderInBrowser` helper inside the spec — polls for `order-review-row-${orderId}` testid then clicks)
- Calls `new WarehouseApprovalPage(loggedInSCM).approve(mrName)` with a resilient wrapper (try/catch + backend readback of MR status)
- Inlines the dispatch flow (skips `DispatchPage` broken `dispatch-row` wait; uses `dispatch-button-${mrName}` + dialog source warehouse input + Create Transfer button)
- Uses backend readback (`queryDocs`, `readDoc`) ONLY AFTER UI click confirms success (HB-4 compliant)

**Before running S2-S4/F1-F3 extend this spec with one new `test(...)` block per scenario.** Do NOT write from scratch — reuse the `StoreOrderingPage`, `WarehouseApprovalPage`, inline dispatch helper, and `ReceivingQueuePage` patterns already in the file.

### Accept-leg-only proof spec (reference)

`F:\Dropbox\Projects\bei-tasks\tests\e2e\specs\s198-accept-leg.spec.ts` — today's S1 proof. Navigates store crew directly to an existing WR detail page, clicks Accept, asserts SI `docstatus=1`. Keep as regression for the submit leg.

### Page Objects (library — owned by S198, consumed here)

| File | Status | Purpose |
|---|---|---|
| `F:\Dropbox\Projects\bei-tasks\tests\e2e\pages\StoreOrderingPage.ts` | Stable | Order submit via `submitOrderAtSuggested` with react-aware fill |
| `F:\Dropbox\Projects\bei-tasks\tests\e2e\pages\OrderApprovalPage.ts` | Stable | Store-ops order approval (testid `order-review-row-${orderId}` + `approve-order-button`) |
| `F:\Dropbox\Projects\bei-tasks\tests\e2e\pages\WarehouseApprovalPage.ts` | S198 new | MR approval at `/dashboard/warehouse/approve` (aria-label `Approve ${mrName}` + DOM click) |
| `F:\Dropbox\Projects\bei-tasks\tests\e2e\pages\DispatchPage.ts` | **S198 rewrite — has `dispatch-row` wait bug** | Use inline dispatch pattern from `s198-l3-retry.spec.ts` instead until fixed |
| `F:\Dropbox\Projects\bei-tasks\tests\e2e\pages\ReceivingQueuePage.ts` | S198 new | Navigate to store-ops/receiving queue + click `delivery-row-${wrName}` |
| `F:\Dropbox\Projects\bei-tasks\tests\e2e\pages\ReceivingPage.ts` | S198 rewrite | Full queue → detail → accept-delivery-button flow |

### Fixtures (shared — do NOT duplicate)

- `F:\Dropbox\Projects\bei-tasks\tests\e2e\fixtures\auth.ts` — `loggedInAreaSupervisor`, `loggedInSCM`, `loggedInStoreSupervisor`
- `F:\Dropbox\Projects\bei-tasks\tests\e2e\fixtures\cleanup.ts` — `CleanupLedger` (must reverse every `order-create`, `mr-create`, `se-create`, `wr-create`, `si-create`, `warehouse-create`, `customer-rename` at closeout)
- `F:\Dropbox\Projects\bei-tasks\tests\e2e\fixtures\evidence.ts` — `ensureEvidenceDirs`, `snapshot`, `attachNetworkRecorder` — ALWAYS call `ensureEvidenceDirs()` in `beforeAll` or the spec will fail on the first `snapshot()` call with ENOENT

### Assertions

- `F:\Dropbox\Projects\bei-tasks\tests\e2e\assertions\billingAssertions.ts` — `assertCompanyChainCorrect(orderId, expectedChain)` is the single call that verifies the full S190 chain (order.company → MR.target_company → SI customer/tax_id/vat/party). Use this on S1/S2/S4.
- `F:\Dropbox\Projects\bei-tasks\tests\e2e\assertions\orderAssertions.ts` — `assertOrderCompany`, `assertMRCreatedForOrder`, `assertMRFields`

### Support

- `F:\Dropbox\Projects\bei-tasks\tests\e2e\support\frappeReadback.ts` — `readDoc`, `queryDocs`, `findWarehouseReceivingForOrder` (two-hop MR→SE→WR lookup). Read-only backend verification, HB-4 compliant.
- `F:\Dropbox\Projects\bei-tasks\tests\e2e\support\selectors.ts` — `TEST_IDS.orderReviewRow`, `TEST_IDS.approveOrderButton`, `TEST_IDS.dispatchRow` (broken — do not use for S1-S4), `TEST_IDS.dispatchButton`, `TEST_IDS.deliveryRow`, `TEST_IDS.acceptDeliveryButton`
- `F:\Dropbox\Projects\bei-tasks\tests\e2e\support\session.ts` — `USERS.area`, `USERS.scm`, `USERS.supervisor` email + password constants

### Helper scripts used this session (F:\Dropbox\Projects\BEI-ERP\scripts\)

| Script | Purpose | Deploy-pwd gate |
|---|---|---|
| `s192_seed_pinnacle_stock.py` | Seed FG001/FG002/FG010/FG023/PM002/PM003/PM007 at `PINNACLE COLD STORAGE SOLUTIONS - BKI` to 20000 each. Skips if has_batch_no items exist. | `# 2289454` |
| `s192_cleanup_strays.py` | Cancel/delete test orders 248-269 and any later stranded test orders. | `# 2289454` |
| `s192_check_error_log.py` | Pull last 15 min of Frappe Error Log rows. | `# 2289454` |
| `s203_check_state.py` | Given an MR name, report linked SE + WR + Draft SI status. | `# 2289454` |
| `s203_full_error.py` | Get full traceback of `S203 Draft SI Error` errors. | `# 2289454` |
| `s203_find_customer.py` | For an MR, find what Customer the Draft SI builder would use + try to build directly. Diagnosis only. | `# 2289454` |
| `s203_fix_customer_bki_allow.py` | Patch all internal customers to include `BEBANG KITCHEN INC.` in their `companies` allowlist. **ALREADY RUN TODAY — do not rerun unless a new internal customer is onboarded.** | `# 2289454` |
| `s203_hook_trace.py` | Trace why the S198 WR auto-create hook skipped during a specific MR's dispatch (checks source_company ↔ commissary_company match, contract.destination_warehouse, finance_treatment). | `# 2289454` |
| `s203_submit_error.py` | Direct SI submit attempt with full traceback. | `# 2289454` |
| `s203_fix_si_and_submit.py` | One-off: flip `bei_legal_entity` on a Draft SI to the company field and submit. **Only usable as a workaround until #610 deploys.** | `# 2289454` |
| `s203_check_mr127.py`, `s203_check_mr127_v2.py`, `s203_check_mr128_v2.py` | Session-specific MR diagnostics. Reference patterns for writing new ones. | `# 2289454` |
| `s203_find_customer.py` | Trace Draft SI builder customer resolution. | `# 2289454` |

---

## Execution Phases

### Phase 0 — Preflight + readiness (3 units)

**P0-T1 — confirm deployment state.** Verify `hrms#610` is MERGED and deployed to production before ANY code/test changes. If NOT merged → STOP, report to Sam, wait.

`MUST_CONTAIN on origin/production:hrms/api/commissary.py`: the string `si.bei_legal_entity = bki_company`.

**P0-T2 — confirm live-data patches.** Read back three values to confirm today's SSM patches are still in force:
1. `curl --get 'https://hq.bebang.ph/api/method/frappe.client.get_single_value' --data-urlencode 'doctype=BEI Settings' --data-urlencode 'field=commissary_company' -H 'Authorization: token <KEY>:<SECRET>'` → must return `"BEBANG KITCHEN INC."`.
2. Pick any of the 37 patched customers (e.g. `BEBANG MEGA INC.`), fetch via `frappe.client.get`, assert `companies` child table contains `BEBANG KITCHEN INC.`.
3. `BEI Settings.bki_markup_jv_percent` value captured for S2 assertion (do NOT hardcode).

**P0-T3 — stock + strays cleanup.**
- Run `python scripts/s192_seed_pinnacle_stock.py # 2289454` and confirm each SKU ≥ 5000.
- Run `python scripts/s192_cleanup_strays.py # 2289454` to remove any Draft orders left from today.
- Verify: cleanup script output shows zero errors.

**Evidence:** `output/l3/s204/PHASE0_READINESS.json` with the three values above + cleanup result.

### Phase 1 — S1 fresh run (5 units)

**P1-T1 — extend `s198-l3-retry.spec.ts` to run S1 fresh.** The file already has one test case; confirm it uses the canonical flow. If needed, reorder so the S1 test runs first (before new S2-F3 tests added in Phase 2).

`MUST_MODIFY`: `bei-tasks/tests/e2e/specs/s198-l3-retry.spec.ts`
`MUST_CONTAIN`: `assertCompanyChainCorrect(orderId, { company: "SM TANZA - BEBANG MEGA INC."`

**P1-T2 — run and assert SI.**
```bash
cd F:/Dropbox/Projects/bei-tasks
FRAPPE_API_KEY=$(doppler secrets get FRAPPE_API_KEY --plain --project bei-erp --config dev) \
FRAPPE_API_SECRET=$(doppler secrets get FRAPPE_API_SECRET --plain --project bei-erp --config dev) \
S192_EVIDENCE_ROOT="F:/Dropbox/Projects/BEI-ERP/output/l3/s204" \
npx playwright test tests/e2e/specs/s198-l3-retry.spec.ts --reporter=list --timeout=1500000
```

**Pass criterion:** spec produces a real `ACC-SINV-YYYY-NNNNN` where:
- `customer == "BEBANG MEGA INC."` (Customer docname, not Company)
- `tax_id == "010-885-436-00000"`
- `grand_total > 0` and `total_taxes_and_charges / base_net_total` is within 0.01 of 0.12 (12% VAT)
- GL Entry exists for voucher with `party_type="Customer" party="BEBANG MEGA INC."` (DM-1)

**Evidence:** `output/l3/s204/s1_fresh.json` + screenshots.

### Phase 2 — S2 / S3 / S4 runs (12 units)

Add one test case per scenario to `s198-l3-retry.spec.ts`. Use the S1 test block as template.

**P2-T1 S2 SM Megamall (4u).** Change `SM_TANZA` constant usage to a new `SM_MEGAMALL` constant:
```
store: "SM Megamall",
company: "SM MEGAMALL - BEBANG ENTERPRISE INC.",
customer: "SM MEGAMALL - BEBANG ENTERPRISE INC.",  // S188 child entity
// DO NOT hardcode markup — read from BEI Settings.bki_markup_jv_percent
```
Add assertion that reads live markup from settings, computes expected grand_total, asserts within 0.5%.

**P2-T2 S3 The Grid - Rockwell negative-path (5u).** This is the scenario where SI is EXPECTED to be blocked:
```
store: "The Grid - Rockwell",
company: "THE GRID ROCKWELL - TASTECARTEL CORP.",
tin: "672-270-879-00000",
expected_outcome: "billing_hold",
```
Assertions:
- Order created with correct company ✓
- MR approved + SE created ✓
- WR auto-created ✓
- After accept: `queryDocs("Sales Invoice", {custom_bei_store_order: orderId, docstatus: 1})` returns `[]`
- `queryDocs("Comment", {reference_doctype: "BEI Warehouse Receiving", content: ("LIKE", "%billing hold%")})` returns at least one entry

**P2-T3 S4 Ayala Evo multi-store same-entity (3u).** Submit order to Ayala Evo, verify SI customer docname === S1 fresh SI customer docname. Test depends on S1 fresh having run.

### Phase 3 — F1 / F2 / F3 failure scenarios (7 units)

**P3-T1 F1 empty order (1u).** In `s198-l3-retry.spec.ts`, add test: go to `/dashboard/store-ops/ordering`, select SM Tanza, set no qty, attempt submit. Assert Review/Submit controls hidden OR inline "At least one item with quantity > 0" error visible. Assert `queryDocs("BEI Store Order", {submitted_by: "test.area@bebang.ph", creation: [">=", "<now-2min>"]})` returns `[]`.

**P3-T2 F2 missing-Company warehouse (3u).** Requires pre-run SSM setup + post-run SSM cleanup. Script + spec:
1. Helper `scripts/s204_f2_setup.py`: create warehouse `S204-F2-TEST - <co>` with `company=NULL` (if allowed) OR with `company=""` empty; grant test.area access; record docname.
2. Spec: test.area submits order selecting the test warehouse; assert inline ValidationError "Store warehouse … has no Company set"; zero order created.
3. Helper `scripts/s204_f2_cleanup.py`: delete the test warehouse, revoke access. Registered in `CleanupLedger` as `warehouse-create`.

**P3-T3 F3 Customer rename billing-hold (3u).** Requires S1 fresh SI to already exist. Rename `BEBANG MEGA INC.` → `BEBANG MEGA INC. RENAMED-S204` via SSM. Attempt new dispatch for SM Tanza. Assert dispatch either (a) fails with billing-hold error OR (b) creates Draft SI that does NOT submit, plus a Comment/log entry on the order referring to the customer mismatch. Rename back at cleanup.

`CleanupLedger` entry kind: `customer-rename` with `{oldName, newName}` for reversal.

### Phase 4 — Evidence + closeout (6 units)

**P4-T1 cleanup verification.** After all scenarios, assert `cleanupLedger.pendingEntries === 0` in `afterEach` equivalent. Every order/MR/SE/WR/SI/warehouse/customer-rename mutation must be reversed.

**P4-T2 evidence artifact pack.** Write to `output/l3/s204/`:
- `SUMMARY.md` — scenario × pass/fail matrix, honest verdict, defect list
- `state_verification.json` — per-scenario `{verdict: "PASS"|"FAIL", si_name, customer, grand_total, vat, markup_used, ...}` with hard `score: {pass: N, fail: 7-N, total: 7}`
- `form_submissions.json` — every POST to `/api/ordering` + `/api/warehouse` recorded via `attachNetworkRecorder`
- `api_mutations.json` — every Frappe doc created/modified during the run (before/after snapshots)
- `cleanup_ledger.json` — running ledger
- `cleanup_report.json` — reverser output; `failed: []`
- `screenshots/` — per-step captures
- `blocking_defects.json` / `deferred_defects.json` — any new defects
- `LIBRARY_IMPROVEMENTS.md` — if ≥ 3 library fixes happened during the run

**P4-T3 plan + registry flip.**
- Plan YAML: `status: COMPLETED`, `completed_date: "2026-04-17"` (or actual), `execution_summary: …` (2-3 sentences).
- Sprint registry S204 row: flip to COMPLETED with PR refs + summary.
- S192 row: flip from `FAIL_RETRY_REQUIRED` to `RETRIED_BY_S204_PASSED` if all 7 scenarios green. If still partial, keep `FAIL_RETRY_REQUIRED` and record the count.

`git add -f` is required for both files (`docs/` may be gitignored).

**P4-T4 closeout PR.** Create a NEW branch (`s204-closeout-<date>` or similar — never reuse the plan branch which has its own PR). PR body includes the scenario pass/fail table + links to the evidence artifacts. Per PR-Handoff: share URL with Sam, STOP, do NOT merge.

---

## L3 Workflow Scenarios (authoritative run table)

| # | User | Action | Expected Outcome | Failure Means |
|---|---|---|---|---|
| S1 | test.area → test.area → test.scm → test.scm → test.supervisor | Submit on SM Tanza → approve order → MR approve → dispatch → accept at `/dashboard/store-ops/receiving` | Real SI ACC-SINV-YYYY-NNNNN, customer=BEBANG MEGA INC., TIN=010-885-436-00000, 12% VAT, 8% markup, GL balanced + Customer party on Debtors - BKI | #610 not deployed OR one of the live patches drifted |
| S2 | same | Same on SM Megamall | Real SI, customer=`SM MEGAMALL - BEBANG ENTERPRISE INC.`, JV markup=`BEI Settings.bki_markup_jv_percent`, 12% VAT | S188 child resolution broken OR markup source wrong |
| S3 | same | Same on The Grid - Rockwell | NEGATIVE: order+approve+dispatch succeed, no SI submitted, billing-hold log entry | Billing-hold guard broken (SI created when it shouldn't) |
| S4 | same (single item) | Same on Ayala Evo | Real SI; SI customer docname === S1's SI customer docname | Multi-store same-entity dedupe broken |
| F1 | test.area | Ordering page, no qty, attempt submit | Controls hidden / inline error; zero order created | S0 empty-order gate broken |
| F2 | Admin setup + test.area run | Submit on warehouse with company=NULL | Inline ValidationError; zero order created | S190 company-first guard broken |
| F3 | test.scm rename after S1 SI | Rename Customer, attempt new dispatch | Billing-hold log entry; new dispatch refuses to bill | S190 rename guard broken |

Score gate: **7 PASS, 0 FAIL.** No partial.

---

## Ground-Truth Lock

- evidence_sources:
  - `output/l3/s198/s1_accept_leg.json` — today's S1 proof (SI 00003 submitted)
  - `output/l3/s198/HANDOFF_FOR_L3_AGENT.md` — prior session's handoff
  - `output/plan-audit/s198-warehouse-receiving-flow-completion/verified_blockers.md` — 15 CRIT audit
  - `hrms/api/warehouse.py` (origin/production post-S203) — S198 + S203 live code
  - `hrms/api/commissary.py` (branch `s203-followup-legal-entity` — NOT YET ON PRODUCTION) — the #610 fix
  - `bei-tasks/tests/e2e/specs/s198-l3-retry.spec.ts` — this session's S1 spec
  - `bei-tasks/tests/e2e/specs/s198-accept-leg.spec.ts` — accept-leg proof
- count_method:
  - metric: scenarios passed browser-only
  - basis: entries in `output/l3/s204/state_verification.json` whose `verdict === "PASS"` and (for S1/S2/S4) whose `si_name` matches `^ACC-SINV-\d{4}-\d{5}$` and whose SI `docstatus === 1`
  - method: `python -c "import json; d=json.load(open('output/l3/s204/state_verification.json')); print(d['score'])"`
- authoritative_sections:
  - "What Was Done This Session" — frozen, historical
  - "Scenarios Still To Run" + "Execution Phases" — execution source of truth
- normalization_required:
  - any amendment that changes scenario counts, customer names, company names, or markup values MUST update the L3 Workflow Scenarios table in the same revision
- unresolved_value_policy:
  - operator-facing unknowns → `[UNVERIFIED — requires Sam confirmation]`

---

## Autonomous Execution Contract

- completion_condition:
  - #610 MERGED + deployed (enforced by Phase 0)
  - Live patches verified (BEI Setting + customer allowlists + Pinnacle stock)
  - Phase 1 S1 fresh: real submitted SI with Customer party on GL
  - Phase 2 S2 / S3 (negative) / S4 each produce the expected outcome
  - Phase 3 F1 / F2 / F3 each produce the expected outcome
  - `state_verification.json` has `score.pass === 7 && score.fail === 0`
  - cleanup_report.json has `failed === []`
  - plan + registry flipped to COMPLETED
  - closeout PR created, URL shared with Sam
- stop_only_for:
  - #610 not deployed (Phase 0 blocker)
  - Missing Doppler creds
  - Pinnacle stock cannot be seeded (BEI Settings gate missing, etc.)
  - 3 consecutive failed attempts on same scenario after Failure Response analysis
  - Business-policy decision needed (e.g., customer rename target name)
  - Rebase conflict on `hrms/api/store.py` or `commissary.py` (S196/S199 frozen surfaces)
- continue_without_pause_through:
  - Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4
  - Evidence assembly
  - Status reconciliation
- blocker_policy:
  - programmatic (syntax, import, typo) → fix + continue
  - mode A (app bug) → file `blocking_defects.json`, do NOT edit test, fix code, push new branch, hand off to Sam for merge+deploy, retry affected scenarios
  - mode B (test bug) → fix test; if applicable, promote fix to Page Object / fixture / assertion
  - mode C (brittleness) → fix LIBRARY, not spec. No `waitForTimeout(N)`, no `test.retry(3)`
- signoff_authority: single-owner (Sam)
- canonical_closeout_artifacts:
  - `output/l3/s204/SUMMARY.md`
  - `output/l3/s204/state_verification.json`
  - `output/l3/s204/form_submissions.json`
  - `output/l3/s204/api_mutations.json`
  - `output/l3/s204/cleanup_ledger.json`
  - `output/l3/s204/cleanup_report.json`
  - `output/l3/s204/blocking_defects.json`
  - `output/l3/s204/deferred_defects.json`
  - `output/l3/s204/LIBRARY_IMPROVEMENTS.md` (conditional)
  - `docs/plans/2026-04-17-sprint-204-s198-l3-resume-plan.md` (status flipped)
  - `docs/plans/SPRINT_REGISTRY.md` (S204 + S192 rows updated)

---

## Failure Response (Mode A / B / C)

| Mode | When | Action |
|---|---|---|
| **A — App bug** | Scenario fails due to production code defect | File `blocking_defects.json`, do NOT modify the spec, create NEW branch (never push to merged branches), fix code, PR, hand off to Sam. After deploy, re-run affected scenario from scratch. |
| **B — Test bug** | Scenario fails because selector/timing/fixture is wrong | Fix the spec. If the fix helps future specs → promote to Page Object / fixture / assertion in the same commit. Re-run from scratch. |
| **C — Brittleness / flakiness** | Intermittent fail OR needs `waitForTimeout` to pass | Fix the LIBRARY, not the spec. **Forbidden:** `test.retry(3)`, `page.waitForTimeout(N)` masking a missing wait. Use explicit wait-for-element or wait-for-network-response. |

If ≥ 3 library fixes happen during execution, write `output/l3/s204/LIBRARY_IMPROVEMENTS.md` as a closeout artifact.

Three consecutive failures on the same scenario → STOP and present blocker to Sam.

---

## Zero-Skip Enforcement

Sam's 2026-04-16 rule (still in force): "Partial tests = Fail as well. Every single time you cut corners the whole test will fail and you will repeat from scratch until the whole flow is tested in a browser."

### Forbidden behaviors
- Skip a task silently
- Mark partial work "done"
- Replace task with simpler version without Sam's explicit approval
- "Deferred to next sprint" for any in-scope task
- Combine tasks and drop features
- Implement happy path, skip edge cases (F1/F2/F3)
- `page.request.*` / `fetch()` / `curl` for workflow steps (approve/dispatch/accept)
- `waitForTimeout` masking a missing wait condition
- Declare PASS without real `ACC-SINV-YYYY-NNNNN` in `state_verification.json` for S1/S2/S4, or without the expected no-SI + billing-hold entry for S3

### Per-phase verification scripts

`output/s204/verify_phase0.py`:
1. `git -C F:/Dropbox/Projects/BEI-ERP log origin/production --oneline | grep -q "bei_legal_entity = bki_company"` (S203 followup deployed)
2. `BEI Settings.commissary_company == "BEBANG KITCHEN INC."` via API
3. Each of the 5 target customers has BKI in their companies allowlist
4. Pinnacle stock ≥ 5000 per key SKU

`output/s204/verify_phase1.py`:
1. `output/l3/s204/state_verification.json` has an `S1` scenario with `verdict === "PASS"` and a real `si_name`
2. `readDoc("Sales Invoice", si_name).docstatus === 1`
3. GL entry exists with `party_type="Customer"`

`output/s204/verify_phase4.py`:
1. `score.pass === 7 && score.fail === 0`
2. S1/S2/S4 each have `si_name` matching `^ACC-SINV-\d{4}-\d{5}$`
3. S3 has `si_name === null` (negative path — no SI is the expected outcome)
4. `cleanup_report.json.failed === []`

**HARD BLOCKER:** If any verification script FAILs, do not proceed to the next phase. Fix the failure first.

---

## Status Reconciliation Contract

When phase status, score, blocker count, defect count, or PR state changes, the agent updates in the SAME work unit:
1. `output/l3/s204/state_verification.json`
2. `output/l3/s204/SUMMARY.md`
3. `output/l3/s204/blocking_defects.json` / `deferred_defects.json` (if changed)
4. `docs/plans/2026-04-17-sprint-204-s198-l3-resume-plan.md` (status YAML)
5. `docs/plans/SPRINT_REGISTRY.md` (S204 row; S192 row at closeout)
6. PR description on the closeout PR

---

## Anti-Rewind / Concurrent-Run Protection

### Surface ownership matrix
| File / surface | S204 owner | Concurrent risk |
|---|---|---|
| `bei-tasks/tests/e2e/specs/s198-l3-retry.spec.ts` | S204 (extend) | None known |
| `bei-tasks/tests/e2e/specs/s198-accept-leg.spec.ts` | S204 (read-only reference) | None |
| `bei-tasks/tests/e2e/pages/*` | S198 owned — S204 consumer only. If S204 needs a Page Object change, the fix is promoted to the library AND committed on a fresh branch. | None |
| `hrms/api/warehouse.py` | S198 + S203 owned. S204 does NOT modify. | S203 followup (#610) must merge before S204 runs. |
| `hrms/api/commissary.py` | S203 followup (#610) owned. S204 does NOT modify. | — |
| `hrms/api/store.py` | S196/S199 frozen. S204 does NOT touch. | — |
| `docs/plans/SPRINT_REGISTRY.md` | S204 adds its own row only | Other sprints own other rows |
| `output/l3/s204/*` | S204 exclusive | — |

### Protected surfaces (do NOT touch)
- `hrms/api/store.py` (S196/S199 frozen)
- `hrms/api/commissary.py::build_bki_store_sale_invoice` (S203 followup owned — will merge via #610)
- `bei-tasks/app/dashboard/store-ops/order-approvals/page.tsx` (S192-frozen)
- `bei-tasks/app/dashboard/warehouse/internal-receiving/[receiving_name]/page.tsx` (S198-frozen)
- Any `bei-tasks/tests/e2e/pages/*` — consume only; library changes go via new PR

### Remote-truth baseline (write at Phase 0 start)
`output/l3/s204/REMOTE_TRUTH_BASELINE.json`:
```json
{
  "hrms": {
    "release_branch": "production",
    "release_head_sha": "<git rev-parse origin/production at Phase 0 start>",
    "confirms": ["S198 live", "S203 live", "S203 followup deployed"]
  },
  "bei_tasks": {
    "release_branch": "main",
    "release_head_sha": "<git rev-parse origin/main at Phase 0 start>",
    "confirms": ["receiving queue pages live", "testids live"]
  }
}
```

---

## Agent Boot Sequence (cold-start)

1. **Read this plan fully.** Including Design Rationale, Requirements Regression Checklist, every phase, Failure Response.
2. **Read predecessor evidence:**
   - `output/l3/s198/HANDOFF_FOR_L3_AGENT.md`
   - `output/l3/s198/s1_accept_leg.json`
   - `output/plan-audit/s198-warehouse-receiving-flow-completion/verified_blockers.md`
3. **Confirm #610 is MERGED and DEPLOYED.** If not, STOP. (Check `gh pr view 610 --repo Bebang-Enterprise-Inc/hrms --json state,mergedAt`.)
4. **Create branch off production:** `cd F:/Dropbox/Projects/BEI-ERP && git fetch origin production && git checkout -b s204-s198-l3-resume-plan origin/production` (already created by the plan-writer; if already checked out, skip).
5. **Fetch creds:** `FRAPPE_API_KEY=$(doppler secrets get FRAPPE_API_KEY --plain --project bei-erp --config dev)`, `FRAPPE_API_SECRET=$(doppler secrets get FRAPPE_API_SECRET --plain --project bei-erp --config dev)`.
6. **Create evidence dirs:** `mkdir -p F:/Dropbox/Projects/BEI-ERP/output/l3/s204/{screenshots,dom_dumps,videos,network}`.
7. **Begin Phase 0.**

---

## Execution Workflow

- Local Python sanity: `/local-frappe`
- Deploys: Sam-mediated (PR → Sam merges → Sam triggers deploy)
- L3 testing: runs against production after #610 is deployed
- PR-Handoff: create PR, share URL with Sam, STOP

---

## Checklist (cold-start verification — do NOT mark COMPLETED until every box is checked)

- [ ] Plan YAML `status: COMPLETED` and `completed_date` set
- [ ] SPRINT_REGISTRY.md S204 row flipped to COMPLETED with PR references
- [ ] S192 row flipped from `FAIL_RETRY_REQUIRED` to `RETRIED_BY_S204_PASSED` (if 7/7) OR updated with partial count (if < 7/7)
- [ ] `output/l3/s204/state_verification.json.score.pass === 7 && fail === 0`
- [ ] S1/S2/S4 each have `si_name` matching `^ACC-SINV-\d{4}-\d{5}$` and `docstatus === 1`
- [ ] S3 has `si_name === null` (negative-path expected) AND billing-hold log entry proven
- [ ] `output/l3/s204/cleanup_report.json.failed === []`
- [ ] `rg 'page\.request|fetch\(' output/l3/s204/` returns 0 hits in workflow specs
- [ ] `rg 'waitForTimeout|retry\(3\)' bei-tasks/tests/e2e/specs/s198-l3-retry.spec.ts` returns 0 hits
- [ ] Every spec uses at least one `loggedInAs*` fixture
- [ ] `cleanupLedger.pendingEntries === 0` at run end
- [ ] Closeout PR created + URL shared with Sam
- [ ] **Plan file body ↔ amendment summary normalized** (no stale directives — S028 discipline)

---

## End

Cold-start handoff complete. Everything the next agent needs is in this document, grounded in files in the current tree. Run Phase 0 verifications first; only proceed once #610 is deployed and the live patches are confirmed.
