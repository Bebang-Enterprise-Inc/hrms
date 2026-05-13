# S252 — ATC Revised List + 2 Reliever Follow-ups

**Status:** AGENT_BUILD_COMPLETE 2026-05-13 PHT
**Branch:** `s252-atc-revised-relievers-followup`
**canonical_scope:** none

## Source

Ron Andrew Santos chat 2026-05-13 PHT — revised yesterday's S245 ATC list (resolves Master CSV discrepancies) + 2 reliever follow-ups.

## Done

| Phase | Action | Result |
|---|---|---|
| W1 | Master CSV updates (3 employees, gitignored SSOT) | CLOSA: AS BF HOMES → STORE OIC ATC (Opening Team); MANGUERA: Galleria South → ATC (kept STORE CREW); BALADJAY: bio_device_name set to ATC |
| W2 | 25 USERINFO inserts | 18 ATC C6 cluster (3 employees) + 6 JIMENEZ C9 home + 1 D'verde reliever |
| W3 | ACK verification | **25/25 ACKED (100%)** at +45s |
| W4 | CHANGE_LOG audit | +9 rows |
| W5 | NAÑOS reliever audit | NO_OP (already enrolled at BF Homes via S244), audit-logged |

## 5 employee operations

| Bio ID | Name | Action | Devices |
|---|---|---|---|
| 9000273 | CLOSA, PAULA ROMAINE G. | Opening Team / Store OIC promo + transfer + C6 enrollment | 6 C6 devices |
| 9000280 | MANGUERA, DEVON R. | Store-only transfer Galleria South → ATC + C6 enrollment | 6 C6 devices |
| 9001860 | BALADJAY, MARY JOYCE S. | C6 enrollment (catch-up from S244 omission) | 6 C6 devices |
| 9001912 | JIMENEZ, CRISMEL F. | First-ever ADMS enrollment (S228 Master-only catch-up) + D'verde reliever | 6 C9 home + 1 D'verde |
| 9001861 | NAÑOS, MELLANE B. | Reliever ATC → BF Homes | 0 (already enrolled S244) |

## Pre-write audit verified

| Check | Result |
|---|---|
| 3 ATC PINs in Master CSV | ✅ Active (CLOSA + MANGUERA had Master/Ron mismatches now resolved per Ron's revised list) |
| JIMENEZ in Master CSV | ✅ Active, S228 import, never enrolled in ADMS |
| NAÑOS S244 BF Homes enrollment | ✅ ID 12184 ACKED 2026-05-10 23:17 |
| Frappe `tabEmployee` for 5 PINs | ✅ All Active, no ghost rows |
| ADMS `user_registry` collisions | ✅ 0 rows for any of the 5 PINs |
| Pre-existing USERINFO at target devices | ✅ Clean except S244 for NAÑOS (expected) |
| ATC device UDP3254701583 | ✅ Heartbeating cleanly from 131.226.100.133 |

## What this sprint did NOT do

- ❌ NO Frappe `tabEmployee` insert/update (all 5 Active; HR audit lifecycle owns Frappe sync)
- ❌ NO Google Sheet sync
- ❌ NO Opening Team full-49-device roving enrollment (separate sprint if formal registration desired)
- ❌ NO `hrms/utils/roving_employees.py` update for CLOSA

## Sprint ID note

Skipped S248-S251 because those are reserved for S247 follow-ups (reconciliation cron, G-046 dashboard, CC tree harmonization, legacy SE harmonization). Used **S252**.

## Sam handoff

1. Merge PR
2. Tell Ron: All 5 done — CLOSA promoted + transferred + enrolled at full C6, MANGUERA transferred + enrolled at full C6, BALADJAY enrolled (S244 omission caught), JIMENEZ first-ever enrollment + D'verde reliever (her S228 gap closed), NAÑOS reliever already covered from S244
3. (Optional follow-up sprint) Formal Opening Team registration for CLOSA — enroll on all 49 devices + add to `roving_employees.py`
