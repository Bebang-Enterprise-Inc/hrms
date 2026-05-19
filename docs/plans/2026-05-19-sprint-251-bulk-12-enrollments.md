---
sprint_id: S251
display: Sprint 251
slug: bulk-12-enrollments
plan_filename: 2026-05-19-sprint-251-bulk-12-enrollments.md
branch: s251-bulk-12-enrollments
repos: [hrms]
date_created: 2026-05-19
status: AGENT_BUILD_COMPLETE
plan_version: v1
canonical_scope: none
canonical_scope_rationale: |
  65 ADMS USERINFO inserts + 12 CHANGE_LOG rows. No Master CSV mutations.
  No Frappe / Google Sheet / Company / Warehouse / Customer / Supplier touches.
ceo_directive_source: |
  Two Ron Andrew Santos chats:
    - Sat 2026-05-17 1:23 PM PHT: 2 SM Clark hires
    - Mon 2026-05-18 6:04 PM PHT: 10 hires across NAIA T3, C3 stores, SM Clark, Market Market
  Sam directive 2026-05-19: "Audit and process the below list"
audit_evidence: tmp/s251_bulk_enroll/
related_plans:
  - docs/plans/2026-05-08-sprint-241-new-hires-apr20-may9-import.md  # 6 of 12 PINs from this batch
evidence_committed:
  - output/s251/SUMMARY.md
  - data/_FINAL/CHANGE_LOG.csv
  - docs/plans/2026-05-19-sprint-251-bulk-12-enrollments.md
  - docs/plans/SPRINT_REGISTRY.md
---

# Sprint 251 — Bulk 12-Employee Multi-Cluster Enrollment

## Source

- Sat 2026-05-17 1:23 PM PHT: Ron — 2 SM Clark hires (NOCUM, PINGUL)
- Mon 2026-05-18 6:04 PM PHT: Ron — 10 hires across multiple stores
- Sam directive 2026-05-19: process

## Pre-write audit — 6 in Master CSV, 6 NOT in Master CSV

| Bio ID | Name | Master state | Store | Cluster |
|---|---|---|---|---|
| 9001908 | GALVEZ, JESIE JHON S. | ✅ S241 | MARKET MARKET | C1 |
| 9001951 | ORIBIAS, JUNELYN P. | ✅ S241 | NAIA T3 | C8 |
| 9001953 | PAGADUAN, MARY ANN M. | ✅ S241 | NAIA T3 | C8 |
| 9001970 | PINGUL, CLARENZE KAYE O. | ✅ S241 | SM CLARK | C9 |
| 9001972 | NOCUM, RUBILYN L. | ✅ S241 (Ron said "Production"; Master STORE CREW kept) | SM CLARK | C9 |
| 9001976 | CAÑADA, RENZPAULO S. | ✅ S241 | NAIA T3 | C8 |
| 9001998 | ROBLES, ROMINA GRACE | ❌ NOT in Master (Ron-assigned) | AYALA EVO | C3 |
| 9002000 | REYES, RUSSELLIER M. | ❌ NOT in Master (Ron-assigned) | AYALA VERMOSA | C3 |
| 9002001 | FLORDELIZA, NORTON B. | ❌ NOT in Master (Ron-assigned) | ROBINSONS GENTRI | C3 |
| 9002007 | SALAS, DAISY S. | ❌ NOT in Master (Ron-assigned) | SM CLARK | C9 |
| 9002009 | DE LEON, ANALYN C. | ❌ NOT in Master (Ron-assigned) | SM CLARK | C9 |
| 9002011 | CALEZA, CLERILYN B. | ❌ NOT in Master (Ron-assigned) | SM CLARK | C9 |

All 12 have **zero ADMS state** (no USERINFO, no punches, no user_registry) — clean enrollments.

## Execution

### W1 — 65 USERINFO commands

| Cluster | Hires | Devices | Commands |
|---|---|---|---|
| C9 (Navatro) — SM Clark | 5 | 6 | 30 |
| C8 (Mendoza) — NAIA T3 home cluster | 3 | 5 | 15 |
| C3 (Tiu/Garcia) — EVO/Vermosa/Gentri | 3 | 5 | 15 |
| C1 (Molina) — Market Market | 1 | 5 | 5 |
| **Total** | **12** | | **65** |

IDs 12257-12321. Tab bytes: 2 per command ✓. UTF-8 (Ñ for CAÑADA) ✓.

### W2 — ACK verification
**57/65 ACKED at +50s (88%)**. 8 PENDING on:
- **CNYG242061011 SM Grand Central**: 5 PENDING (device offline)
- **UDP3252100385 Robinsons Gentri**: 3 PENDING (device offline)

Both will auto-ACK on next heartbeat (offline-device pattern from S241/S250).

### W3 — CHANGE_LOG (+12 rows)
1 ENROLL row per employee, listing target SNs + flagging Master CSV presence.

## What this sprint did NOT do

- ❌ NO Master CSV row additions for the 6 missing PINs (9001998-9002011) — HR owns Master CSV inserts
- ❌ NO Frappe insert
- ❌ NO Google Sheet sync
- ❌ NO NOCUM designation change (kept Master's STORE CREW)

## Flagged

1. **6 new Bio IDs 9001998-9002011 outside S241 range (9001935-9001979)** — Master CSV needs HR backfill. Maybe these are in the New Hires Masterlist Google Sheet already; HR should sync down.
2. **NOCUM "Production" vs Master "STORE CREW"** — same MANGUERA-style pattern; HR should validate her actual role.
3. **S228/S241 Master-only gap continues** — 6 S241-imported PINs were never ADMS-enrolled until today's request. Dedicated backfill sprint worth considering.
4. **8 offline-device commands** (SM Grand Central + Robinsons Gentri) — will auto-ACK on heartbeat; if not within 24h, ops should physically check.

## Sam handoff

1. Merge PR
2. Reply to Ron: 12 enrolled across their target clusters (C1, C3, C8, C9). 57/65 ACKED, 8 PENDING on 2 offline devices will auto-ACK on heartbeat.
3. (Optional) Backfill Master CSV with rows for 9001998-9002011 via `/extract-data` from latest New Hires Masterlist.
