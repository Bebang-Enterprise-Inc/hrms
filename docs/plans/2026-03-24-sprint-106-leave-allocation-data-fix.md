# Sprint 106 — Leave Allocation Data Fix

```yaml
canonical_sprint_id: S106
status: COMPLETED
execution_started: 2026-03-24
created: 2026-03-24
branch: s106-leave-allocation-data-fix
lane: single
depends_on: null
completed_date: 2026-03-24
execution_summary: >
  Fixed 1,557 Leave Allocations via ORM on EC2 (bench execute).
  total_leaves_allocated set correctly, 1,557 Leave Ledger Entries created (8 → 1,565).
  Zero broken allocations remaining. Balance API verified: VL=15, SL=15, EL=5.
  Test leave application filed + cancelled successfully. L3 5/5 PASS.
```

## Summary

Fix 1,555 broken Leave Allocation records that have `total_leaves_allocated = 0` and no Leave Ledger Entries. This blocks **every employee** from filing VL, SL, or Emergency Leave.

**Impact:** 518 VL + 518 SL + 519 EL allocations = 1,555 records across ~519 employees. Zero employees can currently file leave through the system.

## Design Rationale (For Cold-Start Agents)

### Why this exists

During the Feb 2026 HR data import, Leave Allocations were bulk-imported via direct SQL INSERT with `docstatus=1` (submitted). This bypassed two critical Frappe controller methods:

1. `validate()` → `set_total_leaves_allocated()` — sets `total_leaves_allocated = unused_leaves + new_leaves_allocated`. Since it was never called, `total_leaves_allocated` stayed at 0.
2. `on_submit()` → `create_leave_ledger_entry()` — creates Leave Ledger Entry records that `get_leave_balance_on()` reads for balance calculation. Since it was never called, no ledger entries exist.

**Evidence:**
- 1,555 allocations with `total_leaves_allocated = 0`, `new_leaves_allocated > 0`, `docstatus = 1`
- Only 8 Leave Ledger Entries exist (from 8 manually-created test allocations via ORM)
- `get_leave_balance_on()` returns 0 for all employees → `InsufficientLeaveBalanceError`
- Naming pattern `LA-{bio_id}-{type}-2026` (no naming_series) confirms direct SQL origin
- Creation date: 2026-02-22, owner: Administrator

### Why this architecture

- **Fix script on EC2 via SSM, not code deployment:** No Frappe code is wrong — the Leave Allocation controller works correctly. The data was inserted bypassing the ORM. The fix is a one-time data correction script run inside the Frappe container.
- **Use Frappe ORM (not raw SQL) for ledger entries:** Leave Ledger Entries have complex interactions (expiry, carry-forward). Using `allocation.create_leave_ledger_entry()` ensures proper creation including the `is_carry_forward` logic, date ranges, and ledger structure.
- **Separate script for safety:** The fix modifies 1,555+ database records. A standalone Python script with before/after counts, dry-run mode, and transaction batching is safer than ad-hoc commands.

### Key trade-off: ORM loop vs bulk SQL

- **Option A (chosen): ORM loop** — Load each allocation via `frappe.get_doc()`, call `set_total_leaves_allocated()` and `create_leave_ledger_entry()`. Slower (~5 min for 1,555 records) but correct. Handles carry-forward, expiry, and edge cases automatically.
- **Option B (rejected): Bulk SQL** — `UPDATE total_leaves_allocated` + bulk INSERT into Leave Ledger Entry. Fast but error-prone: would need to manually replicate the carry-forward logic, date range calculations, and `is_carry_forward` flags. Risk of creating malformed ledger entries.

### Source references

- Leave Allocation controller: `hrms/hr/doctype/leave_allocation/leave_allocation.py` lines 41-47 (validate), 79-80 (on_submit), 232-241 (set_total_leaves_allocated), 295-317 (create_leave_ledger_entry)
- Balance check: `hrms/hr/doctype/leave_application/leave_application.py` — `get_leave_balance_on()` reads from Leave Ledger Entry, NOT from `total_leaves_allocated` field
- Broken records query: `SELECT COUNT(*) FROM tabLeave Allocation WHERE docstatus=1 AND new_leaves_allocated > 0 AND total_leaves_allocated = 0` → 1,555

## Duplication Audit

