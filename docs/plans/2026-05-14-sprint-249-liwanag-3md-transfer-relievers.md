---
sprint_id: S249
display: Sprint 249
slug: liwanag-3md-transfer-relievers
plan_filename: 2026-05-14-sprint-249-liwanag-3md-transfer-relievers.md
branch: s249-liwanag-3md-transfer-relievers
repos: [hrms]
date_created: 2026-05-14
status: AGENT_BUILD_COMPLETE
plan_version: v1
canonical_scope: none
canonical_scope_rationale: |
  1 ADMS USERINFO insert + 1 Master CSV row update + 4 CHANGE_LOG rows.
  No tabCompany/Warehouse/Customer/Supplier mutations. No SI/PO/MR/SE/JE/PE/GL.
ceo_directive_source: |
  Ron Andrew Santos chat 2026-05-14 + Sam approval same day. 3 requests bundled:
  (1) MATA 9001969 @ Capital House enrollment — already done via S241
  (2) LIWANAG 9000407 transfer Brittany Office -> 3MD COMMISSARY enrollment
  (3) NAÑOS 9001861 reliever ATC -> Festival Mall — already enrolled via S244
audit_evidence: tmp/s249_atc_capitalhouse/
related_plans:
  - docs/plans/2026-05-08-sprint-241-new-hires-apr20-may9-import.md  # MATA was here
  - docs/plans/2026-05-11-sprint-244-atc-device-enrollment.md         # NAÑOS Festival Mall enrolled here
  - docs/plans/2026-05-07-sprint-239-camangyanan-mingoy.md            # 3MD device added here
  - docs/plans/2026-05-13-sprint-252-atc-revised-relievers-followup.md  # yesterday's revised list
evidence_committed:
  - output/s249/SUMMARY.md
  - output/s249/verification/state_after.json
  - data/_FINAL/CHANGE_LOG.csv  # +4 rows
  - docs/plans/2026-05-14-sprint-249-liwanag-3md-transfer-relievers.md
  - docs/plans/SPRINT_REGISTRY.md  # +S249 row, Next -> S250
evidence_local_only:
  - data/_FINAL/EMPLOYEE_MASTER.csv  # 1 row update (LIWANAG)
sprint_registry_row: |
  | `S249` | Sprint 249 | `s249-liwanag-3md-transfer-relievers` (hrms — single LIWANAG enrollment at UDP3254800655 + Master CSV transfer + 2 NO_OP audit-logs) | TBD | AGENT_BUILD_COMPLETE 2026-05-14 — LIWANAG QA Brittany→3MD Transfer + MATA + NAÑOS Verification Logs | `docs/plans/2026-05-14-sprint-249-liwanag-3md-transfer-relievers.md` |
---

# Sprint 249 — LIWANAG 3MD Transfer + MATA/NAÑOS Verification

> **Source:** Ron Andrew Santos chat 2026-05-14 PHT + Sam approval same day.
> **PR-Handoff:** Agent created PR + STOPS for Sam to merge.

## Pre-write audit found 2 of 3 requests already satisfied

| Bio ID | Ron's request | Live ADMS state | Action |
|---|---|---|---|
| **9001969 MATA** | Enroll at Capital House | ✅ Already enrolled at all 3 head office devices via S241 (IDs 12120-12122 ACKED 2026-05-08) | NO_OP audit log |
| **9000407 LIWANAG** | Brittany Office → 3MD Commissary | ✅ Roving QA — enrolled on 47 devices via 2026-03-04 mass enrollment, but **MISSING UDP3254800655** (3MD Commissary device was created later in S239 2026-05-07) | 1 USERINFO + Master CSV update |
| **9001861 NAÑOS** | ATC → Festival Mall reliever | ✅ Already enrolled at Festival Mall (UDP3251200195) via S244 ID 12200 ACKED 2026-05-10 | NO_OP audit log |

## What this sprint did

### W1 — Master CSV update (gitignored, local SSOT)

| Bio ID | Field | Before | After |
|---|---|---|---|
| 9000407 LIWANAG | store_location | SHAW COMMISSARY (latent drift) | **3MD COMMISSARY** |
| 9000407 LIWANAG | bio_device_name | BRITANY OFFICE (typo + latent) | **3MD COMMISSARY** |

Backup: `tmp/s249_atc_capitalhouse/EMPLOYEE_MASTER_pre_s249_backup.csv`

Notes appended documenting transfer source + date + Ron's request reference.

### W2 — ADMS USERINFO (1 command)

Single INSERT into `adms_device_cmd`:
- SN: UDP3254800655 (3MD Commissary)
- PIN: 9000407
- Name: LIWANAG, JENNALYN .
- ID assigned: 12244
- **ACKED in 391ms** (sent 2026-05-14 07:05:12.196 UTC, ack 07:05:12.587)
- Tab byte validation: exactly 2 (PIN=…\tName=…\tPri=0)

### W3 — CHANGE_LOG (4 audit rows)

- 1 EMPLOYEE_MASTER UPDATE (LIWANAG transfer)
- 1 ADMS ENROLL (LIWANAG @ UDP3254800655 ACKED)
- 1 ADMS ENROLL_VERIFY NO_OP (MATA already at HO via S241)
- 1 ADMS RELIEVER_ASSIGN NO_OP (NAÑOS already at Festival Mall via S244)

## What this sprint did NOT do

- ❌ NO Frappe `tabEmployee` insert/update for MATA (S241 pattern: no Frappe; HR audit pending). Also noted LIWANAG is not in Frappe by attendance_device_id query — separate HR concern.
- ❌ NO Google Sheet sync
- ❌ NO additional enrollment for LIWANAG on UDP3254701583 (ATC, also missing) — out of Ron's scope today
- ❌ NO touch on the 11 stale `adms_user_registry` test-pollution rows from S237

## Notes for HR (flagged in PR)

- **LIWANAG 9000407** transfer from Brittany Office to 3MD Commissary — please update HR systems
- **Workflow gap**: LIWANAG missing from S239's new UDP3254800655 + S244's new UDP3254701583 — when a new device is added, there's no mechanism to auto-enroll roving employees. Worth a separate sprint to extend roving employees on every new device.

## Sam handoff

1. Merge PR
2. Reply to Ron: All 3 done
   - MATA already enrolled at Capital House (via S241)
   - LIWANAG enrolled at 3MD + Master CSV updated
   - NAÑOS reliever to Festival Mall already covered via S244 (same C6 cluster as yesterday's BF Homes reliever)

## Sprint ID note

Used **S249** per registry's "Next: S249". Following S246/S247 follow-up reservations table (S248 consumed yesterday by `s248-denise-sheet-sync`). My yesterday's S252 (`s252-atc-revised-relievers-followup` PR #750 merged 2026-05-13) row was silently dropped from registry during the S248 merge (plan file + CHANGE_LOG + output/s252/ all still in production tree — only the registry row was lost). Not restoring here to keep scope clean.
