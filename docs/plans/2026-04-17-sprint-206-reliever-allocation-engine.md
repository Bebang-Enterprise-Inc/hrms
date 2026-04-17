---
sprint: S206
title: Reliever Punch-Based Labor Allocation Engine
branch: s206-reliever-allocation-engine
base: production
status: GO
planned_date: 2026-04-17
planned_by: Claude (BEI-ERP)
owner: Sam Karazi (CEO)
depends_on: [S201]
followed_by: []
estimated_units: 52
primary_repo: hrms
touches_frontend: false
l3_required: true
hard_deadline: 2026-05-15  # first payroll cutoff where April mis-allocation is material
completion_condition: |
  - hrms/utils/punch_allocation.py shipped and unit-tested (shift-share per store)
  - hrms/utils/labor_allocation.py shipped and unit-tested (JE generator per Salary Slip)
  - hrms/api/labor_allocation.py::preview_monthly_allocation returns planned JEs for review
  - hrms/api/labor_allocation.py::post_monthly_allocation commits JEs under savepoint (DM-2)
  - All JEs satisfy DM-1 (party fields) + DM-6 (remarks, cost_center, reference)
  - Inter-Company Due From/Due To account seeding patch runs dry-run default; S206_APPLY=1 to apply
  - Sentry observability context on both whitelisted endpoints (DM-7)
  - L3: April 2026 dry-run preview reviewed and posts cleanly for at least 3 store Companies
  - Plan YAML status -> COMPLETED and SPRINT_REGISTRY.md updated
stop_only_for:
  - Missing intercompany accounts that require Sam/Finance decision on COA structure
  - Destructive bulk mutation requires Sam approval (always dry-run first)
  - Punch data gap > 10% of an employee's payroll period (insufficient attendance data)
  - Merge conflict on production during rebase
---

# Sprint S206 — Reliever Punch-Based Labor Allocation Engine

## Background

**Trigger:** S201 Option X decided Employee.company stays on the legal employer. Per-store internal billing must flow via monthly inter-Company labor cost reclassification. S206 delivers that engine.

**Why this matters:**
- Without S206, per-store P&L is fiction — all labor cost sits on BEI parent and per-store Companies show zero labor.
- Relievers (employees who cover multiple stores) need fair attribution to the store that actually consumed their hours.
- Data starts April 01, 2026. Hard deadline: **May 15, 2026** (first half-month payroll cutoff where April allocation becomes material).

**Link to S201:**
- `hrms/utils/company_lookup.py` — branch → Company resolver (used to map punches to store Companies)
- `hrms/utils/non_store_billing.py` — classifier (used to skip roving/AS/HO/SCM/R&D employees whose cost stays on BEI parent)
- `hrms/data_seed/branch_company_map.csv` — branch ↔ Company mapping (already applied to tabEmployee)
- Employee.company = legal employer (UNTOUCHED, stable for statutory filings)

## Architecture Summary

Every month (or on-demand):

1. **Find in-scope Salary Slips** — period ends in the target month, status = Submitted, employee NOT is_non_store_billing.
2. **For each slip:**
   a. Query `tabEmployee Checkin` for punches in the slip's period.
   b. Map device_sn → store Company via `DEVICE_TO_STORE` + `company_lookup`.
   c. Compute shift-share (or hour-share) per store.
   d. If all punches at home store (= employee.company) → skip (no JE needed).
   e. Else: build JE line per covered-store, prorated labor cost:
      - DR `Salaries Expense - <covered-store>` × share, party=employee as Supplier-like
      - CR `Salaries Expense - <home-store>` × share
      - DR/CR "Due From / Due To" inter-Company control accounts (per S175 COA template)
3. **Group JEs** by (home_company, posting_date) into a single Journal Entry with multiple pairs.
4. **Preview mode:** return planned JEs as JSON for review, no DB writes.
5. **Apply mode:** `S206_APPLY=1` + whitelisted function call → savepoint wrap → insert + submit JEs → commit.

## Locked Decisions (from S201 pivot + Sam 2026-04-17)

