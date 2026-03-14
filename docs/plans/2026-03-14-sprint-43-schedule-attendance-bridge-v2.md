# S043 — Schedule & Attendance Bridge V2 (S033 Continuation)

```yaml
canonical_sprint_id: S043
status: GO (Audited 2026-03-14; 13 blockers resolved; Option A — Frappe auto-attendance)
lane: single
created: 2026-03-14
author: Claude (continuation of S033)
parent_sprint: S033
audit_report: output/plan-audit/s043-schedule-attendance-bridge-v2/consolidated_audit_report.md
predecessor_work: |
  S033 Phase 0 shipped 2026-03-11:
  - publish_weekly_plan() live on production (PRs #197-#203)
  - Portal direct publish UI live (bei-tasks PRs #99, #103)
  - Shift type auto-provisioning on publish
  - BEI Weekly Labor Plan + BEI Planned Shift DocTypes operational
```

## Architecture Decision: Frappe Auto-Attendance (Option A)

**Decision:** Use Frappe's built-in `process_auto_attendance_for_all_shifts()` instead of building a custom classifier.

**Why:** Frappe already runs attendance classification hourly via `hooks.py:398`. Building a second custom classifier at 11 PM would either duplicate or conflict with already-submitted Attendance records. Option A eliminates 4 audit blockers and ~80% of custom code.

**What this means:**
- Phase 1 becomes "configure Shift Types correctly + verify Frappe auto-attendance generates correct Attendance records"
- No custom `BEI Daily Attendance Summary` DocType needed — Frappe's built-in `Attendance` DocType captures status (Present/Absent/Half Day/On Leave)
- No custom scheduler for classification — Frappe's hourly scheduler handles it
- Phase 2 (missing punch report) reads from Frappe `Attendance` + `Employee Checkin` records
- Missing Punch detection = Employee has Shift Assignment but no Attendance record marked by auto-attendance (meaning no matching Checkin)

**What Frappe auto-attendance needs to work:**
Each Shift Type MUST have these fields set (bare provisioning will silently fail):
- `enable_auto_attendance = 1`
- `process_attendance_after` = shift end time + 60 min (e.g., 19:00 for S-9A)
- `last_sync_of_checkin` = shift end time + 60 min
- `late_entry_grace_period` = 15 (minutes)
- `early_exit_grace_period` = 15 (minutes)
- `working_hours_threshold_for_half_day` = 4
- `working_hours_threshold_for_absent` = 1
- `allow_check_out_after_shift_end_time` = 60 (minutes)
- For cross-midnight shifts (C-4P, C-5P): `process_attendance_after` must be set to the NEXT DAY time (e.g., 02:00 for C-5P ending at 02:00)

---

## Problem Statement

S033 shipped the publish bridge (labor plan → shift assignments) but stopped at ~20% of the full plan. Supervisors can now create and publish weekly schedules, but the system cannot yet:
- Automatically classify attendance (Present / Late / Absent / Half Day / Missing Punch)
- Generate daily missing-punch reports for supervisors and HR
- Offer copy-last-week or apply-template shortcuts
- Provide a mobile-optimized scheduling UX

## What Already Exists (from S033 Phase 0)

| Component | Location | Status |
|-----------|----------|--------|
| `publish_weekly_plan()` | `hrms/api/supervisor.py` | LIVE on production |
| Shift type provisioning (`_ensure_shift_type_for_plan_row()`) | `hrms/api/supervisor.py:449` | LIVE (but bare — missing required fields) |
| BEI Weekly Labor Plan DocType | `hrms/hr/doctype/bei_weekly_labor_plan/` | LIVE |
| BEI Planned Shift DocType | `hrms/hr/doctype/bei_planned_shift/` | LIVE (DM-4: `shift_type_name` is Data, not Link) |
| BEI Shift Template DocType | `hrms/hr/doctype/bei_shift_template/` | LIVE |
| Portal labor plan page | `bei-tasks: app/dashboard/supervisor/labor-plan/page.tsx` | LIVE |
| Portal publish/bootstrap APIs | `bei-tasks: app/api/supervisor/labor-plan/{publish,bootstrap}/route.ts` | LIVE |
| `use-labor-plan.ts` hook | `bei-tasks: hooks/use-labor-plan.ts` | LIVE |
| Frappe Shift Assignment | upstream DocType | LIVE (used by publish bridge) |
| Frappe auto-attendance | `hooks.py:398` hourly scheduler | LIVE (but no Shift Types configured yet) |
| ADMS WorkCode fix | 47/48 devices | LIVE (IN/OUT/Break punches clean) |

