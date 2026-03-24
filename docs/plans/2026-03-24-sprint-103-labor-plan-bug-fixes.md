# Sprint 103 — Labor Plan Bug Fixes

```yaml
canonical_sprint_id: S103
status: COMPLETED
created: 2026-03-24
audited: 2026-03-24
branch: s103-labor-plan-bug-fixes
lane: single
depends_on: S099
completed_date: 2026-03-24
execution_summary: >
  All 6 bugs fixed + VL/SL verified. Backend PR hrms#328 (merged), frontend PR bei-tasks#233 (merged).
  Batch publish uses Redis lock + chunks of 20. Compliance API fixed with OR query + bulk attendance lookup.
  Approve/Reject UI wired with APPROVER_ROLES gate. Publish disabled on Rejected with tooltip.
  ADMS auto-attendance verified (129 records). VL/SL dropdown shows 2 options + 1 leave override locked.
  L3: 8/8 PASS (S1-S7 including VL/SL workflow).
```

## Summary

Fix 6 bugs discovered during S099 (Labor Plan → Payroll Pipeline) execution.
The most critical is the publish timeout that blocks supervisors from publishing
full-store schedules. All bugs are in deployed code — this sprint is pure fixes.

## Design Rationale (For Cold-Start Agents)

### Why this exists

S099 deployed the labor plan → payroll pipeline but L3 testing revealed:
1. Publishing a 26-employee plan (181 shifts) times out on Vercel (504)
2. The compliance API returns 0 results due to store name mismatch
3. Approval UI buttons were never wired to the deployed hooks
4. ADMS auto-attendance was enabled but not verified
5. Legacy Shift Assignments (519, open-ended) were blocking publish — fixed via SQL but root cause needs prevention

### Why this architecture

- **Batch publish (not background job):** `frappe.enqueue` adds complexity (polling, status tracking). Batching shift creation in chunks of 20 with `frappe.db.commit()` between chunks is simpler and stays within Vercel's 60s timeout for 26 employees.
- **Store name normalization (not LIKE query):** The compliance API should resolve store names the same way `create_weekly_plan` does. Fix the query to use the same resolution path, not add fuzzy matching.
- **Approval buttons inline (not separate page):** The hooks and routes already exist from S099. Just render the buttons conditionally based on role and plan status.

### Source references

- Publish timeout: `hrms/api/supervisor.py:1988` (publish_weekly_plan)
- Compliance API: `hrms/api/supervisor.py:3665` (get_schedule_compliance)
- Approval hooks: `bei-tasks/hooks/use-labor-plan.ts` (approvePlan, rejectPlan)
- ADMS config: `adms_receiver/config.py:71`, EC2 container already changed to 0
- Legacy SA fix: SQL applied 2026-03-24 (519 rows, end_date set to 2026-03-22)
- Publish proxy: `bei-tasks/app/api/supervisor/labor-plan/publish/route.ts`

## Duplication Audit

