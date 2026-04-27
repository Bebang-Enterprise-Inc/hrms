# S225 Phase 2 — Warehouse Duplicate Audit Report

**For Sam to review BEFORE authorizing Phase 3 consolidation.**

- Total warehouses scanned: **331**
- Duplicate clusters found: **2**
- Intercompany clusters (audit B-13 — excluded from APPROVED ALL): **0**
- Manual-review-required clusters: **0**
- Auto-apply-eligible clusters (with `S225 Phase 3 APPROVED ALL`): **2**
- Stranded SKUs across all duplicates: **79**
- Stranded stock units (sum of qty on losers): **32627.00**

## Per-cluster decision required

Sam, for each cluster below please confirm in a PR comment using one of these tokens:

- `S225 Phase 3 APPROVED ALL` — apply all clusters in the audit (excluding INTERCOMPANY-flagged ones)
- `S225 Phase 3 APPROVED: <cluster_id1>, <cluster_id2>` — apply only listed clusters
- `S225 Phase 3 APPROVED INTERCOMPANY: <cluster_id>` — explicit intercompany authorization
- `S225 Phase 3 SKIP: <cluster_id>` — skip listed clusters (with rationale)

---

## `cluster-3md-logistics-camangyanan-bki`

Status: auto-apply eligible

**Proposed Canonical Winner:**

| Name | Company | Stock units | Non-zero SKUs | Disabled | Is group |
|---|---|---|---|---|---|
| `3MD LOGISTICS - CAMANGYANAN - BKI` | `BEBANG KITCHEN INC.` | 797874.00 | 83 | 0 | 0 |

**Losers (to be DISABLED + stock migrated to winner):**

| Name | Company | Stock units | Non-zero SKUs | Disabled | Is group | Open MRs | Draft SEs |
|---|---|---|---|---|---|---|---|
| `3MD LOGISTICS – CAMANGYANAN - BKI` | `BEBANG KITCHEN INC.` | 32627.00 | 79 | 0 | 0 | 0 | 0 |

  Stock breakdown for loser `3MD LOGISTICS – CAMANGYANAN - BKI`:

  | Item code | Qty | UoM |
  |---|---|---|
  | A058 | 434.0 | PACK |
  | A059 | 550.0 | PACK |
  | A060 | 354.0 | PACK |
  | BEB-CCF | 40.0 | PACK |
  | CM30 | 54.0 | BUNDLE |
  | CM31 | 53.0 | BUNDLE |
  | CM32 | 47.0 | BUNDLE |
  | CM33 | 75.0 | BUNDLE |
  | CM34 | 24.0 | BUNDLE |
  | CM37 | 57.0 | BUNDLE |
  | CM38 | 573.0 | BUN |
  | CM39 | 419.0 | BUN |
  | CS007 | 7.0 | PIECE |
  | CS008 | 4.0 | PIECE |
  | CS012 | 48.0 | BUNDLE |
  | CS012-A | 5.0 | BUNDLE |
  | CS013 | 3000.0 | PIECE |
  | CS014 | 124.0 | PIECE |
  | CS016 | 228.0 | PIECE |
  | FG001 | 12194.0 | PIECE |
  | FG002-A | 1244.0 | KG |
  | FG003 | 387.0 | KG |
  | FG004 | 648.0 | KG |
  | FG005 | 131.0 | KG |
  | FG006 | 100.0 | KG |
  | FG007 | 92.0 | KG |
  | FG009 | 1043.0 | KG |
  | FG012 | 568.0 | KG |
  | FG013 | 892.0 | KG |
  | FG014 | 17.0 | KG |
  | ... +49 more rows | | |

  Sentry errors past 14d mentioning `3MD LOGISTICS – CAMANGYANAN - BKI`:
  - [2026-04-27T01:44:22.094000Z] Sales Dashboard: unmapped warehouse dropped
  - [2026-04-27T01:44:22.083000Z] Sales Dashboard: unmapped warehouse dropped
  - [2026-04-27T01:44:21.856000Z] Sales Dashboard: unmapped warehouse dropped
  - [2026-04-27T01:44:21.864000Z] Sales Dashboard: unmapped warehouse dropped
  - [2026-04-27T00:57:03.686000Z] Sales Dashboard: unmapped warehouse dropped

## `cluster-royal-cold-storage-taytay-rcs-bki`

Status: auto-apply eligible

**Proposed Canonical Winner:**

