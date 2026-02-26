# Sprint 03 Detailed Plan: Integration Backbone and Auto-Posting

**Sprint:** 03  
**Status:** Planned (NO-GO until AUDIT-01..AUDIT-10 are closed)  
**Master Plan:** `docs/plans/sprint-master-p0-plus-10-p1.md`  
**Escalation Authority:** `Sam Karazi (CEO)`  
**Scope Lock:** Only the 8 gaps listed below
**Business Evidence Lock:** `docs/plans/2026-02-25-p0-p1-business-evidence-lock.md`
**Code Verification:** `output/plan-audit/p0-plus-10-p1-2026-02-25/code_verification.md`

## 1) Sprint Goal

Turn sync stubs into real ERP writes, add operational failure signaling, and complete delivery-to-billing automation.

## 2) In-Scope Gaps

| Gap | Summary | Domain | Execution Channel | Dependency |
|---|---|---|---|---|
| GAP-006 | AR aging sync stub | Platform Integrations | Codex + Claude Code | none |
| GAP-007 | Inventory sync stub | Platform Integrations | Codex + Claude Code | none |
| GAP-008 | COA sync stub | Platform Integrations | Codex + Claude Code | none |
| GAP-009 | AP opening sync stub | Platform Integrations | Codex + Claude Code | none |
| GAP-025 | Bank account sync stub | Platform Integrations | Codex + Claude Code | none |
| GAP-046 | G-046 failure alerts missing | Platform Integrations | Codex + Claude Code | none |
| GAP-022 | Verify gross/net persistence behavior and edge-case extraction quality | Store Operations Systems | Codex + Claude Code | none |
| GAP-092 | Enforce controlled pre-delivery exception policy (default `confirm_delivery` auto-create already exists) | Supply Chain Systems | Codex + Claude Code | GAP-003, GAP-020 |

## 2.1 Implementation Touchpoints by Gap

| Gap | Backend Touchpoints | Frontend Touchpoints | Data Touchpoints | External/Integration |
|---|---|---|---|---|
| GAP-006 | ERP sync AR aging write-path | AR/finance monitoring surfaces | Sales invoice/update logs | Sheets receiver / sync source |
| GAP-007 | ERP sync inventory write-path | Inventory monitoring surfaces | Stock reconciliation records | Sync source feeds |
| GAP-008 | ERP sync COA write-path | Account visibility surfaces | Account master records | Sync source feeds |
| GAP-009 | ERP sync AP opening write-path | AP monitoring surfaces | Purchase invoice opening records | Sync source feeds |
| GAP-025 | ERP sync bank account write-path | Bank account visibility surfaces | Bank account records | Sync source feeds |
| GAP-046 | G-046 failure notification handler | Failure visibility UI/logs | Failure logs and alert payloads | Google Chat notifications |
| GAP-022 | POS upload parser and persistence path | POS upload UX | `gross_sales` and `net_sales` fields | Analytics/reporting consumers |
| GAP-092 | Delivery confirmation billing hook + pre-delivery exception approval hook | Trip and billing status UX | Trip records, delivery billing records, exception approvals | Store ops and finance linkage |

## 2.2 Acceptance Checklist by Gap

| Gap | Must-Pass Acceptance Checks |
|---|---|
| GAP-006 | AR aging sync writes expected invoice updates with idempotent behavior |
| GAP-007 | Inventory sync creates/updates stock reconciliation records correctly |
| GAP-008 | COA sync creates/updates account records without duplicates |
| GAP-009 | AP opening sync creates purchase invoices from source data correctly |
| GAP-025 | Bank account sync writes valid bank account records and updates |
| GAP-046 | Forced sync failure emits actionable GChat alert with traceable context |
| GAP-022 | POS upload persists gross/net values and downstream dashboards reflect values |
| GAP-092 | Default flow: `confirm_delivery` auto-creates billing linked to correct trip context. Exception flow: pre-delivery billing is blocked unless dual approval exists (Daymae/CPO + Butch/CFO) |

## 2.3 Definition of Ready (Sprint 03)

Each scoped gap must have all of the following before Stage 02/03:

1. Execution channel confirmed as `Codex + Claude Code`.
2. Input/output contract documented for the gap.
3. Idempotency rule documented for write-path gaps.
4. Alerting expectation documented for failure-path gaps.
5. Verification path defined for Stage 04.

## 3) Stage-Based Execution (Parallel)

