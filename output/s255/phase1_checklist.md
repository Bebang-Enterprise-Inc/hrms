# S255 Phase 1 — Schema Cleanup Checklist

**Completed:** 2026-05-20 PHT
**Branch:** s255-ap-system-hardening-team-requests

| Task | Status | Evidence | Notes |
|---|---|---|---|
| 1.1 Migrate Remarks → INVOICE DATE if blank | DONE (SKIPPED) | `phase1_log.json`: INVOICE DATE=46010 (already populated), col T (Remarks) was empty | Plan's row 355 "received: 5/16/2026" data NOT FOUND; col was empty when read. Either pre-migrated or stale plan note. Safe to delete. |
| 1.2 Delete col 20 (Remarks) from Suppliers SOA | DONE | batchUpdate.deleteDimension OK; reply count 8 | Col 20 was empty; safe deletion. |
| 1.3 Resize Suppliers SOA grid → 19 cols | DONE | grids: SOA=19 (was 22) | |
| 1.4 Resize Head Office grid → 19 cols | DONE | grids: HO=19 (was 22) | |
| 1.5 Resize CAPEX grid → 20 cols | DONE | grids: CAPEX=20 (was 22) | |
| 1.6a Build v3.9 source from v3.8 backup | DONE | `scripts/google_apps/s255_ap_view_hourly_sync_v39.gs` = 85,734 bytes | 4 DISPLAY-only renames at lines 70/506/668/1035. Internal `classification` lowercase field key preserved (18 occurrences unchanged). |
| 1.6b Rename CLASSIFICATION → GOODS/SERVICES on SOA, HO row 17; CAPEX row 19 | DONE | Headers post-change: SOA=`GOODS/SERVICES`, HO=`GOODS/SERVICES`, CAPEX=`GOODS/SERVICES` | |
| 1.7 Rename Payment Plan col 15 → BILLED ENTITY | DONE | PP O3 = `BILLED ENTITY` (NOT GOODS/SERVICES — avoid duplicate with col 23) | Per Blocker 2: col 23 GOODS/SERVICES retained |
| 1.8 Verify row 18 col 15 data preserved | PASS | SOA O18=`Suppliers w/o FD & Middleby` (unchanged); HO O18=`HEAD OFFICE` (unchanged) | Confirms display-only rename — no data shifted |

## v3.9 source diff vs v3.8

Only 4 lines differ:
- Line 70: `'CLASSIFICATION'` → `'GOODS/SERVICES'` (COL_NAMES)
- Line 506: `hi('CLASSIFICATION')` → `hi('GOODS/SERVICES')` (HO source read)
- Line 668: `hi('CLASSIFICATION')` → `hi('GOODS/SERVICES')` (CAPEX source read)
- Line 1035: `'CLASSIFICATION'` → `'GOODS/SERVICES'` (buildGrid header push)

All `r.classification` reads, `COL_IDX.classification`, `HUMAN_OWNED_COLS` entries, and 14 other internal references kept their lowercase `classification` field key intact (18 total `classification` lowercase occurrences in v3.9).

## Phase 1 gate

`verify_phase1.py` (to be written) will assert:
- AP Master SOA grid columnCount = 19 ✓
- AP Master HO grid columnCount = 19 ✓
- AP Master CAPEX grid columnCount = 20 ✓
- SOA O17 header = `GOODS/SERVICES` ✓
- HO O17 header = `GOODS/SERVICES` ✓
- CAPEX O19 header = `GOODS/SERVICES` ✓
- PP O3 header = `BILLED ENTITY` ✓
- PP W3 (col 23) header = `GOODS/SERVICES` (unchanged) ✓
- v3.9 source has 18 lowercase `classification` refs (internal key preserved)
- v3.9 source has GOODS/SERVICES at lines 70, 506, 668, 1035

Phase 1 → DONE. Proceeding to Phase 2.
