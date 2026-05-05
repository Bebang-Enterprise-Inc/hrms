# S237 — L3 Test Pollution Cleanup + Test Bio ID Range Reservation + Skill Amendments

**Status:** AGENT_BUILD_COMPLETE 2026-05-05
**Branch:** `s237-l3-test-pollution-cleanup`

## Frappe `tabEmployee` cleanup results

| Action | Rows | Bio IDs affected |
|---|---|---|
| Migrated Active test rows to 3xxxxxx range | 6 | 9001909, 9001910, 9001911, 9001912, 9001914, 9001916 → 3000001-3000006 |
| NULLed Left test rows | 26 | 9001883–9001917 (Carlos/Cristina/Caleb/Camille Lane-C, Maria Santos, L3TEST RETEST, L3RT2, BROWSERTEST FINAL01, APPROVETEST FINAL — all status=Left) |
| **Total mutated** | **32** | **All 31 9xxxxxx test ghosts cleared from real-range** |

## 3xxxxxx test range now occupied

| New Bio | Frappe row | employee_name | Status |
|---|---|---|---|
| 3000001 | HR-EMP-00062 | L3RT2 RETEST02FINAL | Active |
| 3000002 | HR-EMP-00063 | L3RT2 FINALTEST | Active |
| 3000003 | HR-EMP-00064 | L3RT2 RT02FINAL | Active |
| 3000004 | HR-EMP-00065 | L3RT2 RT02FINAL | Active |
| 3000005 | HR-EMP-00067 | L3RT2 RT02FINAL | Active |
| 3000006 | HR-EMP-00069 | BROWSERTEST FINAL01 | Active |

## Bio IDs now free for S228 P4 import

All 31 Bio IDs in the range 9001883–9001917 are now freely assignable to real employees in Frappe `tabEmployee`. S228's pending HR-audited Frappe insert (53 new hires from the New Hires Masterlist) will succeed without collision.

## Skill amendments

3 SKILL.md files updated with the new test Bio ID rules:
- `.claude/skills/l3-v2-bei-erp/SKILL.md` — added "TEST EMPLOYEE & ACCOUNT NUMBERING — NON-NEGOTIABLE (S237)" with 6 rules
- `.claude/skills/write-plan-bei-erp/SKILL.md` — added "S237 Test Employee & Account Numbering Rule"
- `.claude/skills/audit-plan-bei-erp/SKILL.md` — added "S237 Test Employee & Account Numbering Audit Rule" with 7 blocker classes

## Going forward

- All test Employee `attendance_device_id` MUST be in `3000001..3999999`
- All test `employee_name` MUST start with `L3-`, `TEST-`, `L3TEST `, `BROWSERTEST `, or `APPROVETEST `
- All test login emails MUST match `test.X@bebang.ph` from `memory/testing-accounts.md`
- All test branches MUST use `TEST-*` prefix
- Plan audits will reject any test data violating these rules

## SSM CommandIds

- 8c5b546c-179a-4439-9252-288e9e54085f — main cleanup execution (Steps 1-6)
