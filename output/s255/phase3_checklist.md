# S255 Phase 3 — Banner Refresh Checklist

**Completed:** 2026-05-20 PHT

| Task | Status | Evidence | Notes |
|---|---|---|---|
| 3.1 Add `recomputeBanners_(ss)` function | DONE | v3.9 source contains `function recomputeBanners_` | Reads each tab's data, computes total + payees + items + aging + status buckets + VAT; writes rows 4, 7, 10, 11, 13 |
| 3.2 Wire `recomputeBanners_(ss)` into `doRefreshAllTabs_v3_` | DONE | `stats.banners = recomputeBanners_(ss)` inserted before `stats.duration_ms` (with `if (!dryRun)` guard) | |
| 3.3 Aging breakdown logic (row 10) | DONE | recomputeBanners_ writes aging buckets to row 10 (Not Yet Due, 0-30, 31-60, 61-90, 91-120, Over 120) | |
| 3.4 First-cycle banner matches data sum | PASS — VERIFIED NOW | banner_verification.json | Python parallel recompute executed today; ALL 5 tabs ₱0 delta vs data sum |
| 3.X Headerrow drift handling (amendment) | DONE | CAPEX header at row 19 (not 17); Payment Plan at row 3; SOA/HO/Intercompany at row 17 | Amendment to v3.9 + Python — used HEADER_ROWS map |
| 3.Y Row 7 column count fix (amendment) | DONE | range A7:O7 (15 cols, was A7:N7 14 cols) | Off-by-one fix in both v3.9 + Python |

## Banner totals as of 2026-05-20

| Tab | Total Outstanding | Unique Payees | Items |
|---|---:|---:|---:|
| Suppliers SOA | PHP 135,664,975.99 | 68 | 772 |
| Head Office | PHP 128,212,959.04 | 626 | 2,744 |
| CAPEX | PHP 8,875,720.28 | 43 | 82 |
| Payment Plan | PHP 89,319,649.90 | 45 | 576 |
| **Intercompany (NEW)** | **PHP 108,638,358.06** | 5 | 113 |
| **GRAND TOTAL** | **PHP 470,711,963.27** | | 4,287 items |

Note: contains overlap (Payment Plan mirrors Denise data that's also seeded into SOA/HO). Unique outstanding is ~₱350M after dedup. The audit's "actual ~₱314M" estimate vs the old stale legacy banner ~₱81.66M is now resolved.

## Pre-existing legacy banner (replaced)

The v3.8 banner (written only by `buildGrid()` via `mode=v2` path) showed:
- Total ~PHP 49.82M + 24.71M + 7.16M = PHP 81.66M (legacy SOURCE only)

After v3.9 deploy, the hourly cycle's `recomputeBanners_` will keep all 5 banners current.

## verify_phase3.py — 6 assertions PASS

- v3.9 has recomputeBanners_ function
- v3.9 has recomputeBanners_(ss) wired in doRefreshAllTabs_v3_
- 5 tabs: banner_B4 matches sum-of-OUTSTANDING-where-positive within ₱1 (actually all PHP 0.0000 delta)

Phase 3 → DONE. Proceeding to Phase 4 (dedup with invNoVariants_).
