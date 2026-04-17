---
sprint: S201
title: Per-Store Employee Billing Foundation
branch: s201-per-store-employee-billing
base: production
status: DEPLOYED_PENDING_L3_AND_FINANCE_SIGNOFF
audit_date: 2026-04-17
audit_version: v2
audit_findings_path: output/plan-audit/s201/verified_blockers.md
open_policy_blockers: [B1, B2, B3, B4, B5, B15]  # Sam/Finance must sign off before S201_APPLY=1
planned_date: 2026-04-17
planned_by: Claude (BEI-ERP)
owner: Sam Karazi (CEO)
depends_on: [S188, S196]
followed_by: [S202]
estimated_units: 38
primary_repo: hrms
touches_frontend: false
l3_required: true
completion_condition: |
  - All 54 Employee.branch values renamed to match Company prefix (Analytics/ordering naming)
  - hrms/utils/company_lookup.py::resolve_branch_to_company shipped and tested
  - hrms/utils/non_store_billing.py::is_non_store_billing shipped and tested
  - Employee.validate() derives company from (is_non_store_billing ? BEI parent : branch→Company)
  - hrms/api/transfers.py::create_transfer updates new_company based on new_branch
  - One-time backfill patch reassigns ~510 store employees to per-store Companies
  - Commissary (44) employees confirmed under BEBANG KITCHEN INC.
  - L3: 6 scenarios pass with evidence in output/l3/s201/
  - Plan YAML status=COMPLETED and SPRINT_REGISTRY.md updated
stop_only_for:
  - Missing access (Frappe bench, Doppler, GH)
  - Destructive bulk mutation requires Sam approval
  - HO/store boundary ambiguity on a specific employee the rule can't classify
  - Merge conflict on production during rebase
---

# Sprint 201 — Per-Store Employee Billing Foundation

## Background

**What Sam asked for (2026-04-17 PHT):**
> When an employee punches in at a store (e.g., SM Megamall), they should be billed to that store/company — NOT BEI parent. Area Supervisors, Regional Managers, Projects, IT, Marketing stay on BEI. Store employees (OIC, Production, Cashier, Supervisors) bill to their store's Corp. Relievers bill by punch location. Data from April 01, 2026 forward (no retro to Feb).

**Why this matters:**
- Without this, per-store P&L is fiction. All 541 BEI-group employees post to `BEBANG ENTERPRISE INC.` parent — store Companies show zero labor.
- S188 created 49 per-store child Companies. S196 renamed them to ALL CAPS store-first (e.g. `SM MEGAMALL - BEBANG ENTERPRISE INC.`). The Employee-Company wiring was never done.
- S201 is the **foundation**. S202 will add punch-based reliever allocation (month-end JE reclassification).

## Current State (verified 2026-04-17)

| Fact | Value | Evidence |
|---|---|---|
| Employees on `BEBANG ENTERPRISE INC.` parent | 541 | Frappe tabEmployee |
| Employees on per-store Companies | 0 | Frappe tabEmployee |
| Employees with `branch` set | 539 / 542 | Frappe tabEmployee.branch |
| Per-store Companies post-S196 | 49 | `entity_category='Store'` |
| Roving / AS / HO employees (hardcoded) | 27 | `hrms/utils/roving_employees.py` |
| EMPLOYEE_MASTER.csv HO dept count | ~45 (Finance, HR, Marketing, Projects, Admin, Exec, Audit, R&D, IT, BD) | `data/_FINAL/EMPLOYEE_MASTER.csv` |
| EMPLOYEE_MASTER.csv Commissary dept | 44 | Same CSV |
| EMPLOYEE_MASTER.csv Operations dept | 565 + 12 (case drift) | Same CSV |

**Root cause of the gap:** `hrms/api/transfers.py:75-76` hardcodes `new_company=emp_doc.company` — the existing Transfer API literally never changes Company when branch changes.

