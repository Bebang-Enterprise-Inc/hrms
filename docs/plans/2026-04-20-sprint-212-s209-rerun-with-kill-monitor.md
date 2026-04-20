---
sprint: S212
title: S209 L3 Rerun — fix 3 defects + kill-on-defect sweep monitor
branch: s212-s209-rerun-kill-on-defect
bei_tasks_branch: s212-l3-sweep-monitor
base: production
status: GO
plan_version: v1
plan_date: 2026-04-20
canonical_scope: in
canonical_model_reference: docs/STORE_COMPANY_CANONICAL.md
canonical_preflight: required
depends_on:
  - S209 L3 closeout (PR #650, #654, #655 merged) — established the 20/49 baseline + the three defects this sprint fixes
  - hrms/api/store.py `_create_mr_for_store_order` exists and is currently swallowing exceptions silently (see S209 SWEEP_VERIFICATION_SUMMARY §"Collateral defects")
  - Fiscal Year 2026 has BKI + BEBANG ENTERPRISE + SM TANZA + AYALA VERMOSA linked as companies (S209 manually linked the last two)
execution_mode: autonomous
signoff_authority: single-owner (Sam, CEO)
completed_date:
execution_summary:
---

# S212 — S209 L3 Rerun with Kill-on-Defect Sweep Monitor

## Registry lock (evidence)

```text
| `S212` | Sprint 212 | `s212-s209-rerun-kill-on-defect` (hrms) + `s212-l3-sweep-monitor` (bei-tasks) | TBD | PLANNED 2026-04-20 — S209 L3 Rerun with Kill-on-Defect Monitor. ... | docs/plans/2026-04-20-sprint-212-s209-rerun-with-kill-monitor.md |
```

Cross-check run 2026-04-20: `git branch -a | grep -iE 's21[2-5]'` confirmed S212/S213/S214/S215 free on both hrms and bei-tasks. `ls docs/plans/ | grep sprint-212` returned empty before this plan was written. Registry Next Sprint Reservation advanced to `S213`.

---

## 🟥 Canonical Model Preflight (Mandatory)

Executing agent MUST run before the first code change:

```bash
python scripts/verify_canonical_structure.py
```

Accept only these two outcomes:
- `[RESULT] ALL CANONICAL — no action required` → proceed
- `[RESULT] VIOLATIONS FOUND` with exactly 1 violation, `BILLING_CUST_TIN_EMPTY` on `ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC` → proceed (pre-existing allowed skip, documented in S209 plan)

Any other violation → **STOP** and ask the user. Do NOT add records, flip fields, or create Customers/Warehouses to paper over it.

**Canonical law (summary; full rules in `docs/STORE_COMPANY_CANONICAL.md`):**
- Every store has EXACTLY 1 per-store Company + 1 Warehouse + 1 billing Customer + 1 Internal Customer.
- All four share the same name string (e.g. `SM TANZA - BEBANG MEGA INC.`).
- Warehouse.company = the per-store Company (NEVER the parent).
- Billing Customer: `customer_name` = per-store Company name, `is_internal_customer=0`, `tax_id` = legal entity BIR TIN.

**Forbidden in this plan (without explicit CEO approval in-line):**
- Creating a second Warehouse / Company / Customer for any of the 49 stores.
- Ad-hoc SQL mutations on `tabCompany` / `tabWarehouse` / `tabCustomer`.
- Adding new fallback logic to `resolve_store_buyer_entity`.
- Using the parent Company's Customer for store-level billing.
- Reusing an Internal Customer for a regular SI.
- Hard-deleting any test-created SI / SE / WR — use `cancel()` then reverse GL only.

**Scope claim (what S212 touches):**
- **Reads:** all 49 per-store `Warehouse`, all 49 per-store `Company`, all 49 per-store `Customer`, all `tabSales Invoice` / `tabStock Entry` / `tabWarehouse Receiving` / `tabMaterial Request` / `tabBEI Store Order` created by the sweep.
- **Writes (backend patches):**
  - `hrms/api/store.py::_create_mr_for_store_order` — change error-swallow path to re-raise with structured context (DEFECT-1 fix).
  - `hrms/api/store.py::approve_order` — add post-save verify that the MR row actually exists before returning success (DEFECT-1 fix, belt-and-braces).
  - `hrms/hr/doctype/bei_warehouse_receiving/bei_warehouse_receiving.py::on_submit` (or adjacent SI creation helper) — compute billed qty from accepted rows, not dispatched rows (DEFECT-2 fix).
  - `scripts/s212_link_stores_to_fy.py` (new) — one-off SSM script to append the 47 remaining per-store Companies to Fiscal Year 2026's `companies` table (DEFECT-3 fix).
  - `scripts/s212_sweep_monitor.py` (new) — Python daemon that tails the Playwright log + polls the ledger, kills the `npx playwright` PID on defect patterns, dumps evidence.
- **Writes (temporary, reverted in closeout):** `custom_area_supervisor` on 43 warehouses (already idempotent from S209), test-created `BEI Store Order` + cascading SI/SE/WR/MR rows.
- **Does NOT touch:** per-store `tabCompany` / `tabWarehouse` / `tabCustomer` records (no renames, no field flips), S206 Internal Customers, Chart of Accounts, Cost Centers, `resolve_store_buyer_entity` code, `resolve_warehouse_company` code.

---

## Canonical Model Binding

This feature binds to the canonical model as follows:

| Canonical surface | How S212 uses it |
|---|---|
| `Warehouse.company` | Read via `StoreOrderingPage.submitOrder` → resolves per-store Company for order stamping |
| `resolve_store_buyer_entity(warehouse_docname)` | Implicitly exercised when SI is created; test asserts it returned the exact-name Customer |
| `Sales Invoice.customer` | Asserted == per-store Customer from fixture (NOT parent) |
| `Sales Invoice.company` | Asserted == per-store Company (NOT parent) |
| `Sales Invoice.tax_id` | Asserted == fixture.tin (empty for ORTIGAS GREENHILLS only) |
| `Sales Invoice.items[].qty` | **DEFECT-2 fix asserts this == accepted qty, not dispatched qty** |
| `BEI Store Order.company` | Asserted via `assertOrderCompany` helper |
| `Material Request.custom_target_company` | Asserted == per-store Company |
| `Material Request.name` | **DEFECT-1 fix asserts this row materializes after every successful submit + approve, no silent-swallow path** |
| Fiscal Year 2026 `companies` child table | **DEFECT-3 fix appends all 49 per-store Companies (currently only 4 linked)** |
| Cost centers | Implicitly exercised; S212 does not mutate |

S212 does NOT:
- Infer store identity from warehouse_name string parsing.
- Hardcode parent Company names (BEBANG MEGA INC., TUNGSTEN CAPITAL HOLDINGS OPC, etc.).
- Add its own `store_id` / `branch_code` field parallel to the canonical model.
- Bypass `resolve_store_buyer_entity` by reading `tabCustomer` directly during test execution.

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

S209 L3 ran three sweep rounds (R1 58.5 min, R2 partial, R3 47.6 min) against production and three variance attempts. Final cumulative result: **20/49 unique stores have end-to-end browser-verified Sales Invoice billing**. The 26 residual failures traced to THREE real product-side defects, not test-infra:

1. **[CRITICAL] MR-create silent-swallow in `_create_mr_for_store_order`** — 14/49 R1 orders submitted successfully (order row in `tabBEI Store Order` with `status=Approved`), but the Material Request was never created. Direct SSM probe immediately after the sweep confirmed zero `tabMaterial Request` rows for those orders AND zero Frappe Error Log entries during the sweep window. The savepoint rollback path in the function swallows the upstream exception. In production this leaves silent dangling approved orders — unacceptable.
2. **[MAJOR] V1 short-receive SI-qty defect** — the auto-posted Sales Invoice bills the dispatched qty (10), not the accepted qty (8). When a store rejects 2 of 10 delivered items, the SI still bills 10. Real billing-correctness issue uncovered by V1 variance.
3. **[MINOR] Per-store Companies not linked to Fiscal Year 2026** — only BKI + BEBANG ENTERPRISE were linked at sprint start. S209 manually linked SM TANZA + AYALA VERMOSA to unblock variance seeding. 47 other per-store Companies are still unlinked, which silently fails any Stock Entry / Sales Invoice / Journal Entry posted against them.

Additionally, the S209 sweep wasted ~60 minutes running R2 + R3 after the dominant failure class was already visible in R1. The 3-consecutive-failure circuit breaker was the wrong heuristic — it kept resetting on interleaved passes. The next sweep needs a **pattern-aware kill monitor** that spots "same error fingerprint ≥3 times" and kills the Playwright process the instant it's clear we're grinding through the same defect.

### Why this architecture

**Fix the backend first, then rerun.** Tests aren't flaky — production is. The 30-s test-side retry loops added in S209 round 2 were pointless because the MR was never created, not delayed. Backend patches first, then one clean sweep.

**Kill-on-defect monitor runs as a separate Python daemon, not in Playwright.** Playwright has no hook for "stop after N failures" that matches error-fingerprint buckets. A supervisor Python process tails the log, groups errors by signature, and sends SIGTERM to the `npx playwright test` process when a bucket crosses threshold OR when pass rate drops below policy. Same-PID process-group kill makes sure Chromium children die too.

**Rejected alternative: Add `maxFailures` to playwright.config.ts.** Playwright's built-in max-failures stops the run but doesn't classify error buckets — it would kill on 3 flake-style failures too. We need semantic bucket-based kill ("3 MRs didn't exist" ≠ "3 selector timeouts").

**Rejected alternative: Keep 30-s retry loops and hope for the best.** Proven useless in S209 R2/R3. Retrying a query for a row the backend never creates just wastes wall-clock.

**Rejected alternative: Run V1/V2 variance before fixing DEFECT-2.** V1 will pass the infra and fail on SI.items[0].qty == 8 every time (just like R3). Must fix backend first.

### Key trade-off decisions

| Decision | Chosen | Rejected | Reason |
|---|---|---|---|
| MR-create race fix location | Patch `_create_mr_for_store_order` to re-raise + patch `approve_order` to verify MR exists before returning success | Add retries at the test side (already tried in S209 R2/R3) | Test retries can't find a row that doesn't exist. Must surface backend error. |
| SI-qty source on short-receive | Read accepted qty from the WR items child table (with fallback to dispatched qty when short-receive isn't applicable) | Add a UI toggle for "bill accepted" vs "bill dispatched" | BIR-side: the SI should bill what the store actually received (invoiceable event). Dispatched-but-rejected is a commissary write-off, not a store billable. |
| FY 2026 linking method | One-off SSM Python script that appends all 49 per-store Companies idempotently | Ask operator to add manually via Frappe UI | 49 manual clicks is error-prone. Script is auditable + reusable when new stores get per-store Companies. |
| Sweep monitor lifecycle | Separate daemon launched by the orchestrator (not inside the Playwright process) | Custom Playwright reporter that calls `process.exit(1)` on pattern | Cleaner separation; doesn't couple monitor to Playwright reporter API. Daemon can also kill Playwright cleanly via PID even when Playwright is hanging. |
| Kill threshold | `≥3 failures sharing the same error-fingerprint bucket` OR `pass rate < 50% after 10 completed tests` | `≥3 consecutive failures` (S209's broken heuristic) | Interleaved passes hide dominant defects. Bucket-count + rolling pass rate survives interleaving. |
| Resume behavior | Preserve S209 skip-logic (ledger-driven) so if a defect fix still has gaps the next retry is fast | Force fresh full sweep | We already proved the skip-logic works; let it do its job. |

### Known limitations and their mitigations

| Limitation | Mitigation |
|---|---|
| Fiscal Year link script must run as Administrator | Script invokes `bench execute-script` inside the frappe container via SSM as the `frappe-hrms-admin` IAM user — same pattern as `scripts/s209_generate_fixture.py` |
| `_create_mr_for_store_order` fix must not silently re-enable MR creation via a different path that also swallows | Unit test in `hrms/tests/test_s212_mr_create_surface.py` injects a raise inside the MR `insert()` and asserts `approve_order` returns 500 with the structured error, not 200 |
| SI-qty fix on short-receive must not regress full-receive (accepted == dispatched) | Unit test asserts both code paths: (a) all items accepted → SI bills dispatched; (b) partial accept → SI bills accepted |
| Sweep monitor might kill a sweep that's genuinely slow but eventually succeeds | Threshold tuned to `3 same-bucket failures` (not 3 total). Monitor logs every decision to `output/l3/s212/monitor_decisions.log` for audit |
| 47 per-store Companies already have SIs posted against parent-Company ledgers from production real traffic | The FY link script is additive (appends to child table) — does not move existing ledger entries. S207 seeding already handled COA. |

### Source references

- S209 closeout evidence: `F:/Dropbox/Projects/BEI-ERP/output/l3/s209/SWEEP_VERIFICATION_SUMMARY.md` (defect taxonomy, per-run results, collateral findings)
- S209 plan: `F:/Dropbox/Projects/BEI-ERP/docs/plans/2026-04-20-sprint-209-all-stores-ordering-billing-acceptance.md`
- `_create_mr_for_store_order` silent-swallow: `hrms/api/store.py` line 3806-3950 (savepoint/rollback/log_error/raise pattern)
- S209 library fixes (merged in PR #439 + #440): `F:/Dropbox/Projects/bei-tasks/tests/e2e/pages/*.ts` + `tests/e2e/assertions/*.ts`
- Fiscal Year structure: `tabFiscal Year Company` child table, parent `tabFiscal Year.name='2026'`

---

## Requirements Regression Checklist (v1)

Executing agent MUST verify each of these before claiming COMPLETED:

- [ ] RR-01 — `scripts/verify_canonical_structure.py` exits 0 BEFORE any code change (allowed skip only)
- [ ] RR-02 — DEFECT-1 fix: `hrms/api/store.py::_create_mr_for_store_order` no longer swallows MR-insert exceptions. Unit test `test_s212_mr_create_surface.py` passes.
- [ ] RR-03 — DEFECT-1 fix: `hrms/api/store.py::approve_order` verifies MR row exists after `_create_mr_for_store_order` returns. If missing, throws `frappe.ValidationError` with structured context (order_name, submit_user, elapsed_ms).
- [ ] RR-04 — DEFECT-2 fix: BEI Warehouse Receiving `on_submit` (or adjacent SI creation helper) sets `Sales Invoice Item.qty = WR.items[i].accepted_qty` (not dispatched qty). Unit test covers both full-receive and partial-receive paths.
- [ ] RR-05 — DEFECT-3 fix: `scripts/s212_link_stores_to_fy.py` executes idempotently and ends with all 49 per-store Companies in `tabFiscal Year Company` child table where `parent='2026'`
- [ ] RR-06 — `scripts/s212_sweep_monitor.py` exists and is invokable: `python scripts/s212_sweep_monitor.py --log <log> --pid-file <pid> --ledger <ledger>`
- [ ] RR-07 — Monitor kills the Playwright PID when same-error-fingerprint failures hit ≥3 within a rolling 10-test window
- [ ] RR-08 — Monitor kills the Playwright PID when pass rate drops below 50% after 10 completed tests
- [ ] RR-09 — Monitor dumps `output/l3/s212/monitor_decisions.log` with every bucket-count + kill decision
- [ ] RR-10 — hrms unit tests green locally (`pytest hrms/tests/test_s212_*.py`)
- [ ] RR-11 — hrms unit tests green in SSM-executed mode (against real Frappe)
- [ ] RR-12 — Full 49-store sweep R1 runs to completion OR monitor kills early with a named fingerprint (no silent hangs)
- [ ] RR-13 — If monitor killed, root-cause the fingerprint, patch, rerun. No R2 without patching.
- [ ] RR-14 — V1 short-receive passes: SI.items[0].qty == 8 (accepted qty, NOT dispatched 10)
- [ ] RR-15 — V2 short-dispatch passes: SI.items[0].qty == 8 (dispatched qty, order was 10)
- [ ] RR-16 — Final unique-stores-with-SI count ≥48/49 (ORTIGAS GREENHILLS allowed skip if empty-TIN gate fires)
- [ ] RR-17 — Canonical postcheck identical to preflight (zero net drift)
- [ ] RR-18 — `scripts/s209_cleanup_sweep.py` + direct SSM nuke reduces all S212 test artifacts to zero (assert via ledger + SSM probe)
- [ ] RR-19 — No Sentry errors tagged `module=commissary|warehouse|billing|ordering` during the sweep window (Sentry audit, not just Error Log grep)
- [ ] RR-20 — Evidence files exist: `output/l3/s212/SWEEP_VERIFICATION_SUMMARY.md`, `sweep_ledger.json`, `state_verification.json`, `form_submissions.json`, `api_mutations.json`, `canonical_preflight.txt`, `canonical_postcheck.txt`, `monitor_decisions.log`
- [ ] RR-21 — Branch `s212-s209-rerun-kill-on-defect` on hrms + `s212-l3-sweep-monitor` on bei-tasks, both with PRs open
- [ ] RR-22 — Plan YAML flipped to `status: COMPLETED` + `completed_date: 2026-04-20` + `execution_summary` populated
- [ ] RR-23 — `SPRINT_REGISTRY.md` S212 row flipped to COMPLETED with PR numbers

---

## Ground-Truth Lock

- **evidence_sources:**
  - `F:/Dropbox/Projects/BEI-ERP/output/l3/s209/SWEEP_VERIFICATION_SUMMARY.md` — S209 defect taxonomy + 20/49 baseline
  - `F:/Dropbox/Projects/BEI-ERP/output/l3/s209/sweep_full_run_r3.log` — R3 failure classes + error text
  - `F:/Dropbox/Projects/BEI-ERP/output/l3/s209/variance_run_r3.log` — V1 SI-qty defect evidence (expected 8 received 10)
  - `F:/Dropbox/Projects/BEI-ERP/hrms/api/store.py` — live source of `_create_mr_for_store_order` + `approve_order` (the files this plan patches)
  - `F:/Dropbox/Projects/BEI-ERP/hrms/hr/doctype/bei_warehouse_receiving/bei_warehouse_receiving.py` — live source of the WR on_submit + SI qty logic (DEFECT-2 patch target)
  - `F:/Dropbox/Projects/BEI-ERP/scripts/verify_canonical_structure.py` — the canonical gate script (read-only, unchanged by this plan)
  - `F:/Dropbox/Projects/bei-tasks/tests/e2e/specs/s209-all-stores.spec.ts` — the sweep spec reused as-is (S212 only adds the monitor wrapper around the launch)
  - `F:/Dropbox/Projects/bei-tasks/tests/e2e/specs/s209-variance.spec.ts` — V1/V2 variance spec reused as-is
- **count_method:**
  - metric: `unique store count with end-to-end verified SI`
  - basis: `distinct store values from sweep_ledger.json si-create entries where SI docstatus=1 at the time of assertion`
  - method: Python count of `len(set(e['payload']['store'] for e in ledger if e['kind']=='si-create'))`
- **authoritative_sections:**
  - This plan body is execution-authoritative. Any amendment must edit the plan body, not only append.
- **unresolved_value_policy:**
  - None. Every threshold, file, and endpoint in this plan is grounded in S209 evidence or live source files.

---

## Phase Budget Contract

| Phase | Units | Ceiling check |
|---|---:|---|
| Phase 0 — Preflight + State Capture | 4 | ≤12 OK |
| Phase 1 — DEFECT-1 fix (MR-create surface) | 7 | ≤12 OK |
| Phase 2 — DEFECT-2 fix (SI-qty from accepted) | 6 | ≤12 OK |
| Phase 3 — DEFECT-3 fix (FY 2026 link script) | 3 | ≤12 OK |
| Phase 4 — Sweep monitor daemon | 7 | ≤12 OK |
| Phase 5 — Deploy hrms patches | 3 | ≤12 OK |
| Phase 6 — Full sweep + variance execution (monitored) | 8 | ≤12 OK |
| Phase 7 — Cleanup + closeout | 6 | ≤12 OK |
| **Total** | **44** | ≤80 OK |

- **preferred_split_threshold:** 12
- **hard_limit:** 15
- **normalization_rule:** any phase exceeding 12 at execution time must be split before proceeding.

---

## Anti-Rewind / Concurrent-Run Protection Contract

- **ownership_matrix:** single owner (S212 executor). Files touched exclusively by this sprint:
  - hrms repo: `hrms/api/store.py` (add re-raise + MR-exists verify), `hrms/hr/doctype/bei_warehouse_receiving/bei_warehouse_receiving.py` (SI-qty from accepted), `scripts/s212_*.py`, `hrms/tests/test_s212_*.py`, `output/l3/s212/**/*`
  - bei-tasks repo: NOTHING. Sweep + variance specs reused as-is from `s209-l3-round2-resume` / PR #440. The bei-tasks branch `s212-l3-sweep-monitor` is a **empty protective branch** (no code changes) so S212 has its own PR shell if evidence or config needs to land.
- **protected_surfaces (DO NOT MODIFY):**
  - `hrms/api/store.py::submit_order` (S037 hardened; scope out)
  - `hrms/api/store.py::_resolve_store_order_source_warehouse` (canonical routing)
  - `hrms/utils/supply_chain_contracts.py::resolve_store_buyer_entity` (canonical resolver)
  - `docs/STORE_COMPANY_CANONICAL.md` (SSOT)
  - All 49 per-store `tabCompany` / `tabWarehouse` / `tabCustomer` records
  - S206 Internal Customer records
  - `scripts/verify_canonical_structure.py` (enforcer)
  - `scripts/s209_*.py` (prior-sprint scripts — reuse by invocation, no edits)
- **remote_truth_baseline:**
  - hrms base: `origin/production` HEAD at sprint start (captured in Phase 0 as `output/l3/s212/baseline_sha.txt`)
  - bei-tasks base: `origin/main` HEAD at sprint start
- **active_run_coordination:** S212 is the only active sweep. S210 (tier-A) and S211 (AP consolidation) touch different surfaces (receipts/payments + AP consolidation) and do not collide with store-order or WR on_submit.
- **pretouch_backup:** Phase 1 commit of the `store.py` change runs BEFORE Phase 2 so the MR-create fix is isolated. Phase 2 change is a separate commit. This matters for bisecting if the sweep surfaces a regression.
- **supersession_map:** S212 supersedes the S209 "partial pass" status; S209 evidence is preserved as historical baseline.

---

## Autonomous Execution Contract

- **completion_condition:**
  - All 22 RR items checked
  - Full sweep completed OR monitor-killed with named fingerprint + root-cause patch + retry that hits ≥48/49
  - Variance V1 + V2 both PASS (asserting SI.qty == 8 for both scenarios)
  - Canonical postcheck identical to preflight
  - All S212 artifacts cleaned up (ledger shows `pendingEntries === 0`)
  - PRs created on both repos, plan status flipped to COMPLETED
- **stop_only_for:**
  - Canonical preflight has violation other than the allowed ORTIGAS GREENHILLS skip → STOP
  - Monitor kills sweep AND the fingerprint doesn't map to a known defect class (new unknown failure) → STOP, triage with user
  - Any cleanup failure (SI cancel errors, GL won't reverse) → STOP, do not merge
  - Discovery of a canonical drift (new duplicate Warehouse / Customer / Company) → STOP
- **continue_without_pause_through:**
  - Phase 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → PR creation
- **blocker_policy:**
  - unit test failure → fix code, retry
  - monitor kill on a fingerprint matching DEFECT-1/2/3 → the fix didn't land or didn't deploy → check deploy, rerun
  - monitor kill on a NEW fingerprint → STOP and triage
  - business-data / policy decision → pause
- **signoff_authority:** `single-owner` — Sam (CEO)
- **canonical_closeout_artifacts:**
  - `output/l3/s212/SWEEP_VERIFICATION_SUMMARY.md`
  - `output/l3/s212/sweep_ledger.json` (must show `pendingEntries: 0`)
  - `output/l3/s212/monitor_decisions.log` (daemon kill rationale)
  - `output/l3/s212/canonical_preflight.txt`
  - `output/l3/s212/canonical_postcheck.txt`
  - `output/l3/s212/state_verification.json`
  - `output/l3/s212/form_submissions.json`
  - `output/l3/s212/api_mutations.json`
  - `output/l3/s212/sweep_full_run.log` (final passing run)
  - `output/l3/s212/variance_run.log`
  - `docs/plans/2026-04-20-sprint-212-s209-rerun-with-kill-monitor.md` (status → COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (S212 row → COMPLETED with PR numbers)

---

## Signoff Model

- **mode:** `single-owner`
- **approver_of_record:** Sam Karazi (CEO, BEI)
- **signoff_artifact:** `output/l3/s212/SWEEP_VERIFICATION_SUMMARY.md`
- **note:** No department countersign. PR-handoff: agent creates hrms + bei-tasks PRs and stops; Sam reviews/merges.

---

## Certification Coverage Contract

- **certified_universe:**
  - stores: `49` (same fixture as S209)
  - happy-chain SIs: `49`
  - variance scenarios: `2` (V1 short-receive, V2 short-dispatch)
  - DM-1 assertions per SI: `1` (GL party_type=Customer)
  - A2 VAT assertions per SI: `1` (12% ±1%)
  - A5 TIN assertions per SI: `1` (except ORTIGAS GREENHILLS)
- **closeout_zero_equations:**
  - `review_required` = 0
  - `authoring_required` = 0
  - `unmapped` = 0
  - `required_l4_failed` = 0
  - `required_l4_blocked` = 0
  - `cleanup_ledger.pendingEntries` = 0
- **allowed_skips:**
  - ONLY: `ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC` TIN assertion (DEFERRED to separate BIR data-fill sprint)
- **final_readiness_basis:**
  - `output/l3/s212/SWEEP_VERIFICATION_SUMMARY.md`
  - `output/l3/s212/sweep_ledger.json`
  - `output/l3/s212/canonical_postcheck.txt`

---

## L3 Workflow Scenarios

| ID | User | Action | Expected Outcome | Failure Means |
|---|---|---|---|---|
| HC-1 to HC-49 | test.area + test.scm + test.supervisor | (reuse S209 happy chain per-store) | SI exists with `customer == fixture.customer`, `company == fixture.company`, `tax_id == fixture.tin`, GL party_type=Customer, VAT/net_total ≈ 0.12 | If ≥3 stores fail with the same fingerprint → monitor kills early; root-cause before R2 |
| V1 short-receive | test.area + test.scm + test.supervisor (SM TANZA) | Submit DRY qty=10 → approve → dispatch 10 → accept 8 reject 2 "items missing in transit" | **SI.items[0].qty == 8** (DEFECT-2 fix); source wh -10, dest wh +8 | DEFECT-2 fix didn't land OR WR on_submit SI helper didn't pick up the change |
| V2 short-dispatch | test.area + test.scm + test.supervisor (AYALA VERMOSA) | Pre-seed source=8 → submit qty=10 → approve → dispatch 8 → accept 8 | SI.items[0].qty == 8 (dispatched); source wh -8, dest wh +8; dispatch UI must allow dispatched<ordered | Dispatch UI blocks partial dispatch OR SI bills ordered qty |

---

## Zero-Skip Enforcement

Every task below MUST be implemented. No skipping. No "defer to S213". No silent partials.

### Phase gate verification (machine-readable)

Agent writes `output/l3/s212/verify_phase{N}.py` BEFORE starting each phase. Each script:
1. Runs `git diff --name-only origin/production...HEAD` and asserts every `MUST_MODIFY` file appears.
2. Runs `grep -c <pattern> <file>` per `MUST_CONTAIN` row and asserts ≥ min-hits.
3. Runs `python scripts/verify_canonical_structure.py` and asserts allowed-only violations.
4. Exits non-zero if ANY assertion fails. Blocks progress to next phase.

### Forbidden agent behaviors

- Skipping a phase because "the fix is trivial" — run the phase, write the test, commit.
- Marking the sweep monitor as "done" without proving it actually kills PIDs in a dry-run.
- Running the sweep before all three backend patches are deployed.
- Running V1/V2 before DEFECT-2 fix is deployed.
- Claiming COMPLETED with <48/49 pass count — either sweep hits 48+ or there's a named fingerprint with follow-up sprint.

---

## Files to Create or Modify

### BEI-ERP repo (hrms)

| Action | File | MUST_MODIFY | MUST_CONTAIN |
|---|---|---|---|
| MODIFY | `hrms/api/store.py` | `hrms/api/store.py` | `def _create_mr_for_store_order`, `raise` (after savepoint rollback, not swallow), new verification block in `approve_order` that asserts MR exists |
| MODIFY | `hrms/hr/doctype/bei_warehouse_receiving/bei_warehouse_receiving.py` | `hrms/hr/doctype/bei_warehouse_receiving/bei_warehouse_receiving.py` | `accepted_qty` read from items child table, used in Sales Invoice Item.qty assignment |
| CREATE | `scripts/s212_link_stores_to_fy.py` | `scripts/s212_link_stores_to_fy.py` | `"Fiscal Year"`, `"2026"`, `"append"`, `"idempotent"` |
| CREATE | `scripts/s212_sweep_monitor.py` | `scripts/s212_sweep_monitor.py` | `"subprocess"`, `"SIGTERM"`, `"pass_rate"`, `"fingerprint"`, `"bucket"`, `"kill"` |
| CREATE | `scripts/s212_launch_sweep.sh` (or `.ps1`/`.py` wrapper) | `scripts/s212_launch_sweep.sh` | launches npx playwright + monitor daemon, plumbs PID file |
| CREATE | `hrms/tests/test_s212_mr_create_surface.py` | `hrms/tests/test_s212_mr_create_surface.py` | `test_mr_insert_raises_propagates`, `test_approve_order_verifies_mr_exists` |
| CREATE | `hrms/tests/test_s212_wr_si_qty.py` | `hrms/tests/test_s212_wr_si_qty.py` | `test_full_receive_bills_dispatched`, `test_partial_receive_bills_accepted` |
| CREATE | `output/l3/s212/SWEEP_VERIFICATION_SUMMARY.md` | `output/l3/s212/SWEEP_VERIFICATION_SUMMARY.md` | `"48/49"` (or `"49/49"`), `"V1"`, `"V2"`, `"canonical preflight"`, `"canonical postcheck"`, `"monitor kills"` |
| CREATE | `output/l3/s212/sweep_ledger.json` | — | `"pendingEntries"` = 0 after cleanup |
| CREATE | `output/l3/s212/canonical_preflight.txt` | — | `"CANONICAL OK"` (with ORTIGAS GREENHILLS allowed-skip note) |
| CREATE | `output/l3/s212/canonical_postcheck.txt` | — | `"CANONICAL OK"` |
| CREATE | `output/l3/s212/monitor_decisions.log` | — | each bucket-count decision logged |
| MODIFY | `docs/plans/SPRINT_REGISTRY.md` | `docs/plans/SPRINT_REGISTRY.md` | S212 row flipped to COMPLETED + PRs, Next Sprint → S213 |
| MODIFY | `docs/plans/2026-04-20-sprint-212-s209-rerun-with-kill-monitor.md` | this file | `status: COMPLETED` + `completed_date` + `execution_summary` |

### bei-tasks repo

| Action | File | Why |
|---|---|---|
| (no code changes) | — | Sweep + variance specs reused as-is from S209 round 2 branches. S212 uses the same `s209-all-stores.spec.ts` + `s209-variance.spec.ts` after DEFECT-2 fix deploys. |
| CREATE (optional) | `tests/e2e/support/s212_monitor_bridge.md` | Minimal doc explaining the hrms `scripts/s212_sweep_monitor.py` contract so future sprints can reuse. |

**Note:** If S209 PR #440 (library fixes R2) has not been merged by sprint start, Phase 0 includes a verification that these commits are on `origin/main` before launching the sweep. If not merged, Phase 0 blocks until Sam merges.

---

## Phases

### Phase 0 — Preflight + State Capture (4 units)

Agent Boot Sequence:
1. Read this plan fully.
2. Create sprint branch: `git fetch origin production && git checkout -b s212-s209-rerun-kill-on-defect origin/production`
3. Confirm bei-tasks PR #440 is merged to main (required for sweep skip-logic + library R2 fixes). If not merged, block + ask Sam.
4. Run canonical preflight.
5. Capture baseline SHAs.

| ID | Unit | Task | MUST_MODIFY / MUST_CONTAIN | Source |
|---|---:|---|---|---|
| P0-T1 | 1 | Run `python scripts/verify_canonical_structure.py > output/l3/s212/canonical_preflight.txt` — assert `CANONICAL OK` (or 1 allowed skip) | `output/l3/s212/canonical_preflight.txt` contains `CANONICAL OK` | S209 baseline |
| P0-T2 | 1 | Capture `git rev-parse origin/production` (hrms) + `git rev-parse origin/main` (bei-tasks) → `output/l3/s212/baseline_sha.txt` | file exists with two SHAs | — |
| P0-T3 | 1 | Verify S209 PR #440 is merged to bei-tasks/main (check commit `275fd6b`, `1b73d4a`, `f4e7e56` are in origin/main). If not, STOP and ask Sam. | `git log --oneline origin/main \| grep -E '275fd6b\|1b73d4a\|f4e7e56'` returns 3 hits | S209 PR #440 |
| P0-T4 | 1 | Query Fiscal Year 2026's current `companies` list → `output/l3/s212/fy_2026_before.json`. Expect 4 entries (BKI, BEBANG ENTERPRISE, SM TANZA, AYALA VERMOSA). | file has exactly 4 companies | S209 collateral note |

**Phase 0 Exit gate:** `python scripts/s212_verify_phase.py --phase 0` exits 0.

### Phase 1 — DEFECT-1 fix: MR-create surface + verify (7 units)

| ID | Unit | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---:|---|---|
| P1-T1 | 2 | In `hrms/api/store.py::_create_mr_for_store_order`, change the except path to `frappe.log_error(...) ; raise` (or `raise e from None` with structured message) so the caller sees the real exception instead of a silent `None` return. | `hrms/api/store.py` grep `raise` in the savepoint rollback block; no bare `return None` in that block |
| P1-T2 | 2 | In `hrms/api/store.py::approve_order`, after `mr_name = _create_mr_for_store_order(order)`, add `if not mr_name or not frappe.db.exists("Material Request", mr_name): frappe.throw(...)` with structured context. Remove the existing `if not mr_name: frappe.throw(...)` only if it's duplicate; otherwise extend it. | `hrms/api/store.py` grep `frappe.db.exists("Material Request"` + `order_name` in the throw message |
| P1-T3 | 1 | Write `hrms/tests/test_s212_mr_create_surface.py` with two tests: (a) `test_mr_insert_raises_propagates` — monkey-patches `frappe.new_doc("Material Request").insert` to raise, asserts `_create_mr_for_store_order` re-raises; (b) `test_approve_order_verifies_mr_exists` — monkey-patches `_create_mr_for_store_order` to return a non-existent name, asserts `approve_order` throws ValidationError. | `hrms/tests/test_s212_mr_create_surface.py` grep `test_mr_insert_raises_propagates`, `test_approve_order_verifies_mr_exists` |
| P1-T4 | 1 | Run `bench --site hq.bebang.ph run-tests --module hrms.tests.test_s212_mr_create_surface` via SSM; assert both pass. | SSM stdout contains `2 passed` |
| P1-T5 | 1 | Commit Phase 1: `git add hrms/api/store.py hrms/tests/test_s212_mr_create_surface.py && git commit -m "fix(S212 DEFECT-1): _create_mr_for_store_order re-raises + approve_order verifies MR exists"` | commit message contains `S212 DEFECT-1`; `git log --oneline -1` matches |

**Phase 1 Exit gate:** `python scripts/s212_verify_phase.py --phase 1` exits 0; tests pass.

### Phase 2 — DEFECT-2 fix: SI-qty from accepted qty on short-receive (6 units)

| ID | Unit | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---:|---|---|
| P2-T1 | 2 | Locate the Sales Invoice creation helper invoked from BEI Warehouse Receiving's `on_submit` (likely `_create_si_from_wr_accepted(wr)` or inline in `bei_warehouse_receiving.py`). Change Sales Invoice Item `qty` source from `dispatched_qty` (or SE items) to `accepted_qty` from WR items. For full-receive case (accepted == dispatched), behavior is identical; for short-receive it drops to accepted. | `hrms/hr/doctype/bei_warehouse_receiving/bei_warehouse_receiving.py` grep `accepted_qty` used in SI Item qty assignment |
| P2-T2 | 2 | Write `hrms/tests/test_s212_wr_si_qty.py` with two tests: (a) `test_full_receive_bills_dispatched` — sets items accepted=10 dispatched=10, asserts SI.items[0].qty == 10; (b) `test_partial_receive_bills_accepted` — sets items accepted=8 dispatched=10 rejected=2, asserts SI.items[0].qty == 8. | `hrms/tests/test_s212_wr_si_qty.py` grep `test_full_receive_bills_dispatched`, `test_partial_receive_bills_accepted` |
| P2-T3 | 1 | Run `bench --site hq.bebang.ph run-tests --module hrms.tests.test_s212_wr_si_qty` via SSM; assert both pass. | SSM stdout contains `2 passed` |
| P2-T4 | 1 | Commit Phase 2: `git add hrms/hr/doctype/bei_warehouse_receiving/bei_warehouse_receiving.py hrms/tests/test_s212_wr_si_qty.py && git commit -m "fix(S212 DEFECT-2): SI bills accepted qty on short-receive, not dispatched"` | commit message contains `S212 DEFECT-2` |

**Phase 2 Exit gate:** `python scripts/s212_verify_phase.py --phase 2` exits 0; tests pass.

### Phase 3 — DEFECT-3 fix: FY 2026 link script (3 units)

| ID | Unit | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---:|---|---|
| P3-T1 | 2 | Write `scripts/s212_link_stores_to_fy.py` — SSM-driven. Queries all 49 per-store Companies from `tabCompany WHERE entity_category='Store' AND operational_status NOT IN ('Permanently Closed','Dormant')`. Loads `tabFiscal Year` name=`2026`. Appends any missing Company to `fy.companies` child table. Saves with `ignore_permissions=True`. Emits `output/l3/s212/fy_2026_after.json`. | `scripts/s212_link_stores_to_fy.py` grep `"Fiscal Year"`, `"2026"`, `"append"`, `ignore_permissions` |
| P3-T2 | 1 | Run the script. Assert end-state has all 49 per-store Companies in `tabFiscal Year Company WHERE parent='2026'`. | `output/l3/s212/fy_2026_after.json` has 4 pre-existing + 47 new = 51+ entries (includes parents that were already linked); ledger shows 47 new links appended |

**Phase 3 Exit gate:** `python scripts/s212_verify_phase.py --phase 3` exits 0.

### Phase 4 — Sweep monitor daemon (7 units)

| ID | Unit | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---:|---|---|
| P4-T1 | 3 | Write `scripts/s212_sweep_monitor.py` — Python daemon with these responsibilities: (a) opens `--log` file in follow mode (tail -f style); (b) parses lines matching Playwright error patterns; (c) extracts error fingerprint via regex: everything after `Error:` up to first `at ` line, normalized by stripping docnames (`BEI-ORD-\d+-\d+` → `<ORDER>`, `MAT-MR-\d+-\d+` → `<MR>`, etc.); (d) counts fingerprints in rolling window; (e) also reads `--ledger` periodically to count `si-create` entries and derive pass rate after N completed tests; (f) on threshold hit, reads `--pid-file` and sends SIGTERM to PID (+ process group on Unix; taskkill /T on Windows); (g) writes every decision to `--decision-log`. | `scripts/s212_sweep_monitor.py` grep `subprocess`, `SIGTERM` (or `taskkill`), `fingerprint`, `pass_rate`, `bucket` |
| P4-T2 | 1 | Write `scripts/s212_launch_sweep.sh` (POSIX shell) and `scripts/s212_launch_sweep.ps1` (Windows PowerShell) OR a single Python wrapper `scripts/s212_launch_sweep.py` that: (a) starts `npx playwright test` in background with PID captured; (b) starts `s212_sweep_monitor.py` with that PID; (c) waits for either process to exit; (d) emits final exit status. | Wrapper script exists and is executable |
| P4-T3 | 2 | Dry-run test: write a fake playwright log to `/tmp/fake_log.log` line-by-line simulating 3 same-fingerprint failures. Run the monitor pointed at it with a throwaway PID. Assert monitor logs the kill decision and (would) SIGTERM the PID. Includes a second dry-run for the pass-rate branch (10 tests, <50% pass). | Dry-run test script exists; monitor_decisions.log shows both kill triggers |
| P4-T4 | 1 | Commit Phase 4: `git add scripts/s212_sweep_monitor.py scripts/s212_launch_sweep.* && git commit -m "feat(S212): kill-on-defect sweep monitor daemon"` | commit message contains `S212` + `kill-on-defect` |

**Phase 4 Exit gate:** `python scripts/s212_verify_phase.py --phase 4` exits 0; dry-run monitor kills work.

### Phase 5 — Deploy hrms patches (3 units)

| ID | Unit | Task |
|---|---:|---|
| P5-T1 | 1 | Push branch `s212-s209-rerun-kill-on-defect` to origin. |
| P5-T2 | 1 | Create hrms PR via `GH_TOKEN="" gh pr create --base production --head s212-s209-rerun-kill-on-defect ...`. Include test evidence + verify_phase outputs in PR body. |
| P5-T3 | 1 | Notify user the PR is ready. **STOP here if auto-merge is off. Wait for Sam to merge + deploy. Do NOT proceed to Phase 6 until deploy confirmed via hq.bebang.ph. Once Sam confirms, continue.** |

**Phase 5 Exit gate:** PR merged AND deployed to hq.bebang.ph (verify via `GET /api/method/hrms.api.store.get_order_history` or similar quick sanity check). Sam's signoff in chat required.

### Phase 6 — Full sweep + variance execution (monitored) (8 units)

| ID | Unit | Task |
|---|---:|---|
| P6-T1 | 1 | Grant test.area access (idempotent): `python scripts/s209_grant_test_area_access.py` (reuses S209 script). |
| P6-T2 | 4 | Launch monitored sweep: `python scripts/s212_launch_sweep.py --spec tests/e2e/specs/s209-all-stores.spec.ts --evidence-root output/l3/s212 --kill-same-fingerprint 3 --kill-pass-rate-below 0.5 --kill-pass-rate-after-n 10`. ETA ~60 min for full sweep (serial). Monitor must not kill unless a real defect pattern emerges. |
| P6-T3 | 1 | If monitor killed: inspect `output/l3/s212/monitor_decisions.log`, identify fingerprint, map to DEFECT-1/2/3 or a new defect class. If known → fix didn't land (recheck deploy); if new → STOP and triage with Sam. |
| P6-T4 | 1 | Launch variance (V1 + V2): `python scripts/s212_launch_sweep.py --spec tests/e2e/specs/s209-variance.spec.ts ...`. Assert V1.SI.qty == 8, V2.SI.qty == 8. |
| P6-T5 | 1 | Emit `output/l3/s212/{form_submissions.json,api_mutations.json,state_verification.json}` — same pattern as S209. |

**Phase 6 Exit gate:** ≥48/49 happy-chain PASS + V1 PASS + V2 PASS. If <48/49, retry once (skip-logic ensures fast retry); if still <48/49, stop and triage.

### Phase 7 — Cleanup + closeout (6 units)

| ID | Unit | Task |
|---|---:|---|
| P7-T1 | 2 | Run `python scripts/s209_cleanup_sweep.py` + direct-SSM nuke pattern (from S209 session transcript) to remove every SI/WR/SE/MR/Order created by S212. Assert ledger `pendingEntries === 0` after. |
| P7-T2 | 1 | Run `python scripts/s209_revert_test_area_access.py` — restores pre-sweep `custom_area_supervisor` values. |
| P7-T3 | 1 | Run `python scripts/verify_canonical_structure.py > output/l3/s212/canonical_postcheck.txt`. Assert identical to preflight. |
| P7-T4 | 1 | Write `output/l3/s212/SWEEP_VERIFICATION_SUMMARY.md` with final pass counts + defect-fix evidence + monitor decision log + cleanup reconciliation. |
| P7-T5 | 1 | Flip plan YAML to `status: COMPLETED`, add `completed_date`, `execution_summary`. Update `SPRINT_REGISTRY.md` S212 row. Commit: `git add -f docs/plans/... output/l3/s212/...`. Push to hrms. |

**Phase 7 Exit gate:** `python scripts/s212_verify_phase.py --phase 7` exits 0; both PRs updated with final evidence.

---

## Sentry Observability (DM-7 check)

S212 patches existing `@frappe.whitelist()` endpoints (`approve_order`), does NOT create new whitelisted functions. The patches add `frappe.throw(...)` paths — these go through Frappe's default error handler which already reports to Sentry via the BEI monkey-patch.

- [x] No new whitelisted endpoints → no new `set_backend_observability_context` calls required.
- [x] Existing `set_backend_observability_context` in `approve_order` remains unchanged.

Add to RRC:
- [ ] RR-19 — Sentry audit for sweep window: no new errors tagged `module=commissary|warehouse|billing|ordering`.

---

## Status Reconciliation Contract

At every phase end, the agent updates in the same work unit:
1. `output/l3/s212/SWEEP_VERIFICATION_SUMMARY.md` (running tally)
2. `output/l3/s212/sweep_ledger.json`
3. `docs/plans/2026-04-20-sprint-212-s209-rerun-with-kill-monitor.md` (YAML status if changed)
4. `docs/plans/SPRINT_REGISTRY.md` (at closeout only)
5. PR description on hrms PR

---

## Review Gates (before COMPLETED)

- [ ] `rg 'page\.request|fetch\(' F:/Dropbox/Projects/bei-tasks/tests/e2e/specs/s209-*.spec.ts` returns 0 in workflow specs (reused from S209, already clean)
- [ ] `rg 'return None' F:/Dropbox/Projects/BEI-ERP/hrms/api/store.py` shows no return-None in the MR-create savepoint block
- [ ] Monitor decision log exists and shows decisions (either "below threshold, no kill" or "threshold hit, killed")
- [ ] `python scripts/s212_verify_phase.py --phase 0..7` all exit 0
- [ ] Final unique-stores-with-SI >= 48 (48/49 or 49/49)
- [ ] V1 SI qty == 8, V2 SI qty == 8 (both asserted in evidence)
- [ ] `canonical_postcheck.txt` == `canonical_preflight.txt` (diff shows zero new violation classes)
- [ ] 22 RRC items all `[x]`
- [ ] Cleanup ledger `pendingEntries === 0`

---

## Failure Response (QA library discipline)

Per `.claude/docs/qa-test-library-discipline.md`:

- **Mode A (app bug — real product defect):** file `[BUG]` in Sprint Registry deferred-followups, do NOT touch the test or library, re-run after fix. S212 already identifies DEFECT-1/2/3; Mode A is the expected path for any NEW defect discovered during sweep.
- **Mode B (test bug — wrong assertion or wrong fixture data):** fix the test; if the fix helps other tests, promote to the Page Object / fixture. For S212 this is unlikely since we're reusing S209 specs unchanged.
- **Mode C (brittleness / flakiness):** fix the LIBRARY, NOT the spec. Forbidden: `waitForTimeout(Ns)`, `retry(3)` at spec level, try/catch masking.

**If ≥3 library fixes happen during execution:** emit `output/l3/s212/LIBRARY_IMPROVEMENTS.md` as a closeout artifact.

---

## Library Audit (Phase 0 task — results captured here)

S212 reuses S209 library surfaces ENTIRELY. No new Page Objects, assertions, or fixtures required.

| Surface | S209 source | S212 usage |
|---|---|---|
| `StoreOrderingPage.submitOrderAtSuggested` + `submitOrderWithExplicitQty` | PR #438/#439/#440 | reused unchanged |
| `OrderApprovalPage.approve` (backend-probe-first) | PR #440 | reused unchanged |
| `WarehouseApprovalPage.approve` (MR approval) | PR #440 | reused unchanged |
| `DispatchPage.dispatch` + `qtyOverrides` | PR #440 | reused unchanged |
| `ReceivingPage.accept` + `acceptedQty/rejectedQty` | PR #440 | reused unchanged |
| `assertCompanyChainCorrect` + `assertSIGLPartyIsCustomer` | PR #439 | reused unchanged |
| `assertInventoryDelta` + `withPhtWindow` | PR #439 | reused by variance |
| `assertMRCreatedForOrder` (30s poll) | PR #440 | reused; WILL NOW SUCCEED because backend fix makes MR actually exist |
| `assertSIForOrder` (30s poll) | PR #440 | reused; should succeed consistently once DEFECT-2 fix lands |
| Resume skip-logic in `s209-all-stores.spec.ts` | PR #440 | reused for retry after monitor kill |

**New surfaces this sprint adds (hrms-side only):**
1. `scripts/s212_sweep_monitor.py` — monitor daemon
2. `scripts/s212_launch_sweep.py` — wrapper that ties Playwright + monitor
3. `scripts/s212_link_stores_to_fy.py` — FY 2026 link
4. `hrms/tests/test_s212_mr_create_surface.py` — DEFECT-1 regression guard
5. `hrms/tests/test_s212_wr_si_qty.py` — DEFECT-2 regression guard

**Ownership:** these new hrms scripts become part of the BEI test infrastructure. Future sprints consuming L3 sweeps can reuse the monitor daemon.

---

## Execution Workflow

- Test Python changes locally (optional): `/local-frappe`
- Agent runs `/execute-plan-bei-erp` with this plan
- After Phase 5 (PR created), builder STOPS. Sam reviews + merges + deploys.
- Once deploy confirmed, Sam says "go" in chat and agent resumes Phase 6.
- Agent creates PRs on both repos at closeout and STOPS.

---

## Execution Authority

This sprint is intended for autonomous end-to-end execution EXCEPT for the Phase 5 → Phase 6 gate (requires Sam merge + deploy confirmation). Do not stop for progress-only updates. Only pause for items in the `stop_only_for` list.

---

*Plan authored 2026-04-20 (Monday) PHT by S209 L3 closeout agent after Sam's feedback on wasted R2/R3 sweeps. All factual claims trace to S209 evidence files or live hrms source. Next action: create plan PR and wait for user approval.*
