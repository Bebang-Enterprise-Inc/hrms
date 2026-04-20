---
sprint: S209
title: 49-Store Ordering + Billing + Receive-Variance Browser Acceptance
branch: s209-all-stores-ordering-billing-acceptance
bei_tasks_branch: s209-all-stores-specs
base: production
status: GO
plan_version: v1
plan_date: 2026-04-20
ceo_directive_date: 2026-04-20
canonical_scope: in
canonical_model_reference: docs/STORE_COMPANY_CANONICAL.md
canonical_preflight: required
depends_on:
  - PR #638 merged (canonical cleanup, landed 2026-04-19)
  - 49 per-store billing Customers exist with exact-name match to per-store Companies
  - scripts/verify_canonical_structure.py exits 0 on all 49 stores
execution_mode: autonomous
signoff_authority: single-owner (Sam, CEO)
completed_date:
execution_summary:
---

# S209 — 49-Store Ordering + Billing + Receive-Variance Browser Acceptance

## Registry lock (evidence)

```text
| `S209` | Sprint 209 | `s209-all-stores-ordering-billing-acceptance` (hrms) + `s209-all-stores-specs` (bei-tasks) | TBD | PLANNED 2026-04-20 — 49-Store Ordering + Billing + Receive-Variance Browser Acceptance. | docs/plans/2026-04-20-sprint-209-all-stores-ordering-billing-acceptance.md |
```

Cross-check run 2026-04-20: `git branch -a | grep -iE 's20[9]|s21[0-2]'` returned only `s208-admin-dd-gap-closure` (S208 taken) and the S209 branch created for this plan. S210+ free. Registry Next Sprint Reservation advanced to `S210`.

---

## 🟥 Canonical Model Preflight (Mandatory)

Executing agent MUST run before the first code change:

```bash
python scripts/verify_canonical_structure.py
```

If the verifier prints `[VIOLATION]`, STOP and ask the user. Do NOT add records, flip fields, or create customers/warehouses to paper over a violation — fix the master data with the canonical scripts (`scripts/canonical/migrate_49_stores.py`).

**Canonical law (summary; full rules in `docs/STORE_COMPANY_CANONICAL.md`):**
- Every store has EXACTLY 1 per-store Company + 1 Warehouse + 1 billing Customer + 1 Internal Customer.
- All four share the same name string (e.g. `SM TANZA - BEBANG MEGA INC.`).
- Per-store Company's `parent_company` links to the legal entity parent (if any).
- Warehouse.company = the per-store Company (NEVER the parent).
- Billing Customer: `customer_name` = per-store Company name, `is_internal_customer=0`, `tax_id` = legal entity BIR TIN.
- Internal Customer: `represents_company` = per-store Company, `is_internal_customer=1`, no TIN. Used by S206 labor journals ONLY — never for regular SIs.

**Forbidden in this plan (without explicit CEO approval in-line):**
- Creating a second Warehouse / Company / Customer for any of the 49 stores.
- Ad-hoc SQL mutations on `tabCompany` / `tabWarehouse` / `tabCustomer`.
- Adding new fallback logic to `resolve_store_buyer_entity`.
- Using the parent Company's Customer for store-level billing.
- Reusing an Internal Customer for a regular SI.
- Hard-deleting any test-created SI / SE / WR — use `cancel()` then reverse GL only.

**Scope claim (what S209 touches):**
- **Reads:** all 49 per-store `Warehouse`, all 49 per-store `Company`, all 49 per-store `Customer`, all `tabSales Invoice` / `tabStock Entry` / `tabWarehouse Receiving` / `tabMaterial Request` / `tabBEI Store Order` created by the sweep.
- **Writes (temporary, reverted in closeout):** `custom_area_supervisor` on 43 warehouses (grants `test.area@bebang.ph`), test-created `BEI Store Order` + cascading SI/SE/WR/MR rows.
- **Does NOT touch:** per-store `tabCompany` records (no renames, no field flips), the 49 `tabCustomer` billing records (no name/TIN changes), `tabWarehouse` `company` or `disabled` fields, S206 Internal Customers, Chart of Accounts, Cost Centers, `resolve_store_buyer_entity` code.

---

## Canonical Model Binding

This feature binds to the canonical model as follows:

| Canonical surface | How S209 uses it |
|---|---|
| `Warehouse.company` | Read via `StoreOrderingPage.submitOrder` → resolves per-store Company for order stamping |
| `resolve_store_buyer_entity(warehouse_docname)` | Implicitly exercised when SI is created; test asserts it returned the exact-name Customer |
| `Sales Invoice.customer` | Asserted == per-store Customer from fixture (NOT parent) |
| `Sales Invoice.company` | Asserted == per-store Company (NOT parent) |
| `Sales Invoice.tax_id` | Asserted == fixture.tin (empty for ORTIGAS GREENHILLS only) |
| `BEI Store Order.company` | Asserted via `assertOrderCompany` helper |
| `Material Request.custom_target_company` | Asserted == per-store Company |
| Cost centers | Implicitly exercised; S209 does not mutate |

S209 does NOT:
- Infer store identity from warehouse_name string parsing.
- Hardcode parent Company names (BEBANG MEGA INC., TUNGSTEN CAPITAL HOLDINGS OPC, etc.).
- Add its own `store_id` / `branch_code` field parallel to the canonical model.
- Bypass `resolve_store_buyer_entity` by reading `tabCustomer` directly during test execution.

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

Three prior sprints ran partial store validation:
- **S190 / S192** — validated 4 stores (SM TANZA, SM MEGAMALL, THE GRID ROCKWELL, AYALA EVO) through the full happy chain. Proved Company-first billing resolution works for the cases tested. Evidence: `bei-tasks/tests/e2e/specs/s190-store-company-integration.spec.ts`.
- **S204** — re-ran the same 4 stores + 3 failure scenarios (F1 empty order, F2 NULL-company warehouse, F3 customer-rename billing-hold). 7/7 PASS documented in registry row.
- **PR #638 (2026-04-19)** — canonical cleanup landed. Every store now has exactly one Warehouse + Company + Customer + Internal Customer. 49/49 stores migrated, 65 actions, 0 failures.

**Gap:** 4 stores validated end-to-end, 45 stores validated ONLY at the resolver layer (static `canonical_resolver_live_check.py`). CEO directive 2026-04-20: run the full browser chain for every single store, issue a Sales Invoice per store, verify it bills to the correct corporation — no doubt that all 49 stores' ordering + billing is production-ready.

**Additional gap from CEO directive (2026-04-20):** Two inventory-variance scenarios were not validated anywhere in prior sprints:
1. Store short-receive (warehouse dispatches 10, store receives 8 because items are missing in transit) — how does inventory adjust on both sides? Does the SI bill only what was received?
2. Warehouse short-dispatch (store orders 10, warehouse has only 8, dispatches 8) — does the order process cleanly without errors? Does inventory on both sides reflect the dispatched qty, not the ordered qty?

### Why this architecture

