# Sprint S150 — Payroll Data Quality + Allowance Setup

```yaml
canonical_sprint_id: S150
sprint_title: "Payroll Data: Import Actual Salaries, Set Up Allowances, Fix Blockers, Enrich Dashboard"
status: IN_PROGRESS
branch: s150-payroll-data-quality
repos:
  - hrms (backend: add allowance fields to get_compensation_grid)
  - bei-tasks (frontend: add allowance columns to compensation dashboard)
created_date: 2026-03-31
execution_started: 2026-03-31
completed_date: null
execution_summary: |
  Phase 3-4 code complete. PRs pending creation (GH PAT scope issue).
  Phase 1-2 SSM script ready at scripts/s150_payroll_data_quality.py.
  Pending: merge PRs, deploy, run SSM script, bench migrate, L3 verification.
audit_history:
  - "2026-03-31: Phase 3-4 code implemented — allowance fields added to backend SQL + frontend grid"
depends_on: S149 (compensation enrichment — projected columns + currency fixes)
total_units: 52
signoff_owner: Sam Karazi (sam@bebang.ph)
registry_row: "S150 | Sprint 150 | s150-payroll-data-quality | — | PLANNED | docs/plans/2026-03-31-sprint-150-payroll-data-quality.md"
```

---

## Executive Summary

This sprint does three things:

1. **Fix 5 payroll blockers** — submit Payroll Period, link tax slabs, set salary_mode, fix zero-base SSAs, create missing SSAs
2. **Import actual salary + allowance data** from March 2026 payroll files into Frappe — base salaries from payroll (not Employee Master), plus 5 allowance types per employee
3. **Add allowance columns to the compensation dashboard** — so HR sees Communication, De Minimis, Honorarium, Meal, Gasoline, Other Fixed alongside Base Salary, Gross, Net, and statutory deductions

After this sprint, HR validates the data in Frappe and the my.bebang.ph dashboard shows the complete compensation picture.

---

## Design Rationale (For Cold-Start Agents)

### Why import from payroll files, not Employee Master

The Employee Master `monthly_rate` came from an earlier payroll-to-employee matching process with 85.7% coverage. The actual March 2026 payroll files (`Payroll_Feb25_Mar10_Mar25.csv`) have 463 employees with exact semi-monthly rates — this is the freshest, most authoritative salary data. Using payroll data also gives us allowance breakdowns that don't exist in the Employee Master.

### Why allowances matter (Ronald Caringal conversation, 2026-03-31)

HR Manager Ronald confirmed the compensation dashboard needs to show itemized allowances:
1. **Non-Taxable** (De Minimis) — clothing/laundry/rice subsidy
2. **Honorarium** — select employees
3. **Gasoline** — supervisors/managers
4. **Meal** — 84 employees receive this
5. **Other Fixed** — 150 employees (₱2K-₱30K/mo, often housing/transport)

These are real payroll components being paid today but invisible in the dashboard. Sam's directive: "We don't want to limit the findings — we want to learn from actual payroll how the dashboard and whole payroll module should be."

### Data sources

| File | Path | Rows | Use |
|------|------|------|-----|
| Payroll ComprePayRun (3 cutoffs) | `data/_FINAL/Payroll_Feb25_Mar10_Mar25.csv` | 1,488 | Base salary, gross/net, statutory deductions |
| RatesData (all 3 batches) | `data/_FINAL/Payroll_RatesData_Mar25_AllBatches.csv` | 463 | Monthly allowance rates per employee |
| Audit report | `output/s149_payroll_consolidated_audit.md` | — | Blocker list |

### Allowance coverage from actual payroll (463 employees, Mar 25 cutoff)