| Feature | Existing Code | Classification |
|---------|--------------|----------------|
| Fix script | `scripts/testing/fix_leave_allocations.py` (S103 test hack — SQL-only, no ledger) | [BUILD] — need proper ORM-based fix |
| Leave Allocation controller | `hrms/hr/doctype/leave_allocation/leave_allocation.py` — works correctly | [SKIP] — no code change needed |
| Leave balance API | `hrms/hr/doctype/leave_application/leave_application.py` — reads ledger correctly | [SKIP] — no code change needed |

## Phase 1 — Write Fix Script (~4 units)

### P1-1: Create `hrms/patches/v16_0/s106_fix_leave_allocations.py` [BUILD]

**What:** Write a Frappe bench-executable patch script that:

1. Queries all broken allocations: `docstatus=1 AND new_leaves_allocated > 0 AND total_leaves_allocated = 0`
2. For each allocation:
   a. Load via `frappe.get_doc("Leave Allocation", name)`
   b. Call `doc.set_total_leaves_allocated()` to compute `total_leaves_allocated` correctly
   c. Call `doc.db_update()` to save the field (NOT `doc.save()` which triggers full validation + naming_series check)
   d. Check if Leave Ledger Entries already exist for this allocation
   e. If no ledger entries: call `doc.create_leave_ledger_entry()` to create them
   f. Commit every 50 records to avoid long-running transactions
3. Print before/after counts for verification
4. Log any failures (employee, allocation name, error) without stopping the batch

**HARD BLOCKER:** Do NOT use `doc.save()` — the naming_series field is NULL on these records and `save()` will throw `MandatoryError`. Use `doc.db_update()` for field updates and `create_leave_ledger_entry()` for ledger creation.

**HARD BLOCKER:** Do NOT set `total_leaves_allocated` via raw SQL alone — `get_leave_balance_on()` reads from Leave Ledger Entry, not from the allocation field. Without ledger entries, balance stays 0.

**Files:** `hrms/patches/v16_0/s106_fix_leave_allocations.py`

### P1-2: Add before-snapshot query [BUILD]

**What:** Before running the fix, capture a snapshot:
```sql
SELECT leave_type, COUNT(*) as broken_count, SUM(new_leaves_allocated) as total_new
FROM `tabLeave Allocation`
WHERE docstatus=1 AND new_leaves_allocated > 0 AND total_leaves_allocated = 0
GROUP BY leave_type;
```
And count existing Leave Ledger Entries:
```sql
SELECT COUNT(*) FROM `tabLeave Ledger Entry` WHERE transaction_type = 'Leave Allocation';
```

Store in `output/s106/before_snapshot.json`.

## Phase 2 — Execute Fix on Production (~4 units)

### P2-1: Deploy script to EC2 container and execute [BUILD]

**What:**
1. Copy the fix script to the EC2 container via SSM + docker cp
2. Execute via `bench --site hq.bebang.ph execute hrms.patches.v16_0.s106_fix_leave_allocations.execute` (or `python` with proper imports)
3. Capture stdout/stderr output
4. Verify: `total_leaves_allocated > 0` count should be 1,555+ (was 10)
5. Verify: Leave Ledger Entry count should be 1,555+ (was 8)

**EC2:** Instance `i-026b7477d27bd46d6`, container pattern `frappe_backend.*`, site `hq.bebang.ph`

**HARD BLOCKER:** Use SSM for EC2 access. Do NOT SSH directly. See `/credentials-lookup` for SSM patterns.

### P2-2: Post-fix verification queries

**What:** Run these verification queries after the fix:

```sql
-- 1. Zero broken allocations remaining
SELECT COUNT(*) FROM `tabLeave Allocation`
WHERE docstatus=1 AND new_leaves_allocated > 0 AND total_leaves_allocated = 0;
-- Expected: 0

-- 2. Leave Ledger Entries created
SELECT COUNT(*) FROM `tabLeave Ledger Entry`
WHERE transaction_type = 'Leave Allocation';
-- Expected: 1555+ (was 8)

-- 3. Spot-check balance for known employee
-- Use get_leave_balance_on via API
```

Store in `output/s106/after_snapshot.json`.

## Phase 3 — L3 Verification (~4 units)

### P3-1: Verify leave balance API returns > 0