1. Stage 01: Lock sync payload contracts, idempotency, and observability requirements.
2. Stage 02: Sync write-path stream in parallel (`GAP-006`, `GAP-007`, `GAP-008`, `GAP-009`, `GAP-025`).
3. Stage 03: Failure signaling stream (`GAP-046`) and store data correctness stream (`GAP-022`).
4. Stage 04: Delivery billing automation stream (`GAP-092`) with dependency checks from prior sprint outputs.
5. Stage 05: End-to-end integration reruns, deploy by bundle, and finalize sign-off evidence.

## 3.1 Stage Capacity and WIP Limits

1. Stage 02 sync stream: max 3 active PRs (split by entity family).
2. Stage 03 signal/data stream: max 2 active PRs.
3. Stage 04 automation stream: single PR until verified.
4. Stage 05 release candidate must have zero unresolved schema/contract blockers.

## 3.2 Stage Exit Artifacts

Required artifacts per stage:

1. Stage 01:
   - contract lock for each sync entity
   - execution model confirmation
2. Stage 02/03:
   - merged code reference
   - contract/idempotency smoke checks
3. Stage 04:
   - L1/L2/L3 evidence paths
   - Frappe write verification paths
   - alerting verification path
4. Stage 05:
   - deployment reference
   - rollback target reference
   - sign-off entry

## 3.3 Blocker Burn-Down During Implementation (MANDATORY)

The following work packets must be executed during implementation (not deferred to final audit):

| Packet ID | Stage | Scope | Blockers Closed | Required Output |
|---|---|---|---|---|
| S03-P01-GOV | Stage 01 | contracts + governance + permissions baseline | AUDIT-03, AUDIT-04, AUDIT-05, AUDIT-10 | contract spec, idempotency key map, transaction/rollback design, RBAC matrix, cleanroom assignment matrix |
| S03-P02-SYNC-ARINV | Stage 02 | GAP-006 + GAP-007 write paths | AUDIT-01 (partial), AUDIT-03, AUDIT-04, AUDIT-05 | AR/inventory write proofs, replay/idempotency tests, RBAC allow/deny tests |
| S03-P02-SYNC-COAAPBANK | Stage 02 | GAP-008 + GAP-009 + GAP-025 + `sync_supplier_soa` | AUDIT-01, AUDIT-02, AUDIT-03, AUDIT-04, AUDIT-05 | COA/AP/bank write proofs, supplier_soa handler proof, duplicate guard tests |
| S03-P03-ALERTING | Stage 03 | GAP-046 critical alerting completion | AUDIT-07 | forced-failure alert evidence with payload + escalation metadata |
| S03-P04-BILLING-EXC | Stage 04 | GAP-092 dual-approval pre-delivery flow | AUDIT-06 | blocked-without-approval proof, approved-exception proof, audit trail proof |
| S03-P05-RELEASE-QA | Stage 05 | preflight/rollback and scenario hardening | AUDIT-08, AUDIT-09 | preflight checklist, rollback drill log, GAP-specific L4 scenario evidence |

Implementation enforcement rules:

1. No packet is marked complete until its mapped `AUDIT-*` blockers show closure evidence in this plan.
2. Integration order is packet-by-packet; failed gate returns the packet to rework before the next packet proceeds.
3. Builder branches follow cleanroom branch naming and must push scoped commits only.
4. Any packet with out-of-scope file edits is rejected and reworked.

### 3.3.1 Blocker Closure Checkpoint Cadence

1. Stage 01 close checkpoint: `AUDIT-03/04/05/10` evidence reviewed and linked.
2. Stage 02 midpoint checkpoint: at least one sync packet demonstrates non-log write behavior plus duplicate-safe replay.
3. Stage 03 checkpoint: GAP-046 alert path tested with forced failure and real-time dispatch evidence.
4. Stage 04 checkpoint: dual-approval exception flow enforced end-to-end.
5. Stage 05 final checkpoint: `AUDIT-01..AUDIT-10` all marked resolved with linked artifacts before GO consideration.

## 3.4 Implementation Run Manifest (Kickoff)

Run metadata:

1. `run_id`: `s03-cleanroom-20260226-a`
2. base branch for new packet worktrees: `origin/integration/cleanup-20260226`
3. integration authority: `validator-release` only
4. deploy authority in this phase: disabled (cleanup freeze)

