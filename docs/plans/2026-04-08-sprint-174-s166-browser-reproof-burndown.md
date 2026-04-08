---
sprint_id: S174
display: Sprint 174
title: "S166 Browser-Proof Re-Test Burn-Down — close 86-row test-debt ledger via real-browser Playwright re-execution"
branch: s174-s166-browser-reproof-burndown
status: PLANNED
planned_date: 2026-04-08
completed_date: null
depends_on: [S172 must deploy first, S173 ledger must be locked]
input_ledger: docs/plans/2026-04-08-sprint-173-s166-retest-debt-ledger.md
total_work_units: 75
execution_type: L3-reproof-only (no product-code changes)
sprint_registry_row: "S174 reserved on 2026-04-08. Branch: s174-s166-browser-reproof-burndown. Parent: origin/production post S172 merge."
---

# S174 — S166 Browser-Proof Re-Test Burn-Down

## Mission

Close the **86-row test-debt ledger** at `docs/plans/2026-04-08-sprint-173-s166-retest-debt-ledger.md`. Every row in that ledger represents an S166 scenario whose pass verdict was rejected by the 2026-04-08 strict browser-proof audit because the runner agent took an API shortcut or never actually drove the UI.

This sprint does NOT touch product code. It is pure test-debt burn-down: re-execute each scenario via real Playwright headless browser, produce evidence with screenshots + action logs + network capture, and submit each verdict through an independent audit gate (per the post-PR-#497 `/l3-v2-bei-erp` rule).

**Success = every row in the ledger flipped from PENDING to either `CLOSED_BROWSER_PASS`, `CLOSED_BROWSER_FAIL` (new product defect surfaced), or `DEFERRED_BLOCKED` (with documented blocker).**

## Out of Scope (STOP and ask if you hit these)

- ❌ Fixing any product defects discovered during re-proof — log them as new rows in `output/l3/s166/DEFECTS.csv` and continue. S174 or a follow-up sprint handles the fix.
- ❌ Authoring new L3 scenarios not already in the S166 catalog.
- ❌ Re-testing the 22 scenarios already marked `VERIFIED_BROWSER_PASS` / `VERIFIED_BROWSER_DEFECT_PASS` by the 2026-04-08 audit.
- ❌ Re-testing the 31 `LEGITIMATE_SKIP_WITH_PROOF` scenarios (their upstream blockers are documented; re-testing them is only valid if the blocker has been cleared by S170/S172).
- ❌ Touching the ADMS→Attendance→Timesheet→Payslip computation path — that's a separate sprint (future: time-log e2e sprint).

## Design Rationale (Cold-Start Agents)

### Why this sprint exists

S166 ran 137 scenarios and claimed ~132 PASS. The 2026-04-08 strict audit re-scored every scenario against a browser-proof bar (real Playwright action log + non-zero screenshots per scenario) and found that **only 22 of 143 scenarios (15.4%) actually held up**. 86 were rejected as `AUDIT_FAILED_*` with no trustworthy verdict.

The cause was systemic: the original L3 runners were allowed to use `fetch /api/method/…` as their "proof" because the `/l3-v2-bei-erp` skill did not require visual browser evidence. PR #497 closed that loophole going forward, but it did NOT retroactively re-prove any of the 86 existing scenarios. That's this sprint's job.

### Why one sprint, not inline with S172

S172 fixes product defects. S174 fixes test debt. Mixing them would (a) double the total work unit count above the 80-unit ceiling, (b) couple two independent risk profiles, and (c) create a single huge PR where a test-harness bug could block a real product fix from merging. Separating keeps both audit trails clean.

### Why 75 units

86 rows × 0.75 units per scenario (run + audit per pair) = 64.5. Plus ~10 units of orchestration (runner dispatch, audit gate dispatch, ledger updates, closeout). Total 75, within the 80 ceiling.

### Known limitations

- **Clean test data dependency.** Several P0 prefixes (CREATE, EDIT, SALARY) require a clean scratch employee per scenario. Phase 0 must provision these and clean them up at end.
- **Browser flakiness.** shadcn Radix dialogs need `click({ force: true })` workarounds. Lift from `scripts/testing/l3_s166_lane_h_runner.mjs`.
- **Audit gate rejection loop.** If an audit gate rejects a scenario, the fix-only retry budget is 3 iterations per scenario per the v3 plan rule. On 4th failure, mark `DEFERRED_BLOCKED` and continue.

## Ground Truth Lock

### Source files (cold-start ready)

| Artifact | Path | Purpose |
|---|---|---|
| **Debt ledger (MUST read first)** | `docs/plans/2026-04-08-sprint-173-s166-retest-debt-ledger.md` | Authoritative list of 86 scenarios + priorities + verdict definitions |
| Per-scenario audit verdicts | `output/l3/s166/AUDIT_2026-04-08/audit_per_scenario.json` | Machine-readable source |
| S166 original catalog | `docs/testing/TEST_SCENARIOS.md` (if present) or `output/l3/s166/lanes/*/SUMMARY.md` | Original scenario definitions / steps |
| Proven browser runner template | `scripts/testing/l3_s166_lane_h_runner.mjs` | Only lane runner with full browser interaction pattern |
| Login chain helper | `scripts/testing/l3_s166_phase0_preconditions.mjs` | Frappe → my.bebang.ph session bootstrap |
| SSM Frappe cleanup | `scripts/testing/s166_cleanup_conflict_orphans.py` | Pattern for post-test cleanup |
| L3 skill rule (binding) | `.claude/skills/l3-v2-bei-erp/SKILL.md` (post-PR-#497) | Audit-gate rule that governs this sprint |
| Defect register | `output/l3/s166/DEFECTS.csv` | Where NEW product defects discovered during re-proof get logged |
| S172 plan (upstream dep) | `docs/plans/2026-04-08-sprint-172-s166-followup-defect-fixes.md` | Must merge + deploy before S174 Phase 2 starts |

### Priority buckets (copied from debt ledger)

**P0 — core lifecycle, cannot ship without proof (~48 rows)**
- EMP-CREATE × 7 (7 of 12 create flows lack browser proof)
- EMP-SALARY × 10 (full salary chain — runner used API path)
- EMP-EDIT × 16 (HR profile edits — 15 API-only + 1 browser-fail)
- EMP-PAYROLL × 6 (payroll processing page flows)
- EMP-PAYSLIP × 2 (employee self-service slip viewer)
- EMP-ATTENDANCE × 3 (correction request + approve + verify)
- EMP-ADMS × 2 (enrollment screenshots missing)
- EMP-GOVID × (tracked as EDIT subset in audit output)
- EMP-BANK × (tracked as EDIT subset)

**P1 — compliance + RBAC + UX (~32 rows)**
- EMP-UX × 11
- EMP-STUB × 6
- EMP-RBAC × 5
- EMP-TRANSFER × 5
- EMP-LEAVE × 4
- EMP-REGULARIZE × 3
- EMP-BIOCHANGE × 2
- EMP-OVERTIME × 1 (remainder after S172 closes #19/#20)
- EMP-DISCIPLINARY × 1 (remainder after S172 closes #18)

**P2 — residual (~6 rows)**
- EMP-PHOTO × 2
- EMP-CLEAN × 1
- EMP-CONFLICT × 1 (test-harness bug, not product)
- EMP-COMPLETION × 1
- retest × 1

Totals must match the debt ledger exactly. If they don't, STOP and reconcile before writing code.

## Requirements Regression Checklist (verify before executing)

- [ ] Have I read `docs/plans/2026-04-08-sprint-173-s166-retest-debt-ledger.md` end-to-end?
- [ ] Is S172 merged AND deployed to production? (Phase 2 depends on this.)
- [ ] Am I using `scripts/testing/l3_s166_lane_h_runner.mjs` as the runner template, not inventing a new pattern?
- [ ] **HARD BLOCKER:** For every scenario I retest, am I dispatching an INDEPENDENT audit agent (separate session, different context) per PR #497?
- [ ] **HARD BLOCKER:** Am I marking a scenario CLOSED only when the audit agent writes a PASS_WITH_PROOF flag, not when the runner reports success?
- [ ] Am I writing EVIDENCE files for every scenario — `actions[]`, `screenshots[]` (non-zero bytes), `network[]`?
- [ ] Am I NOT fixing any product defects discovered — logging them as new DEFECTS.csv rows and continuing?
- [ ] Am I updating the debt ledger (`docs/plans/2026-04-08-sprint-173-s166-retest-debt-ledger.md`) after each phase with status flips?
- [ ] Branch compliance: `s174-s166-browser-reproof-burndown` created from `origin/production` POST S172 merge?
- [ ] PR-handoff: creating PR and stopping at PR_CREATED?

## Phase Budget Contract

| Phase | Units | Description |
|---|---:|---|
| Phase 0 | 4 | Preconditions: branch, test-data provisioning, ledger read-back, S172 deploy verification |
| Phase 1 | 14 | P0 wave 1 — EMP-CREATE ×7 + EMP-ADMS ×2 + EMP-ATTENDANCE ×3 (12 scenarios) |
| Phase 2 | 16 | P0 wave 2 — EMP-SALARY ×10 + EMP-PAYROLL ×6 + EMP-PAYSLIP ×2 (18 scenarios) — DEPENDS ON S172 DEPLOY |
| Phase 3 | 14 | P0 wave 3 — EMP-EDIT ×16 (mostly API-only false positives) |
| Phase 4 | 12 | P1 wave 1 — EMP-UX ×11 + EMP-STUB ×6 (17 scenarios) |
| Phase 5 | 10 | P1 wave 2 — EMP-RBAC ×5 + EMP-TRANSFER ×5 + EMP-LEAVE ×4 + EMP-REGULARIZE ×3 + EMP-BIOCHANGE ×2 + EMP-OVERTIME ×1 + EMP-DISCIPLINARY ×1 (21 scenarios) |
| Phase 6 | 2 | P2 residual — EMP-PHOTO ×2 + EMP-CLEAN ×1 + EMP-CONFLICT ×1 + EMP-COMPLETION ×1 + retest ×1 |
| Phase 7 | 3 | Ledger reconciliation + new-defect triage + DEFECTS.csv updates |
| Phase 8 | — | (reserved for retry loop if audit gates reject) — not counted, 3-iter budget per scenario |
| Phase 9 | — | (reserved for closeout) — merged into Phase 7 + PR creation below |
| **Total** | **75** | Under 80-unit ceiling. Largest phase (Phase 2) = 16 units. |

## Autonomous Execution Contract

- **completion_condition:** Every row in `docs/plans/2026-04-08-sprint-173-s166-retest-debt-ledger.md` has status ∈ {`CLOSED_BROWSER_PASS`, `CLOSED_BROWSER_FAIL`, `DEFERRED_BLOCKED`}. No PENDING rows remain.
- **stop_only_for:**
  - S172 not yet deployed at start of Phase 2 (wait for Sam's deploy signal)
  - Test data exhaustion (>50 scratch employees needed, SSM bulk-provision blocked)
  - Audit gate 4th-iteration failure on >5 scenarios in a single prefix (indicates systemic runner bug, escalate)
  - >10 NEW product defects discovered in a single phase (indicates S172 didn't deploy cleanly)
- **continue_without_pause_through:** Phase 0 → 7
- **signoff_authority:** single-owner (Sam). PR lands in Sam's inbox.
- **canonical_closeout_artifacts:**
  - `docs/plans/2026-04-08-sprint-173-s166-retest-debt-ledger.md` (updated with per-row status)
  - `docs/plans/2026-04-08-sprint-173-s166-browser-reproof-burndown.md` (this file, status=COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (S174 row COMPLETED)
  - `output/l3/s174/reproof/<prefix>/<sid>.json` (per scenario)
  - `output/l3/s174/AUDIT_REPORT.md` (aggregate audit gate report)
  - `output/l3/s166/DEFECTS.csv` (any new product defects discovered, logged but NOT fixed)

## Agent Boot Sequence

1. **Read `docs/plans/2026-04-08-sprint-173-s166-retest-debt-ledger.md` end-to-end.** This is the source of truth for what to retest.
2. **Read this plan fully, every phase.**
3. **Verify S172 merged + deployed.** Check `docs/plans/SPRINT_REGISTRY.md` S172 row status; if not COMPLETED, STOP and wait for Sam.
4. **Create sprint branch:** `git fetch origin production && git checkout -b s174-s166-browser-reproof-burndown origin/production`. Same for bei-tasks if any frontend-side test changes needed.
5. **Read post-#497 audit-gate rule:** `.claude/skills/l3-v2-bei-erp/SKILL.md` — search for "Audit Gate on EVERY Verdict-Producing Agent"
6. **Read runner template:** `scripts/testing/l3_s166_lane_h_runner.mjs`
7. **Start Phase 0.**

## Phases

### Phase 0 — Preconditions (4 units)

1. Branch created from `origin/production` POST S172 merge
2. Verify S172 deploy: hit `https://my.bebang.ph/dashboard/hr/payroll/compensation-setup/9000003` as test.hr and confirm Edit button is enabled (Defect #21 fixed). If not, STOP.
3. Provision clean scratch employees via `/frappe-bulk-edits` — target: 5 scratch employees with unique Bio IDs, clean `status=Active`, no SSA, no disciplinary records. Name pattern: `S174-SCRATCH-01..05`.
4. Create artifact dirs: `mkdir -p output/l3/s174/{reproof,audit,evidence,diagnostics}`
5. Copy debt ledger PENDING count into `output/l3/s174/BASELINE.json`
6. Write `output/l3/s174/REQUIREMENTS_REGRESSION_CHECK.md`

**Verification:** Phase 0 passes only when all 6 items are complete AND the baseline PENDING count matches the debt ledger exactly.

### Phase 1 — P0 wave 1: CREATE + ADMS + ATTENDANCE (14 units)

**Scenarios (12 total):**
- EMP-CREATE-001 through EMP-CREATE-007 (7 of 12 create flows — the ones flagged NO_BROWSER_PROOF in ledger)
- EMP-ADMS-001, EMP-ADMS-002 (enrollment — missing screenshots in audit)
- EMP-ATTENDANCE-001, EMP-ATTENDANCE-002, EMP-ATTENDANCE-003

**Pattern per scenario:**
1. Dispatch runner subagent with scenario brief + pointer to `l3_s166_lane_h_runner.mjs` template
2. Runner writes `output/l3/s174/reproof/CREATE/EMP-CREATE-NNN.json` with actions + screenshots + network
3. Dispatch INDEPENDENT audit subagent (fresh context) to inspect evidence
4. Audit writes `output/l3/s174/audit/CREATE/EMP-CREATE-NNN.verdict.json`
5. Orchestrator reads verdict file (NOT runner summary), flips ledger row
6. On audit reject → retry loop (max 3 iterations per scenario)

**MUST_MODIFY:** `docs/plans/2026-04-08-sprint-173-s166-retest-debt-ledger.md` (flip 12 PENDING rows)
**MUST_EXIST:** 12 evidence files + 12 verdict files + 12 pre-screenshots + 12 post-screenshots

### Phase 2 — P0 wave 2: SALARY + PAYROLL + PAYSLIP (16 units)

**HARD GATE:** Phase 2 may NOT start until S172 is MERGED AND DEPLOYED. Verify via browser (see Phase 0 step 2) + check SPRINT_REGISTRY.md S172 row = COMPLETED.

**Scenarios (18 total):**
- EMP-SALARY-001 through EMP-SALARY-013 (minus any already passed in S172 Phase 8 — reconcile against ledger first)
- EMP-PAYROLL-RUN-001 through EMP-PAYROLL-RUN-006 (Generate Slips + review + compare + history)
- EMP-PAYSLIP-001, EMP-PAYSLIP-002

**Special notes:**
- EMP-SALARY chain needs a fresh scratch employee per Lane A workflow. Pre-provision in Phase 0.
- EMP-PAYROLL-RUN-001 is the "Generate Slips button disabled" scenario from S166 Defect #5. If S172 Phase 7 did NOT fix it (it was marked speculative), this scenario will now legitimately fail — log as new defect in DEFECTS.csv, mark ledger row `CLOSED_BROWSER_FAIL`, continue.

**Same dispatch pattern as Phase 1.** Runner + independent audit gate per scenario.

### Phase 3 — P0 wave 3: EDIT (14 units)

**Scenarios (16 total):**
- EMP-EDIT-001 through EMP-EDIT-016 (15 currently API-only + 1 browser-fail)

**Focus:** This wave is almost entirely API-only false positives — the original runner called `frappe.client.set_value` and checked the 200 response. S174 must drive the actual EmployeeDetailDialog UI:
1. Navigate to `/dashboard/hr/employee-master`
2. Open a scratch employee row
3. Edit the target field (cell number, middle name, etc.) via the rendered input
4. Click Save
5. Wait for toast / reload
6. Re-fetch via API and confirm persistence

This is the exact scenario S166 Lane A2/A5 claimed to have tested — the audit caught that they never actually did.

**Special: EMP-EDIT-CONTACT-002** — if S172 Phase 6 fixed Defect #13 (emergency_phone_number drop), this scenario should now legitimately pass. If it still fails, log as retained defect.

### Phase 4 — P1 wave 1: UX + STUB (12 units)

**Scenarios (17 total):**
- EMP-UX-001 through EMP-UX-012 (minus UX-004 and UX-005 already in verified bucket)
- EMP-STUB-001 through EMP-STUB-007 (minus STUB-005 already verified)

UX scenarios are mostly menu navigation + RBAC visibility + dashboard card rendering. STUB scenarios are collateral / placeholder checks.

### Phase 5 — P1 wave 2: RBAC + TRANSFER + LEAVE + REGULARIZE + BIOCHANGE + OVERTIME + DISCIPLINARY (10 units)

**Scenarios (21 total):** as listed in debt ledger EMP-RBAC ×5, EMP-TRANSFER ×5, EMP-LEAVE ×4, EMP-REGULARIZE ×3, EMP-BIOCHANGE ×2, EMP-OVERTIME ×1 (post S172 unblock), EMP-DISCIPLINARY ×1 (post S172 unblock).

### Phase 6 — P2 residual (2 units)

**Scenarios (6 total):** EMP-PHOTO ×2, EMP-CLEAN ×1, EMP-CONFLICT ×1 (expected to remain FAIL — test harness bug), EMP-COMPLETION ×1, retest ×1.

### Phase 7 — Reconciliation + closeout (3 units)

1. Read `docs/plans/2026-04-08-sprint-173-s166-retest-debt-ledger.md` and count status by verdict
2. Confirm 0 PENDING rows
3. Write `output/l3/s174/FINAL_RECONCILIATION.md` with baseline vs end-state
4. Triage any new product defects discovered → create rows in `output/l3/s166/DEFECTS.csv` with `recommended_sprint: S174`
5. Update `docs/plans/2026-04-08-sprint-173-s166-retest-debt-ledger.md` header: `status: CLOSED`, `closed_by: S174`, `closed_date: <ISO PHT>`
6. Update `docs/plans/SPRINT_REGISTRY.md` S174 row: PLANNED → COMPLETED with per-phase summary
7. Cleanup scratch employees provisioned in Phase 0 via `/frappe-bulk-edits`
8. Create PR via `gh pr create --base production --head s174-s166-browser-reproof-burndown`
9. STOP at PR_CREATED

## Zero-Skip Enforcement

- Every scenario in the debt ledger MUST get one of: `CLOSED_BROWSER_PASS`, `CLOSED_BROWSER_FAIL`, `DEFERRED_BLOCKED`
- `DEFERRED_BLOCKED` is only valid with a documented blocker (missing prerequisite, upstream defect, etc.) written to `output/l3/s174/BLOCKERS.csv`
- `CLOSED_BROWSER_FAIL` requires a corresponding row in `output/l3/s166/DEFECTS.csv`
- Running a scenario via API shortcut is FORBIDDEN. The runner brief must explicitly instruct Playwright headless usage. The audit gate rejects anything without screenshots.

## Test Scripts Reference

| Purpose | Script |
|---|---|
| Runner template | `scripts/testing/l3_s166_lane_h_runner.mjs` |
| Login chain | `scripts/testing/l3_s166_phase0_preconditions.mjs` |
| SSM cleanup | `scripts/testing/s166_cleanup_conflict_orphans.py` |
| Audit script template | `scripts/testing/s166_audit_browser_proof_v3.py` |
| Frappe bulk data provisioning | `/frappe-bulk-edits` skill |

Test accounts: `memory/testing-accounts.md` (all passwords `BeiTest2026!`)

## Execution Authority

Autonomous end-to-end except for the S172-deploy gate at start of Phase 2. Do not stop for progress updates. Only pause for items in `stop_only_for`.

PR-Handoff Rule: agent creates PR and STOPS. Sam merges.