**What:** Call `get_leave_balance_on` for 3 employees across VL, SL, EL:
- Employee 9000924 (HELUTIN) — Vacation Leave balance should be ~14 (15 minus the 1 we used in S103)
- Employee 9000358 (SAMSON) — Sick Leave balance should be ~14
- Employee 9000003 — Emergency Leave balance should be 5

### P3-2: File a test leave application via my.bebang.ph

**What:** Using Playwright browser automation:
1. Login as a test employee at a known store
2. Navigate to Leave section in my.bebang.ph
3. File a 1-day Vacation Leave application
4. Verify it is accepted (no InsufficientLeaveBalanceError)
5. Cancel/delete the test application afterward to avoid cluttering real data

## L3 Workflow Scenarios

| # | User | Action | Expected Outcome | Failure Means |
|---|------|--------|-------------------|---------------|
| 1 | (API) | Call `get_leave_balance_on` for 9000924, Vacation Leave, 2026-03-27 | Returns >= 13 (15 minus used) | Ledger entries not created correctly |
| 2 | (API) | Call `get_leave_balance_on` for 9000358, Sick Leave, 2026-03-27 | Returns >= 14 | Ledger entries not created correctly |
| 3 | (API) | Call `get_leave_balance_on` for 9000003, Emergency Leave, 2026-03-27 | Returns 5 | Ledger entries not created correctly |
| 4 | (API) | POST Leave Application for 9000924, VL, 2026-03-28 | HTTP 200, application created | Balance fix not working end-to-end |
| 5 | (API) | Cancel the test leave application from scenario 4 | Application cancelled | Cleanup failed |

## Phase 4 — Closeout (~2 units)

### P4-1: Update plan and registry

1. Update this plan YAML: status -> COMPLETED, add completed_date and execution_summary
2. Update SPRINT_REGISTRY.md: S106 row -> COMPLETED
3. `git add -f docs/plans/ output/s106/` and push

## Requirements Regression Checklist

- [ ] Is the fix using ORM (`frappe.get_doc`) not raw SQL for ledger entry creation?
- [ ] Is the fix using `doc.db_update()` not `doc.save()` to avoid naming_series error?
- [ ] Does the fix create Leave Ledger Entries, not just update total_leaves_allocated?
- [ ] Is there a before/after snapshot for verification?
- [ ] Is the fix batched with periodic commits (every 50 records)?
- [ ] Does the L3 test verify balance via API, not just field value?

## Ground-Truth Lock

- evidence_sources:
  - `output/s106/before_snapshot.json` -> pre-fix allocation + ledger counts
  - `output/s106/after_snapshot.json` -> post-fix verification
- count_method:
  - metric: broken Leave Allocation records
  - basis: `docstatus=1 AND new_leaves_allocated > 0 AND total_leaves_allocated = 0`
  - method: `SELECT COUNT(*) FROM tabLeave Allocation WHERE ...`
- authoritative_sections:
  - Phases 1-4 are authoritative for execution
  - Design Rationale is context only

## Autonomous Execution Contract

- completion_condition:
  - zero broken allocations remaining (query returns 0)
  - Leave Ledger Entry count >= 1555
  - `get_leave_balance_on` returns > 0 for spot-checked employees
  - test leave application creates successfully
  - plan YAML status updated to COMPLETED
  - SPRINT_REGISTRY.md updated
- stop_only_for:
  - SSM/EC2 access failure
  - fix script errors affecting > 5% of records (systemic failure)
- continue_without_pause_through:
  - script creation, deployment, execution, verification, closeout
- blocker_policy:
  - programmatic -> fix and continue
  - individual record failure -> log and continue (batch tolerance)
  - systemic failure (>5%) -> stop and investigate
- signoff_authority: single-owner (Sam)

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branch:** `git fetch origin production && git checkout -b s106-leave-allocation-data-fix origin/production`. NEVER write code on production.
3. Write the fix script in Phase 1.
4. Copy to EC2 and execute in Phase 2.
5. Verify in Phase 3.
6. Closeout in Phase 4.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

## Execution Workflow

- Deploy fix: SSM to EC2 container (no code deploy needed — this is a data fix)
- Verify: API calls to `get_leave_balance_on`
- No Sentry instrumentation needed (no new/modified `@frappe.whitelist()` endpoints)
- No frontend changes
- No governor involvement (no PR to merge — data fix only)
