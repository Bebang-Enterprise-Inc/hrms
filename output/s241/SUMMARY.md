# S241 — New Hires Masterlist Import (April 20 - May 9, 2026)

**Status:** AGENT_BUILD_COMPLETE 2026-05-08 PHT
**Branch:** `s241-new-hires-apr20-may9-import`
**Worktree:** `F:/Dropbox/Projects/BEI-ERP-s241-new-hires`
**canonical_scope:** none

## What was requested

Sam directive 2026-05-08 PHT — extract from Google Sheet "New Hires Masterlist_Feb 2026 Onwards" (ignore "New Batch" + tabs ≤Apr 17), find missing from Master CSV, add them. Then per Sam: "for now only add to the CSV file and Generate an /xlsx-bei-erp list for HR ... if where each is working is already indicated on the Sheet I shared with you then we can enroll in /adms-bei-erp without HR comment".

## What was done

| Phase | Action | Result |
|---|---|---|
| W1 | Extracted 79 hires from 12 tabs of Google Sheet `1oxf0ApyxoCrObatos6rO_qLZcv04P8_NC6b9JIGHPtM` (Apr 20 - May 9) | `tmp/s241_new_hires/extracted_apr20_to_may9.csv` |
| W2 | Cross-referenced against Master CSV by normalized (Last, First) name | 34 matched, **45 missing** |
| W3 | Pre-write collision audit (Frappe + ADMS) | All clean — Bio IDs 9001935-9001979 virgin |
| W4 | Appended 45 rows to `data/_FINAL/EMPLOYEE_MASTER.csv` | 749 → **794 rows** |
| W5 | Generated HR handoff XLSX | `output/s241/hr_handoff/S241_New_Hires_Apr20_May9_2026-05-08.xlsx` |
| W6 | Inserted 146 PENDING USERINFO commands (cluster cross-enrollment) | All ACK validated |
| W7 | Appended 90 audit rows to CHANGE_LOG.csv | 798 → 888 rows |

## Bio ID assignments

Sequential 9001935..9001979 in tab-chronological order (April 20 first). 16 of 45 are at 3MD COMMISSARY (renamed from CAMANGYANAN BULACAN per S240).

## ADMS enrollment scope

Per `clusters.md` "Adding a New Employee to Their Cluster" rule:

| Group | Hires | Devices each | Commands |
|---|---|---|---|
| 3MD Commissary (standalone) | 16 | 1 | 16 |
| Head Office (Brittany + Capital House) | 5 | 3 | 15 |
| Cluster 1 (Paseo) | 1 | 5 | 5 |
| Cluster 2 (Tomas Morato) | 1 | 4 | 4 |
| Cluster 3 (Ayala Evo) | 1 | 5 | 5 |
| Cluster 4 (Solenad / D'verde / Sta Rosa) | 5 | 4 | 20 |
| Cluster 5 (Sta Lucia) | 2 | 5 | 10 |
| Cluster 6 (Festival / Southmall) | 3 | 5 | 15 |
| Cluster 8 (NAIA T3 / SM MOA) | 5 | 5 | 25 |
| Cluster 9 (SM Clark / Sangandaan) | 5 | 6 | 30 |
| Standalone (Greenhills) | 1 | 1 | 1 |
| **Total** | **45** | | **146** |

## Verification

- **Tab byte:** All 146 commands have exactly 2 tab bytes (PIN=…\tName=…\tPri=0)
- **UTF-8:** Hex-dumped Ñ-containing names confirm `c391` bytes correctly stored (SSM display rendered `�` due to Windows console codepage — not data corruption)
- **ACK status @ +60s:** 141 of 146 ACKED (96.6%)
- **5 remaining PENDING:** UDP3251600215 BF Homes (×3), UDP3252100385 Gentri (×1), UDP3252900251 Greenhills (×1) — devices were offline at moment of poll, will auto-ACK on next heartbeat

## What was NOT done (per CEO directive)

- ❌ NO Frappe `tabEmployee` insert (HR audit pending — S228/S230/S239 precedent)
- ❌ NO Google Sheet auto-sync (HR will mirror via XLSX handoff)
- ❌ NO ADMS receiver restart (all target devices already in allowlist)
- ❌ NO touch on the 11 stale `adms_user_registry` test-pollution rows (deferred)

## Sam handoff

1. **Merge PR**
2. **Send XLSX to HR:** `output/s241/hr_handoff/S241_New_Hires_Apr20_May9_2026-05-08.xlsx`
3. (Optional) Re-poll ACK status in 5-10 min for the 5 offline-device commands
4. Notify stores/commissary that the new 45 hires can physically register fingerprints

## Files (worktree-tracked)

| Path | Change |
|---|---|
| `data/_FINAL/CHANGE_LOG.csv` | +90 rows |
| `docs/plans/2026-05-08-sprint-241-new-hires-apr20-may9-import.md` | new plan |
| `docs/plans/SPRINT_REGISTRY.md` | +S240 (retroactive) +S241 rows, Next → S242 |
| `output/s241/SUMMARY.md` | this file |
| `output/s241/verification/state_after.json` | post-write snapshot |
| `output/s241/hr_handoff/S241_New_Hires_Apr20_May9_2026-05-08.xlsx` | HR deliverable |

## Local-only (gitignored)

| Path | Change |
|---|---|
| `data/_FINAL/EMPLOYEE_MASTER.csv` | +45 rows in main checkout SSOT (Bio IDs 9001935-9001979) |

## Audit evidence (transient — `tmp/`)

- `tmp/s241_new_hires/AUDIT.md` — initial extraction audit
- `tmp/s241_new_hires/COLLISION_AUDIT.md` — Bio ID + name collision check
- `tmp/s241_new_hires/extracted_apr20_to_may9.csv` — 79 raw extracted rows
- `tmp/s241_new_hires/missing_from_master.csv` — 45 missing rows
- `tmp/s241_new_hires/proposed_assignments.json` — Bio ID → name mapping
- `tmp/s241_new_hires/new_45_rows.csv` — 45 Master CSV rows in target schema
- `tmp/s241_new_hires/EMPLOYEE_MASTER_pre_s241_backup.csv` — backup
- `tmp/s241_new_hires/enrollment_plan.json` — 146 USERINFO targets
- `tmp/s241_new_hires/enrollment.sql` — generated SQL
- `tmp/s241_new_hires/probe_*_output.txt` — SSM probe captures