---

## Remaining Deliverables

### Phase 0 — Shift Naming Policy, Seed Data & Fixes

BEI currently has no shared shift vocabulary. This phase introduces canonical naming, seeds Frappe with 12 Shift Types (all required fields), and fixes two pre-existing issues.

#### BEI Shift Naming Policy

**Frappe record name:** Display name (e.g., "Store - Morning"). **Short code:** `S-9A` (stored in custom field `short_code` for portal display).

**Rationale for dual naming:** S033 already provisioned Shift Types with display names. Renaming would break existing Shift Assignments. Short codes are a portal UI convenience, not the Frappe record name.

**Retail Store Shifts (7):**

| Short Code | Frappe Name (record) | Start | End | `process_attendance_after` | `allow_check_out_after_shift_end_time` |
|------------|---------------------|-------|-----|---------------------------|---------------------------------------|
| `S-8A` | Store - Early Opening | 08:00 | 17:00 | 18:00 | 60 min |
| `S-9A` | Store - Morning | 09:00 | 18:00 | 19:00 | 60 min |
| `S-10A` | Store - Mid Morning | 10:00 | 19:00 | 20:00 | 60 min |
| `S-11A` | Store - Late Morning | 11:00 | 20:00 | 21:00 | 60 min |
| `S-12P` | Store - Afternoon | 12:00 | 21:00 | 22:00 | 60 min |
| `S-1P` | Store - Mid Afternoon | 13:00 | 22:00 | 23:00 | 60 min |
| `S-2P` | Store - Late Afternoon | 14:00 | 23:00 | 00:00 (+1d) | 60 min |

**Commissary Shifts (5):**

| Short Code | Frappe Name (record) | Start | End | `process_attendance_after` | Cross Midnight? |
|------------|---------------------|-------|-----|---------------------------|-----------------|
| `C-4A` | Commissary - Dawn | 04:00 | 13:00 | 14:00 | No |
| `C-5A` | Commissary - AM | 05:00 | 14:00 | 15:00 | No |
| `C-6A` | Commissary - AM Late | 06:00 | 15:00 | 16:00 | No |
| `C-4P` | Commissary - PM Night | 16:00 | 01:00 (+1d) | 02:00 (+1d) | **YES** |
| `C-5P` | Commissary - Night | 17:00 | 02:00 (+1d) | 03:00 (+1d) | **YES** |

**All Shift Types share:** `enable_auto_attendance=1`, `late_entry_grace_period=15`, `early_exit_grace_period=15`, `working_hours_threshold_for_half_day=4`, `working_hours_threshold_for_absent=1`, `allow_check_out_after_shift_end_time=60`

**Status codes (portal schedule grid):**

| Code | Meaning |
|------|---------|
| `RD` | Rest Day |
| `LWOP` | Leave Without Pay |
| `SL` | Sick Leave |
| `VL` | Vacation Leave |
| `OT` | Overtime (suffix — e.g., `S-9A+OT`) |

#### Phase 0 Tasks

