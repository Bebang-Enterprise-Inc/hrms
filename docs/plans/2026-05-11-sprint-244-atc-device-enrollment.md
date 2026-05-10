---
sprint_id: S244
display: Sprint 244
slug: atc-device-enrollment
plan_filename: 2026-05-11-sprint-244-atc-device-enrollment.md
branch: s244-atc-device-enrollment
repos: [hrms]
date_created: 2026-05-11
status: AGENT_BUILD_COMPLETE
plan_version: v1
canonical_scope: none
canonical_scope_rationale: |
  ADMS device config (1 new device UDP3254701583 → 3 registers) + 48 INSERT rows
  into `adms_device_cmd` queue (full C6 cluster enrollment for 8 employees on 6 devices)
  + 16 audit rows into CHANGE_LOG.csv + 7 bio_device_name UPDATE in Master CSV
  (local-only SSOT).
  No tabCompany / tabWarehouse / tabCustomer / tabSupplier UPDATE/INSERT/DELETE.
  No SI / PO / MR / SE / JE / PE / GL.
  No Frappe `tabEmployee` insert (all 8 already in Frappe).
ceo_directive_source: |
  Ron Andrew Santos chat 2026-05-11 PHT — requested ATC device UDP3254701583
  registration + 8 employee enrollments. Sam directive: "Audit the Device and
  employees in Ron message and let's add the device if not there yet, white list it
  and add the employees including in the cluster in the south."
audit_evidence: tmp/s243_atc_enrollment/  # path uses pre-rename label; file content references S244
related_plans:
  - docs/plans/2026-05-07-sprint-239-camangyanan-mingoy.md  # device-registration pattern
  - docs/plans/2026-05-08-sprint-241-new-hires-apr20-may9-import.md  # cluster cross-enrollment pattern
evidence_committed:
  - output/s244/SUMMARY.md
  - output/s244/verification/state_after.json
  - hrms/utils/device_mapping.py  # +1 entry (UDP3254701583)
  - data/_FINAL/CHANGE_LOG.csv  # +16 rows
  - docs/plans/2026-05-11-sprint-244-atc-device-enrollment.md
  - docs/plans/SPRINT_REGISTRY.md  # +S244 row, Next -> S245
evidence_local_only:
  - .claude/skills/adms-bei-erp/references/clusters.md  # C6 D6 row added
  - data/_FINAL/EMPLOYEE_MASTER.csv  # bio_device_name updated for 7 ATC hires
sprint_registry_row: |
  | `S244` | Sprint 244 | `s244-atc-device-enrollment` (hrms — ATC device UDP3254701583 added + Cluster 6 expanded to 6 devices + 8 employees full C6 enrollment) | TBD | AGENT_BUILD_COMPLETE 2026-05-11 — ATC Device Registration + 8 Employee C6 Cluster Enrollment | `docs/plans/2026-05-11-sprint-244-atc-device-enrollment.md` |
---

# Sprint 244 — Alabang Town Center Device Registration + 8 Employee C6 Cluster Enrollment

> **Source:** Ron Andrew Santos chat 2026-05-11; Sam approval same day.
> **PR-Handoff:** Agent created PR + STOPS for Sam to merge.

## Design Rationale

### Why this exists

ATC is a new BEI store joining the South Cluster (C6 — David Ramal). Device UDP3254701583 has been physically deployed but unregistered — heartbeating from IP 131.226.100.198 since at least 2026-05-08 and receiving 403 Forbidden on every request (~every 15s). This sprint registers the device across all three required surfaces and enrolls the ATC team across the full C6 cluster.

### Why full cluster cross-enrollment

Per `clusters.md` "Adding a New Employee to Their Cluster" rule — store crew enroll on ALL cluster devices (not just home). For S244 this means 8 employees × 6 C6 devices = 48 USERINFO commands. Pattern matches S241 (which enrolled new hires on full cluster).

### Pre-write audit findings

| Check | Result |
|---|---|
| `UDP3254701583` in server allowlist | ❌ NOT present (was getting 403 for days) |
| `UDP3254701583` heartbeating | ✅ Yes, from IP 131.226.100.198 (Alabang area) |
| All 8 PINs in Master CSV | ✅ All Active (7 at ATC + RAMAL roving AS at BF Homes) |
| All 8 in Frappe `tabEmployee` | ✅ All Active, no ghost rows |
| ADMS `user_registry` for 8 PINs | ✅ Zero rows (clean) |
| Real punch history (attlog_raw) | ✅ All 8 actively punching at C6/C4 devices (BONGAY last punched yesterday 23:22 at Galleria South; RAMAL roving across 9 devices in 2 months) |
| Pre-existing USERINFO at UDP3254701583 | ✅ Zero commands queued |

## What this sprint did

