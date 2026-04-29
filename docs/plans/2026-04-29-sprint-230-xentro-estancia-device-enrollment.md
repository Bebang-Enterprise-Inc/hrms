---
sprint_id: S230
display: Sprint 230
slug: xentro-estancia-device-enrollment
plan_filename: 2026-04-29-sprint-230-xentro-estancia-device-enrollment.md
branch: s230-xentro-estancia-device-enrollment
repos: [hrms]
date_created: 2026-04-29
status: AGENT_BUILD_COMPLETE
plan_version: v2-executed
completed_date: 2026-04-29
execution_summary: |
  Executed 2026-04-29 PHT. Scope reduced inline per CEO directive: NO Frappe inserts, NO Google Sheet sync (Master CSV is authoritative; HR audit pending). Net actions: (W1) appended UDP3254701502,XENTROMALL_MONTALBAN to /opt/.../sn_mapping_all.csv (51 rows total, was 50); (W2) added 'UDP3252900249':'ORTIGAS ESTANCIA' and 'UDP3254701502':'XENTROMALL MONTALBAN' to hrms/utils/device_mapping.py (50 entries total, was 48); (W3) inserted 48 PENDING USERINFO commands into adms_device_cmd (12 each on UDP3251200193 SM East Ortigas + UDP3252900048 SM Taytay + UDP3235200594 Robinsons Antipolo + UDP3254701502 Xentro Mall home) — deduped against the 24 already-ACKED Marikina/Sta Lucia rows; (W4) appended 50 entries to data/_FINAL/CHANGE_LOG.csv. 5/6 verification probes PASS, 1 PARTIAL (live heartbeat watch deferred until Sam executes manual_steps.md Step 1 API container restart). Pending Sam: API container restart, PR review+merge.
canonical_scope: none
canonical_scope_rationale: |
  ADMS device config + Employee Master CSV reshape + new-hire Frappe `tabEmployee` inserts only.
  No tabCompany / tabWarehouse / tabCustomer / tabSupplier UPDATE/INSERT/DELETE.
  No Sales Invoice / Purchase Order / Material Request / Stock Entry / Journal Entry / Payment Entry / GL Entry creation.
  Canonical store entity rows for `Ortigas Estancia` and `Xentromall Montalban` already exist in `hrms/data_seed/store_entity_mapping_2026-04-14.csv`; this sprint does not modify them.
  Reuses the same canonical_scope=none classification as S228 (parallel HR-data-only sprint).
  Audit confirmed canonical_scope: PASS SKIPPED-OUT-OF-SCOPE (v2 audit 2026-04-29).
ceo_directive_source: 2026-04-29 conversation; transcript captured in tmp/s230/PROVENANCE.md
audit_evidence: output/plan-audit/sprint-230-xentro-estancia-device-enrollment/
v2_amendments_resolve: 10 CRITICAL (B1-B10) + 10 high-priority WARNING blockers from 4-domain audit
depends_on:
  - S228 (NewHires Import) — coordination via live SSM Frappe MAX query; verify no Bio ID overlap before pushing rows. NOTE — S228 branch is LOCAL only on origin (verified 2026-04-29 git branch -r), so the concurrency check uses live Frappe state, not git refs.
related_plans:
  - docs/plans/2026-04-28-sprint-228-new-hires-import-anomaly-fix.md
  - docs/plans/2026-03-14-sprint-42-new-hire-onboarding-adms-scheduler.md
  - .claude/skills/adms-bei-erp/references/clusters.md
canonical_branch_name: "XENTRO MONTALBAN"   # v2-B1: matches S228 tabBranch row tmp/insert_13_employees.py:23-32
canonical_estancia_branch_name: "ORTIGAS ESTANCIA"  # v2-B8: verified at Phase 4-0 against tabBranch
evidence_committed:
  - output/s230/SUMMARY.md
  - output/s230/DEFECTS.md
  - output/s230/manual_steps.md                                    # v2-B5: SSM commands for Sam
  - output/s230/REMOTE_TRUTH_BASELINE.json                         # v2-B5: Phase 0 capture
  - output/s230/SURFACE_OWNERSHIP_MATRIX.csv                       # v2-B5
  - output/s230/PROTECTED_SURFACE_REGISTRY.csv                     # v2-B5
  - output/s230/TOUCHED_FILE_ROUTING.csv                           # v2-B5
  - output/s230/verification/server_allowlist_after.txt
  - output/s230/verification/local_mapping_after.diff
  - output/s230/verification/employee_master_after.csv_diff
  - output/s230/verification/google_sheet_after.json
  - output/s230/verification/adms_enrollment_acks.json
  - output/s230/verification/state_after.json
  - output/s230/verification/enrollment_matrix.csv                 # v2-B5: Phase 5-5 output
  - output/s230/verification/tabBranch_precheck.json               # v2-B8: Phase 4-0 output
  - output/s230/verification/frappe_max_bio_id.json                # v2-B3: Phase 4-2-bis output
  - output/s230/verify_phase0.py
  - output/s230/verify_phase1.py
  - output/s230/verify_phase2.py
  - output/s230/verify_phase3.py
  - output/s230/verify_phase4.py
  - output/s230/verify_phase5.py
  - output/s230/verify_phase6.py
  - output/s230/verify_phase7.py
  - data/_FINAL/CHANGE_LOG.csv (rows added — committed via `git add -f`)
  - data/_FINAL/EMPLOYEE_MASTER.csv (rows added if Xentro crew supplied — committed via `git add -f`)
  - hrms/utils/device_mapping.py (tracked — no -f needed)
  - .claude/skills/adms-bei-erp/references/clusters.md (v2-B6 staleness fix — `git add -f` since `.claude/` is gitignored)
  - docs/plans/2026-04-29-sprint-230-xentro-estancia-device-enrollment.md (`git add -f`)
  - docs/plans/SPRINT_REGISTRY.md (`git add -f`)
