# S237 Defect Register

No defects detected during S237 execution.

## Pre-existing pollution remediated (32 rows)

The L3 test pollution that S237 cleaned was pre-existing — created on 2026-04-07 and 2026-04-09 by `test.hr@bebang.ph` and `test.hrmanager@bebang.ph`. Not a defect introduced by S237.

## Notes for future cleanup

The 53 total test rows in `tabEmployee` (the broader L3 test cohort) are NOT all cleaned by S237 — only the 32 that were squatting on 9xxxxxx real-range Bio IDs. The remaining 21 test rows have `attendance_device_id IS NULL` already (e.g., the original 10 TEST-XXX-001 rows from 2026-02-22 created by Administrator) and pose no Bio ID collision risk. They can be left as-is or cleaned up in a future hygiene sprint.

## Rows that were NOT touched

- HR-EMP-00027 (L3 SQL Verify5255) — already NULL attendance_device_id
- BEI-EMP-2026-00001..00003 (L3 SQL Verify) — already NULL
- HR-EMP-00028 (Test TransferE2E) — already NULL
- HR-EMP-00030..00032, 00044..00046 — already NULL
- TEST-HR-001, TEST-AREA-001, TEST-CREW-001, TEST-STAFF-001, TEST-AUDITOR-001, TEST-PROJECTS-001, TEST-PROJECTS-002, TEST-WAREHOUSE-001, TEST-COMMISSARY-001, TEST-SUPERVISOR-001 — all have attendance_device_id NULL since 2026-02-22

These are well-behaved test fixtures that don't violate the new S237 rule.
