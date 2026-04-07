# S166 Lane H — EMP-CREATE-004 Summary

**Run:** 2026-04-07T04:05:04.284Z
**Final outcome:** PASS
**Unmapped branch discovered:** CAPITAL HOUSE
**Candidates tried:** 2 / 5
**Employees created (total, incl. trial-and-error):** 0
**Employees soft-deleted:** 0
**Runtime:** 49.2s

## Attempts

| # | Branch | Outcome | Toast | API Reason |
|---|--------|---------|-------|------------|
| 0 | BRITTANY OFFICE | FAILED | Employee BEI-EMP-2026-00004 created. Bio ID 9001882 enrolled on device UDP325160 |  |
| 1 | CAPITAL HOUSE | NO_DEVICE | Employee BEI-EMP-2026-00004 created. No biometric device mapped to CAPITAL HOUSE |  |

## Winning Attempt Evidence

- **Branch:** CAPITAL HOUSE
- **Toast:** `Employee BEI-EMP-2026-00004 created. No biometric device mapped to CAPITAL HOUSE — enroll manually.`
- **API reason:** `(not found in response)`
- **Employee created:** (unknown)

## Files
- form_submissions.json
- api_mutations.json
- state_verification.json
- EMP_STATE.json
- ORPHANS.csv
- DEFECTS.csv
- evidence/EMP-CREATE-004.json
- screenshots/
- artifacts/EMP-CREATE-004.trace.zip