## Locked Decisions (Sam, 2026-04-17)

| ID | Decision | Source |
|---|---|---|
| LD-1 | Store employees (OIC, Production, Cashier, Store/Assistant Supervisors) → `Employee.company = <store's child Company>` | Sam Q1&2 |
| LD-2 | Non-store employees (AS, Regional Manager, Projects, IT, Marketing, Finance, HR, Legal, Admin, Executive, Audit, R&D, BD) → `Employee.company = BEBANG ENTERPRISE INC.` | Sam Q1&2 |
| LD-3 | Commissary employees → `Employee.company = BEBANG KITCHEN INC.` (existing BKI company) | Sam Q4 |
| LD-4 | Rename Employee.branch values to match Analytics/ordering Company prefix (e.g. `AYALA UPTC` → `AYALA UP TOWN CENTER`) | Sam Q3 |
| LD-5 | Reliever punch-based billing = S202 (follow-up sprint) | Sam Q1&2 |
| LD-6 | Data starts April 01, 2026 forward — no retroactive allocation to Feb 01 | Sam Q5 |
| LD-7 | Option C (shift-level split payslips) is OUT — violates PH statutory single-employer rule | Scoping |

## Requirements Regression Checklist

Before declaring COMPLETED, the executing agent MUST answer YES to each:

- [ ] Every store employee's `Employee.company` equals the store's child Company (e.g. `SM MEGAMALL - BEBANG ENTERPRISE INC.`) — not the parent.
- [ ] Every non-store employee (per LD-2 rules) `Employee.company` equals `BEBANG ENTERPRISE INC.`.
- [ ] Every Commissary dept employee `Employee.company` equals `BEBANG KITCHEN INC.`.
- [ ] No Employee has `branch` value that fails `resolve_branch_to_company(branch)`.
- [ ] `hrms/api/transfers.py::create_transfer` updates `new_company` when `new_branch` resolves to a different Company.
- [ ] The one-time backfill patch emits an audit log with before/after counts per Company.
- [ ] The 27 roving employees in `roving_employees.py` remain on `BEBANG ENTERPRISE INC.` even if their `home` branch has a store Company.
- [ ] Salary Slip generated against a store employee posts to the store's Company (not parent).
- [ ] L3 evidence files exist: `output/l3/s201/{form_submissions,api_mutations,state_verification}.json`.
- [ ] Plan YAML `status: COMPLETED` and SPRINT_REGISTRY.md row updated (per S092 closeout rule).

## Design Rationale (For Cold-Start Agents)

**Why Option A (home-store = Employee.company) + deferred Option B (reliever allocation JE to S202)?**

- PH payroll law (SSS, PhilHealth, Pag-IBIG, BIR 2316) requires one legal employer per period. Splitting payslips per punch location (Option C) breaks statutory filings. Rejected.
- Option A alone doesn't handle relievers fairly — 3 days at SM MOA by a Tanza employee still bill to Tanza. Insufficient per Sam's ask.
- Option B (monthly reclassification JE) delivers fair per-store P&L without breaking statutory. Post inter-Company JE: debit covered-store Salaries, credit home-store Salaries by punch share. This is the standard accounting practice for shared services.
- Splitting S201 (foundation) + S202 (allocation) avoids the 80-unit single-session ceiling (S089 rule). S201 is independently useful — fixes the Transfer bug, establishes branch→Company SSOT, enables per-store Salary Slip posting for stable-assignment employees.

**Why rename branches instead of aliasing?**
- Analytics + Store Ordering + Delivery Schedule all use Company prefix. Keeping a separate `branch` naming convention creates permanent alias debt (two names per store forever).
- Renaming in Frappe Branch doctype is safe (data migration) and eliminates the alias map altogether.

**Why not just blank Employee.branch and rely on Employee.company?**
- Branch drives geofence, attendance device selection, and scheduling. Employee.company is a legal entity. Both are needed.
- Going forward: branch = "where", company = "who pays". Punches populate Employee Checkin with branch-derived company for cost-center stamping in S202.

