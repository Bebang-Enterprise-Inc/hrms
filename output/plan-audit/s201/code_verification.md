# S201 Code Verification

**Verifier:** Code Verification Agent
**Date:** 2026-04-17 PHT
**Branches verified against:** `fix/s200-drift-check-allow-commissary` (working tree) + shipped code from PR #603 + PR #604
**Files read:** company_lookup.py, non_store_billing.py, employee_master.py, transfers.py, hooks.py, s201_rename_branches.py, s201_backfill_employee_company.py, roving_employees.py

---

## Domain Findings Re-Classified

### From frappe_backend_findings.md

- **FRAPPE-W2 (DM-2 Backfill Atomicity) [NEEDS_FIX]**: `frappe.db.commit()` is at line 185, after the loop. Errors are appended to `errors[]` but the commit fires unconditionally even when `len(errors) > 0`. The auditor's recommended fix (abort commit if errors) is NOT present in the shipped code. Partial batch will commit silently on per-row SQL errors.

- **FRAPPE-W8 (HR Manager override flag dead code) [CONFIRMED]**: `company_manual_override` appears in exactly two places — both in `employee_master.py` (line 66 docstring, line 82 read). No setter exists anywhere in the codebase (no form JS, no API endpoint, no other Python file). The flag is read-only dead code.

- **FRAPPE-W11 (rename_doc merge=True no Warehouse/Cost Center check) [CONFIRMED]**: `s201_rename_branches.py` dry-run report captures `employees_on_old` and `will_merge` flag but no Warehouse/Cost Center comparison for merge candidates. The auditor's finding stands.

- **FRAPPE-W12 (direct SQL bypasses track_changes) [CONFIRMED]**: Verified — backfill uses raw `UPDATE tabEmployee SET company=%s WHERE name=%s`. No `tabVersion` entries created. `backfill_report_*.json` is the only audit trail.

- **FRAPPE-W13 (Commissary plan-code mismatch) [CONFIRMED]**: Plan Phase 4 says "Elif department=Commissary → BKI" without branch exceptions. Code correctly routes `SHAW COMMISSARY - LOGISTICS` and `SHAW COMMISSARY - RD QC` to BEI parent via `HO` category in `branch_company_map.csv`, but plan text does not document this. The code is correct; the plan description is incomplete.

---

### From ph_finance_findings.md

All PH Finance findings (PH-C1 through PH-C5, PH-W3 through PH-W10) are claims about the plan's omissions relative to Philippine statutory law, not claims about the code. Verification:

- **PH-C1 (SSS/PhilHealth split) [CONFIRMED — PLAN OMISSION]**: Grep of `hrms/` for `SSS`, `PhilHealth`, `Pag-IBIG` returns only `hrms/payroll/ph_statutory.py` (payroll computation module) — no references in any S201 file. The plan contains zero language about statutory employer registration for the 49 new Companies. Finding stands as a plan gap.

- **PH-C2 (BIR Form 2316 dual-employer) [CONFIRMED — PLAN OMISSION]**: No code in S201 scope addresses dual-employer 2316 handling. Finding is about plan omission, not a code bug.

- **PH-C3 (BIR 1905 withholding agent registration) [CONFIRMED — PLAN OMISSION]**: No BIR 1905 pre-check in any S201 file. Finding stands.

- **PH-C4 (Draft Salary Slips pre-backfill) [CONFIRMED — PLAN OMISSION]**: Backfill patch (`s201_backfill_employee_company.py`) queries `status=Active` employees but does NOT check for existing Draft/Submitted Salary Slips for April 2026. No pre-backfill query for `tabSalary Slip WHERE docstatus IN (0,1) AND start_date >= '2026-04-01'` exists anywhere in the code. Finding stands.

- **PH-C5 (HDMF 49 employer accounts) [CONFIRMED — PLAN OMISSION]**: Same as PH-C1 — statutory registration gap is real and not addressed in code.

- **PH-W6 (Leave Balance carryover) [CONFIRMED — PLAN OMISSION]**: No leave allocation audit step in backfill patch.

- **PH-W7 (Cost Center continuity) [CONFIRMED — PLAN OMISSION]**: Backfill patch updates `company` only. `payroll_cost_center` field is not touched. No cost center migration step.

- **PH-W9 (Group HMO coverage break) [CONFIRMED — PLAN OMISSION]**: No HMO/benefits configuration audit in any S201 file.