| ID | Decision | Source |
|---|---|---|
| LD-1 | Employee.company NOT touched by S206 (stable for SSS/BIR/HDMF) | S201 Option X |
| LD-2 | Allocation is internal-only (reclassification JE within group books, no cash movement) | Sam B2 |
| LD-3 | Non-store billers (roving/AS/RM/IT/Marketing/Finance/HR/Legal/Admin/Exec/R&D/BD/SCM) stay on BEI parent — no allocation runs for them | S201 LD-2 |
| LD-4 | Commissary employees (dept=Commissary on SHAW COMMISSARY - PRODUCTION) stay on BKI — no allocation runs for them | S201 LD-3 |
| LD-5 | Data starts April 01, 2026 — no retro before that | S201 LD-6 |
| LD-6 | Deadline May 15, 2026 cutoff | S201 B15 |
| LD-7 | Default runtime = preview (dry-run); apply requires `S206_APPLY=1` | S201 patch pattern |
| LD-8 | Shift-share unit = counted IN/OUT pairs; hour-share (end-start) is optional v2 refinement if pairs are unreliable | Proposed — confirm during L3 |

## Requirements Regression Checklist

Before declaring COMPLETED, the executing agent MUST answer YES to each:

- [ ] Every generated JE has `party` + `party_type` on receivable/payable rows (DM-1)?
- [ ] Every JE creation is wrapped in `frappe.db.savepoint()` with rollback on partial failure (DM-2)?
- [ ] Every JE has `user_remark` citing source Salary Slip + period (DM-6)?
- [ ] Every JE row has `cost_center` set to the target store's cost center (DM-6)?
- [ ] Every new `@frappe.whitelist()` function calls `set_backend_observability_context()` (DM-7)?
- [ ] Allocation skips employees where `is_non_store_billing()` returns True?
- [ ] Allocation skips Commissary-dept employees on SHAW COMMISSARY - PRODUCTION branch (they stay on BKI)?
- [ ] If an employee has zero punches for the period, allocation is skipped and logged (not error)?
- [ ] If all punches are at home store, no JE is generated (shortcut)?
- [ ] Apply mode uses direct SQL UPDATE on Salary Slip reference field OR inserts JE with reference to slip (audit trail)?
- [ ] `S206_APPLY=1` is required for actual posting (dry-run is default)?
- [ ] Plan YAML `status: COMPLETED` and SPRINT_REGISTRY.md row updated (S092 closeout rule)?

## Design Rationale (For Cold-Start Agents)

### Why monthly JE instead of per-slip?

Grouping all slips of a period into one JE per (home_company, period) reduces JE count (49 stores × 1 period = max 49 JEs vs 500+ slips × 49 stores = thousands of JEs). This matches how finance teams process month-end adjustments.

### Why shift-share (counted punch pairs), not hour-share?

- **Shift-share**: count IN/OUT pairs; each valid pair = one shift; share = store_shifts / total_shifts.
- **Hour-share**: sum (OUT - IN) hours per store; share = store_hours / total_hours.

Shift-share is simpler and robust to missing punches (common per S043). Hour-share is "more accurate" but fails catastrophically when punches are missed. BEI already ran into this in S043 auto-attendance work. **Default: shift-share.** Hour-share is v2 refinement.

### Why not touch Employee.company?

S201 Option X is the core architectural decision: legal employer stays stable for PH statutory compliance (single employer per SSS/PhilHealth/HDMF/BIR 2316 period). Internal billing flows via reclassification JE. See `output/plan-audit/s201/verified_blockers.md` for the full audit trail.

### Why inter-Company Due From / Due To accounts?

BEI's group structure has 49 store Companies + BEI parent + BKI commissary + 5 holding Companies. When labor cost shifts from Company A to Company B, the JE must balance across both books using standard intercompany accounts:

- Company A (home, legal employer): CR `Salaries Expense` + DR `Due From Company B` → Company A now has a receivable from B for the reclassified labor.
- Company B (covered store): DR `Salaries Expense` + CR `Due To Company A` → Company B now has a payable to A for the labor they consumed.

S175 created a master COA with `2104200 DUE TO BFC` and `1104200 DUE FROM BEI` for specific pairs. We may need to seed a generic "Due To/From Group Entities" per Company.

