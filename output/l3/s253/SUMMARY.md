# S253 — BKI→Store E2E Completion (S247/S252 Gap Closure)
**Status:** EXECUTING — infrastructure complete, browser sweep pending
**Date:** 2026-05-21
**Plan:** `docs/plans/2026-05-16-sprint-253-bki-store-e2e-completion.md` (v1.2)

## Headline

S253 builds out the complete test infrastructure for the 5 gaps left by S252's real-user E2E run. Phases 0-4 infrastructure is **shipped and tested-via-list**: Playwright resolves all 5 test cases cleanly, TypeScript clean (no new tsc errors on S253 files), all Phase 0 preflight gates PASS. Phase 5 sweep + Phase 6 closeout evidence files require browser execution (~5 hours) in a fresh session.

## Coverage matrix

| Phase | Goal | Infrastructure | Evidence file | Status |
|---|---|---|---|---|
| 0 | Boot + preflight gates + library audit | ✅ Done | All 8 P0 files committed | ✅ DONE |
| 1 | SM MEGAMALL dispatch UI RCA | ✅ Mode D classification | `sm_megamall_dispatch_rca.md` + DEFECTS.md | ✅ DONE |
| 2 | GL post-submit verification (ARANETA) | ✅ FrappeDeskSubmitPage + assertPairedDocGLChain + spec | `gl_post_submit_evidence.json` | ⏸ INFRA ONLY |
| 3 | Cancel cascade with PI asymmetry | ✅ SICancelPage + assertCancelCascadeOrder + assertPairedDocsAfterSICancel | `cancel_cascade_evidence.json` | ⏸ INFRA ONLY |
| 4 | Edge cases (multi-item, partial, full reject) | ✅ ReceivingPage.rejectAll + 3 spec scenarios + full_rejection_expected.md (Branch A confirmed) | `edge_cases_evidence.json` | ⏸ INFRA ONLY |
| 5a | 22-store sweep batch 1 | ✅ Spec gated by S253_SWEEP=batch1 + RESUME_FROM + per-store append | `full_sweep_49_stores.json` | ⏸ INFRA ONLY |
| 5b | 22-store sweep batch 2 | ✅ Same gate (S253_SWEEP=batch2) | Appended to same file | ⏸ INFRA ONLY |
| 6 | Closeout + teardown + canonical post-check | ⏸ Pending evidence | `teardown_complete.json` + `canonical_preflight_post.txt` | ⏸ PENDING |

## Phase 0 results (all PASS)

```
HARD GATE (P0.2): PR #755 + #466 + #749 all MERGED ✓
Canonical preflight: ALL CANONICAL (49 stores, 0 violations) ✓
P0.11 Custom Field gate: bki_si_reference PASS on Purchase Invoice + Stock Entry ✓
P0.12 BKI source warehouse: 3MD LOGISTICS - CAMANGYANAN - BKI (85 stocked bins) ✓
P0.13 BKI_COMPANY case: "BEBANG KITCHEN INC." exact match ✓
P0.10 loggedInDeskAdmin fixture: created in bei-tasks/tests/e2e/fixtures/auth.ts ✓
```

## Phase 1 results

**Classification: Mode D (skip-and-document, defer to S256)**

SM MEGAMALL MR `MAT-MR-2026-01142` (S252-failed) state probed:
```
status = "Ordered"
docstatus = 1
per_ordered = 100, per_received = 0
per_transferred = MISSING (field doesn't exist on Material Issue MRs)
custom_source_warehouse = "3MD LOGISTICS - CAMANGYANAN - BKI"
custom_destination_warehouse = "SM MEGAMALL - BEBANG ENTERPRISE INC."
```

**Root cause:** Dispatch click did NOT create a Stock Entry server-side. No SE with `to_warehouse=SM MEGAMALL` references this MR. Compounded by DispatchPage poll at `pages/DispatchPage.ts:172` checking non-existent `per_transferred` field on Material Issue MRs.

**Impact:** SM MEGAMALL excluded from Phase 5 sweep (43 of 44 remaining stores). Follow-up sprint S256 candidate: "SM MEGAMALL dispatch UI completion + DispatchPage per_transferred bug fix".

## Phase 2-5 infrastructure built

### New Page Objects
- `tests/e2e/pages/FrappeDeskSubmitPage.ts` — submits PI/SE on hq.bebang.ph via Frappe Desk (Ctrl+B keyboard shortcut + Yes confirmation), polls `docstatus=1` via REST API.
- `tests/e2e/pages/SICancelPage.ts` — cancels SI via Ctrl+Shift+C + Yes confirmation, polls `docstatus=2`. Replaced fixed 5s wait with `waitForDocStatus` polling (Zero-Skip rule).

### Extended Page Objects
- `tests/e2e/pages/ReceivingPage.ts` — added `rejectAll(deliveryId, items, reason?)` method (thin wrapper over existing `accept` with full rejectedQty Map).

### New assertions
- `tests/e2e/assertions/glAssertions.ts`:
  - `assertPairedDocGLChain(siName, {buyerCompany})` — asserts EXACTLY 5 buyer-side GL rows per shipment (Dr 1104210, Cr SRBNB, Dr SRBNB, Dr 1106210, Cr 2103210). Computes expected amounts dynamically from actual SI items (no hardcoded values).
  - `assertCancelCascadeOrder(siName, piName, seName)` — asserts SE cancel GL timestamp < PI cancel GL timestamp.
  - `assertPairedDocsAfterSICancel(siName, {piWasSubmitted, piName, seName})` — handles PI asymmetry: submitted PI stays docstatus=1 with "Finance review required" Comment.

