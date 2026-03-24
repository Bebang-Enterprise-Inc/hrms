# Sprint Registry (Canonical SSOT)
**Last Updated:** 2026-03-24
**Policy:** `docs/plans/SPRINT_NUMBERING_POLICY.md`

## Branch & PR Reservation Rules

Every sprint MUST reserve a branch name and PR slot before code is written.

1. **Branch name format:** `s{number}-{slug}` (lowercase, hyphen-separated, from plan filename slug)
2. **Branch is reserved** when the sprint row is added to this registry
3. **Agent MUST `git checkout -b <reserved-branch>`** before writing any code — committing to production is FORBIDDEN
4. **PR number** is filled in once the agent creates the PR via `gh pr create`
5. **Two sprints MUST NOT share a branch or PR** — each sprint gets its own, even if they touch the same files
6. **Violation:** S099 committed directly to production without a branch (2026-03-24). This caused S099+S100 to merge in the same PR #321, violating independence.

## Canonical Sprint Timeline
| Canonical ID | Display | Branch | PR | Status | Primary Reference |
|---|---|---|---|---|---|
| `S001` | Sprint 01 | — | — | Done | `docs/plans/archived/2026-02-27-sprint-01-runtime-governance.md` |
| `S002` | Sprint 02 | — | — | Done | `docs/plans/archived/2026-02-27-sprint-02-finance-procurement-core.md` |
| `S003` | Sprint 03 | — | — | Done | `docs/plans/archived/2026-02-27-sprint-03-integration-backbone.md` |
| `S004` | Sprint 04 | — | — | Done | `docs/plans/archived/2026-02-27-sprint-04-business-capability-completion.md` |
| `S005` | Sprint 05 | — | — | Done | `docs/plans/archived/2026-02-27-sprint-05-hr-compliance-notifications.md` |
| `S006` | Sprint 06 | — | — | Done | `docs/plans/archived/2026-02-27-sprint-06-supervisor-projects-p1.md` |
| `S007` | Sprint 07 | — | — | Done | `docs/plans/archived/2026-02-27-sprint-07-supply-chain-p1.md` |
| `S008` | Sprint 08 | — | — | Done | `docs/plans/archived/2026-02-27-sprint-08-finance-procurement-reliability.md` |
| `S009` | Sprint 09 | — | — | Done | `docs/plans/archived/2026-02-27-sprint-09-hr-self-service-data-integrity.md` |
| `S010` | Sprint 10 | — | — | Done | `docs/plans/archived/2026-02-27-sprint-10-inventory-warehouse-consistency.md` |
| `S011` | Sprint 11 | — | — | Done | `docs/plans/archived/2026-02-27-sprint-11-store-ops-commissary-execution.md` |
| `S012` | Sprint 12 | — | — | Done | `docs/plans/archived/2026-02-27-sprint-12-platform-admin-hardening.md` |
| `S013` | Sprint 13 | — | — | Done | `docs/plans/archived/2026-02-27-sprint-13-projects-supervisor-automation.md` |
| `S014A` | Sprint 14 Lane A | — | — | Done | `docs/plans/archived/2026-02-28-sprint-14a-finance-config-closure.md` |
| `S014B` | Sprint 14 Lane B | — | — | Done | `docs/plans/archived/2026-02-28-sprint-14b-hr-leave-command-center-closure.md` |
| `S014C` | Sprint 14 Lane C | — | — | Done | `docs/plans/archived/2026-02-28-sprint-14c-commissary-production-logistics-closure.md` |
| `S015` | Sprint 15 | — | — | Done | `docs/plans/archived/2026-03-01-sprint-15-end-to-end-application-mapping-ssot-refresh.md` |
| `S016` | Sprint 16 | — | — | Done | `docs/plans/archived/2026-03-01-sprint-16-contract-stabilization-remediation.md` |
| `S017` | Sprint 17 | — | — | Done | `docs/plans/archived/2026-03-01-sprint-17-missing-endpoint-feature-completion.md` |
| `S018` | Sprint 18 | — | — | Done | `docs/plans/archived/2026-03-02-sprint-18-api-contract-backlog-remediation.md` |
| `S019` | Sprint 19 | — | — | Done (Archived 2026-03-02) | `docs/plans/archived/2026-03-02-sprint-19-demand-driven-store-ordering-reliability.md` |
| `S020` | Sprint 20 | — | — | Planned | `docs/plans/2026-03-02-sprint-20-stockout-risk-visibility-control-tower.md` |
| `S021` | Sprint 21 | — | — | In Progress | `docs/plans/2026-03-02-sprint-21-stockout-control-command.md` |
| `S022` | Sprint 22 | — | — | Planned | `docs/plans/2026-03-02-sprint-22-control-tower-operational-control.md` |
| `S023` | Sprint 23 | — | — | Planned (Superseded by lanes) | `docs/plans/archived/2026-03-03-sprint-23-open-brain-personal-memory-system.md` |
| `S023A` | Sprint 23 Lane A | — | — | Planned | `docs/plans/2026-03-03-sprint-23a-bei-brain-foundation-data.md` |
| `S023B` | Sprint 23 Lane B | — | — | Planned | `docs/plans/2026-03-03-sprint-23b-bei-brain-intelligence-layer.md` |
| `S023C` | Sprint 23 Lane C | — | — | Planned | `docs/plans/2026-03-03-sprint-23c-bei-brain-integration-hardening.md` |
| `S024` | Sprint 24 | — | — | Planned | `docs/plans/2026-03-03-sprint-24-adms-attendance-supabase-sync.md` |
| `S025` | Sprint 25 | — | — | Planned | `docs/plans/2026-03-03-sprint-25-control-tower-command-closure.md` |
| `S026` | Sprint 26 | — | — | Done (Closed 2026-03-09) | `docs/plans/2026-03-09-s026-full-surface-operational-readiness-final-consolidated-closeout.md` |
| `S027` | Sprint 27 | — | — | Done (Single-owner signoff 2026-03-11; 217 locked / live L4 green / ready for team use) | `docs/plans/2026-03-09-sprint-27-full-surface-e2e-l1-l4-operational-certification.md` |
| `S028` | Sprint 28 | — | — | Planned | `docs/plans/2026-03-09-sprint-28-discount-monitoring-ux-incident-workspace.md` |
| `S029` | Sprint 29 | — | — | Planned | `docs/plans/2026-03-09-sprint-29-discount-monitoring-finance-benchmark-foundation.md` |
| `S030` | Sprint 30 | — | — | Done (Completed 2026-03-09) | `docs/plans/2026-03-09-analytics-agent-10x-report.md` |
| `S031` | Sprint 31 | — | — | In Progress | `docs/plans/2026-03-10-sprint-31-store-inventory-import-and-shadow-sync.md` |
| `S032` | Sprint 32 | — | — | Planned | `docs/plans/2026-03-10-sprint-32-dual-repo-safe-clean-start.md` |
| `S033` | Sprint 33 | — | — | Partial (Phase 0 shipped 2026-03-11 via PRs #197-#203 + bei-tasks #99/#103; publish bridge live; remaining phases — attendance classification, missing-punch reports, scheduling UX — deferred to S043) | `docs/plans/2026-03-10-sprint-33-schedule-management-attendance-bridge.md` |
| `S034` | Sprint 34 | — | — | Done (Completed 2026-03-11; canonical my-bebang reference regenerated from current source) | `docs/plans/2026-03-11-sprint-34-my-bebang-reference-canonical-regeneration.md` |
| `S035` | Sprint 35 | — | — | Done (Completed 2026-03-13; strict L1/L2/L3/L4/payroll certification passed after HRMS payroll hotfix #216) | `docs/plans/2026-03-11-sprint-35-overtime-post-approval-operational-workflow.md` |
| `S036` | Sprint 36 | — | — | Planned | `docs/plans/2026-03-12-sprint-36-omnichannel-order-hub.md` |
| `S037` | Sprint 37 | — | — | Done (Completed 2026-03-14; final live heads hrms 0471cad199a9557d73c53b5322391609100c2aa8 and portal 7ccaa5df70b3c8fea4e6f742716d1ee7c72c6044; full production E2E passed; finance math fact-check passed; no open Sprint 37 defects remain) | `docs/plans/2026-03-12-sprint-37-warehouse-commissary-store-handoff-alignment.md` |
| `S038` | Sprint 38 | — | — | Done (Completed 2026-03-13; structured notification intelligence live, receiver topology fixed, PHT business-date correction live, full E2E certification passed) | `docs/plans/2026-03-12-sprint-38-blip-notification-intelligence-and-routing.md` |
| `S039` | Sprint 39 | — | — | In Progress | `docs/plans/2026-03-13-sprint-39-cfo-disciplinary-action-transition.md` |
| `S040` | Sprint 40 | — | — | Done (Completed 2026-03-14; semantic_search fixed, 56 memories seeded, RPCs deployed, Edge Functions verified) | `docs/plans/2026-03-14-sprint-40-bei-brain-repair-and-feeding.md` |
| `S041` | Sprint 41 | — | — | Done (Completed 2026-03-14; repos clean, 331K files removed, 137 branches deleted, Dropbox sync stabilized) | `docs/plans/2026-03-14-sprint-41-repo-dropbox-hygiene-cleanup.md` |
| `S042` | Sprint 42 | — | — | Phase 1 Done, Phase 2 Planned (13 new hires onboarded across 5 systems; ADMS scheduler planned) | `docs/plans/2026-03-14-sprint-42-new-hire-onboarding-adms-scheduler.md` |
| `S043` | Sprint 43 | — | — | GO (Audited 2026-03-14; 13 blockers resolved; Frappe auto-attendance architecture) | `docs/plans/2026-03-14-sprint-43-schedule-attendance-bridge-v2.md` |
| `S044` | Sprint 44 | — | — | Planned | `docs/plans/2026-03-14-sprint-44-bei-brain-gemini-embedding-2-migration.md` |

## Legacy Sprint Labels (Non-Canonical)
These documents contain sprint-like naming but are not part of the canonical sequence and must not be used as numbering anchors for new work.

| Legacy Label | File | Canonical Handling |
|---|---|---|
| `Sprint A` (patch list draft) | `docs/plans/2026-02-23-sprint-a-go-no-go-patch-list.md` | Pre-lane artifact for `S014A` |
| `Sprint 01` (domain plan) | `docs/plans/legacy-sprint-01-scm-commissary-warehouse.md` | Legacy domain sprint label |
| `Sprint 02` (domain plan) | `docs/plans/legacy-sprint-02-stock-counting-app.md` | Legacy domain sprint label |
| `Sprint 03` (domain plan) | `docs/plans/legacy-sprint-03-store-ops-inventory.md` | Legacy domain sprint label |
| `Sprint 04` (domain plan) | `docs/plans/legacy-sprint-04-maintenance.md` | Legacy domain sprint label |
| `Sprint 05` (domain plan) | `docs/plans/legacy-sprint-05-supervisor-tools.md` | Legacy domain sprint label |
| `Sprint 06` (domain plan) | `docs/plans/legacy-sprint-06-cross-cutting.md` | Legacy domain sprint label |
| `Sprint 07` (domain plan) | `docs/plans/legacy-sprint-07-hr-management.md` | Legacy domain sprint label |
| `Sprint 08` (domain plan) | `docs/plans/legacy-sprint-08-project-management.md` | Legacy domain sprint label |
| `Sprint 09` (domain plan) | `docs/plans/legacy-sprint-09-finance-procurement.md` | Legacy domain sprint label |
| `Store Ops Sprint 2` | `docs/plans/Completed/STORE_OPS_SPRINT2_PLAN_2026-02-07.md` | Separate historical track |
| `Geotagged Attendance Sprint 3` | `docs/plans/Completed/GEOTAGGED_ATTENDANCE_SPRINT3_GEOFENCE_UX_2026-02-10.md` | Separate historical track |
| `Geo-Attendance Sprint 3 E2E` | `docs/plans/archived/GEO_ATTENDANCE_SPRINT3_E2E_TEST_PLAN_2026-02-10.md` | Separate historical track |
| `S092` | Sprint 92 | `fix/s092-erp-testing-bugs` | #309 | COMPLETED 2026-03-23 — 7 backend + 4 frontend fixes + billing view-only fix. PRs: hrms#309, bei-tasks#225, bei-tasks#226. L3 regression 7/8 PASS. | `docs/plans/2026-03-22-sprint-92-erp-testing-bug-remediation.md` |
| `S095A` | Sprint 95 Lane A | — | — | COMPLETED 2026-03-23 — Agent SDK review backend, confidence gate, cost caps, PreToolUse hooks | `docs/plans/2026-03-23-sprint-95-governor-agent-sdk-upgrade.md` |
| `S095B` | Sprint 95 Lane B | — | — | COMPLETED 2026-03-23 — Builder subagent dispatch, worktree isolation, conflict resolver, default switched to agent-sdk | `docs/plans/2026-03-23-sprint-95-governor-agent-sdk-upgrade.md` |
| `S096` | Sprint 96 | — | — | COMPLETED 2026-03-23 — Two-layer release gate (deterministic + AI). Blocks merge without L3 evidence. Re-queue on fix push. | `docs/plans/2026-03-23-sprint-96-release-manager-gate.md` |
| `S097` | Sprint 97 | `fix/s097-commissary-handoff` | #317 | COMPLETED 2026-03-23 — Commissary handoff notification fix + grouped warehouse targets. PRs: hrms#317, bei-tasks#231. | `docs/plans/2026-03-23-sprint-97-commissary-handoff-fix.md` |
| `S098` | Sprint 98 | — | — | COMPLETED 2026-03-23 — Self-evolution memory: 5 lessons + 3 playbooks seeded, Reflexion + Procedural, prompt injection on startup | `docs/plans/2026-03-23-sprint-98-governor-self-evolution.md` |
| `S099` | Sprint 99 | **VIOLATION: no branch** | #321 (shared) | COMPLETED 2026-03-24 — SCM policy enforcement. **Committed directly to production — no branch created.** | `docs/plans/2026-03-23-sprint-99-scm-policy-enforcement.md` |
| `S100` | Sprint 100 | `s100-scm-operational-hardening` | #321 (shared) | MERGED 2026-03-24 — SCM operational hardening. **PR shared with S099 due to S099 branch violation.** | `docs/plans/2026-03-23-sprint-100-scm-operational-hardening.md` |
| `S101` | Sprint 101 | `s101-governor-review-intelligence` | #324 | COMPLETED — Governor AI Review Intelligence. L3 6/6 pass. Pre-checks (py_compile, Link defaults, decorators, lessons), streaming AI review, calculated confidence. | `docs/plans/2026-03-24-sprint-101-governor-review-intelligence.md` |

| `S102` | Sprint 102 | `s102-governor-agent-platform` | #327 | COMPLETED — Governor Agent Platform: REST API (10 endpoints), event bus, force-wake, self-diagnosis. L3 10/10 pass. | `docs/plans/2026-03-24-sprint-102-governor-agent-platform.md` |
| `S103` | Sprint 103 | `s103-labor-plan-bug-fixes` | #328, #233 | COMPLETED 2026-03-24 — Labor plan bug fixes: batch publish (Redis lock), compliance API (OR query + N+1 fix), approve/reject UI, ADMS verification, VL/SL dropdown. PRs: hrms#328, bei-tasks#233. L3 8/8 PASS. | `docs/plans/2026-03-24-sprint-103-labor-plan-bug-fixes.md` |
| `S104` | Sprint 104 | `s104-contracted-price-master` | #330,#333,#334 | COMPLETED 2026-03-24 — Contracted Price Master: 92 item prices, CPO price change approval, item onboarding control, override audit trail. L3 14/14 PASS. | `docs/plans/2026-03-24-sprint-104-contracted-price-master.md` |

| `S105` | Sprint 105 | `s105-production-deploy` | #340 | COMPLETED 2026-03-24 — Docker Build Acceleration: 12min->3.7min pipeline. Containerfile.fast overlay (54s build), GHCR push with zstd, consolidated 1-round SSM deploy (56s), cancel-in-progress concurrency. 3 production deploys validated. | `docs/plans/2026-03-24-sprint-105-docker-build-acceleration.md` |
| `S106` | Sprint 106 | `s106-leave-allocation-data-fix` | — (data fix, no PR) | COMPLETED 2026-03-24 — Fixed 1,557 Leave Allocations: total_leaves_allocated set, 1,557 Leave Ledger Entries created (8→1,565). All employees can now file VL/SL/EL. L3 5/5 PASS. | `docs/plans/2026-03-24-sprint-106-leave-allocation-data-fix.md` |

| `S107` | Sprint 107 | `s107-pr-form-frontend-fix` | #336 (hrms), #234 (bei-tasks) | COMPLETED 2026-03-24 — PR form frontend fix: departments from API ({value,label} with BEI filter), UOMs from API (29 vs 14 hardcoded), item_code onBlur price auto-fill, qty NaN fix. Luwi's "Could not find Department: Commissary" bug fixed. L3 6/6 PASS. | `docs/plans/2026-03-24-sprint-107-pr-form-frontend-fix.md` |

| `S108` | Sprint 108 | `s108-pr-form-luwi-fix` | #341 (hrms), #236 (bei-tasks) | COMPLETED 2026-03-24 — PR form fix: auto-set request_date/requested_by/date_required/purpose, map justification→purpose, item_code fallback, Sentry. L3 3/3 PASS (PR-2026-02968, PR-2026-02969). | `docs/plans/2026-03-24-sprint-108-procurement-module-hardening.md` |
| `S109` | Sprint 109 | `s109-procurement-full-audit` | — | PLANNED — Full procurement module hardening: Sentry for 93 endpoints, comprehensive L1/L2/L3 audit of all 107 endpoints + 36 pages, fix all bugs. | — |
| `S110` | Sprint 110 | `s108-leave-type-validation` | #339 (hrms), #235 (bei-tasks) | COMPLETED 2026-03-24 — Leave-overtime mutual exclusion guards, compensation eligibility tagging, leave dropdown filter, policy doc, reference doc. VL/SL/EL/LWOP lifecycle 27/27. OT-leave guards S11-S13 ALL PASS. L3 0 FAIL 0 SKIP. | `docs/plans/2026-03-24-sprint-108-leave-type-e2e-validation.md` |

| `S111` | Sprint 111 | `s111-submit-permission-hardening` | #343 | DEPLOYED 2026-03-24 — PR#343 merged. 15 commissary .submit() wraps + Sentry on 60 endpoints. Awaiting L3 in fresh session. | `docs/plans/2026-03-24-sprint-110-submit-permission-hardening.md` |

| `S112` | Sprint 112 | `s112-luwi-training-blockers` | — | GO — Close all blockers for Luwi's procurement training: OR Follow-up sidebar nav, Warehouse RBAC for GR, supplier_code auto-gen, empty error toast, payments 500, seed verified invoice. | `docs/plans/2026-03-24-sprint-112-luwi-training-blockers.md` |
| `S113` | Sprint 113 | `s113-payroll-command-center` | — | PLANNED — Payroll Command Center & Navigation: rebuild landing, Finance RBAC, Current Cutoff view, Review Output view, History + Comparison redirect. Read-only views. Replaces S083 scope 1/3. | `docs/plans/2026-03-24-sprint-113-payroll-command-center-navigation.md` |
| `S114` | Sprint 114 | `s114-payroll-compensation-sensitive` | — | PLANNED — Payroll Compensation & Sensitive Changes: compensation setup grid, dual-control approval for bank/statutory, effective dating, self-service intake. Replaces S083 scope 2/3. | `docs/plans/2026-03-24-sprint-114-payroll-compensation-sensitive-changes.md` |
| `S115` | Sprint 115 | `s115-payroll-processing-remittances` | — | PLANNED — Payroll Processing & Remittances: step wizard for payroll run, S076 blocker handling, government remittance views + export. Replaces S083 scope 3/3. | `docs/plans/2026-03-24-sprint-115-payroll-processing-remittances.md` |

## Next Sprint Reservation
1. Next canonical sprint ID to assign: `S116`.
2. Reserve branch name: `s{number}-{slug}` (fill slug from plan filename).
3. Create new sprint plan only after adding row here first.
4. **Agent MUST `git checkout -b <branch>` before writing any code.**

## Superseded Plans
| Original | Superseded By | Reason |
|----------|---------------|--------|
| S083 (never registered) | S113 + S114 + S115 | S083 was ~100 real work units (7 new routes, dual-control workflows, RBAC, dense grids). Split into 3 independent sprints of ~25-28 units each. Original plan at `docs/plans/2026-03-19-sprint-83-payroll-war-room-portal-operations-workspace.md`. |
