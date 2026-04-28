---
canonical_id: S225
sprint_name: Sprint 225
plan_filename: 2026-04-26-sprint-225-canonical-warehouse-cleanup-and-pattern-a-safeguard.md
slug: canonical-warehouse-cleanup-and-pattern-a-safeguard

branches:
  hrms: s225-canonical-warehouse-cleanup-and-pattern-a-safeguard

worktrees:
  hrms: F:/Dropbox/Projects/BEI-ERP-s225-canonical-warehouse-cleanup-and-pattern-a-safeguard

status: COMPLETED
created_date: 2026-04-26
completed_date: 2026-04-28
execution_summary: |
  S225 delivered (1) canonical warehouse duplicate cleanup — 2 em-dash clusters consolidated via Material Transfer (PR #689), 49 stores / 0 violations final, Stock Settings flags reverted; (2) Pattern A FOR UPDATE row lock on `create_stock_transfer` covering tabBin + tabBatch (PR #690), Phase 5 stress 10/10 pass with 0 negative-stock and 0 deadlocks; (3) S226 hot-fix for orphan BEI Approval Queue rows (out-of-band, deployed before Phase 2); (4) 7 Sentry-driven defects fixed and deployed via PR #694 (D1 source-route fallback, D2 approve_order idempotency, D3 warehouse queue includes Ordered, D4 lock-wait try/except, D5 Sentry monkey-patch for non-request contexts, D6 sales dashboard non-POS, D7 mosaic on_conflict). Final L3 sweep against PR #694: 32 PASS / 14 FAIL / 3 SKIP (65%, +4 vs pre-PR#694 sweep, no early kill). Residual failures cluster into 3 classes — WarehouseApprovalPage UI button-not-visible (9 stores), DispatchPage non-concurrency residual (4 stores), Warehouse Receiving missing (1 store) — recommended for follow-up sprint S228+. PRs: hrms #688 (S226), #689 (Phase 3), #690 (Phase 4), #691 (Phase 5), #692 (empty — lost code via stash bug, see HANDOFF lesson A), #694 (actual 7-defect ship), #695 (handoff doc).
work_units: 56
phase_count: 8
audit_amendments_applied: 2026-04-26 v2 (B-2/B-4/B-5/B-6/B-7/B-8/B-9/B-10/B-11/B-12/B-13 — see output/plan-audit/s225-canonical-warehouse-cleanup-and-pattern-a-safeguard/verified_blockers.md)
plan_version: 2

canonical_scope: in
canonical_model_reference: docs/STORE_COMPANY_CANONICAL.md
canonical_preflight: required

evidence_committed:
  - output/s225/SUMMARY.md
  - output/s225/RUN_STATUS.json
  - output/s225/RUN_SUMMARY.md
  - output/s225/PHASE_CHECKLIST.md
  - output/s225/verification/canonical_preflight.txt
  - output/s225/verification/canonical_postcheck.txt
  - output/s225/verification/canonical_postcheck_phase3.txt
  - output/s225/verification/canonical_postcheck_phase7.txt
  - output/s225/verification/duplicate_warehouse_audit.json
  - output/s225/verification/duplicate_warehouse_audit.md
  - output/s225/verification/dup_consolidation_dry_run.json
  - output/s225/verification/dup_consolidation_applied.json
  - output/s225/verification/s224_pattern_b_validation.json
  - output/s225/verification/s224_pattern_c_validation.json
  - output/s225/verification/s224_deploy_sha_check.json
  - output/s225/verification/pattern_a_lock_test.json
  - output/s225/verification/pattern_a_concurrency_results.json
  - output/s225/verification/pattern_a_concurrency_summary.md
  - output/s225/verification/sam_consolidation_approval.md
  - output/l3/s225/sweep_full_run.log
  - output/l3/s225/sweep_ledger.json
  - output/l3/s225/monitor_decisions.log
  - output/l3/s225/SWEEP_VERIFICATION_SUMMARY.md

evidence_transient:
  - tmp/s225/probe_*.json
  - tmp/s225/sql_*.txt
  - tmp/s225/console_logs_*.txt
  - tmp/s225/sentry_capture_*.json
  - tmp/s225/playwright_trace_*.zip
  - tmp/s225/git_*.txt

depends_on:
  - S223 (DEFECT-11 + ORTIGAS TIN — merged + deployed)
  - S224 PR #687 (Pattern B idempotency + Pattern C fuzzy resolver — Phase 1 of THIS sprint validates the deploy)

execution_authority: Sam (CEO) — single-owner. No department co-signatures required.
---

# S225 — Canonical Warehouse Cleanup, S224 Validation, Pattern A Safeguard

## v2 — AUDIT RESPONSE (2026-04-26)

This plan has been audited by 6 domain agents + code-verifier + adversarial fact-checker. Results in `output/plan-audit/s225-canonical-warehouse-cleanup-and-pattern-a-safeguard/verified_blockers.md`.

**Audit verdict:** 11 CRITICAL + 4 WARNING blockers. Zero hallucinations. All addressed inline below.

**Phase ordering changed in v2:** Phase 5 (concurrency stress test) and Phase 6 (full L3 sweep) now run AFTER Sam's deploy. New Phase 4.5 is a "wait-for-deploy" gate that polls the Docker container's code SHA. This fixes B-4 (the corrupt-success deploy gap that 4 audit agents independently flagged).

**Key amendments per blocker:**

| Blocker | Severity | Section amended | Fix |
|---|---|---|---|
| B-2 `SR.add_batch()` hallucinated | CRITICAL | Phase 3 task 1 | **Switch from Stock Reconciliation to Material Transfer** (Stock Entry, `stock_entry_type="Material Transfer"`). Removes the v15 SABB complication AND fixes BIR audit trail (W-3). |
| B-4 Phase 4→5 deploy gap | CRITICAL | New Phase 4.5 + Phase 5/6 reorder | Add deploy-SHA verification gate. Phase 5/6 only run AFTER container running merge SHA. |
| B-5 PR merged ≠ deployed | CRITICAL | Phase 1 task 1 + new Phase 4.5 | Add Docker container code SHA probe alongside `gh pr view`. |
| B-6 Pattern B probe broken | CRITICAL | Phase 1 task 2 | Probe constructs `approved_items` from MR's existing items (matches `approve_material_request` validation order at warehouse.py:1219 vs 1228). |
| B-7 Phase 7 filename mismatch | CRITICAL | Phase 7 gate | Phase 3 already writes `canonical_postcheck_phase3.txt`; Phase 7 also writes `canonical_postcheck_phase7.txt`. Closeout gate asserts both exist. |
| B-8 Sweep log filename | CRITICAL | Phase 6 + frontmatter | Reconciled to single path: `output/l3/s225/sweep_full_run.log`. Removed phantom `output/s225/verification/sweep_post_s224_s225.log` references. |
| B-9 Stock conservation one-sided | CRITICAL | Phase 3 task 8 | Added per-item two-sided assertion: duplicate.actual_qty == 0 AND canonical.gain == duplicate.pre_total. |
| B-10 Zero-Skip omits Phase 2+3 | CRITICAL | Zero-Skip Enforcement | Added Phase 2 + Phase 3 to "no deferral" list. |
| B-11 Approval gate ambiguous | CRITICAL | Phase 2 HARD BLOCKER + helper script | New `scripts/s225_check_sam_approval.py` polls PR comments via `gh pr view --comments` and writes the local file when approval token is detected. Removes ambiguity. |
| B-12 bei-tasks worktree | CRITICAL | Phase 0 task 5 + Phase 7 task 6 | Spawn bei-tasks worktree in Phase 0 (with dirty-state check). Remove in Phase 7. |
| B-13 Company-mismatch hard-stop | CRITICAL | Phase 2 task 1 | Audit script now flags `winner.company != loser.company` clusters as `MANUAL_REVIEW_REQUIRED — INTERCOMPANY` and excludes them from "APPROVED ALL" eligibility. |
| W-1 FOR UPDATE batch coverage | WARNING | Phase 4 task 1 | Pre-implementation probe checks `Item.has_batch_no` for affected items. If batch-tracked, lock both `tabBin` AND `tabBatch`. |
| W-3 SR vs Material Transfer | RESOLVED | n/a | Resolved by B-2 fix (we now use Material Transfer, no SR). |
| W-A `s224_diagnose_pattern_a_batches.py` | WARNING | Source references | Use `scripts/s224_query_sentry_api.py` as boto3 SSM template instead. |
| W-B Phase 6 stock-out classification | WARNING | Phase 6 outcome matrix | Added explicit failure-cause classification step. |

**Phase count changed from 8 to 9** to accommodate the new Phase 4.5 (deploy-wait gate). Total work units now 60 (was 56) — still under 80 ceiling.

---

## Bottom line

Three discrete, sequenceable workstreams driven by the S223 sweep findings + Sentry root-cause analysis:

1. **Audit + consolidate canonical warehouse duplicates.** Sentry surfaced one specific duplicate (`3MD LOGISTICS – CAMANGYANAN - BKI` em-dash vs `3MD LOGISTICS - CAMANGYANAN - BKI` hyphen, 648 vs 1095 units of FG004). Sam's directive: don't just fix that one — **audit ALL warehouse duplicates** (em-dashes, smart quotes, double spaces, trailing whitespace, case differences), identify the canonical correct version per duplicate, and consolidate stock without losing any SKU. Disable losers per `disabled=1` rule.

2. **Validate S224 PR #687 deployed and the fixes work.** PR #687 ships Pattern B idempotency (`approve_material_request` no-op when status="Ordered") + Pattern C fuzzy `resolve_warehouse`. Validate via direct REST probes against the deployed backend AND a targeted L3 retest of the 6 stores known to fail with these patterns (4 Pattern B + 2 Pattern C). Confirm the fix shipped, the fix works, and document expected pass count for the next full sweep.

3. **Pattern A safeguard.** Real product fix for the negative-stock race condition observed during S223 sweep: add `SELECT ... FOR UPDATE` row lock around the batch availability check + decrement in `create_stock_transfer` so concurrent dispatches serialize. Plus add `set_backend_observability_context` breadcrumb when batch goes to/below zero so future regressions surface with store + batch tags.

**Hard rule (Sam directive 2026-04-26):** Phase 1 (canonical cleanup) is destructive master-data work. The script is built read-only by default with a `--commit` flag gated on the audit report. Sam reviews the audit JSON before authorizing the consolidation run.

## Design Rationale (For Cold-Start Agents)

### Why this exists

- 2026-04-26: S223 L3 sweep ran with S221+S222 fallbacks reverted per CEO directive. 16/49 PASS, 14 FAIL, 19 not started (kill-monitor terminated early).
- S224 (PR #687) shipped Pattern B + C fixes plus observability gap closure. **PR is open at time of writing — Phase 1 of S225 confirms it merged + deployed before any other work proceeds.**
- Sentry investigation (`output/s223/verification/sentry_event_details.json`) revealed Pattern A's root cause is a race condition under parallel sweep load PLUS a canonical drift bug: `3MD LOGISTICS – CAMANGYANAN - BKI` (em-dash) is a duplicate of the canonical `3MD LOGISTICS - CAMANGYANAN - BKI` (hyphen). 648 units of FG004 are stranded.
- Sam directive 2026-04-26: don't just cleanup that one duplicate — **audit ALL warehouses for similar drift** (BEI has 49+ canonical warehouses + commissary + cold storage hubs). The em-dash slipped past prior canonical audits because `verify_canonical_structure.py` checks per-store canonical structure but doesn't audit the broader warehouse population for typo-duplicates.

### Why this architecture

**Three workstreams, one sprint, sequential:**
1. Validate S224 deploy first (Phase 1) — if S224 didn't ship cleanly we can't claim a baseline for the rest.
2. Canonical audit + consolidation second (Phase 2-3) — touches master data, needs Sam approval gates.
3. Pattern A FOR UPDATE lock third (Phase 4-5) — backend code change, has regression risk on a hot path used by all 49 stores; ships after the other two so the regression check has cleaner inputs.
4. Final L3 retest (Phase 6) verifies the cumulative effect of S223 + S224 + S225.

**Single sprint vs split:** total work units fit under the 80-unit ceiling (56u). Workstreams share the audit infrastructure (canonical preflight/postcheck, sweep harness) and the same hrms branch. Splitting would force 3 cycles of preflight/postcheck/PR/deploy at marginal value.

### Key trade-off decisions

| Decision | Chosen | Rejected | Reason |
|---|---|---|---|
| Audit scope for canonical cleanup | ALL warehouses (49 canonical + commissary + cold storage hubs) | Just the 3MD em-dash one | Sam directive 2026-04-26 — don't band-aid one symptom; find every drift instance once |
| Consolidation method | Stock Reconciliation (ERPNext-native, reversible) | Direct UPDATE on `tabBin` | Stock Reconciliation generates SLEs, preserves audit trail, ERPNext recomputes balances correctly. Direct SQL bypasses safety checks per canonical rule 6. |
| Pattern A fix layer | `SELECT FOR UPDATE` row lock at the batch availability check inside `create_stock_transfer` | Higher-level mutex, optimistic concurrency, retry-on-conflict | FOR UPDATE is the ERPNext-native primitive for this exact case (matches the existing pattern at `warehouse.py:1238` for `approve_material_request`). Mutex/optimistic both add complexity without solving the same window. |
| Sweep-to-validate scope | Targeted (4 Pattern B + 2 Pattern C stores, focused via `--grep`) for Phase 1; full 49-store sweep at Phase 6 only | Full 49-store sweep at every phase | Targeted Phase 1 sweep is ~10 min and proves S224 fixes; full sweep at Phase 6 is ~60 min and proves cumulative S223+S224+S225. Two cheap targeted runs > four expensive full runs. |
| Disabled vs deleted for warehouse duplicates | `disabled=1` (canonical rule 2) | `frappe.delete_doc` | Stock Ledger Entries reference these warehouses; deletion would break GL/SL history. Disable hides them from UI selectors but preserves history. |

### Known limitations and their mitigations

- **Some duplicates may have legitimate history under both names.** Mitigation: the audit phase reports BOTH the canonical and duplicate's full SLE history. The consolidation script uses Stock Reconciliation (which makes a new SLE on the canonical warehouse) rather than rewriting old SLEs. The disabled duplicate keeps its history intact.
- **Pattern A FOR UPDATE introduces lock contention under high concurrency.** Mitigation: lock scope is narrow — only the bin row for the specific item+warehouse being dispatched, held only for the dispatch transaction. Test under 10 concurrent dispatches in Phase 5 and confirm no deadlocks.
- **Phase 1 validation depends on S224 PR #687 being merged + deployed.** If PR #687 stalls in review or deploy fails, Phase 1 blocks Phase 2-6. Mitigation: Phase 1 task 1 is `gh pr view 687 --json state,mergedAt` — if state != MERGED, STOP and surface to Sam. Don't proceed.
- **Full sweep at Phase 6 may surface NEW failure patterns S224 didn't address.** Mitigation: Phase 6 outcome decision matrix explicitly handles the case where pass rate doesn't reach the 36-43/49 projection (file as S226 follow-up; do not re-merge S221/S222 fallbacks).

### Source references

- S223 closeout PR: hrms #685 (sweep evidence committed to `output/l3/s223/`)
- S224 PR (validated by this sprint Phase 1): hrms #687
- Sentry root-cause writeup: `output/s223/verification/pattern_a_b_c_root_cause_analysis.md`
- Sentry event details: `output/s223/verification/sentry_event_details.json`
- Canonical model: `docs/STORE_COMPANY_CANONICAL.md` (Rule 1 = no duplicates, Rule 2 = disable not delete, Rule 6 = no ad-hoc SQL on master records)
- Canonical scripts in scope: `scripts/verify_canonical_structure.py`, `scripts/canonical_scan_store_state.py`
- L3 sweep harness: `scripts/s212_launch_sweep.py` + `scripts/s212_sweep_monitor.py`
- L3 cleanup: `scripts/s209_cleanup_sweep.py`
- S224 SSM diagnostic scripts: `scripts/s224_diagnose_pattern_a_batches.py` (ran successfully — uses `boto3.client("ssm")` pattern)
- Memory lessons: `memory/canonical-store-company-ssot.md`, `memory/feedback_correct_over_fast.md`, `memory/feedback_kill_sweep_fix_backend.md`

## Canonical Model Preflight (Mandatory)

Executing agent MUST run before the first code change in each phase that touches master data:

```bash
python scripts/verify_canonical_structure.py > output/s225/verification/canonical_preflight.txt 2>&1
tail -10 output/s225/verification/canonical_preflight.txt
```

Expected at sprint start: `[RESULT] ALL CANONICAL — no action required` (S223 Phase 5 resolved the only known violation, ORTIGAS GREENHILLS TIN). Any new violation → STOP, ask Sam.

**Canonical law (summary — full rules in `docs/STORE_COMPANY_CANONICAL.md`):**
- Every store has EXACTLY 1 per-store Company + 1 Warehouse + 1 billing Customer + 1 Internal Customer.
- All four share the same name string.
- Warehouse `name` is the docname; `warehouse_name` is the human-readable short form (e.g. `"3MD LOGISTICS - CAMANGYANAN"`).
- Master records with transactional history (Bin, SLE, GL Entry references) are NEVER deleted — `disabled=1` instead.

**Forbidden in this plan (without explicit Sam approval inline in PR):**
- Creating a NEW Warehouse (the cleanup only DISABLES existing duplicates and consolidates stock to the canonical version).
- Direct SQL on `tabWarehouse` / `tabBin` / `tabStock Ledger Entry` to "fix" balances. Use Stock Reconciliation entries which generate proper SLEs.
- Adding new fallback logic to `resolve_store_buyer_entity`, `resolve_warehouse_company`, or any canonical resolver.
- Reusing an Internal Customer for any operation.
- Creating any S206 records (this sprint does NOT touch labor cost-sharing).

**Scope claim:**
- This plan creates ZERO new Companies, Warehouses, Customers, or Internal Customers.
- This plan **DISABLES** N warehouses (count discovered in Phase 2 audit; expected ≥1 — the `3MD LOGISTICS – CAMANGYANAN - BKI` em-dash duplicate; possibly more depending on what the audit finds).
- This plan **CREATES** Stock Reconciliation entries (one per disabled-warehouse SKU pair) to migrate stock from the duplicate to the canonical version. Each Reconciliation has a clear `Title` field referencing this sprint and the source duplicate.
- This plan **MODIFIES** `hrms/api/warehouse.py:create_stock_transfer` (adds `FOR UPDATE` row lock around the batch availability check). Function signature unchanged.
- This plan **READS** canonical resolvers (`resolve_warehouse_company`) for verification but does not modify them.

## Canonical Model Binding

This sprint's changes bind to the canonical model as follows:

- **Phase 2-3 (warehouse cleanup):** disables non-canonical Warehouse rows. Operates ONLY on `tabWarehouse.disabled` and creates `tabStock Reconciliation` records. Does NOT change `Warehouse.company` (which is the per-store Company link), does NOT touch `tabCompany` or `tabCustomer`.
- **Phase 4-5 (Pattern A FOR UPDATE):** modifies `create_stock_transfer` only. Preserves the existing `set_backend_observability_context(module="warehouse", action="create_stock_transfer", ...)` call. Does NOT touch resolvers.
- **Phase 6 (full sweep):** read-only verification.

**Does NOT:**
- Bypass canonical resolvers via warehouse-name string parsing.
- Hardcode parent Company names.
- Add new identifiers parallel to the canonical model.
- Modify Warehouse `parent_warehouse` or `is_group` fields.

**Closeout verifier check:** Phase 7 re-runs `scripts/verify_canonical_structure.py` and asserts zero new violations vs the preflight baseline. Both the disabled duplicates AND the canonical originals must verify clean.

## Worktree Isolation & Evidence Split

```bash
cd F:/Dropbox/Projects/BEI-ERP && git fetch origin --prune
git worktree add F:/Dropbox/Projects/BEI-ERP-s225-canonical-warehouse-cleanup-and-pattern-a-safeguard \
  -B s225-canonical-warehouse-cleanup-and-pattern-a-safeguard origin/production
```

All work happens in the worktree. Main checkout is read-only inspection only.

**Closeout removes the worktree** (Phase 7). If it has uncommitted scratch at closeout, it must be committed to a follow-up branch (never to a merged PR branch) before removal.

**Evidence split (matches frontmatter):**
- Final summaries, audit reports, consolidation ledgers, post-checks, sweep verification → `output/s225/` (committed).
- Mid-run probes, SQL outputs, raw Sentry captures, Playwright traces → `tmp/s225/` (gitignored).

## Anti-Rewind / Concurrent-Run Protection Contract

| Surface | Owner | File globs |
|---|---|---|
| `hrms/api/warehouse.py:create_stock_transfer` | This sprint (Phase 4-5 — adds FOR UPDATE lock) | function only, signature unchanged |
| `tabWarehouse` rows for duplicate canonicals | This sprint (Phase 3 — `disabled=1` + Stock Reconciliation moves stock) | only the rows identified in the Phase 2 audit |
| `scripts/canonical/retire_warehouse_duplicate.py` | This sprint (NEW) | full file |
| `scripts/s225_audit_warehouse_duplicates.py` | This sprint (NEW) | full file |
| `scripts/s225_pattern_a_lock_smoke.py` | This sprint (NEW) | full file |

**Protected surfaces (must not change):**
- `hrms/api/store.py:resolve_warehouse` (just-fixed in S224)
- `hrms/api/warehouse.py:approve_material_request` (just-fixed in S224)
- `hrms/api/warehouse.py:get_pending_material_requests` (just-instrumented in S224)
- All `tabCompany` rows
- All `tabCustomer` rows (no changes)
- Internal Customers (`*  (Internal)`)
- `scripts/verify_canonical_structure.py`, `scripts/canonical_scan_store_state.py` (canonical scripts, read-only here)
- `hrms/api/ordering.py:get_order_review_queue` (just-fixed in S223 DEFECT-11)
- `bei-tasks/tests/e2e/pages/*` — this sprint does NOT modify any test Page Object

**Remote-truth baseline (record at Phase 0 boot):**
- hrms `origin/production` HEAD: capture in `output/s225/verification/baseline.json`

**Pre-touch backup contract:** Before Phase 3 disables any warehouse OR creates any Stock Reconciliation, agent MUST snapshot the warehouse row + all its Bin rows via SSM:
```python
{
    "warehouse_doc": frappe.get_doc("Warehouse", <name>).as_dict(),
    "bin_rows": frappe.db.sql("SELECT * FROM `tabBin` WHERE warehouse=%s", <name>, as_dict=True),
}
```
→ `output/s225/verification/dup_<slug>_before.json`. Same after the consolidation → `dup_<slug>_after.json`.

## Requirements Regression Checklist

Executing agent MUST verify each item before claiming any phase complete:

- [ ] Have I confirmed S224 PR #687 is MERGED and the backend is deployed before starting Phase 2? (Phase 1 task 1)
- [ ] Have I run `scripts/verify_canonical_structure.py` BEFORE the first master-data mutation and AFTER each phase that touches master data, and confirmed zero new violations?
- [ ] Have I gated the consolidation script behind a `--commit` flag (default OFF) and shared the dry-run JSON with Sam BEFORE applying?
- [ ] Have I disabled (NOT deleted) every duplicate warehouse identified in the Phase 2 audit?
- [ ] Have I created a Stock Reconciliation entry (per duplicate × per item) to move stock to the canonical, with a clear `Title` referencing S225?
- [ ] Did the Pattern A FOR UPDATE lock change preserve the existing Sentry observability context (`module="warehouse", action="create_stock_transfer"`)?
- [ ] Have I tested the FOR UPDATE lock under 10 concurrent dispatches in Phase 5 and confirmed no deadlocks + no negative-stock errors?
- [ ] Has every modified `@frappe.whitelist()` endpoint received its required `set_backend_observability_context()` call?
- [ ] Have I committed evidence files to `output/s225/` per the YAML split? (`-f` required because `output/` is gitignored)
- [ ] Has the worktree been removed at closeout?
- [ ] Has the SPRINT_REGISTRY.md row been updated to COMPLETED with PR links?

## Phase Budget Contract (v2 — Phase 4.5 added per audit B-4)

| Phase | Title | Units | Owner | Repo |
|---|---|---|---|---|
| 0 | Boot, BOTH worktrees, canonical preflight, baseline capture | 5 | hrms | hrms + bei-tasks |
| 1 | Validate S224 PR #687 merged + **deployed-SHA verified** (Pattern B + C live) | 8 | hrms | hrms (read-only) |
| 2 | Canonical warehouse duplicate audit (read-only, builds report, **flags intercompany clusters**) | 9 | hrms | hrms (SSM) |
| 3 | Canonical warehouse duplicate consolidation **via Material Transfer** (Sam-gated, mutates) | 11 | hrms | hrms (SSM) |
| 4 | Pattern A FOR UPDATE lock implementation + unit-style probe + **Item.has_batch_no probe** | 9 | hrms | hrms |
| **4.5** | **PR creation → Sam merges → Sam deploys → wait-for-deploy gate (Docker SHA matches merge commit)** | **4** | **hrms** | **hrms (SSM)** |
| 5 | Pattern A concurrency stress test (10 parallel dispatches via SSM, AGAINST DEPLOYED LOCK) | 8 | hrms | hrms (SSM) |
| 6 | Full L3 sweep validating S223 + S224 + S225 cumulative | 5 | hrms | both (sweep) |
| 7 | Closeout: registry update, evidence commit, worktree removal (BOTH worktrees) | 2 | hrms | hrms + bei-tasks |

**Hard limit:** 15 units per phase. **Largest phase: 3 at 11 units.** All within budget.
**Total: 60 units** (under 80-unit ceiling — was 56 in v1).

**Phase ordering note (v2):** strict 0 → 1 → 2 → 3 → 4 → **4.5** → 5 → 6 → 7. Phase 1 gates everything else (S224 must be deployed-LIVE, not just merged). Phase 3 gates 4-7 (canonical state must be clean). **Phase 4.5 gates 5-6** — Sam merges + deploys this sprint's Phase 4 lock change before stress test or full sweep run, otherwise both phases test pre-S225 code (corrupt success per audit B-4).

## Plan Resumption Protocol (multi-session execution)

**Realistic wallclock estimate:** Phase 0 (~10min) + Phase 1 (~15min) + Phase 2 (~15min) + Phase 3 (~30min Sam review + 15min apply) + Phase 4 (~30min) + Phase 5 (~25min) + Phase 6 (~75min sweep + 15min classify) + Phase 7 (~15min) = **~4 hours**. Single-session if budget permits; multi-session safe at the boundaries below.

**Checkpoint protocol (mandatory + COMMIT-AT-PHASE-BOUNDARY):** at the end of each phase the executing agent writes AND COMMITS an entry to `output/s225/RUN_STATUS.json`:

```json
{
  "phase": "<phase id, e.g., 2>",
  "status": "complete | in_progress | blocked",
  "timestamp": "<UTC ISO>",
  "evidence_paths": ["output/s225/verification/...", "..."],
  "next_phase": "<from PHASE_ORDER below>",
  "blockers": [],
  "canonical_postcheck_violations": <int>,
  "branch_head_sha": "<git rev-parse HEAD>"
}
```

> **HARD BLOCKER:** because `output/` is gitignored, RUN_STATUS.json must be committed via `git add -f` at every phase boundary:
>
> ```bash
> git add -f output/s225/RUN_STATUS.json
> git commit -m "chore(S225 checkpoint): phase <X> complete"
> git push origin s225-canonical-warehouse-cleanup-and-pattern-a-safeguard
> ```
>
> Push is mandatory — local-only commits don't survive worktree removal.

**Explicit phase order (v2 — Phase 4.5 added):**
```python
PHASE_ORDER = ["0", "1", "2", "3", "4", "4.5", "5", "6", "7"]
```

**Allowed pause boundaries:**
- After Phase 1 (S224 validated, no in-flight code changes)
- After Phase 2 (audit JSON written, awaiting Sam approval before Phase 3 mutation)
- After Phase 3 (consolidation done; canonical postcheck clean; before Phase 4 backend code change)
- **After Phase 4 — MANDATORY pause for Sam to merge + deploy** (the next phase's stress test runs against the deployed container, so Sam's deploy must complete first)
- After Phase 4.5 (deploy-SHA verified live; before stress test)
- After Phase 5 (FOR UPDATE lock proven safe under concurrency; before full sweep)

**Forbidden pause boundaries:**
- During Phase 3 mutation (the consolidation runs all-or-nothing per duplicate; partial state is risky)
- During Phase 6 sweep (test artifacts orphaned; cleanup is mid-phase)

If a session must pause mid-phase, agent commits work-in-progress with `chore(S225 WIP): <phase> partial — see RUN_STATUS.json`, pushes, records `status: in_progress`. Next session resumes from the same phase.

## Phase 0 — Boot Sequence (5 units, was 4 — added bei-tasks worktree per audit B-12)

> **HARD BLOCKER:** Agent must NOT touch any code or master data until Phase 0 completes successfully.

1. Read this plan fully end to end.
2. Read `output/s223/verification/pattern_a_b_c_root_cause_analysis.md` (S224 root-cause findings).
3. Read `docs/STORE_COMPANY_CANONICAL.md` rules 1, 2, 6 in full.
4. Read `.claude/rules/worktree-isolation.md` for the worktree contract.
5. **Spawn BOTH worktrees** (audit B-12 fix — bei-tasks worktree was previously spawned inline in Phase 1 with `2>/dev/null` error suppression which silently inherited prior session dirty state):
    ```bash
    # hrms worktree
    cd F:/Dropbox/Projects/BEI-ERP && git fetch origin --prune
    git worktree add F:/Dropbox/Projects/BEI-ERP-s225-canonical-warehouse-cleanup-and-pattern-a-safeguard \
      -B s225-canonical-warehouse-cleanup-and-pattern-a-safeguard origin/production
    cd F:/Dropbox/Projects/BEI-ERP-s225-canonical-warehouse-cleanup-and-pattern-a-safeguard
    mkdir -p output/s225/verification output/l3/s225 tmp/s225

    # bei-tasks worktree (Phase 1 + Phase 6 use this for Playwright)
    cd F:/Dropbox/Projects/bei-tasks && git fetch origin --prune
    BT_WT=F:/Dropbox/Projects/bei-tasks-s225-canonical-warehouse-cleanup-and-pattern-a-safeguard
    git worktree add "$BT_WT" -B s225-canonical-warehouse-cleanup-and-pattern-a-safeguard origin/main
    # If worktree already exists, dirty-state check
    DIRTY=$(git -C "$BT_WT" status --short 2>&1 | wc -l)
    if [ "$DIRTY" -gt 0 ]; then
      echo "STOP: bei-tasks worktree has uncommitted files from prior session — surface to Sam"
      exit 1
    fi
    # Junction node_modules from main bei-tasks (avoids redundant npm install)
    cmd //c "if not exist \"$BT_WT\\node_modules\" mklink /J \"$BT_WT\\node_modules\" \"F:\\Dropbox\\Projects\\bei-tasks\\node_modules\""
    cd F:/Dropbox/Projects/BEI-ERP-s225-canonical-warehouse-cleanup-and-pattern-a-safeguard
    ```
6. Run canonical preflight:
    ```bash
    python scripts/verify_canonical_structure.py > output/s225/verification/canonical_preflight.txt 2>&1
    tail -10 output/s225/verification/canonical_preflight.txt
    ```
    Expected: `[RESULT] ALL CANONICAL — no action required`. Any violation → STOP.
7. Capture remote-truth baseline:
    ```bash
    HEAD=$(git rev-parse origin/production)
    NOW=$(date -Is)
    cat > output/s225/verification/baseline.json <<EOF
    {"hrms_origin_production": "$HEAD", "captured_at": "$NOW", "expected_s224_pr": 687}
    EOF
    ```

**MUST_MODIFY:** none in Phase 0 — this is read-only setup.

**MUST_CONTAIN (in evidence):**
- `output/s225/verification/canonical_preflight.txt` exists and contains `Violations: 0`
- `output/s225/verification/baseline.json` exists with valid 40-char SHA

**Phase 0 verification gate:**
```bash
python -c "
import json, pathlib
b = json.load(open('output/s225/verification/baseline.json'))
assert len(b['hrms_origin_production']) == 40, 'baseline missing'
preflight = pathlib.Path('output/s225/verification/canonical_preflight.txt').read_text()
assert 'Violations: 0' in preflight, 'canonical violations exist — STOP'
print('PHASE 0 PASS')
"
```

Mark Phase 0 complete: write + commit + push `output/s225/RUN_STATUS.json` per checkpoint protocol.

## Phase 1 — Validate S224 PR #687 deployed and Pattern B + C fixes work (8 units)

**Goal:** prove S224 backend is live and Pattern B + Pattern C fixes function correctly via direct REST probes + targeted L3 retest.

**HARD BLOCKER (Sam directive 2026-04-26):** if S224 PR #687 is not MERGED at start of Phase 1, STOP. Do not proceed to Phase 2-7. The whole sprint depends on the S224 baseline being live.

**Tasks:**

1. **Verify PR #687 merged AND deployed (audit B-5 fix — PR-merged ≠ deployed):**

    **1a. Check PR state:**
    ```bash
    GH_TOKEN="" gh pr view 687 --repo Bebang-Enterprise-Inc/hrms --json state,mergedAt,mergeCommit > tmp/s225/pr_687_state.json
    cat tmp/s225/pr_687_state.json
    ```
    If `state != "MERGED"` → STOP, surface to Sam, do not proceed.

    **1b. Verify deployed Docker container actually contains S224 code** (NEW per audit B-5):
    Sam's deploy is a separate manual step from PR merge. Probe the live container:
    ```python
    # scripts/s225_check_s224_deploy_sha.py — uses boto3 SSM (template: scripts/s224_query_sentry_api.py)
    # Method 1: read approve_material_request source from container, grep for the v2 idempotency return
    cmd = '''docker exec frappe_backend grep -A2 "current_status == \\"Ordered\\"" /home/frappe/frappe-bench/apps/hrms/hrms/api/warehouse.py | head -5'''
    # Expect to see: return {"success": True, ..., "already_approved": True}
    # If we still see frappe.throw("...already been approved"), S224 is merged but NOT yet deployed.
    ```
    Save → `output/s225/verification/s224_deploy_sha_check.json` with fields: `pr_merge_sha`, `container_code_has_idempotency` (bool), `container_code_has_fuzzy_resolver` (bool).

    If `container_code_has_idempotency == False` OR `container_code_has_fuzzy_resolver == False` → STOP. Tell Sam: "PR #687 merged at <mergedAt> but deployed container does not yet have S224 code. Trigger `/deploy-frappe` and re-run Phase 1 task 1."

2. **Verify backend deployed (REST probe — Pattern B idempotency, audit B-6 fix):**
    Call `approve_material_request` against an MR already at status="Ordered" — pre-S224 returned 417 with "already been approved"; post-S224 should return 200 with `already_approved: true`.

    **CRITICAL audit fix (B-6):** `approve_material_request` validates `approved_items` at line 1219 BEFORE the FOR UPDATE status check at line 1228. The previous probe pseudocode passed empty `approved_items` and would 400 before reaching idempotency. The probe MUST construct `approved_items` from the MR's existing items:
    ```python
    # scripts/s225_validate_s224_pattern_b.py — runs via SSM
    import frappe, json
    frappe.set_user("test.scm@bebang.ph")

    # Find an existing Ordered MR (do NOT create a new one)
    mr_name = frappe.db.get_value("Material Request",
        {"status": "Ordered", "docstatus": 1,
         "material_request_type": ["in", ["Material Transfer", "Material Issue"]]},
        "name", order_by="creation desc")
    if not mr_name:
        # Fallback: create a fresh order, walk approval, get MR — then probe.
        # (Skipped in fallback document — covered by Phase 1 task 4 sweep.)
        raise SystemExit("No existing Ordered MR found; rely on Phase 1 task 4 sweep instead.")

    # B-6 FIX: build approved_items from the MR's actual items so the probe
    # passes the line 1219 validation and reaches the line 1228 idempotency branch.
    items = frappe.get_all("Material Request Item",
        filters={"parent": mr_name},
        fields=["item_code", "qty"])
    approved_items = json.dumps([{"item_code": it["item_code"], "approved_qty": it["qty"]} for it in items])

    # Probe: call approve_material_request via REST as test.scm
    # Expect: status 200, body {"success": true, "already_approved": true}
    from hrms.api.warehouse import approve_material_request
    resp = approve_material_request(mr_name=mr_name, approved_items=approved_items)
    # Result MUST contain already_approved=True per S224 PR #687 fix
    ```
    Save response → `output/s225/verification/s224_pattern_b_validation.json`. Assert `resp.get("already_approved") is True`.

3. **Verify backend deployed (REST probe — Pattern C fuzzy resolver):**
    Call `validate_order_schedule` (or `get_orderable_items`) with a truncated identifier — pre-S224 this threw "Could not find Store: Estancia"; post-S224 should resolve and return data.
    ```python
    # scripts/s225_validate_s224_pattern_c.py — runs via SSM
    # Probe 1: validate_order_schedule(store="Estancia") — should resolve to ORTIGAS ESTANCIA
    # Probe 2: validate_order_schedule(store="ESTANCIA") — case insensitive
    # Probe 3 (negative): validate_order_schedule(store="Bebang Enterprise Inc.") — should still throw (multiple matches → ambiguous)
    ```
    Save → `output/s225/verification/s224_pattern_c_validation.json`. Assert probe 1 + 2 return success; probe 3 throws "Ambiguous".

4. **Targeted L3 retest of S224-fixed stores via Playwright `--grep`:**
    Run a focused 6-store sweep (Pattern B: ROBINSONS ANTIPOLO, ROBINSONS IMUS, AYALA FAIRVIEW TERRACES, AYALA UP TOWN CENTER; Pattern C: NAIA T3, ORTIGAS ESTANCIA — skip ORTIGAS GREENHILLS for now since it's the 1-of-49 allowed skip).

    **Worktree assumption (audit B-12 fix):** the bei-tasks worktree was already spawned in Phase 0 task 5. Do NOT re-spawn it inline here.
    ```bash
    cd F:/Dropbox/Projects/bei-tasks-s225-canonical-warehouse-cleanup-and-pattern-a-safeguard
    npx playwright test tests/e2e/specs/s209-all-stores.spec.ts \
      --grep "ROBINSONS ANTIPOLO|ROBINSONS IMUS|AYALA FAIRVIEW TERRACES|AYALA UP TOWN CENTER|NAIA T3|ORTIGAS ESTANCIA" \
      --reporter=line \
      --max-failures=0 2>&1 | tee tmp/s225/s224_targeted_sweep.log
    ```
    Cleanup any test artifacts via `python scripts/s209_cleanup_sweep.py --ledger output/l3/s225/sweep_ledger.json`.

5. **Outcome decision matrix:**

| Result | Action |
|---|---|
| All 6 stores PASS | S224 fully validated. Proceed to Phase 2. |
| 5/6 PASS, 1 fails for a NEW reason (not Pattern B or C) | New defect surfaced. File as Phase 6 follow-up. Proceed to Phase 2. |
| ≤4/6 PASS | S224 fixes incomplete. STOP. Surface to Sam — choose to revisit S224 or scope down S225. |
| Any test crashes (env issue) | Re-run once. If crash repeats, STOP and ask Sam. |

**MUST_MODIFY:**
- `scripts/s225_validate_s224_pattern_b.py` (NEW)
- `scripts/s225_validate_s224_pattern_c.py` (NEW)

**MUST_CONTAIN:**
- `output/s225/verification/s224_pattern_b_validation.json` with `already_approved: true`
- `output/s225/verification/s224_pattern_c_validation.json` with successful Estancia + ESTANCIA probes
- `tmp/s225/s224_targeted_sweep.log` showing 6/6 (or 5/6 with documented exception) pass

**Phase 1 verification gate:**
```bash
python -c "
import json, pathlib
b = json.load(open('output/s225/verification/s224_pattern_b_validation.json'))
assert b.get('already_approved') is True, 'Pattern B fix not deployed'
c = json.load(open('output/s225/verification/s224_pattern_c_validation.json'))
assert c['probe_estancia']['ok'] is True
assert c['probe_estancia_uppercase']['ok'] is True
log = pathlib.Path('tmp/s225/s224_targeted_sweep.log').read_text()
# Playwright reporter prints 'X passed' at the end
import re
m = re.search(r'(\\d+)\\s+passed', log)
passed = int(m.group(1)) if m else 0
assert passed >= 5, f'Phase 1 sweep: expected ≥5 of 6 passing, got {passed}'
print(f'PHASE 1 PASS — S224 validated, sweep {passed}/6')
"
```

If FAIL → STOP, surface to Sam. Do not proceed.

## Phase 2 — Canonical warehouse duplicate audit (read-only, 9 units)

**Goal:** identify EVERY warehouse duplicate across all 49+ canonical warehouses and the commissary/cold-storage hubs. Build a definitive audit report Sam reviews before authorizing Phase 3 consolidation.

**Tasks:**

1. **Build the audit script** `scripts/s225_audit_warehouse_duplicates.py` (NEW). Uses SSM to run:

    ```python
    # Detection rules — match canonical warehouses against typo-similar duplicates
    import frappe, re, unicodedata
    from collections import defaultdict

    def normalize(s):
        # Lowercase, NFKD-normalize unicode, replace em-dash/en-dash with hyphen,
        # collapse whitespace, strip
        s = unicodedata.normalize("NFKD", str(s or ""))
        s = s.replace("–", "-").replace("—", "-")  # em/en dash to hyphen
        s = re.sub(r"\s+", " ", s).strip().lower()
        return s

    all_wh = frappe.db.sql("""
        SELECT name, warehouse_name, company, disabled, is_group, parent_warehouse,
               (SELECT SUM(actual_qty) FROM `tabBin` b WHERE b.warehouse = w.name) AS total_stock,
               (SELECT COUNT(*) FROM `tabBin` b WHERE b.warehouse = w.name AND b.actual_qty != 0) AS sku_count
        FROM `tabWarehouse` w
    """, as_dict=True)

    # Cluster by normalized name
    clusters = defaultdict(list)
    for w in all_wh:
        clusters[normalize(w["name"])].append(w)

    # Anything with len > 1 is a candidate duplicate
    duplicates = {k: v for k, v in clusters.items() if len(v) > 1}
    ```

    For each cluster, classify:
    - **canonical_winner:** the one matching `<STORE LABEL> - <LEGAL ENTITY>` exactly (no em-dash, no extra whitespace, hyphens only)
    - **losers:** the remaining ones (em-dash variants, extra-space variants, etc.)
    - For each loser, list:
      - SKU count (`tabBin` rows with non-zero `actual_qty`)
      - Total stock (sum of `actual_qty`)
      - All SKU codes + qty in that warehouse
      - Whether the loser has any in-flight transactions (open MRs, draft SEs, draft SIs referencing it)
    - **HARD CHECK per audit B-13: `cluster.intercompany = (winner.company != loser.company)`**
      - If `intercompany == True` → flag cluster as `MANUAL_REVIEW_REQUIRED — INTERCOMPANY` and EXCLUDE from "APPROVED ALL" eligibility.
      - Reason: stock movement between Companies isn't a simple Material Transfer — it's an intercompany transaction triggering NIRC §34(E) transfer-pricing rules. Needs separate inter-company billing flow, not in S225 scope.
      - Sam can still authorize per-cluster approval for intercompany, but the audit script forces explicit acknowledgment via `S225 Phase 3 APPROVED INTERCOMPANY: <cluster_id>` token (different from generic APPROVED ALL).

    Output:
    - `output/s225/verification/duplicate_warehouse_audit.json` — full machine-readable
    - `output/s225/verification/duplicate_warehouse_audit.md` — human-readable summary table for Sam review

2. **Detection rule precision:** the audit MUST also check warehouse_name field collisions (two warehouses with same `warehouse_name` but different docnames — also a duplicate signal). And test for case-only differences (`Pinnacle Cold Storage` vs `PINNACLE COLD STORAGE`).

3. **Commissary + cold-storage scope:** the canonical 49 stores are `Warehouse.company in (per-store Companies)`, but commissary + cold-storage hubs (PINNACLE, 3MD, SHAW BLVD, BKI HQ) are separate. The audit covers ALL warehouses (`disabled=0`), not just store warehouses, because Sentry showed the failing duplicate is on a cold-storage hub.

4. **Surface to Sam:** the audit MD file must include this top section:
    ```markdown
    # S225 Phase 2 — Warehouse Duplicate Audit Report

    **For Sam to review BEFORE authorizing Phase 3 consolidation.**

    Total warehouses scanned: <N>
    Duplicate clusters found: <K>
    Stranded SKU count across all duplicates: <M>
    Stranded total stock: <T> units

    ## Per-cluster decision required

    For each cluster below, Sam confirms:
    - The "Canonical Winner" choice
    - Whether to disable the loser(s) AS-IS or rename them first
    - Whether any loser has in-flight work that should pause consolidation

    [Audit table follows]
    ```

5. **Auto-detection limitations to flag:** the script should output a "Manual Review Needed" list for:
    - Clusters where no member matches the strict canonical pattern (Sam picks)
    - Clusters where the proposed loser has more stock than the proposed winner (counterintuitive — Sam decides)
    - Clusters where any loser is `is_group=1` (groups have child warehouses; can't simply disable)

6. **Post Sentry confirmation tag:** the script also queries Sentry (via `SENTRY_API_TOKEN` from Doppler — bypass MCP) for any error in past 14 days mentioning each loser's full name. If errors exist, include the count + sample messages in the audit report so Sam knows which duplicates are actively causing user pain.

**MUST_MODIFY:**
- `scripts/s225_audit_warehouse_duplicates.py` (NEW)

**MUST_CONTAIN:**
- `output/s225/verification/duplicate_warehouse_audit.json` with at least 1 cluster (the known 3MD em-dash one)
- `output/s225/verification/duplicate_warehouse_audit.md` with per-cluster decision table

**MUST_NOT (forbidden):**
- ANY mutation in this phase. Audit is strictly read-only.
- Skipping the Sentry cross-check (it's how we prioritize which duplicates Sam fixes first).

**Phase 2 verification gate:**
```bash
python -c "
import json, pathlib
audit = json.load(open('output/s225/verification/duplicate_warehouse_audit.json'))
assert 'clusters' in audit
assert any(len(c['members']) > 1 for c in audit['clusters']), 'no duplicates found — should at least find 3MD em-dash'
md = pathlib.Path('output/s225/verification/duplicate_warehouse_audit.md').read_text()
assert 'Per-cluster decision required' in md
assert 'Sam' in md, 'audit must surface a Sam decision'
print('PHASE 2 PASS — audit complete, awaiting Sam approval for Phase 3')
"
```

> **HARD BLOCKER (audit B-11 fix):** at the end of Phase 2, agent creates a PR (`gh pr create`) with the audit MD content as the PR body, then writes the PR# to `output/s225/verification/sam_consolidation_pr.txt`. Phase 3 cannot start until Sam responds with explicit approval **on that PR**.
>
> **Approval mechanism (unambiguous per audit B-11):**
> - Sam writes a PR comment containing one of these exact tokens:
>   - `S225 Phase 3 APPROVED ALL` — apply all clusters in the audit (excluding INTERCOMPANY-flagged ones)
>   - `S225 Phase 3 APPROVED: <cluster_id1>, <cluster_id2>` — apply only listed clusters
>   - `S225 Phase 3 APPROVED INTERCOMPANY: <cluster_id>` — explicit intercompany authorization
>   - `S225 Phase 3 SKIP: <cluster_id>` — skip listed clusters (with rationale)
> - Agent runs `scripts/s225_check_sam_approval.py` (NEW per audit B-11) which:
>   1. Reads PR# from `sam_consolidation_pr.txt`
>   2. Polls `gh pr view <pr> --comments` for token regex
>   3. On detection: writes the canonical approval to `output/s225/verification/sam_consolidation_approval.md`
>   4. Phase 3 reads ONLY this file as authority (single source of truth)
> - Without the file, Phase 3 STOPs.
>
> **`cluster_id` format (audit CS-3 fix):** UUID-like slug derived from canonical name. Example cluster IDs:
> - `cluster-3md-logistics-camangyanan-bki` (em-dash duplicate)
> - `cluster-pinnacle-cold-storage-solutions-bki`
> Format: `cluster-<canonical-warehouse-name-lowercased-hyphenated>`. Audit JSON includes the full mapping.

## Phase 3 — Canonical warehouse duplicate consolidation (Sam-gated, 11 units)

**Goal:** disable each loser, migrate its stock to the canonical winner via Stock Reconciliation, verify no SKU lost.

**HARD BLOCKER:** Phase 3 only runs after Sam confirms the Phase 2 audit. The script reads `output/s225/verification/sam_consolidation_approval.md` for the approval token; if missing or token doesn't match expected format → STOP.

**Tasks:**

1. **Build the consolidation script** `scripts/canonical/retire_warehouse_duplicate.py` (NEW). Per canonical rule 6, this lives under `scripts/canonical/`. Default behavior is dry-run; `--commit` flag required for actual mutations.

    **AUDIT B-2 + B-3 + W-3 FIX: use Material Transfer (Stock Entry), NOT Stock Reconciliation.**
    The original v1 plan used Stock Reconciliation but: (a) `SR.add_batch()` doesn't exist in ERPNext v15 — that API was hallucinated, (b) SR posts the delta through P&L "Stock Adjustment Expense" leaving no linking transfer doc for BIR audit, (c) BEI's existing inter-warehouse stock movement pattern uses `Stock Entry` with `stock_entry_type="Material Transfer"` (see `hrms/api/warehouse.py:1537`).

    Material Transfer is the correct doctype: single document, asset-to-asset GL movement (no P&L), generates a matched SLE pair (s-out at duplicate, s-in at canonical), preserves batch tracking via the existing v15 `Serial and Batch Bundle` flow, full BIR audit trail via the linked Stock Entry doc.

    ```python
    # scripts/canonical/retire_warehouse_duplicate.py --duplicate <NAME> --canonical <NAME> [--commit]
    # 1. Validate: both warehouses exist; canonical is not disabled; canonical is not is_group;
    #    canonical.company == duplicate.company (B-13 hard-stop already enforced in Phase 2 audit)
    # 2. Snapshot before: warehouse doc + all Bin rows for both
    # 3. Build ONE Material Transfer Stock Entry covering all items:
    #    - se = frappe.new_doc("Stock Entry")
    #    - se.stock_entry_type = "Material Transfer"
    #    - se.company = duplicate.company  # same as canonical.company per B-13 check
    #    - se.posting_date = frappe.utils.today()
    #    - se.from_warehouse = duplicate (the loser)
    #    - se.to_warehouse = canonical (the winner)
    #    - se.purpose = "Material Transfer"
    #    - se.remarks = (
    #        f"S225 canonical cleanup: consolidate {duplicate} → {canonical}. "
    #        f"Sam authorization: <token>. Per docs/STORE_COMPANY_CANONICAL.md rules 1+2."
    #      )
    #    - For each item with actual_qty > 0 in duplicate's Bin:
    #        row = {
    #          "item_code": ..., "qty": <actual_qty>, "uom": ...,
    #          "s_warehouse": duplicate, "t_warehouse": canonical,
    #        }
    #        if Item.has_batch_no:
    #          # v15 SABB pattern: build batch-aware allocation
    #          # The bundle is auto-resolved by ERPNext from from_warehouse stock at submit time
    #          # No manual SR.add_batch() needed — Material Transfer respects batch tracking natively.
    #          pass  # ERPNext handles batch deduction from from_warehouse via standard SE submit
    #        se.append("items", row)
    # 4. se.insert(ignore_permissions=True); se.submit()  # generates matched SLE pair
    # 5. After SE submits, set Warehouse.disabled = 1 on the duplicate
    # 6. Snapshot after; verify per-item:
    #    - duplicate.Bin.actual_qty[item] == 0 for every migrated item
    #    - canonical.Bin.actual_qty[item] gained exactly the duplicate's pre-consolidation qty (within 0.001 tolerance)
    #    - System-wide stock conservation (sum_after == sum_before)
    # 7. Write per-cluster ledger to output/s225/verification/dup_<slug>_consolidation.json:
    #    {"se_name": "<docname>", "items_migrated": [...], "qty_per_item": {...}, "duplicate_disabled": True}
    ```

    **Per-item batch-tracking probe (audit W-1 alignment):** before building the SE, the script queries `frappe.db.get_value("Item", item_code, "has_batch_no")` for every item in the duplicate's Bin. The script does NOT need to call `SR.add_batch()` (hallucinated) because Material Transfer's normal `se.submit()` path respects batch tracking natively via the source warehouse's existing batch allocations.

2. **Pre-touch backup:** before any mutation, snapshot:
    ```python
    {
      "duplicate": <warehouse>.as_dict(),
      "canonical": <warehouse>.as_dict(),
      "duplicate_bins": [...],
      "canonical_bins_before": [...],
      "open_transactions_referencing_duplicate": <SQL probe for MRs/SEs/SIs>
    }
    ```
    → `output/s225/verification/dup_<slug>_before.json`

3. **Dry run first:** for every cluster in the audit, run:
    ```bash
    python scripts/canonical/retire_warehouse_duplicate.py \
      --duplicate "3MD LOGISTICS – CAMANGYANAN - BKI" \
      --canonical "3MD LOGISTICS - CAMANGYANAN - BKI"
    ```
    Without `--commit` — outputs the planned Stock Reconciliations + before-after deltas. Save to `output/s225/verification/dup_consolidation_dry_run.json`. Sam reviews this file.

4. **HARD BLOCKER for actual apply:** Sam's approval token (from Phase 2) must include either:
    - `S225 Phase 3 APPROVED ALL` — apply to all clusters
    - `S225 Phase 3 APPROVED: <cluster_id1>, <cluster_id2>` — apply only the listed clusters
    - `S225 Phase 3 SKIP: <cluster_id>` — skip specific clusters (with rationale)

    The script reads the approval file and applies only what's authorized.

5. **Apply consolidation:**
    ```bash
    # For each approved cluster:
    python scripts/canonical/retire_warehouse_duplicate.py \
      --duplicate "<name>" --canonical "<name>" --commit
    ```
    Save per-cluster output to `output/s225/verification/dup_<slug>_after.json`.

6. **Aggregate ledger:** combine all per-cluster outputs into `output/s225/verification/dup_consolidation_applied.json`:
    ```json
    {
      "applied_clusters": [...],
      "skipped_clusters_with_reason": [...],
      "total_stock_units_migrated": N,
      "total_skus_migrated": M,
      "stock_reconciliation_docnames": [...],
      "disabled_warehouse_docnames": [...]
    }
    ```

7. **Run canonical postcheck:**
    ```bash
    python scripts/verify_canonical_structure.py > output/s225/verification/canonical_postcheck_phase3.txt 2>&1
    ```
    Expected: `[RESULT] ALL CANONICAL — no action required`. The disabled warehouses must NOT show as new violations.

8. **Stock conservation check:** sum of stock across all (canonical + non-disabled) warehouses for any item must equal sum BEFORE consolidation (within float tolerance). The script outputs a conservation table.

**MUST_MODIFY:**
- `scripts/canonical/retire_warehouse_duplicate.py` (NEW)

**MUST_CONTAIN:**
- `output/s225/verification/dup_consolidation_dry_run.json` (per-cluster planned deltas)
- `output/s225/verification/dup_consolidation_applied.json` (per-cluster applied state)
- `output/s225/verification/canonical_postcheck_phase3.txt` with `Violations: 0`
- Stock Reconciliation docnames in the ledger (one per duplicate × per item)
- All disabled-warehouse docnames in the ledger (matches Phase 2 audit's losers, minus skips)

**MUST_NOT (forbidden):**
- Direct UPDATE on `tabBin.actual_qty` (must use Stock Reconciliation per canonical rule 6)
- `frappe.delete_doc` on any Warehouse (rule 2 — disable, never delete)
- Skipping the dry-run (forbidden by Sam directive)
- Applying clusters Sam didn't explicitly approve

**Phase 3 verification gate (audit B-9 fix — TWO-SIDED stock conservation):**
```bash
python -c "
import json, pathlib
applied = json.load(open('output/s225/verification/dup_consolidation_applied.json'))
assert applied.get('applied_clusters'), 'no clusters applied'
post = pathlib.Path('output/s225/verification/canonical_postcheck_phase3.txt').read_text()
assert 'Violations: 0' in post, 'canonical postcheck failed'

# Two-sided per-item stock conservation (audit B-9):
# Total system conservation alone could PASS while leaving stranded units on the disabled warehouse.
# We require BOTH sides:
#   (a) duplicate's Bin.actual_qty[item] == 0 after consolidation (loser fully drained)
#   (b) canonical.gain_per_item == duplicate.pre_consolidation_qty (per item, within tolerance)
#   (c) system-wide total_after == total_before (sanity check)
TOLERANCE = 0.001
for cluster in applied['applied_clusters']:
    for item_record in cluster.get('per_item_results', []):
        # (a) duplicate fully drained
        assert item_record['duplicate_after_qty'] == 0, (
            f'cluster {cluster[\"cluster_id\"]} item {item_record[\"item_code\"]}: '
            f'duplicate Bin still has {item_record[\"duplicate_after_qty\"]} units — STRANDED')
        # (b) canonical gained exactly the right amount
        gain = item_record['canonical_after_qty'] - item_record['canonical_before_qty']
        expected = item_record['duplicate_before_qty']
        assert abs(gain - expected) < TOLERANCE, (
            f'cluster {cluster[\"cluster_id\"]} item {item_record[\"item_code\"]}: '
            f'canonical gain={gain}, expected={expected} — MIGRATION INCOMPLETE')

# (c) system-wide conservation as final sanity
for entry in applied.get('system_wide_conservation', []):
    delta = entry['after_total'] - entry['before_total']
    assert abs(delta) < 0.01, f'system stock not conserved for {entry[\"item\"]}: delta={delta}'

print(f'PHASE 3 PASS — {len(applied[\"applied_clusters\"])} clusters consolidated, all per-item migrations verified two-sided, system stock conserved')
"
```

## Phase 4 — Pattern A FOR UPDATE lock implementation (9 units)

**Goal:** add row-level lock around the batch availability check in `create_stock_transfer` so concurrent dispatches serialize. Preserves existing Sentry context.

**Tasks:**

0. **Pre-implementation: probe Item.has_batch_no for FG004 and other Pattern A items (audit W-1):**
   ```python
   # scripts/s225_probe_batch_tracking.py — runs via SSM
   # The Bin-only FOR UPDATE lock is sufficient for non-batch items because Bin's actual_qty is the
   # serialized authority. For batch-tracked items (has_batch_no=1), batch allocation reads from
   # tabBatch which the Bin lock does NOT cover — concurrent dispatches could pass the Bin check
   # but race on the SABB allocation in se.submit().
   #
   # Probe checks:
   #   - FG004 (canonical Pattern A failure item)
   #   - All items present in BACKFILL-20260421-FG004-* batches
   #   - All items in the duplicate warehouses' Bin (Phase 2 audit list)
   batch_tracked = frappe.db.sql("""
       SELECT name, item_name, has_batch_no, has_serial_no
       FROM `tabItem`
       WHERE name = 'FG004'
          OR name IN (SELECT DISTINCT item_code FROM `tabStock Ledger Entry`
                      WHERE batch_no LIKE 'BACKFILL%FG004%')
   """, as_dict=True)
   # Save → output/s225/verification/batch_tracking_probe.json
   ```

   **If ANY relevant item has `has_batch_no=1`:** Phase 4 task 2's lock MUST cover both `tabBin` AND `tabBatch` rows. Otherwise the Bin-only lock is sufficient.

1. **Read `hrms/api/warehouse.py:create_stock_transfer` in full** (lines 1431-1714 pre-S224). Identify the points where bin/batch read precedes write:
    - `_resolve_stock_entry_item_valuation(item_code, source_warehouse)` — reads valuation
    - `mr.items` iteration that builds the SE row — implicit read of `Bin.actual_qty` via `frappe.new_doc("Stock Entry").submit()` validation
    - The actual stock decrement happens inside `se.submit()` via ERPNext's stock ledger insert

2. **Add explicit `SELECT ... FOR UPDATE` row lock** before any item row is appended to the SE. The lock scope: every `(item, source_warehouse)` tuple the dispatch will touch, **plus `tabBatch` rows for batch-tracked items** per the W-1 audit fix (the Phase 4 task 0 probe determines which items need this).

    ```python
    # After se.from_warehouse is set, before items append:
    # S225: serialize concurrent batch decrements per item+warehouse pair.
    # Sentry confirmed Pattern A is a race condition where parallel
    # create_stock_transfer calls read Bin.actual_qty, both decide there's stock,
    # and both submit — pushing the batch briefly negative.
    item_codes = sorted({i.get("item_code") for i in normalized_items if i.get("item_code")})
    if item_codes:
        # FOR UPDATE locks the Bin rows for the duration of the transaction.
        # Acquired before SE.insert/submit, released on COMMIT/ROLLBACK.
        # Sorted item_codes ensure deterministic lock acquisition order across concurrent
        # transactions (prevents deadlocks where T1 locks ItemA→ItemB and T2 locks ItemB→ItemA).
        frappe.db.sql(
            """SELECT name FROM `tabBin`
               WHERE warehouse = %s AND item_code IN %s
               FOR UPDATE""",
            (source_warehouse, tuple(item_codes)),
        )

        # AUDIT W-1 FIX: for batch-tracked items, also lock the Batch rows.
        # The Bin lock alone doesn't cover the Serial and Batch Bundle (SABB) allocation
        # path that runs inside se.submit(). Two parallel dispatches could pass the Bin
        # check (because Bin lock works) but still race on batch-level allocation.
        batch_tracked_items = [
            ic for ic in item_codes
            if frappe.db.get_value("Item", ic, "has_batch_no") == 1
        ]
        if batch_tracked_items:
            # Lock all batches that have non-zero stock at this warehouse for these items.
            # The lock is held until COMMIT, serializing batch allocation across concurrent
            # create_stock_transfer calls.
            frappe.db.sql(
                """SELECT b.name FROM `tabBatch` b
                   JOIN `tabStock Ledger Entry` sle ON sle.batch_no = b.name
                   WHERE sle.warehouse = %s
                     AND sle.item_code IN %s
                     AND sle.is_cancelled = 0
                   GROUP BY b.name
                   FOR UPDATE""",
                (source_warehouse, tuple(batch_tracked_items)),
            )
    ```

3. **Preserve Sentry context.** The existing `set_backend_observability_context(module="warehouse", action="create_stock_transfer", ...)` call at line 1454 stays. Add an extra breadcrumb if the lock acquisition triggers a notable wait:
    ```python
    # Optional: log lock-wait duration if it exceeds threshold (>2s) to surface
    # contention in Sentry breadcrumbs.
    import time as _time
    _t0 = _time.time()
    frappe.db.sql(... FOR UPDATE ...)
    _wait_ms = int((_time.time() - _t0) * 1000)
    if _wait_ms > 2000:
        frappe.log_error(
            f"S225 lock wait {_wait_ms}ms for {source_warehouse}/{item_codes}",
            "S225 Lock Contention",
        )
    ```
    `frappe.log_error` feeds Sentry via the BEI monkey-patch (DM-7).

4. **Test locally with a single-thread probe first.** Build `scripts/s225_pattern_a_lock_smoke.py`:
    - Call `create_stock_transfer` against an existing approved MR with the lock change in place
    - Verify normal dispatch still succeeds
    - Verify Bin.actual_qty decremented correctly
    - Verify no SE in draft state left over (failed savepoint)
    - Cleanup: cancel the SE created by the probe

5. **Verify the existing test suite still passes.** Run the relevant Frappe tests for warehouse module:
    ```bash
    cd F:/Dropbox/Projects/BEI-ERP-s225-canonical-warehouse-cleanup-and-pattern-a-safeguard
    # Frappe tests run via SSM bench command
    bash scripts/run_frappe_tests.sh hrms.tests.test_warehouse_module 2>&1 | tee tmp/s225/frappe_tests.log
    # If no test runner script exists, add equivalent SSM call
    ```
    All pre-existing tests must pass.

**MUST_MODIFY:**
- `hrms/api/warehouse.py` — only `create_stock_transfer` function; signature unchanged

**MUST_CONTAIN:**
- `git diff --name-only origin/production` returns exactly `hrms/api/warehouse.py` (plus the new scripts under `scripts/`)
- The diff in `create_stock_transfer` contains `FOR UPDATE`
- The existing `set_backend_observability_context(module="warehouse", action="create_stock_transfer"` call is unchanged
- `output/s225/verification/pattern_a_lock_test.json` shows single-thread probe success

**MUST_NOT (forbidden):**
- Removing or changing the existing Sentry context (per S224 lesson)
- Changing the function signature
- Adding new fallback paths to `resolve_warehouse_company` or other resolvers
- Any change outside `create_stock_transfer`

**Phase 4 verification gate:**
```bash
python -c "
import subprocess, pathlib
diff = subprocess.check_output(['git', 'diff', '--name-only', 'origin/production', '--', 'hrms/'], text=True).strip()
assert diff == 'hrms/api/warehouse.py', f'expected only warehouse.py, got: {diff}'
content = pathlib.Path('hrms/api/warehouse.py').read_text()
assert 'FOR UPDATE' in content, 'FOR UPDATE lock missing'
assert 'set_backend_observability_context(' in content
# Specifically the create_stock_transfer block has both
import re
fn_match = re.search(r'def create_stock_transfer\\(.*?\\):.*?(?=\\ndef |\\Z)', content, re.DOTALL)
assert fn_match, 'create_stock_transfer missing'
fn = fn_match.group(0)
assert 'FOR UPDATE' in fn, 'FOR UPDATE not in create_stock_transfer'
assert 'module=\"warehouse\"' in fn, 'Sentry context lost'
import json
probe = json.load(open('output/s225/verification/pattern_a_lock_test.json'))
assert probe['single_thread_dispatch'] == 'success'
print('PHASE 4 PASS — FOR UPDATE lock added, Sentry preserved')
"
```

## Phase 4.5 — Wait-for-deploy gate (4 units, NEW per audit B-4)

**Goal:** ensure Phase 5 stress test and Phase 6 full sweep run AGAINST the deployed Phase 4 lock change, not against pre-S225 code.

> **HARD BLOCKER (audit B-4 fix):** 4 audit agents independently flagged that the v1 plan's Phase 5/6 ran via SSM against the production Docker container, but the FOR UPDATE code lived only in the worktree branch — not yet deployed. Stress test against pre-lock code = vacuous "PASS" (corrupt success identical to S218/S219 plateau pattern). Phase 4.5 closes this gap by gating the next phases on actual deploy.

**Tasks:**

1. **Push Phase 4 changes + create the S225 PR for review:**
    ```bash
    cd F:/Dropbox/Projects/BEI-ERP-s225-canonical-warehouse-cleanup-and-pattern-a-safeguard
    git push -u origin s225-canonical-warehouse-cleanup-and-pattern-a-safeguard
    GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms \
      --base production --head s225-canonical-warehouse-cleanup-and-pattern-a-safeguard \
      --title "fix(S225): canonical warehouse cleanup + Pattern A FOR UPDATE lock + S224 validation" \
      --body "$(cat output/s225/SUMMARY.md 2>/dev/null || echo 'See plan body')" \
      | tee tmp/s225/s225_pr_url.txt
    ```
    Note: PR description will be replaced at Phase 7 closeout with the final SUMMARY.md.

2. **HARD STOP — wait for Sam to merge + deploy.** Agent posts a comment on the PR:
   > "S225 Phase 4 ready for review. After merge, please trigger `/deploy-frappe`. The next phase (concurrency stress test) cannot run until the deployed Docker container has the Phase 4 FOR UPDATE lock. Phase 4.5 deploy-SHA gate will resume automatically once `container_code_has_for_update == True`."

3. **Deploy-SHA verification gate** — agent polls every 5 minutes (max 4 hours) and exits when the deployed container has the new code:
    ```python
    # scripts/s225_wait_for_deploy.py — uses boto3 SSM (template: scripts/s224_query_sentry_api.py)
    import time, json, subprocess

    MAX_WAIT_MIN = 240  # 4 hours
    deadline = time.time() + MAX_WAIT_MIN * 60

    while time.time() < deadline:
        # Probe the container for the FOR UPDATE string in create_stock_transfer
        ssm_cmd = '''docker exec frappe_backend grep -A30 "def create_stock_transfer" \
                     /home/frappe/frappe-bench/apps/hrms/hrms/api/warehouse.py | grep "FOR UPDATE"'''
        result = run_ssm(ssm_cmd)  # uses scripts/s224_query_sentry_api.py boto3 template
        if "FOR UPDATE" in result.get("stdout", ""):
            # Capture container code git SHA for evidence
            sha_cmd = "docker exec frappe_backend git -C /home/frappe/frappe-bench/apps/hrms rev-parse HEAD"
            sha = run_ssm(sha_cmd).get("stdout", "").strip()
            evidence = {
                "deploy_verified_at": frappe.utils.now(),
                "container_code_sha": sha,
                "for_update_present": True,
            }
            with open("output/s225/verification/s224_deploy_sha_check.json", "w") as f:
                json.dump(evidence, f, indent=2)
            print("Deploy verified. Container running S225 lock code.")
            return 0
        print(f"Deploy not yet visible. Waiting 5 min... ({int((deadline - time.time())/60)} min budget remaining)")
        time.sleep(300)

    raise SystemExit("STOP: Sam has not yet deployed Phase 4 within 4 hours. Surface to Sam manually.")
    ```

4. **Save evidence** to `output/s225/verification/s224_deploy_sha_check.json` with fields: `deploy_verified_at`, `container_code_sha`, `for_update_present` (bool).

**MUST_CONTAIN:**
- `output/s225/verification/s224_deploy_sha_check.json` with `for_update_present: true`
- The S225 PR exists on GitHub (URL captured in `tmp/s225/s225_pr_url.txt`)

**Phase 4.5 verification gate:**
```bash
python -c "
import json, pathlib
sha_check = json.load(open('output/s225/verification/s224_deploy_sha_check.json'))
assert sha_check.get('for_update_present') is True, 'Phase 4 lock not in deployed container'
assert len(sha_check.get('container_code_sha', '')) == 40, 'container SHA missing'
print(f'PHASE 4.5 PASS — deployed container running S225 code at SHA {sha_check[\"container_code_sha\"][:8]}')
"
```

**Forbidden behaviors in Phase 4.5:**
- Skipping the deploy-SHA check and proceeding to Phase 5 (this is the entire point of Phase 4.5)
- Polling more frequently than 5min intervals (rate-limit-safe boundary)
- Treating "PR merged" as sufficient evidence of deploy (audit B-5 fix — merge ≠ deployed)

## Phase 5 — Pattern A concurrency stress test (8 units)

**Goal:** confirm the FOR UPDATE lock makes parallel dispatches safe — no negative-stock errors, no deadlocks.

**Tasks:**

1. **Build the stress harness** `scripts/s225_pattern_a_concurrent_stress.py`. Via SSM, runs 10 parallel `create_stock_transfer` calls against the same source warehouse + same item:

    ```python
    # 10 parallel threads, each:
    #   1. Submit a fresh order for a different store (isolated approval queues)
    #   2. Walk through approve_order(stage1) + approve_order(stage2) to create MR
    #   3. Call create_stock_transfer in parallel
    # Capture: which calls succeeded, which got a "negative stock" error,
    # whether any deadlock fired (MySQL error 1213)
    # Cleanup: cancel all SEs + MRs + Orders created
    ```

2. **Pass criteria:**
    - 10/10 calls return 200 (or fail for a non-stock reason like "no items left in MR after parallel allocation")
    - 0/10 calls produce "negative stock" or "Stock decreased between resolution and dispatch"
    - 0/10 calls produce MySQL error 1213 (deadlock found)
    - Each call's response time stays under 30s (lock contention bound)

3. **Failure handling:**
    - If 1+ negative-stock errors fire → lock is too narrow. Widen the FOR UPDATE scope or lock the Batch row instead of just the Bin row. Iterate.
    - If 1+ deadlocks → lock acquisition order is non-deterministic. Sort `item_codes` before locking.
    - Either failure → fix and re-run. Max 3 iterations; if still failing, STOP and surface to Sam.

4. **Save results:**
    - `output/s225/verification/pattern_a_concurrency_results.json` — per-call status, response time, error
    - `output/s225/verification/pattern_a_concurrency_summary.md` — pass/fail summary for human review

**MUST_MODIFY:**
- `scripts/s225_pattern_a_concurrent_stress.py` (NEW)

**MUST_CONTAIN:**
- `output/s225/verification/pattern_a_concurrency_results.json` showing 0 negative-stock errors, 0 deadlocks
- `output/s225/verification/pattern_a_concurrency_summary.md` with PASS verdict

**Phase 5 verification gate:**
```bash
python -c "
import json
r = json.load(open('output/s225/verification/pattern_a_concurrency_results.json'))
neg_stock = sum(1 for c in r['calls'] if 'negative stock' in (c.get('error') or '').lower())
deadlocks = sum(1 for c in r['calls'] if '1213' in (c.get('error') or ''))
assert neg_stock == 0, f'{neg_stock} negative-stock errors'
assert deadlocks == 0, f'{deadlocks} deadlocks'
success = sum(1 for c in r['calls'] if c['ok'])
assert success >= 8, f'expected ≥8/10 success, got {success}'
print(f'PHASE 5 PASS — {success}/10 success, 0 negative-stock, 0 deadlocks')
"
```

## Phase 6 — Full L3 sweep validating S223 + S224 + S225 cumulative (5 units)

**Goal:** confirm the cumulative effect — 49-store sweep should now PASS at the projected ~36-43/49 (or higher with the canonical cleanup adding more headroom).

**Tasks:**

1. **Pre-sweep canonical preflight:** must show 0 violations.

2. **Reset L3 evidence:**
    ```bash
    rm -f output/l3/s225/sweep_full_run.log output/l3/s225/sweep.pid output/l3/s225/monitor_decisions.log
    echo "[]" > output/l3/s225/sweep_ledger.json
    ```

3. **Capture sweep window UTC:**
    ```bash
    SWEEP_START=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    echo "$SWEEP_START" > output/s225/verification/sweep_start.txt
    ```

4. **Launch monitored sweep with same harness as S223 Phase 7B:**
    ```bash
    export FRAPPE_API_KEY=$(C:/Users/Sam/bin/doppler.exe secrets get FRAPPE_API_KEY --plain --project bei-erp --config dev)
    export FRAPPE_API_SECRET=$(C:/Users/Sam/bin/doppler.exe secrets get FRAPPE_API_SECRET --plain --project bei-erp --config dev)
    export BEI_ERP_ROOT="F:/Dropbox/Projects/BEI-ERP-s225-canonical-warehouse-cleanup-and-pattern-a-safeguard"
    export S209_EVIDENCE_ROOT="$BEI_ERP_ROOT/output/l3/s225"
    export EVIDENCE_ROOT="$BEI_ERP_ROOT/output/l3/s225"

    # Set higher kill thresholds — we EXPECT some Pattern A failures still since
    # the lock helps under concurrency but doesn't eliminate stock-out scenarios.
    python scripts/s212_launch_sweep.py \
      --spec tests/e2e/specs/s209-all-stores.spec.ts \
      --log output/l3/s225/sweep_full_run.log \
      --pid-file output/l3/s225/sweep.pid \
      --ledger output/l3/s225/sweep_ledger.json \
      --decision-log output/l3/s225/monitor_decisions.log \
      --kill-same-fingerprint 8 \
      --kill-pass-rate-below 0.50 \
      --kill-pass-rate-after-n 30 \
      --bei-tasks F:/Dropbox/Projects/bei-tasks-s225-canonical-warehouse-cleanup-and-pattern-a-safeguard
    ```
    Wallclock: ~75 min.

5. **Capture end UTC + cleanup:**
    ```bash
    SWEEP_END=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    echo "$SWEEP_END" > output/s225/verification/sweep_end.txt
    python scripts/s209_cleanup_sweep.py --ledger output/l3/s225/sweep_ledger.json
    ```

6. **Outcome decision matrix:**

| Result | Action |
|---|---|
| **≥48/49 PASS** | Sweep certifies all real-user paths. Mark sprint COMPLETED. |
| **43-47/49 PASS** | Major progress vs S223 16/49. Document remaining failures as Phase 6 follow-up Sentry issues. Sprint COMPLETED. |
| **36-42/49 PASS** | S224 fixes worked but Pattern A still failing some stores. Document; sprint COMPLETED with note that Pattern A FOR UPDATE addresses concurrency only — stock-out scenarios still need data fixes (separate sprint). |
| **<36/49 PASS** | Regression. STOP. Diff against S223's 16/49 — which stores newly failed? May indicate FOR UPDATE introduced a hot-path slowdown or canonical cleanup created an unintended issue. Surface to Sam. |

7. **Write summary** (audit B-8 fix — single canonical sweep log path is `output/l3/s225/sweep_full_run.log`):
    Write `output/l3/s225/SWEEP_VERIFICATION_SUMMARY.md` with:
    - Pass count vs S223 baseline (16/49) and projected (36-43/49)
    - Per-store outcome
    - Remaining failure patterns (if any)
    - Trajectory comparison (S209 → S221 → S222 → S223 → S225)
    - **Audit W-B fix: failure-cause classification** for each failed store, one of:
      - `RACE_CONDITION` (Pattern A symptom: dispatch modal stuck, batch negative-stock, "stock decreased" S163 fire — even after Phase 4 lock should reduce these to near-zero)
      - `STOCK_OUT` (insufficient stock at source warehouse — not a code bug; data fix in S226)
      - `RESIDUAL_PATTERN_B` or `RESIDUAL_PATTERN_C` (S224 fixes incomplete for that store)
      - `NEW_PATTERN` (failure cause not seen in S221-S223; investigate as separate finding)

**MUST_CONTAIN:**
- `output/l3/s225/sweep_full_run.log` (Playwright reporter output — single canonical path)
- `output/l3/s225/sweep_ledger.json` reset to `[]` after cleanup
- `output/l3/s225/monitor_decisions.log` (kill-monitor history)
- `output/l3/s225/SWEEP_VERIFICATION_SUMMARY.md` with verdict + per-store classification

**Phase 6 verification gate (audit B-8 fix — consistent paths):**
```bash
python -c "
import json, pathlib, re
ledger = json.load(open('output/l3/s225/sweep_ledger.json'))
assert ledger == [], 'sweep ledger not reset'
log = pathlib.Path('output/l3/s225/sweep_full_run.log').read_text()
m = re.search(r'(\\d+)\\s+passed', log)
passed = int(m.group(1)) if m else 0
assert passed >= 36, f'sweep regressed below S223 baseline: {passed}/49 passed'
summary = pathlib.Path('output/l3/s225/SWEEP_VERIFICATION_SUMMARY.md').read_text()
assert str(passed) in summary
# Audit W-B: classification must be present
assert 'STOCK_OUT' in summary or 'RACE_CONDITION' in summary or '49/49' in summary or '48/49' in summary, \\
    'failure-cause classification missing per audit W-B'
print(f'PHASE 6 PASS — {passed}/49 (was 16/49 in S223)')
"
```

## Phase 7 — Closeout (2 units)

**Tasks:**

1. Update plan YAML: `status: PLANNED` → `COMPLETED`, set `completed_date`, populate `execution_summary`.
2. Update `docs/plans/SPRINT_REGISTRY.md` S225 row with PR number + COMPLETED status.

3. **Final canonical postcheck (audit B-7 fix):** write `canonical_postcheck_phase7.txt` so the closeout gate has a stable filename to assert (Phase 3 wrote `_phase3.txt` for its own checkpoint; Phase 7 needs its own snapshot too):
    ```bash
    python scripts/verify_canonical_structure.py > output/s225/verification/canonical_postcheck_phase7.txt 2>&1
    # Also produce the un-suffixed version that the original v1 closeout gate referenced
    cp output/s225/verification/canonical_postcheck_phase7.txt \
       output/s225/verification/canonical_postcheck.txt
    ```

4. Commit + push remaining evidence:
    ```bash
    cd F:/Dropbox/Projects/BEI-ERP-s225-canonical-warehouse-cleanup-and-pattern-a-safeguard
    git add -f docs/plans/2026-04-26-sprint-225-canonical-warehouse-cleanup-and-pattern-a-safeguard.md
    git add -f docs/plans/SPRINT_REGISTRY.md
    git add -f output/s225/
    git add -f output/l3/s225/
    git commit -m "chore(S225): closeout — plan + registry + L3 evidence"
    git push origin s225-canonical-warehouse-cleanup-and-pattern-a-safeguard
    ```

5. **Update the existing PR (created in Phase 4.5)** with the final SUMMARY:
    ```bash
    PR_URL=$(cat tmp/s225/s225_pr_url.txt)
    PR_NUM=$(echo "$PR_URL" | grep -oE '[0-9]+$')
    GH_TOKEN="" gh pr edit $PR_NUM --repo Bebang-Enterprise-Inc/hrms \
      --body "$(cat output/s225/SUMMARY.md)"
    ```
    Note: the PR was already merged in Phase 4.5 if Sam merged before Phase 5/6. Otherwise this updates the PR with full closeout summary.

6. Share PR# with Sam and STOP. Sam confirms merge if not yet done.

7. **Worktree removal — BOTH worktrees (audit B-12 fix):**
    ```bash
    # hrms worktree
    cd F:/Dropbox/Projects/BEI-ERP-s225-canonical-warehouse-cleanup-and-pattern-a-safeguard && git status --short  # must be empty
    cd F:/Dropbox/Projects/BEI-ERP
    git worktree remove F:/Dropbox/Projects/BEI-ERP-s225-canonical-warehouse-cleanup-and-pattern-a-safeguard

    # bei-tasks worktree (was previously left mounted in v1 — fixed here)
    cd F:/Dropbox/Projects/bei-tasks-s225-canonical-warehouse-cleanup-and-pattern-a-safeguard && git status --short  # must be empty
    cd F:/Dropbox/Projects/bei-tasks
    git worktree remove F:/Dropbox/Projects/bei-tasks-s225-canonical-warehouse-cleanup-and-pattern-a-safeguard
    ```

**Phase 7 verification gate (audit B-7 + B-8 + B-12 fix — consistent paths, both worktrees removed):**
```bash
python -c "
import subprocess
remote_files = subprocess.check_output(
    ['git', 'ls-tree', '-r', '--name-only', 'origin/s225-canonical-warehouse-cleanup-and-pattern-a-safeguard'],
    text=True
).splitlines()
must_have = [
    'output/s225/SUMMARY.md',
    'output/s225/RUN_STATUS.json',
    'output/s225/verification/duplicate_warehouse_audit.md',
    'output/s225/verification/dup_consolidation_applied.json',
    'output/s225/verification/canonical_postcheck_phase7.txt',  # B-7 fix: explicit phase7 file
    'output/s225/verification/canonical_postcheck.txt',          # B-7 fix: also keep un-suffixed
    'output/s225/verification/canonical_postcheck_phase3.txt',   # B-7 fix: Phase 3 checkpoint
    'output/s225/verification/pattern_a_concurrency_results.json',
    'output/s225/verification/s224_deploy_sha_check.json',       # B-5 fix: deploy verification evidence
    'output/l3/s225/sweep_full_run.log',                         # B-8 fix: canonical sweep log
    'output/l3/s225/SWEEP_VERIFICATION_SUMMARY.md',              # B-8 fix: under l3/, not under verification/
    'docs/plans/2026-04-26-sprint-225-canonical-warehouse-cleanup-and-pattern-a-safeguard.md',
]
missing = [p for p in must_have if p not in remote_files]
assert not missing, f'evidence missing on remote: {missing}'
# Both worktrees removed (B-12 fix)
worktrees_hrms = subprocess.check_output(['git', '-C', 'F:/Dropbox/Projects/BEI-ERP', 'worktree', 'list'], text=True)
assert 's225' not in worktrees_hrms, 'hrms s225 worktree still present'
worktrees_bt = subprocess.check_output(['git', '-C', 'F:/Dropbox/Projects/bei-tasks', 'worktree', 'list'], text=True)
assert 's225' not in worktrees_bt, 'bei-tasks s225 worktree still present (audit B-12 — must remove both)'
print('PHASE 7 PASS — both worktrees removed, all evidence on remote with correct paths')
"
```

## Library Audit & Contributions (test discipline)

**Library audit (Phase 1 task 4):** The targeted L3 retest reuses the existing S209 `s209-all-stores.spec.ts` with a `--grep` filter. No new Page Objects required — Pattern B + C fixes operate inside existing Page Objects (`OrderApprovalPage`, `WarehouseApprovalPage`, `DispatchPage`) which were already in place pre-S224.

**Library contributions (this sprint adds):**

- `scripts/s225_audit_warehouse_duplicates.py` — reusable canonical duplicate detection logic (Phase 2)
- `scripts/canonical/retire_warehouse_duplicate.py` — reusable duplicate retirement primitive (Phase 3, lives under `scripts/canonical/` per rule 6)
- `scripts/s225_validate_s224_pattern_b.py` + `scripts/s225_validate_s224_pattern_c.py` — direct REST probe pattern for validating deployed fixes (template for future S### sprints)
- `scripts/s225_pattern_a_lock_smoke.py` + `scripts/s225_pattern_a_concurrent_stress.py` — concurrency stress harness pattern (template for future race-condition sprints)

**Three-uses rule:** if a future sprint hits a third use case for "audit canonical drift in domain X", the audit script generalizes to a `scripts/canonical/audit_drift.py` parameterized by table + clustering rule. Out of scope for S225 — flagged for S226+.

**MUST_NOT (test discipline):**
- No `page.request.*` or `fetch(/api/method/...)` in any modified test code (none planned in this sprint, but the rule applies)
- No mutation of `bei-tasks/tests/e2e/pages/*` files (CEO directive 2026-04-25 is permanent)

## Failure Response

- **Mode A (app bug):** if Phase 5 stress test reveals a NEW failure pattern in `create_stock_transfer` not predicted by Sentry → file as `[BUG]` in `output/s225/DEFECT_REGISTER.md`, stop iterating on the lock, surface to Sam. Do NOT mask in tests.
- **Mode B (test bug):** Phase 1 targeted sweep failure that the trace shows is a test selector / timing issue, not a product issue → fix in the Page Object, NOT inline in the spec. If the fix would benefit other tests, promote.
- **Mode C (brittleness):** if Phase 6 full sweep flakes (≥3 stores fail differently between two consecutive runs) → fix the LIBRARY (Page Object timing/selectors). Never `waitForTimeout` or `retry(3)` masking. If ≥3 library fixes happen, emit `output/l3/s225/LIBRARY_IMPROVEMENTS.md`.

## Zero-Skip Enforcement

**Forbidden agent behaviors (audit B-10 fix — added Phase 2 + Phase 3 + Phase 4.5):**
- Skipping Phase 1 (S224 validation) and proceeding to Phase 2-7 — the whole sprint depends on the S224 baseline being live AND deployed
- Skipping Phase 2 (canonical audit) — agents have a documented bias toward "the sprint already addresses Pattern A so canonical cleanup can wait"; this is the exact thing Sam wants done "once and for all"
- Skipping Phase 3 (canonical consolidation) — same audit-bias risk; the 648 stranded units only get freed in Phase 3
- **Skipping Phase 4.5 (deploy-SHA gate) — running Phase 5/6 against pre-deploy code is corrupt success per audit B-4 (S218/S219 plateau pattern)**
- Marking Phase 3 consolidation "done" if Sam approval token is missing
- Direct SQL on `tabBin` to "fix" stock balances (must use Material Transfer Stock Entry per audit B-2/B-3 fix)
- `frappe.delete_doc` on any Warehouse (must use `disabled=1`)
- Using Stock Reconciliation instead of Material Transfer for canonical cleanup (audit B-2/B-3: SR.add_batch is hallucinated v15 API; SR creates wrong BIR audit trail)
- Removing or modifying the existing `set_backend_observability_context(module="warehouse", action="create_stock_transfer", ...)` call
- Replacing the FOR UPDATE lock with a `try/except` to swallow negative-stock errors
- Locking only `tabBin` when the items are batch-tracked (audit W-1 — must lock both `tabBin` AND `tabBatch` for batch-tracked items)
- Passing empty `approved_items` to the Phase 1 Pattern B probe (audit B-6 — must construct from MR's actual items)
- "Deferred to next sprint" for Phase 1, **Phase 2, Phase 3,** Phase 4.5, Phase 5, Phase 6, or Phase 7
- Skipping the canonical postcheck after any master-data mutation
- Treating "PR merged" as sufficient evidence of deploy (audit B-5 — must verify Docker container code SHA)

**Phase Completion Checklist** (agent fills after each phase, in `output/s225/PHASE_CHECKLIST.md`):

```markdown
| Phase | Task | Status | Evidence path | Skipped? | If skipped, why? |
|---|---|---|---|---|---|
| 0 | Boot + worktree + canonical preflight | DONE | output/s225/verification/canonical_preflight.txt | NO | — |
| 1 | Validate S224 PR #687 + Pattern B + Pattern C | ... | ... | ... | ... |
| 2 | Warehouse duplicate audit | ... | output/s225/verification/duplicate_warehouse_audit.md | ... | ... |
| 3 | Consolidation (Sam-gated) | ... | output/s225/verification/dup_consolidation_applied.json | ... | ... |
| 4 | FOR UPDATE lock implementation | ... | git diff hrms/api/warehouse.py | ... | ... |
| 5 | Concurrency stress test | ... | output/s225/verification/pattern_a_concurrency_results.json | ... | ... |
| 6 | Full L3 sweep | ... | output/l3/s225/sweep_full_run.log | ... | ... |
| 7 | Closeout (registry + PR + worktree) | ... | git ls-tree origin/s225 | ... | ... |
```

**PR description gate:** the PR body MUST include the full task-by-task checklist as a top-level `## S225 Phase Status` section. Unchecked items need an explanation. Sam rejects PRs with unexplained gaps.

**Verification script (per S154 lesson — filesystem-grounded, not prose):** `output/s225/verify_phase_<N>.py` for each phase. The phase verification gates above already define these.

## Status Reconciliation Contract

When pass count, blocker, or phase status changes, update IN THE SAME COMMIT:

1. `output/s225/RUN_STATUS.json`
2. `output/s225/RUN_SUMMARY.md`
3. `output/s225/PHASE_CHECKLIST.md`
4. plan YAML status field (only at sprint completion)
5. `docs/plans/SPRINT_REGISTRY.md` S225 row (only at sprint completion or major status change)

## Autonomous Execution Contract

- **completion_condition (v2 — updated per audit):**
  - Phase 1 confirms S224 PR #687 MERGED **and deployed** (Docker container code SHA verified, not just gh pr view) + targeted sweep ≥5/6 passing
  - Phase 2 audit produced with intercompany clusters flagged separately; Sam approval token recorded via PR comment
  - Phase 3 consolidation via **Material Transfer Stock Entry** (not Stock Reconciliation per audit B-2/B-3): 0 canonical violations post-apply, two-sided per-item stock conservation verified, system-wide conservation verified
  - Phase 4 `git diff` shows only `hrms/api/warehouse.py` modified; FOR UPDATE present; covers `tabBin` AND `tabBatch` for batch-tracked items (audit W-1); Sentry context preserved
  - **Phase 4.5: deploy-SHA verification confirms container running merge commit code — Phase 5/6 must NOT run before this**
  - Phase 5: 0 negative-stock errors, 0 deadlocks, ≥8/10 success in concurrency stress (against deployed lock code)
  - Phase 6: full sweep ≥36/49 PASS (no regression vs S223 baseline); failure-cause classification per store (RACE_CONDITION / STOCK_OUT / RESIDUAL_PATTERN_B / RESIDUAL_PATTERN_C / NEW_PATTERN per audit W-B)
  - PR updated with closeout SUMMARY.md; both worktrees (hrms + bei-tasks) removed
  - All evidence files at canonical paths (audit B-7/B-8 fix): `output/l3/s225/sweep_full_run.log`, `output/s225/verification/canonical_postcheck_phase7.txt`, `output/s225/verification/canonical_postcheck.txt` all on remote branch

- **stop_only_for:**
  - S224 PR #687 not merged at Phase 1 → STOP, ask Sam
  - Phase 2 audit identifies a cluster Sam hasn't approved (Phase 3 only applies approved clusters)
  - Phase 5 concurrency stress fails 3 iterations of fix attempts → STOP, ask Sam
  - Phase 6 sweep regresses below S223 16/49 baseline → STOP, ask Sam
  - Canonical postcheck shows new violations after any phase → STOP, ask Sam
  - Pattern A lock change introduces a deadlock that can't be fixed by lock-order sorting → STOP, ask Sam

- **continue_without_pause_through:**
  - audit
  - execute (all 8 phases in canonical order: 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7)
  - PR creation
  - worktree removal

- **blocker_policy:**
  - programmatic (typo, broken import) → fix and continue
  - environment (test account locked, Doppler secret expired) → debug, fix env, continue
  - business-data (Sam approval missing for cluster) → defer cluster, continue with approved ones
  - approval (Phase 2 → Phase 3 token) → pause until token present in `output/s225/verification/sam_consolidation_approval.md`

- **signoff_authority:** `single-owner` — Sam (CEO). No department co-signs needed.

- **canonical_closeout_artifacts:**
  - `output/s225/RUN_STATUS.json`
  - `output/s225/RUN_SUMMARY.md`
  - `output/s225/SUMMARY.md`
  - `output/s225/PHASE_CHECKLIST.md`
  - `output/s225/verification/duplicate_warehouse_audit.{json,md}`
  - `output/s225/verification/dup_consolidation_applied.json`
  - `output/s225/verification/canonical_postcheck.txt`
  - `output/s225/verification/pattern_a_concurrency_results.json`
  - `output/s225/verification/sweep_post_s224_s225_summary.md`
  - `docs/plans/2026-04-26-sprint-225-canonical-warehouse-cleanup-and-pattern-a-safeguard.md` (this file, status updated)
  - `docs/plans/SPRINT_REGISTRY.md` (S225 row updated)

## Signoff Model

- **mode:** single-owner
- **approver_of_record:** Sam Karazi (CEO, sam@bebang.ph)
- **signoff_artifact:** `output/s225/RUN_SUMMARY.md` final state + `output/s225/verification/sam_consolidation_approval.md` (Phase 2→3 gate)

## Files

This plan creates / modifies:

**hrms (backend + scripts + master data):**
- `hrms/api/warehouse.py` — Phase 4 (FOR UPDATE lock in `create_stock_transfer` — covers both `tabBin` AND `tabBatch` for batch-tracked items per audit W-1; preserves existing `module="warehouse"` Sentry context)
- `scripts/s225_audit_warehouse_duplicates.py` — NEW (Phase 2 audit, read-only, includes audit B-13 intercompany hard-stop)
- `scripts/canonical/retire_warehouse_duplicate.py` — NEW (Phase 3 mutation via **Material Transfer** Stock Entry per audit B-2/B-3 fix; lives under `scripts/canonical/` per rule 6)
- `scripts/s225_validate_s224_pattern_b.py` — NEW (Phase 1 REST probe — audit B-6 fix: constructs `approved_items` from MR's actual items)
- `scripts/s225_validate_s224_pattern_c.py` — NEW (Phase 1 REST probe)
- `scripts/s225_check_s224_deploy_sha.py` — NEW (audit B-5 fix — verifies deployed Docker container has S224 code, not just merged PR)
- `scripts/s225_check_sam_approval.py` — NEW (audit B-11 fix — polls PR comments for Phase 3 approval token, writes canonical local file)
- `scripts/s225_probe_batch_tracking.py` — NEW (audit W-1 — Phase 4 task 0 probe for `Item.has_batch_no` to determine lock scope)
- `scripts/s225_pattern_a_lock_smoke.py` — NEW (Phase 4 single-thread probe)
- `scripts/s225_wait_for_deploy.py` — NEW (Phase 4.5 — polls Docker container until Phase 4 lock code is live; audit B-4 fix)
- `scripts/s225_pattern_a_concurrent_stress.py` — NEW (Phase 5 stress test, runs ONLY after Phase 4.5 confirms deploy)
- `output/s225/*` — per evidence_committed list
- `output/l3/s225/*` — sweep evidence (canonical path: `sweep_full_run.log`, `sweep_ledger.json`, `monitor_decisions.log`, `SWEEP_VERIFICATION_SUMMARY.md`)
- `tmp/s225/*` — transient (gitignored)
- `docs/plans/2026-04-26-sprint-225-canonical-warehouse-cleanup-and-pattern-a-safeguard.md` (this file — Phase 7 status update)
- `docs/plans/SPRINT_REGISTRY.md` (S225 row — Phase 7 update)

**bei-tasks:** ZERO modifications. CEO directive 2026-04-25 is permanent — no test-side changes.

## Execution Workflow

- Test Python changes locally (Phase 4 smoke): `/local-frappe`
- Deploy: Sam handles merge + deploy via `/deploy-frappe` (NOT this agent)
- E2E test (Phase 1, Phase 6): `/playwright-bei-erp` or `/l3-v2-bei-erp`
- Bulk SSM probes (Phase 1-3, Phase 5): `/frappe-bulk-edits` pattern via `boto3.client("ssm")`