**Extending the S204 library, not rewriting.** The s190/s192/s204 spec already has the Page Objects (`StoreOrderingPage`, `OrderApprovalPage`, `DispatchPage`, `ReceivingPage`), assertions (`assertCompanyChainCorrect`, `assertOrderCompany`), cleanup (`CleanupLedger`), evidence (`EVIDENCE`, `snapshot`), and fixtures (`loggedInAreaSupervisor`, `loggedInSCM`, `loggedInStoreSupervisor`). S209 is a data-driven sweep of those Page Objects over the 49-store fixture, plus two new variance scenarios that extend `DispatchPage.dispatch` and `ReceivingPage.accept` to accept explicit quantities.

**Rejected alternative: use Tier 1 static resolver check for all 49, Tier 2 browser for a sample.** (Assistant proposed this 2026-04-19 05:01 — session JSONL line 9263). CEO rejected: *"No for this, I need to test every single store. You will create 48 sales invoices in production and then you will delete it. All tests should be in browser."* (JSONL line 9269). The acceptance bar is browser-only end-to-end for all 49.

**Rejected alternative: run 49 specs in parallel.** Playwright's default project runs serially to share auth state; parallelism would require per-spec fresh logins and multiplies flakiness. 49 specs × ~90s each ≈ 75 min serial is acceptable. Variance scenarios add ~6 min.

### Key trade-off decisions

| Decision | Chosen | Rejected | Reason |
|---|---|---|---|
| Fixture source | `scripts/s209_generate_fixture.py` (new, idempotent, commits JSON to bei-tasks) | Hardcoded TypeScript constants (s190 pattern for 4 stores) | 49 stores is too many to maintain as TypeScript literals; regenerates cleanly after any canonical migration |
| Variance scenario count | V1 short-receive + V2 short-dispatch on ONE representative store each (not all 49) | 49 × 4 variance permutations (196 cases) | User directive was 48 SIs, not 196. Variance is orthogonal to per-store billing correctness and only needs to pass once per code path |
| Area supervisor grant strategy | Temporary grant pre-sweep, revert in closeout | Seed permanent grants on all warehouses | Production data (S037 register) defines which supervisor covers which stores; seeding `test.area` permanently pollutes the real supervisor assignments |
| Dispatch-qty parameterization | Extend `DispatchPage.dispatch(mrName, items, { qty?: Map<item, qty> })` | New `DispatchPage.dispatchPartial` method | Three-uses rule: the dispatched-qty parameter is used by V1 (full-qty), V2 (short-qty), happy chain (full-qty). Single method with optional override is simpler |
| ORTIGAS GREENHILLS TIN handling | Allow empty TIN ONLY for this one store; assert empty elsewhere = BLOCKER | Skip ORTIGAS GREENHILLS entirely | CEO directive "every single store"; data gap is separately tracked as a DEFERRED BIR follow-up |
| GL reversal on SI cancel | Use Frappe's native `Sales Invoice.cancel()` which auto-creates reversal GL entries | Manually delete GL entries | DM-1: never mutate GL Entry rows directly; always use Frappe's cancel/amend lifecycle |

### Known limitations and their mitigations

| Limitation | Mitigation |
|---|---|
| Only 6/49 warehouses have `custom_area_supervisor` set (JSONL 9345) — `test.area` sees 6 by default | `scripts/s209_grant_test_area_access.py` pre-sweep (idempotent, captures original value); `scripts/s209_revert_test_area_access.py` in closeout |
| ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC has no BIR TIN (JSONL 10109) | Fixture entry has `tin=""` and `allowEmptyTin=true`; assertion allows empty only for this one store |
| AYALA EVO CITY `get_orderable_items` may return empty (JSONL 10109 follow-up list) — canonical warehouse has no order history | If iteration returns empty items, seed one DRY item via `StoreOrderingPage.submitOrderWithFallbackItems` which falls back to the commissary item catalogue |
| Existing fixture at `bei-tasks/tests/e2e/fixtures/s204_all_stores.json` has 45/49 empty TINs (pre-migration snapshot) | S209 Phase 1 regenerates this fixture; old file is overwritten |
| Fixture generator script (`s204_generate_all_store_configs.py`) was NOT committed in the s204 closeout | Phase 1 writes a new `scripts/s209_generate_fixture.py` from scratch; commits to this branch so future sprints can reuse |
| `AYALA VERMOSA` and `SM TANZA` had warehouse.company flipped during migration (JSONL 10272) | Happy-chain iteration for these two stores must pass without route-map errors; Phase 3 manual run verifies before the 49-sweep |
| Cleanup ledger needs to order cancellations SI→SE→WR→MR→BEI Store Order to respect FK constraints | `scripts/s209_cleanup_sweep.py` reads the ledger, groups by dependency, cancels in reverse order; if any row fails, prints blocker and halts |
| Payroll runs on the 25th of each month; SIs that stay uncancelled could affect per-store P&L | Cleanup is MANDATORY in closeout; Phase 6 verification script asserts ledger is empty; test date 2026-04-20 is 5 days before payroll giving buffer |

### Source references

- Canonical cleanup PR: https://github.com/Bebang-Enterprise-Inc/hrms/pull/638
- Canonical SSOT doc: `F:/Dropbox/Projects/BEI-ERP/docs/STORE_COMPANY_CANONICAL.md`
- Verifier: `F:/Dropbox/Projects/BEI-ERP/scripts/verify_canonical_structure.py`
- Existing s190 spec: `F:/Dropbox/Projects/bei-tasks/tests/e2e/specs/s190-store-company-integration.spec.ts` (275 lines)
- Page objects directory: `F:/Dropbox/Projects/bei-tasks/tests/e2e/pages/`
- Assertions directory: `F:/Dropbox/Projects/bei-tasks/tests/e2e/assertions/`
- Fixture directory: `F:/Dropbox/Projects/bei-tasks/tests/e2e/fixtures/`
- Amended plan context: `F:/Dropbox/Projects/BEI-ERP/tmp/s204_amended_49_store_acceptance_plan.md`
- CEO directive session JSONL: `C:/Users/Sam/.claude/projects/F--Dropbox-Projects-BEI-ERP/a8898593-fd37-4b4b-be40-e619400da7e3.jsonl` line 9269 (original) and 2026-04-20 turn (amendment with V2 short-dispatch)

---

## Requirements Regression Checklist (v1)

Before Phase 6 closeout, the executing agent MUST verify each of these as true:

- [ ] RR-01 — `scripts/verify_canonical_structure.py` exits 0 BEFORE the sweep (Preflight)
- [ ] RR-02 — `scripts/s209_generate_fixture.py` produces exactly 49 entries; each has `customer == company` (canonical exact-name match)
- [ ] RR-03 — Every entry except `ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC` has a non-empty `tin`
- [ ] RR-04 — `scripts/s209_grant_test_area_access.py` captures the original `custom_area_supervisor` for every warehouse it touches (revert file written)
- [ ] RR-05 — All 49 happy-chain specs execute via real browser; zero `page.request.*`, zero `fetch(`, zero `curl` in workflow ops (SSM allowed for environmental setup only)
- [ ] RR-06 — Each of the 49 SIs created has `customer` exactly matching fixture.customer (no parent-Company billing leak)
- [ ] RR-07 — Each of the 49 SIs has `company` exactly matching fixture.company (per-store, not parent)
- [ ] RR-08 — Each of the 49 SIs has `tax_id` exactly matching fixture.tin (empty ONLY for ORTIGAS GREENHILLS)
- [ ] RR-09 — Each of the 49 SIs has GL entries with `party_type=Customer`, `party=<fixture.customer>` (DM-1 compliance)
- [ ] RR-10 — Each of the 49 SIs has `total_taxes_and_charges / net_total ≈ 0.12` within ±1% (12% VAT assertion)
- [ ] RR-11 — Each of the 49 SIs has `posting_date` in PHT (not UTC drift)
- [ ] RR-12 — V1 short-receive: SM TANZA dispatches 10, accepts 8, SI bills for 8 (not 10); source warehouse stock decrements by 10, destination stock increments by 8
- [ ] RR-13 — V2 short-dispatch: AYALA VERMOSA store orders 10, warehouse has 8 available, dispatches 8, SI bills 8; source decrements by 8, destination increments by 8
- [ ] RR-14 — Cleanup script cancels all 49+ SI, all SE, all WR, all MR, all BEI Store Order; `cleanupLedger.pendingEntries === 0` after Phase 6
- [ ] RR-15 — `scripts/verify_canonical_structure.py` exits 0 AFTER the sweep + cleanup (no canonical drift)
- [ ] RR-16 — No new Sentry errors in the `bei-hrms` project tagged `module=commissary|warehouse|billing` during the sweep window
- [ ] RR-17 — `custom_area_supervisor` restored to original pre-sweep values on every touched warehouse
- [ ] RR-18 — Evidence files exist: `output/l3/s209/SWEEP_VERIFICATION_SUMMARY.md`, `sweep_ledger.json`, `state_verification.json`, `form_submissions.json`
- [ ] RR-19 — No SI in the sweep resolved to a Customer with `is_internal_customer=1` (S206 Internal Customers untouched)
- [ ] RR-20 — Library contributions (Page Object + assertion extensions) are committed as separate files before first spec import; no inline-in-spec extensions

---

## Ground-Truth Lock

