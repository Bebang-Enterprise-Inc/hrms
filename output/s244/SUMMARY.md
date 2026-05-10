# S244 — ATC Device Registration + 8 Employee C6 Cluster Enrollment

**Status:** AGENT_BUILD_COMPLETE 2026-05-11 PHT
**Branch:** `s244-atc-device-enrollment`
**canonical_scope:** none

## Source

Ron Andrew Santos chat 2026-05-11 + Sam approval same day.

Request: Register new ATC device `UDP3254701583`, whitelist it, enroll 8 employees in South cluster.

## Done

| Phase | Action | Result |
|---|---|---|
| W1 | Server allowlist append | 52 → **53 rows** |
| W2 | `hrms/utils/device_mapping.py` add ATC entry | 49 → **50 entries** |
| W3 | `clusters.md` C6 expanded with ATC as D6 (local-only) | 5 → **6 C6 devices** |
| W4 | 48 USERINFO inserts (8 employees × 6 C6 devices) | All inserted, tab bytes verified |
| W5 | Receiver restart to reload allowlist | ATC got 200 OK on first post-restart heartbeat |
| W6 | ACK verification @ +30s | **48/48 ACKED (100%)** |
| W7 | Master CSV `bio_device_name` for 7 ATC hires | BLANK → ALABANG TOWN CENTER |
| W8 | CHANGE_LOG audit rows | +16 (1 DEVICE_REGISTER + 8 ENROLL + 7 EMPLOYEE_UPDATE) |

## 8 employees enrolled across C6

| PIN | Name | Position | Master CSV store |
|---|---|---|---|
| 9000490 | RAMAL, RAMIL DAVID C. | AS Trainee (roving) | BF HOMES (home; roving via attlog) |
| 9001854 | BONGAY, ARVIEN M. | Store OIC | ALABANG TOWN CENTER |
| 9001855 | IGNACIO, JACKELYN B. | Cashier | ALABANG TOWN CENTER |
| 9001856 | PUJADO, EDCEL B. | Cashier | ALABANG TOWN CENTER |
| 9001858 | ABALLAR, JERRY F. | Store Crew | ALABANG TOWN CENTER |
| 9001861 | NAÑOS, MELLANE B. | Store Crew | ALABANG TOWN CENTER |
| 9001862 | CONCEPCION, BRIGITTE G. | Store Crew | ALABANG TOWN CENTER |
| 9001863 | SANTOS, CAMILLE D. | Store Crew | ALABANG TOWN CENTER |

## 6 C6 South Cluster devices (post-S244)

| SN | Store |
|---|---|
| UDP3251600317 | SM Bicutan |
| UDP3251600215 | BF Homes |
| CNYG242061718 | The Terminal |
| UDP3251200195 | Festival Mall |
| CNYG242061620 | SM Southmall |
| **UDP3254701583** | **Alabang Town Center (NEW)** |

## Pre-write audit verified

- `UDP3254701583` confirmed unauthorized device, heartbeating from 131.226.100.198 since 2026-05-08 (~2700 403s over 3 days)
- All 8 PINs Active in Frappe `tabEmployee` with correct names + branches
- Zero `adms_user_registry` rows for any of the 8 PINs (no ghost interference)
- Real punch history shows all 8 actively working: BONGAY 9001854 latest punch yesterday at Galleria South; RAMAL roving across 9 devices in 2 months
- CONCEPCION 9001862 (BRIGITTE G., at ATC) verified distinct from S241's CONCEPCION 9001964 (PRECIOUS KRIZZA MAE, at BGC-BRITTANY)

## Verification snapshots

- `output/s244/verification/state_after.json`
- `tmp/s243_atc_enrollment/exec_output.txt` (W1 + W5 + W7)
- `tmp/s243_atc_enrollment/w2_retry_output.txt` (W2 W4 W6 retry with UTF-8)
- `tmp/s243_atc_enrollment/probe_audit_output.txt` (pre-write audit)

## Sam handoff

1. **Merge PR**
2. Tell ATC site team: device operational; crew should physically scan fingerprint at ATC to register biometric
3. Notify Ron: "ATC device added, 8 employees enrolled across South cluster (6 devices). 48/48 ACKED."
4. (Optional) Add RAMAL to `hrms/utils/roving_employees.py` for formal AS registration

## Naming note

Originally branched as `s243-atc-device-enrollment` but S243 was taken by canonical-coa-4-stores (PR #735, merged 2026-05-09 — local registry was stale at session start). Renamed to S244 mid-execution before commit. tmp/ directory name `s243_atc_enrollment` left as-is (file content references S244).
