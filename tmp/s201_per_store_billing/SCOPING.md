# S201 Scoping: Per-Store Employee Billing Attribution

**Date:** 2026-04-17 (PHT)
**Trigger:** Sam's directive — "when an Employee punches in at Mega Mall, bill them to that store, not BEI parent. Except Area Supervisors + HO."
**Context:** S188 created 49 per-store child Companies. S196 renamed to ALL CAPS. Employee.company is still all parent BEI.

---

## Current State (verified 2026-04-17)

### Data
| Field | Value | Source |
|---|---|---|
| Employees under `BEBANG ENTERPRISE INC.` (parent) | 541 | Frappe `tabEmployee` |
| Employees under per-store Companies | 0 | Frappe `tabEmployee` |
| Employees with `branch` assigned | 539 / 542 | Frappe `tabEmployee.branch` |
| Distinct branches | 54 | "AYALA UPTC", "SM MEGAMALL", etc. |
| Per-store Companies (post-S196) | 49 | `entity_category='Store'`, ALL CAPS |
| Roving/AS employees (hardcoded) | 27 | `hrms/utils/roving_employees.py` |

### Code paths
| File | What it does | Problem |
|---|---|---|
| `hrms/api/transfers.py:71-77` | `create_transfer` — sets `branch` on Employee Transfer | **Hardcodes `new_company=emp_doc.company`** — company never changes on transfer |
| `hrms/utils/roving_employees.py` | 27-employee dict of AS/Roving/Projects/Opening-Team | Static — must be kept in sync with HR moves |
| `hrms/api/transfer_requests.py:31` | `BEI_COMPANY_NAME = "Bebang Enterprise Inc."` | Hardcoded parent company name (mixed case, stale post-S199) |
| `Employee.branch` | Store assignment | Branch name ≠ Company name (e.g. "AYALA UPTC" vs "AYALA UP TOWN CENTER - BEBANG ENTERPRISE INC.") |
| `Employee.company` | Legal billing entity | All 541 set to parent `BEBANG ENTERPRISE INC.` |

### Branch-to-Company alignment (the gap)
The 54 branch values do not cleanly map to the 49 Company prefixes. Examples of known drift:

| Employee.branch (current) | Company prefix (post-S196) |
|---|---|
| `AYALA UPTC` | `AYALA UP TOWN CENTER` |
| `XENTRO MONTALBAN` | `XENTROMALL MONTALBAN` |
| `SM MEGAMALL` | `SM MEGAMALL` ✓ |
| `BRITTANY OFFICE` | (Head Office — no store Company) |

No authoritative branch→Company table exists today. Must be built.

### Attendance → Payroll flow
Mosaic attendance is captured via ADMS (ZKTeco devices) into `Employee Checkin` records. Each checkin has `device_id` which maps to a store via `DEVICE_TO_STORE` (48-device table). Currently:
- Attendance rows use `Employee.company` (= parent BEI) on posting
- Salary Slip posts to `Employee.company` (= parent BEI)
- **Zero attribution back to the punch-in store's Company happens today.**

---

## What Sam Wants

> "Employee punches in Mega Mall → billed to Mega Mall's Company.
> Area Supervisors + Head Office stay under BEI parent.
> Relievers = fair split based on actual punch-ins.
> Transfer function exists in my.bebang.ph but Companies/Warehouses not wired."

Decoded as three distinct requirements:

1. **Primary billing entity per employee** — non-roving store staff should have `Employee.company` = their home store's Company. This makes payroll/leave/statutory filings book to the store's books, not BEI parent.
2. **Roving exception** — AS, Projects team, Opening team, HO personnel stay on `BEBANG ENTERPRISE INC.` (parent holding company). 27 known today + need to expand to catch all HO/Brittany.
3. **Reliever attribution** — when a non-roving employee covers a different store, that shift's labor cost should flow to the covered store (not the home store). Fair by punch count.

---

## Three Architectural Options

### Option A — "Home Store Primary Company" (MINIMAL)
**Move everyone to their home Company via `Employee.company` field.**

- Non-roving store crew: `Employee.company = <store>` (one of 49)
- Roving 27 + HO: `Employee.company = BEBANG ENTERPRISE INC.` (parent)
- Existing Transfer function extended to update `new_company` (not just branch)
- Payroll runs per-store automatically

**Pros:**
- Immediate fix for 95% of employees (permanent assignments)
- Salary Slip + Leave Balance + Attendance all book to right Company
- Reuses existing Transfer DocType

**Cons:**
- Does NOT handle relievers fairly — if employee from SM Tanza covers SM MOA for 3 days, their 3 days still bill to Tanza's Company
- Needs `branch → Company` resolver + one-time backfill

