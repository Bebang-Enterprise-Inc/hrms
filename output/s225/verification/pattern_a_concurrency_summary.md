# S225 Phase 5 — Pattern A Concurrency Stress Test

- Test config: 10 parallel `create_stock_transfer` calls
- Source warehouse: `PINNACLE COLD STORAGE SOLUTIONS - BKI`
- Item: `PM007` × 1.0 per call
- MR used: `MAT-MR-2026-00135`

**Result: PASS**

| Metric | Value |
|---|---|
| Successful calls | 10 / 10 |
| Negative-stock errors | 0 |
| MySQL 1213 deadlocks | 0 |
| MR-exhausted (acceptable serialization) | 0 |
| Other failures | 0 |
| Max elapsed per call | 27528 ms |

## Per-call details

| Idx | OK | Elapsed (ms) | Category | SE | Error |
|---|---|---|---|---|---|
| 0 | True | 20572 | - | MAT-STE-2026-01045 |  |
| 1 | True | 16211 | - | MAT-STE-2026-01043 |  |
| 2 | True | 18512 | - | MAT-STE-2026-01044 |  |
| 3 | True | 7499 | - | MAT-STE-2026-01039 |  |
| 4 | True | 25192 | - | MAT-STE-2026-01047 |  |
| 5 | True | 14135 | - | MAT-STE-2026-01042 |  |
| 6 | True | 11825 | - | MAT-STE-2026-01041 |  |
| 7 | True | 27528 | - | MAT-STE-2026-01048 |  |
| 8 | True | 22577 | - | MAT-STE-2026-01046 |  |
| 9 | True | 9847 | - | MAT-STE-2026-01040 |  |

## Cleanup

- MAT-STE-2026-01045: failed
- MAT-STE-2026-01043: failed
- MAT-STE-2026-01044: failed
- MAT-STE-2026-01039: failed
- MAT-STE-2026-01047: failed
- MAT-STE-2026-01042: failed
- MAT-STE-2026-01041: failed
- MAT-STE-2026-01048: failed
- MAT-STE-2026-01046: failed
- MAT-STE-2026-01040: failed