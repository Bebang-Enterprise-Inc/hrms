---
sprint_id: S237
display: Sprint 237
slug: l3-test-pollution-cleanup
plan_filename: 2026-05-05-sprint-237-l3-test-pollution-cleanup.md
branch: s237-l3-test-pollution-cleanup
repos: [hrms]
date_created: 2026-05-05
status: AGENT_BUILD_COMPLETE
plan_version: v1-executed
completed_date: 2026-05-05
canonical_scope: none
canonical_scope_rationale: |
  Frappe `tabEmployee` UPDATE-only cleanup (set `attendance_device_id` to NULL or migrate to 3xxxxxx range) + 3 `.claude/skills/*-bei-erp/SKILL.md` doc edits.
  No tabCompany / tabWarehouse / tabCustomer / tabSupplier UPDATE/INSERT/DELETE.
  No Sales Invoice / Purchase Order / Material Request / Stock Entry / Journal Entry / Payment Entry / GL Entry creation.
  Touches only `tabEmployee` (excluded from canonical gate per docs/STORE_COMPANY_CANONICAL.md scope) and `.claude/skills/` markdown docs.
ceo_directive_source: 2026-05-05 directive after S230 ad-hoc enrollment exposed the L3-test-Bio-ID collision
evidence_committed:
  - output/s237/SUMMARY.md
  - output/s237/DEFECTS.md
  - output/s237/cleanup_log.txt
  - .claude/skills/l3-v2-bei-erp/SKILL.md
  - .claude/skills/write-plan-bei-erp/SKILL.md
  - .claude/skills/audit-plan-bei-erp/SKILL.md
  - docs/plans/2026-05-05-sprint-237-l3-test-pollution-cleanup.md
  - docs/plans/SPRINT_REGISTRY.md
evidence_transient: []
---

# Sprint 237 — L3 Test Pollution Cleanup + Test Bio ID Range Reservation (3xxxxxx) + Skill Amendments

> **Source:** CEO directive 2026-05-05. Triggered by S230 ad-hoc enrollment of CATINDOY (9001893) / BONGAY (9001854) / ESTRELLA (9001903) — forensic audit revealed Bio IDs 9001893 + 9001903 were squatted in Frappe by L3 test ghost rows from 2026-04-07 + 2026-04-09. Broader audit found **31 L3/test ghost rows total** holding real-range Bio IDs 9001883–9001917, blocking S228's HR-audited Frappe import for 31 real new hires.

> **PR-Handoff:** Agent created the PR and STOPS. Sam handles merge.

## What broke

L3 test scripts run by `test.hr@bebang.ph` (2026-04-07) and `test.hrmanager@bebang.ph` (2026-04-09) created **31 fake `tabEmployee` rows** for L3 testing. Those scripts assigned `attendance_device_id` values from the **real-employee 9xxxxxx range** (9001883–9001917) — Bio IDs that were unallocated at the time but that S228 imported from the New Hires Masterlist on **2026-04-28**, assigning them to actual new hires.

End state before this sprint:
- Master CSV (SSOT per CEO directive) has Bio 9001893 = CATINDOY, 9001903 = ESTRELLA, etc.
- Frappe `tabEmployee` has Bio 9001893 = "Maria Santos Santos Reyes (L3 ghost)" status=Left, 9001903 = "L3TEST RETEST07B" status=Left, etc.
- ADMS punches for 9001893/9001903 (post-2026-05-05 enrollment) would join to ghost rows in Frappe — payroll silently fails.

## What this sprint did

### W1 — Frappe cleanup (executed via SSM Postgres on hq.bebang.ph 2026-05-05)