## Phase 0 — Preflight & Data Snapshot (3u)

- [ ] Snapshot current Frappe state: `frappe.db.sql("SELECT company, COUNT(*) FROM tabEmployee WHERE status='Active' GROUP BY company")` → `output/s201/diagnostics/pre_counts.json`.
- [ ] Snapshot current branch values: `SELECT DISTINCT branch FROM tabEmployee ORDER BY branch` → `output/s201/diagnostics/pre_branches.txt`.
- [ ] Snapshot Company list: `SELECT name, entity_category, parent_company FROM tabCompany ORDER BY name` → `output/s201/diagnostics/pre_companies.json`.
- [ ] Confirm 49 per-store Companies + parent `BEBANG ENTERPRISE INC.` + `BEBANG KITCHEN INC.` + known parents (`TUNGSTEN CAPITAL HOLDINGS OPC`, `TAJ FOOD CORP.`, `BEBANG MEGA INC.`, `IRRESISTIBLE INFUSIONS INC.`).

**Verification:** `jq '.[] | select(.company=="Bebang Enterprise Inc.") | .COUNT' output/s201/diagnostics/pre_counts.json` returns a number matching Frappe.

## Phase 1 — Branch → Company Mapping Table (6u)

Build the canonical lookup that drives everything else.

- [ ] Create `hrms/data_seed/branch_company_map.csv` with columns `branch_new, company_name, entity_category, notes`.
- [ ] Enumerate all 49 store Companies → add row `(store_prefix, full_company_name, Store, "")`.
- [ ] Add HO/Commissary rows:
  - `BRITTANY OFFICE, BEBANG ENTERPRISE INC., Head Office, "HO — BEI parent"`
  - `COMMISSARY, BEBANG KITCHEN INC., Commissary, "BKI — commissary"`
- [ ] Map 54 current branch values → new branch names matching Company prefix (use Company list from Phase 0 as SSOT). Write mapping table `hrms/data_seed/branch_rename_map.csv` with columns `old_branch, new_branch`.
- [ ] Spot-check 10 known drift cases: `AYALA UPTC`→`AYALA UP TOWN CENTER`, `XENTRO MONTALBAN`→`XENTROMALL MONTALBAN`, `SHAW BLVD`→`SHAW BLVD`, etc.

**Verification:** All 54 current branches resolve to exactly one of: 49 store Companies, BEI parent, BKI commissary.

## Phase 2 — `company_lookup` Utility (5u)

- [ ] Create `hrms/utils/company_lookup.py` exposing:
  - `resolve_branch_to_company(branch: str) -> str` — returns Company name, raises `UnknownBranch` on miss.
  - `resolve_company_to_branch(company: str) -> str | None` — inverse for reporting.
  - `get_non_store_parent() -> str` — returns `BEBANG ENTERPRISE INC.`.
  - `get_commissary_company() -> str` — returns `BEBANG KITCHEN INC.`.
  - Internal cache: 60s TTL (same pattern as `sales_location_mapping.py`), invalidated by `clear_cache()`.
- [ ] Wire `on_update` hook on Branch doctype and Company doctype to call `clear_cache()`.
- [ ] Write unit tests covering: known store, HO/Brittany, Commissary, unknown branch (raises), case-insensitive lookup.

**Verification:** `python -c "from hrms.utils.company_lookup import resolve_branch_to_company; print(resolve_branch_to_company('SM MEGAMALL'))"` prints `SM MEGAMALL - BEBANG ENTERPRISE INC.`.

## Phase 3 — `is_non_store_billing` Rule (5u)

Reshape the 27-employee roving dict into a broader HO/non-store classifier.