evidence_transient:
  - tmp/s230/PROVENANCE.md
  - tmp/s230/ssm_responses/*.json
  - tmp/s230/ack_polling_*.log
  - tmp/s230/employee_master_pre_change.csv
  - tmp/s230/sn_mapping_all_pre_change.csv
  - tmp/s230/sn_mapping_all_post_change.csv
  - tmp/s230/insert_employee_*.py
  - tmp/s230/enrollment_batch.json
  - tmp/s230/enrollment_plan.json
  - tmp/s230/preexisting_pending_dedup.json                        # v2-B7: Phase 5-1-pre output
  - tmp/s230/changes.json
---

# Sprint 230 — Xentro Mall Device Registration + Estancia Local-Mapping Fix + Crew Enrollment

> **Source:** CEO directive 2026-04-29 — "add Xentro Mall Device ID and whitelist it, make sure Estancia is whitelisted too, add employees to Employee Master and enroll in their stores and territory using `/adms-bei-erp`, fix the local registry and add both devices locally properly."

> **PR-Handoff:** Agent creates the PR and STOPS. Sam handles merge + deploy. The agent does NOT merge or restart `adms_receiver_adms-api_1` without an explicit deploy password from Sam.

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

ADMS biometric devices at BEI stores are gated by THREE separate registers that must agree:

1. **Server-side allowlist** — `/opt/frappe/bebang-hrms/adms_receiver/sn_mapping_all.csv` on EC2 `i-026b7477d27bd46d6`. Without this, the device's heartbeat returns **403 Forbidden** and no commands queue.
2. **Local Python mapping** — `hrms/utils/device_mapping.py` (`DEVICE_TO_STORE` dict). Without this, scripts that resolve serial → store name throw `KeyError("Device <SN> not in mapping. Update device_mapping.py!")`.
3. **`adms_device_cmd` table** — Postgres queue for `DATA UPDATE USERINFO` (enrollment) and other commands. Without enrollment commands, employees can't punch.

A device is "fully enrolled" only when all three are correct. **Estancia** is in #1 (registered as `UDP3252900249,ESTANCIA` in the server allowlist) and has 54 PENDING enrollment commands waiting in #3 since 2026-03-30 — but it is **missing from #2** (local Python mapping has 47 devices, none of which is Estancia). The physical device has also **never heartbeated** (zero rows in `adms_attlog_raw`, zero callbacks in `adms_device_cmd_callback`) — meaning either the device hasn't been physically deployed, isn't pointed at `adms.bebang.ph:8443`, or has a different serial than `UDP3252900249`.

**Xentro Mall** (canonical store name: `Xentromall Montalban`, buyer entity: `Perpetual Food Corp.`, listed in `hrms/data_seed/store_entity_mapping_2026-04-14.csv` row 50) is in **none** of the three registers. The device serial number was not provided in the CEO request and must be supplied at Phase 0.

The 4 known active Estancia crew (`PAGSALIGAN, HAYDEE D.` 9001827; `MORALES, MAE PEARL GRACE E.` 9001830; `MARTILLANO, LUISA B.` 9001832; `VILLAREAL, JENNY A.` 9001835) already exist in `data/_FINAL/EMPLOYEE_MASTER.csv` with `store_location=ESTANCIA` and `Active` status. Their enrollment commands account for some of the 54 PENDING. Xentro Mall has **zero** crew in the Master CSV today — the user must supply the new-hire roster (or confirm there are no Xentro hires yet and the device is being pre-provisioned).

### Why this architecture

The canonical "add a new device" pattern is documented in the `/adms-bei-erp` skill under **Adding a New Device (3 files + restart)**:
1. Local Python: add to `DEVICE_TO_STORE` in `hrms/utils/device_mapping.py`
2. Server CSV: append row to `/opt/frappe/bebang-hrms/adms_receiver/sn_mapping_all.csv`
3. Restart: `docker restart adms_receiver_adms-api_1` (or current container name — confirm with `docker ps`)
4. Verify: heartbeat logs show 200 OK (not 403) within ~60 seconds

This sprint follows that exact playbook for both stores, plus crew enrollment via `scripts/enroll.py` from the skill (which uses the safe REST + actual-tab-byte pattern, never shell pipelines).

### Why NOT canonical_scope: in

The canonical store/company gate (`docs/STORE_COMPANY_CANONICAL.md`) governs `tabCompany`, `tabWarehouse`, `tabCustomer`, `tabSupplier` mutations and per-store P&L bindings. This sprint touches **none** of those:

- Both `Ortigas Estancia` and `Xentromall Montalban` already have rows in `hrms/data_seed/store_entity_mapping_2026-04-14.csv` (rows 15 and 50 respectively); this sprint does not add, edit, or remove store entity rows.
- No SI / PO / MR / SE / JE / PE / GL Entry is created.
- No new Frappe Company / Warehouse / Customer / Supplier is created or renamed.
- ADMS database (separate Postgres instance on EC2) and Employee Master CSV are not under the canonical gate.
- New `tabEmployee` rows are out of canonical scope by the gate's own enumeration (the gate names tabCompany/Warehouse/Customer/Supplier explicitly; Employee is excluded).

S228 (parallel sprint) made the same call (`canonical_scope: none`) for the same reasons — pure HR data import.

### Key trade-off decisions

1. **Restart vs no-restart** — server-side allowlist changes do NOT take effect until the API container is restarted. The `/adms-bei-erp` skill says `docker restart adms_receiver_adms-api_1`. **Decision:** include the restart as a manual step under Sam's deploy-password gate (the agent will write the SSM command to `output/s230/manual_steps.md`, but the agent itself does NOT execute `aws ssm send-command` for the restart — that requires deploy password approval per `.claude/hooks/block-deploy-merge.py`).

2. **Estancia 54 PENDING commands** — leave them in the queue or flush them? **Decision:** leave them. They were inserted on 2026-03-30 by an earlier session attempting bulk enrollment. When the physical device finally heartbeats, ADMS will replay them in order. No harm in waiting; flushing risks losing work.

3. **Xentro device serial unknown** — block plan or proceed with TBD? **Decision:** mark as `[UNVERIFIED — requires resolution]` in Phase 0 user-input gate. This is exactly the case the S028 Ground-Truth Lock rule is designed for: don't fabricate a serial; surface the gap explicitly.

4. **Xentro crew unknown** — are there hires yet, or is the device being pre-provisioned? **Decision:** Phase 0 asks Sam to either supply the roster (with names + Bio IDs from `next_bio_id.py`) or confirm "device-only, no crew yet" — both are valid outcomes. If "device-only," W3 (crew enrollment) skips for Xentro and only Estancia's existing 4 crew are reverified for ACK status.

5. **Container name `adms_receiver_adms-db_1` vs `62c9d67fd960_adms_receiver_adms-db_1`** — the skill doc says the former, but on 2026-04-29 the actual container is the latter (recreated with a hash prefix). **Decision:** Phase 0 dynamically discovers the container name via `docker ps --format "{{.Names}}" | grep -i adms`, instead of hardcoding. Same for the API container (`adms_receiver_adms-api_1` may also be hash-prefixed by now).

6. **Enrollment via REST API or Postgres E-string** — both are documented as safe in the skill. **Decision:** REST API (the safer of the two — Python f-string with assert on tab count is the skill's recommended Method 1).

### Known limitations and mitigations

- **Device may never heartbeat.** Pre-existing problem for Estancia (UDP3252900249 has zero attlogs ever). If the physical device at the store isn't powered or isn't pointed at the ADMS cloud server, no amount of allowlist/mapping changes will surface punches. **Mitigation:** Phase 6 verification includes a 10-minute heartbeat-watch window. If no heartbeat by then, plan reports "device server-side ready but physical device offline" as a closeout state, NOT as a failure. Operational follow-up (store visit) is escalated to Ronald Carigal (IT) or Edlice Dela Cruz (Ops).
- **Bio ID collision risk (v2-B3 corrected).** `next_bio_id.py` reads ONLY `data/_FINAL/EMPLOYEE_MASTER.csv` — it does NOT query live Frappe (verified 2026-04-29 by reading the script: imports are only `csv, sys, io, argparse, json`; no `requests`, no `boto3`, no `frappe`). Therefore the agent MUST run an explicit live SSM Frappe query at Phase 4 task 4-2-bis: `SELECT MAX(CAST(attendance_device_id AS UNSIGNED)) FROM tabEmployee WHERE attendance_device_id REGEXP '^9[0-9]{6}$'`. Take the higher of `next_bio_id.py`'s CSV-max-suggestion vs Frappe-max as the true seed. If Frappe max > CSV max + 0, S228 (or another sprint) has live-but-uncommitted inserts — STOP and ask Sam (per MEMORY.md lesson #8 cleanup pattern). **The git-based check in v1 (`git log origin/s228-...`) was wrong** — S228 branch is LOCAL only on origin (verified 2026-04-29 `git branch -r` returned zero matches), so the v1 command would fail with `fatal: unknown revision`.
- **S228 concurrency check (v2-B4 corrected).** Three-part check at Phase 0 task 0-6: (a) `git worktree list | grep s228` — detect parallel local worktree on Sam's machine; (b) live SSM Frappe MAX query (above) — detect live INSERTs not yet committed; (c) `git branch -l | grep s228 && git -C ../BEI-ERP-s228-* status --short` — peek at any local s228 worktree's dirty state. The v1 `git log origin/s228-...` check is REMOVED because the remote ref doesn't exist.
- **Roving employee semantics.** Estancia is currently NOT in any cluster's roving roster. If the 4 Estancia crew need to be cross-enrolled on Cluster 2 secondary devices, that's already in scope of cluster enrollment per Phase 3. If Sam wants Estancia to remain isolated (single-device-only), that's a `cluster_lookup --store ESTANCIA` policy decision in Phase 0 user-input. **Important (v2-B7):** the 54 PRESERVED PENDING commands on UDP3252900249 from 2026-03-30 are mostly **roving-employee enrollments** (Bio 9000014/152/24/784/657 etc., per live ADMS query 2026-04-29 — these match `roving_employees.py` entries). They do NOT enroll the 4 known Estancia crew (9001827/30/32/35). When Phase 5 builds the new batch, the dedup query in Phase 5 task 5-1-pre subtracts already-pending (sn, pin) pairs to prevent duplicates.
- **Cluster 2 actually has 6 devices, not 4 (v2-B6 corrected).** The cluster doc `clusters.md` line 30 lists "Estancia & Greenhills (C2)" under "Stores without devices" — partly stale because Greenhills now has UDP3252900251 in `device_mapping.py:56`, and after this sprint Estancia gets UDP3252900249. So C2 = 4 canonical-spec devices (Megamall UDP3235200631, NEDSA UDP3235200831, CTTM UDP3252100384, Gateway UDP3252900302) + Greenhills UDP3252900251 + Estancia UDP3252900249 = **6 devices**. Plan corrects the math throughout. `clusters.md` line 30 update is in scope of this sprint (one-line markdown edit).

### Source references

- **`/adms-bei-erp` skill** (loaded above) — canonical playbook, table schema, container names, error patterns
- **`hrms/utils/device_mapping.py`** — current **48-device** DEVICE_TO_STORE dict (verified 2026-04-29 by `grep -c "': '" device_mapping.py` = 48; v1 plan said "47" — corrected v2-INFO)
- **`hrms/utils/roving_employees.py`** — 27-row roving registry (no Estancia entries as of 2026-04-29 read)
- **`hrms/data_seed/store_entity_mapping_2026-04-14.csv`** — confirms `Ortigas Estancia` (row 15) + `Xentromall Montalban` (row 50) as canonical store entities
- **`data/_FINAL/EMPLOYEE_MASTER.csv`** — 4 active Estancia crew with Bio IDs 9001827/30/32/35; zero Xentro Mall crew (`store_location` field never matches `XENTRO*` or `XENTROMALL*`)
- **`.claude/skills/adms-bei-erp/references/clusters.md`** line 30 — "Stores without devices: The Grid (C1), Estancia & Greenhills (C2), Xentro Mall (C5), Ever Commonwealth (C7)" (Greenhills now has device UDP3252900251; Estancia is in server allowlist but no local mapping; Xentro still pending)
- **Live ADMS database query 2026-04-29** — confirmed UDP3252900249 has 54 PENDING commands, 0 attlog_raw rows, 0 callbacks, 0 user_registry rows
- **Live `sn_mapping_all.csv` 2026-04-29** — confirmed `UDP3252900249,ESTANCIA` row exists at end of file
- **Live `docker ps` 2026-04-29** — actual container names: `adms_receiver_adms-api_1`, `adms_receiver_adms-nginx_1`, `62c9d67fd960_adms_receiver_adms-db_1` (db container has hash prefix)

---

## Requirements Regression Checklist

The executing agent MUST verify each of the following before declaring this sprint complete. These are yes/no assertions checked against the agent's own work.

- [ ] Did the agent run `git worktree add F:/Dropbox/Projects/BEI-ERP-s230-xentro-estancia-device-enrollment -B s230-xentro-estancia-device-enrollment origin/production` and execute all work inside that worktree, NOT inside `F:/Dropbox/Projects/BEI-ERP`?
- [ ] Is the new branch `s230-xentro-estancia-device-enrollment`, never committing to production?
- [ ] Did the agent obtain the **Xentro Mall device serial number** from Sam in Phase 0 before any allowlist/mapping mutation?
- [ ] Did the agent obtain or confirm the **Xentro Mall crew roster** from Sam in Phase 0 (or confirm "device-only, no crew yet" mode)?
- [ ] Did the agent capture pre-state snapshots (`tmp/s230/sn_mapping_all_pre_change.csv` and `tmp/s230/employee_master_pre_change.csv`) BEFORE any mutation?
- [ ] Did the agent dynamically discover the live container names via `docker ps --format` instead of hardcoding `adms_receiver_adms-db_1`?
- [ ] Are BOTH `UDP3252900249 → ORTIGAS ESTANCIA` and `<Xentro serial> → XENTRO MONTALBAN` (v2-B1: NOT "XENTROMALL MONTALBAN" — matches S228 tabBranch row) added to `hrms/utils/device_mapping.py` (canonical-cased store names, alphabetically-sorted insert location)?
- [ ] Are BOTH device entries appended to `/opt/frappe/bebang-hrms/adms_receiver/sn_mapping_all.csv` (with the Xentro entry following the same row format as the existing Estancia entry)?
- [ ] Did the agent write the API-container restart command to `output/s230/manual_steps.md` and STOP for Sam's manual deploy-password execution, instead of running `aws ssm send-command` itself?
- [ ] Are all 4 known active Estancia crew (Bio IDs 9001827, 9001830, 9001832, 9001835) re-verified via `audit_employees.py` against the Master CSV BEFORE any enrollment push?
- [ ] Are any new Xentro Mall crew (per Phase 0 input) added to `data/_FINAL/EMPLOYEE_MASTER.csv` AND `data/_FINAL/CHANGE_LOG.csv` AND the Google Sheet `1iFDbvaOg0-kbNLFJ5WuYCFOw2nmlyUkU42MbmPSVmMg` AND Frappe `tabEmployee` (via `/frappe-bulk-edits`) — all four targets, in the same execution batch?
- [ ] Is each ADMS USERINFO command using the safe REST API pattern with Python f-string and `assert command_text.count("\t") >= 2` (skill Method 1)?
- [ ] Are no shell-pipeline insertions used (skill Method "regular SQL quotes through shell" is forbidden)?
- [ ] Is no `C:serial:` prefix included in any `command_text` (the receiver adds it automatically)?
- [ ] Did the agent run `validate_employee_bio_id()` (NOT a hallucinated `validate_bio_id_and_name()` — the real function name verified in S228) for every Bio ID before push?
- [ ] Did Phase 5 cross-check whether S228 is concurrently in flight on `data/_FINAL/EMPLOYEE_MASTER.csv` and serialize if so?
- [ ] Does the Phase 6 heartbeat-watch include both Estancia (UDP3252900249) and the Xentro serial, with a 10-minute deadline before flagging "device offline"?
- [ ] Are all evidence files routed correctly: SUMMARY/DEFECTS/verification → `output/s230/` (committed); SSM responses + pre-change snapshots → `tmp/s230/` (gitignored)?
- [ ] Does the closeout phase update `docs/plans/2026-04-29-sprint-230-xentro-estancia-device-enrollment.md` (status PLANNED → COMPLETED + completed_date + execution_summary) AND `docs/plans/SPRINT_REGISTRY.md` row (status → COMPLETED with PR ref) AND commit both via `git add -f`?
- [ ] Was the disposable worktree `F:/Dropbox/Projects/BEI-ERP-s230-xentro-estancia-device-enrollment` removed at closeout via `git worktree remove`?
- [ ] Did the agent add Sentry observability context to any new/modified `@frappe.whitelist()` endpoints? **(N/A for this sprint — no whitelisted endpoints are touched; if that changes mid-execution, agent must add `set_backend_observability_context()` per `.claude/rules/sentry-observability.md`.)**

---

## Phase Budget Contract (v2 amended)

- phase_unit_budget:
  - `Phase 0` (Boot + Worktree + User-Input Gate + S228 concurrency check) → **6 units** (v1: 5)
  - `Phase 1` (Server Allowlist Update + 3 Restart Commands Handoff) → **5 units** (v1: 4)
  - `Phase 2` (Local Python Mapping Update + clusters.md doc fix) → `3 units`
  - `Phase 3` (Cluster Membership Verification — corrected for 6-device C2/C5) → `3 units`
  - `Phase 4` (tabBranch precheck + Frappe MAX cross-check + 4-target writes with atomicity) → **12 units** (v1: 8)
  - `Phase 5` (ADMS Enrollment with dedup + verify.py fix) → **8 units** (v1: 7)
  - `Phase 6` (Verification + Heartbeat Watch with precise verdicts) → `5 units`
  - `Phase 7` (Closeout: rebase + consolidated `git add -f` + PR + worktree removal) → **5 units** (v1: 3)
- total_units: **47** (v1: 38; +9 units from v2 amendments)
- hard_limit: `15 units per phase`
- preferred_split_threshold: `12 units per phase`
- Phase 4 sits at the preferred-split threshold (12) but stays single-phase because all 7 sub-tasks are sequential atomic-guard members (rollback contract requires they run together).
- normalization_rule: any amendment that splits a phase or moves units across phases must update this Phase Budget Contract and the operative phase tables in the same edit.

---

## Worktree & Branch Setup

- `worktree_path`: `F:/Dropbox/Projects/BEI-ERP-s230-xentro-estancia-device-enrollment`
- `branch`: `s230-xentro-estancia-device-enrollment` (off `origin/production`)
- `repo`: `hrms` only (bei-tasks not touched)
- `workflow`: per `.claude/rules/worktree-isolation.md` — work in disposable worktree, remove at closeout

```bash
# Phase 0 boot — exact commands
cd F:/Dropbox/Projects/BEI-ERP && git fetch origin --prune
git worktree add F:/Dropbox/Projects/BEI-ERP-s230-xentro-estancia-device-enrollment \
    -B s230-xentro-estancia-device-enrollment origin/production
cd F:/Dropbox/Projects/BEI-ERP-s230-xentro-estancia-device-enrollment

# Confirm CWD
pwd  # must be …/BEI-ERP-s230-xentro-estancia-device-enrollment

# Confirm branch
git branch --show-current  # must be s230-xentro-estancia-device-enrollment

# Verify clean worktree
git status --short  # must be empty

# Closeout (Phase 7)
git status --short  # must be empty after final commit
cd F:/Dropbox/Projects/BEI-ERP
git worktree remove F:/Dropbox/Projects/BEI-ERP-s230-xentro-estancia-device-enrollment
```

---

## Agent Boot Sequence

1. Read this plan fully.
2. Read `.claude/rules/worktree-isolation.md` (worktree pattern).
3. Read `.claude/skills/adms-bei-erp/SKILL.md` (this is the operational skill — already loaded if `/adms-bei-erp` was invoked).
4. Read `.claude/skills/adms-bei-erp/references/clusters.md` (cluster mapping — Estancia=C2, Xentro=C5).
5. Read `data/_FINAL/EMPLOYEE_MASTER.csv` (verify 4 active Estancia rows, 0 Xentro rows).
6. Read `hrms/utils/device_mapping.py` (verify 47-device dict, no Estancia, no Xentro).
7. Read `hrms/utils/roving_employees.py` (verify roving roster — no current Estancia/Xentro entries).
8. Spawn the worktree (commands above) and `cd` into it. NEVER work in `F:/Dropbox/Projects/BEI-ERP` itself.
9. Read `docs/plans/SPRINT_REGISTRY.md` to confirm S230 row is registered with `branch=s230-xentro-estancia-device-enrollment`.
10. Cross-check S228 state: `git branch -a | grep s228` and `git log origin/production -- data/_FINAL/EMPLOYEE_MASTER.csv | head -5`. If S228 has uncommitted in-flight changes to the Master CSV, STOP and ask Sam.
11. Begin Phase 0 user-input gate.

---

## Execution Authority

This sprint is intended for autonomous end-to-end execution **except** for two human-input gates:

1. **Phase 0** — Sam supplies the Xentro Mall device serial number AND confirms the Xentro Mall crew roster status (either provides a roster or confirms "device-only, no crew yet").
2. **Phase 1** — the agent writes the SSM restart command to `output/s230/manual_steps.md` but does NOT execute `aws ssm send-command` (which requires deploy password). Sam executes the restart.

Outside of these two gates, the agent runs continuously through Phases 2–7. Do not stop for progress-only updates. Only pause for items in the Autonomous Execution Contract `stop_only_for` section below.

---

## Autonomous Execution Contract

- completion_condition:
  - all 7 phases green
  - all evidence files written to declared paths (`output/s230/` for committed, `tmp/s230/` for transient)
  - PR opened on `Bebang-Enterprise-Inc/hrms` from `s230-xentro-estancia-device-enrollment` → `production`
  - PR number recorded in `docs/plans/SPRINT_REGISTRY.md` S230 row
  - plan YAML status changed `PLANNED` → `COMPLETED` with `completed_date` and `execution_summary` filled
  - worktree removed
- stop_only_for:
  - Phase 0 missing Xentro device serial OR missing Xentro crew decision (device-only vs roster-supplied)
  - Phase 4 detects S228 concurrent in-flight changes to `data/_FINAL/EMPLOYEE_MASTER.csv`
  - Phase 5 enrollment commands return Return < 0 (i.e., device rejected the command — possible auth issue)
  - Bio ID collision detected at insert time
  - SSM call returns auth/permission failure outside of the documented restart-gate
  - Phase 6 heartbeat watch finds the device 200-ing but rejecting USERINFO commands (suggests device hardware problem)
  - any `[UNVERIFIED — requires resolution]` value in operator-facing output
- continue_without_pause_through:
  - audit
  - execute (Phases 2–6)
  - pr_creation
  - closeout
- blocker_policy:
  - programmatic error → fix and continue
  - SSM container-name mismatch → re-run `docker ps`, update agent's local cache, continue
  - 3× failed enrollment ACK on the same Bio ID → grounded research (verify Bio ID in `tabEmployee`, verify device cluster membership), then continue
  - business-data/policy decision (e.g., should Estancia crew be roving?) → pause
- signoff_authority: `single-owner` (Sam)
- approver_of_record: `Sam Karazi (CEO)`
- canonical_closeout_artifacts:
  - `output/s230/SUMMARY.md`
  - `output/s230/DEFECTS.md`
  - `output/s230/verification/server_allowlist_after.txt`
  - `output/s230/verification/local_mapping_after.diff`
  - `output/s230/verification/employee_master_after.csv_diff`
  - `output/s230/verification/google_sheet_after.json`
  - `output/s230/verification/adms_enrollment_acks.json`
  - `output/s230/verification/state_after.json`
  - `output/s230/manual_steps.md` (the SSM restart command for Sam)
  - `data/_FINAL/CHANGE_LOG.csv` (rows added)
  - `docs/plans/2026-04-29-sprint-230-xentro-estancia-device-enrollment.md` (this file, status → COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (S230 row status → COMPLETED with PR ref)

---

## Test Data Seeding Contract

**N/A** — this sprint does NOT include L3 scenarios that depend on production records existing in advance.

The verification work in Phase 6 is **read-only against live data**:
- `audit_employees.py 9001827 9001830 9001832 9001835 <new_bio_ids>` — read-only Master CSV check
- `verify.py --device UDP3252900249 --device <xentro_serial>` — read-only ACK status check + INFO query
- `cluster_lookup.py --store "ORTIGAS ESTANCIA"` and `cluster_lookup.py --store "XENTRO MONTALBAN"` — read-only static lookup (v2-B1: store name with space, no underscore, no "MALL")
- SSM Postgres queries — read-only (`SELECT` only, no `INSERT`/`UPDATE`/`DELETE`)

The mutations performed (USERINFO enrollment commands; Master CSV row appends; sn_mapping_all row appends; tabEmployee inserts; Google Sheet row appends) are the **subject** of the sprint, not test fixtures. They are real, persistent, audited via `data/_FINAL/CHANGE_LOG.csv`, and not torn down at closeout.

If Phase 6 verification fails (e.g., a USERINFO command never ACKs because the device is offline), the closeout writes a `[DEFECT]` row in `output/s230/DEFECTS.md` and the sprint completes with `partial` status — NO test data is "torn down" because there is no test data, only real production state.

---

## L3 Workflow Scenarios

This sprint does NOT have UI-clicking workflow scenarios. The "scenarios" here are **integration-level read probes** against live ADMS / Frappe / Google Sheet:

| User | Action | Expected Outcome | Failure Means |
|------|--------|------------------|---------------|
| agent (read-only Postgres via SSM) | `SELECT alias FROM (SELECT 'ESTANCIA' alias UNION SELECT 'XENTRO_MONTALBAN') a WHERE alias IN (SELECT split_part(line, ',', 2) FROM regexp_split_to_table((SELECT pg_read_file('/opt/frappe/bebang-hrms/adms_receiver/sn_mapping_all.csv')), E'\\n') line);` (or simpler: `cat sn_mapping_all.csv \| grep -E "ESTANCIA\|XENTRO"`) | Both rows present after Phase 1 | Server allowlist update did not land — restart not executed or row not appended |
| agent (Python import) | `from hrms.utils.device_mapping import get_store_name; assert get_store_name('UDP3252900249') == 'ORTIGAS ESTANCIA'; assert get_store_name(XENTRO_SERIAL) == 'XENTRO MONTALBAN'` (v2-B1) | Both calls return without raising `KeyError` | Local mapping update did not land or wrong store-name string |
| agent (read-only Postgres via SSM) | `SELECT pin FROM adms_user_registry WHERE sn IN ('UDP3252900249', '<xentro_serial>') ORDER BY pin;` after Phase 5 + ≥10 min wait | New rows appear matching the enrolled Bio IDs (only if device is online) | If device still offline after 10 min, sprint reports "device server-side ready but offline" — NOT a failure of this sprint |
| agent (read-only Postgres via SSM) | `SELECT bio_id, name FROM adms_attlog_raw WHERE sn = 'UDP3252900249' AND event_time > NOW() - INTERVAL '10 minutes';` | Zero rows OK — punches require physical fingerprint scan after enrollment lands. Sprint succeeds whether or not anyone has punched yet | (this row is informational, not a gate) |
| agent (read-only API) | `GET https://hq.bebang.ph/api/method/frappe.client.get_list?doctype=Employee&filters=[["attendance_device_id","in",["9001827","9001830","9001832","9001835",<new_xentro_bio_ids>]]]&fields=["name","employee_name","attendance_device_id"]` | All Bio IDs return Frappe Employee records with matching names | Insert into `tabEmployee` did not land for one or more rows |
| agent (read-only Google Sheets API) | Read range `Employee Master!A:Z` from sheet `1iFDbvaOg0-kbNLFJ5WuYCFOw2nmlyUkU42MbmPSVmMg`; assert all enrolled Bio IDs are present | All Bio IDs present in the sheet | Google Sheet sync did not land — common cause: OAuth token expired |

These probes run end-to-end in Phase 6 and write to `output/s230/verification/state_after.json` as JSON-formatted assertion results. No browser automation, no Playwright.

---

## Ground-Truth Lock

- **evidence_sources:**
  - `hrms/utils/device_mapping.py` (lines 8–57) → 47-device DEVICE_TO_STORE dict baseline; the `KeyError` path that breaks if Estancia or Xentro punches arrive without a mapping entry
  - `data/_FINAL/EMPLOYEE_MASTER.csv` rows where `store_location=ESTANCIA` → 4 active crew (Bio IDs 9001827, 9001830, 9001832, 9001835); awk-counted 2026-04-29
  - `hrms/data_seed/store_entity_mapping_2026-04-14.csv` rows 15 (`Ortigas Estancia,BB Estancia Food Corp.,Managed Franchise,,BKI_TO_STORE_INTERCOMPANY,active`) and 50 (`Xentromall Montalban,Perpetual Food Corp.,Managed Franchise,,,`) → confirms canonical store entity rows already exist
  - `.claude/skills/adms-bei-erp/references/clusters.md` line 30 → "Stores without devices: …, Estancia & Greenhills (C2), Xentro Mall (C5), …"
  - Live SSM Postgres query 2026-04-29 against `62c9d67fd960_adms_receiver_adms-db_1` → confirmed UDP3252900249 has 54 PENDING `adms_device_cmd` rows, 0 `adms_attlog_raw` rows, 0 `adms_device_cmd_callback` rows
  - Live SSM file read 2026-04-29 → confirmed `UDP3252900249,ESTANCIA` row exists at end of `sn_mapping_all.csv`
  - Live SSM `docker ps` 2026-04-29 → actual container names: `adms_receiver_adms-api_1`, `adms_receiver_adms-nginx_1`, `62c9d67fd960_adms_receiver_adms-db_1`
- **count_method:**
  - metric: `Estancia active crew in Master CSV`
  - basis: `awk -F',' '$14=="ESTANCIA" && $10=="Active" {count++}' data/_FINAL/EMPLOYEE_MASTER.csv`
  - method: 2026-04-29 ran the awk; result was 4
  - metric: `Xentro Mall active crew in Master CSV`
  - basis: Python `csv` parsing with `row['store_location'] == 'XENTRO MONTALBAN'` (v2-B1; uppercase, space-separated, no "MALL"; CSV column 13 per real header, NOT awk-shifted col 14) — 0 rows pre-sprint, N rows post-sprint where N = Sam-supplied Xentro crew count
- **authoritative_sections:**
  - All numbered phases below are authoritative for execution.
  - Design Rationale and Requirements Regression Checklist are also authoritative.
  - This Ground-Truth Lock section is the source for any factual claim cited in execution.
- **normalization_required:**
  - if Phase 0 user input changes the Xentro serial or roster, ALL subsequent phase tasks that reference those values must be normalized in the same edit.
  - if Phase 4 Bio ID assignment differs from the auto-suggested next-available range, the Verification scenario rows must be updated with actual Bio IDs.
- **unresolved_value_policy:**
  - `<xentro_serial>` and `<new_xentro_bio_ids>` placeholders MUST be replaced with concrete values in all task descriptions before Phase 1 begins. If Sam does not provide them by Phase 0, the agent stops and the plan reports "Phase 0 blocked: missing Xentro inputs."
- **normalization_artifacts:**
  - `tmp/s230/PROVENANCE.md` (Phase 0 captures Sam's exact answers)
  - `output/s230/SUMMARY.md` (final reconciled state)

---

## Anti-Rewind / Concurrent-Run Protection Contract

- **ownership_matrix:**
  - artifact: `output/s230/SURFACE_OWNERSHIP_MATRIX.csv`
  - rule: this sprint exclusively owns `hrms/utils/device_mapping.py`. If S228 or any other concurrent sprint touches it, the agent stops at Phase 2 and asks.
- **protected_surfaces:**
  - artifact: `output/s230/PROTECTED_SURFACE_REGISTRY.csv`
  - rule: do not modify `hrms/utils/roving_employees.py`, `hrms/utils/adms_validation.py`, or any other adjacent shipped utility. If a roving change for Estancia or Xentro is needed, that's a separate follow-up sprint, not S230.
- **remote_truth_baseline:**
  - artifact: `output/s230/REMOTE_TRUTH_BASELINE.json`
  - fields:
    - `repo`: `Bebang-Enterprise-Inc/hrms`
    - `release_branch`: `production`
    - `release_head_sha`: capture in Phase 0 via `git rev-parse origin/production`
    - `live_evidence_basis`: `hrms/utils/device_mapping.py` SHA + `sn_mapping_all.csv` SHA (read via SSM)
- **touched_file_routing:**
  - artifact: `output/s230/TOUCHED_FILE_ROUTING.csv`
  - files: `hrms/utils/device_mapping.py`, `data/_FINAL/EMPLOYEE_MASTER.csv`, `data/_FINAL/CHANGE_LOG.csv`, `/opt/frappe/bebang-hrms/adms_receiver/sn_mapping_all.csv` (server-side, not in repo)
  - sentinels: post-edit `python -c "from hrms.utils.device_mapping import get_store_name; print(get_store_name('UDP3252900249'))"` must print `ORTIGAS ESTANCIA` without raising
- **active_run_coordination:**
  - rule: before Phase 4, run `git fetch origin --prune` and `git log origin/production..HEAD -- data/_FINAL/EMPLOYEE_MASTER.csv` to detect S228 commits since the worktree was spawned. If non-empty, rebase first.
- **pretouch_backup:**
  - artifact: `tmp/s230/sn_mapping_all_pre_change.csv` and `tmp/s230/employee_master_pre_change.csv`
  - rule: snapshot BEFORE Phase 1 and Phase 4 mutations. Required for rollback if Phase 6 verification reveals a defect.
- **supersession_truth:**
  - rule: this sprint does NOT supersede any prior packet. The 54 PENDING commands on UDP3252900249 from 2026-03-30 are PRESERVED, not flushed.

---

## Phase 0 — Boot, Worktree, and User-Input Gate (6 units, was 5)

**Goal:** spawn the worktree (handling already-exists case), capture pre-state, ask Sam for the Xentro serial + crew roster decision + branch-name confirmation, run live concurrency check against Frappe, write provenance.

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|------|----------------------------|
| 0-1 | Read this plan, the worktree-isolation rule, the `/adms-bei-erp` skill, and `clusters.md`. | (read-only) |
| 0-1.5 | **(v2-W2)** Check if worktree already exists at `F:/Dropbox/Projects/BEI-ERP-s230-xentro-estancia-device-enrollment`. Run `git -C F:/Dropbox/Projects/BEI-ERP worktree list \| grep s230`. If found, run `git -C F:/Dropbox/Projects/BEI-ERP-s230-xentro-estancia-device-enrollment status --short`. **(a)** Clean → switch into it, rebase on `origin/production`, continue at task 0-3. **(b)** Dirty with S230 scratch → commit as `chore(S230): scratch artifacts from prior session` first, rebase, continue. **(c)** Dirty with unrelated files → STOP and ask Sam (per `.claude/rules/worktree-isolation.md` step 3). | (no file change; logs the decision) |
| 0-2 | Spawn worktree (only if 0-1.5 reported "not found"): `cd F:/Dropbox/Projects/BEI-ERP && git fetch origin --prune && git worktree add F:/Dropbox/Projects/BEI-ERP-s230-xentro-estancia-device-enrollment -B s230-xentro-estancia-device-enrollment origin/production && cd F:/Dropbox/Projects/BEI-ERP-s230-xentro-estancia-device-enrollment` | `git branch --show-current` returns `s230-xentro-estancia-device-enrollment` |
| 0-3 | Capture remote-truth baseline. Run `git rev-parse origin/production` and write the SHA to `output/s230/REMOTE_TRUTH_BASELINE.json`. Also write the current SHA of `hrms/utils/device_mapping.py` (via `git ls-files -s`). | MUST_CONTAIN: `release_head_sha` field with a 40-char hex |
| 0-4 | **HARD BLOCKER — User-Input Gate.** Ask Sam four questions: (1) "What is the Xentro Mall device serial number? (Format: `UDP##########` or `CNYG##########`.)" (2) "Are there any Xentro Mall employees to enroll, or is this device-only / no crew yet? If yes: provide names + Frappe-confirmed Bio IDs (or say 'use next-available'). Source: New Hires Masterlist or direct list." (3) **(v2-B1)** "Confirm Xentro branch-name string: `XENTRO MONTALBAN` (matches S228 `tmp/insert_13_employees.py` and the existing tabBranch row created by S228) — yes/no? If no, supply the canonical name." (4) **(v2-B6)** "Single-device enrollment for Estancia/Xentro crew, or full-cluster cross-enrollment (Estancia 4 crew × 6 C2 devices = 24 commands; Xentro N crew × 6 C5 devices = 6N commands)?" Wait for all four answers before proceeding. Capture verbatim in `tmp/s230/PROVENANCE.md` (timestamped). | MUST_MODIFY: `tmp/s230/PROVENANCE.md` MUST_CONTAIN: `xentro_serial:`, `xentro_crew_mode: roster\|device_only`, `xentro_branch_name:` (default `XENTRO MONTALBAN`), `enrollment_mode: single_device\|cross_cluster` |
| 0-5 | **(v2-B10 read-only)** Pre-state snapshots: `cp data/_FINAL/EMPLOYEE_MASTER.csv tmp/s230/employee_master_pre_change.csv` (local file) and SSM `cat /opt/frappe/bebang-hrms/adms_receiver/sn_mapping_all.csv > tmp/s230/sn_mapping_all_pre_change.csv` (read-only — agent autonomous with password `# 2289454` per Phase 1 SSM-Autonomy-Boundary policy below). | Both files exist with non-zero size |
| 0-6 | **(v2-B4 corrected)** Three-part S228 concurrency check: **(a)** `git -C F:/Dropbox/Projects/BEI-ERP worktree list \| grep s228` — detect parallel local worktree on Sam's machine. If found, peek at its state via `git -C <s228-worktree> status --short` and `git -C <s228-worktree> log --oneline HEAD ^origin/production`. **(b)** Run live SSM Frappe MAX query: `aws ssm send-command --instance-ids i-026b7477d27bd46d6 --document-name AWS-RunShellScript --parameters 'commands=["sudo docker exec -i $(docker ps --filter name=frappe_backend --format {{.Names}} \| head -1) bash -lc \"cd /home/frappe/frappe-bench && bench --site hq.bebang.ph mariadb -e \\\"SELECT MAX(CAST(attendance_device_id AS UNSIGNED)) AS max_bio FROM tabEmployee WHERE attendance_device_id REGEXP \\\\\\\"^9[0-9]{6}$\\\\\\\";\\\"\"]' --region ap-southeast-1 # 2289454`. Write JSON result to `output/s230/verification/frappe_max_bio_id.json`. **(c)** Compare Frappe MAX vs Master CSV MAX (run `python .claude/skills/adms-bei-erp/scripts/next_bio_id.py --json --count 1` to get CSV MAX). If `frappe_max > csv_max`, S228 (or another sprint) has live-but-uncommitted INSERTs — STOP and ask Sam. **DELETE the v1 `git log origin/s228-...` command** — that ref does NOT exist (verified 2026-04-29). | MUST_MODIFY: `output/s230/verification/frappe_max_bio_id.json`. MUST_CONTAIN: `frappe_max:`, `csv_max:`, `safe_to_proceed: true\|false` |
| 0-7 | Normalize the plan body: replace `<xentro_serial>`, `<xentro_branch_name>`, and `<new_xentro_bio_ids>` placeholders with the actual values from Phase 0 answers. Commit normalization edit to this plan file. Use `git add -f` (docs/plans/ is gitignored per .gitignore line 34). | The plan file (post-Phase-0) MUST_CONTAIN the actual Xentro serial AND actual Xentro branch-name string in all subsequent task bodies, NOT the literal placeholder strings |

**Phase 0 verification script:** `output/s230/verify_phase0.py` — checks that (a) `tmp/s230/PROVENANCE.md` has all four required keys (`xentro_serial`, `xentro_crew_mode`, `xentro_branch_name`, `enrollment_mode`), (b) `output/s230/REMOTE_TRUTH_BASELINE.json` has 40-char `release_head_sha`, (c) `output/s230/verification/frappe_max_bio_id.json` has `safe_to_proceed: true`, (d) `git grep -n '<xentro_serial>\|<xentro_branch_name>\|<new_xentro_bio_ids>' docs/plans/2026-04-29-sprint-230-*.md` returns ZERO matches (placeholders fully normalized).

---

## Phase 1 — Server Allowlist Update + Container Restart Handoff (5 units, was 4)

**(v2-B10) SSM Autonomy Boundary policy** (governs all SSM operations across this plan):

| Operation type | Examples | Who executes | Notes |
|---|---|---|---|
| **READ-ONLY (agent-autonomous)** | `cat`, `grep`, `tail`, `SELECT`, `docker ps`, `docker logs --tail` | Agent uses password `# 2289454` | Phase 0 task 0-5/0-6, Phase 1 task 1-1/1-3, Phase 5 task 5-3/5-4, Phase 6 probes |
| **AGENT-MUTATION (agent-autonomous, password-gated)** | `tee -a`, `INSERT INTO adms_device_cmd`, `INSERT INTO tabBranch/tabEmployee` via `/frappe-bulk-edits` | Agent uses password `# 2289454` | Phase 1 task 1-2 (allowlist row append), Phase 4 task 4-0/4-4 (Frappe INSERTs), Phase 5 task 5-2 (USERINFO commands). All MUST be paired with pre-state snapshot + post-state verification. |
| **HUMAN-REQUIRED (Sam executes)** | `docker restart` (any container), `git push --force`, anything destructive on shared infra | Sam — agent writes to `output/s230/manual_steps.md` and STOPS | Phase 1 task 1-4 (API restart), Phase 7-bis (Frappe backend restart per v2-W9) |

**Goal:** add the Xentro serial to `sn_mapping_all.csv` on EC2, write the BOTH restart commands (API container + Frappe backend container) to `manual_steps.md` for Sam.

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|------|----------------------------|
| 1-1 | Verify Estancia row already exists (READ-ONLY): SSM `grep "ESTANCIA" /opt/frappe/bebang-hrms/adms_receiver/sn_mapping_all.csv`. Expected: `UDP3252900249,ESTANCIA`. If absent, append it (it's confirmed present as of 2026-04-29 verification, but re-check). | SSM stdout MUST_CONTAIN `UDP3252900249,ESTANCIA` |
| 1-2 | **(AGENT-MUTATION)** Append Xentro row: SSM `echo "<xentro_serial>,XENTRO_MONTALBAN" \| sudo tee -a /opt/frappe/bebang-hrms/adms_receiver/sn_mapping_all.csv` (row format `SERIAL,UNDERSCORED_STORE_NAME` matching existing `UDP3252900249,ESTANCIA` precedent). Aws ssm command requires deploy password `# 2289454`. **Note (v2-B1):** the underscored token `XENTRO_MONTALBAN` is the server allowlist alias; the local mapping uses `'XENTRO MONTALBAN'` (space) and Frappe `tabBranch.name` is `'XENTRO MONTALBAN'` (space) per S228 precedent. Three different formats for three different consumers; agent does NOT confuse them. | SSM stdout for `cat sn_mapping_all.csv \| tail -3` MUST_CONTAIN: `<xentro_serial>,XENTRO_MONTALBAN` |
| 1-3 | Capture post-state (READ-ONLY): SSM `cat /opt/frappe/bebang-hrms/adms_receiver/sn_mapping_all.csv > tmp/s230/sn_mapping_all_post_change.csv`. Diff vs pre-change, write to `output/s230/verification/server_allowlist_after.txt`. | MUST_MODIFY: `output/s230/verification/server_allowlist_after.txt` MUST_CONTAIN both Estancia and Xentro rows |
| 1-4 | **(HUMAN-REQUIRED — agent writes-and-stops)** Write BOTH restart commands to `output/s230/manual_steps.md`: <br>**Restart 1: API container (immediate effect for the allowlist change)** <br>```bash<br>aws ssm send-command --instance-ids i-026b7477d27bd46d6 --document-name AWS-RunShellScript --parameters 'commands=["sudo docker restart adms_receiver_adms-api_1"]' --region ap-southeast-1 # 2289454<br>```<br>**Restart 2: Verification probe (within 60 sec) — also in manual_steps.md** <br>```bash<br>aws ssm send-command --instance-ids i-026b7477d27bd46d6 --document-name AWS-RunShellScript --parameters 'commands=["sleep 30; docker logs adms_receiver_adms-api_1 --tail 30 \| grep -E \"200\|listening\""]' --region ap-southeast-1 # 2289454<br>```<br>**Restart 3 (v2-W9): Frappe backend (so `device_mapping.py` change picks up after PR merge + deploy)** — write but mark `RUN AFTER PR MERGE+DEPLOY, NOT NOW`:<br>```bash<br># Run AFTER deploy completes — not now. Discover live container name first.<br>aws ssm send-command --instance-ids i-026b7477d27bd46d6 --document-name AWS-RunShellScript --parameters 'commands=["FB=$(docker ps --filter name=frappe_backend --format {{.Names}} \| head -1); echo Restarting $FB; sudo docker restart $FB"]' --region ap-southeast-1 # 2289454<br>```<br>**Do NOT execute any of these yourself.** | MUST_MODIFY: `output/s230/manual_steps.md` MUST_CONTAIN three labeled sections: `## Restart 1: API container (run after PR merge+deploy is OK; can also run right now to flush 54 PENDING)`, `## Restart 2: Verification probe`, `## Restart 3: Frappe backend (run AFTER PR merge+deploy)`. |

**Phase 1 verification script:** `output/s230/verify_phase1.py` — checks that (a) the Xentro serial appears in `tmp/s230/sn_mapping_all_post_change.csv` AND not in `tmp/s230/sn_mapping_all_pre_change.csv` (real append), (b) `output/s230/manual_steps.md` contains all three restart sections (`Restart 1`, `Restart 2`, `Restart 3`).

---

## Phase 2 — Local Python Mapping Update (3 units)

**Goal:** add both devices to `hrms/utils/device_mapping.py` (currently 48 entries, becoming 50).

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|------|----------------------------|
| 2-1 | Edit `hrms/utils/device_mapping.py`. Insert two new entries into `DEVICE_TO_STORE` in alphabetical order by serial number. Use exactly: `'UDP3252900249': 'ORTIGAS ESTANCIA',` and `'<xentro_serial>': 'XENTRO MONTALBAN',` (**v2-B1: name is `'XENTRO MONTALBAN'` with a space, matching S228's `tabBranch` row, NOT `'XENTROMALL MONTALBAN'`**). **Store name MUST be uppercase, matching the existing pattern (e.g., 'BRITTANY OFFICE', 'GREENHILLS').** | MUST_MODIFY: `hrms/utils/device_mapping.py` MUST_CONTAIN: `'UDP3252900249': 'ORTIGAS ESTANCIA'` AND `<xentro_serial>': 'XENTRO MONTALBAN'` |
| 2-2 | Smoke test: `cd <worktree> && python -c "from hrms.utils.device_mapping import get_store_name, DEVICE_TO_STORE; assert len(DEVICE_TO_STORE) == 50; print(get_store_name('UDP3252900249')); print(get_store_name('<xentro_serial>'))"`. Both prints must succeed without `KeyError`, and the dict count assertion must pass (48 + 2 new = 50). | stdout MUST_CONTAIN: `ORTIGAS ESTANCIA` AND `XENTRO MONTALBAN` (NO trailing "MALL") |
| 2-3 | Capture diff: `git diff hrms/utils/device_mapping.py > output/s230/verification/local_mapping_after.diff`. Commit the file with message `feat(S230): add Xentro Mall + Estancia to device-to-store mapping`. (`hrms/` is tracked — no `-f` needed.) | MUST_MODIFY: `output/s230/verification/local_mapping_after.diff` non-empty |
| 2-4 | **(v2-B6 doc fix)** Update `.claude/skills/adms-bei-erp/references/clusters.md` line 30 in this same sprint. Old: `**Stores without devices:** The Grid (C1), Estancia & Greenhills (C2), Xentro Mall (C5), Ever Commonwealth (C7)`. New: `**Stores without devices:** The Grid (C1), Ever Commonwealth (C7)` (Estancia and Xentro Mall now have devices per this sprint; Greenhills already has UDP3252900251 per `device_mapping.py:56`). Also update the C2 device list (lines 42-47) to ADD `D5  UDP3252900249   Ortigas Estancia` and `D6  UDP3252900251   Ortigas Greenhills`; update the C5 device list (lines 61-66) to ADD `D6  <xentro_serial>   Xentro Mall Montalban`. Use `git add -f` because `.claude/` is gitignored per `.gitignore` line 32. | MUST_MODIFY: `.claude/skills/adms-bei-erp/references/clusters.md` MUST_CONTAIN: `UDP3252900249   Ortigas Estancia` AND `UDP3252900251   Ortigas Greenhills` AND the Xentro serial+store row in C5 |

**Phase 2 verification script:** `output/s230/verify_phase2.py` — runs `python -c "from hrms.utils.device_mapping import DEVICE_TO_STORE; assert len(DEVICE_TO_STORE) == 50, f'expected 50, got {len(DEVICE_TO_STORE)}'; assert DEVICE_TO_STORE['UDP3252900249'] == 'ORTIGAS ESTANCIA'; xs = open('tmp/s230/PROVENANCE.md').read(); import re; m = re.search(r'xentro_serial:\\s*(\\S+)', xs); assert m, 'xentro_serial missing from PROVENANCE.md'; serial = m.group(1).strip(); assert DEVICE_TO_STORE[serial] == 'XENTRO MONTALBAN', f'wrong name {DEVICE_TO_STORE[serial]}'"`. Reads serial from PROVENANCE.md at runtime (v2-W3 fix). Exit code 0 = pass.

---

## Phase 3 — Cluster Membership Verification (3 units)

**Goal:** confirm cluster assignments, decide whether Estancia/Xentro crew get cross-cluster enrollment.

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|------|----------------------------|
| 3-1 | Run `python .claude/skills/adms-bei-erp/scripts/cluster_lookup.py --store "ORTIGAS ESTANCIA"` and `python .claude/skills/adms-bei-erp/scripts/cluster_lookup.py --store "XENTRO MONTALBAN"` (v2-B1: store name with space, no "MALL"). Per `clusters.md` line 30 (post-Phase-2-task-2-4 update), Estancia is C2 (canonical 4 + Greenhills + Estancia = 6 devices) and Xentro is C5 (canonical 5 + Xentro = 6 devices). | stdout MUST_CONTAIN: `cluster: 2` for Estancia and `cluster: 5` for Xentro (or `not found` if cluster_lookup.py hasn't been updated to recognize the new stores — fall back to Phase 3 task 3-2 manual cluster mapping) |
| 3-2 | Decide cross-cluster enrollment policy. Default per `clusters.md` is "every store employee enrolled on ALL devices within their cluster." Estancia crew → enroll on UDP3252900249 + 4 secondary C2 devices (UDP3235200631, UDP3235200831, UDP3252100384, UDP3252900302). Xentro crew (if any) → enroll on Xentro serial + 5 secondary C5 devices (UDP3251200193, CNYG242061071, UDP3252900048, UDP3252900155, UDP3235200594). Write the chosen policy to `tmp/s230/enrollment_plan.json`. | MUST_MODIFY: `tmp/s230/enrollment_plan.json` MUST_CONTAIN: `home_devices`, `secondary_devices`, `bio_ids` arrays |
| 3-2 (replacement) | **(v2-B6 corrected)** Decide cross-cluster enrollment policy. Default per `clusters.md` is "every store employee enrolled on ALL devices within their cluster." After this sprint, **C2 has 6 devices, not 4**: 4 canonical + Greenhills (UDP3252900251) + Estancia (UDP3252900249). Xentro joins C5 making it 6 devices: 5 canonical + new Xentro. So: <br>**Estancia crew (4) × 6 C2 devices = 24 commands** (cross-cluster) or 4 (single-device). C2 devices: UDP3235200631 Megamall, UDP3235200831 NEDSA, UDP3252100384 CTTM, UDP3252900302 Gateway, UDP3252900251 Greenhills, UDP3252900249 Estancia (home).<br>**Xentro crew (N) × 6 C5 devices = 6N commands** (cross-cluster) or N (single-device). C5 devices: UDP3251200193 Ortigas, CNYG242061071 Marikina, UDP3252900048 Taytay, UDP3252900155 Sta Lucia, UDP3235200594 Antipolo, `<xentro_serial>` Xentro (home).<br>Read `enrollment_mode` from `tmp/s230/PROVENANCE.md` (set in Phase 0 task 0-4 question 4). Write the chosen policy to `tmp/s230/enrollment_plan.json`. | MUST_MODIFY: `tmp/s230/enrollment_plan.json` MUST_CONTAIN: `home_devices`, `secondary_devices`, `bio_ids` arrays AND a top-level `cluster_size_after_sprint` field showing 6 for C2 and 6 for C5 |
| 3-3 | If `enrollment_mode = single_device` per PROVENANCE.md, revise `enrollment_plan.json` to set `secondary_devices: []`. Default = `cross_cluster`. | (only modifies enrollment_plan.json if needed) |

**Phase 3 verification script:** `output/s230/verify_phase3.py` — checks that `tmp/s230/enrollment_plan.json` is valid JSON, has all 6 C2 devices listed for Estancia, all 6 C5 devices listed for Xentro (when crew supplied), and `cluster_size_after_sprint == 6` for both clusters.

---

## Phase 4 — Employee Master CSV + Google Sheet + Frappe `tabEmployee` (12 units, was 8)

**Goal:** if Phase 0 supplied Xentro crew, add them to all 4 systems (CSV + Sheet + Frappe + CHANGE_LOG). If no crew, this phase is a no-op for Xentro and only re-verifies the 4 existing Estancia rows. **(v2 reordering: tabBranch verify FIRST, Frappe MAX query SECOND, CSV append before validate, atomicity guard around 4 writes.)**

> **HARD BLOCKER (v2-B4):** This phase MUST NOT proceed unless Phase 0 task 0-6 wrote `safe_to_proceed: true` to `output/s230/verification/frappe_max_bio_id.json`. The v1 git-based check (`git log origin/s228-...`) was REMOVED — that ref doesn't exist on origin (verified 2026-04-29). The real check is: live Frappe MAX(attendance_device_id) ≤ Master CSV MAX(attendance_device_id). If diverged, S228 (or another sprint) has live-but-uncommitted INSERTs — STOP.

> **HARD BLOCKER — INSERT_SQL TEMPLATE (v2-B2):** Inlined below. Do NOT synthesize a different SQL string. Source: `tmp/insert_13_employees.py:181-204` and S228 plan body line 447-470 (audit-verified canonical template). All metadata columns are required for the row to appear in Frappe Desk and to participate in tree walks.

```sql
INSERT IGNORE INTO `tabEmployee` (
  name, creation, modified, modified_by, owner, docstatus, idx,
  naming_series, employee_name, first_name, last_name,
  attendance_device_id, employee_number,
  designation, department, branch, company,
  employment_type, date_of_joining, date_of_birth, gender,
  status, personal_email, cell_number,
  lft, rgt, old_parent,
  notice_number_of_days, ctc, unsubscribed,
  create_user_permission, custom_verification_status, custom_enrichment_status
) VALUES (
  %(bio_id)s,                              -- name = bio_id (PK)
  NOW(), NOW(), 'Administrator', 'Administrator', 0, 0,
  'HR-EMP-',                               -- naming_series
  %(employee_name)s,                       -- "LASTNAME, FIRSTNAME M."
  %(first_name)s, %(last_name)s,
  %(bio_id)s,                              -- attendance_device_id
  %(bio_id)s,                              -- employee_number = bio_id
  'STORE CREW',                            -- designation default for crew
  'Operations', %(branch_name)s, %(company)s,
  'Probationary',                          -- employment_type for new hires
  %(date_of_joining)s, %(date_of_birth)s,
  %(gender)s,                              -- 'Male'|'Female'|'' (CSV may have empty)
  'Active', %(personal_email)s, %(cell_number)s,
  0, 0, '',                                -- lft, rgt, old_parent (tree)
  60, 0, 0,                                -- notice_number_of_days, ctc, unsubscribed
  0, 'Pending', 'Pending'                  -- create_user_permission, custom_*
);
```

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|------|----------------------------|
| 4-0 | **(v2-B8 NEW)** **Prerequisite — verify tabBranch rows exist with correct casing.** SSM Frappe query: `SELECT name FROM tabBranch WHERE name IN ('XENTRO MONTALBAN','ORTIGAS ESTANCIA','XENTROMALL MONTALBAN','Ortigas Estancia');`. Write JSON result to `output/s230/verification/tabBranch_precheck.json`. **(a)** If `XENTRO MONTALBAN` AND `ORTIGAS ESTANCIA` both exist → continue. **(b)** If `XENTRO MONTALBAN` is missing → INSERT it via `/frappe-bulk-edits` script using S228's pattern (`tmp/insert_13_employees.py:22-32`): `INSERT INTO tabBranch (name, creation, modified, modified_by, owner, docstatus, idx) VALUES ('XENTRO MONTALBAN', NOW(), NOW(), 'Administrator', 'Administrator', 0, 0);`. **(c)** If `ORTIGAS ESTANCIA` is missing → INSERT it the same way. **(d)** If `XENTROMALL MONTALBAN` (with MALL) exists instead → STOP and ask Sam: "Existing tabBranch row uses 'XENTROMALL MONTALBAN'; S228 plan and this plan use 'XENTRO MONTALBAN'. Pick one and we'll align the rest of the work." | MUST_MODIFY: `output/s230/verification/tabBranch_precheck.json` MUST_CONTAIN: `xentro_branch_exists: true`, `estancia_branch_exists: true`, AND `chosen_xentro_string: "XENTRO MONTALBAN"` (or whatever Sam confirmed in Phase 0) |
| 4-1 | Re-verify Estancia crew with `python .claude/skills/adms-bei-erp/scripts/audit_employees.py --with-names "9001827:PAGSALIGAN, HAYDEE D." "9001830:MORALES, MAE PEARL GRACE E." "9001832:MARTILLANO, LUISA B." "9001835:VILLAREAL, JENNY A."`. All 4 must return `match=True` and `store=ESTANCIA`. | stdout MUST_CONTAIN: 4 `match=True` lines |
| 4-2 | **CONDITIONAL — Xentro crew supplied (per Phase 0):** Get Bio IDs. If Sam supplied them, defer validation to task 4-2a (after Frappe MAX check). If Sam said "use next-available," run `python .claude/skills/adms-bei-erp/scripts/next_bio_id.py --count <N> --json > tmp/s230/csv_max_query.json` to get CSV-max-based suggestion. Document in `tmp/s230/PROVENANCE.md`. | MUST_MODIFY: `tmp/s230/PROVENANCE.md` adds Bio IDs section. tmp/s230/csv_max_query.json has `next_available` array |
| 4-2a | **(v2-B3 NEW)** **Live Frappe MAX cross-check** (the real concurrency safeguard). Re-run the Phase 0 task 0-6 SSM Frappe MAX query (cached result is fine if <5 min old). Compare `frappe_max` vs the CSV-max-based suggestion from 4-2. **(a)** If `frappe_max > csv_max`, take `frappe_max + 1` as the new seed; offset all suggested Bio IDs accordingly. Document the offset in `tmp/s230/PROVENANCE.md`. **(b)** If `frappe_max <= csv_max`, use the CSV suggestion as-is. **(c)** Cross-check each chosen Bio ID with `frappe.db.exists("Employee", {"attendance_device_id": "<bio>"})` via `/frappe-bulk-edits` query. If ANY exists, STOP and ask Sam — collision with prior sprint or untracked manual insert. | MUST_MODIFY: `tmp/s230/PROVENANCE.md` MUST_CONTAIN: `frappe_max:`, `csv_max:`, `final_bio_ids: [...]`, `bio_id_collisions: []` |
| 4-3 | **CONDITIONAL — Xentro crew supplied:** **(v2-W5 atomicity guard)** Wrap tasks 4-3 → 4-4 → 4-5 → 4-6 in an explicit reverse-rollback contract (see "Phase 4 Atomicity Contract" subsection below). Append rows to `data/_FINAL/EMPLOYEE_MASTER.csv` with `store_location=XENTRO MONTALBAN` (uppercase, matching local mapping; **v2-B1: NO trailing "MALL"**) and `Active` status. **CSV column reference (v2-INFO):** real CSV columns per header are status=col 9, store_location=col 13, but with naive `awk -F','` the comma INSIDE quoted name shifts everything by 1, so awk sees status at col 10 and store_location at col 14. Use Python `csv` module for parsing/writing to avoid the shift. Use the existing Estancia row format as a template. | MUST_MODIFY: `data/_FINAL/EMPLOYEE_MASTER.csv` MUST_CONTAIN new rows; `python -c "import csv; r=list(csv.reader(open('data/_FINAL/EMPLOYEE_MASTER.csv'))); print(sum(1 for x in r[1:] if len(x)>13 and x[12]=='XENTRO MONTALBAN' and x[8]=='Active'))"` prints N |
| 4-4 | **CONDITIONAL — Xentro crew supplied:** Insert into Frappe `tabEmployee` via `/frappe-bulk-edits` SSM pipeline. **Use the inlined HARD BLOCKER INSERT_SQL template above verbatim — do NOT synthesize a different INSERT.** Required column-binding: `bio_id` from PROVENANCE.md final_bio_ids, `employee_name` per Sam's Phase 0 input, `branch_name` = `'XENTRO MONTALBAN'` (verified in 4-0), `company` = `'PERPETUAL FOOD CORP. - BEI'` (or canonical match — verify against `tabCompany`), `date_of_joining` and `date_of_birth` per Sam-supplied roster (default `date_of_birth='1990-01-01'` if unknown — flag for HR follow-up). Wrap each INSERT in `frappe.db.savepoint("s230_emp_<bio>")` per DM-2. **Sentry observability is NOT required** (verified: `/frappe-bulk-edits` runs via `docker exec ... python` after `frappe.init()`, bypassing the `@frappe.whitelist()` middleware — see SKILL.md §Execution Environment). | INSERT scripts logged to `tmp/s230/insert_employee_<bio_id>.py`; Frappe `frappe.db.exists("Employee", {"attendance_device_id": <bio>})` returns True for every new bio after step completes |
| 4-4a | **(v2-W8 NEW — explicit defer note)** Xentro crew enrolled here will appear in Frappe Desk Employee list and can punch biometrically. They will NOT have a `tabUser` row, so they CANNOT log into my.bebang.ph until a follow-up sprint creates User rows + role assignment. This is intentionally OUT OF SCOPE for S230. Document in `tmp/s230/PROVENANCE.md` under `tab_user_followup_required: [<bio_id_list>]`. | MUST_MODIFY: PROVENANCE.md MUST_CONTAIN `tab_user_followup_required:` line |
| 4-5 | **CONDITIONAL — Xentro crew supplied:** **(v2-W6 OAuth refresh)** BEFORE the Sheets API call, refresh the OAuth token via `hrms.utils.google_oauth.refresh_access_token()` pattern (or its current equivalent). On 401-after-refresh, STOP and write to DEFECTS.md "Google OAuth refresh failed — Sam must re-authorize". Then sync to Google Sheet `1iFDbvaOg0-kbNLFJ5WuYCFOw2nmlyUkU42MbmPSVmMg` (sheet "Employee Master"). Append rows matching the CSV format. On 429 rate limit, exponential backoff (1s, 2s, 4s, 8s) for up to 30 sec. Capture response in `output/s230/verification/google_sheet_after.json`. **(v2-W5 atomicity)** If Sheets API fails after all retries, do NOT roll back the CSV/Frappe inserts (they're authoritative); flag DEFECT-Sheet and continue. | MUST_MODIFY: `output/s230/verification/google_sheet_after.json` MUST_CONTAIN: `updates.updatedRows: <N>` OR `error_after_retries: ...` |
| 4-6 | **ALWAYS:** Append change rows to `data/_FINAL/CHANGE_LOG.csv` for every Bio ID enrolled (Estancia 4 + any new Xentro): use `python .claude/skills/adms-bei-erp/scripts/log_change.py --batch tmp/s230/changes.json` where each row has `system=ADMS, action=ENROLL` for new enrollments, plus `system=EMPLOYEE_MASTER, action=ADD` for new CSV rows. | MUST_MODIFY: `data/_FINAL/CHANGE_LOG.csv` MUST_CONTAIN new rows for each affected Bio ID |
| 4-7 | Diff the CSV: `git diff data/_FINAL/EMPLOYEE_MASTER.csv > output/s230/verification/employee_master_after.csv_diff`. **(v2-B5)** Stage with `git add -f data/_FINAL/EMPLOYEE_MASTER.csv data/_FINAL/CHANGE_LOG.csv output/s230/verification/employee_master_after.csv_diff` (paths are gitignored). | MUST_MODIFY: `output/s230/verification/employee_master_after.csv_diff` non-empty if Xentro crew supplied; empty if device-only mode |

### Phase 4 Atomicity Contract (v2-W5)

The 4 writes in Phase 4 (CSV → Frappe → Sheet → CHANGE_LOG) span 4 disjoint systems. No single transaction covers them. Use this manual rollback contract:

```
Pre-snapshot (Phase 0 task 0-5 already captured):
  - tmp/s230/employee_master_pre_change.csv

Order: 4-3 (CSV) → 4-4 (Frappe inside savepoint) → 4-5 (Sheet) → 4-6 (CHANGE_LOG)

If 4-4 (Frappe) fails:
  - frappe.db.rollback_to_savepoint("s230_emp_<bio>") — rolls Frappe
  - cp tmp/s230/employee_master_pre_change.csv data/_FINAL/EMPLOYEE_MASTER.csv — restores CSV
  - DO NOT touch Sheet (not yet attempted) or CHANGE_LOG (not yet attempted)
  - Write [DEFECT-PHASE4-FRAPPE] to DEFECTS.md, STOP

If 4-5 (Sheet) fails after retries:
  - DO NOT roll back Frappe or CSV (they're authoritative — Sheet sync is a mirror)
  - Write [DEFECT-PHASE4-SHEET] to DEFECTS.md with detailed state
  - Continue to 4-6 (CHANGE_LOG still required)
  - Sam must manually reconcile the Sheet later

If 4-6 (CHANGE_LOG) fails:
  - Audit trail is missing but data is authoritative — write [DEFECT-PHASE4-CHANGELOG]
  - Sam appends manually before closeout
```

**Phase 4 verification script:** `output/s230/verify_phase4.py` — reads `tmp/s230/PROVENANCE.md` to determine `xentro_crew_mode`. If `roster`, asserts (a) `tabBranch_precheck.json` shows both Branch rows exist, (b) every final Bio ID exists in CSV (parsed via `csv` module, NOT awk), (c) every Bio ID exists in Frappe via `frappe.db.exists("Employee", {"attendance_device_id": "<bio>"})`, (d) Google Sheet response shows `updatedRows >= N` OR `error_after_retries` documented in DEFECTS.md, (e) CHANGE_LOG has `system=EMPLOYEE_MASTER` rows for each Bio ID. If `device_only`, asserts CSV diff is empty for Xentro additions but Estancia 4 CHANGE_LOG entries exist.

---

## Phase 5 — ADMS Enrollment via `/adms-bei-erp` Scripts (8 units, was 7)

**Goal:** push DATA UPDATE USERINFO commands to ADMS for every (employee, device) pair per the Phase 3 enrollment_plan, after deduping against the 54 PRESERVED PENDING from 2026-03-30.

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|------|----------------------------|
| 5-1-pre | **(v2-B7 NEW — idempotency dedup)** Query existing PENDING commands BEFORE building the batch: SSM `SELECT id, sn, command_text, status, attempts, created_at, substring(command_text from 'PIN=([0-9]+)') AS pin FROM adms_device_cmd WHERE sn IN ('UDP3252900249', '<xentro_serial>', 'UDP3235200631', 'UDP3235200831', 'UDP3252100384', 'UDP3252900302', 'UDP3252900251', 'UDP3251200193', 'CNYG242061071', 'UDP3252900048', 'UDP3252900155', 'UDP3235200594') AND status = 'PENDING';`. Write JSON to `tmp/s230/preexisting_pending_dedup.json`. **Expected baseline: ~54 rows on UDP3252900249 (the 2026-03-30 roving roster batch, PRESERVED).** Document the (sn, pin) pairs that will be EXCLUDED from the new batch in 5-1. | MUST_MODIFY: `tmp/s230/preexisting_pending_dedup.json` MUST_CONTAIN: `existing_pairs: [(sn,pin), ...]`, `dedup_count: <N>` |
| 5-1 | Build the enrollment batch JSON `tmp/s230/enrollment_batch.json`. For each Bio ID and each device in the Phase 3 enrollment_plan, produce one row: `{"bio": <bio>, "name": "<name>", "device": "<sn>"}`. **(v2-B6 corrected math)** Estancia 4 crew × 6 C2 devices (UDP3252900249 + Megamall + NEDSA + CTTM + Gateway + Greenhills) = **24 rows** IF cross-cluster mode; or 4 rows IF single-device mode. Xentro N crew × 6 C5 devices (xentro + Ortigas + Marikina + Taytay + Sta Lucia + Antipolo) = **6N rows** IF cross-cluster; or N rows IF single-device. **(v2-B7 dedup)** SUBTRACT every (sn, pin) pair already in `tmp/s230/preexisting_pending_dedup.json` from the new batch — these would create duplicates if pushed. Document the FINAL batch size after subtraction. | MUST_MODIFY: `tmp/s230/enrollment_batch.json` JSON array with correct row count after dedup |
| 5-1-bis | **(v2-Frappe-C8)** Verify `enroll.py` implementation against the canonical pattern in `hrms/api/transfer_requests.py:759`. Read the script. Assert it: (a) uses `requests.post()` to `{ADMS_BASE}/admin/device/<sn>/commands` (REST, not Postgres E-string), (b) sends `X-Admin-Token` header, (c) builds `command_text` exactly as `f'DATA UPDATE USERINFO PIN={bio}\\tName={name}\\tPri=0'` with literal tab bytes, (d) does NOT include any `C:serial:` prefix, (e) does NOT shell out. If any check fails, STOP — fall back to the canonical `_build_update_command` + `_queue_adms_command` pattern from `transfer_requests.py:710-770`. | (no file mutation; agent transcript captures the verification) |
| 5-2 | Push enrollments via `python .claude/skills/adms-bei-erp/scripts/enroll.py --batch tmp/s230/enrollment_batch.json`. The script uses REST API + Python f-string + `assert command_text.count("\t") >= 2` (skill Method 1 — safest). Each command_text MUST be `DATA UPDATE USERINFO PIN=<bio>\tName=<name>\tPri=0` with actual tab bytes (0x09), NOT literal `\t`. | enroll.py stdout MUST_CONTAIN: `inserted` count matching the deduped batch row count |
| 5-3 | Verify the commands queued in Postgres: SSM `SELECT sn, COUNT(*) AS pending FROM adms_device_cmd WHERE created_at > NOW() - INTERVAL '5 minutes' AND status='PENDING' GROUP BY sn ORDER BY sn;`. Compare to expected counts (deduped). | SSM stdout MUST_CONTAIN: row count per device matching expected |
| 5-4 | **HARD BLOCKER — heartbeat watch.** Wait up to 10 minutes for live devices to pick up commands. Poll every 60 seconds: **(v2-W3 fix)** `SELECT sn, COUNT(*) FROM adms_device_cmd_callback WHERE received_at > NOW() - INTERVAL '70 seconds' GROUP BY sn;` (per-poll delta, NOT 15-min cumulative). Track per-poll deltas in `tmp/s230/ack_polling_<timestamp>.log`. <br>**Verdict logic (v2-System-Arch-F2 + F8 reconciled):**<br>- UDP3252900249 (Estancia): if zero callbacks after 10 min AND Sam confirmed device is physically deployed — flag `[DEFECT-Estancia-OFFLINE_NEW]`. If Sam said device is NOT physically deployed yet — flag `[NOTE-Estancia-OFFLINE_PRE_EXISTING]` (informational only, not a defect).<br>- Xentro serial: same logic, keyed by Sam's Phase 0 answer about physical deployment status.<br>- If device 200-ing but `adms_device_cmd_callback.return_code < 0` → `[DEFECT-ONLINE_NOT_ACKING]` (firmware/fingerprint-DB issue — see Failure Response Mode D). | MUST_MODIFY: `tmp/s230/ack_polling_<timestamp>.log` MUST_CONTAIN: 10 polling rounds with per-poll delta counts (NOT cumulative) |
| 5-5 | **(v2-B9 fix)** Capture ACK status snapshot: `python .claude/skills/adms-bei-erp/scripts/verify.py --device UDP3252900249 <xentro_serial> --check-info --recent 60` (single `--device` flag with multiple SN args per `verify.py` argparse `nargs='+'`; **`--json` flag does NOT exist in verify.py** — use stdout capture as-is). Pipe stdout to `output/s230/verification/adms_enrollment_acks.json` after wrapping in a JSON envelope: `python .claude/skills/adms-bei-erp/scripts/verify.py --device UDP3252900249 <xentro_serial> --check-info --recent 60 > tmp/s230/verify_raw.txt && python -c "import json,sys; print(json.dumps({'verify_output': open('tmp/s230/verify_raw.txt').read(), 'captured_at': '$(date -Iseconds)'}, indent=2))" > output/s230/verification/adms_enrollment_acks.json`. | MUST_MODIFY: `output/s230/verification/adms_enrollment_acks.json` MUST_CONTAIN: `verify_output` (string), `captured_at` (ISO date) |

**Phase 5 verification script:** `output/s230/verify_phase5.py` — reads `tmp/s230/enrollment_batch.json` and `output/s230/verification/adms_enrollment_acks.json`. Asserts (a) batch row count > 0 (or 0 if device_only and Estancia all already enrolled — baseline 54 PENDING already exist), (b) every command in the new batch was found in `adms_device_cmd` (PENDING or ACKED), (c) no duplicates in `adms_device_cmd` for (sn, pin) pairs from the new batch (count = 1 per pair, NOT 2), (d) writes a per-Bio-ID, per-device matrix to `output/s230/verification/enrollment_matrix.csv`.

---

## Phase 6 — Verification + Heartbeat Watch + L3-style ACK Audit (5 units)

**Goal:** end-to-end probe that all six target systems agree.

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|------|----------------------------|
| 6-1 | Run all L3 Workflow Scenario probes (the table earlier in this plan). Capture each probe result as a JSON entry in `output/s230/verification/state_after.json` with shape `{"probe": "<id>", "expected": "<x>", "actual": "<y>", "pass": <bool>, "evidence_path": "<path>"}`. | MUST_MODIFY: `output/s230/verification/state_after.json` MUST_CONTAIN: 6 probe entries (one per L3 scenario row) |
| 6-2 | Reconcile the 6 systems: (a) `sn_mapping_all.csv` server allowlist, (b) `device_mapping.py` local mapping, (c) `EMPLOYEE_MASTER.csv` Master CSV, (d) Frappe `tabEmployee`, (e) Google Sheet, (f) `adms_device_cmd` queue. Write a 6-column reconciliation matrix to `output/s230/SUMMARY.md` showing PASS/FAIL per system per (Estancia, Xentro). | MUST_MODIFY: `output/s230/SUMMARY.md` MUST_CONTAIN: a 2-row × 6-column markdown table |
| 6-3 | If any defects surface (Xentro device not heartbeating, Frappe insert silently failed, Sheet API timeout, etc.), write detailed entry to `output/s230/DEFECTS.md` with: defect ID, system, expected vs actual, suggested follow-up. If zero defects, file MUST_CONTAIN the literal string `No defects detected.` | MUST_MODIFY: `output/s230/DEFECTS.md` exists |
| 6-4 | **(v2-W7 precise verdicts)** Heartbeat verdict: classify each device using the SQL-defined criteria below. <br>**`ONLINE_AND_ACKING`** = `EXISTS (SELECT 1 FROM adms_device_cmd_callback WHERE sn=? AND received_at > NOW() - INTERVAL '5 min')` AND `last_callback.return_code >= 0`<br>**`ONLINE_NOT_ACKING`** = device has heartbeat in last 5 min (`adms_device_cmd_callback` row received) BUT `return_code < 0` for ≥1 of the new commands sent in Phase 5<br>**`OFFLINE_PRE_EXISTING`** = no heartbeat AND device existed in `sn_mapping_all.csv` before Phase 1 (Estancia is the only such device — UDP3252900249 since 2026-03-30)<br>**`OFFLINE_NEW`** = no heartbeat AND device was added in this sprint (Xentro serial)<br><br>Estancia UDP3252900249: pre-existing offline → not a regression. Xentro serial: expect `ONLINE_AND_ACKING` if Sam restarted the API container AND the device is physically powered+pointed at adms.bebang.ph:8443; otherwise `OFFLINE_NEW`. Use this precise SQL: `SELECT cmd.sn, cmd.id, cmd.command_text, cb.return_code, cb.received_at FROM adms_device_cmd cmd LEFT JOIN adms_device_cmd_callback cb ON cb.sn = cmd.sn AND cb.received_at >= cmd.created_at WHERE cmd.sn IN (?,?) AND cmd.created_at > NOW() - INTERVAL '15 min';` and capture rows to `output/s230/verification/heartbeat_verdict_query.json`. | MUST_MODIFY: `output/s230/SUMMARY.md` MUST_CONTAIN: `heartbeat_verdict:` section with precise verdict per device + supporting SQL row counts |

**Phase 6 verification script:** `output/s230/verify_phase6.py` — asserts `output/s230/verification/state_after.json` is valid JSON with 6 entries, asserts `output/s230/SUMMARY.md` has the reconciliation table heading, asserts `output/s230/DEFECTS.md` exists.

---

## Phase 7 — Closeout: PR + Plan/Registry Update + Worktree Removal (5 units, was 3)

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|------|----------------------------|
| 7-1 | Update plan YAML: set `status: COMPLETED`, `completed_date: 2026-04-29` (or actual date), `execution_summary: "Estancia local mapping fix landed (UDP3252900249 → ORTIGAS ESTANCIA). Xentro Mall <serial> added to all 3 registers (server allowlist, local mapping, ADMS commands). N crew enrolled on N devices. Heartbeat verdicts: Estancia=<verdict>, Xentro=<verdict>. PR #<num>."`. | MUST_MODIFY: this file, status field changes |
| 7-2 | Update `docs/plans/SPRINT_REGISTRY.md` S230 row: status `PLANNED_AUDITED_v2` → `COMPLETED`, add PR ref. | MUST_MODIFY: SPRINT_REGISTRY.md S230 row |
| 7-2.5 | **(v2-W1 NEW — rebase before push)** Re-fetch and rebase: `git fetch origin --prune && git log --oneline origin/production..HEAD` (review commits ahead). If `origin/production` advanced since worktree spawn, run `git rebase origin/production`. After rebase, verify no conflict markers: `git grep -n '<<<<<<<\|=======\|>>>>>>>'` returns ZERO. Origin: 2026-04-05 S159/S161 silent feature-revert incident — non-conflicting auto-merges silently dropped delivery schedule fields. | `git log origin/production..HEAD --oneline` clean; no conflict markers in any file |
| 7-2a | **(v2-B5 NEW — consolidated `git add -f` block)** Stage every committed-evidence path explicitly. `output/`, `data/`, `docs/plans/`, `.claude/` are ALL gitignored (per `.gitignore` + `.git/info/exclude` lines verified 2026-04-29). Run: <br>```bash<br>git add -f output/s230/SUMMARY.md output/s230/DEFECTS.md output/s230/manual_steps.md \<br>           output/s230/REMOTE_TRUTH_BASELINE.json \<br>           output/s230/SURFACE_OWNERSHIP_MATRIX.csv \<br>           output/s230/PROTECTED_SURFACE_REGISTRY.csv \<br>           output/s230/TOUCHED_FILE_ROUTING.csv \<br>           output/s230/verification/server_allowlist_after.txt \<br>           output/s230/verification/local_mapping_after.diff \<br>           output/s230/verification/employee_master_after.csv_diff \<br>           output/s230/verification/google_sheet_after.json \<br>           output/s230/verification/adms_enrollment_acks.json \<br>           output/s230/verification/state_after.json \<br>           output/s230/verification/enrollment_matrix.csv \<br>           output/s230/verification/tabBranch_precheck.json \<br>           output/s230/verification/frappe_max_bio_id.json \<br>           output/s230/verify_phase*.py<br>git add -f data/_FINAL/CHANGE_LOG.csv<br># Only if Xentro crew supplied:<br>git add -f data/_FINAL/EMPLOYEE_MASTER.csv<br>git add -f .claude/skills/adms-bei-erp/references/clusters.md  # v2-B6 doc fix<br>git add -f docs/plans/2026-04-29-sprint-230-xentro-estancia-device-enrollment.md<br>git add -f docs/plans/SPRINT_REGISTRY.md<br>git add hrms/utils/device_mapping.py   # tracked — no -f<br>git status --short                     # final review<br>git commit -m "feat(S230): Xentro Mall + Estancia device registration + crew enrollment v2-amended"<br>``` | `git status --short` after commit shows nothing in `output/s230/` left unstaged |
| 7-3 | Push branch and create PR: `git push -u origin s230-xentro-estancia-device-enrollment` then `GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms --base production --head s230-xentro-estancia-device-enrollment --title "S230: Xentro Mall + Estancia device registration + crew enrollment" --body "$(cat output/s230/SUMMARY.md)"`. Capture PR URL. | PR exists at `https://github.com/Bebang-Enterprise-Inc/hrms/pull/<num>` |
| 7-4 | Verify worktree clean: `git status --short` (must be empty). If dirty with intentional scratch, commit as `chore(S230): scratch artifacts from execution` to the branch (NOT to a follow-up — this branch hasn't merged yet). | (no file change if already clean) |
| 7-5 | Remove worktree: `cd F:/Dropbox/Projects/BEI-ERP && git worktree remove F:/Dropbox/Projects/BEI-ERP-s230-xentro-estancia-device-enrollment`. Verify removal via `git worktree list`. **(v2-W1 fallback)** If removal fails: re-enter the worktree, identify uncommitted files via `git status --short`, commit them with `chore(S230): scratch artifacts from execution` per the worktree-isolation rule step 5, then re-run the removal. **NEVER use `--force`.** **STOP after this — Sam handles merge.** | `git worktree list` MUST NOT_CONTAIN: the s230 path |

**Phase 7 verification script:** `output/s230/verify_phase7.py` — asserts (a) plan YAML has `status: COMPLETED`, (b) registry row has `COMPLETED`, (c) `gh pr view <num>` returns valid PR, (d) `git worktree list` does not include the s230 worktree, (e) `git ls-files output/s230/ \| wc -l` returns ≥ 14 (at least the SUMMARY/DEFECTS/manual_steps + 11 verification files), proving the consolidated `git add -f` worked.

---

## Status Reconciliation Contract

Whenever counts, blockers, stage, or status changes, update in the same work unit:

1. `output/s230/SUMMARY.md` (reconciliation table + heartbeat verdict)
2. `output/s230/DEFECTS.md` (defect register)
3. `output/s230/verification/state_after.json` (probe-by-probe pass/fail)
4. This plan's `status` and `execution_summary` YAML fields
5. `docs/plans/SPRINT_REGISTRY.md` S230 row (Status + PR fields)

---

## Signoff Model

- **mode:** `single-owner`
- **approver_of_record:** `Sam Karazi (CEO)`
- **signoff_artifact:** `output/s230/SUMMARY.md` (signoff is implicit on PR merge — Sam is the merger)
- **note:** This sprint does not require department-level signoff. Operations team (Edlice Dela Cruz, Ronald Carigal IT) are notified-but-not-gating; if the Xentro device fails to heartbeat after restart, IT escalation is a follow-up sprint, not a blocker for S230 closeout.

---

## Forbidden Patterns (S154 Zero-Skip Enforcement)

The executing agent MUST NOT:

- Skip a task silently
- Mark partial work as "done"
- Replace a task with a simpler version without Sam's approval (e.g., "I'll just add Estancia and skip Xentro because the serial wasn't supplied" — instead, STOP at Phase 0)
- Hardcode the container name `adms_receiver_adms-db_1` (live name has a hash prefix as of 2026-04-29 — discover dynamically)
- Use shell pipelines for USERINFO commands (skill explicitly forbids — use REST API or Postgres E-strings)
- Include `C:serial:` prefix in `command_text` (the receiver adds this automatically)
- Fabricate a Xentro device serial if Sam doesn't provide it
- Fabricate Xentro Bio IDs without running `next_bio_id.py` against live Frappe
- Push enrollment commands without first running `validate_employee_bio_id` for each Bio ID
- Restart the API container without Sam's explicit deploy-password approval
- Push to `production` branch directly (use `s230-xentro-estancia-device-enrollment` branch)
- Merge the PR (Sam merges)

---

## Sentry Observability

This sprint does not modify any `@frappe.whitelist()` endpoints. The work is:
- Direct edits to `hrms/utils/device_mapping.py` (a utility, not an endpoint)
- SQL INSERT into `tabEmployee` via `/frappe-bulk-edits` (no whitelisted handler)
- File appends to `sn_mapping_all.csv` (not a Frappe surface)
- ADMS Postgres INSERT via REST/SSM (separate database, not Frappe)

If during execution the agent finds it must add a new whitelisted endpoint (unexpected), it MUST add `set_backend_observability_context(module="adms", action="<fn_name>", mutation_type="create")` per `.claude/rules/sentry-observability.md`.

---

## Failure Response

This sprint does NOT include browser/Playwright/L3 UI tests, but the same failure-mode discipline applies to integration probes:

- **Mode A (system bug):** if Frappe / ADMS / Google Sheet API rejects the agent's payload with a structured error, file `[DEFECT]` in `output/s230/DEFECTS.md`, do NOT mutate the underlying system, retry once if transient (rate-limit), then escalate.
- **Mode B (script bug):** if `enroll.py` / `audit_employees.py` / `next_bio_id.py` from `/adms-bei-erp` skill fails, fix the script in the branch (skill scripts are versioned in git — they're not external dependencies). If the fix is broadly useful (e.g., better error messaging), promote to the skill in a follow-up sprint.
- **Mode C (flake):** if SSM calls intermittently fail, retry with exponential backoff (1s, 2s, 4s) up to 3 times. If all fail, document in `tmp/s230/ssm_responses/` and request user retry. Do NOT mask flakes with try/except that swallows errors.
- **(v2-W7) Mode D (device hardware/firmware suspect):** if Phase 6 verdict is `ONLINE_NOT_ACKING` for any device (heartbeating but `return_code < 0` on USERINFO commands), this likely indicates: device firmware mismatch / corrupt fingerprint database / time sync drift / cloud server config drift. **Action template (write to DEFECTS.md):** `ESCALATION: Device <SN> heartbeating but rejecting USERINFO commands. Likely cause: device firmware mismatch or fingerprint-DB corruption. Action: Ronald Carigal IT to physically inspect device. Evidence: output/s230/verification/adms_enrollment_acks.json + heartbeat_verdict_query.json`. Do NOT retry the USERINFO commands automatically — physical inspection required.

If ≥3 library/skill-script fixes occur during execution, write `output/s230/LIBRARY_IMPROVEMENTS.md` describing each, for the next maintainer of the `/adms-bei-erp` skill to review.

---

## Closeout Artifacts (Final Checklist — v2 amended)

- [ ] `output/s230/SUMMARY.md` — reconciliation table, heartbeat verdicts, PR ref (`git add -f`)
- [ ] `output/s230/DEFECTS.md` — defect register (or "No defects detected.") (`git add -f`)
- [ ] `output/s230/manual_steps.md` — 3 SSM commands for Sam (API restart, verify probe, Frappe backend restart) (`git add -f`)
- [ ] `output/s230/REMOTE_TRUTH_BASELINE.json` — Phase 0 capture (`git add -f`)
- [ ] `output/s230/SURFACE_OWNERSHIP_MATRIX.csv` — anti-rewind contract (`git add -f`)
- [ ] `output/s230/PROTECTED_SURFACE_REGISTRY.csv` — anti-rewind contract (`git add -f`)
- [ ] `output/s230/TOUCHED_FILE_ROUTING.csv` — anti-rewind contract (`git add -f`)
- [ ] `output/s230/verification/server_allowlist_after.txt` — sn_mapping_all.csv post-state (`git add -f`)
- [ ] `output/s230/verification/local_mapping_after.diff` — git diff of device_mapping.py (`git add -f`)
- [ ] `output/s230/verification/employee_master_after.csv_diff` — git diff of EMPLOYEE_MASTER.csv (or "no changes" if device-only) (`git add -f`)
- [ ] `output/s230/verification/google_sheet_after.json` — Google Sheets API response (or "skipped: device-only") (`git add -f`)
- [ ] `output/s230/verification/adms_enrollment_acks.json` — verify.py output for both serials (`git add -f`)
- [ ] `output/s230/verification/state_after.json` — 6-probe assertion results (`git add -f`)
- [ ] `output/s230/verification/enrollment_matrix.csv` — per Bio-ID × per device matrix (`git add -f`)
- [ ] **(v2-B8)** `output/s230/verification/tabBranch_precheck.json` — Phase 4-0 prerequisite verification (`git add -f`)
- [ ] **(v2-B3)** `output/s230/verification/frappe_max_bio_id.json` — Phase 0/4 live Frappe MAX query (`git add -f`)
- [ ] **(v2-W7)** `output/s230/verification/heartbeat_verdict_query.json` — Phase 6 verdict SQL evidence (`git add -f`)
- [ ] `output/s230/verify_phase{0..7}.py` — 8 verification scripts (`git add -f`)
- [ ] `data/_FINAL/CHANGE_LOG.csv` — new rows for every enrollment (`git add -f`)
- [ ] `data/_FINAL/EMPLOYEE_MASTER.csv` — new Xentro rows if applicable (`git add -f`)
- [ ] `hrms/utils/device_mapping.py` — both new entries committed (tracked, no `-f`)
- [ ] **(v2-B6)** `.claude/skills/adms-bei-erp/references/clusters.md` — Estancia/Xentro/Greenhills updates (`git add -f`)
- [ ] `docs/plans/2026-04-29-sprint-230-xentro-estancia-device-enrollment.md` — status COMPLETED (`git add -f`)
- [ ] `docs/plans/SPRINT_REGISTRY.md` — S230 row COMPLETED with PR ref (`git add -f`)
- [ ] PR opened on `Bebang-Enterprise-Inc/hrms` from `s230-xentro-estancia-device-enrollment` → `production` (rebased on origin/production first per v2-W1)
- [ ] Worktree `F:/Dropbox/Projects/BEI-ERP-s230-xentro-estancia-device-enrollment` removed (no `--force`)

---

## Cold-Start Readability Test

If an agent reads ONLY this document with zero conversation history, can it answer:

- ✅ Where is the worktree spawned? (Phase 0 boot block, exact commands)
- ✅ What's the branch name? (YAML `branch:` field, repeated in Phase 0 and Phase 7)
- ✅ Why does Estancia only need a local-mapping fix (not a full device-add)? (Design Rationale paragraph 1)
- ⚠️ What is the Xentro serial number? (Phase 0 user-input gate — agent MUST stop and ask. This is INTENTIONAL — fabricating a serial would be worse than asking.)
- ⚠️ What are the Xentro Bio IDs? (Phase 0 user-input gate — same as serial, intentional.)
- ✅ Which cluster do Estancia/Xentro belong to? (Phase 3, references `clusters.md` line 30 — Estancia=C2, Xentro=C5)
- ✅ Which devices to push USERINFO to? (Phase 3 enrollment_plan.json + clusters.md device serial table)
- ✅ Which database container is the live Postgres? (Phase 0 dynamic discovery via `docker ps`, NOT hardcoded — current 2026-04-29 reality is `62c9d67fd960_adms_receiver_adms-db_1`)
- ✅ How to push USERINFO safely? (Phase 5 — REST API + Python f-string + tab-count assert; references `/adms-bei-erp` skill Method 1)
- ✅ What MUST_MODIFY/MUST_CONTAIN assertions exist? (every phase task has them)
- ✅ What's the closeout sequence? (Phase 7, 5 numbered tasks)

The intentional ⚠️ items above are the user-input gates — they are correctly NOT pre-resolved, and the plan correctly stops the agent at Phase 0 to obtain them.

---

## Amendment Log

| Date | Author | Section | Change |
|------|--------|---------|--------|
| 2026-04-29 | Sam (via Claude) | INITIAL v1 | Plan created. CEO directive: add Xentro Mall device + whitelist Estancia + add employees + fix local registry. Sprint registered as S230 (S229 was occupied by stray `fix/s229-*` branches per cross-check rule). canonical_scope=none rationale: ADMS device config + Employee Master CSV + new tabEmployee inserts only; no Company/Warehouse/Customer/Supplier mutations. |
| 2026-04-29 | Sam (via Claude) | v2 — full audit amendments | `/audit-plan-bei-erp` + `/fact-check-bei-erp` produced 10 CRITICAL + 21 WARNING blockers across 4 domain agents (Frappe-backend, Deployment-QA, System-Arch, Cold-Start) + lead live-system fact-checks. v2 resolves all 10 CRITICAL + top 10 WARNINGs in-line. Audit evidence: `output/plan-audit/sprint-230-xentro-estancia-device-enrollment/AUDIT_SUMMARY.md` and supporting findings files. Phase budget grew 38→47 units (still under 80 ceiling). Status: PLANNED → PLANNED_AUDITED_v2. **v2 changes by blocker ID:** **B1** branch-name fixed `XENTROMALL MONTALBAN`→`XENTRO MONTALBAN` throughout (matches S228 tabBranch row in `tmp/insert_13_employees.py:23`); **B2** full INSERT_SQL template inlined in Phase 4 task 4-4 with all 25+ required metadata cols, replacing the v1 4-column placeholder; **B3** Design Rationale §5 corrected — `next_bio_id.py` does NOT query Frappe (CSV-only), Phase 4-2a now runs explicit live SSM Frappe MAX query; **B4** Phase 0 task 0-6 S228 concurrency check rewritten — git-based check removed (origin/s228-... doesn't exist on remote, verified `git branch -r`), replaced with 3-part check (worktree list + Frappe MAX + local s228 dirty-state peek); **B5** consolidated `git add -f` block added in Phase 7-2a covering all 16+ output/s230/ paths plus data/, .claude/, docs/plans/; **B6** cluster math corrected — C2 has 6 devices (incl. Greenhills UDP3252900251 + new Estancia) not 4; clusters.md doc fix added as Phase 2 task 2-4; **B7** Phase 5 task 5-1-pre dedup query added against existing 54 PRESERVED PENDING (these are roving employees, not the 4 known crew); **B8** Phase 4 task 4-0 prerequisite added — verify tabBranch rows exist with correct casing, INSERT if missing (per S228 pattern); **B9** Phase 5 task 5-5 verify.py call corrected — single `--device` flag with multiple SN args, removed non-existent `--json` flag, JSON envelope wrapping for output; **B10** SSM Autonomy Boundary policy table added to Phase 1 — explicit classification of READ-ONLY (agent-autonomous) vs AGENT-MUTATION (autonomous-with-password) vs HUMAN-REQUIRED (Sam executes). **WARNINGs addressed:** **W1** Phase 7-2.5 explicit rebase-before-push step (S159/S161 silent-revert pattern); **W2** Phase 0 task 0-1.5 worktree-already-exists handling (3-case decision tree); **W3** Phase 5-4 query window changed `15 min` → `70 seconds` for per-poll deltas; **W4** Phase 4 reordered — CSV append before validate, plus Phase 4-2a Frappe collision precheck; **W5** Phase 4 Atomicity Contract subsection added with explicit reverse-rollback steps; **W6** Phase 4-5 OAuth refresh + 429 backoff prescribed; **W7** Phase 6-4 verdict logic uses precise SQL definitions, plus Failure Response Mode D escalation template; **W8** Phase 4-4a explicit defer note for `tabUser` follow-up (my.bebang.ph login deferred); **W9** Phase 1-4 manual_steps.md now has THREE restart commands (API immediate + verify probe + Frappe backend post-deploy); **W10** Phase 2 verify_phase2.py reads serial from PROVENANCE.md at runtime instead of hard-coding placeholder. **INFO fixes:** DEVICE_TO_STORE corrected from "47 devices" → "48 devices" (current pre-sprint, becomes 50 post-sprint); CSV column reference clarified (real columns vs awk-shifted columns). |
