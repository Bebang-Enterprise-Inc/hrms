---
sprint_id: S253
display: Sprint 253
slug: brittany-3-head-office-enrollment
plan_filename: 2026-05-19-sprint-253-brittany-3-head-office-enrollment.md
branch: s253-brittany-3-head-office-enrollment
repos: [hrms]
date_created: 2026-05-19
status: AGENT_BUILD_COMPLETE
plan_version: v1
canonical_scope: none
---

# Sprint 253 — Brittany Office 3-Employee Head-Office Enrollment

## Source

Ron Andrew Santos chat 2026-05-19 10:38 AM PHT — enroll 3 head office hires at Brittany. Sam directive same day.

## Pre-write audit

| Bio ID | Name | Position | Master state | ADMS state |
|---|---|---|---|---|
| 9001916 | LIMOSNERO, MARCO R. | ACCOUNTING SUPERVISOR | ✅ store=BRITTANY OFFICE, bio_dev=BRITTANY OFFICE | Zero |
| 9001981 | TAMACA, JAMES M. | ACCOUNTING MANAGER | ⚠️ store=BLANK, bio_dev=BLANK (S252 sync) | Zero |
| 9001980 | TELAN, LEONIDA P. | SUPPLY CHAIN MANAGER | ⚠️ store=BLANK, bio_dev=BLANK (S252 sync) | Zero |

All 3 head office devices healthy (Brittany/Capital House/Shaw all heartbeating).

## What this sprint did

### W1 — Master CSV updates (gitignored, local SSOT)
Filled `store_location` + `bio_device_name` = `BRITTANY OFFICE` for TELAN + TAMACA (were blank from S252 Sheet sync; Ron's request confirms their assignment).

### W2 — Sheet writeback
Cells M796 (TELAN) + M797 (TAMACA) set to `BRITTANY OFFICE`.

### W3 — ADMS enrollment: 9 USERINFO (3 employees × 3 HO devices)

Head office cluster:
- UDP3251600245 (Brittany Office)
- UDP3235200625 (Capital House)
- UDP3235200629 (Shaw Commissary)

Per `clusters.md`: head office staff are enrolled on all 3 HO devices (they move between locations).

| PIN | Name | HO devices |
|---|---|---|
| 9001916 | LIMOSNERO, MARCO R. | 3 ✓ |
| 9001981 | TAMACA, JAMES M. | 3 ✓ |
| 9001980 | TELAN, LEONIDA P. | 3 ✓ |

**ACK rate at +30s: 9/9 (100%)**. Tab byte validation: 2 per command.

### W4 — CHANGE_LOG (7 rows)
2 EMPLOYEE_MASTER UPDATE + 2 GOOGLE_SHEET UPDATE_STORE + 3 ADMS ENROLL.

## What this sprint did NOT do

- ❌ NO Frappe insert (S228/S241 pattern continues)
- ❌ NO designation changes
- ❌ NO touch on roving_employees.py (separate sprint if formal AS/Manager registration desired)

## Sam handoff

1. Merge PR
2. Reply to Ron: 3 head office employees enrolled at all 3 head office devices (Brittany + Capital House + Shaw). 9/9 ACKED.
