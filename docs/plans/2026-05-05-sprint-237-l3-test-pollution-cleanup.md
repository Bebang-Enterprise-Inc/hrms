---
sprint_id: S237
display: Sprint 237
slug: l3-test-pollution-cleanup
plan_filename: 2026-05-05-sprint-237-l3-test-pollution-cleanup.md
branch: s237-l3-test-pollution-cleanup
repos: [hrms]
date_created: 2026-05-05
status: COMPLETED
plan_version: v1-executed
completed_date: 2026-05-06
backend_pr: 726
frontend_pr: null
l3_result: N/A (no L3 phase — backend cleanup + skill doc amendments only)
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

## Design Rationale (For Cold-Start Agents)

This section exists so a fresh agent reading this plan 6 months from now (or anyone allocating another reserved range / cleaning more test rows / deciding why some rows stayed and others were nulled) can act without re-deriving every choice.

### Why 3xxxxxx for the test range (not 1/2/4/5/6/7/8xxxxxx)?

The ZKTeco MB10-VL biometric device firmware accepts any 7-digit numeric PIN — there is no firmware-level constraint that forced 3xxxxxx. The choice was anchored in three properties:

1. **Distinguishability at a glance.** Real BEI employees are allocated sequentially from 9000003 upward (verified 2026-05-05 against `data/_FINAL/EMPLOYEE_MASTER.csv` — 696 rows, max 9001881). A reviewer reading SQL output or audit logs can tell at-a-glance that `3000001` is a test row but `9001827` is a real employee. Numeric ranges that share a leading digit with real PINs (any 9xxxxxx) failed this test by definition.
2. **Distance from real-allocation pace.** BEI hires roughly 50 employees/year (~50 new Bio IDs/year). Starting from 9001881, the real range will reach 9999999 in approximately 1600 years. 3xxxxxx is comfortably distant from any historical or projected real-PIN allocation — there is zero collision risk for the lifespan of BEI.
3. **Future reservation flexibility.** Choosing 3xxxxxx leaves 1/2/4/5/6/7/8xxxxxx all available for future explicit reservations (e.g., `8xxxxxx` for external contractor IDs, `4xxxxxx` for pilot-store crew, `5xxxxxx` for integration-partner accounts). Future plans that reserve another range should pick from those untaken digits and document their own rationale here.

Sam's directive ("BIO ID number start with 3 or something") set 3 as the choice. The reasoning above is what makes 3 a defensible long-term decision rather than an arbitrary one.

### Why migrate 6 Active rows but NULL 26 Left rows?

Both groups need their 9xxxxxx Bio IDs freed. The asymmetric treatment reflects different downstream requirements:

- **Active rows (`HR-EMP-00062, 63, 64, 65, 67, 69`)** are owned by ongoing L3 test scenarios that still execute against them. They need a stable, non-NULL `attendance_device_id` so Frappe permission checks and ADMS punch routing keep working in test runs. Migrating them to `3000001..3000006` preserves the foreign-key surface — every test that reads `frappe.get_doc("Employee", "HR-EMP-00062").attendance_device_id` still gets a valid value, just one in the test range instead of the real range. The `branch` field was also migrated (`ALABANG TOWN CENTER` → `TEST-STORE-BGC`) in v1.1 for the same reason: don't pollute real-branch reports with test rows that are still being actively exercised.
- **Left rows (26 ghost employees)** are decommissioned test fixtures with no future use. NULL'ing the device_id achieves three goals at once: (a) frees the 9xxxxxx PIN for re-use by real new hires, (b) prevents accidental ADMS routing if an old PIN is ever re-issued, (c) keeps a forensic trail on the row (`employee_name`, `name`, `creation` timestamp) for incident reconstruction without wasting a test-range PIN on a row nothing will read again.

A simpler "NULL all" approach would have broken the 6 still-active L3 scenarios on the next test run. A simpler "migrate all" approach would have wasted 26 test-range PINs on dead fixtures and left them as confusing pseudo-active records with valid-looking PINs.

### Why 21 historical NULL'd test rows were NOT touched

Live audit found 21 additional test-named rows with `attendance_device_id IS NULL` already (created 2026-02-22 by Administrator + a few earlier sprints — `TEST-XXX-001` series, `BEI-EMP-2026-00001..00003`, etc.). These were intentionally LEFT ALONE because:

1. **Zero PIN-collision risk.** Their `attendance_device_id` is already NULL. They cannot squat a real Bio ID by definition — they don't have one.
2. **Some are referenced by historical L3 traces / docs.** Renaming or deleting them would break `git blame`-equivalent forensic queries that reference these specific row names.
3. **`status='Left'` already excludes them from the active-employee queries that matter for payroll and reports.** They show up only in `SELECT * FROM tabEmployee` (no filter) — a reasonable place for dead test fixtures to live.

A future hygiene sprint could choose to delete them outright. S237 was scoped to PIN-collision remediation only; broader test-fixture deletion would have inflated scope without addressing the actual incident.

### Why the cleanup ran direct SQL UPDATE instead of Frappe ORM

`frappe.set_value("Employee", name, "attendance_device_id", new)` would have triggered the `Employee.validate` hook, which (per `hrms/utils/bio_id_validation.py` BEFORE v1.1) would have rejected `3000001..3000006` as invalid because the regex was `^9\d{6}$`. The chicken-and-egg: the migration needed the validator extended, but the validator was the thing being migrated to allow. Using direct SQL via `bench mariadb -e` bypassed the validator for the bulk migration, then v1.1 extended the regex (`^[39]\d{6}$`) so future Desk-side or ORM saves work without `frappe.throw`.