- [ ] Create `hrms/utils/non_store_billing.py` with:
  - `is_non_store_billing(employee_doc) -> bool` — returns True if employee is a non-store biller (i.e. stays on BEI parent).
  - Rule set (evaluated in order):
    1. `department` in `{"Finance and Accounting", "Marketing", "HR and Admin", "Projects", "Admin", "Executive", "Audit", "R&D", "IT", "Business Development", "Legal"}` → True.
    2. `designation` contains any of `{"Area Supervisor", "Regional Manager", "Operations Manager", "Area Coordinator"}` → True.
    3. `bio_id` in `ROVING_EMPLOYEES` dict → True (keep explicit override list).
    4. Otherwise → False (= store biller).
- [ ] Keep `ROVING_EMPLOYEES` dict for backward compat + device authorization, but non-store rule is broader.
- [ ] Write unit tests covering each rule branch + edge cases (empty department, case variants like "OPERATIONS").

**Verification:** Running `is_non_store_billing()` across all 696 EMPLOYEE_MASTER.csv rows, count classifiers — expect ~80 non-store (45 HO + 9 AS + 27 roving overlap) and ~610 store + 44 commissary. Dump to `output/s201/diagnostics/classifier_results.csv`.

## Phase 4 — Employee.validate() Hook (5u)

- [ ] Extend `hrms/hr/doctype/employee/employee.py` (or add override via `hooks.py` `doc_events`) with `derive_company_from_branch` hook that runs in `validate()`:
  - If `is_non_store_billing(doc)`: set `doc.company = get_non_store_parent()` (BEI).
  - Elif `department in {"Commissary"}` (case-insensitive): set `doc.company = get_commissary_company()` (BKI).
  - Elif `doc.branch`: set `doc.company = resolve_branch_to_company(doc.branch)`.
  - Else: leave unchanged (no-op — manual override possible for HR Manager).
- [ ] HR Manager role bypass: if user has `HR Manager` role AND company was manually changed in this save, skip derivation. (Allows overrides for edge cases.)
- [ ] Add Frappe Sentry context per DM-7 if the hook becomes an `@frappe.whitelist()` endpoint — currently it's a validate hook so Sentry auto-captures via `frappe.log_error`.

**Verification:** Create a test employee with branch="SM MEGAMALL" dept="Operations" designation="CASHIER" → save → company becomes `SM MEGAMALL - BEBANG ENTERPRISE INC.`. Change dept to "IT" → save → company becomes `BEBANG ENTERPRISE INC.`.

## Phase 5 — Transfer API Fix (5u)

- [ ] Edit `hrms/api/transfers.py::create_transfer` (lines ~71-77):
  - Replace `"new_company": emp_doc.company` with:
    ```python
    new_company = resolve_branch_to_company(new_branch)
    if is_non_store_billing(emp_doc):
        new_company = get_non_store_parent()  # roving stays on parent even when branch changes
    # ... build transfer_details with Company row if new_company != emp_doc.company
    ```
  - Append `Company` row to `transfer_details` when `new_company != emp_doc.company`.
- [ ] Add Sentry context (DM-7): `module="hr", action="create_transfer", mutation_type="update"`.
- [ ] Write unit test: transfer store employee SM MEGAMALL → SM MOA should update Company to `SM MOA - BEBANG ENTERPRISE INC.`. Roving employee transfer SM MEGAMALL → SM MOA should keep Company = BEI parent.

**Verification:** `git diff hrms/api/transfers.py` shows `new_company` computed dynamically, not hardcoded.

## Phase 6 — Branch Rename Patch (5u)

- [ ] Create `hrms/patches/v15_bei/s201_rename_branches.py` that:
  1. Reads `hrms/data_seed/branch_rename_map.csv`.
  2. For each `(old_branch, new_branch)` pair where old ≠ new: `frappe.rename_doc("Branch", old_branch, new_branch, force=True, merge=True)`.
  3. Logs before/after counts of Employees per branch to `output/s201/diagnostics/branch_rename_report.json`.
