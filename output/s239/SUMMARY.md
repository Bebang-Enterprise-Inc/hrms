# S239 — Camangyanan Bulacan Device + 8 Crew + Mingoy Reliever

**Status:** AGENT_BUILD_COMPLETE 2026-05-07 PHT
**Branch:** `s239-camangyanan-mingoy`
**Worktree:** `F:/Dropbox/Projects/BEI-ERP-s239-camangyanan-mingoy`
**canonical_scope:** none (verified — no tabCompany/tabWarehouse/tabCustomer/tabSupplier touched)

## What was requested

Ron Andrew Santos chat 2026-05-06 (two messages):
1. **10:22 AM:** Enroll `9001701 MINGOY, DOMINIC LANCE M.` (STORE CREW, D'verde Calamba) at THE TERMINAL ALABANG as same-day reliever.
2. **5:41 PM:** Register new BIO device `UDP3254800655` at CAMANGYANAN BULACAN + enroll 8 commissary crew (Bio IDs 9001882, 9001885, 9001898, 9001899, 9001906, 9001911, 9001921, 9001931).

Sam approval 2026-05-07 PHT after live audit.

## What was done

### W1 — Server allowlist (EC2)
- File: `/opt/frappe/bebang-hrms/adms_receiver/sn_mapping_all.csv`
- Lines: 51 → **52**
- Row appended: `52,CAMANGYANAN BULACAN,camangyananbulacan,Camangyanan Bulacan,commissary,,EXACT_NAME,user_clarification,ZKTeco MB10-VL,UDP3254800655,Active,5/7/2026,,`
- Verified via `grep` post-write.

### W2 — Local Python mapping
- File: `hrms/utils/device_mapping.py`
- Entries: 47 → **48**
- Added: `'UDP3254800655': 'CAMANGYANAN BULACAN',  # S239 (2026-05-07): new commissary device`

### W3 — Cluster doc (local-only — `.claude/` is gitignored)
- File: `.claude/skills/adms-bei-erp/references/clusters.md` (Sam's main checkout)
- Added new row in "Not Part of Store Clusters" table:
  > `| Camangyanan Bulacan Commissary | 1 (UDP3254800655) | 8 | New BEI commissary, S239 2026-05-07 |`
- NOT included in PR diff (file is gitignored — Sam already has the local update).

### W4 — 9 PENDING USERINFO commands inserted
- Table: `adms_device_cmd`
- IDs 12016-12024 (auto-incremented serial)
- Tab-byte validation: 2 tabs per command_text (PIN=...\tName=...\tPri=0)
- Per-PIN target:

| ID | SN | PIN | Name | Status |
|---|---|---|---|---|
| 12016 | UDP3254800655 | 9001882 | ALIMAN, BERNADETTE E. | PENDING |
| 12017 | UDP3254800655 | 9001885 | ATIP, MARVIN G. | PENDING |
| 12018 | UDP3254800655 | 9001898 | DEL CARMEN, RUBELYN R. | PENDING |
| 12019 | UDP3254800655 | 9001899 | DELA CRUZ, GERZIE A. | PENDING |
| 12020 | UDP3254800655 | 9001906 | GABRIEL, JAIDIE H. | PENDING |
| 12021 | UDP3254800655 | 9001911 | HACOME, GERALYN L. | PENDING |
| 12022 | UDP3254800655 | 9001921 | PALOQUIA, LADIE MAE C. | PENDING |
| 12023 | UDP3254800655 | 9001931 | SISON, DANICA I. | PENDING |
| 12024 | CNYG242061718 | 9001701 | MINGOY, DOMINIC LANCE M. | **ACKED** at 06:26:36 UTC (0.24s after sent) |

### W5 — CHANGE_LOG.csv
- File: `data/_FINAL/CHANGE_LOG.csv`
- Rows: 786 → **796** (+10: 1 device-register + 8 crew + 1 reliever)

## Outcomes

### ✅ Mingoy reliever — operational immediately
The Terminal device (CNYG242061718) ACKED USERINFO for PIN 9001701 in 240 milliseconds. **Mingoy can punch at The Terminal RIGHT NOW** upon physical fingerprint scan. (Per ZKTeco MB10-VL behavior: USERINFO creates the user record on-device; fingerprint must still be scanned physically.)

### ⏳ Camangyanan 8 — queued, waiting on Sam's receiver restart
8 commands stay PENDING because the ADMS receiver's in-memory allowlist hasn't reloaded the new SN. Once Sam runs `docker restart adms_receiver_adms-api_1`, the receiver picks up UDP3254800655 from the file, and on the device's next heartbeat, all 8 USERINFO commands will be sent + (presumably) ACKED.

If the device is **not yet physically deployed** at Camangyanan, the 8 commands stay PENDING harmlessly until the device is plugged in and connects to `adms.bebang.ph:8443`.

### Sam handoff (post-merge)

```bash
# Step 1 — merge this PR (PR# below)
# Step 2 — restart ADMS receiver to reload allowlist
ssh ... or via SSM
docker restart adms_receiver_adms-api_1

# Step 3 — wait for device heartbeat (depends on physical install state)
# Step 4 — verify 8 ACKs (after some minutes)
sudo docker exec <ADMS_DB> psql -U adms -d adms -c \
  "SELECT id, sn, status, acked_at FROM adms_device_cmd WHERE id BETWEEN 12016 AND 12023;"
```

## What was NOT done (per CEO directive — same as S228/S230)

- ❌ NO Frappe `tabEmployee` insert for the 8 Camangyanan crew. Reason: HR audit of the 2026-04-28 New Hires Masterlist still pending. Frappe MAX(bio_id)=9001881; these 8 are 9001882-9001931, ready for batched insert when HR clears.
- ❌ NO Google Sheet sync. Same reason.
- ❌ NO Master CSV update. Already correct since 2026-04-28 (8 Camangyanan rows have `store_location=CAMANGYANAN BULACAN`, `bio_device_name=CAMANGYANAN BULACAN`, `status=Active`).
- ❌ NO touch on the 11 stale `adms_user_registry` rows from 2026-04-07 L3 test campaign. Verified test pollution (zero attlogs, zero device commands, all `enrolled_by='api'`/`api_push`) — physical devices never had these users. Deferred to optional S240 if cleanup is ever desired.

## Verifying the audit was honest

Pre-write probes captured: `tmp/adms_camangyanan_audit_2026-05-07/probe_*_output*.txt`
Post-write probes captured: `output/s239/verification/state_after.json` + `output/s239/verification/ack_polling.log`

Mingoy real-vs-test verification (probe C from `probe_attlog_v2_output.txt`):
```
9001701 | UDP3252900188 | 262 punches | latest 2026-05-07 13:12:26 PHT
```
He's punching at D'verde literally an hour before this sprint ran. Real human, real attendance.

## Worktree evidence

| Path | Type |
|------|------|
| `output/s239/SUMMARY.md` | this file |
| `output/s239/verification/state_before.json` | pre-write snapshot |
| `output/s239/verification/state_after.json` | post-write snapshot |
| `output/s239/verification/ack_polling.log` | 3-poll loop output |
| `hrms/utils/device_mapping.py` | +1 entry |
| `data/_FINAL/CHANGE_LOG.csv` | +10 rows |
| `docs/plans/2026-05-07-sprint-239-camangyanan-mingoy.md` | the plan |
| `docs/plans/SPRINT_REGISTRY.md` | +S239 row, Next bumped to S240 |

## Closeout

After Sam merges and restarts: flip plan `status: AGENT_BUILD_COMPLETE` → `COMPLETED`, update registry `TBD` → PR#, append closeout amendment row.