### Why preview + apply separation?

Finance never wants an automated bot posting JEs without review. The preview mode lets Finance (or Sam) review the planned allocation BEFORE committing. Default is always dry-run. Apply is gated by `S206_APPLY=1` env var.

### Known limitations

- Does not handle retro edits to Salary Slip (if a slip is amended post-allocation, the allocation JE should be reversed + regenerated — v2).
- Does not handle part-time or multi-employer edge cases (rare in BEI).
- Assumes DEVICE_TO_STORE mapping is current (maintained manually in `hrms/utils/device_mapping.py`).

## Ground-Truth Lock

- **Evidence sources:**
  - `hrms/utils/company_lookup.py` → store prefix → Company resolver
  - `hrms/utils/non_store_billing.py` → HO/roving classifier
  - `hrms/utils/device_mapping.py` → DEVICE_TO_STORE dict (48 devices)
  - `hrms/data_seed/branch_company_map.csv` → branch taxonomy
  - `tabEmployee Checkin` → ADMS punch records (pin, device_id, event_time, log_type)
  - `tabSalary Slip` → payroll cost basis
  - `tabCompany` → 49 store Companies + parents
- **Count method:**
  - metric: shifts per store per employee per period
  - basis: IN/OUT pair count from tabEmployee Checkin grouped by device→store
  - method: SQL aggregate over `status='Submitted' AND employee=X AND start_date<=event_time<=end_date`
- **Authoritative sections:** Phase 0-6 are execution source of truth. Amendment history is traceability.
- **Unresolved value policy:** `[UNVERIFIED — requires resolution]` for any Company/account path not found in live Frappe.

## Phase 0 — Preflight & Account Audit (6u)

Goal: confirm every store Company has the required accounts for JE posting.

- [ ] P0-T1 Query live Frappe for each store Company's COA — confirm presence of:
  - `Salaries Expense` (or equivalent — use `frappe.defaults.get_default("default_salary_expense_account")` per Company)
  - `Due From Group Entities` (or equivalent intercompany receivable)
  - `Due To Group Entities` (or equivalent intercompany payable)
  - Default cost center
- [ ] P0-T2 Dump audit results to `output/s206/diagnostics/company_coa_audit.json` with columns `company | salaries_expense_account | due_from_account | due_to_account | default_cost_center | status`.
- [ ] P0-T3 If any Company lacks the required accounts, log gaps to `output/s206/diagnostics/MISSING_ACCOUNTS.md` and create Phase 0.5 remediation (patch or manual seed via Sam).

**HARD BLOCKER:** If >10 store Companies lack required accounts, STOP and request Finance intervention. Do NOT proceed to code phases with unresolvable accounts.

MUST_MODIFY: `output/s206/diagnostics/company_coa_audit.json` (created)
MUST_CONTAIN: `output/s206/diagnostics/company_coa_audit.json` → entries for all 49 store Companies

## Phase 1 — `punch_allocation.py` (10u)

Goal: compute per-employee shift-share across stores for a given period.

- [ ] P1-T1 Create `hrms/utils/punch_allocation.py` exposing:
  - `compute_shift_share(employee: str, start_date: date, end_date: date) -> dict[str, float]` — returns `{company_name: share (0-1)}` where shares sum to 1.0. Empty dict if no punches.
  - `compute_shifts_by_store(employee: str, start_date: date, end_date: date) -> dict[str, int]` — returns raw shift counts per store (not normalized).
  - `_pair_punches(checkins: list) -> list[dict]` — pair IN with next OUT per device; unpaired punches counted as orphan half-shifts (logged).
  - Internal: query `tabEmployee Checkin` filtered by employee + time range; join DEVICE_TO_STORE to resolve store; join `company_lookup` to get Company docname.