### W1 — Server allowlist (EC2)
Appended line 53: `53,ALABANG TOWN CENTER,alabangtowncenter,Alabang Town Center,store,ATC,EXACT_NAME,user_clarification,ZKTeco MB10-VL,UDP3254701583,Active,5/11/2026,,`
Allowlist: 52 → **53** rows.

### W2 — Local Python mapping
`hrms/utils/device_mapping.py`: added `'UDP3254701583': 'ALABANG TOWN CENTER'`. Entries: 49 → **50**.

### W3 — Cluster doc (local-only — `.claude/` gitignored)
`.claude/skills/adms-bei-erp/references/clusters.md`: added Cluster 6 D6 row for ATC. C6 expanded from 5 → 6 devices.

### W4 — ADMS USERINFO inserts (48 commands)
All 8 employees enrolled on all 6 C6 devices (cluster cross-enrollment):

| PIN | Name | Position | C6 devices enrolled |
|---|---|---|---|
| 9000490 | RAMAL, RAMIL DAVID C. | Area Supervisor (AS Trainee per Master) | 6 |
| 9001854 | BONGAY, ARVIEN M. | Store OIC | 6 |
| 9001855 | IGNACIO, JACKELYN B. | Cashier | 6 |
| 9001856 | PUJADO, EDCEL B. | Cashier | 6 |
| 9001858 | ABALLAR, JERRY F. | Store Crew | 6 |
| 9001861 | NAÑOS, MELLANE B. | Store Crew | 6 |
| 9001862 | CONCEPCION, BRIGITTE G. | Store Crew | 6 |
| 9001863 | SANTOS, CAMILLE D. | Store Crew | 6 |

Devices (C6 — South Cluster):
- UDP3251600317 (SM Bicutan)
- UDP3251600215 (BF Homes)
- CNYG242061718 (The Terminal)
- UDP3251200195 (Festival Mall)
- CNYG242061620 (SM Southmall)
- **UDP3254701583 (ATC — NEW)**

### W5 — Receiver restart
`docker restart adms_receiver_adms-api_1` to reload allowlist. ATC device immediately got 200 OK on heartbeat post-restart (was 403 before).

### W6 — Verification
- All 48 commands: tab byte count = 2 (PIN=…\tName=…\tPri=0) ✓
- UTF-8 byte verification: NAÑOS `c391` byte sequence stored correctly (initial cp1252 encoding issue caught + retried; SSM display showed `�` due to Windows console codepage, NOT data corruption)
- **ACK rate at +30s: 48/48 (100%)** — all 6 devices ACKED 8 commands each

### W7 — Master CSV bio_device_name update (local-only)
7 ATC hires had `bio_device_name=BLANK` in Master CSV. Updated to `ALABANG TOWN CENTER`. RAMAL stays as `bio_device_name=BF HOMES` (his home; ATC is cluster cross-enrollment, not home reassignment).

### W8 — CHANGE_LOG audit (16 rows)
- 1 DEVICE_REGISTER (UDP3254701583)
- 8 ENROLL (one per employee, all 6 C6 SNs in new_value)
- 7 EMPLOYEE_MASTER UPDATE (bio_device_name for 7 ATC hires)

## What this sprint did NOT do

- ❌ NO Frappe `tabEmployee` insert — all 8 employees already in Frappe with Active status
- ❌ NO Google Sheet sync (consistent with S228/S239/S241 pattern)
- ❌ NO touch on the 11 stale `adms_user_registry` test-pollution rows from S237 (deferred)
- ❌ NO Roving Employee Registry update for RAMAL — `hrms/utils/roving_employees.py` not edited; he's already roving across 9 devices in practice; formal registry update could be a separate sprint

## Sam handoff

1. Merge PR
2. Tell ATC site team: device now operational; employees should physically scan fingerprint at ATC to register
3. Tell Ron: ATC device registration complete, 8 employees enrolled across C6 cluster
4. Optional: Add RAMAL to `hrms/utils/roving_employees.py` (Area Supervisor formal registration)

## Source References

- **Audit evidence:** `tmp/s243_atc_enrollment/` (path uses pre-rename label; content references S244)
- **Pattern references:** S239 (device registration), S241 (cluster cross-enrollment)
- **Cluster rule:** `.claude/skills/adms-bei-erp/references/clusters.md` C6 South Cluster
- **Tab-byte USERINFO rule:** `.claude/skills/adms-bei-erp/SKILL.md`

## Amendment Log

| Date | Author | Section | Change |
|---|---|---|---|
| 2026-05-11 | Sam (via Claude) | INITIAL | Plan written + executed in same session per Ron's request + Sam approval. Originally branched as `s243-atc-device-enrollment` but S243 was already taken by canonical-coa-4-stores (PR #735, merged 2026-05-09) — renamed to S244 mid-execution before commit/push. tmp/ folder name still uses `s243_atc_enrollment` (pre-rename, content references S244). |
