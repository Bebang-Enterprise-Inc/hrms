# S166 Strict Browser-Proof Audit (2026-04-08)

**Rule:** Every scenario must have verifiable browser evidence or is reclassified as FAILED.

## Overall verdict counts

| Verdict | Count |
|---|---|
| AUDIT_FAILED_NO_BROWSER_PROOF | 93 |
| AUDIT_FAILED_API_ONLY | 37 |
| LEGITIMATE_SKIP_WITH_PROOF | 31 |
| VERIFIED_BROWSER_PASS | 18 |
| VERIFIED_BROWSER_FAIL | 10 |
| VERIFIED_BROWSER_DEFECT_PASS | 6 |
| AUDIT_FAILED_MISSING_SCREENSHOT | 2 |
| AUDIT_FAILED_FABRICATED | 0 |
| **TOTAL** | **197** |

## Per-lane breakdown

| Lane | VERIFIED_PASS | VERIFIED_DP | VERIFIED_FAIL | LEGIT_SKIP | AUDIT_FAILED |
|---|---|---|---|---|---|
| lane_a | 9 | 5 | 3 | 28 | 41 |
| lane_b | 0 | 0 | 0 | 0 | 9 |
| lane_c | 5 | 0 | 1 | 0 | 5 |
| lane_d | 0 | 1 | 0 | 3 | 10 |
| lane_e | 0 | 0 | 0 | 0 | 8 |
| lane_f | 0 | 0 | 0 | 0 | 15 |
| lane_g | 0 | 0 | 0 | 0 | 6 |
| lane_h | 0 | 0 | 0 | 0 | 1 |
| retest_r1 | 1 | 0 | 0 | 0 | 0 |
| retest_r2 | 1 | 0 | 3 | 0 | 0 |
| retest_r2_fix | 0 | 0 | 3 | 0 | 0 |
| retest_r3 | 2 | 0 | 0 | 0 | 2 |
| retest_r4 | 0 | 0 | 0 | 0 | 35 |
