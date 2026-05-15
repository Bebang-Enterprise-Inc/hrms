---
sprint_id: S250
display: Sprint 250
slug: smsm-sadio-orayan-enrollment
plan_filename: 2026-05-15-sprint-250-smsm-sadio-orayan-enrollment.md
branch: s250-smsm-sadio-orayan-enrollment
repos: [hrms]
date_created: 2026-05-15
status: AGENT_BUILD_COMPLETE
plan_version: v1
canonical_scope: none
canonical_scope_rationale: |
  12 ADMS USERINFO inserts (2 employees × 6 C6 devices) + 2 CHANGE_LOG rows.
  No Master CSV row changes (both Active + correct store_location since S228).
  No tabCompany/Warehouse/Customer/Supplier mutations. No SI/PO/MR/SE/JE/PE/GL.
ceo_directive_source: |
  Ron Andrew Santos chat 2026-05-15 PHT — enroll 2 SM Southmall hires.
  Sam directive same day: "Audit and enroll these two."
audit_evidence: tmp/s250_smsm_enroll/
related_plans:
  - docs/plans/2026-05-11-sprint-244-atc-device-enrollment.md  # C6 cluster expanded to 6 devices including ATC
evidence_committed:
  - output/s250/SUMMARY.md
  - data/_FINAL/CHANGE_LOG.csv  # +2 rows
  - docs/plans/2026-05-15-sprint-250-smsm-sadio-orayan-enrollment.md
  - docs/plans/SPRINT_REGISTRY.md  # +S250 row, Next -> S251
sprint_registry_row: |
  | `S250` | Sprint 250 | `s250-smsm-sadio-orayan-enrollment` (hrms — 12 USERINFO inserts on C6 cluster for 2 SM Southmall hires + 2 CHANGE_LOG rows) | TBD | AGENT_BUILD_COMPLETE 2026-05-15 — SM Southmall 2-employee C6 Cluster Enrollment | `docs/plans/2026-05-15-sprint-250-smsm-sadio-orayan-enrollment.md` |
---

# Sprint 250 — SM Southmall 2-Employee C6 Cluster Enrollment

> **Source:** Ron Andrew Santos chat 2026-05-15 + Sam approval same day.

## Pre-write audit

| Bio ID | Master CSV | Ron's request | ADMS state | Action |
|---|---|---|---|---|
| **9001920 ORAYAN, MITCHEL G.** | CASHIER @ SM SOUTHMALL, Active | CASHIER @ SM SOUTHMALL | Zero USERINFO, zero punches anywhere (S228 Master-only gap — same as JIMENEZ S249) | Full C6 enrollment |
| **9001929 SADIO, KIANA JANE J.** | STORE CREW @ SM SOUTHMALL, Active | "Production" @ SM SOUTHMALL ⚠️ | Same as above | Full C6 enrollment; Master designation STORE CREW kept (Ron's "Production" likely same mistake as MANGUERA earlier — flag in PR) |

Both NOT in Frappe `tabEmployee` (S228 CEO-directed Master-only pattern).
SM Southmall device CNYG242061620 healthy (heartbeating from 131.226.101.229).

## Execution

### W1 — 12 USERINFO inserts (2 employees × 6 C6 devices)

Cluster 6 South: UDP3251600317 (Bicutan), UDP3251600215 (BF Homes), CNYG242061718 (Terminal), UDP3251200195 (Festival), CNYG242061620 (Southmall — home), UDP3254701583 (ATC).

- IDs 12245-12256 (12 contiguous)
- Tab byte validation: 2 per command_text ✓
- **ACK rate at +35s: 10/12 (83%)**
- 2 PENDING at UDP3251600215 (BF Homes) — same offline-device pattern from S241; will auto-ACK on next heartbeat

### W2 — CHANGE_LOG (2 rows)

1 ENROLL row per employee summarizing the 6 target SNs.

## What this sprint did NOT do

- ❌ NO Master CSV updates (both rows already correct: store_location=SM SOUTHMALL, status=Active, bio_device_name=SM SOUTHMALL)
- ❌ NO Frappe insert (both Master-only per S228 directive)
- ❌ NO Google Sheet sync
- ❌ NO SADIO designation change (Ron's "Production" likely Ron-mistake same as MANGUERA correction; kept Master's STORE CREW — flagged in PR for HR validation)

## Flagged for HR

- SADIO 9001929 designation: Ron says "Production", Master says STORE CREW. Same pattern as MANGUERA S252 where Ron self-corrected to STORE CREW. HR should confirm SADIO's actual role.
- S228 workflow gap continues: BIO IDs 9001920, 9001929 (and likely many others in the 9001882-9001932 range) imported to Master CSV 2026-04-28 but never enrolled in ADMS — only triggered when Ron individually requests. A "S228 backfill" sprint to enroll all S228 imports onto home clusters would close this gap.

## Sam handoff

1. Merge PR
2. Reply to Ron: Both enrolled at SM Southmall + full C6 cluster (ATC, Bicutan, BF Homes, Festival, Terminal, Southmall). 10 of 12 ACKED at +35s, 2 PENDING on BF Homes device will auto-ACK on next heartbeat.