| Packet ID | Owner | Worktree | Branch | File Scope (globs) | Acceptance Gate | Status |
|---|---|---|---|---|---|---|
| S03-P01-GOV | codex53 | `F:/Dropbox/Projects/BEI-ERP-agent-codex53` | `agent/codex53-audit-followup-20260226` | `docs/plans/sprint-03-integration-backbone.md`, `hrms/api/erp_sync.py`, `hrms/utils/**`, `docs/testing/**` | governance/rbac/idempotency spec approved | IN_PROGRESS |
| S03-P02-SYNC-ARINV | codex53 | `F:/Dropbox/Projects/BEI-ERP-agent-codex53` | `agent/codex53-audit-followup-20260226` | `hrms/api/erp_sync.py`, `hrms/tests/test_erp_sync.py` | L1/L3 + Frappe write checks for GAP-006/007 | IN_PROGRESS |
| S03-P02-SYNC-COAAPBANK | codex53 | `F:/Dropbox/Projects/BEI-ERP-agent-codex53` | `agent/codex53-audit-followup-20260226` | `hrms/api/erp_sync.py`, `hrms/tests/test_erp_sync.py` | L1/L3 + Frappe write checks for GAP-008/009/025 + `sync_supplier_soa` | IN_PROGRESS |
| S03-P03-ALERTING | codex53 | `F:/Dropbox/Projects/BEI-ERP-agent-codex53` | `agent/codex53-audit-followup-20260226` | `hrms/services/sheets_receiver/**`, `hrms/services/sheets_receiver/notifications.py` | forced-failure alert dispatch proof (GAP-046) | IN_PROGRESS |
| S03-P04-BILLING-EXC | codex53 | `F:/Dropbox/Projects/BEI-ERP-agent-codex53` | `agent/codex53-audit-followup-20260226` | `hrms/api/dispatch.py`, `frontend/src/views/dispatch/DeliveryStop.vue`, `hrms/tests/test_dispatch_pre_delivery.py` | blocked-without-approval and approved-exception proofs | IN_PROGRESS |
| S03-P05-RELEASE-QA | validator-release | `F:/Dropbox/Projects/BEI-ERP-orchestrator` | `integration/cleanup-20260226` | `docs/testing/scenarios/**`, `docs/testing/reports/**`, release checklist docs | preflight + rollback + L4 evidence complete | READY |

### 3.4.1 Stage 01 Immediate Execution Checklist

- [x] Publish packet manifest + ownership to handoff thread.
- [x] Finalize idempotency key map for GAP-006/007/008/009/025.
- [x] Finalize transaction/compensation model (`savepoint` + rollback path) per lane.
- [x] Finalize sync endpoint RBAC/authorization matrix and deny tests (local unit coverage in `hrms/tests/test_erp_sync.py`).
- [x] Confirm cleanroom assignment matrix and single-writer file ownership for all packets.

Stage 01 note (2026-02-26): RBAC guards are implemented in code and local allow/deny unit tests are now captured. Frappe-integrated RBAC evidence is still pending for final closure.

## 4) Technical Deliverables

1. Five sync lanes write real ERP records instead of logging-only.
2. Sync failures surface in chat alerting with actionable context.
3. POS upload values persist and feed reporting.
4. Delivery confirmation creates billing by default, with auditable pre-delivery exception path requiring dual approval (Daymae/CPO + Butch/CFO).

## 5) Test and Verification Gates

Minimum before close:

1. L1 sync and store-ops API checks pass with no new hard fail.
2. L2 affected dashboards/pages pass.
3. L3 reruns for affected modules pass.
4. Frappe checks confirm:
   - created/updated records for AR/AP/COA/inventory/bank syncs
   - `confirm_delivery` creates billing record with correct links
   - pre-delivery attempt without dual approval is blocked and logged
   - approved pre-delivery exception creates billing with approval trace
   - alert is emitted on forced sync failure test

Evidence locations:

- `output/l1/runs/`
- `output/l2/runs/`
- `output/l3/runs/`
- `output/l4/runs/sprint-03-integration-backbone/`
- `docs/testing/reports/`

Mandatory evidence bundle per gap:

1. Source input sample and resulting Frappe write evidence.
2. Idempotency/duplicate guard proof where applicable.
3. Alerting proof (for GAP-046).
4. Roll-forward and rollback validation notes.

## 6) Deployment and Rollback