**Effort:** ~40 units (branch-Company mapping, backfill script, transfer API extension, 1 UI update)

---

### Option B — "Punch-Based Monthly Allocation" (FAIR)
**Keep `Employee.company` = home store (Option A) + add monthly JE to reallocate labor cost by punch share.**

- Option A base (Employee.company = home)
- Nightly/monthly job aggregates `Employee Checkin` by store per employee
- If employee punched at a non-home store, calculate % of shifts there
- Post inter-Company reclassification JE at month-end: home-store `Salaries-Expense` debits, covered-store `Salaries-Expense` credits, by punch share
- Works for relievers, AS who did a one-off cover, etc.

**Pros:**
- Per-store P&L truly fair — stores pay only for labor consumed
- No overhead on daily ops — only month-end reclass JE
- Preserves Employee.company as stable (legal) assignment

**Cons:**
- Requires inter-Company JE logic (DM-1, DM-6 rules apply)
- Month-end job needs robust testing
- Reports need to show "allocated" vs "direct" labor

**Effort:** ~80 units (Option A + allocation engine + JE generator + reporting)

---

### Option C — "Shift-Level Attribution" (MAXIMAL)
**Attribute every single shift to the punch-in store in real-time, not monthly.**

- Employee checkin itself stamps target Company from DEVICE_TO_STORE
- Salary Slip is sharded: each pay period splits into N slips, one per punched-in Company
- Cost centers per shift

**Pros:**
- Real-time per-store P&L
- No month-end reconciliation needed

**Cons:**
- Huge change to payroll architecture (violates 1-slip-per-employee-per-period assumption)
- Statutory filings (SSS, PhilHealth, Pag-IBIG, BIR 2316) assume single employer per employee per period — this breaks them
- Likely violates DOLE regulation

**Effort:** ~200+ units. **NOT RECOMMENDED** — regulatory minefield.

---

## Recommendation: Option B (Option A as Phase 1, Allocation as Phase 2)

Option B gives Sam what he asked for (fair per-store billing) without violating Philippine payroll law (single legal employer per period). It also ships value incrementally:

- **Phase 1 (S201):** Implement Option A foundation — Employee.company = home store for 514 non-roving, parent BEI for 27 roving + HO. Backfill branches. Extend Transfer API to update company. **~40 units.**
- **Phase 2 (S202):** Add monthly reliever allocation JE engine. **~40 units.**

Split because 80u in one sprint exceeds single-session ceiling (S089 rule) and Phase 1 is independently useful.

---

## Open Questions for Sam

Before reserving S201 + writing the plan, need answers on:

1. **Who exactly is "HO / non-store personnel"?**
   Today we have 27 in the roving dict (AS + Projects + Opening + Duty MyTown). Likely many more HO employees (Finance, Legal, IT, HR at Brittany Office) that stay under BEI parent. Need a definitive list or rule (e.g., `department in [Finance, HR, IT, Legal, Executive]` → BEI parent).

2. **Where's "home" for an Area Supervisor?**
   Today AS roving dict lists `home` (e.g., "ARANETA GATEWAY") but they cover 10+ stores. Under Option B, their `Employee.company` = BEI parent (not any single store). Does Sam agree?

3. **Branch naming drift — rename branches to match Companies, or keep aliases?**
   Today: branch="AYALA UPTC", Company="AYALA UP TOWN CENTER - BEBANG ENTERPRISE INC.". Option 1: rename 54 branches to match 49 Company prefixes exactly. Option 2: keep alias map in code forever. **Recommend renaming branches** — one source of truth.

4. **Commissary (BKI) employees?**
   BKI is separate legal entity. Its employees should be under `BEBANG KITCHEN INC.` Company already. Verify count.

5. **Start date for Option A backfill?**
   Retroactive from Feb 1 go-live, or prospective from next payroll cycle?

---

## Files That Will Need Changes (Option A / Phase 1)

| File | Change |
|---|---|
| `hrms/api/transfers.py` | Extend `create_transfer` to update `new_company` based on new_branch → Company resolver |
| `hrms/utils/company_lookup.py` (new) | `resolve_branch_to_company(branch_name)` — single SSOT for branch→Company mapping |
| `hrms/data_seed/branch_company_map.csv` (new) | Canonical 54-row branch→Company lookup + roving override |
| `hrms/patches/s201_*.py` (new) | One-time Employee.company backfill patch |
| `hrms/hr/doctype/employee/employee.py` | Add `validate()` hook that derives `company` from branch (unless roving) |
| `hrms/api/company_master.py` | Export `get_employee_company(employee)` for RBAC callers |

---

## Status

**Awaiting Sam decision on 5 open questions above.** Do not reserve S201 or branch until confirmed.
