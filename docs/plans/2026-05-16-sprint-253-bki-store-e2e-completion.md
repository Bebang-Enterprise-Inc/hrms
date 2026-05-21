---
sprint: S253
sprint_title: "BKI→Store E2E Completion — S247/S252 Gap Closure"
plan_filename: 2026-05-16-sprint-253-bki-store-e2e-completion.md
branch_hrms: s253-bki-store-e2e-completion
branch_bei_tasks: s253-bki-store-e2e-completion
target_base_branch_hrms: production
target_base_branch_bei_tasks: main
canonical_scope: in
canonical_model_reference: docs/STORE_COMPANY_CANONICAL.md
canonical_preflight: required
status: EXECUTING_INFRA_DONE
planned_date: 2026-05-16
completed_date: null
execution_summary: |
  2026-05-21 — Phases 0+1 complete + Phases 2-5 infrastructure complete +
  Phase 4.6 pre-step complete + Phase 5 sweep batches enumerated.
  All Page Objects (FrappeDeskSubmitPage, SICancelPage, loggedInDeskAdmin
  fixture), assertions (assertPairedDocGLChain, assertCancelCascadeOrder,
  assertPairedDocsAfterSICancel), and spec (5 tests resolve via Playwright
  --list) shipped. Phase 1 SM MEGAMALL classified Mode D (defer to S256).
  TypeScript clean on all S253 files. PENDING: ~5-hour browser execution
  to produce gl_post_submit_evidence.json + cancel_cascade_evidence.json +
  edge_cases_evidence.json + full_sweep_49_stores.json. Run via:
  `doppler run --project bei-erp --config dev -- npx playwright test
   tests/e2e/specs/s253-bki-store-e2e-completion.spec.ts`
  then S253_SWEEP=batch1|batch2 for the 44-store sweep. After evidence
  produced + teardown clean + canonical post-preflight passes, flip
  status to DEPLOYED then COMPLETED.
depends_on:
  - hrms PR #755 (S252 evidence) MERGED to production — provides the canonical S252 evidence files in `output/l3/s252/` for cross-reference
  - bei-tasks PR #466 (S252 Playwright spec) MERGED to main — provides the base `s252-bki-store-paired-doc-e2e.spec.ts` that S253 extends + the StoreOrderingPage/OrderApprovalPage/DispatchPage/WarehouseApprovalPage/ReceivingPage Page Objects
  - hrms PR #749 (S247 closeout incl. hooks.py dedupe hotfix) MERGED — Stock Entry validate hook + SE generator already on production
signoff_authority: single-owner
signoff_owner: Sam Karazi (CEO)
phase_count: 7
work_unit_estimate: ~74
work_unit_ceiling: 80

evidence_committed:
  - output/l3/s253/SUMMARY.md
  - output/l3/s253/DEFECTS.md
  - output/l3/s253/teardown_ledger.json
  - output/l3/s253/teardown_complete.json
  - output/l3/s253/form_submissions.json
  - output/l3/s253/api_mutations.json
  - output/l3/s253/state_verification.json
  - output/l3/s253/verification/sm_megamall_dispatch_rca.md
  - output/l3/s253/verification/gl_post_submit_evidence.json
  - output/l3/s253/verification/cancel_cascade_evidence.json
  - output/l3/s253/verification/edge_cases_evidence.json
  - output/l3/s253/verification/full_sweep_49_stores.json
  - output/l3/s253/verification/canonical_preflight_baseline.txt
  - output/l3/s253/verification/canonical_preflight_post.txt
  - output/l3/s253/verification/custom_field_gate.json
  - output/l3/s253/verification/bki_company_case.json
  - output/l3/s253/state/ACTIVE_RUN.json
  - output/l3/s253/state/REMOTE_TRUTH_BASELINE.json
  - output/l3/s253/state/SURFACE_OWNERSHIP_MATRIX.csv
  - output/l3/s253/audit/library_audit.md
  - output/l3/s253/audit/bki_source_inventory.json
  - output/l3/s253/audit/full_rejection_expected.md
  - output/l3/s253/audit/sweep_batch_1.txt
  - output/l3/s253/audit/sweep_batch_2.txt

evidence_transient:
  - tmp/s253/sweep_run_*.log
  - tmp/s253/probe_*.json
  - tmp/s253/traceback_*.txt
  - tmp/s253/playwright_trace_*.zip
  - tmp/s253/dispatch_diag_*.json
---

## Sprint Metadata

| Field | Value |
|---|---|
| Canonical ID | `S253` |
| Branch (hrms) | `s253-bki-store-e2e-completion` |
| Branch (bei-tasks) | `s253-bki-store-e2e-completion` |
| Target base (hrms) | `origin/production` |
| Target base (bei-tasks) | `origin/main` |
| Worktree (hrms) | `F:/Dropbox/Projects/BEI-ERP-s253-bki-store-e2e-completion` |
| Worktree (bei-tasks) | `F:/Dropbox/Projects/bei-tasks-s253-bki-store-e2e-completion` |
| Status | PLANNED |

## Goal