| Name | Company | Stock units | Non-zero SKUs | Disabled | Is group |
|---|---|---|---|---|---|
| `ROYAL COLD STORAGE - TAYTAY (RCS) - BKI` | `BEBANG KITCHEN INC.` | 1873.00 | 1 | 0 | 0 |

**Losers (to be DISABLED + stock migrated to winner):**

| Name | Company | Stock units | Non-zero SKUs | Disabled | Is group | Open MRs | Draft SEs |
|---|---|---|---|---|---|---|---|
| `ROYAL COLD STORAGE – TAYTAY (RCS) - BKI` | `BEBANG KITCHEN INC.` | 0.00 | 0 | 0 | 0 | 0 | 0 |

  Sentry errors past 14d mentioning `ROYAL COLD STORAGE – TAYTAY (RCS) - BKI`:
  - [2026-04-27T01:44:27.219000Z] Sales Dashboard: unmapped warehouse dropped
  - [2026-04-27T01:44:27.923000Z] Sales Dashboard: unmapped warehouse dropped
  - [2026-04-27T01:44:27.886000Z] Sales Dashboard: unmapped warehouse dropped
  - [2026-04-27T01:44:27.188000Z] Sales Dashboard: unmapped warehouse dropped
  - [2026-04-27T00:57:06.302000Z] Sales Dashboard: unmapped warehouse dropped

## Warehouse_name field collisions (separate detection)

These warehouses have the same `warehouse_name` field but distinct docnames.
Not necessarily duplicates — review each.