- [ ] Append patch to `hrms/patches.txt`.
- [ ] Dry-run first: `--dry-run` flag that emits report without executing.

**Verification:** Post-patch, `SELECT DISTINCT branch FROM tabEmployee` returns branch names that all match Company prefixes. No residual old names.

## Phase 7 — Employee.company Backfill Patch (6u)

- [ ] Create `hrms/patches/v15_bei/s201_backfill_employee_company.py` that:
  1. For every Active Employee: compute target company via same logic as Phase 4 validate hook.
  2. If current != target: UPDATE `tabEmployee SET company = <target>` (direct SQL, bypassing Employee validate to avoid hook re-firing).
  3. Log each change row to `output/s201/diagnostics/backfill_log.csv` with columns `employee_id, name, old_company, new_company, reason`.
  4. Emit summary: before/after counts per Company.
- [ ] Append patch to `hrms/patches.txt`.
- [ ] HARD BLOCKER: patch must be `--dry-run` first. No direct execution without Sam approval confirming dry-run report.

**Verification:**
- Before: 541 on BEI parent, 0 on per-store Companies.
- After: ~45 on BEI parent (HO), ~9 AS + Regional Manager on BEI parent, 27 roving on BEI parent, ~44 on BKI, remainder (~510) distributed across 49 store Companies.
- `SELECT company, COUNT(*) FROM tabEmployee WHERE status='Active' GROUP BY company` output matches expected distribution.

## L3 Workflow Scenarios (per S092 corrupt-success rule)

Run these in a fresh Playwright session. Record each in `output/l3/s201/`.

| # | Scenario | Action | Verify |
|---|---|---|---|
| L3-1 | Store employee created with store branch | Create employee dept=Operations branch=`SM MEGAMALL` designation=CASHIER → Save | Form submits. Company field auto-populates to `SM MEGAMALL - BEBANG ENTERPRISE INC.`. Confirm via GET `/api/method/frappe.client.get_value?doctype=Employee&filters={"name":"..."}&fieldname=company`. |
| L3-2 | HO employee created with IT dept | Create employee dept=IT branch=BRITTANY OFFICE designation="System Administrator" → Save | Company = `BEBANG ENTERPRISE INC.`. |
| L3-3 | Commissary employee | Create employee dept=Commissary branch=COMMISSARY → Save | Company = `BEBANG KITCHEN INC.`. |
| L3-4 | Transfer store→store updates company | Pick store employee on `SM MEGAMALL - BEI`. Transfer to branch=SM MOA. Submit transfer. | After approval, Employee.company = `SM MOA - BEBANG ENTERPRISE INC.`. Transfer record shows Company change row. |
| L3-5 | Transfer roving employee stays on parent | Pick roving employee (bio 9000037). Transfer SM MEGAMALL → SM MOA. | After approval, Employee.company still = `BEBANG ENTERPRISE INC.`. |
| L3-6 | Salary slip posts to store Company | Generate Salary Slip for store employee (post-backfill) for April 2026 cutoff | Slip.company = store's Company. Journal Entry posts to that Company's books. |

**Evidence contract:**
- `form_submissions.json` — record of each form submit with payload + response.
- `api_mutations.json` — record of all `frappe.client.set_value` / `frappe.client.insert` calls and their before/after state.
- `state_verification.json` — post-action DB reads confirming final state.

## Phase 9 — Closeout

- [ ] Update plan YAML: `status: COMPLETED`, fill `completed_date`, `backend_pr`, `l3_result`.
- [ ] Update `docs/plans/SPRINT_REGISTRY.md` S201 row with status + PR number.
- [ ] Reserve S202 row (PLANNED — reliever allocation engine, depends on S201).
- [ ] `git add -f docs/plans/*.md output/s201/ output/l3/s201/ hrms/data_seed/branch_*.csv`.
- [ ] Commit + push + create PR to production.

## Rollback Contract

If backfill patch causes payroll regression:

