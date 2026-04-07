# S166 Strict Browser-Proof Audit v4 (2026-04-08)

**Source of truth:** form_submissions.json per lane (canonical verdict).
**Verification:** evidence files cross-checked for actual browser actions or screenshots.
**Operator:** Orchestrator (no subagent trust).

## Overall counts

| Verdict | Count |
|---|---|
| AUDIT_FAILED_UNDETERMINED | 48 |
| VERIFIED_BROWSER_PASS | 25 |
| LEGITIMATE_SKIP_WITH_REASON | 20 |
| LEGITIMATE_SKIP_WITH_PROOF | 19 |
| AUDIT_FAILED_NEVER_REDONE | 10 |
| VERIFIED_BROWSER_DEFECT_PASS | 5 |
| VERIFIED_BROWSER_FAIL | 3 |
| AUDIT_FAILED_NO_BROWSER_PROOF | 2 |
| **TOTAL** | **132** |

## Per-lane breakdown

| Lane | VERIFIED PASS | RBAC API | DEFECT PASS | FAIL | LEGIT SKIP | AUDIT FAILED |
|---|---|---|---|---|---|---|
| lane_a | 22 | 0 | 5 | 2 | 37 | 14 |
| lane_b | 0 | 0 | 0 | 0 | 0 | 9 |
| lane_c | 0 | 0 | 0 | 0 | 0 | 5 |
| lane_d | 0 | 0 | 0 | 0 | 0 | 9 |
| lane_e | 0 | 0 | 0 | 0 | 0 | 7 |
| lane_f | 0 | 0 | 0 | 0 | 0 | 15 |
| lane_g | 3 | 0 | 0 | 1 | 2 | 0 |
| lane_h | 0 | 0 | 0 | 0 | 0 | 1 |
| retest_r1 | 0 | 0 | 0 | 0 | 0 | 0 |
| retest_r2 | 0 | 0 | 0 | 0 | 0 | 0 |
| retest_r2_fix | 0 | 0 | 0 | 0 | 0 | 0 |
| retest_r3 | 0 | 0 | 0 | 0 | 0 | 0 |
| retest_r4 | 0 | 0 | 0 | 0 | 0 | 0 |

## Discrepancies (Summary vs Evidence)

| Agent | Scenario | Summary claimed | Evidence actual | Impact |
|---|---|---|---|---|
| R3 | EMP-UX-004 | PASS_POST_FIX | STILL_BROKEN | Defect #6 (compensation list-page modal) NOT closed |