Cleanroom override (effective while branch target is `integration/cleanup-20260226`):

1. Deployment actions are frozen for builder agents in this sprint lane.
2. No `workflow_dispatch`, no merge to `production`, and no direct merge to `main` from worker branches.
3. Backend/frontend deploy commands below are retained as post-cleanroom reference only.

1. Deploy sequence:
   - Batch A: Sync write-path changes (GAP-006/007/008/009/025)
   - Batch B: Alerting and operational fixes (GAP-046/022/092)
2. Keep feature flags or safe guards for sync write activation where possible.
3. If write-path regression occurs, disable affected sync lane and preserve alerting.

Recommended execution commands:

1. Backend deploy with full build:
```bash
gh workflow run build-and-deploy.yml --ref production -f skip_build=false -f run_migrate=true -f no_cache=true
```
2. Monitor deployment:
```bash
gh run list --workflow "Build and Deploy Frappe HRMS" --limit 5
gh run watch <run-id>
```
3. Frontend deploy (if POS/trip pages changed):
```powershell
pwsh -File scripts/deploy_frontend.ps1
```
4. Rollback:
   - isolate failed sync lane and revert only impacted batch commit(s);
   - redeploy and rerun sync contract checks before reopening flow.

### 6.2 Sprint 03 Preflight, Migration Order, and Compensation Rollback (B-08)

Preflight dependency gate (must pass before any deployment bundle):

1. Verify `AUDIT-01..AUDIT-10` status table has no `OPEN` blockers scheduled in the target bundle.
2. Confirm all Sprint 03 sync endpoints are auth-guarded and callable by integration token/user only.
3. Confirm mandatory scenario bundle includes:
   - `docs/testing/scenarios/flows/sprint-03-integration-backbone.md`
   - L4 run artifact root: `output/l4/runs/sprint-03-integration-backbone/<run-id>/`
4. Confirm cleanroom branch target and release owner:
   - worker PR target: `integration/cleanup-20260226`
   - release authority: `validator-release`

Migration/deploy order:

1. Backend code deploy (sync lanes + alerting + dispatch policy).
2. Run migrations/schema updates (if any) before enabling traffic to modified sync lanes.
3. Execute L1 smoke for scoped endpoints.
4. Execute L3/L4 scenario bundle for Sprint 03 flow file.
5. Promote bundle only if all scoped checks pass.

Compensation rollback steps:

1. Disable the affected lane by reverting scoped commit(s) only (no broad reset).
2. Re-run deploy with reverted bundle.
3. Replay idempotent sync payload for impacted lane to verify no duplicate writes.
4. Validate stop-level billing references for affected trips; cancel and recreate only impacted billing records with trace notes.
5. Publish rollback evidence links under `docs/testing/reports/` and `output/l4/runs/sprint-03-integration-backbone/<rollback-run-id>/`.

### 6.1 Cleanroom Worktree + Commit Protocol (MANDATORY, 2026-02-26)

1. Root repository is read-only for git write operations:
   - `F:/Dropbox/Projects/BEI-ERP`
   - Prohibited there: `git add`, `git commit`, `git reset`, `git clean`, `git checkout`.
2. Each agent must use a dedicated clean worktree:
   - Base: `origin/integration/cleanup-20260226`
   - One agent = one branch = one worktree (no shared worktree).
3. Branch/PR restrictions during cleanroom:
   - Builders push branch only (no deploy).
   - PR target must be `integration/cleanup-20260226`.
4. Protected paths (do not edit unless explicitly assigned):
   - `data/**`
   - `archive/worktree-recovery/**`
   - `output/worktree-snapshots/**`
   - `docs/plans/2026-02-26-worktree-clean-room-consolidation-plan.md`
   - `scripts/git/no_loss_worktree_snapshot.ps1`
5. Clean-start requirement:
   - If worktree is not clean at start, stop and report before coding.
6. Commit hygiene:
   - Small scoped commits only.
   - Push after each scoped commit.
   - Handoff must include exact changed file paths.
7. Agent setup template:
```powershell
$ORCH='F:/Dropbox/Projects/BEI-ERP-orchestrator'
$WT='F:/Dropbox/Projects/BEI-ERP-agent-<name>'
$BR='agent/<name>-<task>-20260226'
git -C $ORCH fetch origin --prune
git -C $ORCH worktree add $WT -b $BR origin/integration/cleanup-20260226
git -C $WT status --porcelain   # must be empty
```