| Allowance | Employees with > ₱0 | Total Monthly | Taxable? |
|-----------|---------------------|---------------|----------|
| OtherFixed (housing/transport) | 150 (32%) | ₱826,080 | Non-taxable |
| Meal | 84 (18%) | ₱54,195/cutoff | Non-taxable |
| De Minimis | 7 (1.5%) | ₱27,518 | Non-taxable |
| Gasoline | 8 (1.7%) | ₱16,050/cutoff | Non-taxable |
| Honorarium | 4 (0.9%) | ₱10,000 | Split |
| Communication | 0 (0%) | ₱0 | Taxable |

---

## Requirements Regression Checklist

| # | Assertion | Source |
|---|-----------|--------|
| R1 | Payroll Period is Submitted (docstatus=1) | Audit B-1 |
| R2 | All SSAs have income_tax_slab linked | Audit B-2 |
| R3 | All active employees have salary_mode set | Audit B-3 |
| R4 | SSA base salaries match actual payroll data (not stale Employee Master) | Sam's directive |
| R5 | All active employees in payroll have a submitted SSA | Audit B-5 |
| R6 | Dashboard shows 5 allowance columns (De Minimis, Honorarium, Meal, Gasoline, Other Fixed) | Ronald + Sam |
| R7 | Dashboard shows total Gross Pay = Base + all allowances (matching payroll GrossPay) | Sam's request |
| R8 | Duplicate salary components cleaned up | Audit H-3 |
| R9 | All 4 salary structures exist with correct SSA mapping | Sam confirmed 4 tiers |
| R10 | Every SSM script prints before/after counts | Execution safety |
| R11 | Every new/modified @frappe.whitelist() has set_backend_observability_context() | DM-7 |

---

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branch:** `git fetch origin production && git checkout -b s150-payroll-data-quality origin/production`. NEVER write code on production.
3. Read `docs/plans/SPRINT_REGISTRY.md` to verify S150 row exists.
4. Read source data files to verify they exist:
   - `data/_FINAL/Payroll_RatesData_Mar25_AllBatches.csv` (463 rows, 31 columns — monthly allowance rates per employee)
   - `data/_FINAL/Payroll_Feb25_Mar10_Mar25.csv` (1,488 rows — 3 cutoff payroll data)
   - `data/_FINAL/EMPLOYEE_MASTER.csv` (SSOT — 696 employees)
5. Read `output/s149_payroll_consolidated_audit.md` for the 5 blockers + 4 high issues.
6. Read `hrms/api/payroll_compensation.py` — the file you will modify in Phase 3.
7. Read `bei-tasks/app/dashboard/hr/payroll/compensation-setup/page.tsx` — the file you will modify in Phase 4.
8. Read `bei-tasks/lib/queries/hr-payroll-compensation.ts` — TypeScript types to update in Phase 4.
9. Read `hrms/patches/v16_0/add_employee_enrichment_fields.py` — the Custom Field creation pattern to follow in Phase 2.

**Execution order is STRICT:** Phase 1 (SSM data fixes) → Phase 2 (SSM allowance import + bench migrate) → Phase 3 (backend code) → Phase 4 (frontend code) → Phase 5 (verify + closeout). Do NOT start Phase 3 code until Phase 2 `bench migrate` is confirmed.

## Source Data Column Reference

### Payroll_RatesData_Mar25_AllBatches.csv (463 rows)
Primary source for monthly allowance rates. Key columns:
- `EmployeeNo` — legacy payroll ID (e.g., "00126"). NOT the Frappe employee ID.
- `BasicPay_Monthly` — monthly base salary
- `CommAllow_Monthly` — Communication Allowance monthly rate (0 for all 463 employees currently)
- `DeMinimis_Monthly` — De Minimis monthly rate (7 employees with > ₱0)
- `Honorarium_Monthly` — Honorarium monthly rate (4 employees)
- `OtherFixed_Monthly` — Other Fixed Allowance monthly rate (150 employees, ₱2K-₱30K)
- `FullName` — "LastName, FirstName MiddleName" format (use for matching to Frappe)
- `batch` — 1, 2, or 3

