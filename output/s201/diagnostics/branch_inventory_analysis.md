# S201 Phase 0 — Branch Inventory (from EMPLOYEE_MASTER.csv 2026-02 snapshot)

**Source:** `data/_FINAL/EMPLOYEE_MASTER.csv` (696 rows, Feb snapshot — live Frappe has 541 active)
**Purpose:** Drive `branch_company_map.csv` and `branch_rename_map.csv`
**Note:** Live Frappe Company names post-S196 are ALL CAPS store-first `<STORE> - <CORP>`. Resolver at runtime queries Frappe Company table, not this snapshot.

## 60 distinct branch values

### A. Head Office / non-store (route → `BEBANG ENTERPRISE INC.`)
Per Sam 2026-04-17: **3 HOs in BGC** (confirmed below):
| Branch | Count | Notes |
|---|---|---|
| `BRITTANY OFFICE` | 70 | = **Brittany Hotel - BGC** (HO) |
| `CAPITAL HOUSE` | 12 | = **Capital House - BGC** (HO) |
| `MYTOWN` | 3 | = **My Town - BGC** (HO) |

### B. Commissary (route → `BEBANG KITCHEN INC.` except SCM which stays on BEI)
Per Sam 2026-04-17: **SCM team at commissary = BEI parent**, NOT BKI.
Branch suffix drives routing:
| Branch | Count | Routes to | Reason |
|---|---|---|---|
| `SHAW COMMISSARY - Production` | 23 | **BKI** | Actual kitchen/production crew |
| `COMMISSARY SHAW` | 10 | **BKI** (if dept=Commissary) / BEI otherwise | Needs dept check — rename to canonical |
| `SHAW COMMISSARY - Logistics` | 9 | **BEI parent** | SCM team — per Sam |
| `SHAW COMMISSARY` | 6 | **BKI** (if dept=Commissary) / BEI otherwise | Needs dept check |
| `SHAW COMMISSARY - RD QC` | 1 | **BEI parent** | R&D dept → BEI via dept rule |

Canonical post-rename suffixes:
- `SHAW COMMISSARY` (bare) → dept-driven
- `SHAW COMMISSARY - PRODUCTION` → BKI
- `SHAW COMMISSARY - LOGISTICS` → BEI (SCM)
- `SHAW COMMISSARY - RD QC` → BEI (R&D)

### C. Stores that match S037 store_name directly [19 branches]
| Branch | S037 store_name |
|---|---|
| `SM NORTH EDSA` | SM North EDSA |
| `ROBINSONS GALLERIA SOUTH` | Robinsons Galleria South |
| `SM MARILAO` | SM Marilao |
| `AYALA VERMOSA` | Ayala Vermosa |
| `SM TAYTAY` | SM Taytay |
| `SM CLARK` | SM Clark |
| `AYALA FAIRVIEW TERRACES` | Ayala Fairview Terraces |
| `SM SOUTHMALL` | SM Southmall |
| `SM SANGANDAAN` | SM Sangandaan |
| `VENICE GRAND CANAL` | Venice Grand Canal |
| `SM BICUTAN` | SM Bicutan |
| `SM MARIKINA` | SM Marikina |
| `SM EAST ORTIGAS` | SM East Ortigas |
| `SM VALENZUELA` | SM Valenzuela |
| `SM TANZA` | SM Tanza |
| `SM MANILA` | SM Manila |
| `SM CALOOCAN` | SM Caloocan |
| `SM MEGAMALL` | SM Megamall |
| `AYALA UP TOWN CENTER` | Ayala UP Town Center |

### D. Stores that need rename mapping [32 branches]