```sql
-- 6 Active test rows migrated to 3xxxxxx range (preserve test history but free 9xxxxxx PINs)
UPDATE tabEmployee SET attendance_device_id = '3000001' WHERE name = 'HR-EMP-00062' AND status = 'Active';  -- L3RT2 RETEST02FINAL
UPDATE tabEmployee SET attendance_device_id = '3000002' WHERE name = 'HR-EMP-00063' AND status = 'Active';  -- L3RT2 FINALTEST
UPDATE tabEmployee SET attendance_device_id = '3000003' WHERE name = 'HR-EMP-00064' AND status = 'Active';  -- L3RT2 RT02FINAL
UPDATE tabEmployee SET attendance_device_id = '3000004' WHERE name = 'HR-EMP-00065' AND status = 'Active';  -- L3RT2 RT02FINAL
UPDATE tabEmployee SET attendance_device_id = '3000005' WHERE name = 'HR-EMP-00067' AND status = 'Active';  -- L3RT2 RT02FINAL
UPDATE tabEmployee SET attendance_device_id = '3000006' WHERE name = 'HR-EMP-00069' AND status = 'Active';  -- BROWSERTEST FINAL01

-- 26 Left test rows: NULL out attendance_device_id (frees Bio IDs)
UPDATE tabEmployee SET attendance_device_id = NULL
WHERE attendance_device_id REGEXP '^9[0-9]{6}$' AND status = 'Left'
  AND (UPPER(employee_name) LIKE '%L3%' OR UPPER(employee_name) LIKE '%TEST%' OR
       UPPER(employee_name) LIKE '%RETEST%' OR UPPER(employee_name) LIKE '%CONFLICT%' OR
       UPPER(employee_name) LIKE '%CARLOS LANE-C%' OR UPPER(employee_name) LIKE '%CALEB LANE-C%' OR
       UPPER(employee_name) LIKE '%CRISTINA LANE-C%' OR UPPER(employee_name) LIKE '%CAMILLE LANE-C%' OR
       UPPER(employee_name) LIKE '%MARIA SANTOS%' OR UPPER(employee_name) LIKE '%BROWSERTEST%' OR
       UPPER(employee_name) LIKE '%APPROVETEST%');
```

**Result (verified live):**
- Step 2 affected 1 row (last UPDATE only — ROW_COUNT() reports last statement); all 6 confirmed via Step 6 audit.
- Step 3 affected 26 rows.
- Step 4 verification: `SELECT … WHERE LIKE '%L3%' OR '%TEST%' AND attendance_device_id IS NOT NULL` returned ONLY the 6 migrated rows in 3xxxxxx range. **Zero test rows remain on 9xxxxxx Bio IDs.**
- Step 5 verification: 9001893 and 9001903 are now FREE in Frappe. Only 9001854 BONGAY (real) remains.

### W2 — Test Bio ID range reserved: `3000001..3999999`

The 9xxxxxx range is now strictly reserved for real BEI employees in the Master CSV. The 3xxxxxx range is reserved for test attendance_device_id values. These two ranges will NEVER collide.

### W3 — 3 skill amendments

| Skill | What was added |
|---|---|
| `/l3-v2-bei-erp` (`.claude/skills/l3-v2-bei-erp/SKILL.md`) | New "TEST EMPLOYEE & ACCOUNT NUMBERING — NON-NEGOTIABLE (S237)" section near the top with 6 enforcement rules: 3xxxxxx range, employee_name patterns (L3-/TEST-/L3TEST/BROWSERTEST/APPROVETEST), test login email pattern, test branch (TEST-STORE-BGC), teardown discipline, pre-seed audit query. |
| `/write-plan-bei-erp` (`.claude/skills/write-plan-bei-erp/SKILL.md`) | New "S237 Test Employee & Account Numbering Rule" section with 6 rules. Plans that propose 9xxxxxx test Bio IDs are CRITICAL blockers at audit time. |
| `/audit-plan-bei-erp` (`.claude/skills/audit-plan-bei-erp/SKILL.md`) | New "S237 Test Employee & Account Numbering Audit Rule" section with 7 specific blocker classes: `TEST_BIO_ID_REAL_RANGE_COLLISION` (CRITICAL), `TEST_EMPLOYEE_NAME_LOOKS_REAL` (WARNING), `TEST_BRANCH_USES_REAL_LOCATION` (WARNING), `TEST_LOGIN_NOT_IN_REGISTRY` (WARNING), `TEST_EMPLOYEE_TEARDOWN_MISSING` (CRITICAL), `MISSING_PRESEED_POLLUTION_CHECK` (WARNING), and 3 forbidden plan-pattern strings. |