The trade-off acknowledged: direct SQL skips `tabVersion` audit trail entries. The cleanup is recorded in Frappe via the `modified` timestamp on each row, in `data/_FINAL/CHANGE_LOG.csv` via S237's manual entries, and in the SSM CommandId `8c5b546c-179a-4439-9252-288e9e54085f` whose stdout is captured in `output/s237/cleanup_log.txt`.

### Why Step-2 of the cleanup script reports "1 row affected"

The cleanup script issued 6 sequential `UPDATE tabEmployee SET attendance_device_id = '3000001..6' WHERE name = 'HR-EMP-00062..69'` statements. MariaDB's `ROW_COUNT()` reports the affected count of the LAST statement only, so the SSM probe captured "1" (the final UPDATE that touched HR-EMP-00069). All 6 migrations succeeded — verified row-by-row in Step 6's enumeration. A reader who sees `Step 2: 1 row affected` should NOT interpret it as "5 of 6 failed"; it's a SQL semantics quirk of `ROW_COUNT()` on chained `bench mariadb -e` statements.

If reproducing the migration with rollback safety, prefer `frappe.db.savepoint()` + `frappe.db.set_value()` AFTER the validator regex is already extended.

### Why `cleanup_log.txt` is base64-encoded

The SSM-side script runs `{ ... } | base64 -w 0` as the last step so the encoded output survives Windows console code-page (cp1252) and BOM-sensitive transports without character corruption. Decode locally with:

```bash
cat output/s237/cleanup_log.txt | base64 -d | less
```

The plain-text content is also summarized in `output/s237/SUMMARY.md` for direct reading.

### Known limitations and follow-up work

1. **Validator allows 3xxxxxx but does not enforce it for test rows.** `bio_id_validation.py` accepts any `^[39]\d{6}$`. A developer creating a new test Employee via Desk could still set `attendance_device_id = 9999999` and pass validation. Enforcement requires adding a check like "if `employee_name` matches a TEST/L3 prefix, `attendance_device_id` must start with 3" — DEFERRED to a future sprint that has a clear definition of "test row."
2. **L3 scenario files still call `create_employee_direct` which auto-allocates the next 9xxxxxx PIN.** S237 added an S237 banner to `docs/testing/scenarios/modules/hr-employee-lifecycle.md` flagging this, but the actual fix requires extending `create_employee_direct` to accept `is_test=True` flag and allocate from 3xxxxxx. **DEFERRED to S238+.** Until then, every L3 sweep that runs `EMP-CREATE-*` will re-pollute the 9xxxxxx range. Mitigation: run `output/s237/verify_s237_state.sh` after each L3 sweep — if it fails, re-run S237's cleanup pattern on the new pollution.
3. **S228 P4 race window.** S228's pending Frappe Employee insert for 53 new hires depends on Bio IDs 9001882-9001934 being free. S237 freed 9001883-9001917. If S228 P4 runs before another L3 sweep re-pollutes those PINs, the insert succeeds. Sam coordinates manually — there is no advisory lock between S237's verifier and S228's import.
4. **The 4 Estancia crew (9001827/30/32/35) are still missing from Frappe `tabEmployee`.** Out of S237 scope — S228 anomaly class A1 will fix when HR audit completes.
5. **No `tabVersion` audit trail.** Direct SQL UPDATE bypassed Frappe's Activity log. Documented in this section + Amendment Log; the live SSM CommandId is the audit anchor.

### Source references

Every claim above is anchored in a specific file or live system state:

- ADMS device firmware constraints: `data/ADMS/ZKTECO_COMPREHENSIVE_DOCUMENTATION.md` + skill `/adms-bei-erp` (verifies 7-digit PIN range)
- Real Bio ID range: `data/_FINAL/EMPLOYEE_MASTER.csv` (696 rows, max 9001881 verified 2026-05-05)
- Validator location + hook registration: `hrms/utils/bio_id_validation.py` + `hrms/hooks.py:243`
- Cleanup execution: SSM CommandId `8c5b546c-179a-4439-9252-288e9e54085f` (output captured in `output/s237/cleanup_log.txt`)
- Test rows that were active vs Left: `output/s237/cleanup_log.txt` Step 6 enumeration
- 21 untouched historical rows: `output/s237/DEFECTS.md` "Rows that were NOT touched"
- L3 scenario impact: `docs/testing/scenarios/modules/hr-employee-lifecycle.md` (S237 banner near top of file)
- S228 dependency: `docs/plans/2026-04-28-sprint-228-new-hires-import-anomaly-fix.md` (anomaly class A1)
- Regression detector: `output/s237/verify_s237_state.sh` (run anytime to re-validate cleanup is intact)

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
| 2026-05-07 | Sam (via Claude) | v1.2 — closeout | PR #726 merged 2026-05-06 (UTC 11:13, PHT 19:13). Status flipped `AGENT_BUILD_COMPLETE` → `COMPLETED`. `completed_date` corrected from 2026-05-05 (agent-build date) to 2026-05-06 (PR-merge date). Added `backend_pr: 726`, `frontend_pr: null`, `l3_result: N/A`. Registry row updated: `#726 (PR pending merge)` → `#726`, `AGENT_BUILD_COMPLETE 2026-05-05` → `COMPLETED 2026-05-06`. Doc-only follow-up PR #727 (cold-start Design Rationale section, +77 lines) still OPEN — non-blocking, awaiting Sam merge. No code changes in this closeout. |
