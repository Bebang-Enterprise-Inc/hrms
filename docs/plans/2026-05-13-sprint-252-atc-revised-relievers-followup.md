---
sprint_id: S252
display: Sprint 249
slug: atc-revised-relievers-followup
plan_filename: 2026-05-13-sprint-252-atc-revised-relievers-followup.md
branch: s252-atc-revised-relievers-followup
repos: [hrms]
date_created: 2026-05-13
status: AGENT_BUILD_COMPLETE
plan_version: v1
canonical_scope: none
canonical_scope_rationale: |
  ADMS enrollment + Master CSV updates + audit log. No tabCompany/Warehouse/Customer/Supplier mutations. No SI/PO/MR/SE/JE/PE/GL.
ceo_directive_source: |
  Ron Andrew Santos chat 2026-05-13 (revised S245 list + 2 reliever follow-ups). Sam approval same day.
audit_evidence: tmp/s245_atc_additional/
related_plans:
  - docs/plans/2026-05-11-sprint-244-atc-device-enrollment.md  # ATC device + 8 employees
  - docs/plans/2026-05-07-sprint-239-camangyanan-mingoy.md  # reliever-rule reference
evidence_committed:
  - output/s249/SUMMARY.md
  - output/s249/verification/state_after.json
  - data/_FINAL/CHANGE_LOG.csv  # +9 rows
  - docs/plans/2026-05-13-sprint-252-atc-revised-relievers-followup.md
  - docs/plans/SPRINT_REGISTRY.md  # +S252 row, Next -> S250
evidence_local_only:
  - data/_FINAL/EMPLOYEE_MASTER.csv  # 3 rows updated in Sam's main checkout