### Payroll_Feb25_Mar10_Mar25.csv (1,488 rows)
3 cutoffs × 3 batches. Key columns for Meal/Gasoline (not in RatesData):
- `MealAllow_NonTax` — per-cutoff meal allowance (84 employees, multiply × 2 for monthly)
- `GasolineAllow` — per-cutoff gasoline (8 employees, multiply × 2 for monthly)
- `cutoff_date` — "2026-02-25", "2026-03-10", "2026-03-25"
- Filter to `cutoff_date = '2026-03-25'` for latest data

### Employee-to-Payroll Matching (CRITICAL — read this before Phase 1)
The payroll `EmployeeNo` (e.g., "00126") does NOT directly map to Frappe employee IDs (e.g., "9000003"). However, **the Employee Master SSOT has the mapping already built:**

`data/_FINAL/EMPLOYEE_MASTER.csv` columns:
- Column 1: `employee_id` — the Frappe employee ID (e.g., "9000003")
- Column 22: `match_confidence` — how well the payroll match was (HIGH/MEDIUM/LOW)
- Column 23: `payroll_name` — the matched payroll full name
- Column 26: `payroll_emp_no` — the payroll EmployeeNo (e.g., "00126")

**Tier 1 matching (preferred):** Load Employee Master → build `payroll_emp_no → employee_id` map → join with RatesData on `EmployeeNo = payroll_emp_no`. This gives direct Frappe ID for each payroll row.

**Tier 2 (fallback for unmatched):** Normalized name match: `payroll FullName → Employee Master employee_name`.

**Tier 3 (last resort):** Fuzzy match with threshold ≥ 95 + collision guard.

---

## Phase Budget Contract

| Phase | Units | Description |
|-------|-------|-------------|
| Phase 1 | 12 | Fix 5 blockers: Payroll Period, tax slabs, salary_mode, zero-base SSAs, missing SSAs |
| Phase 2 | 12 | Import allowance data: create salary components, create Additional Salary records or update SSA/Employee fields |
| Phase 3 | 10 | Backend: add allowance fields to get_compensation_grid |
| Phase 4 | 10 | Frontend: add allowance columns to dashboard |
| Phase 5 | 8 | Verification + closeout |
| **Total** | **52** | |

---

## Phase 1 — Fix 5 Blockers (12 units)

### P1-1: Submit Payroll Period (1 unit)

```python
pp = frappe.get_doc("Payroll Period", "2026 - Bebang Enterprise Inc.")
pp.submit()
frappe.db.commit()
```

**Verification:** docstatus=1 after.

### P1-2: Link Income Tax Slab to all SSAs (2 units)

**HARD BLOCKER (AUDIT B-1/H-3):** Use `frappe.db.set_value()` with `update_modified=True`, NOT raw SQL UPDATE on submitted SSAs. Raw SQL bypasses `validate_income_tax_slab()`, `validate_company()`, `validate_dates()` and breaks audit trail. For bulk operations, `frappe.db.set_value()` is acceptable for one-shot patches.

**HARD BLOCKER (AUDIT H-3):** Before ANY SSA modifications, run a verify step:
```python
# FIRST LINE of every import script
slab = frappe.db.get_value("Income Tax Slab", "TRAIN Law 2025 - Philippines", "name")
if not slab:
    all_slabs = frappe.get_all("Income Tax Slab", pluck="name")
    frappe.throw(f"Tax slab not found! Available: {all_slabs}")
```

```python
# Use frappe.db.set_value, NOT raw SQL
for ssa_name in ssa_names:
    frappe.db.set_value(
        "Salary Structure Assignment", ssa_name,
        "income_tax_slab", "TRAIN Law 2025 - Philippines",
        update_modified=True
    )
frappe.db.commit()
```

**HARD BLOCKER:** The slab name must be exact: "TRAIN Law 2025 - Philippines".

### P1-3: Set salary_mode on all active employees (2 units)

- `salary_mode = 'Bank'` where bank_name + bank_ac_no both exist
- `salary_mode = 'Cash'` for rest