| Task | Classification | Details |
|------|---------------|---------|
| 0.1 Seed 12 Shift Types in Frappe with ALL required fields (see table above) | [BUILD] | Use `bench execute` or API. Include `process_attendance_after`, `last_sync_of_checkin`, grace periods, thresholds. Verify with `has_incorrect_shift_config()` — must return False for all 12. |
| 0.2 Add `short_code` custom field to Shift Type DocType | [BUILD] | `Data` field, unique. Populate with S-8A through C-5P. Used by portal dropdown. |
| 0.3 Fix DM-4: Change `shift_type_name` in `bei_planned_shift.json` from `Data` to `Link` (→ Shift Type) | [BUILD] | Requires migration of existing data. Run `bench migrate` after change. |
| 0.4 Fix `_ensure_shift_type_for_plan_row()` in `supervisor.py` to set ALL required fields when auto-provisioning | [EXTEND] | Currently only sets `start_time` + `end_time`. Add all fields from the table above. |
| 0.5 Update portal shift picker to load from `short_code` field, display as "S-9A (09:00-18:00)" | [EXTEND] | Existing `<Select>` component — change data source, not component type. Bootstrap API must return `short_code` + `name` + time range. |
| 0.6 Add `WAREHOUSE_USER` to `canManageStoreSchedule()` in `bei-tasks/lib/roles.ts` | [BUILD] | Commissary supervisors need portal access for commissary shift scheduling. |
| 0.7 Generate one-page shift code reference card (PDF) | [BUILD] | `/pdf` skill. For store posting. |

**Deploy sequence for Phase 0:**
1. Deploy Frappe code (0.3, 0.4) → `bench migrate` → `bench restart`
2. Run seed script (0.1, 0.2) → verify all 12 Shift Types pass `has_incorrect_shift_config()=False`
3. Deploy portal code (0.5, 0.6) to Vercel
4. Verify: publish a test plan for SM East Ortigas → confirm Shift Assignment created with correct Shift Type → confirm Frappe auto-attendance picks it up within 1 hour

### Phase 1 — Verify Auto-Attendance & Handle Gaps

Frappe's hourly `process_auto_attendance_for_all_shifts()` now does the classification. This phase verifies it works and handles what it doesn't cover.

| Task | Classification | Details |
|------|---------------|---------|
| 1.1 Publish a test weekly plan for SM East Ortigas with real employee data | [EXTEND] | Use existing portal publish flow. |
| 1.2 Wait for Frappe auto-attendance to run (hourly) | [VERIFY] | Check `Attendance` DocType for auto-generated records. Verify status: Present, Absent, Half Day. |
| 1.3 Verify Late detection | [VERIFY] | Frappe marks late via `late_entry=1` flag on Attendance. Confirm this fires when punch-in > shift start + 15 min grace. |
| 1.4 Verify cross-midnight for commissary | [VERIFY] | Publish C-5P shift, simulate punch at 17:05 and 02:00+1d. Confirm Attendance record created correctly. |
| 1.5 Build Missing Punch detector: query employees with Shift Assignment but no Attendance record after `process_attendance_after` time | [BUILD] | `hrms/services/missing_punch_report.py` — reads Attendance + Employee Checkin, not raw ADMS. |
| 1.6 Handle edge cases: employee transfer mid-week, terminated employee with active shift, holiday (prevent false-absent flood) | [BUILD] | Holiday check: skip classification if company holiday. Transfer: use `Employee.custom_store` as of shift date. |

**Dependency:** Phase 0 complete. ADMS punches flowing to Employee Checkin (confirmed since 2026-03-10).

### Phase 2 — Missing Punch Daily Report

