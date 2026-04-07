# S166 Strict Browser-Proof Audit v3 (2026-04-08)

**Rule:** Every scenario must have verifiable browser evidence or is reclassified as FAILED.
**Operator:** Orchestrator (no subagent trust). All file inspection direct.

## Overall counts

| Verdict | Count |
|---|---|
| VERIFIED_BROWSER_PASS | 81 |
| AUDIT_FAILED_UNDETERMINED | 50 |
| LEGITIMATE_SKIP_WITH_PROOF | 44 |
| VERIFIED_BROWSER_FAIL | 13 |
| VERIFIED_BROWSER_DEFECT_PASS | 6 |
| AUDIT_FAILED_NO_BROWSER_PROOF | 3 |
| **TOTAL** | **197** |

## Per-lane breakdown

| Lane | VERIFIED PASS | VERIFIED DP | VERIFIED FAIL | LEGIT SKIP | AUDIT FAILED |
|---|---|---|---|---|---|
| lane_a | 49 | 5 | 3 | 28 | 1 |
| lane_b | 1 | 0 | 0 | 8 | 0 |
| lane_c | 5 | 0 | 1 | 5 | 0 |
| lane_d | 2 | 1 | 0 | 3 | 8 |
| lane_e | 4 | 0 | 0 | 0 | 4 |
| lane_f | 13 | 0 | 2 | 0 | 0 |
| lane_g | 1 | 0 | 0 | 0 | 5 |
| lane_h | 1 | 0 | 0 | 0 | 0 |
| retest_r1 | 1 | 0 | 0 | 0 | 0 |
| retest_r2 | 1 | 0 | 3 | 0 | 0 |
| retest_r2_fix | 0 | 0 | 3 | 0 | 0 |
| retest_r3 | 3 | 0 | 1 | 0 | 0 |
| retest_r4 | 0 | 0 | 0 | 0 | 35 |

## Discrepancies (Summary vs Evidence)

| Agent | Scenario | Summary claimed | Evidence actual | Type |
|---|---|---|---|---|
| R3 | EMP-UX-004 | PASS_POST_FIX | STILL_BROKEN | SUMMARY_LIED |