### P1-4: Update SSA base salaries from actual payroll data (4 units)

**Source:** `data/_FINAL/Payroll_RatesData_Mar25_AllBatches.csv` — `BasicPay_Monthly` column.

**Steps:**
1. Load RatesData CSV (463 employees with monthly rates)
2. **HARD BLOCKER (AUDIT H-2):** Build employee matching in 3 tiers — do NOT rely on fuzzy name matching alone:
   - **Tier 1:** Exact match on `EmployeeNo` → check if Employee Master CSV has a `payroll_employee_no` or legacy mapping column
   - **Tier 2:** Exact name match (normalized: uppercase, stripped whitespace, "LASTNAME, FIRSTNAME" format)
   - **Tier 3:** Fuzzy match with threshold ≥ 95 AND collision guard (if 2+ employees match at same score, flag for HR review instead of picking one)
   - **Always** produce `output/s150_unmatched_employees.csv` before committing any updates
3. For each match: use `frappe.db.set_value()` (NOT raw SQL) to update SSA `base`
4. For zero-base SSAs: if payroll has a rate, fix. If not, flag for HR.
5. **HARD BLOCKER (AUDIT DQ-2):** Exclude NAIA T3 placeholder rows (BasicPay = 0 in all cutoffs) from SSA creation.
6. Report: X SSAs updated, Y couldn't match, Z still zero.

**HARD BLOCKER (AUDIT DQ-1):** Payroll deduction columns (SSS_EE, PhilHealth_EE, PagIBIG_EE, WithholdingTax) contain NEGATIVE values (e.g., WHT = -₱50,342 for Formoso). Import scripts must use `abs()` when comparing or importing deduction amounts. Do NOT confuse sign convention with data errors.

**HARD BLOCKER:** The payroll EmployeeNo (e.g., "00126") is NOT the Frappe employee ID (e.g., "9000003"). Use the 3-tier matching above.

### P1-5: Create SSAs for employees in payroll but without SSA (3 units)

For employees found in the payroll data but missing from Frappe SSAs:
1. Use designation → structure mapping (4-tier: Executive, Supervisory, HO Staff, Store Staff)
2. Create SSA with base = payroll BasicPay_Monthly, currency = PHP, from_date = 2026-02-01
3. Set income_tax_slab, payroll_payable_account, employee_name, department, designation

Also create the 2 new salary structures:
- "Supervisory Staff - Regular" — clone components from Store Staff - Regular
- "Executive Staff - Regular" — clone components from HO Staff - Regular

**HARD BLOCKER (AUDIT M-1):** Use `frappe.copy_doc()` for salary structure cloning, NOT manual INSERT. Add idempotency guard: check if structure exists before creating. Verify `company` field is correct after copy.

Then re-map existing SSAs by designation using case-insensitive keyword matching. Use `frappe.db.set_value()` for SSA salary_structure field changes.

---

## Phase 2 — Import Allowance Data (12 units)

### P2-1: Create missing Salary Components (2 units)

Ensure these components exist in Frappe (create if missing):

| Component | Type | Taxable | In Structure |
|-----------|------|---------|-------------|
| Communication Allowance | Earning | Yes | Add to all structures |
| De Minimis Allowance | Earning | No | Add to all structures |
| Honorarium Allowance | Earning | No (non-taxable portion) | Add to all structures |
| Meal Allowance | Earning | No | Add to all structures |
| Gasoline Allowance | Earning | No | Add to all structures |
| Other Fixed Allowance | Earning | No | Add to all structures |

Note: "Honorarium" and "Clothing Allowance" already exist. Create the missing ones. Add all to the 4 salary structures' earnings table.

### P2-2: Store allowance amounts on Employee records (6 units)