| Task | Classification | Details |
|------|---------------|---------|
| 2.1 Create `hrms/services/missing_punch_report.py` | [BUILD] | Queries: employees with Shift Assignment today but no Attendance record OR Attendance with `status=Absent`. |
| 2.2 Format report: employee name, store (`Employee.custom_store`), shift code, last known punch time (from Employee Checkin) | [BUILD] | |
| 2.3 Send to store supervisor via Google Chat (`custom_gchat_space` on store's Branch doc) | [EXTEND] | Uses existing `hrms/api/google_chat.py`. Fallback: global ops space if `custom_gchat_space` is null. |
| 2.4 Send to Area Supervisor via Google Chat | [EXTEND] | Look up AS from store cluster mapping. |
| 2.5 Send daily summary to `hr@bebang.ph` via email (frappe.sendmail) | [BUILD] | |
| 2.6 Scheduler: `"0 16 * * *"` (midnight PHT = 16:00 UTC, after all shifts including S-2P end at 23:00 + 60 min checkout window) | [BUILD] | `hooks.py` cron entry. Runs at 00:00 PHT, well after last shift ends. |
| 2.7 Dual delivery failure handling: if Chat fails, still send email (and vice versa). Log failures, don't crash. | [BUILD] | try/except per channel. |

**Dependency:** Phase 1 verified. Auto-attendance generating Attendance records.

### Phase 3 — Scheduling UX Improvements (Portal) [V1 SCOPE]

Phase 3 is scoped to V1 essentials. Tasks 3.3 (Apply Template) and 3.4 (Mobile Day-Card) are deferred to V2 after store adoption proves the platform.

#### 3.1 Shift Code Dropdown Enhancement

| Item | Detail |
|------|--------|
| Component | Existing `<Select>` in `page.tsx:161-172` |
| Data source | Bootstrap API returns `{short_code, name, start_time, end_time}` for each Shift Type |
| Display format | `"S-9A (09:00-18:00)"` |
| Store filtering | Bootstrap API filters by store type: retail stores see `S-*` codes, commissary sees `C-*` codes. Filter via `Employee.custom_store` → `Branch.store_type`. |
| Fallback | If API fails, show raw Shift Type names (existing behavior). |
| Empty state | If no Shift Types seeded, show "No shift types configured — contact admin." |

#### 3.2 Copy Previous Week

| Item | Detail |
|------|--------|
| API route | `POST /api/supervisor/labor-plan/copy-week` |
| Request | `{ store: string, target_week_start: string }` |
| Response | `{ shifts: PlannedShift[], source_week: string }` or `{ error: "no_previous_week" }` |
| Backend | `hrms/api/supervisor.py` → query last published `BEI Weekly Labor Plan` for same store, return its `BEI Planned Shift` rows with dates shifted to target week |
| Edge: first week | Return `{ error: "no_previous_week" }` → portal shows "No previous schedule found. Create from scratch." |
| Edge: partial week | Copy whatever exists. Portal shows banner: "Copied from {date}. {N} days had no shifts — fill them manually." |
| Edge: current week has data | Confirmation dialog: "Current week already has {N} shifts. Replace all?" |
| Portal | Button in labor plan page header. Calls API, populates grid, user reviews and publishes. |

#### 3.5 Validation

| Item | Detail |
|------|--------|
| Double-schedule | On publish, backend checks: any employee with >1 Shift Assignment for same date. Return warning list, don't block. |
| 48h/week | On publish, sum planned hours per employee for the week. Warn if >48h. Don't block. |
| Portal | Show warnings in a dismissible banner before final publish confirmation. |

#### 3.6 Color-Coded Shift Grid

| Item | Detail |
|------|--------|
| Mapping | Each short code gets a Tailwind color class. `S-8A: blue-100`, `S-9A: green-100`, `S-10A: amber-100`, `S-11A: orange-100`, `S-12P: rose-100`, `S-1P: purple-100`, `S-2P: slate-200`, `C-*: teal-100/200/300/400/500`. |
| Implementation | CSS classes keyed by `short_code` in a constants file. Applied to grid cells. |
| `RD` / `LWOP` | Gray-100 / Red-50. |

#### Deferred to V2
- **3.3 Apply Template** — needs BEI Shift Template weekly pattern rows (schema design pending)
- **3.4 Mobile Day-Card** — needs UX research on bottom sheet vs drawer, read-only vs editable

### Phase 4 — Tests & Build Integrity

| Task | Classification | Details |
|------|---------------|---------|
| 4.1 Remove old approval workflow from labor plan (if still present) | [CHECK] | Read `supervisor.py` — if approval flow code exists, remove it. If already gone, skip. |
| 4.2 Write Build Integrity Matrix | [BUILD] | S026-required artifact. |
| 4.3 Write CTA Wiring Matrix | [BUILD] | Every button → handler mapping. |
| 4.4 Write Dependency Map | [BUILD] | API → hook → backend method mapping. |

#### 4.5 Pre-Written L3 Test Scenarios

| # | Scenario | Input | Expected |
|---|----------|-------|----------|
| L3-S043-01 | Happy path: publish schedule, auto-attendance marks Present | Publish S-9A for employee, employee punches in at 09:10, out at 18:05 | Attendance record: Present, late_entry=0 |
| L3-S043-02 | Late arrival | Publish S-9A, employee punches in at 09:20 (> 15 min grace) | Attendance: Present, late_entry=1 |
| L3-S043-03 | Absent — no punch | Publish S-9A, no Employee Checkin for the day | No Attendance record after `process_attendance_after`. Missing punch report includes this employee. |
| L3-S043-04 | Half day | Publish S-9A, employee punches in at 09:00, out at 12:30 (3.5h < 4h threshold) | Attendance: Half Day |
| L3-S043-05 | Missing punch — punch in, no punch out | Publish S-9A, employee punches in at 09:00, no out punch | Attendance: Present (Frappe marks based on checkin). Report flags as "Missing OUT". |
| L3-S043-06 | Cross-midnight commissary | Publish C-5P (17:00-02:00), employee punches in at 17:05, out at 01:55+1d | Attendance on START date: Present |
| L3-S043-07 | Holiday — no false absent flood | Company holiday on March 20. Employees have Shift Assignments but don't punch. | No Attendance records generated. Report skips holiday. |
| L3-S043-08 | Copy previous week | Store has published plan for Week 11. User clicks "Copy Previous Week" for Week 12. | Grid populates with Week 11 shifts, dates shifted to Week 12. |

---

## RESOLVED: Shift Data (Investigated 2026-03-14)

All 4 original blockers from S033 resolved via Google Drive investigation across 65+ store accounts and 2,708 schedule files. Full evidence: `tmp/s043_shift_schedule_investigation.md`

- **Finding 1:** BEI does NOT use named shifts — raw time ranges in Google Sheets
- **Finding 2:** 7 retail shift patterns (08:00-17:00 through 14:00-23:00)
- **Finding 3:** 5 commissary patterns (04:00-13:00 through 17:00-02:00), 2 cross midnight
- **Finding 4:** Grace period = 15 minutes universal
- **Finding 5:** PM Night and Night shifts cross midnight
- **Finding 6:** No store uses more than 3 of the 7 patterns
- **Finding 7:** Report recipients: store supervisor + Area Supervisor + hr@bebang.ph

---

## Vertical Slice

Anchor on **SM East Ortigas** (best data — 30 weeks of schedule history):
1. Seed all 12 Shift Types with ALL required fields (Phase 0)
2. Publish a weekly plan for SM East Ortigas (existing publish bridge)
3. Wait for Frappe auto-attendance to run (hourly) — verify Attendance records
4. Missing punch report sent to SM East Ortigas supervisor + hr@bebang.ph at 00:00 PHT
5. **Day 1 verification = technical complete.** 1-week soak is post-deploy monitoring, not a sprint gate.

**Acceptance criteria for vertical slice:**
- All SM East Ortigas employees with shifts have Attendance records within 2 hours of shift end
- Late detection matches actual punch times (spot-check 5 employees)
- Missing punch report correctly identifies employees with no punch-out
- No false absents on rest days or holidays

---

## Technical Risk: Cross-Midnight Shifts

Commissary PM/Night shifts (16:00→01:00, 17:00→02:00) need `process_attendance_after` set to next-day time. Frappe's auto-attendance should handle this if configured correctly, but must be verified explicitly in Phase 1 (Task 1.4).

**Mitigation:** Deploy retail-only first (no midnight crossing). Verify commissary in a separate test before enabling for commissary employees.

---

## Deploy Sequence (All Phases)

```
Phase 0 Deploy:
  1. git push → PR → merge to production (supervisor.py fix, bei_planned_shift Link fix, short_code field)
  2. SSH → bench migrate → bench restart
  3. Run seed script → verify has_incorrect_shift_config()=False for all 12
  4. Vercel deploy (portal dropdown + RBAC fix)
  5. Verify: publish test plan → Shift Assignment created → auto-attendance fires within 1 hour

Phase 1 Deploy:
  (No code deploy needed — Phase 1 is verification of Phase 0 configuration)
  If edge case handlers needed (1.6): deploy as hotfix PR

Phase 2 Deploy:
  1. git push → PR → merge (missing_punch_report.py, hooks.py scheduler entry)
  2. SSH → bench migrate → bench restart
  3. Verify scheduler appears in Frappe Scheduler Log
  4. Wait for 00:00 PHT → confirm report sends to Chat + email

Phase 3 Deploy:
  1. Vercel deploy (copy-week, validation, color grid)
  2. Verify in portal with test account
```

---

## Autonomous Execution Contract

```yaml
completion_condition:
  - 12 Shift Types seeded with ALL required fields (has_incorrect_shift_config=False for all)
  - DM-4 fixed: bei_planned_shift.shift_type_name changed to Link
  - _ensure_shift_type_for_plan_row() sets all required fields
  - WAREHOUSE_USER added to canManageStoreSchedule()
  - Frappe auto-attendance verified generating correct Attendance records for SM East Ortigas
  - Missing punch report running at 00:00 PHT and delivering to Chat + email
  - Copy-previous-week working in portal
  - Shift validation warnings (double-schedule, 48h/week) working
  - Color-coded shift grid rendering
  - 8 L3 test scenarios written in docs/testing/scenarios/
  - Build integrity matrix, CTA wiring matrix, dependency map written

stop_only_for:
  - Missing credentials or access
  - Cross-midnight auto-attendance fails after 3 attempts (need Frappe source investigation)
  - Destructive production data changes requiring explicit approval
  - Frappe auto-attendance creates corrupt Attendance records (data integrity risk)

continue_without_pause_through:
  - Shift Type seeding (data validated from 2,708 source files)
  - DM-4 fix + bench migrate
  - Portal code changes + Vercel deploy
  - Missing punch report development + deploy
  - Phase 3 UX development + deploy
  - L3 scenario writing + execution
  - Build integrity artifacts

blocker_policy:
  programmatic: fix and continue
  cross_midnight: verify with test data first, research if 3 failures
  production_seed: proceed (shift data validated)
  bench_migrate: verify table exists after migrate, retry once if missing

signoff_authority: single-owner (Sam)

canonical_closeout_artifacts:
  - output/agent-runs/YYYY-MM-DD_s043-schedule-attendance-v2/RUN_STATUS.json
  - output/agent-runs/YYYY-MM-DD_s043-schedule-attendance-v2/RUN_SUMMARY.md
  - output/plan-audit/s043-schedule-attendance-bridge-v2/consolidated_audit_report.md
  - docs/testing/scenarios/s043-schedule-attendance-l3.md
  - docs/plans/SPRINT_REGISTRY.md (update S043 status on completion)
  - this plan (update status in YAML block)

status_reconciliation:
  When any of these change, update ALL in same work unit:
  - RUN_STATUS.json
  - RUN_SUMMARY.md
  - This plan's YAML status
  - SPRINT_REGISTRY.md (if sprint state changes)
```

## Execution Authority

This sprint is intended for autonomous end-to-end execution. Do not stop for progress-only updates. Only pause for items listed in `stop_only_for`.

## Agent Boot Sequence

1. Read this plan fully.
2. Read `docs/plans/SPRINT_REGISTRY.md` for cross-sprint context.
3. Read `hrms/api/supervisor.py` — existing publish bridge and `_ensure_shift_type_for_plan_row()`.
4. Read `hrms/hr/doctype/bei_planned_shift/bei_planned_shift.json` — the DM-4 field to fix.
5. Read `bei-tasks/app/dashboard/supervisor/labor-plan/page.tsx` — existing portal page.
6. Read `bei-tasks/lib/roles.ts` — RBAC predicate to update.
7. Read `bei-tasks/hooks/use-labor-plan.ts` — existing hook.
8. Read `.claude/rules/frappe-development.md` — DM checklist.
9. Confirm all Phase 0 dependencies are met before starting.