- key='all warehouses': `ALL WAREHOUSES - AFT`, `ALL WAREHOUSES - AMM`, `ALL WAREHOUSES - ARGW`, `ALL WAREHOUSES - AYEVO`, `ALL WAREHOUSES - AYSOL`, `ALL WAREHOUSES - AYVER`, `ALL WAREHOUSES - BAG`, `ALL WAREHOUSES - BDV`, `ALL WAREHOUSES - BFC`, `ALL WAREHOUSES - BFH`, `ALL WAREHOUSES - BMI2`, `ALL WAREHOUSES - CTTM`, `ALL WAREHOUSES - DVCAL`, `ALL WAREHOUSES - EGC`, `ALL WAREHOUSES - ESM`, `ALL WAREHOUSES - FMA`, `ALL WAREHOUSES - GHO`, `ALL WAREHOUSES - L77`, `ALL WAREHOUSES - LCT`, `ALL WAREHOUSES - MPD`, `ALL WAREHOUSES - NAIA`, `ALL WAREHOUSES - PTX`, `ALL WAREHOUSES - ROBDA`, `ALL WAREHOUSES - ROBGS`, `ALL WAREHOUSES - ROBGT`, `ALL WAREHOUSES - ROBIM`, `ALL WAREHOUSES - SJDM`, `ALL WAREHOUSES - SLGM`, `ALL WAREHOUSES - SMBIC`, `ALL WAREHOUSES - SMCAL`, `ALL WAREHOUSES - SMCLK`, `ALL WAREHOUSES - SMEO`, `ALL WAREHOUSES - SMGC`, `ALL WAREHOUSES - SMK`, `ALL WAREHOUSES - SMMAR`, `ALL WAREHOUSES - SMMOA`, `ALL WAREHOUSES - SMNE`, `ALL WAREHOUSES - SMPUL`, `ALL WAREHOUSES - SMSDN`, `ALL WAREHOUSES - SMSTR`, `ALL WAREHOUSES - SMTAY`, `ALL WAREHOUSES - SMTZ`, `ALL WAREHOUSES - SMV`, `ALL WAREHOUSES - TGR`, `ALL WAREHOUSES - TTA`, `ALL WAREHOUSES - UMBGC`, `ALL WAREHOUSES - UPTC`, `ALL WAREHOUSES - VGC`, `ALL WAREHOUSES - VMTAG`, `ALL WAREHOUSES - XMM`
- key='finished goods': `FINISHED GOODS - AFT`, `FINISHED GOODS - AMM`, `FINISHED GOODS - ARGW`, `FINISHED GOODS - AYEVO`, `FINISHED GOODS - AYSOL`, `FINISHED GOODS - AYVER`, `FINISHED GOODS - BAG`, `FINISHED GOODS - BDV`, `FINISHED GOODS - BFC`, `FINISHED GOODS - BFH`, `FINISHED GOODS - BMI2`, `FINISHED GOODS - CTTM`, `FINISHED GOODS - DVCAL`, `FINISHED GOODS - EGC`, `FINISHED GOODS - ESM`, `FINISHED GOODS - FMA`, `FINISHED GOODS - GHO`, `FINISHED GOODS - L77`, `FINISHED GOODS - LCT`, `FINISHED GOODS - MPD`, `FINISHED GOODS - NAIA`, `FINISHED GOODS - PTX`, `FINISHED GOODS - ROBDA`, `FINISHED GOODS - ROBGS`, `FINISHED GOODS - ROBGT`, `FINISHED GOODS - ROBIM`, `FINISHED GOODS - SJDM`, `FINISHED GOODS - SLGM`, `FINISHED GOODS - SMBIC`, `FINISHED GOODS - SMCAL`, `FINISHED GOODS - SMCLK`, `FINISHED GOODS - SMEO`, `FINISHED GOODS - SMGC`, `FINISHED GOODS - SMK`, `FINISHED GOODS - SMMAR`, `FINISHED GOODS - SMMOA`, `FINISHED GOODS - SMNE`, `FINISHED GOODS - SMPUL`, `FINISHED GOODS - SMSDN`, `FINISHED GOODS - SMSTR`, `FINISHED GOODS - SMTAY`, `FINISHED GOODS - SMTZ`, `FINISHED GOODS - SMV`, `FINISHED GOODS - TGR`, `FINISHED GOODS - TTA`, `FINISHED GOODS - UMBGC`, `FINISHED GOODS - UPTC`, `FINISHED GOODS - VGC`, `FINISHED GOODS - VMTAG`, `FINISHED GOODS - XMM`
- key='goods in transit': `GOODS IN TRANSIT - AFT`, `GOODS IN TRANSIT - AMM`, `GOODS IN TRANSIT - ARGW`, `GOODS IN TRANSIT - AYEVO`, `GOODS IN TRANSIT - AYSOL`, `GOODS IN TRANSIT - AYVER`, `GOODS IN TRANSIT - BAG`, `GOODS IN TRANSIT - BDV`, `GOODS IN TRANSIT - BFC`, `GOODS IN TRANSIT - BFH`, `GOODS IN TRANSIT - BMI2`, `GOODS IN TRANSIT - CTTM`, `GOODS IN TRANSIT - DVCAL`, `GOODS IN TRANSIT - EGC`, `GOODS IN TRANSIT - ESM`, `GOODS IN TRANSIT - FMA`, `GOODS IN TRANSIT - GHO`, `GOODS IN TRANSIT - L77`, `GOODS IN TRANSIT - LCT`, `GOODS IN TRANSIT - MPD`, `GOODS IN TRANSIT - NAIA`, `GOODS IN TRANSIT - PTX`, `GOODS IN TRANSIT - ROBDA`, `GOODS IN TRANSIT - ROBGS`, `GOODS IN TRANSIT - ROBGT`, `GOODS IN TRANSIT - ROBIM`, `GOODS IN TRANSIT - SJDM`, `GOODS IN TRANSIT - SLGM`, `GOODS IN TRANSIT - SMBIC`, `GOODS IN TRANSIT - SMCAL`, `GOODS IN TRANSIT - SMCLK`, `GOODS IN TRANSIT - SMEO`, `GOODS IN TRANSIT - SMGC`, `GOODS IN TRANSIT - SMK`, `GOODS IN TRANSIT - SMMAR`, `GOODS IN TRANSIT - SMMOA`, `GOODS IN TRANSIT - SMNE`, `GOODS IN TRANSIT - SMPUL`, `GOODS IN TRANSIT - SMSDN`, `GOODS IN TRANSIT - SMSTR`, `GOODS IN TRANSIT - SMTAY`, `GOODS IN TRANSIT - SMTZ`, `GOODS IN TRANSIT - SMV`, `GOODS IN TRANSIT - TGR`, `GOODS IN TRANSIT - TTA`, `GOODS IN TRANSIT - UMBGC`, `GOODS IN TRANSIT - UPTC`, `GOODS IN TRANSIT - VGC`, `GOODS IN TRANSIT - VMTAG`, `GOODS IN TRANSIT - XMM`
- key='megaworld paseo center': `MEGAWORLD PASEO CENTER - BEBANG PASEO INC.`, `Megaworld Paseo Center - BFC`
- key='robinsons antipolo': `ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.`, `Robinsons Antipolo - BFC`
- key='sm manila': `SM  Manila - BFC`, `SM MANILA - BEBANG ENTERPRISE INC.`
- key='sm megamall': `SM MEGAMALL - BEBANG ENTERPRISE INC.`, `SM Megamall - BFC`
- key='sm southmall': `SM SOUTHMALL - BEBANG ENTERPRISE INC.`, `SM Southmall - BFC`
- key='sta. lucia east grand mall': `STA. LUCIA EAST GRAND MALL - BEBANG SM MARIKINA INC.`, `Sta. Lucia East Grand Mall - BFC`
- key='stores': `STORES - AFT`, `STORES - AMM`, `STORES - ARGW`, `STORES - AYEVO`, `STORES - AYSOL`, `STORES - AYVER`, `STORES - BAG`, `STORES - BDV`, `STORES - BEI`, `STORES - BFC`, `STORES - BFH`, `STORES - BMI2`, `STORES - CTTM`, `STORES - DVCAL`, `STORES - EGC`, `STORES - ESM`, `STORES - FMA`, `STORES - GHO`, `STORES - L77`, `STORES - LCT`, `STORES - MPD`, `STORES - NAIA`, `STORES - PTX`, `STORES - ROBDA`, `STORES - ROBGS`, `STORES - ROBGT`, `STORES - ROBIM`, `STORES - SJDM`, `STORES - SLGM`, `STORES - SMBIC`, `STORES - SMCAL`, `STORES - SMCLK`, `STORES - SMEO`, `STORES - SMGC`, `STORES - SMK`, `STORES - SMMAR`, `STORES - SMMOA`, `STORES - SMNE`, `STORES - SMPUL`, `STORES - SMSDN`, `STORES - SMSTR`, `STORES - SMTAY`, `STORES - SMTZ`, `STORES - SMV`, `STORES - TGR`, `STORES - TTA`, `STORES - UMBGC`, `STORES - UPTC`, `STORES - VGC`, `STORES - VMTAG`, `STORES - XMM`
- key='work in progress': `WORK IN PROGRESS - AFT`, `WORK IN PROGRESS - AMM`, `WORK IN PROGRESS - ARGW`, `WORK IN PROGRESS - AYEVO`, `WORK IN PROGRESS - AYSOL`, `WORK IN PROGRESS - AYVER`, `WORK IN PROGRESS - BAG`, `WORK IN PROGRESS - BDV`, `WORK IN PROGRESS - BFC`, `WORK IN PROGRESS - BFH`, `WORK IN PROGRESS - BMI2`, `WORK IN PROGRESS - CTTM`, `WORK IN PROGRESS - DVCAL`, `WORK IN PROGRESS - EGC`, `WORK IN PROGRESS - ESM`, `WORK IN PROGRESS - FMA`, `WORK IN PROGRESS - GHO`, `WORK IN PROGRESS - L77`, `WORK IN PROGRESS - LCT`, `WORK IN PROGRESS - MPD`, `WORK IN PROGRESS - NAIA`, `WORK IN PROGRESS - PTX`, `WORK IN PROGRESS - ROBDA`, `WORK IN PROGRESS - ROBGS`, `WORK IN PROGRESS - ROBGT`, `WORK IN PROGRESS - ROBIM`, `WORK IN PROGRESS - SJDM`, `WORK IN PROGRESS - SLGM`, `WORK IN PROGRESS - SMBIC`, `WORK IN PROGRESS - SMCAL`, `WORK IN PROGRESS - SMCLK`, `WORK IN PROGRESS - SMEO`, `WORK IN PROGRESS - SMGC`, `WORK IN PROGRESS - SMK`, `WORK IN PROGRESS - SMMAR`, `WORK IN PROGRESS - SMMOA`, `WORK IN PROGRESS - SMNE`, `WORK IN PROGRESS - SMPUL`, `WORK IN PROGRESS - SMSDN`, `WORK IN PROGRESS - SMSTR`, `WORK IN PROGRESS - SMTAY`, `WORK IN PROGRESS - SMTZ`, `WORK IN PROGRESS - SMV`, `WORK IN PROGRESS - TGR`, `WORK IN PROGRESS - TTA`, `WORK IN PROGRESS - UMBGC`, `WORK IN PROGRESS - UPTC`, `WORK IN PROGRESS - VGC`, `WORK IN PROGRESS - VMTAG`, `WORK IN PROGRESS - XMM`