1. Truncate `tabEmployee.company` back to parent: `UPDATE tabEmployee SET company = 'BEBANG ENTERPRISE INC.' WHERE company IN (<49 store companies> + 'BEBANG KITCHEN INC.')`.
2. Revert Phase 4 validate hook: `git revert` the hook commit.
3. Revert Phase 5 transfer fix: `git revert` the transfer commit.
4. Revert Phase 6 branch rename: apply inverse map from `branch_rename_map.csv` (swap columns).

## Files To Be Modified/Created

| Action | File |
|---|---|
| CREATE | `hrms/data_seed/branch_company_map.csv` |
| CREATE | `hrms/data_seed/branch_rename_map.csv` |
| CREATE | `hrms/utils/company_lookup.py` |
| CREATE | `hrms/utils/non_store_billing.py` |
| CREATE | `hrms/patches/v15_bei/s201_rename_branches.py` |
| CREATE | `hrms/patches/v15_bei/s201_backfill_employee_company.py` |
| CREATE | `hrms/tests/test_s201_company_lookup.py` |
| CREATE | `hrms/tests/test_s201_non_store_billing.py` |
| CREATE | `hrms/tests/test_s201_transfer_company_update.py` |
| MODIFY | `hrms/api/transfers.py` (Phase 5) |
| MODIFY | `hrms/hr/doctype/employee/employee.py` OR `hrms/hooks.py` (Phase 4) |
| MODIFY | `hrms/patches.txt` (register patches) |
| MODIFY | `hrms/utils/roving_employees.py` (keep dict, reshape exports) |

## Dependencies

- **S188** MERGED — 49 per-store Companies exist.
- **S196** MERGED — ALL CAPS store-first naming complete.
- **S200** MERGED — Analytics mapping uses Company prefix. Post-rename, Analytics leaderboard already correct.

## Out of Scope (deferred to S202)

- Punch-based monthly reliever allocation JE engine.
- Labor cost reclassification across Companies.
- Per-store labor P&L reporting.

## Notes

- `my.bebang.ph` frontend: no changes expected in S201. Company field on Employee Detail Dialog already reads from backend. Backfill makes it show correct value automatically.
- Frappe desk Employee form: Company field becomes read-only after Phase 4 hook is live, unless user has HR Manager role (manual override allowed).
- Backfill assumes EMPLOYEE_MASTER.csv counts are approximately correct — Phase 0 pre-counts are the authoritative baseline.

---

## POST-AUDIT AMENDMENTS (v2 — 2026-04-17)

Full audit report: `output/plan-audit/s201/verified_blockers.md`
Raw counts: 17 CRITICAL / 42 WARNING / 16 INFO across 5 domain agents.
After code verification: 7 CRITICAL / 18 WARNING CONFIRMED, 5 new code-level gaps.

### B5 — CORRECTED S201_APPLY invocation syntax

The original plan's Phase 6/7 instructions showed `S201_APPLY=1 bench --site hq.bebang.ph execute ...` in a plain shell. On production, `bench` runs inside a Docker container. Setting the env var in the host shell does NOT propagate through `docker exec`.

**Correct apply command (run from the EC2/host shell, not inside the container):**
```bash
docker exec -e S201_APPLY=1 $BACKEND_CONTAINER \
  bench --site hq.bebang.ph execute \
  hrms.patches.v16_0.s201_rename_branches.execute

docker exec -e S201_APPLY=1 $BACKEND_CONTAINER \
  bench --site hq.bebang.ph execute \
  hrms.patches.v16_0.s201_backfill_employee_company.execute
```

The `-e` flag is mandatory. Without it, `S201_APPLY` remains empty inside the container and the patch stays in dry-run mode silently.

### B9 — Commissary classification two-stage rule (plan text clarification)

The plan's Phase 4 task said "department == Commissary → BKI". Accurate description of the shipped code:

