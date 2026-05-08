---
sprint_id: S241
display: Sprint 241
slug: new-hires-apr20-may9-import
plan_filename: 2026-05-08-sprint-241-new-hires-apr20-may9-import.md
branch: s241-new-hires-apr20-may9-import
repos: [hrms]
date_created: 2026-05-08
status: AGENT_BUILD_COMPLETE
plan_version: v1
canonical_scope: none
canonical_scope_rationale: |
  HR data import + ADMS enrollment only.
  - 45 row append to `data/_FINAL/EMPLOYEE_MASTER.csv` (gitignored, local SSOT).
  - 146 INSERT rows into `adms_device_cmd` queue (cluster cross-enrollment).
  - 90 audit rows into `data/_FINAL/CHANGE_LOG.csv`.
  - 1 XLSX deliverable for HR handoff.
  No tabCompany / tabWarehouse / tabCustomer / tabSupplier UPDATE/INSERT/DELETE.
  No SI / PO / MR / SE / JE / PE / GL creation.
  No Frappe `tabEmployee` insert (HR audit pending — same CEO directive as S228/S230/S239).
  No Google Sheet sync (HR audit pending — XLSX handed off for HR mirror instead).
ceo_directive_source: |
  Sam approval 2026-05-08 PHT after audit:
    - Extracted 79 hires from 12 tabs (Apr 20 - May 9) in Google Sheet
      "New Hires Masterlist_Feb 2026 Onwards" (1oxf0ApyxoCrObatos6rO_qLZcv04P8_NC6b9JIGHPtM)
    - 34 already in Master, 45 missing
    - Verified 0 collisions in Frappe / ADMS for Bio ID range 9001935-9001979
    - Sam: "for now only add to the CSV file and Generate an /xlsx-bei-erp list for HR
      ... if where each is working is already indicated on the Sheet I shared with you
      then we can enroll in /adms-bei-erp without HR comment"
audit_evidence: tmp/s241_new_hires/
related_plans:
  - docs/plans/2026-04-28-sprint-228-new-hires-import-anomaly-fix.md
  - docs/plans/2026-04-29-sprint-230-xentro-estancia-device-enrollment.md
  - docs/plans/2026-05-07-sprint-239-camangyanan-mingoy.md
evidence_committed:
  - output/s241/SUMMARY.md
  - output/s241/verification/state_after.json
  - output/s241/hr_handoff/S241_New_Hires_Apr20_May9_2026-05-08.xlsx
  - data/_FINAL/CHANGE_LOG.csv  # +90 rows
  - docs/plans/2026-05-08-sprint-241-new-hires-apr20-may9-import.md
  - docs/plans/SPRINT_REGISTRY.md  # +S241 row, Next -> S242
evidence_local_only:
  - data/_FINAL/EMPLOYEE_MASTER.csv  # +45 rows in main checkout SSOT (gitignored)
evidence_transient:
  - tmp/s241_new_hires/extracted_apr20_to_may9.csv
  - tmp/s241_new_hires/missing_from_master.csv
  - tmp/s241_new_hires/matched_summary.csv
  - tmp/s241_new_hires/proposed_assignments.json
  - tmp/s241_new_hires/new_45_rows.csv
  - tmp/s241_new_hires/EMPLOYEE_MASTER_pre_s241_backup.csv
  - tmp/s241_new_hires/enrollment_plan.json
  - tmp/s241_new_hires/enrollment.sql
  - tmp/s241_new_hires/probe_*.json
  - tmp/s241_new_hires/probe_*_output.txt
  - tmp/s241_new_hires/exec_output.txt
  - tmp/s241_new_hires/AUDIT.md
  - tmp/s241_new_hires/COLLISION_AUDIT.md
sprint_registry_row: |
  | `S241` | Sprint 241 | `s241-new-hires-apr20-may9-import` (hrms — Master CSV bulk import + 146 ADMS USERINFO inserts cluster cross-enrollment, no Frappe/no Sheets) | TBD | AGENT_BUILD_COMPLETE 2026-05-08 - New Hires Masterlist Import Apr 20 - May 9 (45 hires, Bio IDs 9001935-9001979) | `docs/plans/2026-05-08-sprint-241-new-hires-apr20-may9-import.md` |
---

# Sprint 241 — New Hires Masterlist Import (April 20 - May 9, 2026)

> **Source:** Sam directive 2026-05-08 PHT — "extract from New Hires Masterlist Google Sheet, ignore New Batch and tabs earlier than April 20, find missing from Master, add to CSV, generate XLSX for HR, enroll in ADMS without HR comment if work locations already indicated".

## What this sprint did

### W1 — Data extraction
- Source: Google Sheet `1oxf0ApyxoCrObatos6rO_qLZcv04P8_NC6b9JIGHPtM` (title: "New Hires Masterlist_Feb 2026 Onwards")
- Scope: 12 tabs (April 20-30 + May 6 + May 9)
- Ignored: "New Batch" tab + 14 tabs dated April 17 and earlier
- Extracted: 79 employee rows

### W2 — Master CSV cross-reference
- Matched against `data/_FINAL/EMPLOYEE_MASTER.csv` by normalized (Last, First) name
- Result: 34 already in Master; **45 missing** → import targets