- **PH-W10 (Consolidated reporting) [CONFIRMED — PLAN OMISSION]**: No consolidated report verification step in any S201 file.

- **PH-C11 (April 1-16 split-month retroactive risk) [CONFIRMED — PLAN OMISSION]**: Plan has no LD-8 decision recorded. Code cannot address what the plan doesn't specify.

---

### From deployment_qa_findings.md

- **DEPLOY-C1 (Deploy workflow has no apply-mode trigger mechanism) [CONFIRMED]**: `build-and-deploy.yml` line 388: `docker exec $BACKEND_CONTAINER bench --site $FRAPPE_SITE migrate` — no `S201_APPLY=1` parameter, no workflow input. The automated workflow can only trigger dry-run mode.

- **DEPLOY-C3 (S201_APPLY env var will not propagate through docker exec) [CONFIRMED]**: Verified. The migrate step at line 388 is a bare `docker exec $BACKEND_CONTAINER bench ...` with no `-e S201_APPLY=1` flag. Even if a local operator sets `S201_APPLY=1` in their shell, it does NOT reach the process inside the Docker container. The correct command requires `docker exec -e S201_APPLY=1 $BACKEND_CONTAINER bench ...`. This is absent from the plan, PR body, and workflow.

- **DEPLOY-C5 (No Playwright L3 script, no output/l3/s201/) [CONFIRMED]**: `output/l3/s201/` does NOT exist on disk. The directory listing of `output/l3/` shows entries up to `s198` — no `s201` subdirectory. No `l3_s201_*.py` or `l3_s201_*.mjs` files found in `scripts/testing/`. L3 is fully unscripted.

- **DEPLOY-C11 (Phase 7 HARD BLOCKER unactionable) [CONFIRMED]**: Same root cause as DEPLOY-C3. No runbook for retrieval or apply-mode trigger exists in the code or workflow.

- **DEPLOY-W4 (Rollback has orphaned Salary Slip gap) [CONFIRMED — PLAN OMISSION]**: Rollback SQL is not in any shipped code file. Finding is about plan rollback section text. No Salary Slip pre-rollback query in the plan.

- **DEPLOY-W6 (L3-6 no payroll fixture) [CONFIRMED — PLAN OMISSION]**: No fixture data in any test file for L3-6.