## 7) Exit Criteria

1. All 8 gaps moved to DONE or explicitly blocked with root-cause memo.
2. No sync lane remains log-only for scoped features.
3. Failure alerting works for forced-error cases.
4. Trip to delivery-billing automation works without manual intervention.

## 7.1 NO-GO Conditions (Sprint 03)

Release is NO-GO if any is true:

1. Any scoped gap has `Status=IN_PROGRESS` or `BLOCKED-NEEDS-CEO`.
2. Any scoped sync lane remains log-only.
3. Any affected L2 route fails.
4. Any affected L3 scenario fails.
5. Alerting verification for GAP-046 is missing or failed.
6. Any cleanroom protocol violation occurs (root git writes, shared worktree, or wrong PR target).
7. Any deploy action is attempted from a builder branch during cleanup freeze.
8. Protected paths are modified without explicit assignment.

## 8) Sprint Risk Register

| Risk | Trigger | Mitigation | Steward |
|---|---|---|---|
| Duplicate writes from sync retries | repeated runs create duplicate records | add idempotency key checks and duplicate assertions | Platform Integrations |
| Partial sync success hidden from operators | some entities write, some fail silently | enforce per-entity status + alert thresholds | Platform Integrations |
| POS fix breaks historical parsing | old file variants fail | include regression samples from prior uploads | Store Operations |
| Trip billing hook fires twice | duplicate billing entries | enforce uniqueness guard on trip-billing link | Supply Chain |

## 9) Scope Changes Log

| Change ID | Gap ID | Change Type (add/remove/swap) | Reason | Approver | Impact |
|---|---|---|---|---|---|
| S03-CHG-001 | - | - | - | - | - |

## 10) Execution Evidence Ledger

