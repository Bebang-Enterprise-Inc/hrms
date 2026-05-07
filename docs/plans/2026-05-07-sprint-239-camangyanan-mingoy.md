---
sprint_id: S239
display: Sprint 239
slug: camangyanan-mingoy
plan_filename: 2026-05-07-sprint-239-camangyanan-mingoy.md
branch: s239-camangyanan-mingoy
repos: [hrms]
date_created: 2026-05-07
status: PLANNED
plan_version: v1
canonical_scope: none
canonical_scope_rationale: |
  ADMS device config (server allowlist + local Python mapping + skill cluster doc) +
  9 INSERT rows into `adms_device_cmd` queue (8 Camangyanan crew + 1 Mingoy reliever) +
  9 append rows into `data/_FINAL/CHANGE_LOG.csv`.
  No tabCompany / tabWarehouse / tabCustomer / tabSupplier UPDATE/INSERT/DELETE.
  No Sales Invoice / Purchase Order / Material Request / Stock Entry / Journal Entry /
  Payment Entry / GL Entry creation.
  No Frappe `tabEmployee` insert (HR audit pending — same CEO directive as S228/S230).
  No Master CSV row addition (8 Camangyanan crew already present with correct
  store_location + bio_device_name set on 2026-04-28; Mingoy already present at home
  store D'verde Calamba).
  No Google Sheet sync (HR audit pending).
ceo_directive_source: |
  Sam approval 2026-05-07 PHT after Ron Andrew Santos chat requests:
    - Yesterday 10:22 AM: enroll 9001701 MINGOY at THE TERMINAL ALABANG (reliever from D'verde Calamba)
    - Yesterday 5:41 PM: register UDP3254800655 + enroll 8 Camangyanan crew (9001882, 9001885, 9001898, 9001899, 9001906, 9001911, 9001921, 9001931)
audit_evidence: tmp/adms_camangyanan_audit_2026-05-07/
related_plans:
  - docs/plans/2026-04-29-sprint-230-xentro-estancia-device-enrollment.md  # exact pattern reference
  - docs/plans/2026-05-05-sprint-237-l3-test-pollution-cleanup.md          # post-S237 vigilance
evidence_committed:
  - output/s239/SUMMARY.md
  - output/s239/verification/state_before.json
  - output/s239/verification/state_after.json
  - output/s239/verification/ack_polling.log
  - hrms/utils/device_mapping.py        # +1 entry: UDP3254800655
  - data/_FINAL/CHANGE_LOG.csv          # +9 rows
  - docs/plans/2026-05-07-sprint-239-camangyanan-mingoy.md
  - docs/plans/SPRINT_REGISTRY.md       # +S239 row, bump Next to S240
evidence_local_only:
  # `.claude/` is gitignored and never committed to production (verified via `git log --all --oneline -- .claude/skills/adms-bei-erp/` returns 0 commits)
  - .claude/skills/adms-bei-erp/references/clusters.md   # Sam's main-checkout local copy — agent reference doc only
evidence_transient:
  - tmp/adms_camangyanan_audit_2026-05-07/probe_*.json
  - tmp/adms_camangyanan_audit_2026-05-07/probe_*_output*.txt
  - tmp/s239/ssm_responses/*.json
sprint_registry_row: |
  | `S239` | Sprint 239 | `s239-camangyanan-mingoy` (hrms — ADMS: new commissary device UDP3254800655 + 8 Camangyanan crew enrollments + 1 cross-cluster reliever Mingoy → The Terminal) | TBD | PLANNED 2026-05-07 — Camangyanan Bulacan Device Registration + 8 Crew Enrollments + Mingoy Cross-Cluster Reliever | `docs/plans/2026-05-07-sprint-239-camangyanan-mingoy.md` |
---

# Sprint 239 — Camangyanan Bulacan Device + 8 Crew + Mingoy Reliever

> **Source:** Ron Andrew Santos two requests on 2026-05-06; Sam approval 2026-05-07 PHT.
> **PR-Handoff:** Agent creates the PR and STOPS. Sam handles merge. Sam runs `docker restart adms_receiver_adms-api_1` post-merge to reload allowlist for the new SN.

## Design Rationale (For Cold-Start Agents)

### Why this exists

Two unrelated enrollment requests bundled into one sprint because they're operationally adjacent:

1. **Camangyanan Bulacan commissary** — a new BEI commissary location. ZKTeco MB10-VL device with serial `UDP3254800655` shipped to site. Master CSV already pre-allocated 8 commissary crew there (assigned 2026-04-28, Bio IDs 9001882..9001931, all Active). Device needs all 3 BEI ADMS registers populated:
   - **Server allowlist** (`/opt/.../sn_mapping_all.csv`) — without this, device heartbeat returns 403
   - **Local Python mapping** (`hrms/utils/device_mapping.py`) — without this, scripts that resolve SN → store throw KeyError
   - **`adms_device_cmd` queue** — 8 PENDING USERINFO commands needed for crew to punch
   - And `clusters.md` doc updated so future agents know Camangyanan exists

2. **Mingoy reliever** — `9001701 MINGOY, DOMINIC LANCE M.` is an Active store crew at D'VERDE CALAMBA (Cluster 4, UDP3252900188), being deployed today as reliever to THE TERMINAL ALABANG (Cluster 6, CNYG242061718). Per `clusters.md:217` cross-cluster reliever rule: push USERINFO to the destination home device only (CNYG242061718), NOT to all C6 devices, NOT to other C4 devices. Master CSV `bio_device_name` stays `D'verde` (his anchor); CHANGE_LOG records the temporary deployment.

### Why no Frappe insert / no Google Sheet sync (same as S228/S230)

CEO directive paused Frappe `tabEmployee` mass-import until HR completes audit of the 2026-04-28 New Hires Masterlist (the upload that allocated Bio IDs 9001882-9001931). Until that audit lands, Master CSV is the SSOT and Frappe stays at MAX(bio_id)=9001881. ADMS enrollment can proceed independently because punches resolve through ADMS receiver's own `adms_user_registry`, not Frappe's `tabEmployee`. Payroll's tie-back to Frappe Employee happens in scheduled job after HR audit.

### Why Camangyanan is "standalone commissary" not a cluster

`clusters.md` documents 9 retail clusters under Edlice's area supervisors. Camangyanan crew are all `department=Commissary` (production supervisor, commissary crew, delivery helper) — same operational class as Shaw Commissary (UDP3235200629) which is documented as a non-clustered device. Camangyanan inherits that pattern: single device, single store assignment, no cross-enrollment.

### Why Mingoy reliever pushes ONLY to CNYG242061718

Cross-cluster reliever rule (`clusters.md:217`):
> "When an employee is temporarily deployed to a store in a **different** cluster, push USERINFO to that specific device only (not the whole target cluster)."

Mingoy's home is C4. Terminal is C6. Pushing him to ALL C6 devices would imply he's a C6 hire — wrong signal for cluster operations + payroll attribution. Single USERINFO + CHANGE_LOG entry preserves the "temporary reliever" semantics.

### Live audit verified before this plan was written

5 SSM probe batches against `i-026b7477d27bd46d6` confirmed:
- `UDP3254800655` not in server allowlist (51 lines, no match) — genuinely new
- 0 callbacks ever for `UDP3254800655` — device hasn't tried to heartbeat
- 0 attlogs for any of the 9 enrollment-target Bio IDs at any device (the 8 Camangyanan crew never punched anywhere; MINGOY actively punching at D'verde today)
- MINGOY 9001701: 262 punches at UDP3252900188, last today 13:12:26 PHT — verified real and active
- 192 ACKED commands at CNYG242061718 (Terminal) + 0 PENDING — healthy target
- 11 stale `adms_user_registry` rows from 2026-04-07 L3 test campaign exist (PINs 9001882, 9001883, 9001884, 9001885, 9001886, 9001887, 9001888, 9001889, 9001890, 9001894, 9001895). Verified NOT real-employee data: 0 attlogs, 0 `adms_device_cmd` records, all `enrolled_by='api'` `enrollment_method='api_push'` from L3 test framework. Physical devices (Brittany, Araneta) NEVER had USERINFO commands for these PINs. Tracking-table-only artifacts. **DEFERRED OUT-OF-SCOPE for S239** per Sam approval — discuss separately if/when worth cleaning.

Audit evidence: `tmp/adms_camangyanan_audit_2026-05-07/` (probes + AUDIT_FINAL.md).

### Known limitations

1. Device must be physically deployed at Camangyanan and pointed at `adms.bebang.ph:8443`. If Ron's team hasn't completed physical install, the allowlist append is harmless — device will connect later when plugged in.
2. After allowlist append on EC2, the receiver must reload its in-memory allowlist via `docker restart adms_receiver_adms-api_1`. Sam handles this manually post-merge (deploy-handoff per BEI policy).
3. USERINFO creates the user record on the device, but fingerprints must still be physically scanned at the device by each employee. The receiver/server cannot push fingerprint data — only the device records it locally.
4. The 8 Camangyanan crew will not appear in Frappe payroll reports until HR audit completes and S228 phase 4 runs (Frappe `tabEmployee` insert). Bio attendance attribution still works via ADMS receiver's `adms_user_registry`.

## What this sprint does

### W1 — Server allowlist (1 line append on EC2)

```bash
# Via SSM on i-026b7477d27bd46d6
echo "52,CAMANGYANAN BULACAN,camangyananbulacan,Camangyanan Bulacan,commissary,,EXACT_NAME,user_clarification,ZKTeco MB10-VL,UDP3254800655,Active,5/7/2026,," \
  | sudo tee -a /opt/frappe/bebang-hrms/adms_receiver/sn_mapping_all.csv
```

Net: 51 → 52 lines. After-state verification: `grep UDP3254800655` returns 1 row.

### W2 — Local Python mapping (1 entry add)

```python
# hrms/utils/device_mapping.py
DEVICE_TO_STORE = {
    ...,
    'UDP3252900251': 'GREENHILLS',
    'UDP3254800655': 'CAMANGYANAN BULACAN',  # S239 (2026-05-07): commissary device
}
```

Net: 47 → 48 entries.

### W3 — Cluster doc update

`.claude/skills/adms-bei-erp/references/clusters.md` — add Camangyanan to the "Not Part of Store Clusters" table alongside Head Office, MyTown, Shaw Commissary. New row:
```
| Commissary | 1 (Camangyanan UDP3254800655) | 8 | New Bulacan commissary, S239 2026-05-07 |
```

### W4 — 9 PENDING USERINFO commands inserted into `adms_device_cmd`

Via SSM Postgres on EC2. Tab-byte safe per `adms-bei-erp/SKILL.md`:

```sql
-- 8 Camangyanan crew (target: UDP3254800655)
INSERT INTO adms_device_cmd (sn, command_text, status, attempts, created_at, updated_at)
VALUES
  ('UDP3254800655', E'DATA UPDATE USERINFO PIN=9001882\tName=ALIMAN, BERNADETTE E.\tPri=0', 'PENDING', 0, NOW(), NOW()),
  ('UDP3254800655', E'DATA UPDATE USERINFO PIN=9001885\tName=ATIP, MARVIN G.\tPri=0', 'PENDING', 0, NOW(), NOW()),
  ('UDP3254800655', E'DATA UPDATE USERINFO PIN=9001898\tName=DEL CARMEN, RUBELYN R.\tPri=0', 'PENDING', 0, NOW(), NOW()),
  ('UDP3254800655', E'DATA UPDATE USERINFO PIN=9001899\tName=DELA CRUZ, GERZIE A.\tPri=0', 'PENDING', 0, NOW(), NOW()),
  ('UDP3254800655', E'DATA UPDATE USERINFO PIN=9001906\tName=GABRIEL, JAIDIE H.\tPri=0', 'PENDING', 0, NOW(), NOW()),
  ('UDP3254800655', E'DATA UPDATE USERINFO PIN=9001911\tName=HACOME, GERALYN L.\tPri=0', 'PENDING', 0, NOW(), NOW()),
  ('UDP3254800655', E'DATA UPDATE USERINFO PIN=9001921\tName=PALOQUIA, LADIE MAE C.\tPri=0', 'PENDING', 0, NOW(), NOW()),
  ('UDP3254800655', E'DATA UPDATE USERINFO PIN=9001931\tName=SISON, DANICA I.\tPri=0', 'PENDING', 0, NOW(), NOW());

-- 1 Mingoy reliever (target: CNYG242061718 only — cross-cluster, NOT all C6)
INSERT INTO adms_device_cmd (sn, command_text, status, attempts, created_at, updated_at)
VALUES
  ('CNYG242061718', E'DATA UPDATE USERINFO PIN=9001701\tName=MINGOY, DOMINIC LANCE M.\tPri=0', 'PENDING', 0, NOW(), NOW());
```

Tab-separator validation: each `command_text` must contain ≥2 actual `\t` (0x09) bytes between PIN/Name/Pri. PostgreSQL E-string syntax (`E'...'`) interprets `\t` as the tab byte.

### W5 — CHANGE_LOG.csv (9 audit rows)

Append 9 rows to `data/_FINAL/CHANGE_LOG.csv` with structure matching existing rows (S230 reference). Reason for the 8 Camangyanan crew: `s239-camangyanan-enrollment`. Reason for Mingoy: `s239-mingoy-reliever-to-terminal`.

### W6 — Verification phase (read-only SSM)

After W4 is queued, poll `adms_device_cmd` every ~30s for ACK transitions. Target devices:
- UDP3254800655: device must heartbeat first (requires receiver restart) — likely 0 ACKs in this session, all 8 stay PENDING until Sam restarts the API container
- CNYG242061718: existing healthy device, should ACK Mingoy USERINFO within 1-2 minutes if device is online

Capture all status snapshots to `output/s239/verification/ack_polling.log`.

## Phase order

| Phase | Action | System | Verifier |
|---|---|---|---|
| P0 | Capture state_before via SSM | ADMS DB read | Save to `output/s239/verification/state_before.json` |
| P1 | Append `UDP3254800655` to server allowlist | EC2 file write | `grep` returns 1 row, line count = 52 |
| P2 | INSERT 8 USERINFO for UDP3254800655 + 1 for CNYG242061718 | ADMS DB write | `SELECT COUNT(*) FROM adms_device_cmd WHERE created_at > P2_start` returns 9 |
| P3 | Edit `hrms/utils/device_mapping.py` | Local file | `grep UDP3254800655 hrms/utils/device_mapping.py` returns 1 |
| P4 | Edit `clusters.md` | Local file | `grep CAMANGYANAN .claude/skills/adms-bei-erp/references/clusters.md` returns 1 |
| P5 | Append 9 rows to `data/_FINAL/CHANGE_LOG.csv` | Local file | `tail -10 data/_FINAL/CHANGE_LOG.csv` shows 9 new rows |
| P6 | Sync skill mirrors to Codex (`scripts/sync_claude_skills_to_codex.ps1`) | Local file | `.agent/skills/adms-bei-erp/...` and `.agents/skills/adms-bei-erp/...` updated |
| P7 | Capture state_after via SSM read | ADMS DB read | `output/s239/verification/state_after.json` |
| P8 | ACK polling (60s loop, ≤5 iterations) | ADMS DB read | `output/s239/verification/ack_polling.log` |
| P9 | Write `output/s239/SUMMARY.md` | Local file | exists |
| P10 | Commit + push + create PR | Git | PR# returned |

## Source References

- **Audit:** `tmp/adms_camangyanan_audit_2026-05-07/AUDIT_FINAL.md`
- **Pattern reference:** `docs/plans/2026-04-29-sprint-230-xentro-estancia-device-enrollment.md`
- **Cross-cluster reliever rule:** `.claude/skills/adms-bei-erp/references/clusters.md:217`
- **Tab-byte USERINFO rule:** `.claude/skills/adms-bei-erp/SKILL.md` (Method 2 PG E-string)
- **Master CSV (SSOT):** `data/_FINAL/EMPLOYEE_MASTER.csv` — 9 employees verified clean
- **Frappe state at audit time:** MAX(attendance_device_id) = 9001881; only MINGOY (9001701) row exists for the 9 PINs

## Amendment Log

| Date | Author | Section | Change |
|------|--------|---------|--------|
| 2026-05-07 | Sam (via Claude) | INITIAL | Plan written + executed in same session per Ron's two requests + Sam approval. canonical_scope=none. No Frappe / no Google Sheet (HR audit pending pattern, S228/S230 precedent). |