**Stage 1:** `is_non_store_billing(employee)` evaluates (bio_id in roving dict) → (designation keyword) → (department in HO_DEPARTMENTS) → (branch category == HO per map). If any returns True → `BEBANG ENTERPRISE INC.` (parent) and stop.

**Stage 2:** Otherwise, `resolve_branch_to_company(branch, department)` runs:
- Branch category `HO` → BEI parent (unreachable here because Stage 1 caught it)
- Branch category `Commissary`:
  - hint != `DEPT_DRIVEN` → the deterministic hint (BKI for SHAW COMMISSARY - PRODUCTION)
  - hint == `DEPT_DRIVEN` AND dept=Commissary → BKI
  - hint == `DEPT_DRIVEN` AND dept≠Commissary → BEI parent (SCM/R&D at commissary per Sam 2026-04-17)
- Branch category `Store` → live Frappe lookup for `<STORE_PREFIX> - <CORP>` Company

The rule is first-match-wins across Stage 1, then branch-driven in Stage 2. Department alone does NOT route to BKI in isolation — a "Commissary" dept employee at a store branch would route to that store's Company, and a "Commissary" dept employee at `SHAW COMMISSARY - LOGISTICS` routes to BEI parent (LOGISTICS branch is HO category per SCM rule).

### B10 — HR Manager override flag is unwired (known)

`flags.company_manual_override` is read in `hrms/overrides/employee_master.py::derive_company_from_branch` but never set anywhere. There is no Custom Field, no Form JS, no API to set it. Accepted as known limitation for S201:

- No employee today needs an override that the classifier can't handle.
- When the first real override case arises, wire it via (a) a boolean Custom Field on Employee set by HR Manager before save, OR (b) a Form JS that toggles `cur_frm.doc.flags.company_manual_override = 1` when HR Manager edits the Company field manually.

### B11 — Zero-Skip Enforcement (S154 — retrofit)

**PHASE COMPLETION GATE (mandatory per phase):**

Before advancing to Phase N+1, the executing agent MUST:

1. Run the phase's `Verification` bullet to PASS.
2. Run `git diff --name-only origin/production...HEAD` and confirm every file in the phase's "Files To Be Modified" table appears in the diff.
3. Append to `output/s201/phase_status.md`:
   ```
   ## Phase N — <title>
   - Status: DONE
   - Verification: <result of Verification step>
   - Files modified: <list from git diff>
   - Timestamp: <ISO>
   ```

If ANY verification fails, the agent MUST fix the failing task before advancing. Skipping a phase's Verification = corrupt success per S092.

### B12 — Machine-verifiable MUST_MODIFY / MUST_CONTAIN (S154 — retrofit)

Per-phase assertions the executing agent MUST check via `grep` before marking Phase done:

| Phase | MUST_MODIFY | MUST_CONTAIN |
|---|---|---|
| P2 | `hrms/utils/company_lookup.py` | `def resolve_branch_to_company`, `UnknownBranch`, `_CACHE_TTL` |
| P3 | `hrms/utils/non_store_billing.py` | `is_non_store_billing`, `HO_DEPARTMENTS`, `REGIONAL MANAGER` |
| P4 | `hrms/overrides/employee_master.py` | `derive_company_from_branch`, `is_non_store_billing_doc` |
| P4 | `hrms/hooks.py` | `hrms.overrides.employee_master.derive_company_from_branch`, `Branch.*on_update.*company_lookup.clear_cache`, `Company.*on_update.*company_lookup.clear_cache` |
| P5 | `hrms/api/transfers.py` | `_derive_new_company`, `resolve_branch_to_company`, `new_company = _derive_new_company(emp_doc, new_branch)` |
| P6 | `hrms/patches/v16_0/s201_rename_branches.py` | `S201_APPLY`, `savepoint("s201_rename_branches")`, `frappe.rename_doc("Branch"`, `frappe.log_error` |
| P7 | `hrms/patches/v16_0/s201_backfill_employee_company.py` | `S201_APPLY`, `savepoint("s201_backfill_employee_company")`, `UPDATE \`tabEmployee\` SET company`, `frappe.log_error` |
| P7 | `hrms/patches.txt` | `s201_rename_branches`, `s201_backfill_employee_company` |