| Feature | Existing Code | Classification |
|---------|--------------|----------------|
| Publish batching | `publish_weekly_plan` creates SAs in a loop — no batching | [EXTEND] |
| Compliance store fix | `get_schedule_compliance` has warehouse_name fallback (PR #326) — still broken | [EXTEND] |
| Approval buttons | Hooks + routes deployed, buttons not rendered | [EXTEND] |
| ADMS verification | `SKIP_AUTO_ATTENDANCE=0` set on EC2, cron exists in hooks.py | [EXTEND] |
| Prevent open-ended SAs | `_create_shift_assignment_from_plan` always sets single-day (start=end) | [SKIP] — already correct |
| Vercel timeout increase | `vercel.json` can set `maxDuration` per route | [BUILD] |

## Phase 1 — Publish Timeout Fix (2 tasks, ~8 units)

### P1-1: Batch Shift Assignment creation in publish_weekly_plan [EXTEND]

**What:** Modify `publish_weekly_plan()` to create/update Shift Assignments in batches
of 20, calling `frappe.db.commit()` after each batch. This prevents the Frappe request
from accumulating hundreds of uncommitted document operations.

**Logic change in `hrms/api/supervisor.py`:**

**AUDIT AMENDMENT v1:** `frappe.db.commit()` WILL release the `for_update` row lock (InnoDB
behavior — COMMIT unconditionally releases all row-level locks). Use Redis lock instead:

```python
BATCH_SIZE = 20
lock_key = f"labor-plan-publish:{plan_name}"
with frappe.cache().lock(lock_key, timeout=180):
    # Idempotent cleanup: remove orphaned SAs from any previous failed publish
    week_dates = [...]  # compute from plan week_start
    frappe.db.sql("""
        DELETE FROM `tabShift Assignment`
        WHERE custom_bei_schedule_source = %s
        AND start_date IN %s
        AND docstatus = 0
    """, (plan_name, week_dates))
    frappe.db.commit()

    for i in range(0, len(rows_to_process), BATCH_SIZE):
        batch = rows_to_process[i:i + BATCH_SIZE]
        for row in batch:
            _create_shift_assignment_from_plan(plan, row, work_date, publish_run_id)
        frappe.db.commit()

    # Re-read plan (lock was on Redis, not row) and update status
    plan.reload()
    plan.status = "Published"
    plan.save(ignore_permissions=True)
    frappe.db.commit()
```

**HARD BLOCKER (RESOLVED):** Redis lock replaces `for_update=True` for concurrency control.
Idempotent cleanup handles orphaned SAs from partial failures (Vercel timeout mid-batch).

**Sentry:** Already instrumented (S099).

**Files:** `hrms/api/supervisor.py` (publish_weekly_plan)

### P1-2: Increase Vercel function timeout for publish route [BUILD]

**What:** Add `maxDuration` to the publish API route in bei-tasks to allow up to 120s
for large publishes. This is a safety net — batching should bring it under 60s, but
larger stores may still need headroom.

**Files:**
- `bei-tasks/app/api/supervisor/labor-plan/publish/route.ts` — add `export const maxDuration = 120;`
- OR `bei-tasks/vercel.json` — add function config for the route

**Note:** Vercel Pro plan allows up to 300s. Current plan is Pro. Check `vercel.json` for
existing `functions` config before adding.

## Phase 2 — Compliance API Fix (1 task, ~4 units)

### P2-1: Fix store name resolution in compliance query [EXTEND]

**What:** The compliance API queries `BEI Weekly Labor Plan` by `store` field but the stored
value doesn't match what `_resolve_labor_plan_store()` returns. Debug by:

1. Query a known published plan's `store` field value directly from MariaDB
2. Compare with what `_resolve_labor_plan_store("Araneta Gateway")` returns
3. Fix the compliance query to use the same resolution or normalize both

**Approach:** Read the `store` field from `BEI-WLP-2026-00017` (the plan created during
S099 testing), compare with the warehouse resolution output, and fix the mismatch.

**AUDIT AMENDMENT v1 — Additional fix in same function:**
The compliance loop has an N+1 query (lines 3704-3714): one `frappe.get_all("Attendance")`
per shift assignment (182 queries for 26 employees x 7 days). Refactor to a single bulk query:
```python
attendance_map = {}
for att in frappe.get_all("Attendance", filters={...}, fields=[...]):
    attendance_map[(att.employee, att.attendance_date)] = att
```
Then dict-lookup in the loop instead of querying.

**Files:** `hrms/api/supervisor.py` (get_schedule_compliance)

## Phase 3 — Approval UI Buttons (2 tasks, ~10 units — AUDIT: increased from 8)

### P3-1: Render Approve/Reject buttons in labor plan page [EXTEND]

**What:** Add Approve and Reject buttons to `weekly-labor-plan-page.tsx`:

1. Import `approvePlan` and `rejectPlan` from the `useLaborPlan` hook (already returned)
2. Add Approve button next to Publish — visible when:
   - `plan?.status === "Draft"`
   - User role is Area Supervisor, Regional Manager, HR User, HR Manager, or System Manager
   - Check role via existing `useUserStore` pattern
3. Add Reject button with dialog:
   - Opens a modal with required textarea (min 10 chars)
   - Calls `rejectPlan({ plan_name, rejection_reason })`
4. Update `statusConfig` — already done in S099 (Approved: blue, Rejected: red)
5. Disable Publish when `plan?.status === "Rejected"` with tooltip
   **AUDIT FIX:** Current disabled condition (line 1087) is `isSubmitting || !hasScheduledShifts`.
   Must add `|| plan?.status === "Rejected"`.
6. **AUDIT AMENDMENT v1 — Preserve approved_by on publish:**
   `publish_weekly_plan` line 2106 sets `approved_by = None`. When approval workflow is live,
   this wipes the audit trail. Fix: remove the `plan.approved_by = None` line (or copy to
   `published_approved_by` if a separate field is preferred). Product decision: ask Sam.

**Files:** `bei-tasks/components/scheduling/weekly-labor-plan-page.tsx`, `hrms/api/supervisor.py`

### P3-2: Add role check utility for approval visibility [BUILD]

**What:** Wire role-based approval visibility. Three sub-tasks:

1. **Expose `role` from `useUserStore`:** The hook's API response includes `role: string` but
   the return object (lines 55-62) does not expose it. Add `role: storeData?.role` to the return.
   **File:** `bei-tasks/hooks/use-user-store.ts`

2. **Define APPROVER_ROLES:** Add to `bei-tasks/lib/roles.ts`:
   ```typescript
   export const APPROVER_ROLES = new Set([
     "Area Supervisor", "Regional Manager", "HR User", "HR Manager", "System Manager"
   ]);
   ```

3. **Role check pattern (AUDIT FIX — plan had wrong data shape):**
   ```typescript
   // WRONG (plan v0): user?.roles?.some(r => APPROVER_ROLES.includes(r))
   // CORRECT: useUserStore returns role: string (singular), not roles: string[]
   const { role } = useUserStore();
   const canApprove = role != null && APPROVER_ROLES.has(role);
   ```

4. **Fix catch blocks in use-labor-plan.ts** (lines 165-167, 181-183):
   Change bare `catch` to `catch (err: any)` and include `err?.message` in the return.

**Files:** `bei-tasks/hooks/use-user-store.ts`, `bei-tasks/lib/roles.ts`, `bei-tasks/hooks/use-labor-plan.ts`, `bei-tasks/components/scheduling/weekly-labor-plan-page.tsx`

## Phase 4 — ADMS Verification & Cleanup (2 tasks, ~4 units)

### P4-1: Verify ADMS auto-attendance is creating records [EXTEND]

**What:** Query the Frappe database to confirm that Employee Checkin records created after
the `SKIP_AUTO_ATTENDANCE=0` change (2026-03-24 ~10:30 PHT) are being processed into
Attendance records by the hourly cron.

**Steps:**
1. Via SSM, query MariaDB:
   ```sql
   SELECT COUNT(*) FROM `tabEmployee Checkin`
   WHERE creation >= '2026-03-24 02:30:00'
   AND skip_auto_attendance = 0;
   ```
2. Check if any Attendance records were created from these checkins:
   ```sql
   SELECT COUNT(*) FROM `tabAttendance`
   WHERE creation >= '2026-03-24 02:30:00'
   AND shift IS NOT NULL;
   ```
3. If zero Attendance records: check Shift Type `last_sync_of_checkin` to see if the cron ran
4. If cron hasn't run: trigger manually via `bench execute`

**DB creds:** Use SSM + `site_config.json` on EC2 (see `/credentials-lookup` skill). Do NOT put credentials in plan files.

### P4-2: Prevent future open-ended Shift Assignments [EXTEND]

**What:** Add a validation to `_create_shift_assignment_from_plan` that ensures `end_date`
is always set (never NULL). The existing code already sets `end_date = work_date` for
single-day assignments — verify this is correct and add an explicit assertion.

Also: add a one-time data check for any remaining NULL `end_date` Shift Assignments
and log a warning if found.

**AUDIT AMENDMENT v1 — Backend 10-char minimum for rejection reason:**
`reject_weekly_plan` (lines 3655-3656) only checks empty/whitespace. Add:
```python
if len(rejection_reason.strip()) < 10:
    frappe.throw(_("Rejection reason must be at least 10 characters"))
```

**Files:** `hrms/api/supervisor.py` (_create_shift_assignment_from_plan, reject_weekly_plan)

## Phase 5 — Closeout (1 task, ~2 units)

### P5-1: Update plan status and registry

1. Update this plan YAML: status → COMPLETED, add completed_date and execution_summary
2. Update SPRINT_REGISTRY.md: S103 row → COMPLETED with PR references
3. `git add -f docs/plans/` and push
4. Clean up branch: delete `s103-labor-plan-bug-fixes` after merge

## Requirements Regression Checklist

- [ ] Does publish_weekly_plan batch SA creation in chunks of ≤20?
- [ ] Does frappe.db.commit() between batches NOT release the for_update lock?
- [ ] Is Vercel maxDuration set for the publish route?
- [ ] Does get_schedule_compliance find published plans regardless of store name form?
- [ ] Are Approve/Reject buttons visible only to APPROVER_ROLES?
- [ ] Does Reject require a reason (min 10 chars)?
- [ ] Is Publish disabled when status=Rejected?
- [ ] Are new ADMS checkins (skip=0) being processed into Attendance?
- [ ] Does _create_shift_assignment_from_plan always set end_date?
- [ ] Does every new/modified @frappe.whitelist() call set_backend_observability_context()?

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| test.supervisor@bebang.ph | Fill full 7-day schedule for 26 employees at Araneta Gateway → click Publish | Plan published within 60s, 130+ Shift Assignments created, status = Published | Batch publish not working or timeout still hit |
| test.supervisor@bebang.ph | Open compliance for Araneta Gateway, published week → check total_scheduled_shifts | Returns > 0, details array has entries | Store name mismatch not fixed |
| test.supervisor@bebang.ph (Area Supervisor role) | View Draft plan → verify Approve button visible → click Approve | Plan status changes to Approved, approved_by set | Approval UI not wired |
| test.supervisor@bebang.ph | View Draft plan → click Reject → enter "Insufficient coverage" → confirm | Plan status = Rejected, rejection_reason saved, Publish disabled | Reject flow broken |
| test.supervisor@bebang.ph | View Rejected plan → verify Publish button is disabled with tooltip | Publish button disabled, tooltip says must re-approve | Status gate not working |
| (automated) | Query MariaDB for Attendance records created after ADMS change | ≥1 Attendance with shift field populated | Auto-attendance cron not running |

## Autonomous Execution Contract

```yaml
completion_condition:
  - All 6 bugs fixed and deployed
  - L3 scenarios (6) executed with real browser evidence
  - L3 evidence committed: git add -f output/l3/s103/
  - Plan YAML status → COMPLETED
  - SPRINT_REGISTRY.md → COMPLETED

stop_only_for:
  - Vercel plan doesn't support maxDuration > 60s (check first)
  - frappe.db.commit() releases for_update lock (architecture decision needed)
  - ADMS container not receiving punches (infrastructure issue)

continue_without_pause_through:
  - code → test → PR → governor → deploy → L3 → closeout

blocker_policy:
  programmatic: fix and continue
  environment: debug, retry, escalate after 3 failures
  business-data: pause

governor_decisions:
  APPROVE: proceed to L2-L4
  REJECT: read PR comment, fix, push to same branch
  NEEDS_FIX: apply fix, push
  MERGE_CONFLICT: rebase onto production, resolve, force-push

signoff_authority: single-owner (Sam Karazi, CEO)

canonical_closeout_artifacts:
  - docs/plans/2026-03-24-sprint-103-labor-plan-bug-fixes.md
  - docs/plans/SPRINT_REGISTRY.md
  - output/l3/s103/form_submissions.json
  - output/l3/s103/api_mutations.json
  - output/l3/s103/state_verification.json
```

## Phase Budget Contract

| Phase | Units | Notes |
|-------|-------|-------|
| Phase 1 | 8 | Publish batch + Vercel timeout |
| Phase 2 | 4 | Compliance store name fix |
| Phase 3 | 10 | Approval UI buttons + role check + catch fixes (AUDIT: +2u) |
| Phase 4 | 5 | ADMS verification + SA validation + reject 10-char (AUDIT: +1u) |
| Phase 5 | 2 | Closeout |
| **Total** | **29** | Within 80-unit ceiling (AUDIT: was 26) |

## Rollback Plan

| Phase | Rollback |
|-------|----------|
| Phase 1 | Revert batch commit — publish reverts to single-commit (slower but functional for small stores) |
| Phase 2 | Revert compliance query — returns 0 (non-breaking, just empty data) |
| Phase 3 | Revert button rendering — buttons disappear, hooks remain dormant |
| Phase 4 | Set SKIP_AUTO_ATTENDANCE=1 in ADMS container — reverts to pre-S099 behavior |

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branch:** `git fetch origin production && git checkout -b s103-labor-plan-bug-fixes origin/production`
3. Read `docs/plans/SPRINT_REGISTRY.md` for cross-sprint context.
4. Read `docs/plans/2026-03-24-s099-bugs-handoff.md` for full bug details.
5. Read `hrms/api/supervisor.py` lines 1988-2120 (publish_weekly_plan) and 3665-3730 (get_schedule_compliance).
6. Read `bei-tasks/components/scheduling/weekly-labor-plan-page.tsx` lines 49-55 (statusConfig) and 1080-1100 (Publish button area).
7. Read `bei-tasks/hooks/use-labor-plan.ts` to find approvePlan/rejectPlan mutations.

## Audit Amendment History

### Amendment v1 (2026-03-24) — Multi-Domain Audit + Code Verification + Fact-Check

**Pipeline:** 6 domain agents → code verifier → adversarial fact-checker
**Result:** 12 verified blockers (9 SUPPORTED, 2 PARTIAL/merged, 1 CONTRADICTED/removed)
**4 STALE findings removed** (approve_weekly_plan has @frappe.whitelist, Sentry already present, routes exist, commit bug is prospective not current)
**Amendments applied to operative sections:**

| Blocker | Amendment |
|---------|-----------|
| B-1: for_update + commit() | P1-1 rewritten: Redis lock + batch commit (was: deferred to runtime) |
| B-2: Orphaned SAs | P1-1 rewritten: idempotent cleanup before re-publish |
| B-3: N+1 compliance query | P2-1 amended: bulk attendance query added |
| B-4: DB creds in plan | Credentials removed from line 172, replaced with SSM reference |
| B-5: approved_by wiped | P3-1 amended: preserve approved_by on publish |
| B-6: No Rejected guard | P3-1 amended: add status check to disabled condition |
| B-7: P3 is net-new | P3 budget increased from 8 to 10 units |
| B-8: APPROVER_ROLES + role | P3-2 rewritten: 4 sub-tasks with correct data shapes |
| B-9: Bare catch blocks | P3-2 amended: fix catch in use-labor-plan.ts |
| B-10: maxDuration absent | P1-2 unchanged (already covers this) |
| B-11: No 10-char backend | P4-2 amended: add min-length validation |
| B-12: Wrong role pattern | P3-2 rewritten: uses Set.has(role) not .some() |

**Full audit artifacts:** `output/plan-audit/s103-labor-plan-bug-fixes/`

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.