## Verification

- ✅ Pre-cleanup audit: 31 test rows on 9xxxxxx Bio IDs in Frappe (live SSM 2026-05-05 ~13:00 PHT)
- ✅ Post-cleanup audit: 0 test rows on 9xxxxxx Bio IDs; 6 test rows now on 3000001..3000006
- ✅ 9001893, 9001903 free in Frappe (only the real 9001854 BONGAY row remains in our 3-Bio-ID lookup)
- ✅ Total `tabEmployee` rows: 748 (no rows deleted; 32 rows had only their `attendance_device_id` field changed)
- ✅ All 3 skill files have S237 sections inserted at logical locations
- ✅ SPRINT_REGISTRY.md S237 row added; "Next" bumped to S238

## Implication for S228 P4 (HR-audited Frappe import)

S228's pending Phase 4 (Frappe `tabEmployee` insert for 53 new hires) can now proceed safely. None of S228's reserved Bio IDs (9001882–9001934) are squatted by ghost rows anymore. When HR completes their Master audit and you greenlight S228 P4, the inserts will succeed without collision.

## Plans / scripts to update next (out of scope for S237)

- `data/_FINAL/EMPLOYEE_MASTER.csv` — no change needed (already had real employees on these Bio IDs)
- L3 scenario files in `docs/testing/scenarios/` that create test employees — should be reviewed at the next L3 sprint to ensure they use 3xxxxxx going forward
- `hrms/utils/adms_validation.py` — no change needed (it validates against Master CSV which already only has 9xxxxxx)

## Amendment Log

| Date | Author | Section | Change |
|------|--------|---------|--------|
| 2026-05-05 | Sam (via Claude) | INITIAL + EXECUTED | Plan written and executed in same session per CEO "Now" directive. 32 Frappe rows mutated, 3 skills amended, registry updated, PR created. canonical_scope=none verified. |
| 2026-05-06 | Sam (via Claude) | v1.1 — audit fixes | `/audit-plan-bei-erp` retrospective audit caught 2 CRITICAL + multiple WARNING findings on PR #726 BEFORE merge. v1.1 amendments: **(C-1 fix)** Recovered SPRINT_REGISTRY.md silent-revert — the original S237 commit's registry was based on the pre-S233/S234/S235 snapshot (worktree spawned 2026-04-29 from `3e47ceace`), so the diff against current production silently DELETED the S233 row + S235 row + downgraded S234 from "COMPLETED PR #716 merged" back to "PLANNED TBD". Recovered all 3 rows + appended fresh S237 row + bumped Next to S238. Same incident class as S161 (MEMORY.md `feedback_rebase_before_merge.md`). **(F-1 fix)** Extended `hrms/utils/bio_id_validation.py` regex from `^9\d{6}$` to `^[39]\d{6}$` — the original validator (registered as `Employee.validate` hook in `hrms/hooks.py:243`) would have rejected every future ORM `.save()` on the 6 migrated test rows (3000001..3000006). Bulk SQL UPDATE bypassed it for the migration but Desk-side edits or any `frappe.get_doc("Employee", "HR-EMP-00062").save()` would `frappe.throw`. **(F-4 / self-violation fix)** The 6 migrated test rows still had `branch='ALABANG TOWN CENTER'` (a real BEI branch with 10 active employees) — violating the new S237 audit rule's `TEST_BRANCH_USES_REAL_LOCATION` warning. Created `tabBranch.name='TEST-STORE-BGC'` and migrated all 6 rows' branch via UPDATE. ATC report queries no longer pull these test rows. **(C-CS-1 fix)** Added `output/s237/verify_s237_state.sh` regression-detection script — runs 4 idempotent SSM checks anytime to confirm the cleanup didn't drift. Audit evidence: `output/plan-audit/sprint-237-l3-test-pollution-cleanup/`. ~7 additional work units (32 → 39 total). |