### B13 — Protected Surfaces (S087 — retrofit)

Files the S201 executing agent and any follow-up agent MUST NOT touch:

- `hrms/utils/roving_employees.py` — 27-employee authoritative registry (IT Biometric Audit). Only HR/IT adds new roving entries, NOT code refactors.
- `hrms/overrides/employee_master.py::EmployeeMaster.validate` — contains S172 BEI-EMP-YYYY-NNNNN preservation logic. Do NOT refactor; the class-based override must continue to snapshot + restore `self.employee`.
- Existing Transfer DocType fields (`company`, `new_company`, `transfer_details` schema) — only WRITE via the API, do NOT alter DocType definition.
- Any Salary Slip / Payroll Entry created BEFORE S201 apply date — backfill MUST NOT touch their `company` field.

### B14 — L3 delivery contract

Current state (2026-04-17): `output/l3/s201/` does not exist and there is no Playwright script for S201 scenarios.

**L3 delivery path (either A or B, not both):**

- **Path A — Playwright:** Author `../bei-tasks/tests/playwright/s201-per-store-billing.spec.ts` covering the 6 scenarios. Run via `npm test -- s201`. Evidence: Playwright's JSON report piped to `output/l3/s201/form_submissions.json`.
- **Path B — Python + Frappe API:** Author `scripts/l3/s201_employee_company.py` that uses the Frappe REST API (session token auth) to create test employees, transfer employees, verify responses. Evidence: script writes to `output/l3/s201/{form_submissions,api_mutations,state_verification}.json`.

Either path MUST run in a FRESH agent session (not the builder session) per S092 corrupt-success rule.

### B15 — S202 maximum tolerable gap

S201 ships Employee.company = home-store. Relievers who cover OTHER stores have their labor billed to HOME store (not covered store) between S201 apply and S202 deploy. Estimated exposure: ~27 roving + AS employees × ~PHP 30K avg monthly = ~PHP 810K/month mis-allocated.

**Hard deadline:** S202 MUST ship before **May 15, 2026** payroll cutoff (half-month for May 1-15). After that date the April + early-May mis-allocation becomes financially material and may require manual JV reclassification.

If S202 slips past May 15: Sam must either (a) accept the mis-allocation as non-material and let it flow through, or (b) run a manual reclassification JE for April-May.

### Open policy blockers (Sam + Finance sign-off required BEFORE running S201_APPLY=1)

These are NOT code issues — they are policy decisions the plan didn't address.

- **B1:** SSS/PhilHealth/HDMF 49 employer registrations confirmed live? (If not, remittance filings post-backfill are ambiguous.)
- **B2:** BIR Form 2316 treatment for mid-year employer change (issue one from parent through April, one per child from May? or one consolidated across parent+children?).
- **B3:** Pre-existing April 2026 Draft/Submitted Salary Slips — cancel + regenerate post-backfill, or accept the discontinuity?
- **B4:** Apply timing — wait for next cutoff boundary (e.g., April 30 → May 1), or apply now and regenerate mid-period slips?
- **B15:** S202 deadline confirmed for May 15 or different date?

### Audit-driven code fixes (shipped in follow-up PR)

- Added `hrms.utils.company_lookup.clear_cache` to `Company.on_update` hook list (cache invalidation gap).
- Wrapped both patches (`s201_rename_branches`, `s201_backfill_employee_company`) in `frappe.db.savepoint()` with rollback-on-partial-failure — prevents torn batch commits.
- Routed patch failures through `frappe.log_error()` instead of `frappe.logger().error()` so Sentry captures them per DM-7.