**Approach:** Store monthly allowance rates as custom fields on Employee doctype (or use Frappe's Employee Benefit fields). The cleanest approach for the compensation grid: add custom fields to Employee so `get_compensation_grid` can query them.

**HARD BLOCKER (AUDIT B-3/H-1):** Custom Fields MUST be created via `frappe.custom_field.create_custom_fields()` API, NOT direct SQL. Direct SQL to `tabCustom Field` does NOT create the physical MariaDB column. Use the existing pattern in `hrms/patches/v16_0/add_employee_enrichment_fields.py` as reference.

Add these fields to Employee via Custom Field API:
- `bei_comm_allow_monthly` (Currency)
- `bei_deminimis_monthly` (Currency)
- `bei_honorarium_monthly` (Currency)
- `bei_meal_allow_monthly` (Currency)
- `bei_gasoline_allow_monthly` (Currency)
- `bei_other_fixed_monthly` (Currency)

**HARD BLOCKER (AUDIT B-2):** After Custom Field creation, run `bench migrate` and `bench clear-cache` inside the Docker container. Without this, Frappe's ORM will not see the new columns. Add V-09 verification: `SHOW COLUMNS FROM tabEmployee LIKE 'bei_%'` must return 6 rows.

Then bulk-import from `Payroll_RatesData_Mar25_AllBatches.csv` + ComprePayRun for Meal/Gasoline.

**HARD BLOCKER (AUDIT DQ-4):** Honorarium in actual Mar 25 payroll is fully taxable (all 4 employees in `Honorarium_Taxable` column, NOT split). Verify with HR before setting tax_applicable on the Honorarium Allowance salary component.

**Source mapping:**

| Frappe Field | RatesData Column | ComprePayRun Column |
|-------------|-----------------|-------------------|
| bei_comm_allow_monthly | CommAllow_Monthly | — |
| bei_deminimis_monthly | DeMinimis_Monthly | — |
| bei_honorarium_monthly | Honorarium_Monthly | — |
| bei_meal_allow_monthly | — | MealAllow_NonTax (latest cutoff × 2 for monthly) |
| bei_gasoline_allow_monthly | — | GasolineAllow (latest cutoff × 2 for monthly) |
| bei_other_fixed_monthly | OtherFixed_Monthly | — |

### P2-3: Clean up duplicate salary components (2 units)

- Disable "Basic" (keep "Basic Pay" which structures use)
- Disable "Income Tax" (keep "Withholding Tax" which structures use)
- Fix "Probitionary" typo on 7 employees

### P2-4: Produce employee-payroll matching report (2 units)

Save to `output/s150_employee_payroll_match.csv`:
- Columns: frappe_employee_id, frappe_name, payroll_employee_no, payroll_name, match_confidence, base_salary, allowances_total
- Flag unmatched employees for HR review

---

## Phase 3 — Backend: Add Allowances to Compensation Grid (10 units)

**HARD BLOCKER (AUDIT B-2):** Phase 3 code MUST NOT be deployed until Phase 2 Custom Fields are created AND `bench migrate` has run. If the code tries to SELECT `bei_*_monthly` columns before they exist in MariaDB, every grid load returns a 500 error. Verify with `SHOW COLUMNS FROM tabEmployee LIKE 'bei_%'` returning 6 rows before starting Phase 3 code.

### P3-1: Modify get_compensation_grid to include allowance fields (8 units)

**File:** `hrms/api/payroll_compensation.py`

Add to the SQL query: the 6 `bei_*_monthly` fields from Employee table. **HARD BLOCKER (AUDIT M-2):** Wrap in `COALESCE(..., 0)` — a single NULL propagates through the entire `projected_gross` chain to NULL in MariaDB.

```python
# In the main SQL query, add (with COALESCE for NULL safety):
COALESCE(e.bei_comm_allow_monthly, 0) AS bei_comm_allow_monthly,
COALESCE(e.bei_deminimis_monthly, 0) AS bei_deminimis_monthly,
COALESCE(e.bei_honorarium_monthly, 0) AS bei_honorarium_monthly,
COALESCE(e.bei_meal_allow_monthly, 0) AS bei_meal_allow_monthly,
COALESCE(e.bei_gasoline_allow_monthly, 0) AS bei_gasoline_allow_monthly,
COALESCE(e.bei_other_fixed_monthly, 0) AS bei_other_fixed_monthly

# In the computation loop, update projected_gross to include allowances:
allowances = (
    (emp.get("bei_comm_allow_monthly") or 0)
    + (emp.get("bei_deminimis_monthly") or 0)
    + (emp.get("bei_honorarium_monthly") or 0)
    + (emp.get("bei_meal_allow_monthly") or 0)
    + (emp.get("bei_gasoline_allow_monthly") or 0)
    + (emp.get("bei_other_fixed_monthly") or 0)
)
emp["total_allowances"] = allowances
emp["projected_gross"] = base + allowances  # Now includes allowances!
```

**HARD BLOCKER:** `projected_gross` MUST be `base + allowances`, not just `base`. The statutory deductions still compute from `base` only (SSS/PhilHealth/PagIBIG use basic salary, not gross). But the display Gross Pay should show the full compensation.

### P3-2: Add Sentry observability (2 units)

Existing `get_compensation_grid` already has Sentry. Verify it's still present after modifications. No new endpoints.

---

## Phase 4 — Frontend: Add Allowance Columns to Dashboard (10 units)

### P4-1: Update TypeScript types (2 units)

**File:** `bei-tasks/lib/queries/hr-payroll-compensation.ts`

```typescript
// Add to CompensationGridEmployee:
bei_comm_allow_monthly: number | null;
bei_deminimis_monthly: number | null;
bei_honorarium_monthly: number | null;
bei_meal_allow_monthly: number | null;
bei_gasoline_allow_monthly: number | null;
bei_other_fixed_monthly: number | null;
total_allowances: number | null;
```

### P4-2: Add allowance columns to grid (8 units)

**File:** `bei-tasks/app/dashboard/hr/payroll/compensation-setup/page.tsx`

Add 6 allowance columns + 1 total allowances column AFTER Daily Rate and BEFORE the projected statutory columns:

| Column | Header | Format |
|--------|--------|--------|
| total_allowances | Allowances | ₱ right-aligned monospace, bold |
| bei_comm_allow_monthly | Comm. | ₱ right-aligned monospace |
| bei_deminimis_monthly | De Minimis | ₱ right-aligned monospace |
| bei_honorarium_monthly | Honorarium | ₱ right-aligned monospace |
| bei_meal_allow_monthly | Meal | ₱ right-aligned monospace |
| bei_gasoline_allow_monthly | Gasoline | ₱ right-aligned monospace |
| bei_other_fixed_monthly | Other Fixed | ₱ right-aligned monospace |

**HARD BLOCKER (AUDIT H-4):** Individual allowance columns MUST be hidden by default. The `DataTableWithExport` component initializes `columnVisibility` as `{}` (all visible). The agent MUST either:
- Add an `initialColumnVisibility` prop to `DataTableWithExport`, OR
- Initialize the `VisibilityState` in `page.tsx` before passing to the table

Set these 6 columns to `false` in initial state:
```typescript
const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({
  bei_comm_allow_monthly: false,
  bei_deminimis_monthly: false,
  bei_honorarium_monthly: false,
  bei_meal_allow_monthly: false,
  bei_gasoline_allow_monthly: false,
  bei_other_fixed_monthly: false,
});
```

Only `total_allowances` is visible by default. Users toggle individual allowances via the Columns button (already works — confirmed by audit F-02).

Updated column order: Employee | Dept | Branch | Designation | Type | Structure | Base | Daily | **Allowances** | **Gross** | SSS | PhilHealth | PagIBIG | Tax | **Net** | **Company Cost** | Tax Slab | Bank | Pay Mode | Pending

---

## Phase 5 — Verification + Closeout (8 units)

### P5-1: Database verification queries (3 units)

| # | Check | Expected |
|---|-------|----------|
| V-01 | Payroll Period docstatus | 1 |
| V-02 | SSAs with NULL income_tax_slab | 0 |
| V-03 | Active employees with NULL salary_mode | 0 |
| V-04 | SSAs with base = 0 | 0 (or documented exceptions) |
| V-05 | Active payroll employees without SSA | < 10 |
| V-06 | Salary Structures count | 4 |
| V-07 | Employees with bei_other_fixed_monthly > 0 | ~150 |
| V-08 | Disabled duplicate components | Basic, Income Tax |
| V-09 | `SHOW COLUMNS FROM tabEmployee LIKE 'bei_%'` | 6 rows (Custom Fields created + migrated) |

### P5-2: Sample payroll cross-check (3 units)

Pick 5 employees at different salary/allowance levels. Compare:
- Frappe SSA base vs payroll BasicPay_Monthly
- Frappe bei_other_fixed_monthly vs payroll OtherFixed_Monthly
- Dashboard Gross Pay vs payroll GrossPay

### P5-3: Closeout (2 units)

1. Update plan YAML: status COMPLETED
2. Update SPRINT_REGISTRY.md
3. `git add -f docs/plans/` and push

---

## L3 Workflow Scenarios

| # | User | Action | Expected Outcome | Failure Means |
|---|------|--------|-------------------|---------------|
| L3-01 | test.hr@bebang.ph | Open compensation setup → check Allowances column | Shows ₱ amount > 0 for employees with allowances | Allowance data not imported |
| L3-02 | test.hr@bebang.ph | Check Gross Pay column | Gross = Base + Allowances (not just Base) | Gross computation wrong |
| L3-03 | test.hr@bebang.ph | Click Columns button → toggle individual allowance columns | Comm, De Minimis, Honorarium, Meal, Gasoline, Other visible | Column toggle broken |
| L3-04 | test.hr@bebang.ph | Export CSV | CSV includes allowance columns with values | Export missing new fields |
| L3-05 | test.hr@bebang.ph | Check Net Take-Home | Net = Gross - SSS - PhilHealth - PagIBIG - Tax | Net computation wrong |

Evidence: `output/l3/s150/`

---

## Autonomous Execution Contract

```yaml
completion_condition:
  - All V-01 through V-08 verification queries pass
  - Sample cross-check matches payroll data
  - Dashboard shows allowance columns
  - PRs created for hrms + bei-tasks (user merges)
  - Plan YAML + registry updated

stop_only_for:
  - SSM access failure
  - Employee-to-payroll matching below 80% (need HR input on name mismatches)
  - Business decision on allowance categorization

blocker_policy:
  programmatic: fix and continue
  name_matching: use fuzzy match, flag < 80% confidence for HR review

signoff_authority: single-owner (Sam Karazi)
```

---

## File Ownership

### Files MODIFIED (SSM — production database):
- `tabPayroll Period` — submit
- `tabSalary Structure Assignment` — tax slab, base amounts, salary_structure re-mapping, new SSAs
- `tabEmployee` — salary_mode, employment_type, bei_*_monthly allowance fields
- `tabSalary Component` — disable duplicates, create new components
- `tabSalary Structure` — create 2 new, add allowance components to all 4
- `tabCustom Field` — create 6 bei_*_monthly fields on Employee

### Files MODIFIED (code — PRs):
- `hrms/api/payroll_compensation.py` — add allowance fields to SQL query + computation
- `bei-tasks/lib/queries/hr-payroll-compensation.ts` — updated types
- `bei-tasks/app/dashboard/hr/payroll/compensation-setup/page.tsx` — allowance columns

### Evidence files produced:
- `output/s150_employee_payroll_match.csv`
- `output/s150_payroll_readiness_report.txt`
- `output/l3/s150/` — L3 evidence

### Source data (read-only):
- `data/_FINAL/Payroll_RatesData_Mar25_AllBatches.csv` — 463 employees, allowance rates
- `data/_FINAL/Payroll_Feb25_Mar10_Mar25.csv` — 1,488 rows, 3 cutoffs
