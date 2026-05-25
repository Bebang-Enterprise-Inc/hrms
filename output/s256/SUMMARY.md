# S256 Summary — AP Master v3.10 + Source-of-Truth Redesign

**Deployed:** 2026-05-25 | **Version:** 17 | **Branch:** `s256-ap-source-redesign`

## 6-Item Completion

| # | Item | Status | Key metrics |
|---|---|---|---|
| 1 | Intercompany broadened to 14 affiliates | DONE | 15-pattern allowlist (Bebang + 14 non-Bebang per Denise Section B) |
| 2 | Auto-tag 3PL bypass suppliers | DONE | 8-pattern const; 94 historical rows retagged; FPM-side deferred to S257 |
| 3 | FPM-SOA-aware dedup race fix | DONE | `FPMSOA|payeeKey|amt` key added to existingIndex |
| 4 | Source-of-truth redesign (Denise D2) | DONE | seedFromProcurementApp_ WORKING (138 new rows in dry-run); denise_pp_seed_disabled flag ready; HO opening balance one-shot has minor header issue (see DEFECTS) |
| 5 | Bridge PII audit | DONE | 5 sheets audited; 2 tabs flagged (supplier TIN/address — NOT employee PII); 0 restrictions needed |
| 6 | /finance-ap training refresh | DONE | 96/96 locks, Joevic added, S255+S256 entries, Bridge matrix updated, 3 mirrors synced |

## Deployment Details

- Apps Script project: `1pE8wt_z8NA9q__PNbUilJ72UE0_EI3DmurJekkw6mbgtHr8hosnKsNRF`
- Production deployment: `AKfycbw-AuqJq6OyMV6DGarGWEruDoez04OETlWFQoeppNjvzoeSOJOomPOZNsVPE9iuV6ZC_Q`
- Version: 17 (v3.10)
- v3.10 source size: ~99K bytes
- v3.9 backup: `output/s256/script_source_backup_v39.gs` (95,031 bytes)

## Dry-Run Results (v3.10 version 17)

| Metric | Value |
|---|---|
| Status sync updates | 22 |
| Status sync tabs | 4 (SOA=1386, HO=4499, CAPEX=154, Intercompany=336) |
| Procurement App seed (NEW) | 138 rows would append |
| Denise PP seed | 1 new row (most already in AP Master) |
| FPM seed | 0 new (all existing) |
| HO Opening Balance | Skipped (header detection issue) |

## Cloud Scheduler

- Paused: 2026-05-25 ~14:30 PHT (Phase 0.5)
- Resumed: 2026-05-25 ~15:45 PHT (Phase 8.6)
- Total pause: ~75 minutes
- Current state: ENABLED

## Data Operations Performed

- Phase 3: 0 HO rows migrated to Intercompany (no affiliate fund-transfers currently in HO)
- Phase 5: 94 bypass-supplier rows retagged from 'FPM' to 'Denise PP - Manual' on HO tab