| Gap ID | L1 Evidence | L2 Evidence | L3 Evidence | Frappe Verification | Release/Deploy Ref | Status |
|---|---|---|---|---|---|---|
| GAP-006 | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-006-ar-aging.json` | `n/a (API/runtime evidence scope)` | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-006-ar-aging.json` | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-006-ar-aging.json` | `output/agent-runs/s03-integrated-20260226-212447-codex53/RUN_STATUS.md` | DONE |
| GAP-007 | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-007-inventory.json` | `n/a (API/runtime evidence scope)` | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-007-inventory.json` | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-007-inventory.json` | `output/agent-runs/s03-integrated-20260226-212447-codex53/RUN_STATUS.md` | BLOCKED |
| GAP-008 | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-008-coa.json` | `n/a (API/runtime evidence scope)` | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-008-coa.json` | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-008-coa.json` | `output/agent-runs/s03-integrated-20260226-212447-codex53/RUN_STATUS.md` | BLOCKED |
| GAP-009 | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-009-ap-supplier-soa.json` | `n/a (API/runtime evidence scope)` | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-009-ap-supplier-soa.json` | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-009-ap-supplier-soa.json` | `output/agent-runs/s03-integrated-20260226-212447-codex53/RUN_STATUS.md` | BLOCKED |
| GAP-025 | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-025-bank-sync.json` | `n/a (API/runtime evidence scope)` | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-025-bank-sync.json` | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-025-bank-sync.json` | `output/agent-runs/s03-integrated-20260226-212447-codex53/RUN_STATUS.md` | BLOCKED |
| GAP-046 | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-046-alert-proof.json` | `n/a (backend receiver runtime scope)` | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-046-alert-proof.json` | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-046-alert-proof.json` | `output/agent-runs/s03-integrated-20260226-212447-codex53/RUN_STATUS.md` | DONE |
| GAP-022 | `output/verify-open-first/20260225_220455/GAP-022_pos_gross_net_verify.json` | `n/a (API/data verification scope)` | `output/verify-open-first/20260225_220455/GAP-020_022_l3_store-ops.log` | `output/verify-open-first/20260225_220455/GAP-022_pos_gross_net_nonzero_check.json` | `docs/testing/reports/verify_open_first_20260225_220455.md` | DONE |
| GAP-092 | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-092-pre-delivery-billing.json` | `n/a (backend runtime scope)` | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-092-pre-delivery-billing.json` | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-092-pre-delivery-billing.json` | `output/agent-runs/s03-integrated-20260226-212447-codex53/RUN_STATUS.md` | BLOCKED |

## 10.1 Audit Blocker Closure Ledger (Implementation-Time)

| Audit ID | Packet | Owner Worktree/Branch | Evidence Link | Status |
|---|---|---|---|---|
| AUDIT-01 | S03-P02-SYNC-ARINV + S03-P02-SYNC-COAAPBANK | `F:/Dropbox/Projects/BEI-ERP-agent-codex53` / `agent/codex53-audit-followup-20260226` | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-006-ar-aging.json` + `S03-007-inventory.json` + `S03-008-coa.json` + `S03-009-ap-supplier-soa.json` + `S03-025-bank-sync.json` | PARTIAL |
| AUDIT-02 | S03-P02-SYNC-COAAPBANK | `F:/Dropbox/Projects/BEI-ERP-agent-codex53` / `agent/codex53-audit-followup-20260226` | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-009-ap-supplier-soa.json` | BLOCKED |
| AUDIT-03 | S03-P01-GOV + Stage 02 packets | `F:/Dropbox/Projects/BEI-ERP-agent-codex53` / `agent/codex53-audit-followup-20260226` | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-idempotency-replay.json` | BLOCKED |
| AUDIT-04 | S03-P01-GOV + Stage 02 packets | `F:/Dropbox/Projects/BEI-ERP-agent-codex53` / `agent/codex53-audit-followup-20260226` | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-rollback-probe.json` + `S03-rollback-drill.json` | PARTIAL |
| AUDIT-05 | S03-P01-GOV + Stage 02 packets | `F:/Dropbox/Projects/BEI-ERP-agent-codex53` / `agent/codex53-audit-followup-20260226` | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-RBAC-allow-deny.json` | DONE |
| AUDIT-06 | S03-P04-BILLING-EXC | `F:/Dropbox/Projects/BEI-ERP-agent-codex53` / `agent/codex53-audit-followup-20260226` | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-092-pre-delivery-billing.json` | BLOCKED |
| AUDIT-07 | S03-P03-ALERTING | `F:/Dropbox/Projects/BEI-ERP-agent-codex53` / `agent/codex53-audit-followup-20260226` | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-046-alert-proof.json` | DONE |
| AUDIT-08 | S03-P05-RELEASE-QA | `F:/Dropbox/Projects/BEI-ERP-agent-codex53` + `F:/Dropbox/Projects/BEI-ERP-orchestrator` | `docs/plans/sprint-03-integration-backbone.md#6.2` + `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-rollback-drill.json` | BLOCKED |
| AUDIT-09 | S03-P05-RELEASE-QA | `F:/Dropbox/Projects/BEI-ERP-agent-codex53` / `agent/codex53-audit-followup-20260226` | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-l4-bundle.json` + L4 run folder | PARTIAL |
| AUDIT-10 | S03-P01-GOV + S03-P05-RELEASE-QA | `F:/Dropbox/Projects/BEI-ERP-agent-codex53` + `F:/Dropbox/Projects/BEI-ERP-orchestrator` | `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/S03-AUDIT-10-governance.json` + Section `6.1` cleanroom protocol | DONE |

## 11) Sprint 03 Sign-Off Matrix

| Role | Responsibility | Sign-Off Required |
|---|---|---|
| Platform/Store/Supply Validation | contract correctness and business acceptance | yes |
| Engineering | implementation integrity and dependency checks | yes |
| QA | evidence completeness and pass thresholds | yes |
| Release Validation | deploy/rollback readiness | yes |

## 12) Audit Blocker Implementation Addendum (2026-02-26)

### 12.1 Verified Blocker Baseline

Sprint 03 is gated by the rerun audit package:

1. `output/plan-audit/sprint-03-integration-backbone-rerun-20260226_171906/code_verification.md`
2. `output/plan-audit/sprint-03-integration-backbone-rerun-20260226_171906/glm_verification.md`
3. `output/plan-audit/sprint-03-integration-backbone-rerun-20260226_171906/verified_blockers.md`
4. `output/plan-audit/sprint-03-integration-backbone-rerun-20260226_171906/glm_verification_post_patch_decisions.md` (post-hardening rerun, `--parallel 3`)
5. `output/plan-audit/sprint-03-integration-backbone-rerun-20260226_171906/glm_verification_post_patch_v2_decisions.md` (post-B07/B06/B08/B09 rerun, `--parallel 3`)
6. `output/plan-audit/sprint-03-integration-backbone-rerun-20260226_171906/glm_verification_post_patch_v3_decisions.md` (post-frontend+local-evidence rerun, `--parallel 3`)

Rerun status progression:

1. Baseline (`glm_verification.md`): `B-01..B-10` all `SUPPORTED`.
2. Post-patch v2 (`glm_verification_post_patch_v2_decisions.md`): mixed `SUPPORTED/PARTIAL/CONTRADICTED`.
3. Post-patch v3 (`glm_verification_post_patch_v3_decisions.md`): `SUPPORTED=7`, `CONTRADICTED=3` (B-08/B-09/B-10 now contradicted by added plan governance/evidence entries).

### 12.2 Mandatory Blocker Closure Work Packages

| Audit ID | Blocker Summary | Required Implementation Action | Stage Target | Closure Evidence |
|---|---|---|---|---|
| AUDIT-01 (B-01) | GAP-006/007/008/009/025 remain log-only | Implement write-path services for all 5 lanes with create/update behavior and duplicate-safe writes | Stage 02 | lane-specific Frappe record proofs + L3 logs |
| AUDIT-02 (B-02) | `supplier_soa` route configured but handler missing | Implement `sync_supplier_soa` handler or remove route from config until implemented | Stage 02 | endpoint call success + write proof |
| AUDIT-03 (B-03) | Missing enforceable idempotency model | Add per-lane idempotency key strategy + DB-level uniqueness constraints | Stage 01 + Stage 02 | schema/migration ref + duplicate replay test |
| AUDIT-04 (B-04) | Missing transaction/compensation control | Add transaction boundaries (`savepoint`) and rollback/compensation path per lane | Stage 01 + Stage 02 | forced-failure recovery evidence |
| AUDIT-05 (B-05) | Missing explicit sync endpoint authorization | Add role/permission guards for all whitelisted sync methods | Stage 01 + Stage 02 | RBAC allow/deny L3 tests |
| AUDIT-06 (B-06) | GAP-092 exception enforcement incomplete | Implement pre-delivery dual-approval exception flow (backend + UI + policy checks) | Stage 04 | blocked-without-approval + allowed-with-approval proofs |
| AUDIT-07 (B-07) | GAP-046 sheets-receiver critical alert path incomplete | Replace TODO/disabled paths with real-time critical alert dispatch + escalation metadata | Stage 03 | forced-failure alert payload proof |
| AUDIT-08 (B-08) | Deployment hardening gaps | Add explicit preflight checklist, migration order, and data-compensation rollback runbook | Stage 05 | release checklist + rollback drill evidence |
| AUDIT-09 (B-09) | QA hardening gaps for scoped sync lanes | Add GAP-specific scenarios for 006/007/008/009/025/046/092 and explicit L4 artifact path | Stage 05 | scenario registry refs + `output/l4/runs/` evidence |
| AUDIT-10 (B-10) | Parallel governance under-specified | Enforce cleanroom governance: one-agent-one-worktree, PR target lock (`integration/cleanup-20260226`), protected-path guard, clean-start check, and commit hygiene with handoff file paths | Stage 01 + Stage 05 | orchestration matrix + owner sign-off |

### 12.3 Execution Controls Added

1. Stage 01 cannot close until AUDIT-03, AUDIT-04, AUDIT-05, and governance design from AUDIT-10 are documented and reviewed.
2. Stage 02 cannot close while any scoped sync lane remains logging-only.
3. Stage 03 cannot close until GAP-046 real-time alerting path is proven end-to-end.
4. Stage 04 cannot close until dual-approval pre-delivery exception path is enforced and tested.
5. Stage 05 cannot close until deployment preflight, rollback compensation, and GAP-specific L4 evidence bundle are complete.
6. Stage 05 cannot close if any cleanroom protocol breach is unresolved.

### 12.4 GO/NO-GO Gate Update

NO-GO if any of the following is true:

1. Any `AUDIT-01..AUDIT-10` work package is open.
2. `verified_blockers.md` contains unresolved CRITICAL entries.
3. L4 artifact path for scoped gaps is missing.
4. Any worker branch bypasses PR target `integration/cleanup-20260226` during cleanup phase.
5. Any deploy/workflow dispatch is executed by builder branches during cleanup freeze.

### 12.5 Blocker Status Update (Post Patch, 2026-02-26)

| Blocker | Current Status | Post-Patch Notes | Remaining Closure Requirement |
|---|---|---|---|
| B-01 / AUDIT-01 | PARTIAL | Integrated run `s03-integrated-20260226-212447-codex53` produced mixed lane outcomes: GAP-006 runtime check passed, while GAP-007/008/009/025 lacked concrete Frappe record write evidence (`S03-007-inventory.json`, `S03-008-coa.json`, `S03-009-ap-supplier-soa.json`, `S03-025-bank-sync.json`). | Deploy/align runtime code so all five lanes produce verifiable records for run-generated identifiers. |
| B-02 / AUDIT-02 | BLOCKED | Runtime method `hrms.api.erp_sync.sync_supplier_soa` is missing (`ValidationError` in `S03-009-ap-supplier-soa.json`). | Deploy runtime containing `sync_supplier_soa` and rerun supplier SOA integrated proof. |
| B-03 / AUDIT-03 | BLOCKED | `S03-idempotency-replay.json` is not closable because write artifacts for COA/AP/Bank lanes were not materialized despite success counters. | After runtime alignment, rerun duplicate replay with record-level count assertions. |
| B-04 / AUDIT-04 | PARTIAL | `S03-rollback-probe.json` confirms no residue on forced invalid payload, but `S03-rollback-drill.json` has no reversible created artifacts in this run. | Run rollback drill against concrete created records and capture successful compensation steps. |
| B-05 / AUDIT-05 | DONE | Integrated RBAC allow/deny runtime proof completed in `S03-RBAC-allow-deny.json`. | None. |
| B-06 / AUDIT-06 | BLOCKED | Runtime methods `hrms.api.dispatch.create_pre_delivery_billing` and `hrms.api.dispatch.request_pre_delivery_billing_exception` are missing (`S03-092-pre-delivery-billing.json`). | Deploy runtime with GAP-092 API methods and rerun denied+approved flow proof. |
| B-07 / AUDIT-07 | DONE | Forced critical alert dispatch and cleanup succeeded in test Chat space (`S03-046-alert-proof.json`). | None. |
| B-08 / AUDIT-08 | BLOCKED | Runbook exists (Section `6.2`), but executable rollback drill did not have created artifacts to revert (`S03-rollback-drill.json`). | Execute and evidence a non-empty rollback drill. |
| B-09 / AUDIT-09 | PARTIAL | Full L4 bundle is present (`S03-l4-bundle.json`), but scenario outcome remains mixed due unresolved runtime blockers. | Rerun full bundle after runtime blockers are cleared; require all scoped checks pass. |
| B-10 / AUDIT-10 | DONE | Governance closure proven via `S03-AUDIT-10-governance.json` and enforced cleanroom protocol in Section `6.1`. | None. |

### 12.6 Local Closure Evidence Update (2026-02-26, codex53)

Local blocker-proof bundle generated:

1. `output/l4/runs/sprint-03-integration-backbone/s03-local-20260226-codex53-a/README.md`
2. `output/l4/runs/sprint-03-integration-backbone/s03-local-20260226-codex53-a/unit_test_erp_sync.log`
3. `output/l4/runs/sprint-03-integration-backbone/s03-local-20260226-codex53-a/unit_test_delivery_billing_policy.log`
4. `output/l4/runs/sprint-03-integration-backbone/s03-local-20260226-codex53-a/unit_test_dispatch_pre_delivery.log`
5. `output/l4/runs/sprint-03-integration-backbone/s03-local-20260226-codex53-a/py_compile.log`

Scope note:

1. These artifacts satisfy implementation-time local evidence requirements for code paths and guards.
2. Final gate still requires integrated Frappe + receiver runtime runs for release closure.

### 12.7 Integrated Closure Run (2026-02-26, codex53)

Integrated closure run artifacts:

1. `output/agent-runs/s03-integrated-20260226-212447-codex53/integrated_evidence_summary.json`
2. `output/agent-runs/s03-integrated-20260226-212447-codex53/RUN_STATUS.md`
3. `output/agent-runs/s03-integrated-20260226-212447-codex53/RUN_STATUS.json`
4. `output/l4/runs/sprint-03-integration-backbone/s03-integrated-20260226-212447-codex53/`

Run result:

1. `NO-GO` (runtime blockers remain for GAP-007/008/009/025/092 + rollback drill).
2. `DONE` closures in this run: RBAC allow/deny, GAP-046 alert proof, full L4 bundle, AUDIT-10 governance closure.