- **evidence_sources:**
  - `F:/Dropbox/Projects/bei-tasks/tests/e2e/fixtures/s204_all_stores.json` — current 49-store fixture (will be overwritten by `s209_generate_fixture.py`)
  - `F:/Dropbox/Projects/BEI-ERP/data/_CONSOLIDATED/STORE_CANONICAL_STATE_2026-04-19.json` — canonical structure baseline (49 stores, post-migration) (originally produced by PR #638)
  - `F:/Dropbox/Projects/BEI-ERP/scripts/canonical_scan_store_state.py` — live snapshot script (read-only)
  - `F:/Dropbox/Projects/BEI-ERP/scripts/canonical_resolver_live_check.py` — static resolver audit (read-only)
  - `F:/Dropbox/Projects/BEI-ERP/docs/STORE_COMPANY_CANONICAL.md` — SSOT rules
  - `F:/Dropbox/Projects/bei-tasks/tests/e2e/specs/s190-store-company-integration.spec.ts` — library baseline (275 lines)
- **count_method:**
  - metric: `store count`
  - basis: `distinct per-store Companies where Company.entity_category = 'Store' AND disabled = 0`
  - method: `canonical_scan_store_state.py SSM run`; expected result `49`
- **authoritative_sections:**
  - This plan body is authoritative for execution.
  - Any amendment section (if added later) is traceability only; must update the plan body in the same edit.
- **unresolved_value_policy:**
  - None. Every value in this plan is either grounded in a cited file or deferred to a script output (captured in Phase 1 evidence).

---

## Phase Budget Contract

| Phase | Units | Ceiling check |
|---|---:|---|
| Phase 0 — Preflight + Library Audit | 6 | ≤12 OK |
| Phase 1 — Fixture regeneration | 7 | ≤12 OK |
| Phase 2 — Library extensions (Page Objects + assertions) | 11 | ≤12 OK |
| Phase 3 — Happy-chain sweep spec (49 stores) | 10 | ≤12 OK |
| Phase 4 — Variance specs (V1 short-receive, V2 short-dispatch) | 8 | ≤12 OK |
| Phase 5 — Execution + evidence | 8 | ≤12 OK |
| Phase 6 — Cleanup + closeout | 9 | ≤12 OK |
| **Total** | **59** | ≤80 OK |

- **preferred_split_threshold:** 12
- **hard_limit:** 15
- **normalization_rule:** if any phase exceeds 12 units during execution, split before audit.

---

## Anti-Rewind / Concurrent-Run Protection Contract

- **ownership_matrix:** single owner (S209 builder). Files touched exclusively:
  - hrms repo: `scripts/s209_*.py`, `output/l3/s209/**/*`
  - bei-tasks repo: `tests/e2e/specs/s209-*.spec.ts`, `tests/e2e/fixtures/s204_all_stores.json` (regenerated), `tests/e2e/pages/DispatchPage.ts` (extended), `tests/e2e/pages/ReceivingPage.ts` (extended), `tests/e2e/assertions/billingAssertions.ts` (extended)
- **protected_surfaces (DO NOT MODIFY):**
  - `hrms/api/dispatch.py` (S204/S206 hardened; no scope changes)
  - `hrms/utils/supply_chain_contracts.py` `resolve_store_buyer_entity` (canonical resolver; no changes)
  - `docs/STORE_COMPANY_CANONICAL.md` (SSOT; no changes)
  - All 49 per-store `tabCompany` records (no structure changes)
  - All 49 per-store `tabCustomer` billing records (no name/TIN changes)
  - S206 Internal Customer records (no changes)
  - `scripts/verify_canonical_structure.py` (enforcer; no changes)
- **remote_truth_baseline:**
  - `hrms` base: `origin/production` HEAD at sprint start (captured in Phase 0 as `output/l3/s209/baseline_sha.txt`)
  - `bei-tasks` base: `origin/main` HEAD at sprint start (same capture)
  - Live evidence: `scripts/canonical_scan_store_state.py` output at Phase 0 preflight
- **touched_file_routing:**
  - Bei-tasks spec changes route to Vercel preview build → manual smoke → merge
  - Hrms script changes route to PR #TBD → Sam reviews → merge
- **active_run_coordination:** S209 is the only active sweep; no overlap with S207 (semi-monthly allocation) or S208 (admin-dd gap closure)
- **pretouch_backup:** Phase 2 first commit of extended Page Objects runs immediately after Phase 1 commit; each file change is atomic
- **supersession_map:** S209 supersedes S190 / S192 / S204 as the definitive "all-stores" acceptance. Prior specs are preserved (not deleted) since their failure-mode scenarios (F1-F3) are still valid.

---

## Autonomous Execution Contract

- **completion_condition:**
  - All phases pass verification scripts with exit 0
  - RR-01 through RR-20 all checked
  - `output/l3/s209/SWEEP_VERIFICATION_SUMMARY.md` written
  - Cleanup ledger shows `pendingEntries === 0`
  - Canonical postcheck shows zero drift
  - PR created on hrms (S209 scripts) and bei-tasks (S209 specs)
  - Sprint Registry row updated to COMPLETED with PR numbers
  - This plan's YAML `status` updated to COMPLETED with `completed_date` + `execution_summary`
- **stop_only_for:**
  - Canonical preflight failure (`[VIOLATION]` output) — STOP, ask Sam
  - More than 3 consecutive store failures in the happy-chain sweep (systemic issue, not per-store) — STOP, dump artifacts, ask Sam
  - ORTIGAS GREENHILLS fails for a reason other than empty TIN — STOP, ask Sam (expected outcome is "SI posts with empty TIN")
  - Any test that cannot be cleaned up (SI cancel fails, GL won't reverse) — STOP, ask Sam (cannot leave hanging GL in prod)
  - Discovery of a second canonical violation class (new duplicate Warehouse/Customer) — STOP, ask Sam
- **continue_without_pause_through:**
  - Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → PR creation
- **blocker_policy:**
  - programmatic error (script crash, typo) → fix and continue
  - per-store test flakiness → retry once; if still fails, record and continue with sweep, fix in dedicated pass
  - business-data/policy decision → pause
  - canonical drift → pause
- **signoff_authority:** `single-owner` — Sam (CEO)
- **canonical_closeout_artifacts:**
  - `output/l3/s209/SWEEP_VERIFICATION_SUMMARY.md`
  - `output/l3/s209/sweep_ledger.json`
  - `output/l3/s209/state_verification.json`
  - `output/l3/s209/form_submissions.json`
  - `output/l3/s209/api_mutations.json`
  - `output/l3/s209/canonical_preflight.txt`
  - `output/l3/s209/canonical_postcheck.txt`
  - `output/l3/s209/baseline_sha.txt`
  - `output/l3/s209/LIBRARY_IMPROVEMENTS.md` (only if ≥3 library fixes happened mid-sprint)
  - `docs/plans/2026-04-20-sprint-209-all-stores-ordering-billing-acceptance.md` (this plan, status → COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (S209 row → COMPLETED with PR numbers)

---

## Signoff Model

- **mode:** `single-owner`
- **approver_of_record:** Sam Karazi (CEO, BEI)
- **signoff_artifact:** `output/l3/s209/SWEEP_VERIFICATION_SUMMARY.md`
- **note:** No department countersign required. PR-handoff workflow: agent creates the two PRs (hrms + bei-tasks) and STOPS; Sam reviews and merges.

---

## Certification Coverage Contract

- **certified_universe:**
  - stores: `49` (fixture-enumerated, exact-name canonical matches)
  - happy-chain SIs: `49` (one per store, in browser)
  - variance scenarios: `2` (V1 short-receive on SM TANZA, V2 short-dispatch on AYALA VERMOSA)
  - DM-1 assertions per SI: `1` (GL party_type=Customer)
  - A2 VAT assertions per SI: `1` (12% within ±1%)
  - A4 timezone assertions per SI: `1` (posting_date in PHT)
  - A5 TIN assertions per SI: `1` (== fixture.tin)
- **closeout_zero_equations:**
  - `review_required` = 0
  - `authoring_required` = 0
  - `unmapped` = 0
  - `required_l4_failed` = 0
  - `required_l4_blocked` = 0
  - `cleanup_ledger.pendingEntries` = 0
- **allowed_skips:**
  - ONLY: `ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC` TIN assertion skipped (DEFERRED to separate BIR data-fill sprint)
- **final_readiness_basis:**
  - `output/l3/s209/SWEEP_VERIFICATION_SUMMARY.md`
  - `output/l3/s209/sweep_ledger.json` (must show 0 pending)
  - `output/l3/s209/canonical_postcheck.txt` (must show exit 0)

---

## Library Audit (Phase 0 task — results captured here)

| Surface needed | Already exists in `bei-tasks/tests/e2e/` | Gap |
|---|---|---|
| Log in as area supervisor | `fixtures/auth.ts :: loggedInAreaSupervisor` | none |
| Log in as SCM / warehouse supervisor | `fixtures/auth.ts :: loggedInSCM`, `loggedInStoreSupervisor` | none |
| Go to ordering, select store, pick DRY cargo, fill suggested qty, submit | `pages/StoreOrderingPage.ts :: submitOrderAtSuggested` | ADD explicit-qty variant: `submitOrderWithExplicitQty(store, cargo, { items: [{code, qty}] })` |
| Approve order (area / SCM stages) | `pages/OrderApprovalPage.ts :: approve` | none |
| Dispatch MR with all-items full qty | `pages/DispatchPage.ts :: dispatch(mrName, itemsFilled)` | EXTEND: accept `{ qty?: Map<itemCode, dispatchQty> }` to support V2 short-dispatch |
| Receive MR with all-items accepted full qty | `pages/ReceivingPage.ts :: accept(mrName, itemsFilled)` | EXTEND: accept `{ acceptedQty?: Map<itemCode, acceptedQty>, rejectedQty?: Map<itemCode, rejectedQty> }` to support V1 short-receive |
| Assert BEI Store Order Company | `assertions/orderAssertions.ts :: assertOrderCompany` | none |
| Assert MR target + source + finance_treatment | `assertions/orderAssertions.ts :: assertMRFields` | none |
| Assert SI exists with correct Company + Customer + TIN + VAT | `assertions/billingAssertions.ts :: assertCompanyChainCorrect` | EXTEND: `{ allowEmptyTin?: boolean }` option for ORTIGAS GREENHILLS |
| Assert GL `party_type=Customer`, `party=<customer>` per SI (DM-1) | `assertions/billingAssertions.ts` (check during Phase 0) | If missing: ADD `assertSIGLPartyIsCustomer(siName, expectedCustomer)` |
| Assert inventory delta per warehouse | NOT FOUND in assertions | ADD `assertInventoryDelta(warehouse, itemCode, expectedDelta, windowStart, windowEnd)` — queries `tabStock Ledger Entry` via SSM readback |
| Cleanup ledger | `fixtures/cleanup.ts :: CleanupLedger` + `fixtures/evidence.ts :: EVIDENCE.cleanupLedger` | none |
| Evidence snapshot + network recorder | `fixtures/evidence.ts :: snapshot`, `attachNetworkRecorder` | none |
| SSM readback | `support/frappeReadback.ts` | none |
| SSM setup (fixture regen trigger) | `support/ssmSetup.ts` | none |

**Library contributions this sprint adds:**
1. `pages/StoreOrderingPage.ts` — new method `submitOrderWithExplicitQty`
2. `pages/DispatchPage.ts` — extended `dispatch` signature to accept explicit `qty` overrides
3. `pages/ReceivingPage.ts` — extended `accept` signature to accept explicit `acceptedQty` / `rejectedQty` overrides
4. `assertions/billingAssertions.ts` — `assertCompanyChainCorrect` gains `{ allowEmptyTin?: boolean }` option
5. `assertions/billingAssertions.ts` — new `assertSIGLPartyIsCustomer(siName, expectedCustomer)` (if not already present)
6. `assertions/inventoryAssertions.ts` (new file) — `assertInventoryDelta(warehouse, itemCode, expectedDelta, windowStart, windowEnd)`

**Ownership note:** Library code (`pages/`, `fixtures/`, `builders/`, `assertions/`, `support/`) is owned by S209 once extended; future sprints are consumers + extenders.

---

## L3 Workflow Scenarios

| ID | User | Action | Expected Outcome | Failure Means |
|---|---|---|---|---|
| HC-1 to HC-49 (49 happy chains — one per store in fixture) | test.area@bebang.ph + test.scm@bebang.ph + test.supervisor@bebang.ph | Submit DRY order with 3 items at suggested qty → area approve → SCM approve → dispatch full qty → receive full qty → assert SI posted | SI exists with `customer == fixture.customer`, `company == fixture.company`, `tax_id == fixture.tin`, GL party_type=Customer, total_taxes / net_total ≈ 0.12 | Canonical resolver regression or per-store billing drift |
| V1 (short-receive) | test.area + test.scm + test.supervisor (SM TANZA) | Submit DRY order with 1 item qty=10 → approve → dispatch 10 → receive 8 (reject_qty=2, reason="items missing in transit") | SI posts with billed qty = 8 (not 10); source warehouse Stock Ledger shows -10; destination warehouse Stock Ledger shows +8; WR shows `accepted_qty=8, rejected_qty=2, notes="items missing in transit"` | Either SI bills wrong qty (currently dispatched, not received), or inventory reflects dispatched not accepted |
| V2 (short-dispatch) | test.area + test.scm + test.supervisor (AYALA VERMOSA) | Pre-seed: reduce source warehouse stock to 8 for the item. Submit DRY order with 1 item qty=10 → approve → dispatch 8 (warehouse has only 8, UI should allow `dispatched_qty < ordered_qty`) → receive 8 | SI posts with billed qty = 8 (not 10, not ordered); source warehouse decremented by 8; destination incremented by 8; no error banner during dispatch; order marked "Partial Fulfilment" or equivalent status | Dispatch UI blocks `dispatched_qty < ordered_qty` (bug), or SI bills ordered qty instead of dispatched qty |

**No vague scenarios.** Every row above names the exact user, exact fields filled, exact assertion.

---

## Zero-Skip Enforcement

**Every task MUST be implemented. No skipping, no deferring, no partial work marked "done".**

### Forbidden agent behaviors

- Skipping a store because it looks similar to another (e.g. "AYALA EVO is similar to SM TANZA; I'll assume it passes")
- Marking partial work as "done" (e.g. happy chain executed but SI assertion not run)
- Replacing a task with a simpler version without user approval
- Saying "deferred to next sprint" for any RR item
- Combining tasks and dropping features in the merge
- Implementing happy path only, skipping V1 or V2 variance scenarios

### Verification script (run AFTER each phase)

Agent writes `output/l3/s209/verify_phase{N}.py` BEFORE starting each phase. Script checks:
1. `git diff --name-only origin/production...HEAD` shows all expected files modified/created
2. Each `MUST_MODIFY` file in the Files-to-Modify table appears in the diff
3. Each `MUST_CONTAIN` grep assertion passes
4. Each phase's evidence files exist
5. `python scripts/verify_canonical_structure.py` exits 0

Template:

```python
#!/usr/bin/env python3
"""Phase N verification — runs AFTER phase completion. Exit 0 if all gates pass."""
import subprocess, pathlib, sys

phase = N
sprint = "s209"
expected_files = [
    # list of files MUST be modified/created in this phase
]
grep_assertions = [
    # (file_path, pattern, min_hits)
]
evidence_files = [
    # list of evidence files that MUST exist
]

failures = []

# 1. git diff check
diff_output = subprocess.run(
    ["git", "diff", "--name-only", "origin/production...HEAD"],
    capture_output=True, text=True, check=True
).stdout.splitlines()
for f in expected_files:
    if f not in diff_output:
        failures.append(f"FAIL: expected {f} modified in this phase; not in git diff")

# 2. grep assertions
for file_path, pattern, min_hits in grep_assertions:
    result = subprocess.run(
        ["grep", "-c", pattern, file_path],
        capture_output=True, text=True
    )
    count = int(result.stdout.strip() or 0)
    if count < min_hits:
        failures.append(f"FAIL: expected pattern '{pattern}' in {file_path} ≥{min_hits} times; found {count}")

# 3. evidence files
for f in evidence_files:
    if not pathlib.Path(f).exists():
        failures.append(f"FAIL: expected evidence file {f} does not exist")

if failures:
    print("\n".join(failures))
    sys.exit(1)
print(f"Phase {phase} verification PASS")
sys.exit(0)
```

**FAIL blocks progress.** Agent must fix the failure before starting the next phase.

---

## Failure Response (QA library discipline)

Per `.claude/docs/qa-test-library-discipline.md` §"Failure Discipline", classify every failure mid-sprint:

- **Mode A (app bug — real product defect):** file `[BUG]` in Sprint Registry deferred-followups, do NOT touch the test or library, re-run after fix
- **Mode B (test bug — wrong assertion or wrong fixture data):** fix the test; if the fix helps other tests, promote to the Page Object / fixture
- **Mode C (brittleness / flakiness):** fix the LIBRARY (Page Object, selector, retry logic), NOT the spec. Forbidden: `waitForTimeout(Ns)`, `retry(3)` at spec level, try/catch masking.

**If ≥3 library fixes happen during execution:** emit `output/l3/s209/LIBRARY_IMPROVEMENTS.md` as a closeout artifact listing each fix + rationale.

---

## Files to Create or Modify

### BEI-ERP repo (hrms)

| Action | File | MUST_MODIFY (appears in `git diff --name-only`) | MUST_CONTAIN (grep assertion) |
|---|---|---|---|
| CREATE | `scripts/s209_generate_fixture.py` | `scripts/s209_generate_fixture.py` | `"expected_buyer"`, `"customer_name = company"`, `"is_internal_customer=0"` |
| CREATE | `scripts/s209_grant_test_area_access.py` | `scripts/s209_grant_test_area_access.py` | `"custom_area_supervisor"`, `"test.area@bebang.ph"`, `"revert_path"` |
| CREATE | `scripts/s209_revert_test_area_access.py` | `scripts/s209_revert_test_area_access.py` | `"custom_area_supervisor"`, `"captured_state.json"` |
| CREATE | `scripts/s209_cleanup_sweep.py` | `scripts/s209_cleanup_sweep.py` | `"Sales Invoice"`, `"cancel"`, `"Stock Entry"`, `"Warehouse Receiving"`, `"BEI Store Order"`, `"reverse_order"` |
| CREATE | `scripts/s209_seed_inventory_for_variance.py` | `scripts/s209_seed_inventory_for_variance.py` | `"Stock Entry"`, `"Material Receipt"`, `"qty=10"`, `"qty=8"` |
| CREATE | `scripts/s209_verify_phase.py` | `scripts/s209_verify_phase.py` | `"phase"`, `"verify_canonical_structure"`, `"exit"` |
| CREATE | `output/l3/s209/SWEEP_VERIFICATION_SUMMARY.md` | `output/l3/s209/SWEEP_VERIFICATION_SUMMARY.md` | `"49/49"`, `"V1"`, `"V2"`, `"canonical preflight"`, `"canonical postcheck"` |
| CREATE | `output/l3/s209/sweep_ledger.json` | `output/l3/s209/sweep_ledger.json` | `"si-create"`, `"mr-create"`, `"pendingEntries"` |
| CREATE | `output/l3/s209/canonical_preflight.txt` | `output/l3/s209/canonical_preflight.txt` | `"CANONICAL OK"` |
| CREATE | `output/l3/s209/canonical_postcheck.txt` | `output/l3/s209/canonical_postcheck.txt` | `"CANONICAL OK"` |
| MODIFY | `docs/plans/SPRINT_REGISTRY.md` | `docs/plans/SPRINT_REGISTRY.md` | `S209` row + Next Sprint advanced to `S210` |
| MODIFY | `docs/plans/2026-04-20-sprint-209-all-stores-ordering-billing-acceptance.md` (this file) | this file | `status: COMPLETED`, `completed_date:` populated |

### bei-tasks repo

| Action | File | MUST_MODIFY | MUST_CONTAIN |
|---|---|---|---|
| MODIFY | `tests/e2e/fixtures/s204_all_stores.json` | `tests/e2e/fixtures/s204_all_stores.json` | 49 entries, `"allowEmptyTin": true` on ORTIGAS GREENHILLS only |
| MODIFY | `tests/e2e/pages/StoreOrderingPage.ts` | `tests/e2e/pages/StoreOrderingPage.ts` | `submitOrderWithExplicitQty` |
| MODIFY | `tests/e2e/pages/DispatchPage.ts` | `tests/e2e/pages/DispatchPage.ts` | `qty?: Map` or `qtyOverrides` |
| MODIFY | `tests/e2e/pages/ReceivingPage.ts` | `tests/e2e/pages/ReceivingPage.ts` | `acceptedQty?: Map`, `rejectedQty?: Map` |
| MODIFY | `tests/e2e/assertions/billingAssertions.ts` | `tests/e2e/assertions/billingAssertions.ts` | `allowEmptyTin`, `assertSIGLPartyIsCustomer` |
| CREATE | `tests/e2e/assertions/inventoryAssertions.ts` | `tests/e2e/assertions/inventoryAssertions.ts` | `assertInventoryDelta`, `tabStock Ledger Entry` |
| MODIFY | `tests/e2e/assertions/index.ts` | `tests/e2e/assertions/index.ts` | export `./inventoryAssertions` |
| CREATE | `tests/e2e/specs/s209-all-stores.spec.ts` | `tests/e2e/specs/s209-all-stores.spec.ts` | loops fixture, 49 test cases |
| CREATE | `tests/e2e/specs/s209-variance.spec.ts` | `tests/e2e/specs/s209-variance.spec.ts` | `V1`, `V2`, `short-receive`, `short-dispatch` |

---

## Phases

### Phase 0 — Preflight + Library Audit (6 units)

Agent Boot Sequence:
1. Read this plan fully.
2. Create sprint branch: `git fetch origin production && git checkout -b s209-all-stores-ordering-billing-acceptance origin/production` (hrms). Confirm the same for bei-tasks (`s209-all-stores-specs` from `origin/main`).
3. Run canonical preflight.
4. Capture `origin/production` HEAD SHA for both repos to `output/l3/s209/baseline_sha.txt`.

| ID | Unit | Task | MUST_MODIFY / MUST_CONTAIN | Source |
|---|---:|---|---|---|
| P0-T1 | 1 | Run `python scripts/verify_canonical_structure.py > output/l3/s209/canonical_preflight.txt` — assert contains `CANONICAL OK`, exit 0 | `output/l3/s209/canonical_preflight.txt` contains `CANONICAL OK` | This plan Preflight section |
| P0-T2 | 1 | Run `python scripts/canonical_resolver_live_check.py` — assert all 49 stores return `buyer_entity_status=confirmed_legal_entity` | stdout contains `49 stores passed` or equivalent | JSONL 10109 |
| P0-T3 | 1 | Capture baseline SHAs: `git rev-parse origin/production` (hrms + bei-tasks) → `output/l3/s209/baseline_sha.txt` | file exists with two SHAs | — |
| P0-T4 | 1 | Confirm all Page Objects / assertions / fixtures listed in Library Audit exist | grep output recorded in `output/l3/s209/library_audit.txt` | This plan Library Audit section |
| P0-T5 | 1 | Check `billingAssertions.ts` for an existing `assertSIGLPartyIsCustomer`; if present, skip the "add" task in Phase 2 | `tests/e2e/assertions/billingAssertions.ts` — grep `assertSIGLPartyIsCustomer` | — |
| P0-T6 | 1 | Write `scripts/s209_verify_phase.py` template (phase-parameterized); commit | File exists; takes `--phase N` arg | — |

**Phase 0 Exit gate:** `python scripts/s209_verify_phase.py --phase 0` exits 0.

### Phase 1 — Fixture regeneration (7 units)

| ID | Unit | Task | MUST_MODIFY / MUST_CONTAIN | Source |
|---|---:|---|---|---|
| P1-T1 | 2 | Write `scripts/s209_generate_fixture.py` — SSM-queries Frappe for every `Company.entity_category='Store' AND disabled=0`, joins canonical `Customer` (exact-name match), captures `{store, warehouse_docname, company, customer, tin, expectBillingHold, buyer_entity_status, parent_company, store_ownership_type, current_area_supervisor, allowEmptyTin}`. Script writes to both `tmp/s209_fixture.json` (local) and echoes JSON for stdout → pipe to `bei-tasks/tests/e2e/fixtures/s204_all_stores.json` | `scripts/s209_generate_fixture.py` exists | JSONL 9372 for schema |
| P1-T2 | 1 | Run the script, capture stdout; assert 49 entries | `tmp/s209_fixture_count.txt` contains `49` | — |
| P1-T3 | 1 | Copy fixture to bei-tasks repo: `cp tmp/s209_fixture.json F:/Dropbox/Projects/bei-tasks/tests/e2e/fixtures/s204_all_stores.json` | bei-tasks diff shows `s204_all_stores.json` modified | — |
| P1-T4 | 1 | Set `allowEmptyTin: true` ONLY on `ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC` entry; all others get `allowEmptyTin: false` | fixture grep `allowEmptyTin" : true` returns exactly 1 | JSONL 10109 |
| P1-T5 | 1 | Assert every entry except ORTIGAS GREENHILLS has non-empty `tin`; any other empty TIN = BLOCKER (fix master data via `scripts/canonical_probe_latest_si.py` first) | Python check: `sum(1 for e in d if e['tin'] == '' and 'ORTIGAS GREENHILLS' not in e['store']) == 0` | — |
| P1-T6 | 1 | Commit fixture + generator to their respective branches (hrms script, bei-tasks fixture) with `git add -f` since `.claude/` / `output/` may be gitignored but `scripts/` + `tests/` are not | two commits visible | S092 closeout rule |

**Phase 1 Exit gate:** `python scripts/s209_verify_phase.py --phase 1` exits 0.

### Phase 2 — Library extensions (11 units)

| ID | Unit | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---:|---|---|
| P2-T1 | 2 | Extend `pages/StoreOrderingPage.ts` — add `submitOrderWithExplicitQty(store, cargo, { items: Array<{code, qty}> }): Promise<{orderId, itemsFilled}>`. Reuses same `goToStore` + `selectCargo` flow; fills qty directly from param instead of reading `suggested_qty`. | `tests/e2e/pages/StoreOrderingPage.ts` — grep `submitOrderWithExplicitQty` |
| P2-T2 | 2 | Extend `pages/DispatchPage.ts` — `dispatch(mrName, itemsFilled, opts?: { qtyOverrides?: Map<string, number> })`. If `qtyOverrides` set, fill those qtys instead of `itemsFilled` defaults; otherwise backwards-compatible | `tests/e2e/pages/DispatchPage.ts` — grep `qtyOverrides` |
| P2-T3 | 2 | Extend `pages/ReceivingPage.ts` — `accept(mrName, itemsFilled, opts?: { acceptedQty?: Map<string, number>, rejectedQty?: Map<string, number>, rejectionReason?: string })`. Fills accepted + rejected fields per item when provided | `tests/e2e/pages/ReceivingPage.ts` — grep `acceptedQty`, `rejectedQty` |
| P2-T4 | 1 | Extend `assertions/billingAssertions.ts :: assertCompanyChainCorrect` to accept `{ allowEmptyTin?: boolean }`. When true, skip the TIN assertion (only for ORTIGAS GREENHILLS) | `tests/e2e/assertions/billingAssertions.ts` — grep `allowEmptyTin` |
| P2-T5 | 2 | Add `assertSIGLPartyIsCustomer(siName, expectedCustomer)` to `billingAssertions.ts` (if not present after Phase 0 check). Queries `tabGL Entry WHERE voucher_no=siName` via `frappeReadback`; asserts every debit row has `party_type=Customer AND party=expectedCustomer` | `tests/e2e/assertions/billingAssertions.ts` — grep `assertSIGLPartyIsCustomer` |
| P2-T6 | 1 | Create `assertions/inventoryAssertions.ts` with `assertInventoryDelta(warehouse, itemCode, expectedDelta, windowStart, windowEnd)`. Queries `tabStock Ledger Entry` via `frappeReadback` with posting_date filter | `tests/e2e/assertions/inventoryAssertions.ts` — grep `assertInventoryDelta`, `tabStock Ledger Entry` |
| P2-T7 | 1 | Export new assertion from `assertions/index.ts` | `tests/e2e/assertions/index.ts` — grep `inventoryAssertions` |

**Phase 2 Exit gate:** `python scripts/s209_verify_phase.py --phase 2` exits 0; bei-tasks `npm run typecheck` passes.

### Phase 3 — Happy-chain sweep spec (10 units)

| ID | Unit | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---:|---|---|
| P3-T1 | 1 | Write `scripts/s209_grant_test_area_access.py` — SSM script. For each of 49 warehouses, capture current `custom_area_supervisor` to `output/l3/s209/area_access_snapshot.json`, set to `test.area@bebang.ph`. Idempotent | `scripts/s209_grant_test_area_access.py` exists, grep `custom_area_supervisor`, `test.area@bebang.ph`, `area_access_snapshot.json` |
| P3-T2 | 1 | Write `scripts/s209_revert_test_area_access.py` — reads snapshot, restores each warehouse's original value | `scripts/s209_revert_test_area_access.py` exists, grep `area_access_snapshot.json` |
| P3-T3 | 3 | Write `tests/e2e/specs/s209-all-stores.spec.ts` — imports fixture JSON, runs `test.describe.serial("S209 — 49-store happy chain")` with one `test(name, fn)` per entry. Each test: submit DRY order at suggested qty (3 items) → area approve → SCM approve → dispatch all → receive all → assertCompanyChainCorrect({ allowEmptyTin: fixture.allowEmptyTin }) → assertSIGLPartyIsCustomer → record to ledger | `tests/e2e/specs/s209-all-stores.spec.ts` exists, 49 `test(` calls (grep count = 49), uses `StoreOrderingPage`, `OrderApprovalPage`, `DispatchPage`, `ReceivingPage`, `assertCompanyChainCorrect`, `assertSIGLPartyIsCustomer` |
| P3-T4 | 1 | Add pre-flight hook in spec: run `s209_grant_test_area_access.py` via `support/ssmSetup.ts` in `test.beforeAll`; run `s209_revert_test_area_access.py` in `test.afterAll` | spec grep `ssmSetup`, `grant_test_area_access`, `revert_test_area_access` |
| P3-T5 | 1 | Each test records `{store, orderId, mrName, siName, customer, tin, timestamp}` via `ledger.record('si-create', ...)` to `output/l3/s209/sweep_ledger.json` | spec grep `ledger.record`, `sweep_ledger.json` |
| P3-T6 | 1 | Spec fails fast if >3 consecutive stores fail (systemic issue per stop_only_for) | spec grep `consecutiveFailures`, `>= 3` |
| P3-T7 | 1 | Every test uses `data-testid` for order/approve/dispatch/receive controls; zero raw `button:has-text` in new spec; zero `page.request.*` / `fetch(` | spec grep `button:has-text` = 0, `page.request` = 0 |
| P3-T8 | 1 | Every test uses `loggedInAreaSupervisor`, `loggedInSCM`, `loggedInStoreSupervisor` fixtures (no manual login) | spec grep `loggedInAreaSupervisor`, `loggedInSCM`, `loggedInStoreSupervisor` |

**Phase 3 Exit gate:** `python scripts/s209_verify_phase.py --phase 3` exits 0; typecheck passes; dry-run (`npx playwright test --list tests/e2e/specs/s209-all-stores.spec.ts`) shows 49 tests enumerated.

### Phase 4 — Variance specs (V1 short-receive, V2 short-dispatch) (8 units)

| ID | Unit | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---:|---|---|
| P4-T1 | 1 | Write `scripts/s209_seed_inventory_for_variance.py` — SSM script that (a) ensures source warehouse has ≥10 of the target DRY item (Material Receipt stock entry) for V1, (b) reduces source to exactly 8 for V2. Reverts changes in teardown via a captured `inventory_snapshot.json` | `scripts/s209_seed_inventory_for_variance.py` exists, grep `qty=10`, `qty=8`, `inventory_snapshot.json`, `Stock Entry`, `Material Receipt` |
| P4-T2 | 3 | Write `tests/e2e/specs/s209-variance.spec.ts` — V1 (SM TANZA): `submitOrderWithExplicitQty({code, qty:10})` → dual approve → `dispatch(mr, items, { qtyOverrides: qty:10 })` → `accept(mr, items, { acceptedQty: 8, rejectedQty: 2, rejectionReason: "items missing in transit" })` → assert SI.total_items[0].qty == 8 (billed 8, not 10) → `assertInventoryDelta(source_warehouse, item, -10)` → `assertInventoryDelta(destination_warehouse, item, +8)` | `tests/e2e/specs/s209-variance.spec.ts` exists, grep `V1`, `SM TANZA`, `acceptedQty`, `rejectedQty`, `assertInventoryDelta`, `items missing in transit` |
| P4-T3 | 3 | V2 (AYALA VERMOSA): pre-hook runs `s209_seed_inventory_for_variance.py --scenario V2` → `submitOrderWithExplicitQty({code, qty:10})` → dual approve → `dispatch(mr, items, { qtyOverrides: qty:8 })` (UI must allow dispatched < ordered) → `accept(mr, items, { acceptedQty: 8 })` → assert SI.total_items[0].qty == 8 (billed dispatched, not ordered) → `assertInventoryDelta(source_warehouse, item, -8)` → `assertInventoryDelta(destination_warehouse, item, +8)` | spec grep `V2`, `AYALA VERMOSA`, `qtyOverrides`, `dispatched < ordered`, `-8` |
| P4-T4 | 1 | Post-hook reverts inventory seed; records SI to sweep_ledger for cleanup | spec grep `inventory_snapshot.json` revert, `ledger.record('si-create'` |

**Phase 4 Exit gate:** `python scripts/s209_verify_phase.py --phase 4` exits 0; spec dry-run shows 2 tests enumerated.

### Phase 5 — Execution + evidence (8 units)

| ID | Unit | Task |
|---|---:|---|
| P5-T1 | 1 | Deploy bei-tasks branch `s209-all-stores-specs` to Vercel preview; verify preview URL loads |
| P5-T2 | 4 | Run `npx playwright test tests/e2e/specs/s209-all-stores.spec.ts` against production (hq.bebang.ph) with `EVIDENCE_ROOT=F:/Dropbox/Projects/BEI-ERP/output/l3/s209` — 49 iterations × ~90s ≈ 75 min |
| P5-T3 | 1 | Run `npx playwright test tests/e2e/specs/s209-variance.spec.ts` — 2 iterations |
| P5-T4 | 1 | Write `output/l3/s209/form_submissions.json` (per-test form snapshots from evidence fixture) |
| P5-T5 | 1 | Write `output/l3/s209/api_mutations.json` (network recorder capture, filtered to POST/PATCH/DELETE on Frappe endpoints) |

**Phase 5 Exit gate:** 49/49 HC-* tests PASS + V1 PASS + V2 PASS; if any fail, trigger Failure Response classification.

### Phase 6 — Cleanup + closeout (9 units)

| ID | Unit | Task |
|---|---:|---|
| P6-T1 | 2 | Write `scripts/s209_cleanup_sweep.py` — reads `sweep_ledger.json`, groups entries by doctype in reverse-dependency order (SI → SE → WR → MR → BEI Store Order), calls `frappe.get_doc(dt, name).cancel()` for submitted docs and `delete()` for draft. Reverses GL via Frappe's native `cancel` flow (never ad-hoc SQL on `tabGL Entry`). |
| P6-T2 | 2 | Run cleanup script. Assert `ledger.pendingEntries === 0` post-run. If any cancel fails, STOP and ask Sam (cannot leave hanging GL). |
| P6-T3 | 1 | Run `python scripts/s209_revert_test_area_access.py` — restores original `custom_area_supervisor` values on all touched warehouses. |
| P6-T4 | 1 | Run `python scripts/s209_seed_inventory_for_variance.py --revert` — restores pre-V1/V2 inventory state. |
| P6-T5 | 1 | Run `python scripts/verify_canonical_structure.py > output/l3/s209/canonical_postcheck.txt` — MUST show `CANONICAL OK`. Diff vs preflight; zero structural changes. |
| P6-T6 | 1 | Write `output/l3/s209/SWEEP_VERIFICATION_SUMMARY.md` — one row per store showing SI docname, customer, company, TIN, VAT rate, GL party correctness, inventory delta (if applicable); V1 + V2 results; canonical drift diff. |
| P6-T7 | 1 | Update plan YAML: `status: GO → COMPLETED`, `completed_date: 2026-04-20`, `execution_summary: "49/49 HC + 2/2 V; 51 SIs cancelled; canonical zero-drift."` Update `SPRINT_REGISTRY.md` S209 row to COMPLETED with PR numbers. `git add -f docs/plans/...` + `git add docs/plans/SPRINT_REGISTRY.md`. |

**Phase 6 Exit gate:** `python scripts/s209_verify_phase.py --phase 6` exits 0; PR created on hrms + bei-tasks.

---

## Sentry Observability (DM-7 check)

S209 does NOT add new `@frappe.whitelist()` endpoints. The workflow it exercises goes through existing endpoints (`submit_order`, `approve_order`, `create_material_request_from_order`, `dispatch_material_request`, `complete_warehouse_receiving`, `create_sales_invoice_from_wr`) all of which already have `set_backend_observability_context()` calls per prior sprints. S209 adds ONE new whitelisted helper in `scripts/s209_cleanup_sweep.py` — the cleanup script runs via SSM as Administrator, NOT as a whitelisted endpoint, so no Sentry context required.

Add to RRC:
- [ ] RR-16 — No new Sentry errors in the `bei-hrms` project tagged `module=commissary|warehouse|billing` during the sweep window (already in RRC above)

---

## Status Reconciliation Contract

When Phase 6 closes, update in the same work unit:
1. `output/l3/s209/SWEEP_VERIFICATION_SUMMARY.md`
2. `output/l3/s209/sweep_ledger.json` (must show `pendingEntries: 0`)
3. `docs/plans/2026-04-20-sprint-209-all-stores-ordering-billing-acceptance.md` (this file — YAML metadata)
4. `docs/plans/SPRINT_REGISTRY.md` (S209 row → COMPLETED)
5. PR description on both hrms + bei-tasks PRs

---

## Review Gates (before COMPLETED)

- [ ] `rg 'page\.request|fetch\(' F:/Dropbox/Projects/bei-tasks/tests/e2e/specs/s209-*.spec.ts` returns 0
- [ ] `rg 'page\.click\("button:has-text|page\.locator\("button' F:/Dropbox/Projects/bei-tasks/tests/e2e/specs/s209-*.spec.ts` returns 0
- [ ] `rg 'waitForTimeout|retry\(3\)' F:/Dropbox/Projects/bei-tasks/tests/e2e/specs/s209-*.spec.ts` returns 0
- [ ] Every spec uses at least one `loggedInAs*` fixture
- [ ] `cleanupLedger.pendingEntries === 0` asserted in `afterEach` passes
- [ ] `git diff --name-only origin/production...HEAD` on hrms shows only the "Files to Create or Modify" hrms rows
- [ ] `git diff --name-only origin/main...HEAD` on bei-tasks shows only the "Files to Create or Modify" bei-tasks rows
- [ ] All `output/l3/s209/verify_phase{0..6}.py` return exit 0
- [ ] All 20 RR items checked `[x]`
- [ ] PR #hrms and PR #bei-tasks open and ready for Sam to merge
- [ ] `canonical_postcheck.txt` shows `CANONICAL OK`

---

## Execution Workflow

- Test Python changes locally (optional): `/local-frappe`
- Agent runs `/agent-kickoff` with this plan
- PR-handoff workflow per BEI rules: agent creates PRs → STOPS → Sam merges

---

## Execution Authority

This sprint is intended for autonomous end-to-end execution. Do not stop for progress-only updates. Only pause for items listed in the `stop_only_for` section of the Autonomous Execution Contract.

*Plan authored 2026-04-20 (Monday) PHT from session JSONL `a8898593-fd37-4b4b-be40-e619400da7e3`. All factual claims trace to cited JSONL line numbers or live file reads during plan authorship.*
