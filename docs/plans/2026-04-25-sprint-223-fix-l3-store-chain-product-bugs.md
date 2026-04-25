---
canonical_id: S223
sprint_name: Sprint 223
plan_filename: 2026-04-25-sprint-223-fix-l3-store-chain-product-bugs.md
slug: fix-l3-store-chain-product-bugs

branches:
  hrms: s223-fix-l3-store-chain-product-bugs
  bei-tasks: s223-fix-l3-store-chain-product-bugs

worktrees:
  hrms: F:/Dropbox/Projects/BEI-ERP-s223-fix-l3-store-chain-product-bugs
  bei-tasks: F:/Dropbox/Projects/bei-tasks-s223-fix-l3-store-chain-product-bugs

status: PARTIAL_DEPLOYED
created_date: 2026-04-25
completed_date: null
execution_summary: |
  PARTIAL EXECUTION 2026-04-25 — code-verified shipments + investigation deferrals.

  SHIPPED (verified, ready for review):
  - DEFECT-11 fix: bei-tasks order-approvals/page.tsx default selectedDate="" + hrms ordering.py supports empty date filter. +set_backend_observability_context. Added data-testid for date picker + clear-button.
  - ORTIGAS GREENHILLS TIN apply: Customer.tax_id="688-721-280-00000" via SSM. Canonical postcheck: 0 violations (was 1). 0 prior SIs (no BIR §237 review needed).
  - S221 REST fallback REVERTED in OrderApprovalPage.ts (kept gate-only readback per VERIFICATION-POST-UI convention).
  - S222 SE-existence fallback REVERTED in DispatchPage.ts (canonical poll only). Discipline grep gates pass.

  DEFERRED (require live browser repro per CEO directive 2026-04-25 — no shortcuts):
  - Pattern A: 6 stores (AYALA SOLENAD, AYALA VERMOSA, CTTM TOMAS MORATO, SM GRAND CENTRAL, SM BICUTAN, SM MARIKINA). SSM probe ran; root cause is most likely backend create_stock_transfer raising for intercompany Material Issue path. Hypothesis documented in DEFECT_REGISTER.
  - Pattern B: 4 stores (SM STA. ROSA, ROBINSONS IMUS, SM SOUTHMALL, ROBINSONS ANTIPOLO). Confirmed NOT same root as DEFECT-11 — approve/page.tsx has 0 todayStr() refs. Likely SWR cache or backend get_pending_material_requests scope.
  - Pattern C: 2 stores (NAIA T3, ORTIGAS ESTANCIA). Investigation paused at canonical resolver boundary per HARD STOP rule. Sam approval needed before modifying resolver.
  - Phase 7A/7B sweeps: deferred to Sam — invoke /l3-v2-bei-erp against merged code. Expected best-case: 43/49 (DEFECT-11 +5 + ORTIGAS +1 over S221's 36/49 baseline minus removed fallback support for Pattern A/B/C).

  See output/s223/SUMMARY.md for full breakdown.
work_units: 77
phase_count: 10
audit_amendments_applied: 2026-04-25 (S223 audit B1-B11 — see output/plan-audit/s223-fix-l3-store-chain-product-bugs/verified_blockers.md)

canonical_scope: in
canonical_model_reference: docs/STORE_COMPANY_CANONICAL.md
canonical_preflight: required

evidence_committed:
  - output/s223/SUMMARY.md
  - output/s223/DEFECT_REGISTER.md
  - output/s223/RUN_STATUS.json
  - output/s223/RUN_SUMMARY.md
  - output/s223/verification/state_after.json
  - output/s223/verification/canonical_preflight.txt
  - output/s223/verification/canonical_postcheck.txt
  - output/s223/verification/sweep_final_*.png
  - output/l3/s223/sweep_full_run.log
  - output/l3/s223/sweep_ledger.json
  - output/l3/s223/SWEEP_VERIFICATION_SUMMARY.md
evidence_transient:
  - tmp/s223/trace_zip_extract_*/
  - tmp/s223/devtools_*.json
  - tmp/s223/probe_*.json
  - tmp/s223/console_logs_*.txt
  - tmp/s223/sentry_capture_*.json
  - tmp/s223/playwright_show_trace_*.txt

depends_on:
  - S221 (REST approval fallback merged — must REVERT here)
  - S222 (SE-existence dispatch fallback merged — must REVERT here)
  - S196 (store-first naming — canonical baseline)
  - S206 (per-store labor allocation — canonical seeding precedent)
  - S207 (4-children COA completion — canonical baseline)

execution_authority: Sam (CEO) — single-owner. No department co-signatures required.
---

# S223 — Fix all remaining L3 store-chain failures via real product fixes (no API bypass)

## Bottom line

13 of 49 BEI stores cannot complete the order → approve → dispatch → receive → SI chain in the real app today. Real users (test.area, test.scm, test.warehouse, test.receiver) hit broken UI surfaces. The S221 and S222 fixes were test-side fallbacks that hid these bugs from QA while leaving them broken for users.

This sprint reverts both fallbacks and fixes the underlying product bugs in the actual code paths real users take. The pass-rate target (48/49 with 1 allowed Finance data fix) is the same target real users would experience after deploy.

**Hard rule (CEO directive 2026-04-25):** No `page.request.*`, no `fetch(/api/method/...)`, no `getReadbackCtx`/`queryDocs`/`readDoc`/`frappe.client.*` calls in `bei-tasks/tests/e2e/pages/*` workflow paths. Tests must navigate the same screens, click the same buttons, and wait for the same backend reactions as real users. If a step fails, the bug is in the product, not the test.

**Pre-loaded findings (from S223 audit 2026-04-25, verified by code-verifier + adversarial fact-checker):** the executing agent does NOT need to discover these from scratch — they're confirmed via repo-grounded inspection:
- Pattern A — frontend POSTs to `/api/method/hrms.api.warehouse.create_stock_transfer` (NOT `store.create_warehouse_transfer` which doesn't exist)
- Pattern B + DEFECT-11 — primary hypothesis is `selectedDate = todayStr()` at `bei-tasks/app/dashboard/store-ops/order-approvals/page.tsx:548`. Verify in Phase 3A; reject only if trace contradicts.
- Pattern C — `hrms/api/store.py:submit_order` already calls `set_backend_observability_context(module="ordering", ...)`. Preserve `module="ordering"` — do NOT change to a new string.
- ORTIGAS GREENHILLS TIN — both TINs belong to the SAME legal entity (BEIFRANCHISE FOOD OPC); the suffix distinguishes HQ vs the Greenhills physical branch:
  - `hrms/data_seed/company_register_2026-04-14.csv` row 38 → HQ TIN `688-721-280-00000` (BEIFRANCHISE FOOD OPC headquarters)
  - `data/ENTITY_TIN_RDO_2026-02-27.csv` row 49 → branch TIN `688-721-280-00001` (the Ortigas Greenhills location, RDO 042)
  
  **Per Sam directive 2026-04-25: apply HQ TIN `688-721-280-00000` for now.** The auto-provision hook conflict (it currently writes branch TIN) is a known follow-up — the hook only fires on NEW Company creation, and ORTIGAS GREENHILLS Company already exists, so the conflict is theoretical for this record. A follow-up sprint can align the hook with this policy decision.
- Affected pages use SWR (`useSWR().mutate()`) — not TanStack Query. Cache invalidation pattern: SWR mutate hooks.
- Test fallbacks live in `bei-tasks/tests/e2e/support/frappeReadback.ts` via helpers `getReadbackCtx`, `queryDocs`, `readDoc`. Phase 6 grep gate must catch all of these — NOT just `page.request|fetch(`.

## Design Rationale (For Cold-Start Agents)

### Why this exists

- 2026-04-23: S221 added a REST fallback to `OrderApprovalPage.approve` because the approval page client-side rendering narrowed the order list to ≤1 entry for 7 stores. The fallback called `/api/method/hrms.api.store.approve_order` directly when the UI couldn't show the order. Pass rate went 31→36 of 49.
- 2026-04-24: S222 added an SE-existence fallback to `DispatchPage.dispatch` because the 30s poll watched `MR.per_transferred > 0` which never bumps for Material Issue MRs. The fallback queried `Stock Entry Detail` directly. Result: 33/49 (REGRESSION −3) — fallback couldn't help because the trace zips proved the modal click never reached the backend, so no SE was ever created. The DEFECT-8 "dispatch not registered" label was hiding 3 distinct UI bugs.
- 2026-04-25: CEO directive after reading the S222 closeout — "this is not a fix, this is a shortcut to pass the test and break the rules." The L3 sweep is meant to verify real-user happy paths. Tests bypassing broken UI defeat that purpose. Required: real product fixes, no shortcuts, all 49 stores covered.

### Why this architecture (no fallbacks, real fixes)

- **Canonical UI-first discipline (`.claude/docs/qa-test-library-discipline.md`):** Page Objects are forbidden from calling `page.request.*` or `fetch()` for workflow operations. Every workflow click must go through the actual UI. Backend calls are allowed only for environmental setup and final state verification. S221 + S222 violated this in spirit by adding "fallback" REST calls inside Page Objects.
- **Real-user-equivalence:** The L3 sweep certifies that 49 BEI stores can complete the daily order chain. If `test.scm` can't dispatch an order to AYALA SOLENAD via the UI, neither can the real SCM team. The sweep is our production-readiness signal; tests passing while users fail is a false-green signal.
- **Trace-first debugging (memory: `feedback_trace_first_hypothesize_second.md`):** S218 + S219 wasted ~4 hours each writing test-side patches based on wrong-layer hypotheses. S221 + S222 moved closer to the real layer but still applied band-aids instead of root-cause fixes. S223 must read the error-context.md trace BEFORE any code change AND must fix the layer the trace identifies.

### Key trade-off decisions

| Decision | Chosen | Rejected | Reason |
|---|---|---|---|
| Single sprint vs split into 4 | Single S223 (all 4 patterns) | Split into S223+S224+S225+S226 | The 4 patterns share investigation infrastructure (worktrees, trace tooling, sweep harness). Splitting forces 4 cycles of preflight/postcheck/sweep × 55min each. Total work units fit under the 80-unit ceiling (75u). |
| Revert S221+S222 fallbacks first or last | Last (Phase 6, after fixes ship) | First | Reverting first would push the baseline to ~24/49 before any fix lands, making mid-sprint progress hard to read. Reverting last forces the final sweep to verify product fixes alone, with no test-side help. |
| Combine Pattern B + DEFECT-11 | Yes | Treat as 2 separate phases | Trace evidence (output/l3/s222/TRIAGE_REPORT.md) shows both are client-side rendering narrowing on approval pages — likely the same root cause class, possibly the same shared component. Combine investigation, split fixes only if root causes diverge. |
| Browser-only vs SSM-allowed | Browser-only for workflow, SSM for verify | Allow SSM dispatch | The CEO rule is explicit. SSM is allowed for canonical preflight + post-fix state inspection, never for clicking buttons users would click. |
| Fix UI bug or replace UI surface | Fix in place | Replace approval/dispatch pages | These are operator-facing pages already in use by SCM/warehouse staff. Replacement would expand scope to UX redesign and miss the deadline goal. The CTAs work for some stores; we're fixing the narrowing/click bugs that affect specific stores. |

### Known limitations and their mitigations

- **The 13 failing stores include ORTIGAS GREENHILLS** which has an empty TIN that blocks Sales Invoice posting. This is data, not code. Phase 5 hands ORTIGAS GREENHILLS to Finance for TIN entry; the sprint passes at 48/49 with the 1 allowed skip if Finance hasn't filed by closeout.
- **S221 fallback removal will surface DEFECT-11** which is the same class as Pattern B but on a different page (`/dashboard/store-ops/order-approvals`). Phase 3 explicitly extends scope to fix DEFECT-11 too.
- **Pattern A root cause unknown today.** Trace shows the modal stuck open with all data correct. Could be a React state bug, a network call swallowed by an error boundary, a button handler not wired, or a race with the dispatch queue refresh. Phase 2A is investigation-first; Phase 2B is the fix once the cause is known.
- **Test-account locking risk:** the sweep submits orders for 49 stores in a single run. If a fix lands mid-sprint that changes order numbering or allocation, mid-sprint sweeps will fail spuriously. Mitigation: each phase's per-store verification uses a single store, not the full sweep; full sweep happens only at Phase 7.
- **Worktree disk pressure:** `BEI-ERP-s223-*` worktree clones the full hrms tree (~5K files). Cleanup at closeout (Phase 8) is mandatory.

### Source references

- S221 closeout: `output/l3/s221/SWEEP_VERIFICATION_SUMMARY.md`
- S222 triage: `output/l3/s222/TRIAGE_REPORT.md`
- S222 closeout summary: `output/l3/s222/SWEEP_VERIFICATION_SUMMARY.md`
- L3 test discipline rule: `.claude/docs/qa-test-library-discipline.md`
- Memory lessons: `memory/feedback_trace_first_hypothesize_second.md`, `memory/feedback_kill_sweep_fix_backend.md`, `memory/feedback_corrupt_success.md`
- Library improvements changelog: `output/l3/retrospective/LIBRARY_IMPROVEMENTS.md`
- Trace artifacts (Playwright): `C:/Users/Sam/AppData/Local/Temp/bei-pw-artifacts/specs-s209-all-stores-S209-*--chromium/`
- Frontend Page Objects: `F:/Dropbox/Projects/bei-tasks/tests/e2e/pages/{DispatchPage,OrderApprovalPage,WarehouseApprovalPage,ReceivingPage,StoreOrderingPage}.ts`
- Backend MR creation: `F:/Dropbox/Projects/BEI-ERP/hrms/api/store.py` (functions `submit_order`, `approve_order`, `_create_material_request`)
- Canonical resolver: `F:/Dropbox/Projects/BEI-ERP/hrms/api/store.py:resolve_store_buyer_entity`
- Sweep monitor: `scripts/s212_launch_sweep.py`, `scripts/s212_sweep_monitor.py`
- Cleanup harness: `scripts/s209_cleanup_sweep.py`, `scripts/s222_final_cleanup_probe.py` (will be re-dated to s223)

## Canonical Model Preflight (Mandatory)

Executing agent MUST run before the first code change:

```bash
python scripts/verify_canonical_structure.py > output/s223/verification/canonical_preflight.txt 2>&1
tail -10 output/s223/verification/canonical_preflight.txt
```

Expected output: 1 violation only — `BILLING_CUST_TIN_EMPTY` for `ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC` (the allowed skip; will be resolved in Phase 5). Any OTHER violation → STOP and ask Sam.

**Canonical law (summary — full rules in `docs/STORE_COMPANY_CANONICAL.md`):**
- Every store has EXACTLY 1 per-store Company + 1 Warehouse + 1 billing Customer + 1 Internal Customer.
- All four share the same name string.
- Billing Customer's `tax_id` = legal entity BIR TIN. ORTIGAS GREENHILLS is the one exception, currently being filed.

**Forbidden in this plan (without explicit Sam approval):**
- Creating second Warehouse/Company/Customer for any store.
- Adding new fallback logic to `resolve_store_buyer_entity`.
- Mutating `tabCompany` / `tabWarehouse` / `tabCustomer` via ad-hoc SQL — only the canonical scripts or this plan's TIN-fix script may write.
- Reusing internal Customer for regular SI.

**Scope claim:**
- This plan creates ZERO new Companies, Warehouses, or Customers.
- This plan UPDATES exactly 1 Customer record: `ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC` to set `tax_id = '688-721-280-00000'` (the HQ TIN of BEIFRANCHISE FOOD OPC from `hrms/data_seed/company_register_2026-04-14.csv` row 38 — per Sam directive 2026-04-25; Phase 5).
- This plan READS canonical resolvers (`resolve_warehouse_company`, `resolve_store_buyer_entity`) for trace verification but does not modify them.

## Canonical Model Binding

This sprint's UI fixes do not change canonical data flow. The Page Objects and components being fixed already bind correctly:

- `DispatchPage.dispatch` reads `Material Request → Stock Entry Detail` (canonical doc relations) — fix preserves this.
- `WarehouseApprovalPage` reads `Material Request` queue scoped by `Warehouse → Company` — fix preserves this.
- `OrderApprovalPage` reads `BEI Approval Queue` scoped by user roles — fix preserves this.
- `submit_order` continues calling `resolve_store_buyer_entity(warehouse_docname)` — backend change in Phase 4 does NOT alter resolution path.

**Does NOT:**
- Bypass canonical resolvers via warehouse-name string parsing.
- Hardcode parent Company names.
- Add parallel store_id / branch_code identifiers.

**Closeout verifier check:** Phase 8 re-runs `scripts/verify_canonical_structure.py` and asserts only the (now-resolved or still-pending) ORTIGAS TIN entry differs vs preflight.

## Worktree Isolation & Evidence Split

Two worktrees required (one per repo):

```bash
# hrms (Python backend + master data)
cd F:/Dropbox/Projects/BEI-ERP && git fetch origin --prune
git worktree add F:/Dropbox/Projects/BEI-ERP-s223-fix-l3-store-chain-product-bugs \
  -B s223-fix-l3-store-chain-product-bugs origin/production

# bei-tasks (React frontend + Page Objects)
cd F:/Dropbox/Projects/bei-tasks && git fetch origin --prune
git worktree add F:/Dropbox/Projects/bei-tasks-s223-fix-l3-store-chain-product-bugs \
  -B s223-fix-l3-store-chain-product-bugs origin/main
```

All work happens in worktrees. Main checkouts (`F:/Dropbox/Projects/BEI-ERP` and `F:/Dropbox/Projects/bei-tasks`) are read-only inspection only.

**Closeout removes both worktrees** (Phase 8). If either has uncommitted scratch at closeout, it must be committed to a follow-up branch (never to a merged PR branch) before removal.

**Evidence split (matches frontmatter):**
- Final summaries, DEFECT_REGISTER, canonical pre/postcheck, sweep ledger, final state JSONs → `output/s223/` and `output/l3/s223/` (committed).
- Trace-zip extracts, DevTools snapshots, Sentry captures, mid-run probes → `tmp/s223/` (gitignored).

## Anti-Rewind / Concurrent-Run Protection Contract

| Surface | Owner | File globs |
|---|---|---|
| `bei-tasks/tests/e2e/pages/DispatchPage.ts` | This sprint | full file (revert + improve) |
| `bei-tasks/tests/e2e/pages/OrderApprovalPage.ts` | This sprint | full file (revert + improve) |
| `bei-tasks/tests/e2e/pages/WarehouseApprovalPage.ts` | This sprint | full file (improve) |
| `bei-tasks/app/dashboard/warehouse/dispatch/page.tsx` | This sprint | full file (Pattern A fix) |
| `bei-tasks/app/dashboard/warehouse/approve/page.tsx` | This sprint | full file (Pattern B fix) |
| `bei-tasks/app/dashboard/store-ops/order-approvals/page.tsx` | This sprint | full file (DEFECT-11 fix) |
| `hrms/api/store.py` | This sprint, FUNCTIONS ONLY | `submit_order`, `_create_material_request`, `approve_order` (read-only verify) |
| `tabCustomer` row for ORTIGAS GREENHILLS | This sprint | exactly 1 row UPDATE on `tax_id` |

**Protected surfaces (must not change):**
- `hrms/api/store.py:resolve_store_buyer_entity` (canonical resolver — frozen since S196)
- `hrms/api/store.py:resolve_warehouse_company` (canonical resolver — frozen since S196)
- All `tabCompany` rows
- All `tabWarehouse` rows
- All other `tabCustomer` rows (only ORTIGAS GREENHILLS gets an UPDATE)
- Any `hrms/on_demand/s206_*` script
- Any `scripts/canonical/*.py` script

**Remote-truth baseline (record at Phase 0 boot):**
- hrms `origin/production` HEAD: capture in `output/s223/verification/baseline.json`
- bei-tasks `origin/main` HEAD: capture in `output/s223/verification/baseline.json`

**Pre-touch backup contract:** Before Phase 5 ORTIGAS Customer UPDATE, agent MUST snapshot the row first via SSM `frappe.get_doc("Customer", "ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC").as_dict()` → `output/s223/verification/ortigas_customer_before.json`. Same after the update → `ortigas_customer_after.json`.

## Requirements Regression Checklist

Executing agent MUST verify each item before claiming any phase complete:

- [ ] Have I removed `page.request.*` and `fetch()` usage from `bei-tasks/tests/e2e/pages/*.ts` workflow paths?
- [ ] Are all 49 stores tested through the SAME UI a real user uses (no role escalations, no API shortcuts)?
- [ ] Did I revert S221's REST approval fallback before claiming Phase 6 done?
- [ ] Did I revert S222's SE-existence dispatch fallback before claiming Phase 6 done?
- [ ] Have I read `error-context.md` for at least one failing store BEFORE writing any fix for that pattern?
- [ ] Have I tested the fix manually in a real browser (logged in as the actual test user) before declaring the fix done?
- [ ] Does the fix address the layer the trace identifies — not the layer above or below it?
- [ ] Have I run `scripts/verify_canonical_structure.py` at the start AND end and confirmed zero new violations?
- [ ] Has every modified `@frappe.whitelist()` endpoint received a `set_backend_observability_context()` call (Sentry rule DM-7)?
- [ ] Are bei-tasks API routes I modified covered by the auto-instrumented `@sentry/nextjs` SDK?
- [ ] Have I committed evidence files to `output/s223/` and `output/l3/s223/` per the YAML split?
- [ ] Has the worktree been removed at closeout?
- [ ] Has the SPRINT_REGISTRY.md row been updated to COMPLETED with PR links?

## Phase Budget Contract

| Phase | Title | Units | Owner | Repo |
|---|---|---|---|---|
| 0 | Boot, worktrees, canonical preflight, library audit, testid registry | 6 | hrms | both |
| 1 | Investigation: open trace zips, write DEFECT_REGISTER for all 13 stores | 8 | hrms | both (read-only) |
| 2A | Pattern A — Dispatch modal "Create Transfer" click — root cause | 6 | bei-tasks | bei-tasks |
| 2B | Pattern A — Fix + per-store verify + Vitest setup | 9 | bei-tasks | bei-tasks |
| 3A | Pattern B + DEFECT-11 — Confirm pre-loaded hypothesis (line 548) | 3 | bei-tasks | bei-tasks |
| 3B | Pattern B + DEFECT-11 — Fix + per-store verify | 10 | bei-tasks | bei-tasks |
| 4 | Pattern C — MR creation fix (NAIA T3 + ORTIGAS ESTANCIA) + regression check + rollback | 11 | hrms | hrms |
| 5 | ORTIGAS GREENHILLS TIN apply (canonical TIN from registry) + BIR §237 review | 5 | hrms | hrms (master data) |
| 7A | Verification sweep WITH fallbacks present (proves Phase 2-4 fixes parallel-safe) | 5 | hrms | both |
| 6 | Remove S221 + S222 test fallbacks | 3 | bei-tasks | bei-tasks |
| 7B | UI-only verification sweep (FINAL — proves real-user-equivalent path passes) | 5 | hrms | both |
| 8 | Closeout: registry, PRs, evidence commit, worktree removal, postcheck | 6 | hrms | both |

**Hard limit:** 15 units per phase. **Largest phase: 4 at 11 units.** All within budget.
**Total: 77 units** (under 80-unit ceiling).

**Phase ordering note (post-amendment B11):** the canonical execution order is `0 → 1 → 2A → 2B → 3A → 3B → 4 → 5 → 7A → 6 → 7B → 8`. Phase 6 (revert fallbacks) sits BETWEEN the two sweeps (7A with fallbacks, 7B without) — this is the audit-mandated sequence to prevent N=49-parallel regressions from masking N=1-manual-verify gaps.

## Plan Resumption Protocol (multi-session execution)

**Realistic wallclock estimate:** investigation (~120min) + Pattern fixes (~180min) + Phase 4 regression check on 5 working stores (~30min) + Phase 5 (~30min) + 2 sweeps × 60min (~120min) + cleanup/PR (~60min) = **~9 hours**. This exceeds typical single-session agent context. The plan is designed to support multi-session resumption; a single session is allowed if budget permits but is not required.

**Checkpoint protocol (mandatory + COMMIT-AT-PHASE-BOUNDARY per S223 audit pass-2 P2-4):** at the end of each phase the executing agent writes AND COMMITS an entry to `output/s223/RUN_STATUS.json`:

```json
{
  "phase": "<phase id, e.g., 2B>",
  "status": "complete | in_progress | blocked",
  "timestamp": "<UTC ISO>",
  "evidence_paths": ["output/s223/verification/pattern_a_*.png", "..."],
  "next_phase": "<next phase id from PHASE_ORDER below>",
  "blockers": [],
  "canonical_postcheck_sha": "<sha256 of canonical_postcheck.txt at this phase>",
  "branch_head_sha": "<git rev-parse HEAD>"
}
```

> **HARD BLOCKER (P2-4):** because `output/` is gitignored, RUN_STATUS.json must be committed via `git add -f` at every phase boundary. Without this, a resuming session in a fresh worktree has NO checkpoint state to read.
>
> ```bash
> git add -f output/s223/RUN_STATUS.json
> git commit -m "chore(S223 checkpoint): phase <X> complete"
> git push origin s223-fix-l3-store-chain-product-bugs
> ```
>
> Push is mandatory — local-only commits don't survive worktree removal. Crash safety requires the checkpoint to be on the remote branch.

**Explicit phase order (canonical execution sequence — non-numeric, must use this list, not increment):**

```python
PHASE_ORDER = [
    "0",      # Boot, worktrees, canonical preflight, library audit, testid registry
    "1",      # Investigation: DEFECT_REGISTER for 13 stores
    "2A",     # Pattern A — Dispatch modal root cause
    "2B",     # Pattern A — Fix + per-store verify + Vitest setup
    "3A",     # Pattern B + DEFECT-11 — Confirm pre-loaded hypothesis (line 548)
    "3B",     # Pattern B + DEFECT-11 — Fix + per-store verify
    "4",      # Pattern C — MR creation fix + regression check + rollback
    "5",      # ORTIGAS GREENHILLS TIN apply + BIR §237 review
    "7A",     # Verification sweep WITH fallbacks present
    "6",      # Remove S221 + S222 test fallbacks      ← runs BETWEEN sweeps
    "7B",     # UI-only verification sweep (final)
    "8",      # Closeout
]
```

When writing RUN_STATUS.json, `next_phase` MUST come from this list — `PHASE_ORDER[PHASE_ORDER.index(current_phase) + 1]`. Numeric increment is wrong.

**Resumption boot sequence (if the plan picks up in a NEW agent session):**

1. **Pull the branch from remote** to a fresh worktree:
    ```bash
    cd F:/Dropbox/Projects/BEI-ERP && git fetch origin --prune
    # Re-spawn worktree if removed
    git worktree add F:/Dropbox/Projects/BEI-ERP-s223-fix-l3-store-chain-product-bugs s223-fix-l3-store-chain-product-bugs
    cd F:/Dropbox/Projects/BEI-ERP-s223-fix-l3-store-chain-product-bugs
    git pull origin s223-fix-l3-store-chain-product-bugs
    ```
2. **Read the committed RUN_STATUS.json** from the branch (not from a stale local file):
    ```bash
    git show s223-fix-l3-store-chain-product-bugs:output/s223/RUN_STATUS.json > /tmp/last_checkpoint.json
    cat /tmp/last_checkpoint.json
    ```
    If the file does not exist on the branch → STOP. Either no checkpoint exists yet (start from Phase 0) or the prior session never committed (recover via `git log --oneline | grep checkpoint` to see how far it got).
3. **Pre-resume verification — confirm worktree state matches the last checkpoint:**
    ```bash
    # Confirm branch HEAD matches the SHA recorded in the last RUN_STATUS
    git rev-parse HEAD
    # Should match RUN_STATUS.branch_head_sha — if NOT, someone pushed more commits, replay needed
    
    # Confirm canonical state hasn't drifted since the last checkpoint
    python scripts/verify_canonical_structure.py > /tmp/canonical_now.txt 2>&1
    # Compare against last committed canonical_postcheck — should be ==
    
    # Confirm bei-tasks worktree state too
    cd F:/Dropbox/Projects/bei-tasks-s223-fix-l3-store-chain-product-bugs && git status --short
    # Should be clean
    ```
    If any pre-resume check fails → STOP, ask Sam to triage.
4. **Look up next phase from the explicit PHASE_ORDER** (not numeric increment). Continue from there.

**Allowed pause boundaries (where a session can hand off to the next without losing context):**
- After Phase 1 (DEFECT_REGISTER complete; no in-flight code changes)
- After Phase 2B (Pattern A shipped + verified; before Phase 3A)
- After Phase 3B (Pattern B+DEFECT-11 shipped; before Phase 4)
- After Phase 5 (master-data work done; before Phase 7A sweep)
- After Phase 7A (with-fallbacks sweep done; before Phase 6 revert)
- After Phase 6 (fallbacks reverted; before Phase 7B sweep)

**Forbidden pause boundaries (don't pause mid-phase if avoidable):**
- During Phase 2B/3B/4 implementation (uncommitted changes)
- During Phase 7A/7B sweep (would orphan test artifacts; cleanup is mid-phase)

If a session must pause mid-phase, the agent commits work-in-progress with `chore(S223 WIP): <phase> partial — see RUN_STATUS.json`, pushes to remote, and records the partial state in RUN_STATUS with `status: "in_progress"`. The next session resumes from the same phase, not the next.

## Phase 0 — Agent Boot Sequence (6 units)

> **HARD BLOCKER:** Agent must NOT touch any code until Phase 0 completes successfully. (Source: S099 + S154 + S091)

1. Read this plan fully end to end.
2. Read `output/l3/s222/TRIAGE_REPORT.md` for the trace-first findings.
3. Read `output/l3/s222/SWEEP_VERIFICATION_SUMMARY.md` for the regression context.
4. Read `.claude/docs/qa-test-library-discipline.md` (the test discipline rules — no `page.request.*`, library-first).
5. Spawn the hrms worktree (see "Worktree Isolation & Evidence Split" above). CWD switches to the worktree.
6. Spawn the bei-tasks worktree.
7. From the hrms worktree, run canonical preflight:
    ```bash
    mkdir -p output/s223/verification output/l3/s223 tmp/s223
    python scripts/verify_canonical_structure.py > output/s223/verification/canonical_preflight.txt 2>&1
    ```
    Expect: 1 violation only (ORTIGAS GREENHILLS empty TIN). Any other violation → STOP, ask Sam.
8. Capture remote-truth baseline:
    ```bash
    cd F:/Dropbox/Projects/BEI-ERP-s223-fix-l3-store-chain-product-bugs
    HRMS_HEAD=$(git rev-parse origin/production)
    cd F:/Dropbox/Projects/bei-tasks-s223-fix-l3-store-chain-product-bugs
    BEI_TASKS_HEAD=$(git rev-parse origin/main)
    cd F:/Dropbox/Projects/BEI-ERP-s223-fix-l3-store-chain-product-bugs
    cat > output/s223/verification/baseline.json <<EOF
    {"hrms_origin_production": "$HRMS_HEAD", "bei_tasks_origin_main": "$BEI_TASKS_HEAD", "captured_at": "$(date -Is)"}
    EOF
    ```
9. Library audit (read-only on bei-tasks):

    | Page Object | Has REST fallback today? | Used for |
    |---|---|---|
    | `OrderApprovalPage` | YES (S221, line ~140-180 — to be reverted in Phase 6) | First approval (test.area) |
    | `DispatchPage` | YES (S222, line ~85-130 — to be reverted in Phase 6) | Warehouse dispatch (test.scm) |
    | `WarehouseApprovalPage` | NO | Second approval (test.scm) |
    | `ReceivingPage` | NO | Store receiving (test.receiver) |
    | `StoreOrderingPage` | NO | Store order submit (test.area) |

    Document gaps that this sprint must close to be UI-only:
    - `data-testid` audit: list any element this sprint's tests interact with that lacks a testid.

    Output: `output/s223/library_audit.md`.

10. **Testid registry contract (B7).** Current testid coverage is thin (verified by S223 audit: `dispatch/page.tsx` = 1 testid, `approve/page.tsx` = 0 testids, `order-approvals/page.tsx` = 3 testids). Ad-hoc additions during fix phases will fork naming. Establish a registry now:
    - Check if `bei-tasks/tests/e2e/test-ids.ts` exists. If yes: read it; later phases append to it.
    - If no: this sprint creates `bei-tasks/tests/e2e/test-ids.ts` with the existing testids audited from current code as baseline + reserved namespace blocks for S223 additions.
    - Write the proposed registry to `output/s223/library_audit.md` under a `## Test ID Registry — S223 reservations` section. Each future testid added in Phase 2B/3B/4 must come from this registry — no ad-hoc strings.
    - Naming convention: `s223-<page>-<element>` (e.g., `s223-dispatch-create-transfer-modal-submit`, `s223-approve-mr-row`, `s223-order-approval-date-picker`).
    - Phase 2B/3B/4 verification gates check that any newly-added `data-testid` matches a registry entry.

11. **Pre-loaded findings fact-freshness check (per S223 audit pass-2 P2-8).** The plan was written 2026-04-25; line numbers and CSV row numbers may drift if execution starts later. Verify each pre-load is still accurate BEFORE Phase 1:
    ```bash
    cd F:/Dropbox/Projects/BEI-ERP-s223-fix-l3-store-chain-product-bugs
    
    # Pattern B narrowing — line 548 in order-approvals/page.tsx
    rg -n "selectedDate\s*=\s*todayStr\(\)" ../bei-tasks-s223-fix-l3-store-chain-product-bugs/app/dashboard/store-ops/order-approvals/page.tsx
    
    # Pattern C Sentry module — module="ordering" in store.py
    rg -n 'module="ordering"' hrms/api/store.py
    
    # Pattern A endpoint — create_stock_transfer in warehouse.py
    rg -n "def create_stock_transfer" hrms/api/warehouse.py
    
    # ORTIGAS branch TIN — row 49 in ENTITY_TIN_RDO csv
    rg -n "BEIFRANCHISE\|Greenhills" data/ENTITY_TIN_RDO_2026-02-27.csv
    
    # Auto-provision hook — Customer.tax_id write in company.py
    rg -n "tax_id" hrms/overrides/company.py
    ```
    For each pre-load, confirm the line/row numbers in the plan match what's actually there. If drift found:
    - Update the plan inline with the corrected line/row numbers
    - Commit as `chore(S223): refresh pre-loaded line numbers` BEFORE proceeding to Phase 1
    - Do NOT proceed with stale references — Phase 2A/3A/5 depend on these being accurate.
    
    If the underlying pattern has changed (e.g., `selectedDate = todayStr()` no longer exists at any line), STOP — the plan's hypothesis is invalidated; ask Sam.

12. Mark Phase 0 complete by writing AND COMMITTING a one-line entry to `output/s223/RUN_STATUS.json` (per P2-4 commit-at-phase-boundary):
    ```bash
    cat > output/s223/RUN_STATUS.json <<EOF
    {"phase": "0", "status": "complete", "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "preflight_violations": 1, "preflight_violations_allowed": ["BILLING_CUST_TIN_EMPTY:ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC"], "next_phase": "1", "branch_head_sha": "$(git rev-parse HEAD)"}
    EOF
    git add -f output/s223/RUN_STATUS.json
    git commit -m "chore(S223 checkpoint): phase 0 complete"
    git push origin s223-fix-l3-store-chain-product-bugs
    ```

**Phase 0 verification gate (machine-checkable):**

```bash
# F:/Dropbox/Projects/BEI-ERP-s223-fix-l3-store-chain-product-bugs
python -c "
import json, pathlib
b = json.load(open('output/s223/verification/baseline.json'))
assert len(b['hrms_origin_production']) == 40, 'baseline hrms HEAD missing'
assert len(b['bei_tasks_origin_main']) == 40, 'baseline bei-tasks HEAD missing'
s = json.load(open('output/s223/RUN_STATUS.json'))
assert s['phase'] == '0' and s['status'] == 'complete'
assert pathlib.Path('output/s223/library_audit.md').exists()
assert pathlib.Path('output/s223/verification/canonical_preflight.txt').stat().st_size > 0
print('PHASE 0 PASS')
"
```

If FAIL → fix and re-run. Do NOT proceed to Phase 1.

## Phase 1 — Investigation: Open trace zips for all 13 failing stores (8 units)

**Goal:** for every failing store, write a DEFECT_REGISTER row that names: (a) the failure layer per trace evidence, (b) the exact element/locator that timed out, (c) which of the 4 patterns (A/B/C/Allowed-skip) it belongs to, (d) the file + line where the fix will land.

**Input:** the 13 trace-zip directories under `C:/Users/Sam/AppData/Local/Temp/bei-pw-artifacts/specs-s209-all-stores-S209-*--chromium/` from S222's last run. (If those have been deleted by Playwright cleanup, run a single-store playwright re-run for each cluster representative to regenerate.)

**Tasks:**

1. List the 13 store-failure trace dirs:
    ```bash
    ls "C:/Users/Sam/AppData/Local/Temp/bei-pw-artifacts/" | grep "specs-s209-all-stores"
    ```
    If the count is <13, regenerate by running 13 single-store playwright tests:
    ```bash
    cd F:/Dropbox/Projects/bei-tasks-s223-fix-l3-store-chain-product-bugs
    npx playwright test tests/e2e/specs/s209-all-stores.spec.ts --grep "AYALA SOLENAD"
    # (and 12 more — automate in a small bash loop)
    ```

2. For each trace dir, extract the trace-zip and read both `error-context.md` and the network log:
    ```bash
    for dir in <13 dirs>; do
      cd "$dir"
      unzip -d "tmp/s223/trace_zip_extract_${dir##*-}" trace.zip
      # produces network.log, snapshots, etc
    done
    ```

3. For each store, populate `output/s223/DEFECT_REGISTER.md` with one row:

    ```markdown
    | Store | Pattern | Layer | Element | Network call | File where fix lands | Hypothesized cause |
    |---|---|---|---|---|---|---|
    | AYALA SOLENAD | A | dispatch modal | button "Create Transfer" inside dialog ref=e29 | (TBD — check network.log) | bei-tasks/app/dashboard/warehouse/dispatch/page.tsx OR component | (TBD per network evidence) |
    | ... 12 more rows ... | | | | | | |
    ```

4. Cluster the 13 rows into the 4 patterns. Confirm or reclassify based on trace evidence:
    - **Pattern A** — Dispatch modal stuck open
    - **Pattern B** — Warehouse approval narrowing
    - **Pattern C** — MR never created
    - **DEFECT-11 (latent, will surface in Phase 6)** — Order approval narrowing (currently masked by S221 REST fallback)
    - **Allowed skip** — ORTIGAS GREENHILLS

5. Produce a one-paragraph "investigation summary" per pattern in `output/s223/DEFECT_REGISTER.md` that names:
   - what is broken (in product terms — "the Create Transfer button does not submit the SE")
   - who hits it (`test.scm` user when dispatching to <stores>)
   - what real users see (same broken UI)
   - why S221 / S222 fallback didn't help (per trace evidence, not hypothesis)

6. Write the verification script `output/s223/verify_phase1.py`:

    ```python
    import json, pathlib, re
    
    register = pathlib.Path('output/s223/DEFECT_REGISTER.md').read_text()
    rows = [r for r in register.splitlines() if r.startswith('|') and 'Pattern' not in r and '---' not in r]
    assert len([r for r in rows if 'A' in r or 'B' in r or 'C' in r or 'allowed-skip' in r.lower()]) >= 13, f'expected 13+ store rows, got {len(rows)}'
    
    for pattern in ['Pattern A', 'Pattern B', 'Pattern C']:
        assert pattern in register, f'investigation summary missing for {pattern}'
    
    print('PHASE 1 PASS')
    ```

**MUST_CONTAIN assertions:**
- `output/s223/DEFECT_REGISTER.md` MUST contain at least 13 store rows
- Each row MUST name a specific file path where the fix will land (no "TBD")
- Each row MUST cite a specific trace artifact path

**MUST_NOT (forbidden):**
- Writing any code change in this phase
- Hypothesizing causes without trace evidence

**Phase 1 verification gate:**
```bash
python output/s223/verify_phase1.py  # must print "PHASE 1 PASS"
```

## Phase 2A — Pattern A root cause investigation (6 units)

**Goal:** identify why clicking the inner "Create Transfer" button on `/dashboard/warehouse/dispatch` does not create a Stock Entry for 6 specific stores.

**Tasks:**

1. Pick the simplest representative store from Pattern A: **AYALA SOLENAD** (single child company, PINNACLE source, smallest item count).

2. Open the trace zip in the Playwright trace viewer (read-only inspection):
    ```bash
    npx playwright show-trace "C:/Users/Sam/AppData/Local/Temp/bei-pw-artifacts/specs-s209-all-stores-S209-26df0--SOLENAD-FOOD-SERVICES-INC--chromium/trace.zip"
    ```
    Inspect: at the moment the test times out, what is the DOM, what is the network log, what console errors are present.

3. Reproduce the bug manually in the real browser:
    - Open `https://my.bebang.ph/dashboard/warehouse/dispatch` logged in as `test.scm@bebang.ph` (password from MEMORY: `BeiTest2026!`)
    - Submit a fresh order from `https://my.bebang.ph/dashboard/store-ops/ordering` as `test.area@bebang.ph` for AYALA SOLENAD (3 DRY items)
    - Approve the order via the actual UI (test.area first approval, then test.scm second approval — DO NOT use REST shortcut even for setup)
    - Navigate test.scm to /dashboard/warehouse/dispatch — find AYALA SOLENAD card, click Create Transfer (outer button)
    - Modal opens. Click Create Transfer (inner button).
    - **Observe** what happens: does the click event fire? Is a network request issued? Does it return 200/4xx/5xx? Does the modal close? Does an error toast appear?

4. Open Chrome DevTools BEFORE clicking the inner button:
    - Network tab open with "Preserve log" checked
    - Console tab open
    - Click Create Transfer
    - Capture: HAR file → `tmp/s223/devtools_pattern_a_ayala_solenad.har`
    - Capture: console output → `tmp/s223/console_logs_pattern_a_ayala_solenad.txt`

5. Cross-check against a working store. Pick a store that PASSED in S222 (e.g., ARANETA GATEWAY). Repeat steps 3-4. Capture HAR + console.
    - Diff the network requests between failing AYALA SOLENAD and passing ARANETA GATEWAY.
    - Identify what differs: request URL, payload, status, response body, response timing, missing requests, etc.

6. Check Sentry for backend errors during the AYALA SOLENAD attempt:
    - Org: `bebang-enterprise-inc`, project `bei-hrms`
    - Filter by time window of step 4
    - Capture any errors → `tmp/s223/sentry_capture_pattern_a.json`

7. Write the root cause section in `output/s223/DEFECT_REGISTER.md`:

    ```markdown
    ## Pattern A Root Cause (verified by trace + manual reproduction)
    
    **What breaks:** [exact technical description — e.g., "the Create Transfer button submits a POST to /api/method/hrms.api.warehouse.create_stock_transfer which returns 200 but the response body says success:false with no error message; the frontend doesn't surface this and leaves the modal open"]
    
    **Pre-loaded fact (verified by S223 audit 2026-04-25):** The real backend endpoint name is `hrms.api.warehouse.create_stock_transfer`. There is NO endpoint called `hrms.api.store.create_warehouse_transfer` — that name appeared in earlier S222 documentation but does not exist. The frontend POSTs to `/api/method/hrms.api.warehouse.create_stock_transfer` (verify: `rg -n 'create_stock_transfer' hrms/api/`). Investigation should grep this exact endpoint in HAR + console + source.
    
    **Trace evidence:** tmp/s223/devtools_pattern_a_ayala_solenad.har, tmp/s223/console_logs_pattern_a_ayala_solenad.txt
    
    **Backend evidence:** [Sentry capture id, or "no backend errors logged" if backend is silent]
    
    **What real users see:** Modal stays open. Same as Playwright trace.
    
    **Why S222 didn't help:** [exact reason from network evidence]
    
    **Fix layer:** [frontend / backend / both — name the file + function]
    ```

**MUST (deliverables):**
- `tmp/s223/devtools_pattern_a_ayala_solenad.har` (≥1KB, real network traffic)
- `tmp/s223/console_logs_pattern_a_ayala_solenad.txt`
- `output/s223/DEFECT_REGISTER.md` with Pattern A root cause section populated

**MUST_NOT:**
- Skip manual reproduction. The CEO directive (2026-04-25) requires verifying via real user flow before writing any fix.
- Use REST shortcuts for setup (order submit + approval). Use the actual UI.

**Phase 2A gate:**
```bash
python -c "
import pathlib
har = pathlib.Path('tmp/s223/devtools_pattern_a_ayala_solenad.har')
assert har.exists() and har.stat().st_size > 1024, 'HAR missing or empty'
register = pathlib.Path('output/s223/DEFECT_REGISTER.md').read_text()
assert 'Pattern A Root Cause' in register
assert 'Fix layer:' in register
print('PHASE 2A PASS')
"
```

## Phase 2B — Pattern A fix + per-store verification (9 units)

**Goal:** ship the fix identified in Phase 2A. Verify all 6 Pattern A stores pass via real-browser UI before declaring done.

**Tasks:**

1. Implement the fix in the file identified by the Phase 2A root cause section.
   - **HARD BLOCKER:** the fix must be in the product code path real users execute, not in `bei-tasks/tests/e2e/pages/*`. (Source: CEO directive 2026-04-25)
   - **MUST_MODIFY** at least one of:
     - `bei-tasks/app/dashboard/warehouse/dispatch/page.tsx`
     - `bei-tasks/components/<dispatch-related-component>.tsx`
     - `hrms/api/store.py` (if root cause is backend)

2. If a hrms backend endpoint is created or modified as part of the Pattern A fix: add `set_backend_observability_context()` matching the existing module string for that file. Codebase precedent (verify with `rg 'set_backend_observability_context' hrms/api/`):
   - `hrms/api/dispatch.py` already uses `module="warehouse"` — preserve it
   - `hrms/api/warehouse.py` already uses `module="warehouse"` — preserve it
   - `hrms/api/store.py` already uses `module="ordering"` — preserve it
   **HARD BLOCKER:** do NOT invent a new module string — that fragments existing Sentry dashboards. Pattern A is a frontend-modal fix; if it does NOT modify any whitelisted endpoint, this task is a no-op (skip and document in DEFECT_REGISTER under Pattern A as "no backend instrumentation needed").

3. If new `data-testid` needed: add to component before relying on it in tests.

4. Manually verify the fix in a real browser for AYALA SOLENAD using the same flow as Phase 2A step 3. Modal must close, success toast must appear, Stock Entry must exist in Frappe (verify by navigating to `https://hq.bebang.ph/app/stock-entry` as Administrator). Capture screenshots → `output/s223/verification/pattern_a_ayala_solenad_after_*.png`.

5. Manually verify each of the remaining 5 Pattern A stores in the real browser:
    - AYALA VERMOSA, CTTM TOMAS MORATO, SM GRAND CENTRAL, SM BICUTAN, SM MARIKINA
    - For each: capture screenshot of the post-dispatch state → `output/s223/verification/pattern_a_<store_slug>_after.png`
    - Cleanup the SE/MR/Order after each verify (use `scripts/s209_cleanup_sweep.py` adapted for the single-store ledger).

6. Update `output/s223/DEFECT_REGISTER.md` Pattern A section: mark each of the 6 stores as VERIFIED with the screenshot path.

7. **Component test setup (verified-state-aware):**
   - **Pre-loaded fact (verified by S223 audit 2026-04-25):** `bei-tasks/package.json` has `vitest` in `devDependencies` but no `test` script defined. Before writing a component test, the agent MUST add the script to `package.json`:
     ```json
     "scripts": {
       ...
       "test": "vitest"
     }
     ```
   - With the script added, write a component test in `bei-tasks/tests/` (or a `__tests__/` co-located folder) that asserts the click handler resolves correctly. Run `npm test` to verify.
   - **Skip path:** if Phase 2A's root cause is purely UI state with no testable handler logic (e.g., the bug was missing aria-label and the fix is HTML-only), document the reason in DEFECT_REGISTER and skip the component test; the manual verification screenshot becomes the only evidence. Document the skip in `output/s223/DEFECT_REGISTER.md` under Pattern A.

8. Commit to the bei-tasks worktree branch with message `fix(S223 Pattern A): <one-line description of the fix>`.

**MUST_MODIFY:**
- (Will be determined by Phase 2A — name the file in DEFECT_REGISTER first, then this phase modifies it)

**MUST_CONTAIN:**
- 6 screenshots in `output/s223/verification/pattern_a_*_after.png` (one per Pattern A store)
- DEFECT_REGISTER Pattern A section: 6 rows marked `VERIFIED` with screenshot path

**Phase 2B gate:**
```bash
python -c "
import pathlib, re
shots = list(pathlib.Path('output/s223/verification').glob('pattern_a_*_after.png'))
assert len(shots) >= 6, f'expected 6 verification shots, got {len(shots)}'
register = pathlib.Path('output/s223/DEFECT_REGISTER.md').read_text()
verified = re.findall(r'VERIFIED.*pattern_a_', register, re.IGNORECASE)
assert len(verified) >= 6, f'expected 6 VERIFIED tags, got {len(verified)}'
print('PHASE 2B PASS')
"
```

## Phase 3A — Pattern B + DEFECT-11 root cause investigation (3 units, reduced)

**Goal:** confirm the pre-loaded narrowing hypothesis for the Warehouse Approval page (Pattern B, 4 stores) AND the Order Approval page (DEFECT-11, ~5 stores once S221 fallback is removed). Determine whether they share a root cause.

**Pre-loaded hypothesis (from S223 audit 2026-04-25, verified by code-verifier + adversarial fact-checker):**

> `bei-tasks/app/dashboard/store-ops/order-approvals/page.tsx:548` contains `selectedDate = todayStr()` defaulting to PHT today. This client-side date filter narrows the rendered queue to "orders for today only", filtering out orders submitted with delivery dates other than today (or orders submitted at 23:59 PHT yesterday that still need today's approval). This is the exact pattern of the S221 DEFECT-11 narrowing.

The investigation in this phase confirms this hypothesis (or rejects and re-investigates) — it does not start from zero.

**Tasks:**

1. **Verify the pre-loaded hypothesis directly:**
    - Read `bei-tasks/app/dashboard/store-ops/order-approvals/page.tsx` around line 548. Confirm the `selectedDate = todayStr()` default still exists (line numbers may have drifted; grep for it).
    - Check the `/dashboard/warehouse/approve/page.tsx` for an equivalent date filter — does it have the same `todayStr()` pattern? Does Pattern B share root cause with DEFECT-11?
    - Read the URL query parsing: when an MR has `delivery_date != today`, does the page filter it out client-side, or does the backend `get_pending_warehouse_approvals` also filter? (If client-side: simple frontend fix. If both layers filter: need backend fix too.)

2. Reproduce Pattern B for SM STA. ROSA in the real browser to confirm:
    - Submit order via `test.area`, approve area-side via `test.area`
    - Switch to `test.scm` → `/dashboard/warehouse/approve`
    - Capture HAR → `tmp/s223/devtools_pattern_b_sm_sta_rosa.har`
    - Diff backend response (the `get_pending_warehouse_approvals` API) against what the page renders in DOM. Confirm whether the narrowing is the `selectedDate` client-side filter or something else.

3. Reproduce DEFECT-11 for FESTIVAL MALL ALABANG (S221's canonical example):
    - Navigate to `/dashboard/store-ops/order-approvals` as `test.area`
    - Submit a fresh order with `delivery_date = today + 2 days` (deliberately not-today to trigger the date filter)
    - Capture HAR → `tmp/s223/devtools_defect_11_festival_mall.har`
    - Confirm the order is in the API response but missing from the rendered DOM.

4. **If hypothesis confirmed:** flag both as same root cause (date filter narrowing) and proceed to Phase 3B with a single fix template. **If hypothesis rejected** (the narrowing is a different mechanism — e.g., role gating, pagination cap, or backend-side filter), document the actual mechanism in DEFECT_REGISTER.

5. Update `output/s223/DEFECT_REGISTER.md` Pattern B + DEFECT-11 root cause sections. Confirm whether shared (one fix unblocks both) or separate (two fixes).

**MUST (deliverables):**
- `tmp/s223/devtools_pattern_b_sm_sta_rosa.har`
- `tmp/s223/devtools_defect_11_festival_mall.har`
- DEFECT_REGISTER updated with root causes

**Phase 3A gate:**
```bash
python -c "
import pathlib
for f in ['tmp/s223/devtools_pattern_b_sm_sta_rosa.har', 'tmp/s223/devtools_defect_11_festival_mall.har']:
    p = pathlib.Path(f)
    assert p.exists() and p.stat().st_size > 1024, f'{f} missing or empty'
register = pathlib.Path('output/s223/DEFECT_REGISTER.md').read_text()
assert 'Pattern B Root Cause' in register
assert 'DEFECT-11 Root Cause' in register
print('PHASE 3A PASS')
"
```

## Phase 3B — Pattern B + DEFECT-11 fix + per-store verification (10 units)

**Goal:** ship the fix(es). Verify all 4 Pattern B stores AND all DEFECT-11 stores (TBD count from Phase 3A) pass via real-browser UI.

**Tasks:**

1. Implement the fix(es). If shared root cause, single fix; if not, two fixes.
    - **MUST_MODIFY** at least one of (per Phase 3A finding):
      - `bei-tasks/app/dashboard/warehouse/approve/page.tsx`
      - `bei-tasks/app/dashboard/store-ops/order-approvals/page.tsx`
      - shared component identified in Phase 3A
    - **HARD BLOCKER:** must be a real product fix, not a query-string bypass or test-only flag.

2. Add Sentry context if backend endpoints touched.

3. Add `data-testid` to any element used by Page Objects that lacks one.

4. Manually verify each of the 4 Pattern B stores + each of the DEFECT-11 stores (5+ — count from Phase 3A) in the real browser. Capture screenshots → `output/s223/verification/pattern_b_<slug>_after.png` and `output/s223/verification/defect_11_<slug>_after.png`.

5. Cleanup after each verify.

6. Update DEFECT_REGISTER with VERIFIED tags + screenshot paths.

7. Commit with message `fix(S223 Pattern B + DEFECT-11): <description>`.

**MUST_CONTAIN:**
- ≥4 screenshots `pattern_b_*_after.png`
- ≥5 screenshots `defect_11_*_after.png` (exact count per Phase 3A)
- DEFECT_REGISTER VERIFIED tags

**Phase 3B gate:**
```bash
python -c "
import pathlib
b_shots = list(pathlib.Path('output/s223/verification').glob('pattern_b_*_after.png'))
d_shots = list(pathlib.Path('output/s223/verification').glob('defect_11_*_after.png'))
assert len(b_shots) >= 4, f'expected 4 Pattern B shots, got {len(b_shots)}'
assert len(d_shots) >= 5, f'expected 5+ DEFECT-11 shots, got {len(d_shots)}'
print('PHASE 3B PASS')
"
```

## Phase 4 — Pattern C: MR creation stall (NAIA T3 + ORTIGAS ESTANCIA) + regression check + rollback (11 units)

**Goal:** identify and fix why orders submitted for NAIA T3 and ORTIGAS ESTANCIA never become Material Requests. Trace shows the order page lingers at "Delivery: 2026-04-25" without progressing.

**Tasks:**

1. Manual reproduction:
    - As `test.area`, submit an order for NAIA T3 via the real ordering UI
    - Observe: does the order get a BEI Store Order docname? Does the dual-approval queue contain it? Does an MR get created on dual-approval completion?
    - Capture HAR + console → `tmp/s223/devtools_pattern_c_naia_t3.har`
    - Repeat for ORTIGAS ESTANCIA → `tmp/s223/devtools_pattern_c_ortigas_estancia.har`

2. Backend probe via SSM (allowed for verification):
    ```bash
    cd F:/Dropbox/Projects/BEI-ERP-s223-fix-l3-store-chain-product-bugs
    python scripts/s223_pattern_c_probe.py  # to be created from s220_direct_submit.py template
    ```
    Probe submits an order for NAIA T3 directly using `submit_order(...)`. Capture: does `frappe.log_error` fire? Does the order row exist? Does the approval queue row exist? Does `_create_material_request` get called?

3. Read source for `hrms/api/store.py:submit_order` and any `_create_material_request` helper. Look for branches that silently no-op for specific stores (e.g., a hardcoded skip-list, a missing canonical row, or a Material-Issue MR type guard that doesn't match these 2 stores).
   
   **HARD STOP (resolver immutability):** if the trace evidence OR the code reading points at `resolve_store_buyer_entity`, `resolve_warehouse_company`, `_STORE_TO_CHILD`, or any function in `scripts/canonical/`: STOP. These are canonical resolvers, frozen since S196 per `docs/STORE_COMPANY_CANONICAL.md`. Modifications require explicit CEO approval. Present findings to Sam in a separate `output/s223/verification/canonical_resolver_finding.md` document and do NOT modify the resolver. Phase 4 cannot proceed in its current scope; either Sam approves a resolver edit (then plan is amended for S224), or Sam approves working around the resolver (rare — usually means the bug is upstream).

4. Cross-reference with S196 / S190 store-naming history — NAIA T3 and ORTIGAS ESTANCIA are franchise stores under franchise companies; check whether their canonical Customer / Warehouse / Company chain is intact via `scripts/verify_canonical_structure.py` results.

5. Implement the backend fix in `hrms/api/store.py`. **MUST_MODIFY** the function the Phase 4.2 probe identified.

6. Add Sentry observability. **HARD BLOCKER:** the live `submit_order` already calls `set_backend_observability_context(module="ordering", ...)`. Do NOT change `module=` to a new string — that fragments existing Sentry dashboards. Preserve the existing `module="ordering"` and only ensure the call is present:
    ```python
    set_backend_observability_context(
        module="ordering",      # MUST match existing live value — verify with: rg 'module=' hrms/api/store.py
        action="submit_order",
        mutation_type="create",
    )
    ```

7. Manual re-verify in real browser for both stores. Submit fresh order → walk through approve → confirm MR created. Capture screenshots.

8. **Regression check against 5 currently-working stores.** Because `hrms/api/store.py:submit_order` is used by all 49 stores, a Phase 4 fix could accidentally break stores that were already working. Before declaring Phase 4 done, the agent MUST submit one fresh test order from each of these 5 currently-working stores spanning different parent companies and source warehouses:
   - **ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC** (PINNACLE source, TUNGSTEN parent)
   - **SM TANZA - BEBANG MEGA INC.** (PINNACLE source, BEBANG MEGA parent)
   - **SM MEGAMALL - HFFM SOLENAD FOOD SERVICES INC.** (PINNACLE source, HFFM parent)
   - **AYALA EVO - BEBANG ENTERPRISE INC.** (3MD source, BEBANG ENTERPRISE parent)
   - **THE GRID ROCKWELL - TASTECARTEL CORP.** (PINNACLE source, TASTECARTEL parent)
   
   Confirm each store's order chain still works end-to-end (order → approve → dispatch → receive → SI) after the `submit_order` change.
   
   **HARD BLOCKER:** if ANY of these 5 working stores fails, immediately roll back per task 10 below — do NOT proceed to Phase 5.

9. Cleanup all 5 regression-check test artifacts via `scripts/s209_cleanup_sweep.py` against a small ad-hoc ledger.

10. **Rollback procedure (HARD BLOCKER if invoked).** `hrms/api/store.py:submit_order` is canonical-critical (used by all 49 stores; breakage halts the entire ordering flow). Capture pre-fix baseline + define rollback steps:
    ```bash
    # Before applying the fix, capture baseline for instant revert
    git show origin/production:hrms/api/store.py > tmp/s223/submit_order_baseline.py
    git rev-parse origin/production > tmp/s223/baseline_commit.txt
    
    # If rollback needed (regression check fails OR Phase 7 sweep regresses on previously-passing stores):
    # 1. Revert just the Phase 4 commit on this branch:
    git revert <S223 Pattern C commit SHA> --no-edit
    git push origin s223-fix-l3-store-chain-product-bugs
    
    # 2. If already deployed: emergency redeploy from origin/production HEAD before Phase 4 merged
    #    (use /deploy-frappe with --force-revert flag, not present in current deploy script —
    #     so MUST be done by Sam manually; this is a STOP point.)
    ```
    **Post-deploy production monitoring (when Phase 4 lands):** the executing agent (or Sam during merge) MUST monitor the first 30 minutes of real production order submissions for regressions. Specifically:
    - Sentry `bei-hrms` project → filter `module:"ordering"` action `submit_order` → confirm error rate stays below baseline (< 1% of total submits)
    - Frappe Error Log: query `tabError Log` filtered by `method LIKE '%submit_order%'` for the last 30 minutes — expected 0 new errors
    - If error rate spikes OR any store other than NAIA T3 + ORTIGAS ESTANCIA reports a `submit_order` failure → invoke rollback per the steps above

11. Commit with message `fix(S223 Pattern C): <description of MR creation fix>`.

**MUST_MODIFY:** `hrms/api/store.py`
**MUST_CONTAIN (post-fix):** `set_backend_observability_context(module="ordering"` in `submit_order` (and any modified whitelisted helper). **Verify pre-edit:** `rg -n 'set_backend_observability_context' hrms/api/store.py` returns at least the existing call with `module="ordering"`.
**MUST_CONTAIN:** screenshots `pattern_c_naia_t3_after.png`, `pattern_c_ortigas_estancia_after.png`

**Phase 4 gate:**
```bash
python -c "
import pathlib, subprocess
diff = subprocess.check_output(['git', 'diff', '--name-only', 'origin/production', '--', 'hrms/api/store.py'], text=True).strip()
assert diff == 'hrms/api/store.py', f'expected hrms/api/store.py modified, got: {diff}'
content = pathlib.Path('hrms/api/store.py').read_text()
assert 'set_backend_observability_context' in content, 'Sentry context missing'
shots = list(pathlib.Path('output/s223/verification').glob('pattern_c_*_after.png'))
assert len(shots) >= 2, f'expected 2 Pattern C shots, got {len(shots)}'
print('PHASE 4 PASS')
"
```

## Phase 5 — ORTIGAS GREENHILLS TIN data fix + retroactive BIR §237 review (5 units)

**Goal:** resolve the only remaining canonical violation. Apply the TIN that already exists in the canonical company register to the billing Customer record, AND audit prior Sales Invoices posted to ORTIGAS GREENHILLS during the empty-TIN window for BIR §237 compliance.

**Pre-loaded fact (verified by S223 audit + Sam directive 2026-04-25):** Both TIN values belong to the same legal entity, **BEIFRANCHISE FOOD OPC** — only the suffix differs:
- `hrms/data_seed/company_register_2026-04-14.csv` row 38 → HQ TIN `688-721-280-00000` (BEIFRANCHISE FOOD OPC headquarters; suffix `-00000`)
- `data/ENTITY_TIN_RDO_2026-02-27.csv` row 49 → branch TIN `688-721-280-00001` (Ortigas Greenhills physical store, RDO 042; suffix `-00001`)

**Policy decision (Sam directive 2026-04-25): apply HQ TIN `688-721-280-00000` for now.** The auto-provision hook conflict (it currently writes branch TIN) is a **known follow-up** — but the hook only fires on NEW Company creation events, and ORTIGAS GREENHILLS Company already exists, so the conflict does not affect this specific record. A follow-up sprint can later align the auto-provision hook with this policy if needed.

**Tasks:**

1. Snapshot current Customer state (pre-touch backup):
    ```bash
    python scripts/s223_ortigas_snapshot.py > output/s223/verification/ortigas_customer_before.json
    ```

2. **Verify the HQ TIN value + document the policy decision:**
    ```bash
    # Confirm the HQ TIN value
    rg "BEIFRANCHISE FOOD OPC" hrms/data_seed/company_register_2026-04-14.csv
    # Expected: row 38 with TIN '688-721-280-00000'
    ```
    Write the policy memo to `output/s223/verification/ortigas_tin_policy.md`:
    ```markdown
    # ORTIGAS GREENHILLS TIN — Source-of-Truth Policy (S223)

    **Decision (Sam directive 2026-04-25):** apply HQ TIN `688-721-280-00000` to `Customer.tax_id`.

    **Both TINs belong to the same legal entity:**
    - HQ TIN `688-721-280-00000` — BEIFRANCHISE FOOD OPC headquarters (chosen, applied here)
    - branch TIN `688-721-280-00001` — Ortigas Greenhills physical location, RDO 042

    **Known follow-up (out of scope for S223):** existing auto-provision hook at `hrms/overrides/company.py:578` writes branch TIN to `Customer.tax_id` on new Company creation. This conflicts with the HQ-TIN policy chosen here. Mitigation:
    - The hook only fires on NEW Company creation events.
    - ORTIGAS GREENHILLS Company already exists, so the hook will not run for this record.
    - Future fix can either (a) update the hook to read HQ TIN, or (b) keep the hook as-is if BIR/Finance conclude branch TIN is the correct semantic.

    **Sources:**
    - `hrms/data_seed/company_register_2026-04-14.csv` row 38 — HQ TIN `688-721-280-00000` (chosen)
    - `data/ENTITY_TIN_RDO_2026-02-27.csv` row 49 — branch TIN `688-721-280-00001` (not applied here)
    ```

3. Apply via SSM script `scripts/s223_ortigas_apply_tin.py`:
    ```python
    # Actual script writes to tabCustomer (HQ TIN per Sam directive 2026-04-25)
    import frappe
    frappe.set_value(
        "Customer",
        "ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC",
        "tax_id",
        "688-721-280-00000",   # HQ TIN — see ortigas_tin_policy.md
    )
    frappe.db.commit()
    ```

4. Snapshot post-update:
    ```bash
    python scripts/s223_ortigas_snapshot.py > output/s223/verification/ortigas_customer_after.json
    ```

5. Re-run canonical verifier:
    ```bash
    python scripts/verify_canonical_structure.py > output/s223/verification/canonical_postcheck_phase5.txt 2>&1
    ```
    Expect: 0 violations.

6. **BIR §237 retroactive review.** Enumerate ALL Sales Invoices ever posted to `Customer = "ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC"` while `tax_id` was empty. These invoices were issued without a printed TIN on the customer side, which may require BIR §237 amendment, supplementary OR issuance, or simple re-print. Generate the audit list via SSM:
    ```python
    # scripts/s223_ortigas_si_audit.py
    import frappe, json
    rows = frappe.db.sql("""
        SELECT name, posting_date, grand_total, status
        FROM `tabSales Invoice`
        WHERE customer = 'ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC'
          AND docstatus = 1
        ORDER BY posting_date
    """, as_dict=True)
    json.dump(rows, open('output/s223/verification/ortigas_si_history.json', 'w'), default=str, indent=2)
    print(f"Found {len(rows)} SIs for ORTIGAS GREENHILLS posted with empty TIN")
    ```
    **HARD BLOCKER (Sam decision):** if the count is non-zero, do NOT auto-amend. Pause Phase 5 closeout, present the list to Sam, and let Finance/Denise decide whether to (a) accept retroactively (the new TIN propagates forward, prior SIs remain as-issued — only acceptable if no BIR audit exposure), (b) issue supplementary OR documents for each prior SI, or (c) cancel + re-issue each SI with the now-stamped TIN.
    
    **Resumption signal for autonomous agent:** Sam/Denise documents the decision in `output/s223/verification/ortigas_bir_237_decision.md` with the FIRST non-comment line in EXACTLY this format:
    ```
    DECISION: <APPLY_TIN | DEFER_TIN | CANCEL_AND_REISSUE | ISSUE_SUPPLEMENTARY_OR>
    Rationale: <one paragraph>
    Approved-by: <Sam | Denise>
    Approved-at: <UTC ISO>
    ```
    The autonomous agent reads this file. If the first non-comment line matches the regex `^DECISION: (APPLY_TIN|DEFER_TIN|CANCEL_AND_REISSUE|ISSUE_SUPPLEMENTARY_OR)$`, the agent acts on the decision and resumes. If the file is missing OR the first line doesn't match the regex, the agent pauses (no resumption — wait for next session). The agent does NOT proceed without an explicit decision token.

7. Manually verify in real browser: as test.area, submit a fresh order for ORTIGAS GREENHILLS, walk through approve → dispatch → receive → SI. Confirm the SI posts with the now-set TIN (no billing-hold, TIN visible on printed invoice). Capture screenshot → `output/s223/verification/ortigas_greenhills_si_posted.png`.

8. **Deferred-skip fallback (only if task 2 blocker fires):** if the registry TIN is flagged stale/under-review and Finance can't confirm a current TIN at this phase deadline, mark the store as `Allowed Skip` for this sprint and proceed. The sprint passes at 48/49 with this 1 documented skip. Record reason in `output/s223/RUN_STATUS.json`:
    ```json
    {"ortigas_tin_deferred": true, "ortigas_tin_deferred_reason": "<exact reason — e.g., 'Finance flagged registry TIN under BIR review pending RDO transfer'>"}
    ```

**Phase 5 gate (TIN applied path):**
```bash
python -c "
import json, pathlib, re
before = json.load(open('output/s223/verification/ortigas_customer_before.json'))
after = json.load(open('output/s223/verification/ortigas_customer_after.json'))
assert before['tax_id'] in (None, ''), 'before tax_id should be empty'
TIN_REGEX = r'^\d{3}-\d{3}-\d{3}-\d{5}$'
assert re.match(TIN_REGEX, after['tax_id'] or ''), f'after tax_id must match BIR format ###-###-###-#####, got: {after[\"tax_id\"]}'
assert after['tax_id'] == '688-721-280-00000', f'expected HQ TIN per Sam directive 2026-04-25, got: {after[\"tax_id\"]}'
assert pathlib.Path('output/s223/verification/ortigas_tin_policy.md').exists(), 'policy memo missing'
post = pathlib.Path('output/s223/verification/canonical_postcheck_phase5.txt').read_text()
assert 'Violations: 0' in post, 'expected 0 canonical violations after TIN fill'
assert pathlib.Path('output/s223/verification/ortigas_greenhills_si_posted.png').exists()
si_history = json.load(open('output/s223/verification/ortigas_si_history.json'))
if si_history:
    assert pathlib.Path('output/s223/verification/ortigas_bir_237_decision.md').exists(), \\
        f'BIR §237 decision required: {len(si_history)} SIs posted with empty TIN'
print('PHASE 5 PASS (TIN applied)')
"
```

**Phase 5 gate (deferred-skip path):**
```bash
python -c "
import json, pathlib
status = json.load(open('output/s223/RUN_STATUS.json'))
assert 'ortigas_tin_deferred' in status and status['ortigas_tin_deferred'] == True
assert 'ortigas_tin_deferred_reason' in status and len(status['ortigas_tin_deferred_reason']) > 20
print('PHASE 5 PASS (TIN deferred — sprint closes at 48/49)')
"
```

## Phase 6 — Remove S221 + S222 test fallbacks (3 units)

**Goal:** the L3 test library no longer contains REST/API workflow shortcuts. Tests use only browser-driven flows.

> **Sequencing note (per S223 audit):** this phase runs AFTER Phase 7A (sweep WITH fallbacks present, validates fixes work in parallel) and BEFORE Phase 7B (sweep WITHOUT fallbacks, validates UI-only success). See Phase 7A/7B reorder below.

**Tasks:**

> **PRECISION NOTE (per S223 audit pass-2 P2-3):** the original B3 grep gate was over-broad — it would false-positive on ~25 legitimate post-click verification calls in `WarehouseApprovalPage:59`, `ReceivingPage:156`, and 4 other Page Objects. Those calls READ state AFTER a UI click landed, to confirm the click had effect — they are not REST shortcuts. The narrowed gate below targets only S221/S222-specific call shapes (pre-click bypass) plus the universal page.request/fetch ban.

1. Revert S221 REST approval fallback in `bei-tasks/tests/e2e/pages/OrderApprovalPage.ts`:
   - Remove the REST POST to `/api/method/hrms.api.store.approve_order` and the surrounding fallback logic
   - Keep only the original UI click + waitFor logic
   - **MUST_NOT** contain any `page.request.*`, `fetch(/api/method`, OR pre-click readback (`getReadbackCtx`/`queryDocs`/`readDoc` called BEFORE the UI button click that drives the workflow). Post-click verification readbacks are PERMITTED if marked with the `// VERIFICATION-POST-UI:` comment convention (see task 5).

2. Revert S222 SE-existence fallback in `bei-tasks/tests/e2e/pages/DispatchPage.ts`:
   - Remove the `Stock Entry Detail` query in the dispatch poll path
   - Specifically search for `queryDocs.*Stock Entry Detail` or `readDoc.*Stock Entry` — those are the S222 patterns
   - Keep only the original `MR.per_transferred > 0` / status-set check
   - The Pattern A fix in Phase 2B should make this work without the fallback

3. **Audit existing legitimate post-click verification calls** in other Page Objects. Verified by S223 audit pass-2 to exist:
   - `WarehouseApprovalPage.ts:59` — calls `readDoc` AFTER click to verify approval state transition (KEEP)
   - `ReceivingPage.ts:156` — calls `readDoc` AFTER click to verify WR status (KEEP)
   - `OrderApprovalPage.ts:39` — pre-click bypass shortcut (BAN — this is the S221 leak; should be removed in task 1)
   - 4+ more legitimate post-click usages in `InvoicePage`, `PaymentRequestPage`, `PurchaseOrderPage`, etc.
   For each legitimate post-click call, add a `// VERIFICATION-POST-UI: <reason>` comment one line above. Example:
   ```typescript
   await this.page.locator('button:has-text("Approve")').click();
   // VERIFICATION-POST-UI: confirm MR transitioned to Ordered after click
   const mr = await readDoc("Material Request", mrName);
   ```

4. Run the discipline grep — narrowed pattern (catches only S221/S222-specific call shapes + universal page.request/fetch ban):
    ```bash
    cd F:/Dropbox/Projects/bei-tasks-s223-fix-l3-store-chain-product-bugs
    
    # Universal pre-click bypass shortcuts (BANNED everywhere)
    rg -n 'page\.request\.(post|put|delete|patch)|page\.context\(\)\.request\.|fetch\(.*api/method' tests/e2e/pages/
    
    # S221/S222 fallback patterns specifically (BANNED)
    rg -n 'getReadbackCtx\(\)\.post\(|queryDocs\([^)]*Stock Entry Detail|hrms\.api\.store\.approve_order' tests/e2e/pages/
    
    # Pre-click readback (BANNED) — readback that happens BEFORE a UI click in the same method
    # Manual review: any `getReadbackCtx`/`queryDocs`/`readDoc` call NOT preceded by a `// VERIFICATION-POST-UI:` comment within 5 lines is a violation.
    ```
    Expected: zero hits from rg commands. Manual review confirms every readback call is paired with a `// VERIFICATION-POST-UI:` comment.

5. Commit with `chore(S223 cleanup): remove S221+S222 test-side REST/readback fallbacks — fixes shipped in product code; legitimate post-click verifications kept and marked`.

**MUST_MODIFY:**
- `bei-tasks/tests/e2e/pages/OrderApprovalPage.ts`
- `bei-tasks/tests/e2e/pages/DispatchPage.ts`
- Plus `// VERIFICATION-POST-UI:` comment markers in `WarehouseApprovalPage.ts`, `ReceivingPage.ts`, and any other Page Object retaining legitimate post-click readback (5+ files)

**MUST_NOT_CONTAIN (post-revert):**
- `page.request.post('/api/method/...store.approve_order` anywhere in `tests/e2e/pages/`
- `queryDocs(...Stock Entry Detail` anywhere in `tests/e2e/pages/`
- Pre-click readback in `OrderApprovalPage.ts` (was line 39 — S221 fallback)
- Any `getReadbackCtx`/`queryDocs`/`readDoc` call NOT marked with `// VERIFICATION-POST-UI:` comment

**Phase 6 gate (precision-narrowed):**
```bash
cd F:/Dropbox/Projects/bei-tasks-s223-fix-l3-store-chain-product-bugs
python -c "
import pathlib, re, subprocess

op = pathlib.Path('tests/e2e/pages/OrderApprovalPage.ts').read_text()
dp = pathlib.Path('tests/e2e/pages/DispatchPage.ts').read_text()

# S221 REST fallback removed
assert 'approve_order' not in op or 'page.request' not in op[op.find('approve_order')-200:op.find('approve_order')+200] if op.find('approve_order') >= 0 else True, 'S221 REST fallback still present'

# S222 SE-existence fallback removed
assert 'Stock Entry Detail' not in dp, 'S222 SE-existence fallback still present'

# Universal bypass shortcuts banned (rg-style)
banned_universal = subprocess.run(
    ['rg', '-n', r'page\.request\.(post|put|delete|patch)|fetch\(.*api/method', 'tests/e2e/pages/'],
    capture_output=True, text=True
).stdout
assert banned_universal.strip() == '', f'universal pre-click bypass present:\\n{banned_universal}'

# S221/S222-specific patterns banned
banned_specific = subprocess.run(
    ['rg', '-n', r'getReadbackCtx\(\)\.post\(|queryDocs\([^)]*Stock Entry Detail|hrms\.api\.store\.approve_order', 'tests/e2e/pages/'],
    capture_output=True, text=True
).stdout
assert banned_specific.strip() == '', f'S221/S222 fallback patterns still present:\\n{banned_specific}'

# All legitimate readbacks must have VERIFICATION-POST-UI marker
readbacks = subprocess.run(
    ['rg', '-n', '-B', '2', r'getReadbackCtx\(|queryDocs\(|readDoc\(', 'tests/e2e/pages/'],
    capture_output=True, text=True
).stdout
unmarked = [chunk for chunk in readbacks.split('--') if 'VERIFICATION-POST-UI' not in chunk and chunk.strip()]
assert not unmarked, f'readbacks without VERIFICATION-POST-UI marker:\\n{unmarked[:3]}'

print('PHASE 6 PASS — UI-only discipline enforced; legitimate post-click verifications preserved')
"
```

**Helper file fate:** `bei-tasks/tests/e2e/support/frappeReadback.ts` STAYS — it has 5+ legitimate post-click verification users. Phase 6 does NOT delete the file. Workflow methods MUST NOT call its functions BEFORE a UI click; only AFTER, with a `// VERIFICATION-POST-UI:` comment.

## Phase 7A — Verification sweep WITH fallbacks present (5 units)

> **Sequencing rationale (per S223 audit B11):** N=1 per-store manual verification in Phase 2B/3B/4 cannot predict N=49 parallel sweep behavior. Run a sweep BEFORE removing the fallbacks to confirm Phase 2-4 fixes work in parallel. Then Phase 6 reverts the fallbacks. Then Phase 7B re-runs the sweep UI-only. If Phase 7A passes but 7B regresses, the regression is isolated to fallback-removal effects (likely test flakiness) — not a Phase 2-4 fix bug.

**Goal:** confirm Phase 2-4 fixes hold up under parallel test execution while the S221+S222 fallbacks are still present as a safety net.

**Tasks:**

1. Pre-sweep canonical preflight:
    ```bash
    python scripts/verify_canonical_structure.py > output/s223/verification/canonical_preflight_phase7a.txt 2>&1
    ```

2. Reset L3 evidence dir + ledger:
    ```bash
    rm -f output/l3/s223/sweep_full_run_7a.log output/l3/s223/sweep.pid output/l3/s223/monitor_decisions_7a.log
    echo "[]" > output/l3/s223/sweep_ledger_7a.json
    ```

3. Grant test.area access to all 49 warehouses (idempotent):
    ```bash
    python scripts/s209_grant_test_area_access.py
    ```

4. **Capture sweep window start UTC** (per S223 audit pass-2 P2-7 — required for non-overlapping cleanup window between 7A and 7B):
    ```bash
    export SWEEP_7A_START_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "$SWEEP_7A_START_UTC" > output/s223/verification/sweep_7a_start.txt
    ```

5. Launch monitored sweep with the S221+S222 fallbacks STILL IN PLACE (Phase 6 has not yet run):
    ```bash
    export FRAPPE_API_KEY="$(doppler secrets get FRAPPE_API_KEY --plain --project bei-erp --config dev)"
    export FRAPPE_API_SECRET="$(doppler secrets get FRAPPE_API_SECRET --plain --project bei-erp --config dev)"
    export BEI_ERP_ROOT="F:/Dropbox/Projects/BEI-ERP-s223-fix-l3-store-chain-product-bugs"
    export S209_EVIDENCE_ROOT="$BEI_ERP_ROOT/output/l3/s223"
    export EVIDENCE_ROOT="$BEI_ERP_ROOT/output/l3/s223"
    
    python scripts/s212_launch_sweep.py \
      --spec tests/e2e/specs/s209-all-stores.spec.ts \
      --log output/l3/s223/sweep_full_run_7a.log \
      --pid-file output/l3/s223/sweep.pid \
      --ledger output/l3/s223/sweep_ledger_7a.json \
      --decision-log output/l3/s223/monitor_decisions_7a.log \
      --kill-same-fingerprint 5 \
      --kill-pass-rate-below 0.85 \
      --kill-pass-rate-after-n 20
    
    # After sweep exits, capture end UTC for the cleanup window pair
    export SWEEP_7A_END_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "$SWEEP_7A_END_UTC" > output/s223/verification/sweep_7a_end.txt
    ```
    Expected wallclock: 55–75 min.

5. Classify results using S222's classifier (output to `output/l3/s223/classification_7a.json`).

6. **Phase 7A outcome decision matrix (per S223 audit pass-2 P2-9 — 47/49 boundary split into 3 sub-cases):**

    | Result | Sub-case classification (read trace for failing store) | Action |
    |---|---|---|
    | 48/49 or 49/49 PASS | n/a | Phase 2-4 fixes work in parallel. Proceed to Phase 6 (revert fallbacks). |
    | 47/49 — failing store NOT in original 13 | "NEW pattern" — a store that was passing in S221+S222 baseline now fails despite the Phase 2-4 fixes | Real product bug surfaced. Read trace, classify pattern, decide whether to fix in this sprint OR file as Phase 9 follow-up. STOP fallback removal until disposition. |
    | 47/49 — failing store IS in original 13 | "Phase 2-4 fix gap" — a store the plan was supposed to fix is still failing | Phase 2-4 fix was incomplete for that store under parallel load. Re-investigate that store specifically. Fix before proceeding to Phase 6. |
    | 47/49 — failing store was previously-PASSING in S221 (not in original 13) | "Regression candidate" — the Phase 2-4 changes introduced a regression | Read trace. If the regression is product-side, fix it. STOP — do NOT proceed to Phase 6 since fallback removal would compound the regression. |
    | 46/49 — exactly 2 unexpected failures | Mixed — could be combinations of above | Trace each. Apply the decision rule per failing store. STOP fallback removal. |
    | <46/49 | Multiple unexpected failures | STOP. The Phase 2-4 fixes have systemic parallel-execution defects beyond what single-store verification revealed. Re-investigate before removing fallbacks. Do NOT proceed to Phase 6. Roll back if needed. |

7. Cleanup all 7A sweep test artifacts:
    ```bash
    python scripts/s209_cleanup_sweep.py --ledger output/l3/s223/sweep_ledger_7a.json
    # Pass UTC start AND end timestamps captured at sweep launch + exit (per S223 audit pass-2 P2-7)
    python scripts/s223_final_cleanup_probe.py --window-start "$SWEEP_7A_START_UTC" --window-end "$SWEEP_7A_END_UTC"  # Phase 7A residue only
    echo "[]" > output/l3/s223/sweep_ledger_7a.json
    ```

8. Post-sweep canonical verifier — must equal preflight:
    ```bash
    python scripts/verify_canonical_structure.py > output/s223/verification/canonical_postcheck_phase7a.txt 2>&1
    diff <(grep -v "CommandId:" output/s223/verification/canonical_preflight_phase7a.txt) \
         <(grep -v "CommandId:" output/s223/verification/canonical_postcheck_phase7a.txt)
    ```
    Expected: empty diff.

**Phase 7A gate:**
```bash
python -c "
import json, pathlib
ledger = json.load(open('output/l3/s223/sweep_ledger_7a.json'))
assert ledger == [], 'sweep ledger 7a not reset to []'
import re
classification = json.load(open('output/l3/s223/classification_7a.json'))
pass_count = classification.get('PASS', 0)
assert pass_count >= 47, f'Phase 7A expected >=47 PASS (with fallbacks), got {pass_count}'
post = pathlib.Path('output/s223/verification/canonical_postcheck_phase7a.txt').read_text()
assert 'Violations: 0' in post or ('Violations: 1' in post and 'BILLING_CUST_TIN_EMPTY' in post), 'unexpected canonical violations'
print(f'PHASE 7A PASS — {pass_count}/49 with fallbacks')
"
```

> **Note:** Phase 6 (remove S221+S222 fallbacks) runs AFTER Phase 7A passes. Then Phase 7B (UI-only sweep) is the final validation.

## Phase 7B — UI-only verification sweep (final), expect 48/49 PASS (5 units)

> **Runs AFTER Phase 6 (fallback removal).** The S221 REST approval fallback and S222 SE-existence dispatch fallback are now gone. This sweep proves Phase 2-4 fixes are complete and self-sufficient — same path real users take.

**Goal:** prove all 49 stores complete the chain through the real UI with zero REST shortcuts. Target: 48/49 (49/49 minus the allowed skip if Phase 5 deferred ORTIGAS TIN; 49/49 if applied).

**Tasks:**

1. Pre-sweep canonical preflight:
    ```bash
    python scripts/verify_canonical_structure.py > output/s223/verification/canonical_preflight_phase7b.txt 2>&1
    ```

2. Reset L3 evidence dir + ledger:
    ```bash
    rm -f output/l3/s223/sweep_full_run.log output/l3/s223/sweep.pid output/l3/s223/monitor_decisions.log
    echo "[]" > output/l3/s223/sweep_ledger.json
    ```

3. Grant test.area access to all 49 warehouses (idempotent):
    ```bash
    python scripts/s209_grant_test_area_access.py
    ```

4. **Capture sweep window start UTC** (per S223 audit pass-2 P2-7):
    ```bash
    export SWEEP_7B_START_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "$SWEEP_7B_START_UTC" > output/s223/verification/sweep_7b_start.txt
    ```

5. Launch monitored sweep — fallbacks now removed:
    ```bash
    export FRAPPE_API_KEY="$(doppler secrets get FRAPPE_API_KEY --plain --project bei-erp --config dev)"
    export FRAPPE_API_SECRET="$(doppler secrets get FRAPPE_API_SECRET --plain --project bei-erp --config dev)"
    export BEI_ERP_ROOT="F:/Dropbox/Projects/BEI-ERP-s223-fix-l3-store-chain-product-bugs"
    export S209_EVIDENCE_ROOT="$BEI_ERP_ROOT/output/l3/s223"
    export EVIDENCE_ROOT="$BEI_ERP_ROOT/output/l3/s223"
    
    python scripts/s212_launch_sweep.py \
      --spec tests/e2e/specs/s209-all-stores.spec.ts \
      --log output/l3/s223/sweep_full_run.log \
      --pid-file output/l3/s223/sweep.pid \
      --ledger output/l3/s223/sweep_ledger.json \
      --decision-log output/l3/s223/monitor_decisions.log \
      --kill-same-fingerprint 5 \
      --kill-pass-rate-below 0.85 \
      --kill-pass-rate-after-n 20
    
    export SWEEP_7B_END_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "$SWEEP_7B_END_UTC" > output/s223/verification/sweep_7b_end.txt
    ```
    Expected wallclock: 55–75 min.

5. Classify results using S222's classifier (output to `output/l3/s223/classification.json`).

6. **Phase 7B outcome decision matrix:**

    | Result | Action |
    |---|---|
    | 48/49 PASS (or 49/49 if TIN applied) | Proceed to Phase 8 closeout |
    | 47/49 PASS — exactly 1 unexpected failure | Read trace for failing store. If test flake, re-run that single store via `--grep`; if real bug, add as Phase 9 follow-up issue. Sam decides whether to merge at 47/49 or hold. |
    | 46/49 PASS — 2+ unexpected failures | STOP. Diff vs Phase 7A: which stores newly failed? They are the test-discipline-exposed stores. Trace each, decide whether (a) Phase 2-4 fixes were incomplete, OR (b) the fallback was hiding test-side flake. Do NOT re-add the fallbacks. |
    | <46/49 PASS | STOP. Major regression. Roll back the worktree to phase commits. Sam reviews. |

7. Cleanup:
    ```bash
    python scripts/s209_cleanup_sweep.py --ledger output/l3/s223/sweep_ledger.json
    # Phase 7B residue only — non-overlapping window with 7A
    python scripts/s223_final_cleanup_probe.py --window-start "$SWEEP_7B_START_UTC" --window-end "$SWEEP_7B_END_UTC"
    echo "[]" > output/l3/s223/sweep_ledger.json
    ```

8. Post-sweep canonical verifier:
    ```bash
    python scripts/verify_canonical_structure.py > output/s223/verification/canonical_postcheck_phase7.txt 2>&1
    diff <(grep -v "CommandId:" output/s223/verification/canonical_preflight_phase7b.txt) \
         <(grep -v "CommandId:" output/s223/verification/canonical_postcheck_phase7.txt)
    ```
    Expected: empty diff.

9. Write `output/l3/s223/SWEEP_VERIFICATION_SUMMARY.md` (mirror S221 / S222 closeout structure):
    - Final pass count from BOTH 7A (with fallbacks) and 7B (without)
    - Pattern-by-pattern resolution status
    - Canonical zero-drift confirmation
    - Comparison to S209/S221/S222 trajectory

**MUST_CONTAIN:**
- `output/l3/s223/sweep_ledger.json` reset to `[]`
- `output/l3/s223/SWEEP_VERIFICATION_SUMMARY.md` with both 7A and 7B tallies
- `output/s223/verification/canonical_postcheck_phase7.txt` with `Violations: 0` (or `Violations: 1` only if ORTIGAS TIN deferred)

**MUST_NOT:**
- Re-run the 7B sweep more than 2 times. If 2 7B sweeps don't yield ≥48/49, STOP and ask Sam.
- Re-add the S221/S222 fallbacks during 7B troubleshooting. The fallback removal is permanent.

**Phase 7B gate:**
```bash
python -c "
import json, pathlib
ledger = json.load(open('output/l3/s223/sweep_ledger.json'))
assert ledger == [], 'sweep ledger not reset to []'
summary = pathlib.Path('output/l3/s223/SWEEP_VERIFICATION_SUMMARY.md').read_text()
assert 'PASS' in summary
# Parse final pass count (Phase 7B) from summary
import re
m = re.search(r'(\\d+)/49.*?(?:Phase 7B|UI-only|final)', summary, re.IGNORECASE)
assert m, 'Phase 7B pass count missing in summary'
pass_count = int(m.group(1))
assert pass_count >= 48, f'Phase 7B expected >=48 (UI-only), got {pass_count}'
post = pathlib.Path('output/s223/verification/canonical_postcheck_phase7.txt').read_text()
assert 'Violations: 0' in post or ('Violations: 1' in post and 'BILLING_CUST_TIN_EMPTY' in post), 'unexpected canonical violations'
print(f'PHASE 7B PASS — {pass_count}/49 UI-only')
"
```

## Phase 8 — Closeout (6 units)

**Goal:** finalize plan + registry, create PRs, remove worktrees.

**Tasks:**

1. Update plan YAML frontmatter — set `status: COMPLETED`, `completed_date: <UTC>`, populate `execution_summary` with final pass count + which patterns shipped.

2. Update `docs/plans/SPRINT_REGISTRY.md` S223 row — change `PLANNED 2026-04-25` to `COMPLETED <YYYY-MM-DD>`, fill PR numbers in the PR column.

3. Commit plan + registry + L3 evidence to hrms worktree branch. **HARD BLOCKER:** the bei-release-manager gate will reject the PR unless `output/l3/s223/` and `output/s223/` evidence files are committed to the branch (per audit-skill S027 rule 3b). Both `docs/` and `output/` are in `.gitignore`, so `-f` is required:
    ```bash
    cd F:/Dropbox/Projects/BEI-ERP-s223-fix-l3-store-chain-product-bugs
    git add -f docs/plans/2026-04-25-sprint-223-fix-l3-store-chain-product-bugs.md
    git add -f docs/plans/SPRINT_REGISTRY.md
    git add -f output/s223/
    git add -f output/l3/s223/
    git status --short  # verify all four roots are staged
    git commit -m "chore(S223): closeout — plan + registry + L3 evidence"
    ```
    **Verify before push:** `git ls-tree HEAD -- output/l3/s223/` must return ≥3 entries (sweep_full_run.log, sweep_ledger.json, SWEEP_VERIFICATION_SUMMARY.md). Same for `output/s223/` (DEFECT_REGISTER.md, SUMMARY.md, RUN_STATUS.json, RUN_SUMMARY.md, verification/).

4. Push both branches:
    ```bash
    cd F:/Dropbox/Projects/BEI-ERP-s223-fix-l3-store-chain-product-bugs
    git push -u origin s223-fix-l3-store-chain-product-bugs
    
    cd F:/Dropbox/Projects/bei-tasks-s223-fix-l3-store-chain-product-bugs
    git push -u origin s223-fix-l3-store-chain-product-bugs
    ```

5. Create PRs (one per repo):
    ```bash
    GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms \
      --base production --head s223-fix-l3-store-chain-product-bugs \
      --title "fix(S223): all remaining L3 store-chain failures via real product fixes — 48/49 (or 49/49)" \
      --body "$(cat output/s223/SUMMARY.md)"
    
    GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/BEI-Tasks \
      --base main --head s223-fix-l3-store-chain-product-bugs \
      --title "fix(S223): real product fixes for L3 store-chain — Pattern A/B/DEFECT-11 + remove S221/S222 fallbacks" \
      --body "$(cat output/s223/SUMMARY.md)"
    ```

6. Share PR numbers with Sam, **explicitly stating the merge order:**
   - **hrms PR merges FIRST** (Pattern C backend `submit_order` fix lands; ORTIGAS TIN data fix lands).
   - **bei-tasks PR merges AFTER hrms deploy succeeds and is L1-smoke-confirmed by Sam.** Frontend Pattern A/B/DEFECT-11 fixes depend on the backend Pattern C fix being live; merging bei-tasks first would deploy frontend code calling a backend `submit_order` that hasn't yet been patched for NAIA T3 + ORTIGAS ESTANCIA.
   - If Sam merges bei-tasks first by mistake: not catastrophic (Pattern A/B/DEFECT-11 are independent of Pattern C for the OTHER 47 stores), but NAIA T3 + ORTIGAS ESTANCIA would still fail until hrms ships.
   
   **STOP.** Do NOT merge. Sam reviews and merges in the documented order.

7. Worktree removal:
    ```bash
    # Verify each worktree is clean
    cd F:/Dropbox/Projects/BEI-ERP-s223-fix-l3-store-chain-product-bugs && git status --short  # must be empty
    cd F:/Dropbox/Projects/bei-tasks-s223-fix-l3-store-chain-product-bugs && git status --short  # must be empty
    
    cd F:/Dropbox/Projects/BEI-ERP
    git worktree remove F:/Dropbox/Projects/BEI-ERP-s223-fix-l3-store-chain-product-bugs
    
    cd F:/Dropbox/Projects/bei-tasks
    git worktree remove F:/Dropbox/Projects/bei-tasks-s223-fix-l3-store-chain-product-bugs
    ```

8. Confirm worktree list is back to baseline (no s223 entries).

**Phase 8 gate:**
```bash
python -c "
import json, subprocess
# 1. L3 evidence + s223 evidence committed to remote branch (release-manager gate prerequisite)
remote_files = subprocess.check_output(
    ['git', 'ls-tree', '-r', '--name-only', 'origin/s223-fix-l3-store-chain-product-bugs'],
    text=True
).splitlines()
must_have_on_remote = [
    'output/l3/s223/sweep_full_run.log',
    'output/l3/s223/sweep_ledger.json',
    'output/l3/s223/SWEEP_VERIFICATION_SUMMARY.md',
    'output/s223/DEFECT_REGISTER.md',
    'output/s223/SUMMARY.md',
    'output/s223/RUN_STATUS.json',
]
missing = [p for p in must_have_on_remote if p not in remote_files]
assert not missing, f'L3/s223 evidence NOT on remote branch — bei-release-manager will reject: {missing}'
# 2. Worktrees removed
worktrees = subprocess.check_output(['git', '-C', 'F:/Dropbox/Projects/BEI-ERP', 'worktree', 'list'], text=True)
assert 's223' not in worktrees, 'hrms s223 worktree still present'
worktrees_bt = subprocess.check_output(['git', '-C', 'F:/Dropbox/Projects/bei-tasks', 'worktree', 'list'], text=True)
assert 's223' not in worktrees_bt, 'bei-tasks s223 worktree still present'
print('PHASE 8 PASS')
"
```

## L3 Workflow Scenarios

The Phase 7A and Phase 7B sweeps automatically run all 49 store scenarios via `tests/e2e/specs/s209-all-stores.spec.ts`. Phase 7A runs WITH the S221+S222 fallbacks present (validates Phase 2-4 fixes parallel-safe); Phase 7B runs AFTER Phase 6 reverts those fallbacks (validates UI-only success — same path real users take). The per-store scenario template:

| User | Action | Expected Outcome | Failure Means |
|---|---|---|---|
| `test.area@bebang.ph` | Submit DRY order via `/dashboard/store-ops/ordering` for store X with 3 items, qty cap 5 each | Order docname appears in approval queue; `BEI Store Order` row created with status `Pending Approval` | Submit endpoint broken or store fixture wrong |
| `test.area@bebang.ph` | Approve own area-side via `/dashboard/store-ops/order-approvals` clicking Approve | Order moves to `Pending Warehouse Approval`; queue entry exists for SCM | DEFECT-11 (Order Approval narrowing) — Phase 3B verifies fix |
| `test.scm@bebang.ph` | Approve warehouse-side via `/dashboard/warehouse/approve` clicking Approve All | MR docname appears with status `Ordered` | Pattern B (Warehouse Approval narrowing) — Phase 3B verifies fix |
| `test.scm@bebang.ph` | Dispatch via `/dashboard/warehouse/dispatch` clicking Create Transfer (outer + inner buttons) | Stock Entry created (visible in /app/stock-entry); MR per_transferred bumps OR status moves to Issued; success toast appears | Pattern A (Dispatch modal stuck) — Phase 2B verifies fix |
| `test.receiver@bebang.ph` | Receive via `/dashboard/warehouse/internal-receiving/<WR>` clicking Receive Items | BEI Warehouse Receiving row submitted with status `Completed`; MR moves to `Received`; SI auto-posts | S203 SI auto-post chain (already shipped) |
| `test.area@bebang.ph` | Verify SI exists at `/dashboard/billing` for the store | Sales Invoice with the canonical billing Customer; correct legal_entity per S196 | Canonical resolver issue — out of scope for S223 |

## Library Audit & Contributions

**Library audit (Phase 0 task):** documented in `output/s223/library_audit.md`.

**Library contributions** (NEW Page Object methods or fixtures S223 adds):

- `OrderApprovalPage.approve(orderId)` — REVERTED to UI-only (S221 REST fallback removed)
- `DispatchPage.dispatch(mrName)` — REVERTED to UI-only (S222 SE-existence fallback removed); poll relies on the Pattern A fix
- `WarehouseApprovalPage.approve(mrName)` — extended to handle the post-Pattern-B-fix queue rendering (no REST, just UI)
- New fixture: `freshOrderForStore(store_name)` — sets up a clean order via real UI for any of the 49 stores; reused across Phase 2A/3A/4 manual reproductions and the verification sweeps

Each becomes a first-class deliverable. Future sprints inherit them via the existing fixture system.

**Three-uses rule:** the `manual real-browser reproduction` flow is used in Phase 2A, 3A, 4, and 5. If a 5th use shows up, extract a `repro/<pattern>.repro.ts` script.

## Failure Response

Each pattern's failure mode and the response:

- **Mode A (app bug):** if Phase 2B/3B/4 verification screenshot shows the failure persisting → STOP, re-investigate, do NOT touch test code. The fix is wrong.
- **Mode B (test bug):** if Phase 7A or 7B sweep shows a previously-passing store fails after a Phase 2-4 fix → STOP, read trace, re-investigate. May require a Page Object update (real-UI-driven) but NEVER a fetch/REST shortcut.
  - 7A failure that 2B/3B/4 manual verify did not catch → real Phase 2-4 fix gap. Fix the product code, do NOT touch tests.
  - 7B failure that 7A passed → fallback removal exposed test flakiness; debug the Page Object's real-UI flow, do NOT re-add the fallback.
- **Mode C (brittleness):** if Phase 7 shows ≥3 stores failing the same way that worked in manual repro → likely test parallelism timing. Fix the LIBRARY (Page Object timing/selectors), NOT the spec. NEVER `waitForTimeout` or `retry(3)` masking.

If ≥3 library fixes happen during execution, emit `output/l3/s223/LIBRARY_IMPROVEMENTS.md` (mirroring `output/l3/retrospective/LIBRARY_IMPROVEMENTS.md` structure).

## Zero-Skip Enforcement

**Forbidden agent behaviors:**
- Skipping a task silently
- Marking partial work as "done"
- Replacing a real fix with a test-side workaround
- Adding any `page.request.post(/api/method/...)` to a Page Object workflow path
- Inventing a TIN for ORTIGAS GREENHILLS without Finance authority
- "Deferred to next sprint" for any of the 4 patterns
- Skipping per-store manual verification in Phase 2B/3B/4

**Phase Completion Checklist** (agent fills after each phase, in `output/s223/PHASE_CHECKLIST.md`):

```markdown
| Phase | Task | Status | Evidence path | Skipped? | If skipped, why? |
|---|---|---|---|---|---|
| 0 | Boot + worktrees + canonical preflight | DONE / SKIPPED / IN PROGRESS | output/s223/verification/canonical_preflight.txt | NO/YES | <reason> |
| 1 | DEFECT_REGISTER for 13 stores | ... | output/s223/DEFECT_REGISTER.md | ... | ... |
| ... 9 phases × ~2-4 tasks each ... |
```

**PR description gate:** PRs from this sprint must include the full task-by-task checklist as a top-level `## S223 Phase Status` section. Unchecked items need an explanation. Sam rejects PRs with unexplained gaps.

## Status Reconciliation Contract

When pass count, blocker, or phase status changes, update IN THE SAME COMMIT:

1. `output/s223/RUN_STATUS.json`
2. `output/s223/RUN_SUMMARY.md`
3. `output/s223/DEFECT_REGISTER.md` (if pattern resolution changes)
4. plan YAML status field (only at sprint completion)
5. `docs/plans/SPRINT_REGISTRY.md` S223 row (only at sprint completion or major status change)

## Autonomous Execution Contract

- **completion_condition:**
  - Phase 7A sweep yields ≥47/49 PASS WITH fallbacks (proves Phase 2-4 fixes parallel-safe)
  - Phase 7B sweep yields ≥48/49 PASS via UI-only (no fallbacks; no `page.request.*`/`getReadbackCtx`/`queryDocs`/`readDoc`/`frappe.client.*` in `tests/e2e/pages/`)
  - canonical postcheck shows Violations: 0 (or 1 with documented ORTIGAS TIN-deferred)
  - DEFECT_REGISTER shows VERIFIED tags for all Pattern A/B/C/DEFECT-11 stores with screenshot evidence
  - Phase 4 regression check: 5 currently-working stores (ARANETA GATEWAY, SM TANZA, SM MEGAMALL, AYALA EVO, THE GRID ROCKWELL) still submit successfully after `submit_order` change
  - Phase 5 task 6 BIR §237 review documented (or zero prior SIs found) — `output/s223/verification/ortigas_si_history.json` exists
  - extended grep returns 0 hits: `rg 'page\.request|page\.context\(\)\.request|fetch\(|getReadbackCtx|queryDocs|readDoc|frappe\.client\.' tests/e2e/pages/`
  - L3 evidence + s223 evidence committed to remote branch (`git ls-tree origin/s223-... -- output/l3/s223/` non-empty)
  - both PRs created and PR numbers recorded
  - both worktrees removed

- **stop_only_for:**
  - Phase 5 task 2 — registry TIN flagged stale by Finance → mark deferred and continue (sprint passes at 48/49)
  - Phase 5 task 6 — non-zero prior-SI count without Sam's BIR §237 disposition → pause for Finance/Denise decision
  - Canonical preflight shows new violation that wasn't pre-existing → STOP, ask Sam
  - Phase 4 regression check fails for any of the 5 currently-working stores → invoke rollback, STOP, ask Sam
  - Phase 7A sweep <47/49 → STOP, do not proceed to fallback removal
  - Phase 7B sweep <46/49 after 2 attempts → STOP, ask Sam
  - Trace evidence contradicts the plan's pre-loaded hypothesis (B2/B4/B5) → STOP, present new evidence to Sam
  - Sentry surfaces a backend exception that matches the failure pattern → that's a real backend bug; STOP, ask Sam

- **continue_without_pause_through:**
  - audit
  - execute (all 10 phases in canonical order: 0 → 1 → 2A → 2B → 3A → 3B → 4 → 5 → 7A → 6 → 7B → 8)
  - PR creation
  - worktree removal

- **blocker_policy:**
  - programmatic (typo, broken import) → fix and continue
  - environment (test account locked, Doppler secret expired) → debug, fix env, continue
  - business-data (registry TIN flagged stale) → defer per Phase 5 task 8 deferred path
  - prior-SI BIR §237 exposure → pause for Finance disposition (Phase 5 task 6)
  - approval (CEO directive change) → pause

- **signoff_authority:** `single-owner` — Sam (CEO). No department co-signs needed. Finance provides TIN data only; sprint signoff is Sam's.

- **canonical_closeout_artifacts:**
  - `output/s223/RUN_STATUS.json`
  - `output/s223/RUN_SUMMARY.md`
  - `output/s223/SUMMARY.md`
  - `output/s223/DEFECT_REGISTER.md`
  - `output/s223/PHASE_CHECKLIST.md`
  - `output/l3/s223/SWEEP_VERIFICATION_SUMMARY.md`
  - `docs/plans/2026-04-25-sprint-223-fix-l3-store-chain-product-bugs.md` (this file, status updated)
  - `docs/plans/SPRINT_REGISTRY.md` (S223 row updated)

## Signoff Model

- **mode:** single-owner
- **approver_of_record:** Sam Karazi (CEO, sam@bebang.ph)
- **signoff_artifact:** `output/s223/RUN_SUMMARY.md` final state
- **note:** This is a single-owner sprint. No department co-signatures required.

## Files

This plan creates / modifies the following files:

**bei-tasks (frontend):**
- `app/dashboard/warehouse/dispatch/page.tsx` (Pattern A fix — Phase 2B)
- `app/dashboard/warehouse/approve/page.tsx` (Pattern B fix — Phase 3B)
- `app/dashboard/store-ops/order-approvals/page.tsx` (DEFECT-11 fix at line ~548 `selectedDate` — Phase 3B)
- shared component(s) per Phase 3A finding (Pattern B + DEFECT-11 fix — Phase 3B)
- `tests/e2e/pages/OrderApprovalPage.ts` (revert S221 fallback — Phase 6)
- `tests/e2e/pages/DispatchPage.ts` (revert S222 fallback — Phase 6)
- `tests/e2e/pages/WarehouseApprovalPage.ts` (extend post-fix — Phase 3B)
- `tests/e2e/test-ids.ts` (NEW or EXTEND — testid registry per Phase 0 task 10)
- `package.json` (add `"test": "vitest"` script — Phase 2B task 7)

**hrms (backend + scripts + master data + plan):**
- `hrms/api/store.py` (Pattern C fix in `submit_order` / `_create_material_request` — Phase 4; preserves existing `module="ordering"` Sentry context)
- `scripts/s223_pattern_c_probe.py` (NEW — backend probe template, Phase 4)
- `scripts/s223_ortigas_snapshot.py` (NEW — Customer snapshot helper, Phase 5)
- `scripts/s223_ortigas_apply_tin.py` (NEW — TIN apply helper using canonical TIN from registry, Phase 5)
- `scripts/s223_ortigas_si_audit.py` (NEW — BIR §237 retroactive review of prior SIs, Phase 5)
- `scripts/s223_final_cleanup_probe.py` (NEW — UTC start/end windowed cleanup with `--window-start` and `--window-end` argparse flags; non-overlapping windows for 7A vs 7B per audit P2-7 — adapted from S222)
- `output/s223/*` (per evidence_committed list)
- `output/l3/s223/*` (per evidence_committed list — both 7A and 7B sweep ledgers)
- `tmp/s223/*` (transient, gitignored)
- `docs/plans/2026-04-25-sprint-223-fix-l3-store-chain-product-bugs.md` (this file — Phase 8 status update)
- `docs/plans/SPRINT_REGISTRY.md` (S223 row — Phase 8 update)