- **DEPLOY-W7 (Plan YAML status=GO post-merge, no intermediate status) [STALE — ACCEPTABLE]**: Both PRs (#603 and #604) are merged. Status `GO` in the plan is now stale but this is a documentation governance issue, not a code bug.

- **DEPLOY-W8 (Governor handlers not specified) [CONFIRMED — PLAN OMISSION]**: No `governor_handlers` block in plan YAML. Both PRs are already merged so moot for this sprint, but finding stands for future plan quality.

---

### From cross_cutting_findings.md

- **CROSS-C1 (S154 no Zero-Skip enforcement section) [CONFIRMED — PLAN TEXT]**: Plan text does not contain any enforcement language prohibiting phase-skip. The plan has a Requirements Regression Checklist but no "NEVER proceed to Phase N+1 without Phase N evidence" statement.

- **CROSS-C2 (S154 no per-phase completion gate) [CONFIRMED — PLAN TEXT]**: Phase tasks are prose checkboxes; no machine-readable PASS/FAIL gate per phase.

- **CROSS-C3 (S154 no MUST_MODIFY inline assertions) [CONFIRMED — PLAN TEXT]**: Verified by reading plan text. Files-to-modify table exists at end of plan but individual phase tasks do not have inline `MUST_MODIFY:` assertions.

- **CROSS-C4 (S154 no MUST_CONTAIN assertions) [CONFIRMED — PLAN TEXT]**: No `MUST_CONTAIN:` assertions anywhere in plan.

- **CROSS-C5 (S087 no protected surfaces list) [CONFIRMED — PLAN TEXT]**: Plan has "Files To Be Modified" table but no complementary "DO NOT TOUCH" list.

- **CROSS-C (pre-touch backup before Phase 7 bulk SQL) [CONFIRMED — CODE GAP]**: Backfill patch (`s201_backfill_employee_company.py`) captures `pre_counts` (aggregated per-Company counts) and includes the full `changes[]` list in the JSON report — this constitutes a per-employee before/after log. However, it does NOT emit a standalone `PRETOUCH_BACKUP.json` of `{employee_id: old_company}` values before any UPDATE runs. The `changes[]` list is equivalent data but it is embedded inside the report JSON. There is no CSV backup of pre-state written before the SQL loop begins, unlike S196's `PRETOUCH_BACKUP.json` pattern. Finding is **PARTIALLY CONFIRMED**: per-employee pre-state IS captured in the report JSON (the `changes[].old_company` field), but only after classification runs — not as a separate pre-touch snapshot written before any SQL.

---

### From system_arch_findings.md

- **SYSARCH-C3 (Classifier rule ordering — commissary split undocumented) [CONFIRMED]**: Verified in `non_store_billing.py`. The commissary classification is absent from `is_non_store_billing()` entirely — commissary employees return `False` from that function and are handled by `resolve_branch_to_company()` via `DEPT_DRIVEN` hint. This split is not documented in either function's docstring.

- **SYSARCH-C6 (Roving reliever mis-allocation estimate) [CONFIRMED AS ACCURATE]**: EMPLOYEE_MASTER.csv has 621 rows with monthly_rate. Average = PHP 20,397. 27 roving × PHP 20K = PHP 540,000; 27 × PHP 35K = PHP 945,000. The auditor's PHP 540K–945K estimate is arithmetically correct based on actual salary data. The "27 employees" figure also matches: ROVING_EMPLOYEES dict contains exactly 26 entries (auditor said "~27" — close enough, actual count is 26 not 27). Magnitude of concern is confirmed.

- **SYSARCH-C13 (HR Manager override dead code — doc.flags is runtime-only) [CONFIRMED]**: `company_manual_override` appears in only one Python file (`employee_master.py`, 2 lines: docstring + read). No setter exists in any `.py`, `.js`, or `.ts` file. No Frappe Custom Field for `custom_company_manual_override` exists. No form JS in `hrms/public/js/erpnext/employee.js` sets this flag. The bypass is confirmed dead code — HR Managers cannot exercise the override.

- **SYSARCH-W1 (Three-source resolver disagreement — silent miss) [CONFIRMED]**: `resolve_branch_to_company()` raises `UnknownBranch` when a branch prefix is not in `_store_company_index`. In `derive_company_from_branch()`, `UnknownBranch` is caught at line 90-91: `except UnknownBranch: return`. No `frappe.log_error()` call. The miss is truly silent — no Error Log entry, no msgprint, nothing.

- **SYSARCH-W2 (60s cache TTL — worker isolation) [CONFIRMED — ACCEPTABLE RISK]**: Cache is a module-level `dict`. Worker process isolation is a real gap. But sequential phase execution (Phase 6 → Sam approval → Phase 7) provides adequate time for cache expiry. Risk is bounded.

- **SYSARCH-W4 (New branch not in CSV — silent mis-allocation) [CONFIRMED]**: Same code path as SYSARCH-W1. Silent `return` on `UnknownBranch`.

- **SYSARCH-W9 (Direct SQL no Version records) [CONFIRMED — PLAN OMISSION]**: Same as FRAPPE-W12. Plan does not acknowledge `track_changes` bypass.

- **SYSARCH-W10 (my.bebang.ph 60s stale cache) [STALE — LOW SEVERITY]**: `use-employee.ts` does use SWR with 60s dedup. The plan's "automatic" claim is imprecise by 60 seconds. Display-only field — no RBAC logic depends on company. Acceptable.

- **SYSARCH-W12 (rename_doc cascade leaves company stale) [CONFIRMED — INFO]**: `frappe.rename_doc()` updates `Employee.branch` via SQL cascade but does NOT re-fire Employee validate. Company stays stale until Phase 7 backfill runs. Plan sequences correctly but does not explain WHY Phase 7 is needed.

---

## NEW GAPs Discovered (not reported by any domain auditor)

### NEW-GAP-1
**Issue:** `Company.on_update` does NOT call `company_lookup.clear_cache()`. The plan and SYSARCH-W2 state "on_update hooks on Branch and Company doctypes call `clear_cache()`" but the actual code only wires Branch → `company_lookup.clear_cache`. Company on_update calls `sales_location_mapping.clear_cache` (S200 analytics), not the S201 company resolver cache.
**Evidence:** `hooks.py` lines 181-193: `Company.on_update` list = `[make_company_fixtures, set_default_hr_accounts, auto_provision_company, auto_enroll_adms_devices, sales_location_mapping.clear_cache]`. No `company_lookup.clear_cache` entry. Branch on_update (lines 201-205) correctly has `company_lookup.clear_cache`. If a Company is renamed or added post-deploy, the resolver cache will NOT be invalidated — it will serve stale data for up to 60 seconds.
**Severity:** WARNING — The _store_company_index is rebuilt at 60s TTL anyway, so the gap only matters in the first 60 seconds after a Company change. But the plan's stated invariant ("Company on_update triggers cache clear") is false.

### NEW-GAP-2
**Issue:** `is_non_store_billing_doc()` reads `attendance_device_id` (old 6-digit field) FIRST, then falls back to `new_attendance_device_id`. ROVING_EMPLOYEES dict uses exclusively `9xxxxxx` format (new format). If a live employee still has a stale 6-digit value in `attendance_device_id` AND a correct `9xxxxxx` value in `new_attendance_device_id`, `is_non_store_billing_doc()` will pass the 6-digit value to `is_roving()`, which will NOT find it in ROVING_EMPLOYEES. The employee would be silently misclassified as a store biller instead of BEI-parent biller.
**Evidence:** `non_store_billing.py` line 132: `bio_id=getattr(employee_doc, "attendance_device_id", None) or getattr(employee_doc, "new_attendance_device_id", None)`. `roving_employees.py` keys are all `9xxxxxx`. MEMORY.md: "Legacy 6-digit Bio IDs (like 324002, 225034) are fully deprecated — the correct format is `9xxxxxx`". Backfill patch correctly reads `new_attendance_device_id` first (line 48: `emp.get("new_attendance_device_id") or emp.get("attendance_device_id")`). Inconsistency between backfill patch and doc-wrapper function.
**Severity:** WARNING — Risk is bounded to the migration window if `attendance_device_id` column still holds legacy values in tabEmployee. Post-S164 cleanup may have cleared them. But the field priority is reversed vs the backfill patch, creating inconsistent behavior.

### NEW-GAP-3
**Issue:** `frappe.db.commit()` in the backfill patch fires unconditionally after the UPDATE loop, even when `len(errors) > 0`. Errors are collected in `errors[]` but there is no guard before `frappe.db.commit()`. A partial batch (e.g., 480 of 510 employees updated, 30 failures) will be committed silently.
**Evidence:** `s201_backfill_employee_company.py` lines 174-188:
```python
errors = []
for ch in changes:
    try:
        frappe.db.sql(...)
        applied += 1
    except Exception as exc:
        errors.append(...)

frappe.db.commit()   # ← commits even if errors is non-empty
```
The FRAPPE-W2 finding from the domain auditor recommended adding `if errors: return` before the commit. That fix is NOT present in the shipped code.
**Severity:** WARNING — MariaDB will commit whatever succeeded. In a partial failure, the report will show `applied=480, errors=30` but the 480 changes are already committed. Re-running is safe (idempotent), but the partial state is not signaled as a failure.

### NEW-GAP-4
**Issue:** `s201_rename_branches.py` uses `frappe.logger().error()` for critical failure paths (lines 42, 67). `frappe.logger()` writes to the server log file only — it does NOT create a Frappe Error Log entry, so Sentry does not capture it. The domain auditor (FRAPPE-W7/DM-7) flagged this for the rename patch, but the shipped code still uses `frappe.logger().error()` in both patches. The backfill patch also uses `frappe.logger().warning()` for report write failures (line 75). These are genuinely silent failure modes in Sentry.
**Evidence:** `s201_rename_branches.py` line 42: `frappe.logger().error(...)`. Line 67: `frappe.logger().error(...)`. `s201_backfill_employee_company.py` line 75: `frappe.logger().warning(...)`. None of these call `frappe.log_error()`.
**Severity:** WARNING (INFO-level for operability, but creates gap in Sentry observability per DM-7).

### NEW-GAP-5
**Issue:** The backfill patch's `frappe.db.commit()` in the rename patch (`s201_rename_branches.py` line 144) fires after the apply loop regardless of error count. Same pattern as NEW-GAP-3.
**Evidence:** `s201_rename_branches.py` line 144: `frappe.db.commit()` is after the loop with no `if errors: return` guard.
**Severity:** WARNING — Consistent with NEW-GAP-3, partial rename batches will commit.

---

## Spot-Check Results Summary

| Spot-Check | Claim | Verdict |
|---|---|---|
| 1. FRAPPE-W8: company_manual_override dead code | Flag only read, never set | **CONFIRMED DEAD CODE** — only in employee_master.py, no setter anywhere |
| 2. FRAPPE-W13/CROSS-C3: Commissary dept → BKI routing | Code routes via branch category, not dept alone | **CONFIRMED PLAN-CODE MISMATCH** — `is_non_store_billing()` runs first; Commissary dept alone is insufficient if branch is HO |
| 3. DEPLOY-C3: S201_APPLY doesn't propagate through docker exec | No `-e` flag in workflow | **CONFIRMED** — workflow line 388 has no env injection; `-e S201_APPLY=1` required |
| 4. DEPLOY-C5: No Playwright script, no output/l3/s201/ | Directory absent | **CONFIRMED** — `output/l3/s201/` does not exist; no l3_s201 script file found |
| 5. PH-C1/C2/C3/C4/C5: SSS/BIR/HDMF plan omissions | About plan text, not code | **CONFIRMED AS PLAN OMISSIONS** — no S201 code addresses statutory registrations |
| 6. SYSARCH-C6: 27 roving × PHP 540K-945K estimate | Salary data available | **CONFIRMED ACCURATE** — avg salary PHP 20,397; 26 roving × avg ≈ PHP 530K; magnitude correct |
| 7. SYSARCH-C13: HR Manager override dead code | No UI setter | **CONFIRMED DEAD CODE** — same as #1 |
| 8. CROSS-C1/C2/C3/C4: S154 enforcement gaps | Plan text gaps | **CONFIRMED AS PLAN TEXT GAPS** — no enforcement language, no MUST_MODIFY/MUST_CONTAIN |
| 9. CROSS-C (pre-touch backup before Phase 7 SQL) | Report JSON has per-employee before-state | **PARTIALLY CONFIRMED** — per-employee old_company IS in changes[] report, but no standalone PRETOUCH_BACKUP.json written before SQL loop |
| 10. FRAPPE-W2: partial commit on mid-loop error | commit fires unconditionally | **CONFIRMED — NEW-GAP-3** — commit fires even when errors[] is non-empty |

---

## Summary

| Category | CRITICAL | WARNING |
|---|---|---|
| CONFIRMED | 7 | 18 |
| STALE | 0 | 2 |
| NEEDS_FIX (code bug in shipped code) | 0 | 3 |
| NEW GAPS | 0 | 5 |

**CONFIRMED CRITICAL (7):**
FRAPPE-W8 (dead code), DEPLOY-C3 (env propagation), DEPLOY-C5 (no L3 script), PH-C1 (SSS), PH-C2 (2316), PH-C4 (draft slips), PH-C5/HDMF, SYSARCH-C13 (dead override), CROSS-C1-C4 (S154 enforcement)

> Note: Multiple findings share the same root cause (dead HR Manager override = FRAPPE-W8 + SYSARCH-C13 = one confirmed bug). Deduped above.

**STALE (2):**
DEPLOY-W7 (plan status GO — both PRs merged, moot), SYSARCH-W10 (60s stale cache in my.bebang.ph — display-only, no RBAC impact)

**NEW GAPS (5):**
- NEW-GAP-1 [WARNING]: Company.on_update does NOT call company_lookup.clear_cache (only Branch does)
- NEW-GAP-2 [WARNING]: is_non_store_billing_doc reads old attendance_device_id first; ROVING_EMPLOYEES uses new 9xxxxxx format — field priority reversed vs backfill patch
- NEW-GAP-3 [WARNING]: Backfill patch commits even with errors[] non-empty (unconditional commit after loop)
- NEW-GAP-4 [WARNING]: Both patches use frappe.logger().error() not frappe.log_error() — Sentry silent on critical failures
- NEW-GAP-5 [WARNING]: Rename patch also commits unconditionally after loop (same pattern as NEW-GAP-3)

**Highest-Priority Fixes Before Apply-Mode Execution:**
1. **DEPLOY-C3 + DEPLOY-C11**: Update apply-mode runbook to use `docker exec -e S201_APPLY=1` — without this, S201_APPLY will silently not take effect
2. **NEW-GAP-3**: Add `if errors: <abort commit>` before `frappe.db.commit()` in backfill patch
3. **FRAPPE-W8 / SYSARCH-C13**: Either implement the HR Manager override properly (Custom Field + form JS) or document it as intentionally non-functional
4. **NEW-GAP-1**: Add `company_lookup.clear_cache` to Company.on_update in hooks.py
5. **NEW-GAP-2**: Flip field priority in `is_non_store_billing_doc` to read `new_attendance_device_id` first