sprint_registry_row: |
  | `S252` | Sprint 249 | `s252-atc-revised-relievers-followup` (hrms — ATC 3 employees full C6 + JIMENEZ C9 home + D'verde reliever + Master CSV updates for CLOSA + MANGUERA + BALADJAY) | TBD | AGENT_BUILD_COMPLETE 2026-05-13 — ATC Revised List + 2 Reliever Follow-ups | `docs/plans/2026-05-13-sprint-252-atc-revised-relievers-followup.md` |
---

# Sprint 249 — ATC Revised List + 2 Reliever Follow-ups

> **Source:** Ron Andrew Santos chat 2026-05-13 PHT — revised yesterday's S245 ATC list (resolved Master CSV discrepancies for CLOSA + MANGUERA) + 2 reliever requests.
> **PR-Handoff:** Agent created PR + STOPS for Sam to merge.

## Context (continues S244 + yesterday's S245 audit)

Yesterday (2026-05-12) I audited 3 ATC employees (CLOSA, BALADJAY, MANGUERA) and found Master CSV ↔ Ron mismatches for 2 of them. Sam asked Ron to clarify. Today Ron responded:

1. **CLOSA 9000273** — confirmed: moved to **Opening Team**, promoted to **STORE OIC at ATC effective 2026-05-16**. Master CSV "Area Supervisor at BF HOMES" needs override.
2. **MANGUERA 9000280** — Ron self-corrected: previous "Production" entry was wrong; actual role is **STORE CREW**. Transferred from ROBINSONS GALLERIA SOUTH to ATC.
3. **BALADJAY 9001860** — already at ATC (clean from yesterday's audit).

Plus 2 reliever requests bundled in same message:
4. **9001912 JIMENEZ, CRISMEL F.** — SM Sangandaan → D'verde Calamba reliever (Ron's previous request that was never executed — Master-only since S228 import, never enrolled in ADMS, zero punches anywhere)
5. **9001861 NAÑOS, MELLANE B.** — ATC → BF Homes reliever (already enrolled at BF Homes via S244 C6 cluster on 2026-05-10; no new USERINFO needed)

## What this sprint did

### W1 — Master CSV updates (gitignored, local SSOT)

| Bio ID | Field | Before | After |
|---|---|---|---|
| 9000273 CLOSA | store_location | BF HOMES | **ALABANG TOWN CENTER** |
| 9000273 CLOSA | designation | AREA SUPERVISOR | **STORE OIC** |
| 9000273 CLOSA | bio_device_name | BF HOMES | **ALABANG TOWN CENTER** |
| 9000273 CLOSA | notes | (existing) | + S252 Opening Team note |
| 9000280 MANGUERA | store_location | ROBINSONS GALLERIA SOUTH | **ALABANG TOWN CENTER** |
| 9000280 MANGUERA | bio_device_name | ROBINSON GALLERIA S | **ALABANG TOWN CENTER** |
| 9001860 BALADJAY | bio_device_name | (blank) | **ALABANG TOWN CENTER** |

Backup: `tmp/s245_atc_additional/EMPLOYEE_MASTER_pre_s249_backup.csv`

### W2 — ADMS USERINFO inserts (25 commands)

| Group | Employees | Devices | Commands |
|---|---|---|---|
| ATC C6 cluster | CLOSA, MANGUERA, BALADJAY | 6 (Bicutan, BF Homes, Terminal, Festival, Southmall, ATC) | 18 |
| JIMENEZ C9 home cluster | JIMENEZ | 6 (Grand Central, Valenzuela, Sangandaan, Marilao, Pulilan, Clark) | 6 |
| JIMENEZ D'verde reliever | JIMENEZ | 1 (UDP3252900188) | 1 |
| NAÑOS reliever (already enrolled S244) | — | 0 | 0 (audit-log only) |
| **Total** | | | **25** |

### W3 — Verification

- **Tab byte:** all 25 commands have exactly 2 tab bytes (PIN=…\tName=…\tPri=0)
- **UTF-8:** SQL written with explicit UTF-8 encoding (Ñ in NAÑOS-style strings tested in S244 cycle)
- **ACK rate at +45s: 25/25 (100%)** across 13 unique devices

### W4 — CHANGE_LOG (9 rows)

- 3 EMPLOYEE_MASTER UPDATE rows (CLOSA, MANGUERA, BALADJAY)
- 4 ADMS ENROLL rows (3 ATC team + 1 JIMENEZ home cluster)
- 1 ADMS RELIEVER_ENROLL row (JIMENEZ to D'verde — single-device cross-cluster)
- 1 ADMS RELIEVER_ASSIGN row (NAÑOS to BF Homes — NO_OP, already enrolled S244)

## Pre-write audit findings

| Check | Result |
|---|---|
| 3 ATC PINs in Master CSV | ✅ All Active (CLOSA needed update, MANGUERA needed update, BALADJAY clean) |
| JIMENEZ in Master CSV | ✅ Active, SM Sangandaan |
| NAÑOS S244 enrollment at BF Homes | ✅ ID 12184 ACKED 2026-05-10 23:17 |
| Frappe `tabEmployee` for 5 PINs | ✅ All Active, no ghost rows |
| ADMS `user_registry` collisions | ✅ Zero rows for any of the 5 PINs |
| JIMENEZ pre-existing USERINFO | ✅ **ZERO** — confirms Ron's follow-up was never done |
| NAÑOS S244 USERINFO at BF Homes | ✅ Verified ACKED (broad-scope re-probe) |
| ATC device UDP3254701583 health | ✅ Heartbeating from 131.226.100.133, S244 commands all ACKED |

## What this sprint did NOT do

- ❌ NO Frappe `tabEmployee` insert/update (all 5 already present + Active; HR audit lifecycle owns Frappe sync)
- ❌ NO Google Sheet sync (consistent with S228/S239/S241/S244 pattern)
- ❌ NO Opening Team full-49-device roving enrollment (separate sprint if formal registration desired — for now C6 cluster covers CLOSA's ATC assignment)
- ❌ NO update to `hrms/utils/roving_employees.py` (CLOSA + RAMAL formal AS/Opening-Team registration is separate sprint)

## Notes for HR (flagged in PR)

- **CLOSA 9000273** promotion + transfer + Opening Team status (effective 2026-05-16) — please update HR systems
- **MANGUERA 9000280** transfer from Galleria South to ATC — please update HR systems
- **JIMENEZ 9001912** was a Master-only Apr-28 (S228) import who was never enrolled in ADMS — flag the workflow gap where Master imports don't trigger ADMS enrollment. (S228 was CEO-directed to skip ADMS pending HR audit; gap surfaced today.)

## Sam handoff

1. Merge PR
2. Tell Ron: All 5 requests done — CLOSA + MANGUERA + BALADJAY enrolled on full C6 cluster (Master CSV updated for CLOSA + MANGUERA), JIMENEZ enrolled on C9 home cluster + D'verde reliever (her first ADMS enrollment ever), NAÑOS reliever to BF Homes already covered from S244
3. (Optional) Open follow-up sprint for formal Opening Team registration (CLOSA + future opening-team additions on all 49 devices)

## Sprint ID note

Used **S252** instead of S248 because S248 is reserved for the "reconciliation-cron-for-half-paired-SIs follow-up per S246 Decision 3 atomicity strategy" per registry note.