| Current Branch | S037 Canonical | New Branch Value | Confidence |
|---|---|---|---|
| `ARANETA GATEWAY` | Food Express (Gateway Mall) | `ARANETA GATEWAY` (keep) | HIGH (known alias) |
| `ROBINSONS GENERAL TRIAS` | Robinsons Place Gen. Trias | `ROBINSONS GENERAL TRIAS` (keep) | HIGH |
| `AYALA EVO` | Ayala Evo City | `AYALA EVO CITY` | HIGH |
| `SM MOA` | SM Mall of Asia (not in S037?) | `SM MOA` (verify) | MED |
| `STA LUCIA EAST GRAND MALL` | Sta. Lucia East Grand Mall | `STA. LUCIA EAST GRAND MALL` | HIGH |
| `AYALA MARKET MARKET` | Ayala Market! Market! | `AYALA MARKET MARKET` (keep) | HIGH |
| `FESTIVAL MALL` | Festival Mall Alabang | `FESTIVAL MALL ALABANG` | HIGH |
| `ROBINSONS IMUS` | Robinsons Place Imus | `ROBINSONS IMUS` (keep) | HIGH |
| `SM SJDM` | SM San Jose Del Monte (not in S037?) | `SM SJDM` (verify) | MED |
| `UPTOWN BGC` | Uptown BGC (BGC store 1 of 3 per Sam) | `UPTOWN BGC` (keep) | HIGH |
| `AYALA SOLENAD` | Ayala Solenad 2 | `AYALA SOLENAD` (keep — drop "2") | HIGH |
| `AYALA UPTC` | Ayala UP Town Center | `AYALA UP TOWN CENTER` | HIGH |
| `ROBINSONS ANTIPOLO` | Robinsons Place Antipolo | `ROBINSONS ANTIPOLO` (keep) | HIGH |
| `SM PULILAN` | SM Pulilan (not in S037?) | `SM PULILAN` (verify) | MED |
| `XENTRO MONTALBAN` | Xentromall Montalban | `XENTROMALL MONTALBAN` | HIGH (per S196) |
| `SM SAN PABLO` | SM San Pablo (deferred per S196 P6-T6 / SHFC) | `SM SAN PABLO` (keep) | HIGH |
| `CTTM TOMAS MORATO` | CTTM Tomas Morato (not in S037?) | `CTTM TOMAS MORATO` (verify) | MED |
| `D VERDE CALAMBA` | D'Verde Calamba | `D'VERDE CALAMBA` | HIGH |
| `LUCKY CHINATOWN` | Lucky China Town | `LUCKY CHINATOWN` (keep — preferred spelling) | HIGH |
| `PITX` | Parañaque Integrated Terminal Exchange (not in S037?) | `PITX` (verify) | MED |
| `ALABANG TOWN CENTER` | Alabang Town Center (not in S037?) | `ALABANG TOWN CENTER` (verify) | MED |
| `GRAND CENTRAL` | Grand Central Ayala (not in S037?) | `GRAND CENTRAL` (verify) | MED |
| `MEGAWORLD PASEO CENTER` | Megaworld Paseo Center (not in S037?) | `MEGAWORLD PASEO CENTER` (verify) | MED |
| `SM STA ROSA` | SM Sta. Rosa (deferred per SHFC) | `SM STA. ROSA` | HIGH |
| `THE TERMINAL` | NAIA T3 (Departure)? | `NAIA T3` | MED |
| `GREENHILLS` | Ortigas Greenhills | `ORTIGAS GREENHILLS` | HIGH |
| `NAIA TERMINAL 3` | NAIA T3 (Departure) | `NAIA T3` | HIGH |
| `ESTANCIA` | Ortigas Estancia | `ORTIGAS ESTANCIA` | HIGH |
| `BF HOMES` | BF Homes Paranaque (Aguirre Ave.) | `BF HOMES PARANAQUE` | HIGH |
| `STA LUCIA GRAND MALL` | Sta. Lucia East Grand Mall | `STA. LUCIA EAST GRAND MALL` (merge) | HIGH |
| `MARKET MARKET` | Ayala Market! Market! | `AYALA MARKET MARKET` (merge) | HIGH |
| `ROBINSON GENTRI` | Robinsons Place Gen. Trias | `ROBINSONS GENERAL TRIAS` (merge) | HIGH |
| `BGC` | Uptown BGC | `UPTOWN BGC` (merge) | HIGH |

## Summary

| Category | Branches | Employees |
|---|---|---|
| HO → BEI parent | 3 | 85 |
| BKI commissary | 5 | 49 |
| Store (S037 matched) | 19 | ~260 |
| Store (need rename) | 32 | ~290 |
| Blank | 1 | ~10 |

**Per sprint plan:** `branch_rename_map.csv` handles the rename migration; `branch_company_map.csv` is the post-rename canonical store list.

## Sam clarifications 2026-04-17 (locked)
- **BGC = 3 HOs + 3 stores**: Brittany Hotel/Capital House/MyTown are HOs. Stores are UPTOWN BGC + VENICE GRAND CANAL + AYALA MARKET MARKET (best inference — confirm).
- **SCM team at commissary → BEI parent** (not BKI). Branch `SHAW COMMISSARY - Logistics` routes to BEI.
- **`BGC` (1 employee)** → flag for manual review. Too ambiguous without the employee's name/dept/designation.

## Still pending for Phase 0 live diagnostic
1. `SM MOA`, `SM SJDM`, `SM PULILAN`, `CTTM TOMAS MORATO`, `PITX`, `ALABANG TOWN CENTER`, `GRAND CENTRAL`, `MEGAWORLD PASEO CENTER` — confirm each has a Frappe Company (`entity_category='Store'`).
2. Bare `SHAW COMMISSARY` + `COMMISSARY SHAW` — require per-employee department check (Commissary → BKI, else BEI).
3. ~10 employees with blank branch — re-fetch from live Frappe and reclassify.