### W3 — Collision audit (Frappe + ADMS)
Pre-write SSM probes verified Bio ID range 9001935-9001979 is virgin:
- Frappe `tabEmployee`: 0 rows in range; max stays at 9001881
- ADMS `adms_user_registry`: 0 rows in range
- ADMS `adms_attlog_raw`: 0 punches in range
- ADMS `adms_device_cmd`: 0 USERINFO commands queued for range
- Frappe name surveillance: 5 last-name coincidences (BUENO, CONCEPCION, FERNANDO, GARCIA, MAURICIO) — all confirmed different first names = different people; 3 of the 5 existing are `Left` status
- Diacritic-aware fuzzy check: 0 hits (Cañada/Castañeda/Nuñez do not collide with anyone)

### W4 — Master CSV append (45 rows)
- Bio IDs 9001935..9001979 sequentially assigned by tab-chronological order
- 16 employees auto-renamed: `CAMANGYANAN BULACAN` → `3MD COMMISSARY` (consistent with S239+S240 directive)
- 30 columns matching Master CSV schema
- Department mapping derived from existing precedents:
  - STORE CREW / CASHIER / STORE OIC → Operations
  - COMMISSARY CREW / PRODUCTION SUPERVISOR / DELIVERY DRIVER / DELIVERY HELPER / LOGISTICS SUPERVISOR → Commissary
  - RECEPTIONIST → Admin
  - MARKETING OFFICER → Marketing (corrected from inconsistent precedent)
  - FINANCE ANALYST → Finance and Accounting (corrected from inconsistent precedent)
- Master CSV total: 749 → **794** rows

### W5 — ADMS cluster cross-enrollment (146 USERINFO commands)

Per `clusters.md` "Adding a New Employee to Their Cluster" rule — new hires enroll on ALL cluster devices:

| Group | Hires | Devices each | Total commands |
|---|---|---|---|
| 3MD Commissary (standalone) | 16 | 1 (UDP3254800655) | 16 |
| Head Office (BGC-BRITTANY + BGC-CAPITAL HOUSE) | 5 | 3 (Brittany + Capital House + Shaw) | 15 |
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

All 146 INSERTs verified with exactly 2 tab bytes per command_text (PIN=...\tName=...\tPri=0).

### W6 — CHANGE_LOG audit (90 rows)
- 45 EMPLOYEE_MASTER ADD rows
- 45 ADMS ENROLL rows (one per employee, listing all target SNs in new_value)
- CHANGE_LOG.csv: 798 → 888 lines

### W7 — HR handoff XLSX
- `output/s241/hr_handoff/S241_New_Hires_Apr20_May9_2026-05-08.xlsx`
- Two tabs: "S241 New Hires" (45 employee rows with Bio ID + work location + contact info) + "Summary" (counts + breakdowns)
- Yellow-highlighted rows for the 16 commissary hires (renamed location)
- HR action: mirror these 45 rows into the BEI Employee Master Google Sheet (`1iFDbvaOg0...`)

## Verification (post-execution)

ACK polling at +60 seconds: **141 of 146 ACKED (96.6%)**, 5 PENDING:
- UDP3251600215 (BF Homes): 3 PENDING — device offline at moment of poll
- UDP3252100385 (Robinsons Gentri): 1 PENDING
- UDP3252900251 (Greenhills): 1 PENDING

These 5 will ACK automatically on next device heartbeat (~60s polling interval).

UTF-8 byte verification: hex-dumped commands containing `Ñ` confirmed `c391` bytes correctly stored in DB (the `�` shown in SSM output stream was Windows console display issue, not data corruption).

## What this sprint did NOT do

- ❌ NO Frappe `tabEmployee` insert (HR audit pending — S228/S230/S239 precedent)
- ❌ NO Google Sheet auto-sync (HR will mirror via XLSX handoff)
- ❌ NO ADMS receiver restart (all target devices already in allowlist; no new SNs added)
- ❌ NO touch on the 11 stale `adms_user_registry` test-pollution rows (deferred to optional cleanup sprint)

## Sam handoff

1. Review and merge PR
2. Send the XLSX (`output/s241/hr_handoff/S241_New_Hires_Apr20_May9_2026-05-08.xlsx`) to HR
3. (Optional) Confirm 5 PENDING devices come online + ACK — auto-resolves on heartbeat
4. (Optional) Notify each store/commissary that the new hires can now physically register fingerprints at their assigned device

## Source References

- **Source Google Sheet:** `1oxf0ApyxoCrObatos6rO_qLZcv04P8_NC6b9JIGHPtM`
- **Audit:** `tmp/s241_new_hires/AUDIT.md` + `COLLISION_AUDIT.md`
- **Pattern reference:** `docs/plans/2026-04-29-sprint-230-xentro-estancia-device-enrollment.md`
- **Cluster rule:** `.claude/skills/adms-bei-erp/references/clusters.md` — "Adding a New Employee to Their Cluster"
- **Tab-byte USERINFO rule:** `.claude/skills/adms-bei-erp/SKILL.md`