Close all 5 gaps left open by S252 (PR #755 / #466) — produce **comprehensive real-user E2E coverage** of the S247 Option 3-corrected BKI→Store paired-doc flow with NO corner cutting:

1. **Fix or document the SM MEGAMALL dispatch UI bug** (the 1-of-5 failure from S252)
2. **PI + SE submit → GL post-submit verification** (S252 only checked Drafts)
3. **Cancel cascade via UI** (S252 only checked creation)
4. **Edge cases** — multi-item / partial fulfillment / full rejection
5. **Extend browser-level coverage to all 49 stores** (S252 covered 5; this sprint adds the remaining 44)

## Design Rationale (For Cold-Start Agents)

### Why this exists

S252 (PR #755) was the first real-browser E2E for the S247 Option 3-corrected paired-doc flow. It passed 4 of 5 representative stores (ARANETA, NAIA T3, SM TANZA, XENTROMALL MONTALBAN). 1 store failed (SM MEGAMALL — DispatchPage timeout) on a pre-existing dispatch UI issue, NOT a S247 regression.

Sam asked on 2026-05-12: "did you test all stores end to end like a real user using the test scripts that we have without any corner cutting to validate that all data is accurate and properly generated etc..."

S252 answered with 4/5 PASS but ALSO explicitly documented remaining gaps:
1. PI + SE **submit → GL post** not verified (assertions on Draft docs only)
2. Cancel cascade via **UI** not exercised (creation-only)
3. **Multi-item / partial / return** edge cases not covered
4. **Remaining 44 stores** at browser level not covered (only S247 P5 backend smoke)

This sprint closes all four documented gaps PLUS resolves the SM MEGAMALL fail.

### Why this architecture (gap-closure-first, not a from-scratch rewrite)

Considered: rewrite all 49-store E2E coverage in one comprehensive spec. Rejected because:
- S252 already validates the paired-doc creation chain works correctly for 4 different legal-entity types
- The S247 hook chain is uniform (same code fires for every store regardless of ownership type)
- Rewriting would force re-doing work already proven

Chosen approach: extend S252's spec to add the missing assertions (GL post-submit, cancel-via-UI, edge cases) THEN run the same coverage across the remaining 44 stores. Reuses existing Page Objects (StoreOrderingPage, OrderApprovalPage, DispatchPage, WarehouseApprovalPage, ReceivingPage) and fixtures (loggedIn*, CleanupLedger).

### Key trade-off decisions

**Decision 1: SI cancel via Frappe Desk UI on hq.bebang.ph (NOT via my.bebang.ph or API).**
The BKI Sales Invoice lives on hq.bebang.ph (Frappe Desk), not my.bebang.ph (the operator portal). Finance team manually cancels SIs in Frappe Desk in production. The L3 test must follow the SAME path. Test account: `Administrator` (sole user with SI cancel permission on BKI's books). URL: `https://hq.bebang.ph/app/sales-invoice/{si_name}` → click "Menu" → "Cancel".

**Decision 2: PI + SE submit via Frappe Desk UI as Administrator (NOT via API).**
Per L3-v2 rule "submit must come from browser UI actions" — for the production finance workflow, this is Frappe Desk on hq.bebang.ph. The two-doc submit sequence is: open the PI → click Submit; then open the SE → click Submit. GL entries post automatically on submission.

**Decision 3: 49-store sweep uses sequential execution (not parallel).**
S209 + S252 set `workers=1, fullyParallel=false`. S253 inherits this. Reasons: (a) shared test fixtures (test.area, test.scm, test.supervisor accounts) can't have concurrent sessions; (b) sequential makes failure attribution clean; (c) cleanup ledger needs serial guarantee.

**Decision 4: SM MEGAMALL fix categorisation — investigate first, classify after.**
We don't yet know whether SM MEGAMALL's dispatch timeout is (a) a product bug in the dispatch hook, (b) a master-data issue on SM MEGAMALL specifically, or (c) a flaky DispatchPage waitForToast pattern. Phase 1 investigates via Frappe Error Log + dispatch code path read + side-by-side comparison with a working store. Classification:
- Mode A (app bug): file as DEFECTS.md entry, write fix on hrms repo, re-run
- Mode B (test bug): fix DispatchPage in bei-tasks repo
- Mode C (master data): fix via `/frappe-bulk-edits`
- If 30 minutes investigation yields nothing: skip SM MEGAMALL from full-sweep, document as "known-blocker single-store skip" with `[UNVERIFIED — requires resolution]` until separate sprint

### Known limitations + mitigations

**Limitation 1: 49-store sweep duration.**
Each store takes ~5 min for the full chain (login + order + dual approval + dispatch + receive + paired-doc verify). 49 stores × 5 min = ~4 hours of test runtime. Mitigation: P5 runs as a separate Playwright invocation with extended global timeout; agent commits per-phase before starting P5 so a mid-sweep crash doesn't lose Phases 1-4.

**Limitation 2: Edge case execution requires non-default item quantities.**
Multi-item scenarios need 5+ items in the order. Partial fulfillment needs different dispatched_qty vs accepted_qty. Full rejection needs all items rejected. Each requires PageObject extensions: `StoreOrderingPage.submitOrderWithExactItems(items)`, `DispatchPage.dispatchPartial(mr, qtyMap)`, `ReceivingPage.rejectAll(wr)`. These extensions become "library contributions" per qa-test-library-discipline.

**Limitation 3: GL read happens via Frappe REST API (read-only).**
Per L3-v2 rule, workflow ops via browser ONLY. GL verification is read-only verification AFTER the workflow completes via UI — explicitly allowed. Auth: `FRAPPE_API_KEY` + `FRAPPE_API_SECRET` from Doppler.

**Limitation 4: Cleanup of edge-case test data may produce orphan GL entries.**
Cancelling submitted PI + SE reverses their JEs. If the cancel cascade has any bug, orphan GL entries may remain. Phase 6 closeout verifies via `tabGL Entry` query — any entry referencing a cancelled doc whose corresponding reversal is missing → DEFECTS.md entry.

### Source references

- `output/l3/s252/SUMMARY.md` — S252 closeout summary with the 4 remaining gaps named
- `output/l3/s252/recovery_evidence.json` — S252 evidence baseline (4 PASS rows)
- `output/l3/s252/paired_doc_evidence.json` — S252 Playwright run output
- `tests/e2e/specs/s252-bki-store-paired-doc-e2e.spec.ts` (bei-tasks PR #466) — base spec S253 extends
- `tests/e2e/pages/{StoreOrderingPage,OrderApprovalPage,DispatchPage,WarehouseApprovalPage,ReceivingPage}.ts` — existing Page Objects
- `tests/e2e/fixtures/s204_all_stores.json` — 49-store fixture data
- `tests/e2e/support/frappeReadback.ts` — REST API readback helper (queryDocs, readDoc)
- `hrms/api/bki_store_pi_generator.py` (origin/production) — PI generator + cascade hook
- `hrms/api/bki_store_stock_entry_generator.py` (origin/production) — SE generator + cascade hook
- `hrms/hooks.py:220-240` — Sales Invoice on_submit / on_cancel hook chain
- `hrms/api/dispatch.py` (or equivalent) — dispatch endpoint that triggers SI creation
- `scripts/s209_grant_test_area_access.py` — preflight to grant test.area on all 49 warehouses
- `scripts/s252_recover_evidence.py` — pattern for SSM-based evidence recovery
- `docs/STORE_COMPANY_CANONICAL.md` — canonical store/company model

## Requirements Regression Checklist

Every yes/no the executing agent must verify against its own work before marking a phase complete:

- [ ] Did Phase 0 spawn a worktree at `F:/Dropbox/Projects/BEI-ERP-s253-bki-store-e2e-completion` from `origin/production` (NOT `git checkout -b` in main checkout)?
- [ ] Did Phase 0 spawn a SECOND worktree at `F:/Dropbox/Projects/bei-tasks-s253-bki-store-e2e-completion` from `origin/main`?
- [ ] Did Phase 0 verify hrms PR #755 + bei-tasks PR #466 + hrms PR #749 are all MERGED before starting? (HARD GATES)
- [ ] Did Phase 0 run `python scripts/verify_canonical_structure.py` and capture baseline output?
- [ ] Did Phase 1 produce `output/l3/s253/verification/sm_megamall_dispatch_rca.md` with the failure classification (Mode A / B / C / skip-and-document)?
- [ ] Did Phase 2's GL verification assertion check ALL 5 buyer-side GL rows per shipment? Exactly: (1) Dr `1104210 Inventory-from-Commissary` = SE.basic_rate × qty (SE submit), (2) Cr `SRBNB` = same amount (SE submit), (3) Dr `SRBNB` = same amount (PI submit, clears row 2), (4) Dr `1106210 Input VAT BKI Inter-Co` = tax amount (PI submit), (5) Cr `2103210 AP-Trade-BKI` = qty × rate + tax amount (PI submit). Filter `tabGL Entry` by buyer Company before counting.
- [ ] Did Phase 3's cancel verification check SE-cancellation-before-PI-cancellation timestamp order in `tabGL Entry.creation`?
- [ ] Did Phase 4 cover all 3 edge cases: multi-item (5+ items), partial fulfillment (dispatched < ordered), full rejection (all items rejected on receive)?
- [ ] Did Phase 5 run against all stores in `s204_all_stores.json` EXCEPT the 5 from S252 STORE_FILTER (= 44 stores)?
- [ ] Did closeout phase produce `output/l3/s253/teardown_complete.json` confirming `leftover_count == 0` (NOT just file exists)? HARD STOP if leftover_count > 0 after 3 teardown retries.
- [ ] Did Phase 0 verify `bki_si_reference` Custom Field exists on both `Purchase Invoice` and `Stock Entry` via `frappe.db.has_column()`? HARD STOP if missing.
- [ ] Did Phase 0 create `loggedInDeskAdmin` fixture in `bei-tasks/tests/e2e/fixtures/auth.ts` with `FRAPPE_ADMIN_PASSWORD` from Doppler `bei-erp/dev`?
- [ ] Did Phase 0 SSM-discover canonical BKI source warehouse + 5 distinct DRY items with `actual_qty ≥ 10` and persist to `output/l3/s253/audit/bki_source_inventory.json`?
- [ ] Does every new/modified `@frappe.whitelist()` endpoint call `set_backend_observability_context()` per `.claude/rules/sentry-observability.md`?
- [ ] Did closeout run `python scripts/verify_canonical_structure.py` AND assert zero NEW violations vs baseline?
- [ ] Did `rg 'page\.request\.|fetch\(\)' tests/e2e/specs/s253*` return 0 hits in workflow sections (read-only API verification allowed)?
- [ ] Was the worktree (both repos) removed cleanly at the end (no leftover `git status` output)?

## Canonical Model Preflight (Mandatory)

Executing agent MUST run before the first code change:
```bash
python scripts/verify_canonical_structure.py
```
If the verifier prints `[VIOLATION]`, STOP and ask the user. Do NOT add records, flip fields, or create customers/warehouses to paper over a violation — fix the master data with the canonical scripts.

**Canonical law (summary — full rules in `docs/STORE_COMPANY_CANONICAL.md`):**
- Every store has EXACTLY 1 per-store Company + 1 Warehouse + 1 billing Customer + 1 Internal Customer.
- All four share the same name string (e.g. `SM TANZA - BEBANG MEGA INC.`).
- Per-store Company's `parent_company` links to the legal entity parent (if any).
- Warehouse.company = the per-store Company (NEVER the parent).
- Billing Customer: `customer_name` = per-store Company name, `is_internal_customer=0`, `tax_id` = legal entity BIR TIN.
- Internal Customer: `represents_company` = per-store Company, `is_internal_customer=1`, no TIN. Used by S206 labor journals ONLY — never for regular SIs.

**Forbidden in this plan (without explicit CEO approval in-line):**
- Creating a second Warehouse/Company/Customer for an existing store.
- Ad-hoc SQL mutations on `tabCompany` / `tabWarehouse` / `tabCustomer`.
- Adding new fallback logic to `resolve_store_buyer_entity`.
- Using the parent Company's Customer for store-level billing (breaks per-store P&L).
- Reusing an Internal Customer for a regular SI.
- Deleting a master record with transactions (use `disabled=1`).

**Scope claim:** This sprint READS every per-store Company, Warehouse, Customer, Supplier, and Account on all 49 stores during Phase 5 sweep. This sprint WRITES test transactions ONLY (Sales Invoice + Purchase Invoice + Stock Entry + their cascaded JEs) — all teardown-tracked via cleanupLedger fixture + closeout teardown phase. NO master-data mutations (no Company/Warehouse/Customer changes). Test SIs / PIs / SEs are tracked + cancelled + force-deleted at closeout.

## Canonical Model Binding

This sprint binds to the canonical model as follows:
- Reads `Warehouse.company` → per-store Company resolution for fixture loading
- Reads `Customer.name == Company.name` per S198 + S247 canonical pattern
- Reads `Supplier.name = "BEBANG KITCHEN INC. - Trade"` for PI verification
- Reads `Account.account_type == "Stock Received But Not Billed"` per buyer Company for GR/IR assertion
- Reads `tabGL Entry` rows where voucher_type IN (Sales Invoice, Purchase Invoice, Stock Entry) for GL post-submit verification
- Reads `Sales Invoice/Purchase Invoice/Stock Entry` docs created during workflow

Does NOT:
- Modify canonical Company / Warehouse / Customer records
- Add fallback logic to resolve_store_buyer_entity
- Hardcode parent Company names
- Use Internal Customers for any SI
- Bypass the per-store ownership model

## Ground-Truth Lock

- **evidence_sources:**
  - `output/l3/s252/recovery_evidence.json` → proves 4/5 S252 PASS state + GR/IR clean
  - `output/l3/s252/SUMMARY.md` → names the 4 remaining gaps S253 closes
  - `tests/e2e/specs/s252-bki-store-paired-doc-e2e.spec.ts` (bei-tasks @ PR #466 head) → base spec
  - `tests/e2e/fixtures/s204_all_stores.json` → 49-store fixture (49 rows verified)
  - `docs/STORE_COMPANY_CANONICAL.md` → canonical law
  - `hrms/hooks.py:220-240` (origin/production @ d1ab45c99) → SI on_submit/on_cancel hook list incl. PI + SE generators with SE-first cascade order
- **count_method:**
  - metric: 44 remaining stores for Phase 5 sweep
  - basis: `s204_all_stores.json` count (49) minus S252 STORE_FILTER (5)
  - method: `jq 'length' tests/e2e/fixtures/s204_all_stores.json` returns 49; STORE_FILTER excludes ARANETA, SM TANZA, SM MEGAMALL, XENTROMALL, NAIA T3 = 5 exclusions → 44 in scope
- **authoritative_sections:**
  - Sections "Goal" / "Requirements Regression Checklist" / Phases 0-6 are authoritative
  - "Design Rationale" is traceability
- **normalization_required:**
  - Any amendment that changes phase counts, scenario counts, or evidence file paths must update the authoritative sections in the same edit
- **unresolved_value_policy:**
  - Operator-facing unknowns → `[UNVERIFIED — requires resolution]`
- **normalization_artifacts:**
  - `output/l3/s253/SUMMARY.md` is the final reconciliation artifact

## Phase Budget Contract

- **phase_unit_budget:**
  - Phase 0 (Boot + worktrees + dependency check + library audit + Custom Field gate + loggedInDeskAdmin fixture + BKI inventory probe) → 8 units (v1.0 was 5; v1.1 added 4 audit-driven tasks P0.10–P0.13)
  - Phase 1 (SM MEGAMALL dispatch UI bug investigation + fix or document) → 8 units
  - Phase 2 (GL post-submit verification scenario, 5-row assertion) → 12 units
  - Phase 3 (Cancel cascade via UI scenario, PI asymmetry-aware) → 10 units
  - Phase 4 (Edge case scenarios: multi-item + partial + full rejection, S198 design read) → 14 units
  - Phase 5 (44-store browser sweep, per-store resume) → 17 units total (split as 5a=8u + 5b=9u below)
  - Phase 6 (Closeout, teardown leftover STOP) → 5 units
- **hard_limit:** 15 units per phase. Phase 4 at 14 OK. Phase 5 at 17 total — **MUST split** into 5a (sweep batches 1-22, 8u) + 5b (sweep batches 23-44, 9u). Each split is within the 15u limit.
- **total:** ~74 units v1.1 (was ~71 in v1.0; within 80-unit ceiling)

## Autonomous Execution Contract

- **completion_condition:**
  - All Phase 0-6 tasks marked DONE per the verification scripts
  - `output/l3/s253/RUN_STATUS.json` set to `COMPLETED`
  - `output/l3/s253/SUMMARY.md` + `DEFECTS.md` written with final outcome
  - `output/l3/s253/verification/canonical_preflight_post.txt` shows zero NEW violations vs baseline
  - All 5 gaps closed: SM MEGAMALL classified, GL verified, cancel verified, edges covered, 44 stores swept
  - `output/l3/s253/teardown_complete.json` confirms 0 leftover test SIs/PIs/SEs
  - Plan YAML `status` updated to `COMPLETED`
  - `SPRINT_REGISTRY.md` S253 row updated to COMPLETED with PR refs
  - PRs created on both repos (hrms + bei-tasks); URLs shared
  - Both worktrees removed cleanly
- **stop_only_for:**
  - Missing credentials/access (Doppler, SSM, GH_TOKEN, FRAPPE_API_KEY, FRAPPE_ADMIN_PASSWORD)
  - SM MEGAMALL dispatch bug requires destructive backend code change (CEO authorization required for the actual fix; investigation + classification can proceed autonomously)
  - >5 stores fail with the same fingerprint in Phase 5 sweep — STOP and present BLOCKER
  - PR #755, #466, or #749 NOT merged (HARD GATE — Phase 0 stops)
  - **Phase 0 P0.11 Custom Field gate FAILS** — `bki_si_reference` missing on either Purchase Invoice or Stock Entry — STOP and present BLOCKER: "Generators will silently no-op; deploy S238/S247 Custom Fields first."
  - **Phase 6 teardown leftover_count > 0 after 3 retries** — STOP and present BLOCKER (BIR risk)
- **continue_without_pause_through:**
  - audit → execute → PR creation → closeout
- **blocker_policy:**
  - Programmatic error → fix and continue
  - Repeated 3× same failure → grounded research (read source + Playwright docs), then continue
  - Evidence mismatch → normalize plan and continue
  - Business-data/policy → pause
- **signoff_authority:** `single-owner` (Sam Karazi, CEO)
- **canonical_closeout_artifacts:**
  - `output/l3/s253/SUMMARY.md`
  - `output/l3/s253/DEFECTS.md`
  - `output/l3/s253/RUN_STATUS.json`
  - `output/l3/s253/teardown_complete.json`
  - `output/l3/s253/verification/sm_megamall_dispatch_rca.md`
  - `output/l3/s253/verification/gl_post_submit_evidence.json`
  - `output/l3/s253/verification/cancel_cascade_evidence.json`
  - `output/l3/s253/verification/edge_cases_evidence.json`
  - `output/l3/s253/verification/full_sweep_49_stores.json`
  - `docs/plans/2026-05-16-sprint-253-bki-store-e2e-completion.md` (status COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (S253 row COMPLETED)

## Status Reconciliation Contract

Whenever counts, blockers, stage, or certification status changes:
1. `output/l3/s253/RUN_STATUS.json`
2. `output/l3/s253/SUMMARY.md`
3. `output/l3/s253/DEFECTS.md` (if new defect found)
4. `docs/plans/2026-05-16-sprint-253-bki-store-e2e-completion.md` (status line + amendment block)
5. `docs/plans/SPRINT_REGISTRY.md` (status column)
6. PR descriptions (if open)

## Signoff Model

- **mode:** `single-owner`
- **approver_of_record:** Sam Karazi (CEO)
- **signoff_artifact:** `output/l3/s253/SUMMARY.md`
- **note:** Single-owner per BEI policy 2026-04-15 (Butch/Alyssa/Juanna resigned).

## Anti-Rewind / Concurrent-Run Protection Contract

- **ownership_matrix:**
  - artifact: `output/l3/s253/SURFACE_OWNERSHIP_MATRIX.csv` (Phase 0 deliverable)
  - rule: S253 owns `tests/e2e/specs/s253-bki-store-e2e-completion.spec.ts` (new), `tests/e2e/pages/SICancelPage.ts` (new), `scripts/s253/*.py` (new), `output/l3/s253/**`. Does NOT touch the merged S252 spec or any other shipped spec.
- **protected_surfaces:**
  - The merged S252 spec at `tests/e2e/specs/s252-bki-store-paired-doc-e2e.spec.ts` — extended via NEW S253 spec, NOT modified
  - Existing Page Objects (StoreOrderingPage etc.) — read-only; extensions go in new files or are explicit additive methods
  - `hrms/api/bki_store_pi_generator.py` / `bki_store_stock_entry_generator.py` / `hooks.py` — read-only unless Phase 1 SM MEGAMALL fix requires a change (then explicit + tracked)
- **remote_truth_baseline:**
  - artifact: `output/l3/s253/state/REMOTE_TRUTH_BASELINE.json`
  - fields:
    - `repo`: Bebang-Enterprise-Inc/hrms + BEI-Tasks
    - `release_branch`: production / main
    - `release_head_sha`: filled by Phase 0 (`git rev-parse origin/production` + `git rev-parse origin/main`)
    - `live_evidence_basis`: S252 PRs #755 + #466 merge commits
- **active_run_coordination:**
  - artifact: `output/l3/s253/state/ACTIVE_RUN.json`
  - rule: claim on Phase 0 start, release on Phase 6 closeout
- **pretouch_backup:**
  - artifact: `output/l3/s253/state/PRETOUCH_BACKUP.json`
  - rule: required before Phase 1 fix attempt if SM MEGAMALL needs backend code change
- **supersession_map:**
  - artifact: `output/l3/s253/state/SUPERSESSION_MAP.json`
  - rule: when S253 ships, the S252 "remaining gaps" notes in `output/l3/s252/SUMMARY.md` are closed by S253 evidence

## Agent Boot Sequence

1. **Read this plan fully.**
2. **Verify hrms PR #755 + bei-tasks PR #466 + hrms PR #749 are MERGED.** Run:
   ```bash
   GH_TOKEN="" gh pr view 755 --repo Bebang-Enterprise-Inc/hrms --json state,mergedAt
   GH_TOKEN="" gh pr view 466 --repo Bebang-Enterprise-Inc/BEI-Tasks --json state,mergedAt
   GH_TOKEN="" gh pr view 749 --repo Bebang-Enterprise-Inc/hrms --json state,mergedAt
   ```
   If ANY shows `state: OPEN` or `mergedAt: null`, **STOP** and present BLOCKER to Sam: "S253 depends on these PRs being merged first."
3. **Spawn hrms worktree** from `origin/production`:
   ```bash
   cd F:/Dropbox/Projects/BEI-ERP && git fetch origin --prune
   git worktree add F:/Dropbox/Projects/BEI-ERP-s253-bki-store-e2e-completion \
       -B s253-bki-store-e2e-completion origin/production
   cd F:/Dropbox/Projects/BEI-ERP-s253-bki-store-e2e-completion
   ```
4. **Spawn bei-tasks worktree** from `origin/main`:
   ```bash
   cd F:/Dropbox/Projects/bei-tasks && git fetch origin --prune
   git worktree add F:/Dropbox/Projects/bei-tasks-s253-bki-store-e2e-completion \
       -B s253-bki-store-e2e-completion origin/main
   cd F:/Dropbox/Projects/bei-tasks-s253-bki-store-e2e-completion
   npm install
   ```
5. **Read** `docs/STORE_COMPANY_CANONICAL.md`, `output/l3/s252/SUMMARY.md`, `output/l3/s252/recovery_evidence.json`.
6. **Read source files in hrms worktree:**
   - `hrms/api/bki_store_pi_generator.py` (PI generator + cascade hook + posting-date lock)
   - `hrms/api/bki_store_stock_entry_generator.py` (SE generator + cascade hook + posting-date lock)
   - `hrms/hooks.py` lines 220-240 (Sales Invoice on_submit / on_cancel hook chain)
7. **Read source files in bei-tasks worktree:**
   - `tests/e2e/specs/s252-bki-store-paired-doc-e2e.spec.ts` (base spec to extend)
   - `tests/e2e/pages/StoreOrderingPage.ts`, `OrderApprovalPage.ts`, `DispatchPage.ts`, `WarehouseApprovalPage.ts`, `ReceivingPage.ts` (existing Page Objects)
   - `tests/e2e/support/frappeReadback.ts` (read-only API helper)
   - `tests/e2e/fixtures/s204_all_stores.json` (49-store fixture)
8. **Run canonical preflight:**
   ```bash
   python scripts/verify_canonical_structure.py | tee output/l3/s253/verification/canonical_preflight_baseline.txt
   ```
   Expected: `[RESULT] ALL CANONICAL` (49 stores, 0 violations).
9. **Initialize ACTIVE_RUN.json** at `output/l3/s253/state/ACTIVE_RUN.json` with `{sprint: S253, started_at: <utc>, phase: 0, status: in_progress}`.

## Execution Authority

This sprint is intended for autonomous end-to-end execution. Stop only for items in the Autonomous Execution Contract `stop_only_for` section.

---

## Phase 0 — Boot + Worktrees + Library Audit + Preflight Gates (8 units)

### Goal
Spawn both worktrees, verify dependencies, capture baseline state, perform library audit per qa-test-library-discipline.

### Tasks

| # | Task | Verification |
|---|------|--------------|
| P0.1 | Spawn hrms + bei-tasks worktrees per Agent Boot Sequence steps 3-4 | `pwd` returns correct path; `git branch --show-current` returns `s253-bki-store-e2e-completion` in both repos |
| P0.2 | Verify PR #755 + #466 + #749 MERGED. If not, STOP. | All three `gh pr view` calls return `state: MERGED` |
| P0.3 | Create directories in hrms worktree: `output/l3/s253/{audit,verification,state,ledgers}` + `tmp/s253` + `scripts/s253` | `ls -la output/l3/s253/` shows 4 subdirs |
| P0.4 | Capture baseline state: write `output/l3/s253/state/REMOTE_TRUTH_BASELINE.json` with both repo SHAs + S252 PR refs | File exists |
| P0.5 | Write `output/l3/s253/state/ACTIVE_RUN.json` per boot sequence step 9 | File exists with status=in_progress, phase=0 |
| P0.6 | Run canonical preflight + save to `output/l3/s253/verification/canonical_preflight_baseline.txt` | `grep "ALL CANONICAL" <file>` returns ≥1 match |
| P0.7 | **Library audit task** (per qa-test-library-discipline): list existing Page Objects + fixtures + assertions covering BKI→Store flow. Document gaps in `output/l3/s253/audit/library_audit.md`. Existing: StoreOrderingPage (with `submitOrderWithExplicitQty` already supporting explicit items), OrderApprovalPage, DispatchPage (with `dispatch({qtyOverrides: Map})` already supporting partial), WarehouseApprovalPage, ReceivingPage, loggedInAreaSupervisor/SCM/StoreSupervisor fixtures, CleanupLedger (no `pendingEntries` property — use `entriesSnapshot().length`), assertCompanyChainCorrect, assertSIGLPartyIsCustomer, assertOrderCompany, assertDualApprovalExercised, waitForDocStatus (in frappeReadback.ts). **GAPS for S253:** `loggedInDeskAdmin` fixture (new, HQ_URL-scoped context), SICancelPage (new), FrappeDeskSubmitPage (new), ReceivingPage.rejectAll (extension), assertPairedDocGLChain (new — asserts exactly 5 buyer-side GL rows), assertCancelCascadeOrder (new), assertPairedDocsAfterSICancel (new — handles PI cascade asymmetry: SE cancels but submitted PI only gets Comment). **DO NOT create:** `submitOrderWithExactItems` or `dispatchPartial` — duplicates of existing methods. | File exists listing existing + gaps |
| P0.8 | Write `output/l3/s253/state/SURFACE_OWNERSHIP_MATRIX.csv` listing files S253 owns | File exists with rows per protection contract |
| P0.9 | Initial commit on each worktree: `chore(S253 P0): boot + worktree + baseline + library audit` | `git log -1 --oneline` shows boot commit in both repos |
| P0.10 | **Create `loggedInDeskAdmin` fixture** in `bei-tasks/tests/e2e/fixtures/auth.ts`: separate `BrowserContext` with `baseURL: HQ_URL = "https://hq.bebang.ph"`. Reads password from `process.env.FRAPPE_ADMIN_PASSWORD` (sourced via Doppler project `bei-erp`, config `dev`). Login as user `Administrator` via `${HQ_URL}/login`. Wait for redirect to `/app/`. Pattern reference: `bei-tasks/tests/e2e/specs/s224-cleanup-resilience.spec.ts:86-92` for inline cross-domain auth example. Export `loggedInDeskAdmin` via `test.extend()` in `auth.ts`. | grep `loggedInDeskAdmin` in `bei-tasks/tests/e2e/fixtures/auth.ts` returns ≥1 hit |
| P0.11 | **BKI Custom Field hard gate (SSM probe via headless Python):** `frappe.db.has_column("Purchase Invoice", "bki_si_reference")` AND `frappe.db.has_column("Stock Entry", "bki_si_reference")`. HARD STOP if either returns False — present BLOCKER to Sam: "S238/S247 Custom Field absent; PI/SE generators will silently no-op." Persist probe result to `output/l3/s253/verification/custom_field_gate.json`. | File exists with `{pi_has_field: true, se_has_field: true}` |
| P0.12 | **BKI source warehouse + multi-item discovery (SSM probe):** Query `frappe.db.sql("SELECT name FROM tabWarehouse WHERE company='BEBANG KITCHEN INC.' AND warehouse_type='Stock' AND disabled=0")` AND for each warehouse, query top 5 items by `actual_qty` from `tabBin WHERE warehouse=...`. Filter for DRY category and `actual_qty ≥ 10`. Write canonical BKI source warehouse name + 5 item codes to `output/l3/s253/audit/bki_source_inventory.json`. Phase 4 reads from this file. | File exists; `inventory_items.length >= 5` |
| P0.13 | **BKI_COMPANY case verification (soft preflight):** `frappe.db.get_value("Company", "BEBANG KITCHEN INC.", "name")` — log warning if returns different case. (Soft check; not a STOP because S252 4/5 PASS implies case matches.) | Probe result logged to `output/l3/s253/verification/bki_company_case.json` |

**MUST_MODIFY:** `output/l3/s253/state/REMOTE_TRUTH_BASELINE.json`, `output/l3/s253/state/ACTIVE_RUN.json`, `output/l3/s253/state/SURFACE_OWNERSHIP_MATRIX.csv`, `output/l3/s253/audit/library_audit.md`, `output/l3/s253/verification/canonical_preflight_baseline.txt`, `output/l3/s253/verification/custom_field_gate.json`, `output/l3/s253/audit/bki_source_inventory.json`, `output/l3/s253/verification/bki_company_case.json`, `bei-tasks/tests/e2e/fixtures/auth.ts` (loggedInDeskAdmin fixture added).

---

## Phase 1 — SM MEGAMALL Dispatch UI RCA + Fix (8 units)

### Goal
Investigate the SM MEGAMALL DispatchPage timeout from S252 (`per_transferred=undefined` after MR transitioned to Ordered). Classify and either fix or document.

### Tasks

| # | Task | Verification |
|---|------|--------------|
| P1.1 | Read S252 dispatch failure context: `output/l3/s252/SUMMARY.md` SM MEGAMALL section + `paired_doc_evidence.json` for the fail row | grep for "SM MEGAMALL" matches |
| P1.2 | **SSM Error Log probe** — query `tabError Log` for entries on 2026-05-16 referencing MR for SM MEGAMALL (most recent S252 attempt). Inline SSM pattern: `bench --site hq.bebang.ph execute frappe.client.get_list --kwargs '{"doctype":"Error Log","filters":[["creation",">","2026-05-15"],["error","like","%SM MEGAMALL%"]],"fields":["name","method","error","creation"]}'`. Write to `tmp/s253/dispatch_diag_errorlog.json`. Look for: stock transfer endpoint errors, Stock Entry creation errors, `tabBin` lock errors. | File created with error entries (may be empty if SSM-only error path) |
| P1.3 | **Code-path inspection** — the SM MEGAMALL handler is in `hrms/api/warehouse.py` (NOT `hrms/api/dispatch.py` — dispatch.py is for BEI Distribution Trip logistics and has zero `per_transferred` references). Read `hrms/api/warehouse.py` with grep: `grep -n "per_transferred\|complete_receiving\|_submit_dispatch_draft_si\|create_stock_transfer" hrms/api/warehouse.py`. Trace what sets `per_transferred` on the MR. Write findings to `output/l3/s253/verification/sm_megamall_dispatch_rca.md`. | File exists with code path documented |
| P1.4 | **Comparison probe** — query production MR records for SM MEGAMALL: latest 3 MRs by `creation desc`, check their docstatus, status, per_transferred, per_received, and the linked Stock Entry. Write to `tmp/s253/sm_megamall_mr_state.json`. | File shows whether SM MEGAMALL has any historical successful dispatch (working baseline for comparison) |
| P1.5 | **Master data probe** — verify SM MEGAMALL Warehouse + Company config matches the 4 passing stores from S252. Specifically check: `Warehouse.account`, `Company.cost_center`, `Company.stock_received_but_not_billed`, `enable_perpetual_inventory`. Use `python scripts/verify_canonical_structure.py --mode v2 --store "SM MEGAMALL - BEBANG ENTERPRISE INC."` if available, else write a one-off probe. | All 4 fields populated (S247 P4a/P4b applied) |
| P1.6 | **Classify the failure** in `output/l3/s253/verification/sm_megamall_dispatch_rca.md` as one of: **Mode A** (app bug — fix in hrms repo: e.g. dispatch hook race), **Mode B** (test bug — DispatchPage waitForToast pattern unreliable for this store; fix in bei-tasks repo), **Mode C** (master data — some field still wrong; fix via `/frappe-bulk-edits`), **Mode D** (skip-and-document — defer to dedicated sprint). | RCA file ends with a classification line `**Classification:** Mode X` |
| P1.7 | **If Mode A or C:** apply the fix on hrms worktree (with full code/data context). Commit. **If Mode B:** apply the fix on bei-tasks worktree. **If Mode D:** add to `output/l3/s253/DEFECTS.md` as "known-blocker, skip from Phase 5 sweep", document follow-up sprint candidate. | Either commit exists OR DEFECTS.md entry exists |
| P1.8 | Commit per-repo: `feat(S253 P1): SM MEGAMALL dispatch RCA + Mode X fix/disposition` | `git log -1 --oneline` shows commit |

**HARD BLOCKER:** if Phase 1.6 classifies as Mode A AND the proposed fix touches `hrms/api/dispatch.py` or any other shared backend code, present BLOCKER to Sam before applying — destructive shared-code change requires explicit consent per Autonomous Execution Contract.

---

## Phase 2 — GL Post-Submit Verification Scenario (12 units)

### Goal
Add a Playwright spec that, after the existing S252 chain, ALSO submits the paired PI + SE via Frappe Desk on hq.bebang.ph as Administrator user and verifies the GL entries land correctly.

### Tasks

| # | Task | Verification |
|---|------|--------------|
| P2.1 | **NEW Page Object** `tests/e2e/pages/FrappeDeskSubmitPage.ts` with methods `submitPurchaseInvoice(pi_name)` and `submitStockEntry(se_name)`. Login flow uses Frappe Desk auth (Administrator user). Submit click finds the doctype's Submit button (Frappe Desk standard: top-right "Submit" or Menu→Submit). | File created; class exports both methods |
| P2.2 | **NEW assertion** `tests/e2e/assertions/glAssertions.ts` exporting `assertPairedDocGLChain(siName, expectedAmounts)` — queries `tabGL Entry` for vouchers (SI, PI, SE) filtered by buyer Company, asserts EXACTLY **5 buyer-side GL rows** per shipment per S247:<br>1. Dr `1104210 Inventory-from-Commissary - <ABBR>` = `qty × rate` (SE submit)<br>2. Cr `SRBNB account_type='Stock Received But Not Billed' (buyer)` = `qty × rate` (SE submit)<br>3. Dr `SRBNB account_type='Stock Received But Not Billed' (buyer)` = `qty × rate` (PI submit, CLEARS row 2 → SRBNB net = 0)<br>4. Dr `1106210 Input VAT BKI Inter-Co - <ABBR>` = `tax_amount` (PI submit)<br>5. Cr `2103210 AP-Trade-BKI - <ABBR>` = `qty × rate + tax_amount` (PI submit)<br>Assertion MUST: (a) check `rows.length === 5` after buyer-company filter, (b) check SRBNB Dr+Cr nets to zero, (c) check each row's account name resolves via `Account.account_type` for SRBNB and string match for others, (d) check amounts against ACTUAL submitted SI items (NOT hardcoded). | File created; exports function signature; grep shows exactly `=== 5` row count check |
| P2.3 | **NEW Playwright spec** `tests/e2e/specs/s253-bki-store-e2e-completion.spec.ts` first scenario block: extends S252's chain. For ARANETA only (1 representative store; full sweep happens in P5), after `assertCompanyChainCorrect` returns siName, paired PI/SE found:<br>**Submit order matters: SE FIRST, then PI** (so SE Cr SRBNB lands before PI Dr SRBNB clears it; matches the canonical posting sequence Finance follows).<br>(a) Use `loggedInDeskAdmin` fixture (from P0.10) — separate BrowserContext targeting HQ_URL<br>(b) Open `${HQ_URL}/app/stock-entry/{se_name}` → click Submit → poll `waitForDocStatus("Stock Entry", se_name, 1)`<br>(c) Open `${HQ_URL}/app/purchase-invoice/{pi_name}` → click Submit → poll `waitForDocStatus("Purchase Invoice", pi_name, 1)`<br>(d) Read ACTUAL SI items from `tabSales Invoice Item WHERE parent={si_name}` to compute expected `qty`, `rate`, `tax_amount`<br>(e) Call `assertPairedDocGLChain(siName)` (reads actual amounts internally, no hardcoded params) | Spec file created; first describe block compiles |
| P2.4 | **Test data note** — the existing test order in S252 uses `submitOrderAtSuggested(store, "DRY", { itemCount: 3 })` which creates an order with 3 items at suggested quantities. Calculate expected `qty × rate` from the SI's items table. **GL assertion uses ACTUAL submitted SI amounts** (read from `tabSales Invoice Item`), NOT hardcoded values. | grep for "ACTUAL" or "read from" in assertPairedDocGLChain shows dynamic amount lookup |
| P2.5 | **Local Playwright run** on ARANETA only (filter `S253_SCENARIO=gl_verification`). Capture trace + screenshots. Run command:<br>`doppler run --project bei-erp --config dev -- npx playwright test tests/e2e/specs/s253-bki-store-e2e-completion.spec.ts --grep "GL post-submit"` | At least 1 PASS recorded |
| P2.6 | Persist evidence: `output/l3/s253/verification/gl_post_submit_evidence.json` with the per-SI GL row breakdown — exactly **5 buyer-side rows per shipment** (Dr 1104210, Cr SRBNB [SE]; Dr SRBNB, Dr 1106210, Cr 2103210 [PI]). Plus screenshots of submitted PI and SE in Frappe Desk. | File exists; `len(rows) == 5` per pair; SRBNB Dr+Cr nets to zero per pair |
| P2.7 | Commit on bei-tasks: `feat(S253 P2): GL post-submit verification spec + SICancelPage + assertPairedDocGLChain (library contribution)`; commit on hrms: `feat(S253 P2): GL post-submit evidence + Administrator desk submit recovery probe (if needed)` | Both commits exist |

**MUST_MODIFY:** `tests/e2e/specs/s253-bki-store-e2e-completion.spec.ts` (NEW), `tests/e2e/pages/FrappeDeskSubmitPage.ts` (NEW), `tests/e2e/assertions/glAssertions.ts` (NEW).
**MUST_CONTAIN:** in `assertPairedDocGLChain`: `tabGL Entry`, `SRBNB`, `1104210`, `2103210`, `1106210`, `account_type === "Stock Received But Not Billed"`.

---

## Phase 3 — Cancel Cascade via UI Scenario (10 units)

### Goal
After the GL post-submit step, cancel the BKI Sales Invoice via Frappe Desk UI as Administrator and verify the SE-first cancel order + cascade cleanup.

### Tasks

| # | Task | Verification |
|---|------|--------------|
| P3.1 | **NEW Page Object** `tests/e2e/pages/SICancelPage.ts` with method `cancelSalesInvoice(si_name)`. Login as Administrator on hq.bebang.ph, navigate to `/app/sales-invoice/{si_name}`, click Menu → Cancel, confirm dialog, wait for docstatus=2. | File created; cancelSalesInvoice() callable |
| P3.2 | **NEW assertion** `assertCancelCascadeOrder(siName)` — queries `tabGL Entry` for the SE cancel and PI cancel vouchers, asserts `se_cancel_creation < pi_cancel_creation` (SE cancelled first per S247 hooks.py order). | Function exported from glAssertions.ts |
| P3.3 | **NEW assertion** `assertPairedDocsAfterSICancel(siName, { piWasSubmitted: boolean })` — verifies after SI cancel, handling the PI cascade ASYMMETRY (see `hrms/api/bki_store_pi_generator.py:405-422`):<br>**SE side (auto-cancel for both Draft and Submitted):** assert SE is `docstatus=2` (Cancelled) OR deleted (`frappe.db.exists("Stock Entry", {"bki_si_reference": siName})` returns None).<br>**PI side, IF piWasSubmitted=true (Phase 2 chain):** assert PI is `docstatus=1` (still Submitted), AND a Comment exists on the PI matching `/Finance review required/` — the generator inserts this Comment instead of auto-cancelling. Query: `frappe.db.exists("Comment", {"reference_doctype": "Purchase Invoice", "reference_name": pi_name, "content": ["like", "%Finance review required%"]})`.<br>**PI side, IF piWasSubmitted=false:** assert PI is deleted (Draft PIs are force-deleted by the cascade hook).<br>Asymmetry is by design — only `frappe.delete_doc` or `pi.cancel()` happens for Draft PIs; submitted PIs preserve audit trail. | Function exported; assertion logic matches the asymmetry |
| P3.4 | **Spec extension** — add second describe block "Cancel cascade via UI" to `s253-bki-store-e2e-completion.spec.ts`. For ARANETA, after Phase 2's GL verification (PI was SUBMITTED in Phase 2):<br>(a) `new SICancelPage(loggedInDeskAdmin).cancelSalesInvoice(siName)`<br>(b) **Replace fixed 5s wait** with `await waitForDocStatus({ doctype: "Sales Invoice", name: siName, docstatus: 2, timeoutMs: 15000 })` (uses existing `frappeReadback.ts` helper) — Zero-Skip rule forbids `page.waitForTimeout(N)` (plan line 615)<br>(c) `await assertCancelCascadeOrder(siName)` — verifies SE cancel GL row creation timestamp < PI cancel GL row timestamp (SE-first hook order per `hrms/hooks.py:237-239`)<br>(d) `await assertPairedDocsAfterSICancel(siName, { piWasSubmitted: true })` — handles asymmetry (SE cancelled; PI stays docstatus=1 + Comment)<br>(e) Verify GL reversal of SE submit rows: query `tabGL Entry` for cancellation rows — assert SE Dr 1104210 reversed (matching Cr 1104210 row exists), assert SE Cr SRBNB reversed (matching Dr SRBNB row exists). PI's GL rows REMAIN ON BOOKS (PI is still submitted) — do NOT assert reversal of Dr 1106210 / Cr 2103210. Document this in evidence as expected. | grep for "Cancel cascade" returns ≥1 match |
| P3.5 | Cancel-cascade scenario adds to `cleanupLedger` automatically (paired docs are tracked from creation). Cleanup ledger now has SI + PI + SE for each test scenario. | grep for "cleanupLedger" in spec |
| P3.6 | Local run: `npx playwright test --grep "Cancel cascade"`. Capture trace. | 1 PASS recorded |
| P3.7 | Persist evidence: `output/l3/s253/verification/cancel_cascade_evidence.json` with per-SI cancel order timestamps + reversal GL rows | File exists; SE timestamp < PI timestamp verified |
| P3.8 | Commit on bei-tasks + hrms repos. | `git log -1 --oneline` shows |

**MUST_MODIFY:** `tests/e2e/pages/SICancelPage.ts` (NEW), `tests/e2e/assertions/glAssertions.ts` (extended).

---

## Phase 4 — Edge Case Scenarios (14 units)

### Goal
Three new scenarios covering multi-item, partial fulfillment, and full rejection — each exercises a different code path the S252 baseline didn't touch.

### Tasks

| # | Task | Verification |
|---|------|--------------|
| P4.1 | **REUSE existing `StoreOrderingPage.submitOrderWithExplicitQty(storeName, cargo, { items: Array<{code: string; qty: number}> })`** (already in `bei-tasks/tests/e2e/pages/StoreOrderingPage.ts:391-441`). Do NOT create a parallel `submitOrderWithExactItems`. The existing method's signature exactly matches the multi-item scenario need. Item codes sourced from `output/l3/s253/audit/bki_source_inventory.json` (written in P0.12). | Spec uses `submitOrderWithExplicitQty`; grep `submitOrderWithExactItems` returns 0 hits |
| P4.2 | **REUSE existing `DispatchPage.dispatch(mrName, { qtyOverrides?: Map<string, number> })`** (already in `bei-tasks/tests/e2e/pages/DispatchPage.ts`). Pass `qtyOverrides: new Map(Object.entries(qtyMap))` for partial dispatch. Do NOT create a parallel `dispatchPartial`. | Spec uses `dispatch({qtyOverrides})`; grep `dispatchPartial` returns 0 hits |
| P4.3 | **Extension to ReceivingPage** — `rejectAll(wr)` — mark all items as fully rejected on the receiving page. This IS a genuine new method (no existing method covers full-rejection of every line item). Library contribution. | Method added with data-testid selectors only |
| P4.4 | **Scenario: Multi-item happy chain** — same chain as S252 but order with 5 items (DRY category). Item codes sourced from `output/l3/s253/audit/bki_source_inventory.json` (written by P0.12). Verify: PI has 5 item lines all with SRBNB expense; SE has 5 item lines all with t_warehouse=buyer; GL has 5 inventory rows × Dr + 5 SRBNB rows × Cr (one per SE line), 1 net PI Dr SRBNB row, etc. | spec describe block "Edge: multi-item" PASS |
| P4.5 | **Scenario: Partial fulfillment** — order 10 of ITEM-A, dispatch 7, accept 7. Verify: SI grand_total reflects 7 × rate (not 10); PI grand_total matches SI; SE qty=7 (not 10); GL Dr 1104210 = 7 × rate. | spec describe block "Edge: partial fulfillment" PASS |
| P4.6 | **Scenario: Full rejection** — order 5 of ITEM-A, dispatch 5, on receive page reject ALL 5 (rejected_qty=received_qty=5). **PRE-STEP:** Read S198 receive-rejection design FIRST. Specifically: read `hrms/api/warehouse.py:complete_warehouse_receiving` AND any `_submit_dispatch_draft_si` function. Document the design at `output/l3/s253/audit/full_rejection_expected.md` — pick ONE expected branch (NOT "OR"). Likely branches: (A) SI not created at all (received_qty=0 short-circuits SI submission — BIR-compliant, no zero-value invoice), OR (B) SI created with `net_total = 0` (BIR-non-compliant). Spec asserts ONLY the design-confirmed branch. If branch A: assert `frappe.db.exists("Sales Invoice", {"bki_store_order": orderName}) is None`. If branch B: write DEFECT entry (zero-value SI = BIR violation) and assert SI exists with `grand_total == 0`. | `output/l3/s253/audit/full_rejection_expected.md` exists, names ONE branch; spec asserts that branch only |
| P4.7 | Local run: `npx playwright test --grep "Edge:"`. Capture traces. | 3 PASS or 1 DEFECT-PASS + 2 PASS |
| P4.8 | Persist evidence: `output/l3/s253/verification/edge_cases_evidence.json` | File exists with per-scenario verdict |
| P4.9 | Commit on bei-tasks. | git log |

**MUST_MODIFY:** `tests/e2e/pages/StoreOrderingPage.ts`, `tests/e2e/pages/DispatchPage.ts`, `tests/e2e/pages/ReceivingPage.ts` (all extensions — additive methods only, not rewriting).
**MUST_CONTAIN:** in spec: `"Edge: multi-item"`, `"Edge: partial fulfillment"`, `"Edge: full rejection"`.

---

## Phase 5 — 44-Store Browser Sweep (17 units, split into 5a + 5b)

### Goal
Run the validated S253 spec (with GL + cancel + edge assertions) against the 44 stores NOT in S252's STORE_FILTER. Each store gets the GL post-submit + cancel cascade scenario (skip edge cases for the sweep — they're proven in Phase 4 on representative stores).

### Phase 5a — Sweep batches 1-22 (8 units)

| # | Task | Verification |
|---|------|--------------|
| P5a.1 | **Build the sweep filter** — parse `tests/e2e/fixtures/s204_all_stores.json` (49 entries) minus S252 STORE_FILTER (5 entries) = 44 stores. Split into 2 batches of 22 for crash-resume safety. List in `output/l3/s253/audit/sweep_batch_1.txt`. | File contains 22 store names |
| P5a.2 | **Spec modification** — add TWO env-var filters to the spec: (1) `S253_SWEEP=batch1` (or `batch2`) selects the batch list, (2) `S253_RESUME_FROM=<store_name>` skips all stores BEFORE the named store in the batch (resume-from-crash). When neither set, run all stores in batch. Each store gets order → approve → dispatch → receive → GL submit verify (NOT cancel — cancel cascade verified in Phase 3 on representative store). | grep for `S253_SWEEP` AND `S253_RESUME_FROM` each return ≥1 match in spec |
| P5a.3 | **Run sweep batch 1** — sequential, 22 stores × ~5min = ~2 hours. Use `doppler run -- npx playwright test --grep "S253 sweep"`. Allow up to 2 retries per store via Playwright `retries: 2` for transient EBUSY. **On crash:** the spec writes each completed store to evidence file IMMEDIATELY after success (per-store append, NOT batch-final write). Restart command: `S253_RESUME_FROM=<last_failed_store> S253_SWEEP=batch1 doppler run -- npx playwright test --grep "S253 sweep"`. | Output shows 22 results; per-store evidence rows visible in `full_sweep_49_stores.json` as each store completes |
| P5a.4 | **Persist per-store evidence** to `output/l3/s253/verification/full_sweep_49_stores.json` after EACH store completes (append, not batch-final). Final file aggregates batches 1+2 + S252's 5. **No "all 22 written at end" semantics** — that loses progress on crash. | File grows monotonically during sweep; final has 22 + 5 = 27 after batch 1 |
| P5a.5 | Commit: `feat(S253 P5a): 22-store sweep batch 1 complete` | git log |

### Phase 5b — Sweep batches 23-44 (9 units)

| # | Task | Verification |
|---|------|--------------|
| P5b.1 | List 22 stores for batch 2 in `output/l3/s253/audit/sweep_batch_2.txt` | File contains remaining 22 store names |
| P5b.2 | Run sweep batch 2 — sequential, 22 stores × ~5min = ~2 hours | Output shows 22 results |
| P5b.3 | Aggregate full results into `output/l3/s253/verification/full_sweep_49_stores.json`. Final: 5 (S252) + 22 (5a) + 22 (5b) = 49 entries. | File has 49 entries |
| P5b.4 | **Classify failures**: any store with verdict != PASS gets a row in `output/l3/s253/DEFECTS.md` with classification (Mode A app bug / Mode B test infra / Mode C master data / Mode D store-specific). | DEFECTS.md entries for any non-PASS |
| P5b.5 | **HARD BLOCKER:** if >5 stores fail in batch 2 with the same fingerprint, STOP and present BLOCKER. (5/22 = 23% failure rate is the threshold for a systemic issue.) | Continue if <=5 same-class fails; else stop |
| P5b.6 | Commit: `feat(S253 P5b): 22-store sweep batch 2 complete; 49/49 results aggregated` | git log |

**MUST_MODIFY:** `tests/e2e/specs/s253-bki-store-e2e-completion.spec.ts` (S253_SWEEP filter logic).

---

## Phase 6 — Closeout (5 units)

### Goal
Verify production clean, persist final evidence, update plan + registry, open PRs, remove worktrees.

### Tasks

| # | Task | Verification |
|---|------|--------------|
| P6.1 | **Run teardown** — read `cleanupLedger` entries, cancel + force-delete any test SI/PI/SE artifacts still on production. Retry up to 3 times per entry on transient failure. Write `output/l3/s253/teardown_complete.json` with shape `{leftover_count: N, leftover_docs: [{doctype, name, reason}], retries_per_entry: {...}}`. **HARD STOP** if `leftover_count > 0` after 3 retries — present BLOCKER to Sam: "Permanent test SI/PI/SE artifacts on BKI production books = BIR audit risk. Manual Finance cleanup required before S253 can be marked COMPLETED." Do NOT continue to P6.2+ if leftover > 0. | `teardown_complete.json` shows `leftover_count: 0`; if not, P6.X tasks blocked |
| P6.2 | **Post-run canonical preflight** — `python scripts/verify_canonical_structure.py | tee output/l3/s253/verification/canonical_preflight_post.txt`. Assert zero NEW violations vs baseline. | `diff` of baseline vs post shows no new violations |
| P6.3 | **Write SUMMARY.md** — full closeout per template (gap closure status per 5 items, sweep result counts, DEFECTS classification breakdown, follow-up sprint candidates) | File exists, ≥80 lines |
| P6.4 | **Update plan YAML** — `status: COMPLETED`, `completed_date: 2026-05-16` (or actual), `execution_summary: <one paragraph>` | grep YAML for COMPLETED |
| P6.5 | **Update `SPRINT_REGISTRY.md`** — S253 row to COMPLETED with PR refs | grep for "COMPLETED" in S253 row |
| P6.6 | `git add -f` + commit + push on BOTH worktrees | both branches have push |
| P6.7 | **Create PRs on both repos** via `GH_TOKEN="" gh pr create`. Title: `feat(S253): BKI->Store E2E completion - GL/cancel/edges/49-store sweep`. Body: per-phase status table + DEFECTS summary + closeout signoff. | Both PRs return URLs |
| P6.8 | **Worktree exit:** `cd F:/Dropbox/Projects/BEI-ERP && git worktree remove F:/Dropbox/Projects/BEI-ERP-s253-bki-store-e2e-completion`; same for bei-tasks. | `git worktree list` no longer shows S253 worktrees |
| P6.9 | STOP — Sam reviews + merges + deploys. | done |

---

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|---|---|---|---|
| `test.area@bebang.ph` | Submit Order via my.bebang.ph store ordering page: store=ARANETA, category=DRY, items=3 (suggested qty) → click Submit | BEI Store Order created with status=Draft (or Pending Approval) | StoreOrderingPage broken or RBAC denying access |
| `test.area@bebang.ph` + `test.scm@bebang.ph` | Both click Approve on the order via the approval page → after both clicks, status=Approved + MR created | MR appears in MR list with link to order | Dual-approval logic broken (S235) |
| `test.scm@bebang.ph` | Open Warehouse Approval page → click Approve on the MR → then go to Dispatch page → click Dispatch → fill dispatched_qty=ordered_qty → click Submit | Stock Entry created, BEI Warehouse Receiving auto-generated | DispatchPage broken or MR transition error |
| `test.supervisor@bebang.ph` | Open WR receiving page → set received_qty=ordered_qty for all items → click Submit | WR status=Received; Sales Invoice auto-created + auto-submitted on BKI books; paired Draft PI + Draft SE auto-generated by S247 hooks | Receive flow or S198 SI creation broken |
| `Administrator` | Open `https://hq.bebang.ph/app/purchase-invoice/{pi_name}` → click Submit | PI docstatus=1; GL posts Dr SRBNB + Dr 1106210 / Cr 2103210 | Frappe Desk submit broken or SRBNB account misconfigured |
| `Administrator` | Open `https://hq.bebang.ph/app/stock-entry/{se_name}` → click Submit | SE docstatus=1; GL posts Dr 1104210 / Cr SRBNB; SLE updates buyer's Bin actual_qty | SE submit broken or warehouse account misconfigured |
| (script) | Query `tabGL Entry` for all 3 vouchers (SI, PI, SE), aggregate by account | Per shipment: Dr 1104210 once = (qty × rate); Cr 2103210 once = (qty × rate + tax); Dr 1106210 once = tax; SRBNB net = 0 across SE Cr + PI Dr | GL netting broken (proves S247 GR/IR design was incorrect) |
| `Administrator` | Open `https://hq.bebang.ph/app/sales-invoice/{si_name}` → click Menu → Cancel | SI docstatus=2; cascade hooks fire; SE cancels first then PI | Cancel cascade order wrong or hooks unregistered |
| `test.area@bebang.ph` | Submit order with 5 items via UI (multi-item edge case) | All 5 items appear in SI/PI/SE; GL has 5 inventory rows | Order page can't take 5 items, or one of the generators drops items |
| `test.scm@bebang.ph` | Dispatch with reduced qty (order 10, dispatch 7) | SI/PI/SE reflect 7, not 10 | Partial-fulfillment broken |
| `test.supervisor@bebang.ph` | Receive page: reject ALL items | WR status="With Issues"; SI either not created OR zero-amount; document expected behavior | Full rejection broken |

## Test Data Seeding Contract

### Records the scenarios depend on
- **Test User accounts** (from `memory/testing-accounts.md`): `test.area@bebang.ph`, `test.scm@bebang.ph`, `test.supervisor@bebang.ph`, `Administrator` (password from `BeiTest2026!` or production Doppler)
- **Warehouse.custom_area_supervisor** = `test.area@bebang.ph` on all 49 canonical warehouses (granted by `scripts/s209_grant_test_area_access.py` in beforeAll, reverted in afterAll)
- **49 canonical store Companies + Warehouses + Customers** — all on production via S247 (no seeding needed)
- **BKI Trade Supplier** at `BEBANG KITCHEN INC. - Trade` with per-Company `accounts[]` entries (S247 P4b applied)
- **S247-required master data** on all 49 stores: `Company.cost_center`, `Company.stock_received_but_not_billed`, `Warehouse.account=1104210`, `Company.enable_perpetual_inventory=1` (S247 P4a + P4b applied)
- **Existing BEI Store Order numbers** (real production orders) — fixture `s204_all_stores.json` references real `custom_bei_store_order` values
- **Item codes** for orders — Phase 4 multi-item / partial / rejection need at least 5 distinct items with stock at the BKI source warehouse. Item codes + canonical source warehouse are sourced from `output/l3/s253/audit/bki_source_inventory.json` (written by P0.12 SSM probe). If P0.12's probe finds fewer than 5 items with `actual_qty ≥ 10`, seed top-up via `/frappe-bulk-edits` Stock Entry and record in teardown ledger.

### Pre-test seeding
- **Run `scripts/s209_grant_test_area_access.py`** in P0 beforeAll (idempotent — adds test.area as area_supervisor on all 49 warehouses). Tracked in ledger.
- **For Phase 4 multi-item:** verify ≥5 distinct DRY items have `actual_qty ≥ 10` at the BKI source warehouse (e.g. `BKI - PROCESSED INV - HUB` or whatever canonical source). If short, use `/frappe-bulk-edits` to bulk-insert Stock Entry. Records each seeded Stock Entry in `output/l3/s253/teardown_ledger.json` for reversal at closeout.

### Teardown
- **Run `scripts/s209_revert_test_area_access.py`** in afterAll (restores original Warehouse.custom_area_supervisor values per ledger).
- **Test SIs/PIs/SEs created during runs:** every doc gets a `cleanupLedger.record()` entry. Closeout phase iterates the ledger, cancels Submitted docs (which trigger cascade), then force-deletes.
- **Stock seeds from Phase 4 (if any):** reverse-Stock-Entry to net them out, or delete the seed entry directly via `/frappe-bulk-edits`.

### Teardown ledger path
- `output/l3/s253/teardown_ledger.json` with `{doctype, name, action, original_values}` per seeded record
- `output/l3/s253/teardown_complete.json` with verified-removed proof

### Teardown verification
- Phase 6 final task: query `tabSalesInvoice WHERE company='BEBANG KITCHEN INC.' AND name LIKE 'BKI-SI-2026-%-S253%'` (or any S253-tagged identifier) returns 0 rows
- Query `tabPurchase Invoice WHERE bki_si_reference IN (test_si_list)` returns 0 rows
- Query `tabStock Entry WHERE bki_si_reference IN (test_si_list)` returns 0 rows

### Reference skill
`/frappe-bulk-edits` for Stock Entry seeding (if needed). Sweep workflow does NOT use it for SI/PI/SE creation (those go through real UI flow).

## Failure Response

- **Mode A (app bug found in production code):** Add to `output/l3/s253/DEFECTS.md`, do NOT touch the test or library, file a separate fix PR after S253 ships, re-run the failed scenario after fix deploy.
- **Mode B (test bug — flaky or wrong selector):** Fix the test or Page Object. If the fix is general-purpose (e.g. better wait pattern), promote to the Page Object base class (qa-test-library-discipline three-uses rule).
- **Mode C (brittleness/timing):** Fix the LIBRARY (Page Object base or fixture), not the spec. No `page.waitForTimeout(N)` hacks. No `retry(3)` masking. If ≥3 library fixes happen during execution, emit `output/l3/s253/LIBRARY_IMPROVEMENTS.md` as closeout artifact.

## Sentry Observability

This sprint does NOT add new `@frappe.whitelist()` endpoints (test-only). If Phase 1 SM MEGAMALL fix requires a backend code change in `hrms/api/dispatch.py` or similar, that fix MUST:
1. Call `set_backend_observability_context(module="dispatch", action="<function>", mutation_type="<type>")` at function entry
2. Reference: `.claude/rules/sentry-observability.md`

Frontend changes (bei-tasks repo): all Page Objects + assertions are test-only code (`tests/e2e/`), not production routes — no Sentry instrumentation needed.

## Zero-Skip Enforcement

Every task MUST be implemented. If a task cannot be completed, the agent STOPS and asks Sam.

### Forbidden behaviors
- ❌ Skipping a task silently
- ❌ Marking partial work as "done"
- ❌ Replacing a task with a simpler version without Sam's approval
- ❌ "Deferred to next sprint" — Phases 0-6 ship together
- ❌ Implementing happy path only, skipping edge cases (Phase 4 is explicitly all-3-scenarios)
- ❌ Combining tasks and dropping features
- ❌ Using `page.waitForTimeout(N)` to mask flakiness (library fix required instead)
- ❌ Using `retry(3)` to mask flakiness
- ❌ Using `page.request.*` / `fetch()` in workflow sections (read-only API verification permitted)
- ❌ Hardcoding store literals (use fixture)

### Verification script (machine-verifiable phase gate)
After each phase, agent runs `output/l3/s253/verify_phase_N.py` which uses `git diff --name-only` + `grep -c "MUST_CONTAIN string"` to verify the phase's deliverables exist. FAIL blocks next phase.

```python
# Complete CHECKS — agent runs after each phase. ANY False = STOP and fix that task.
import json, re, subprocess
from pathlib import Path

S253 = Path("output/l3/s253")
HRMS_BASE = Path(".")  # hrms worktree
TASKS = Path("F:/Dropbox/Projects/bei-tasks-s253-bki-store-e2e-completion")

def file_has(path, needle):
    p = Path(path)
    return p.exists() and needle in p.read_text(encoding="utf-8", errors="ignore")

def git_diff_has(repo, filepath):
    r = subprocess.run(["git", "-C", str(repo), "diff", "--name-only", "HEAD~1"], capture_output=True, text=True)
    return filepath in r.stdout

CHECKS = {
    "P0": [
        ("REMOTE_TRUTH_BASELINE.json exists", lambda: (S253/"state/REMOTE_TRUTH_BASELINE.json").exists()),
        ("ACTIVE_RUN.json exists", lambda: (S253/"state/ACTIVE_RUN.json").exists()),
        ("SURFACE_OWNERSHIP_MATRIX.csv exists", lambda: (S253/"state/SURFACE_OWNERSHIP_MATRIX.csv").exists()),
        ("library_audit.md exists", lambda: (S253/"audit/library_audit.md").exists()),
        ("canonical preflight: ALL CANONICAL", lambda: file_has(S253/"verification/canonical_preflight_baseline.txt", "ALL CANONICAL")),
        ("Custom Field gate: pi_has_field true", lambda: json.loads((S253/"verification/custom_field_gate.json").read_text())["pi_has_field"] is True),
        ("Custom Field gate: se_has_field true", lambda: json.loads((S253/"verification/custom_field_gate.json").read_text())["se_has_field"] is True),
        ("bki_source_inventory.json has >=5 items", lambda: len(json.loads((S253/"audit/bki_source_inventory.json").read_text())["inventory_items"]) >= 5),
        ("loggedInDeskAdmin fixture exists in bei-tasks", lambda: file_has(TASKS/"tests/e2e/fixtures/auth.ts", "loggedInDeskAdmin")),
        ("bki_company_case.json exists (P0.13 soft check)", lambda: (S253/"verification/bki_company_case.json").exists()),
    ],
    "P1": [
        ("sm_megamall_dispatch_rca.md exists", lambda: (S253/"verification/sm_megamall_dispatch_rca.md").exists()),
        ("RCA has Classification line", lambda: file_has(S253/"verification/sm_megamall_dispatch_rca.md", "**Classification:** Mode")),
        ("dispatch_diag_errorlog.json exists", lambda: Path("tmp/s253/dispatch_diag_errorlog.json").exists()),
        ("sm_megamall_mr_state.json exists", lambda: Path("tmp/s253/sm_megamall_mr_state.json").exists()),
        ("Mode A => commit OR Mode D => DEFECTS.md entry", lambda: file_has(S253/"DEFECTS.md", "SM MEGAMALL") or git_diff_has(HRMS_BASE, "hrms/api/")),
    ],
    "P2": [
        ("s253 spec file exists", lambda: (TASKS/"tests/e2e/specs/s253-bki-store-e2e-completion.spec.ts").exists()),
        ("FrappeDeskSubmitPage exists", lambda: (TASKS/"tests/e2e/pages/FrappeDeskSubmitPage.ts").exists()),
        ("glAssertions.ts exports assertPairedDocGLChain", lambda: file_has(TASKS/"tests/e2e/assertions/glAssertions.ts", "export") and file_has(TASKS/"tests/e2e/assertions/glAssertions.ts", "assertPairedDocGLChain")),
        ("assertion checks for 5 rows (=== 5)", lambda: file_has(TASKS/"tests/e2e/assertions/glAssertions.ts", "=== 5") or file_has(TASKS/"tests/e2e/assertions/glAssertions.ts", "== 5")),
        ("assertion references SRBNB account_type", lambda: file_has(TASKS/"tests/e2e/assertions/glAssertions.ts", "Stock Received But Not Billed")),
        ("gl_post_submit_evidence.json exists", lambda: (S253/"verification/gl_post_submit_evidence.json").exists()),
        ("evidence rows have 5 per pair", lambda: all(len(r["gl_rows"]) == 5 for r in json.loads((S253/"verification/gl_post_submit_evidence.json").read_text())["runs"])),
    ],
    "P3": [
        ("SICancelPage.ts exists", lambda: (TASKS/"tests/e2e/pages/SICancelPage.ts").exists()),
        ("glAssertions.ts exports assertCancelCascadeOrder", lambda: file_has(TASKS/"tests/e2e/assertions/glAssertions.ts", "assertCancelCascadeOrder")),
        ("glAssertions.ts exports assertPairedDocsAfterSICancel", lambda: file_has(TASKS/"tests/e2e/assertions/glAssertions.ts", "assertPairedDocsAfterSICancel")),
        ("Spec uses waitForDocStatus, NOT waitForTimeout(5000)", lambda: file_has(TASKS/"tests/e2e/specs/s253-bki-store-e2e-completion.spec.ts", "waitForDocStatus") and not file_has(TASKS/"tests/e2e/specs/s253-bki-store-e2e-completion.spec.ts", "waitForTimeout(5000)")),
        ("cancel_cascade_evidence.json exists", lambda: (S253/"verification/cancel_cascade_evidence.json").exists()),
        ("SE-first timestamp order verified", lambda: all(r["se_cancel_ts"] < r["pi_action_ts"] for r in json.loads((S253/"verification/cancel_cascade_evidence.json").read_text())["runs"])),
        ("PI stays docstatus=1 with Comment (submitted case)", lambda: file_has(S253/"verification/cancel_cascade_evidence.json", "Finance review required")),
    ],
    "P4": [
        ("Spec uses submitOrderWithExplicitQty (NOT submitOrderWithExactItems)", lambda: file_has(TASKS/"tests/e2e/specs/s253-bki-store-e2e-completion.spec.ts", "submitOrderWithExplicitQty") and not file_has(TASKS/"tests/e2e/specs/s253-bki-store-e2e-completion.spec.ts", "submitOrderWithExactItems")),
        ("Spec uses dispatch({qtyOverrides}) (NOT dispatchPartial)", lambda: file_has(TASKS/"tests/e2e/specs/s253-bki-store-e2e-completion.spec.ts", "qtyOverrides") and not file_has(TASKS/"tests/e2e/specs/s253-bki-store-e2e-completion.spec.ts", "dispatchPartial")),
        ("ReceivingPage.rejectAll method added", lambda: file_has(TASKS/"tests/e2e/pages/ReceivingPage.ts", "rejectAll")),
        ("full_rejection_expected.md exists with single branch", lambda: file_has(S253/"audit/full_rejection_expected.md", "Expected branch:")),
        ("edge_cases_evidence.json exists", lambda: (S253/"verification/edge_cases_evidence.json").exists()),
        ("3 edge scenarios in spec", lambda: all(file_has(TASKS/"tests/e2e/specs/s253-bki-store-e2e-completion.spec.ts", s) for s in ['"Edge: multi-item"', '"Edge: partial fulfillment"', '"Edge: full rejection"'])),
    ],
    "P5a": [
        ("sweep_batch_1.txt exists with 22 stores", lambda: len((S253/"audit/sweep_batch_1.txt").read_text().strip().splitlines()) == 22),
        ("S253_SWEEP env var filter in spec", lambda: file_has(TASKS/"tests/e2e/specs/s253-bki-store-e2e-completion.spec.ts", "S253_SWEEP")),
        ("S253_RESUME_FROM env var filter in spec", lambda: file_has(TASKS/"tests/e2e/specs/s253-bki-store-e2e-completion.spec.ts", "S253_RESUME_FROM")),
        ("full_sweep_49_stores.json has >=27 entries (5 S252 + 22 batch1)", lambda: len(json.loads((S253/"verification/full_sweep_49_stores.json").read_text())["stores"]) >= 27),
    ],
    "P5b": [
        ("sweep_batch_2.txt exists with 22 stores", lambda: len((S253/"audit/sweep_batch_2.txt").read_text().strip().splitlines()) == 22),
        ("full_sweep_49_stores.json has 49 entries", lambda: len(json.loads((S253/"verification/full_sweep_49_stores.json").read_text())["stores"]) == 49),
        ("DEFECTS.md exists with classification for any non-PASS", lambda: (S253/"DEFECTS.md").exists()),
        ("No more than 5 same-class failures across batch 2", lambda: (lambda rows: sum(1 for r in rows if r.get("verdict") != "PASS") <= 5)(json.loads((S253/"verification/full_sweep_49_stores.json").read_text())["stores"][-22:])),
    ],
    "P6": [
        ("teardown_complete.json exists", lambda: (S253/"teardown_complete.json").exists()),
        ("teardown leftover_count == 0", lambda: json.loads((S253/"teardown_complete.json").read_text())["leftover_count"] == 0),
        ("canonical_preflight_post.txt has 'ALL CANONICAL'", lambda: file_has(S253/"verification/canonical_preflight_post.txt", "ALL CANONICAL")),
        ("SUMMARY.md exists (>=80 lines)", lambda: len((S253/"SUMMARY.md").read_text().splitlines()) >= 80),
        ("Plan YAML status COMPLETED", lambda: file_has(Path("docs/plans/2026-05-16-sprint-253-bki-store-e2e-completion.md"), "status: COMPLETED")),
        ("SPRINT_REGISTRY.md S253 row COMPLETED", lambda: re.search(r"\| `S253` \|.*COMPLETED", Path("docs/plans/SPRINT_REGISTRY.md").read_text(), re.MULTILINE) is not None),
    ],
}

# Runtime: `python output/l3/s253/verify_phase_N.py P3` → exits 1 if any check False
import sys
phase = sys.argv[1]
failures = []
for name, fn in CHECKS[phase]:
    try:
        ok = fn()
    except Exception as e:
        ok = False
        name = f"{name} (EXCEPTION: {e})"
    if not ok:
        failures.append(name)
if failures:
    print(f"PHASE {phase} FAILED — {len(failures)} CHECKS:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print(f"PHASE {phase} OK — {len(CHECKS[phase])} CHECKS PASS")
sys.exit(0)
```

## L3 Handoff Gate

Plan status after agent execution: `DEPLOYED` (PRs created + merged + deployed). Only verified L3 evidence flips to `COMPLETED`. Agent cannot mark COMPLETED without:
- `teardown_complete.json` confirming 0 leftover docs
- 49-store sweep evidence file showing entry count = 49
- All 5 gap-closure scenarios with verdict (P1 SM MEGAMALL classification, P2 GL evidence, P3 cancel evidence, P4 edge evidence, P5 sweep evidence)

## Execution Workflow

- **Test local:** `doppler run --project bei-erp --config dev -- npx playwright test tests/e2e/specs/s253-bki-store-e2e-completion.spec.ts`
- **Sentry (if Phase 1 backend fix):** `/deploy-frappe` (Sam mediates)
- **PR merge + deploy:** Sam handles per PR-handoff rule. Agent creates PRs, shares URLs, stops.

## Phase Completion Checklist (template — agent fills in during execution)

| Phase | Status | Evidence | Skipped? | Why? |
|---|---|---|---|---|
| 0 | | output/l3/s253/state/ACTIVE_RUN.json + library_audit.md | | |
| 1 | | output/l3/s253/verification/sm_megamall_dispatch_rca.md | | |
| 2 | | output/l3/s253/verification/gl_post_submit_evidence.json | | |
| 3 | | output/l3/s253/verification/cancel_cascade_evidence.json | | |
| 4 | | output/l3/s253/verification/edge_cases_evidence.json | | |
| 5a | | output/l3/s253/verification/full_sweep_49_stores.json (after batch 1) | | |
| 5b | | output/l3/s253/verification/full_sweep_49_stores.json (49 final) | | |
| 6 | | output/l3/s253/SUMMARY.md + teardown_complete.json + COMPLETED in registry | | |

## Amendment History
- 2026-05-16 — v1.0 — Initial plan written per CEO directive after S252 PR #755/#466 (5 remaining gaps identified). Cold-start ready: all paths verified, all credentials sourced from Doppler, all source files referenced with line numbers, all 49 stores enumerable from existing fixture, all Page Objects referenced from existing infrastructure.
- 2026-05-16 — v1.1 — Audit-driven hardening. `/audit-plan-bei-erp` produced 14 verified blockers (6 CRITICAL + 7 WARNING + 1 INFO) across 9 domain audits + code-verifier + adversarial fact-checker. Audit artifacts at `output/plan-audit/sprint-253-bki-store-e2e-completion/`. Amendments applied:
  - **C1 — PI cascade asymmetry:** P3.3 `assertPairedDocsRemoved` renamed to `assertPairedDocsAfterSICancel` with explicit `piWasSubmitted` branch — verifies SE-cancelled + PI-stays-docstatus=1-with-Comment for submitted case (matches `bki_store_pi_generator.py:405-422` which does NOT auto-cancel submitted PIs). P3.4 step (d) calls the renamed assertion. Evidence file checks for "Finance review required" Comment.
  - **C2 — `loggedInDeskAdmin` + Administrator credential:** Added P0.10 to create the fixture in `bei-tasks/tests/e2e/fixtures/auth.ts` (separate BrowserContext targeting HQ_URL, password sourced from `FRAPPE_ADMIN_PASSWORD` via Doppler `bei-erp/dev`).
  - **C3 — GL row count 5 not 4:** Requirements Regression Checklist line 159 normalized to "ALL 5 buyer-side GL rows" with explicit row enumeration. P2.2 assertion now requires `=== 5` row count check after buyer-Company filter. P2.6 evidence shape requires `len(rows) == 5`.
  - **C4 — `bki_si_reference` Custom Field gate:** Added P0.11 SSM probe with HARD STOP via `frappe.db.has_column` on both Purchase Invoice and Stock Entry. Added to `stop_only_for`.
  - **C5 — `verify_phase_N.py` incomplete:** Expanded Zero-Skip Enforcement CHECKS dict to ALL 7 phases (P0, P1, P2, P3, P4, P5a, P5b, P6) with concrete file-exists + content-match + JSON-row-count assertions. Removed `# ... per phase` placeholder.
  - **C6 — Teardown leftover not STOP:** P6.1 now mandates HARD STOP if `leftover_count > 0` after 3 retries. Added to `stop_only_for`.
  - **W1 — Phase 1 wrong file:** P1.3 redirected to `hrms/api/warehouse.py` (dispatch.py is BEI Distribution Trip logistics, ZERO `per_transferred` hits).
  - **W3 — BKI source warehouse vague:** Added P0.12 SSM probe to discover canonical BKI source warehouse + 5 distinct DRY items, writes to `output/l3/s253/audit/bki_source_inventory.json`. Phase 4 reads from this file. `inventory.ts` reference removed.
  - **W4 — Full rejection BIR risk:** P4.6 mandates pre-step reading of `hrms/api/warehouse.py:complete_warehouse_receiving` + writing `full_rejection_expected.md` with ONE expected branch (not "OR"). If branch B (zero-value SI), DEFECT entry mandatory.
  - **W5 — Cross-domain isolation:** P0.10 fixture explicitly creates separate BrowserContext for HQ_URL.
  - **W6 — Duplicate Page Object methods:** P4.1/P4.2 explicitly reuse `submitOrderWithExplicitQty` + `dispatch({qtyOverrides})`. P0.7 library audit lists this. CHECKS dict enforces `submitOrderWithExactItems` + `dispatchPartial` are NEVER created.
  - **W7 — Wait 5s self-contradiction:** P3.4 step (b) replaced "Wait 5s for cascade hooks" with `await waitForDocStatus({...timeoutMs: 15000})` polling.
  - **W2 — Phase 5 per-store resume:** P5a.2 adds `S253_RESUME_FROM=<store_name>` env var. P5a.4 mandates per-store evidence append (not batch-final write).
  - **Phase 0 preflight (demoted from blocker):** Added P0.13 BKI_COMPANY case verification (soft check; logs warning if production Company case mismatches `"BEBANG KITCHEN INC."`).
  - **I1 — `scripts/s252_recover_evidence.py`:** Reference removed; inline SSM `bench execute frappe.client.get_list` pattern provided in P1.2.
  - **I2 — `cleanupLedger.pendingEntries`:** P0.7 library audit explicitly notes property does not exist; use `entriesSnapshot().length` if needed.
  - **Phase budget:** P0 bumped from 5u to 8u (added 4 tasks); total 71u → 74u (within 80u ceiling). `phase_count: 7` unchanged (P5 is one phase split into 2 batches).
  - **STALE (NOT amended):** 6 false positives caused by lead auditor's local checkout being 198 commits behind origin/production. Files DO exist on origin/production (verified via `git show origin/production:...`). No plan changes needed; correctly noted in audit summary.
  - Re-audit recommended after v1.1: re-run `/audit-plan-bei-erp` and confirm all 6 CRITICAL blockers cleared before `/execute-plan-bei-erp`.
- 2026-05-20 — v1.2 — Re-audit cleanup. `/audit-plan-bei-erp` re-audit confirmed 13/16 v1.0 issues CLOSED (all 6 CRITICAL), 2 PARTIAL, 1 MISDIRECTED, plus 3 new minor issues from v1.1 amendments. v1.2 closes the 3 real new issues:
  - **Python bug (HIGH):** Removed the obfuscated lambda chain at the runtime block of `verify_phase_N.py` that was immediately overwritten by the for-loop `failures = []` reset. Only the for-loop remains.
  - **Evidence split (MEDIUM):** Added 7 v1.1 artifacts to YAML `evidence_committed`: `custom_field_gate.json`, `bki_company_case.json`, `library_audit.md`, `bki_source_inventory.json`, `full_rejection_expected.md`, `sweep_batch_1.txt`, `sweep_batch_2.txt`. Prevents A7 worktree-dirty stops at closeout.
  - **Narrative inconsistency (MEDIUM):** Phase 0 section header updated `(5 units)` → `(8 units)` to match the v1.1 budget bump. `tests/e2e/builders/inventory.ts` references in P4.4 and the Test Data Seeding Contract replaced with `output/l3/s253/audit/bki_source_inventory.json` (the canonical P0.12 output).
  - **MISDIRECTED P0.13 fixed:** Added `bki_company_case.json` existence check to `CHECKS["P0"]` so the soft preflight is actually verified by the machine gate.
  - **GAP-5 fixed:** `CHECKS["P5b"][3]` was `lambda: True` (always passed). Replaced with a real lambda that counts non-PASS verdicts in the last 22 entries of `full_sweep_49_stores.json` and asserts ≤ 5. This now machine-enforces the systemic-failure threshold.
  - **STALE (NOT amended — same 198-commit-behind issue):** Re-audit's "REGISTRY_ROW_MISSING" and "PLAN_FILE_NOT_IN_DOCS_PLANS" are false positives. The S253 row IS in `docs/plans/SPRINT_REGISTRY.md` on the s253 branch (verified). The plan IS at `docs/plans/2026-05-16-sprint-253-bki-store-e2e-completion.md` on the s253 branch. Local production checkout doesn't have them yet — correct, they land when s253 PR merges.
  - **Minor gaps NOT amended (acceptable to fix inline during execution):** GAP-1 SURFACE_OWNERSHIP_MATRIX file-exists not in CHECKS["P0"]; GAP-2 SHA content not verified in REMOTE_TRUTH_BASELINE; GAP-3 P1.5 master-data probe not in CHECKS["P1"]; GAP-4 P5a counts rows but not per-store verdict shape. All four are minor and don't block execution.
  - Phase budget: unchanged (~74 units, P0 still 8u, total still in 80u ceiling). `phase_count: 7` unchanged.
  - Plan is now READY for `/execute-plan-bei-erp`.