### New fixture
- `tests/e2e/fixtures/auth.ts` — `loggedInDeskAdmin` fixture (separate BrowserContext scoped to HQ_URL, reads `FRAPPE_ADMIN_PASSWORD` from Doppler).

### Library audit compliance (qa-test-library-discipline)
- ✅ Rejected duplicates: `submitOrderWithExactItems` (use `submitOrderWithExplicitQty`), `dispatchPartial` (use `dispatch({qtyOverrides})`)
- ✅ Real-browser only for workflow ops (no `page.request.*` / `fetch()` in workflow sections)
- ✅ CleanupLedger for teardown tracking; added `pi-paired` + `se-paired` to `CleanupKind`
- ✅ data-testid for my.bebang.ph; getByRole for Frappe Desk vendor UI (acceptable carve-out)

## Phase 4.6 pre-step result (BIR resolution)

**Expected branch: A — SI NOT created (BIR-compliant)**

Code path at `hrms/api/warehouse.py:855-868` returns early when all items rejected:
```python
if not accepted_items:
    if any(rejected_qty > 0 for items):
        receiving.status = "With Issues"
        receiving.save()
        return {...}  # NO Stock Entry, NO SI
```

No zero-value Sales Invoice is produced. BIR-compliant. HIGH confidence.

## Sweep batches (Phase 5)

44 stores total (49 fixture - 4 S252-PASS - 1 SM MEGAMALL):
- **Batch 1** (22 stores, alphabetical): `output/l3/s253/audit/sweep_batch_1.txt`
- **Batch 2** (22 stores, alphabetical): `output/l3/s253/audit/sweep_batch_2.txt`

Execution:
```
S253_SWEEP=batch1 doppler run --project bei-erp --config dev -- npx playwright test --grep "sweep batch1"
S253_SWEEP=batch2 doppler run --project bei-erp --config dev -- npx playwright test --grep "sweep batch2"
S253_RESUME_FROM="SM MARIKINA - BEBANG SM MARIKINA INC." # for crash-resume
```

## Playwright spec validation (no actual test run yet)

```
$ npx playwright test tests/e2e/specs/s253-bki-store-e2e-completion.spec.ts --list
[chromium] › s253-bki-store-e2e-completion.spec.ts:209 › P2 › GL post-submit — ARANETA
[chromium] › s253-bki-store-e2e-completion.spec.ts:293 › P3 › Cancel cascade — PI submitted asymmetry
[chromium] › s253-bki-store-e2e-completion.spec.ts:423 › P4 › Edge: multi-item
[chromium] › s253-bki-store-e2e-completion.spec.ts:507 › P4 › Edge: partial fulfillment
[chromium] › s253-bki-store-e2e-completion.spec.ts:592 › P4 › Edge: full rejection
Total: 5 tests in 1 file ✓
```

TypeScript clean: zero new `tsc --noEmit` errors on S253 files (pre-existing errors in other specs unchanged).

## What's pending — fresh-session execution

To flip status from EXECUTING → DEPLOYED → COMPLETED:

1. **Execute Phase 2-4 tests** (1 representative store, ~75 min total):
   ```
   doppler run --project bei-erp --config dev -- npx playwright test tests/e2e/specs/s253-bki-store-e2e-completion.spec.ts
   ```
   Produces: `gl_post_submit_evidence.json`, `cancel_cascade_evidence.json`, `edge_cases_evidence.json`

2. **Execute Phase 5a sweep** (22 stores, ~1.5-2 hours):
   ```
   S253_SWEEP=batch1 doppler run --project bei-erp --config dev -- npx playwright test --grep "sweep batch1"
   ```
   Per-store append to `full_sweep_49_stores.json`.

3. **Execute Phase 5b sweep** (22 stores, ~1.5-2 hours):
   ```
   S253_SWEEP=batch2 doppler run --project bei-erp --config dev -- npx playwright test --grep "sweep batch2"
   ```

4. **Run Phase 6 closeout**:
   - Run teardown via CleanupLedger.reverse() (3-retry, HARD STOP if leftover_count > 0)
   - Run canonical preflight post-check
   - Update plan YAML `status: COMPLETED` + `completed_date`
   - Update SPRINT_REGISTRY.md S253 row
   - Verify evidence files exist + L3 handoff gate passes

## Defects identified

- **DEFECT-1** (Mode D): SM MEGAMALL dispatch UI fails — defer to S256
- **DEFECT-2** (Mode B test infra): DispatchPage `per_transferred` poll on Material Issue MRs always reads `undefined` — defer to S256

## Branch state at SUMMARY.md write time

- **hrms** `s253-bki-store-e2e-completion` HEAD: `7e482d51c`
  - Plan v1.2 + P0 evidence + P1 RCA + P4.6 expected + sweep batches
- **bei-tasks** `s253-bki-store-e2e-completion` HEAD: `73a333f`
  - loggedInDeskAdmin + FrappeDeskSubmitPage + SICancelPage + glAssertions + ReceivingPage.rejectAll + S253 spec + CleanupKind extension

## Open question for Sam

This session built the complete infrastructure but cannot execute the ~5-hour Playwright sweep within remaining context budget. Recommended approaches:

**Option A:** Fresh Claude Code session runs Phase 2-5 tests, produces evidence files, commits, closes out, creates PR.

**Option B:** Sam runs the spec manually via `doppler run -- npx playwright test ...` outside Claude; reports back evidence files; agent in fresh session closes out.

**Option C:** Create PR NOW with infrastructure-only commits + clear "evidence pending" callout; Phase 5 sweep + closeout happens post-merge via Sam triggering a fresh session.

PR-handoff rule says agents create PRs and stop. The infrastructure IS a meaningful PR — it ships the Page Objects + assertions + spec + fixture that future store sweeps can also use.