- [ ] P1-T2 Edge cases:
  - Zero punches → return empty dict, log via `frappe.logger().info`.
  - All punches at one store → return `{store: 1.0}`.
  - IN without matching OUT → count as 0.5 shift, log warning.
  - Device not in DEVICE_TO_STORE → log error, skip that punch (shouldn't happen but fail safe).
- [ ] P1-T3 Unit tests in `hrms/tests/test_s206_punch_allocation.py`:
  - 10 punches all at SM MEGAMALL → share = 1.0 to `SM MEGAMALL - BEI`
  - 5 SM MEGAMALL + 5 SM TANZA → share = 0.5 / 0.5
  - 0 punches → empty dict
  - 1 orphan IN → 0.5 shift
  - Punch at unknown device → skipped, no crash

MUST_MODIFY: `hrms/utils/punch_allocation.py` (new)
MUST_CONTAIN: `compute_shift_share`, `tabEmployee Checkin`, `DEVICE_TO_STORE`
MUST_MODIFY: `hrms/tests/test_s206_punch_allocation.py` (new)
MUST_CONTAIN: at least 5 test methods

## Phase 2 — `labor_allocation.py` core (12u)

Goal: given a Salary Slip, build the inter-Company JE that reclassifies labor cost by punch share.

- [ ] P2-T1 Create `hrms/utils/labor_allocation.py` exposing:
  - `allocate_slip(slip_name: str, dry_run: bool = True) -> dict` — returns dict describing the JE that WOULD be created (if dry_run) or the actual JE name (if not dry_run + apply mode).
  - `_build_je_for_slip(slip_doc, shares: dict) -> frappe.model.document.Document` — constructs the Journal Entry doc without inserting.
  - `_skip_reason(slip_doc) -> str | None` — returns skip reason (non_store_billing, no_punches, all_home, commissary_producer) or None if allocation should proceed.
- [ ] P2-T2 JE construction rules (DM-1, DM-6):
  - `voucher_type = "Journal Entry"`
  - `posting_date = slip.end_date`
  - `user_remark = f"S206 reliever allocation: slip {slip.name}, period {slip.start_date}..{slip.end_date}, home={slip.company}"`
  - One DR Salaries Expense per covered store (amount = slip.gross_pay × share)
  - Matching CR Salaries Expense on home Company (home's total CR = sum of covered DRs)
  - For each DR/CR pair, add intercompany entries: DR `Due From <covered>` on home / CR `Due To <home>` on covered (zero net per pair)
  - Each row: `party_type = "Employee"`, `party = slip.employee`, `cost_center = <target store's default>`, `reference_type = "Salary Slip"`, `reference_name = slip.name`
- [ ] P2-T3 Edge case: if shares includes the home store (employee punched at their own home some shifts), only allocate the NON-home portion. Home portion stays implicitly on home company via the original slip posting.
- [ ] P2-T4 Unit tests in `hrms/tests/test_s206_labor_allocation.py`:
  - Slip with all-home punches → `_skip_reason` returns `all_home`, no JE
  - Slip with 50/50 split → JE has 2 DR rows (home+covered) and matching CRs
  - Slip for non_store_billing employee → `_skip_reason` returns `non_store_billing`
  - Slip with gross_pay=0 → no JE (defensive)

MUST_MODIFY: `hrms/utils/labor_allocation.py` (new)
MUST_CONTAIN: `def allocate_slip`, `party_type`, `cost_center`, `reference_type`, `user_remark`
MUST_MODIFY: `hrms/tests/test_s206_labor_allocation.py` (new)
MUST_CONTAIN: at least 4 test methods

## Phase 3 — `@frappe.whitelist()` API (8u)

Goal: preview + apply endpoints callable from Frappe Desk / scripts.

- [ ] P3-T1 Create `hrms/api/labor_allocation.py` exposing:
  - `preview_monthly_allocation(year: int, month: int) -> dict` — whitelisted, returns dict with all planned JEs for the month (dry-run, no DB writes). Payload shape:
    ```
    {
      "period": {"start": "2026-04-01", "end": "2026-04-30"},
      "total_slips": N,
      "in_scope_slips": M,
      "skipped": [{"slip": ..., "reason": ...}, ...],
      "planned_jes": [{"home_company": ..., "lines": [...], "total": ...}, ...],
      "dry_run": true
    }
    ```
  - `post_monthly_allocation(year: int, month: int) -> dict` — whitelisted, requires `S206_APPLY=1` env OR explicit `confirm=True` kwarg. Actually inserts + submits JEs under `frappe.db.savepoint("s206_monthly_alloc_YYYYMM")`. Returns result with created JE names. Any row-level failure → rollback savepoint + `frappe.log_error` → no partial batch commit.
- [ ] P3-T2 Both functions start with:
  ```python
  set_backend_observability_context(
      module="finance",
      action="<function_name>",
      mutation_type="create",
      extras={"year": year, "month": month},
  )
  ```
- [ ] P3-T3 Permission gate: only users with `Accounts Manager` OR `CFO` OR `System Manager` can call `post_monthly_allocation` (preview can be Finance User).

MUST_MODIFY: `hrms/api/labor_allocation.py` (new)
MUST_CONTAIN: `@frappe.whitelist()`, `set_backend_observability_context`, `preview_monthly_allocation`, `post_monthly_allocation`, `savepoint`, `rollback`, `release_savepoint`

## Phase 4 — Intercompany account seed patch (6u)

Goal: ensure every store Company has the Due From / Due To accounts needed for intercompany JEs.

- [ ] P4-T1 Create `hrms/patches/v16_0/s206_seed_intercompany_accounts.py`:
  - Dry-run default; `S206_APPLY=1` to apply.
  - For each Company where `entity_category='Store'` OR `name='BEBANG ENTERPRISE INC.'`:
    - Ensure account `2104200 - DUE TO GROUP ENTITIES - <abbr>` exists under group "Current Liabilities"
    - Ensure account `1104200 - DUE FROM GROUP ENTITIES - <abbr>` exists under group "Current Assets"
    - If missing, create via `frappe.get_doc("Account", {...}).insert()`
  - Wrap in savepoint, rollback on partial failure, log via `frappe.log_error`.
- [ ] P4-T2 Append to `hrms/patches.txt` under `[post_model_sync]`.
- [ ] P4-T3 Emit audit report to `output/s206/diagnostics/intercompany_seed_report_<timestamp>.json`.

MUST_MODIFY: `hrms/patches/v16_0/s206_seed_intercompany_accounts.py` (new)
MUST_CONTAIN: `S206_APPLY`, `savepoint`, `frappe.log_error`, `DUE TO GROUP ENTITIES`, `DUE FROM GROUP ENTITIES`
MUST_MODIFY: `hrms/patches.txt`
MUST_CONTAIN: `s206_seed_intercompany_accounts`

## Phase 5 — Scheduler hook (optional auto-trigger) (4u)

Goal: nightly check after payroll submit to auto-create DRAFT JEs ready for review.

- [ ] P5-T1 Add to `hrms/hooks.py`:
  ```python
  scheduler_events = {
      "monthly": [
          # S206 — auto-preview reliever allocation first day of each month
          "hrms.api.labor_allocation.preview_monthly_allocation_scheduled",
      ],
  }
  ```
- [ ] P5-T2 Add `preview_monthly_allocation_scheduled()` in `hrms/api/labor_allocation.py` — wraps preview for the prior month and emails the report to Sam via `frappe.sendmail`.
- [ ] P5-T3 Make scheduler event safe (no DB writes, just email).

MUST_MODIFY: `hrms/hooks.py`
MUST_CONTAIN: `preview_monthly_allocation_scheduled`
MUST_MODIFY: `hrms/api/labor_allocation.py`
MUST_CONTAIN: `def preview_monthly_allocation_scheduled`, `frappe.sendmail`

## Phase 6 — Unit tests + closeout (6u)

- [ ] P6-T1 Run all three test files locally: `test_s206_punch_allocation.py`, `test_s206_labor_allocation.py`, `test_s206_api_labor_allocation.py` (if added).
- [ ] P6-T2 Smoke-test via Frappe stub (pattern from S201 /tmp/s201_smoke.py).
- [ ] P6-T3 Update plan YAML: `status: COMPLETED`, `completed_date: 2026-04-??`, PR #.
- [ ] P6-T4 Update `SPRINT_REGISTRY.md` S206 row: status COMPLETED + PR #.
- [ ] P6-T5 `git add -f docs/plans/*.md output/s206/ && git commit && git push`.
- [ ] P6-T6 Create PR to production.

## L3 Workflow Scenarios (per S092 corrupt-success rule)

Run in a FRESH session after deploy (NOT builder session — avoids context bias per S099).

| # | Scenario | Action | Expected Outcome | Failure Means |
|---|---|---|---|---|
| L3-1 | Preview April 2026 with no apply | Call `preview_monthly_allocation(2026, 4)` via bench console | Returns dict with dry_run=true, total_slips and in_scope_slips populated, no JEs created in Frappe | Preview is leaking writes |
| L3-2 | Skip non_store_billing employee | Pick Edlice Dela Cruz (bio 9001812, REGIONAL AREA MANAGER). Confirm her slip appears in `skipped` with reason=`non_store_billing` | Skipped correctly, no JE planned for her | classifier broken |
| L3-3 | All-home punch shortcut | Pick a CASHIER whose all April punches were at their home store. Confirm slip is in `skipped` with reason=`all_home` | No JE planned | shortcut broken |
| L3-4 | Split allocation (real reliever) | Pick a reliever who punched at 2+ stores in April. Confirm planned JE shows DR/CR rows with correct shares summing to slip.gross_pay | Shares balance; DR store ≠ home; CR home | allocation math broken |
| L3-5 | Apply mode with savepoint | Call `post_monthly_allocation(2026, 4)` with `S206_APPLY=1`. Plant one bad account name to force a row-level failure. Verify rollback: no JEs in Frappe + log_error entry | Savepoint rollback works; zero JEs persisted | DM-2 violation |
| L3-6 | Apply mode success path | Reset, call `post_monthly_allocation(2026, 4)` again cleanly. Verify JE(s) created, each with party+party_type on GL rows, user_remark cites slip, cost_center set | JEs visible in Frappe + GL Entries show per-store labor | DM-1 or DM-6 violation |

**Evidence contract:**
- `output/l3/s206/form_submissions.json`
- `output/l3/s206/api_mutations.json`
- `output/l3/s206/state_verification.json`

## Ownership Matrix

| File family | Owner | Protected (do not touch) |
|---|---|---|
| `hrms/utils/punch_allocation.py` | S206 (new) | — |
| `hrms/utils/labor_allocation.py` | S206 (new) | — |
| `hrms/api/labor_allocation.py` | S206 (new) | — |
| `hrms/patches/v16_0/s206_*.py` | S206 (new) | — |
| `hrms/tests/test_s206_*.py` | S206 (new) | — |
| `hrms/utils/company_lookup.py` | S201 | **PROTECTED** — consume only |
| `hrms/utils/non_store_billing.py` | S201 | **PROTECTED** — consume only |
| `hrms/utils/device_mapping.py` | S019 era | **PROTECTED** — consume only |
| `hrms/utils/roving_employees.py` | HR/IT audit | **PROTECTED** — consume via is_roving only |
| `hrms/hooks.py` | shared | only append scheduler_events line |
| `hrms/patches.txt` | shared | only append new row |
| Existing JV / GL logic | Finance | **PROTECTED** — don't refactor |

## Rollback Contract

If a monthly allocation posts bad JEs:

1. Cancel each JE (`frappe.get_doc("Journal Entry", je_name).cancel()`) — GL entries auto-reversed.
2. If cancel fails: `UPDATE tabJournal Entry SET docstatus=2 WHERE name=...` + manual GL cleanup (Finance).
3. Revert code: `git revert` the whitelisted endpoint commit (preserves libraries for S207+ fixes).
4. Delete intercompany accounts created by Phase 4 patch if they were wrongly created (usually safe — accounts just sit unused).

## Files To Be Modified/Created

| Action | File |
|---|---|
| CREATE | `hrms/utils/punch_allocation.py` |
| CREATE | `hrms/utils/labor_allocation.py` |
| CREATE | `hrms/api/labor_allocation.py` |
| CREATE | `hrms/patches/v16_0/s206_seed_intercompany_accounts.py` |
| CREATE | `hrms/tests/test_s206_punch_allocation.py` |
| CREATE | `hrms/tests/test_s206_labor_allocation.py` |
| MODIFY | `hrms/hooks.py` (append scheduler_events entry) |
| MODIFY | `hrms/patches.txt` (append patch row) |

## Zero-Skip Enforcement

**Phase-end gate (run this BEFORE advancing to next phase):**

```bash
# Confirm MUST_MODIFY files are in git diff
git diff --name-only origin/production...HEAD | grep -E "<expected files for this phase>"

# Confirm MUST_CONTAIN patterns
grep -l "<pattern>" <file>
```

If any MUST_MODIFY / MUST_CONTAIN assertion fails, the phase is NOT complete. Fix the failing task before advancing. NO silent skipping. NO "deferred to next sprint".

**Forbidden agent behaviors:**
- Skipping a task
- Marking partial work as "done"
- Replacing a task with a simpler version without user approval
- Saying "deferred to next sprint"
- Implementing happy path only, skipping DM-1/DM-2/DM-6 compliance

## Failure Response

- **App bug** — file `[BUG]` entry in `output/s206/defects/DEFECT_REGISTER.csv`, don't touch test or library, re-run after fix.
- **Test bug** — fix the test; if the fix helps other tests, promote to shared fixture.
- **Brittleness / flakiness** — fix the LIBRARY (`punch_allocation.py` / `labor_allocation.py`), not the spec. No `waitForTimeout`, no retry masking.

If ≥3 library fixes happen during execution, emit `output/l3/s206/LIBRARY_IMPROVEMENTS.md` as closeout artifact.

## Autonomous Execution Contract

- **completion_condition:** see plan YAML
- **stop_only_for:**
  - Missing intercompany accounts on >10 Companies (Phase 0 HARD BLOCKER)
  - Sam/Finance decision needed on allocation methodology (shift-share vs hour-share) if Phase 1 smoke test reveals data quality issues
  - Destructive mutation requires approval (always dry-run first)
  - Merge conflict on production
- **continue_without_pause_through:** audit → execute → PR → L3 handoff
- **signoff_authority:** single-owner (Sam)
- **canonical_closeout_artifacts:**
  - `output/s206/diagnostics/company_coa_audit.json`
  - `output/s206/diagnostics/intercompany_seed_report_*.json`
  - `output/l3/s206/{form_submissions,api_mutations,state_verification}.json`
  - `docs/plans/2026-04-17-sprint-206-reliever-allocation-engine.md` (status -> COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (S206 row updated)

## Dependencies

- **S201 Option X** (PR #606) — MERGED. Provides `company_lookup.py` + `non_store_billing.py` libraries + stable Employee.company semantics.
- **S175** — MERGED. Provides COA template structure with intercompany account slots.
- **S188** — MERGED. 49 per-store Companies exist.
- **S196** — MERGED. Companies use ALL CAPS store-first naming.

## Out of Scope (deferred)

- Hour-share allocation (v2 refinement if shift-share proves unreliable)
- Retroactive re-allocation when slips are amended post-post
- UI page for Finance to review+approve allocations (CLI + scheduler email for S206; UI in S208+)
- my.bebang.ph Company dropdown editability (separate task)
- Full statutory cross-check (B1 follow-up from S201 audit — verify SSS/PhilHealth/HDMF employer IDs populated on Frappe Company docs)

## Scope Size Warning

Total estimated units: **52** (within 80-unit single-session ceiling per S089). Single agent, single session.

## Agent Boot Sequence

1. Read this plan fully.
2. Verify on branch `s206-reliever-allocation-engine` (create via `git fetch origin production && git checkout -b s206-reliever-allocation-engine origin/production` if not already).
3. Read `hrms/utils/company_lookup.py`, `hrms/utils/non_store_billing.py`, `hrms/utils/device_mapping.py` to understand the S201 libraries you'll consume.
4. Read `hrms/api/commissary.py::fulfill_store_order` + `hrms/api/warehouse.py::create_stock_transfer` for JE construction patterns already in the codebase (good template for DM-1/DM-6 compliance).
5. Begin Phase 0.
