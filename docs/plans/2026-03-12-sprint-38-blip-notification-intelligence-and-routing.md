# Sprint 38 Blip Notification Intelligence and Routing Plan

- canonical_sprint_id: `S038`
- display_name: `Sprint 38`
- status: `Done (Completed 2026-03-13; PR #220 live, PR #222 receiver topology live, PR #224 PHT business-date fix live, full E2E certification passed)`
- owner: `Control Cell`
- date_pht: `2026-03-12`
- policy_ref: `docs/plans/SPRINT_NUMBERING_POLICY.md`
- previous_sprint_ref: `docs/plans/2026-03-12-sprint-37-warehouse-commissary-store-handoff-alignment.md`
- scope_ref_1: `docs/plans/2026-03-10-sprint-31-store-inventory-import-and-shadow-sync.md`
- scope_ref_2: `docs/plans/2026-03-09-sprint-28-discount-monitoring-ux-incident-workspace.md`
- scope_ref_3: `docs/plans/2026-03-11-ian-warehouse-inventory-baseline-sync.md`
- required_skill_workflows:
  - `write-plan-bei-erp`
  - `execute-plan-bei-erp`
  - `chat-bei-erp`
  - `google-bei-erp`
  - `frappe-expert-bei-erp`
  - `deploy-frappe-bei-erp`
  - `l1-api-check-bei-erp`

## Agent Boot Sequence
1. Read this plan fully.
2. Read `docs/plans/SPRINT_REGISTRY.md`.
3. Read `tmp/2026-03-12_blip_notifications_audit/summary.md`.
4. Read the live source files named in this plan before touching code:
   - `hrms/api/google_chat.py`
   - `hrms/utils/chat_space_lockdown.py`
   - `hrms/services/sheets_receiver/notifications.py`
   - `hrms/api/projects.py`
   - `hrms/hr/doctype/bei_maintenance_request/bei_maintenance_request.py`
   - `hrms/api/discount_abuse.py`
   - `pyproject.toml`
   - `hrms/tests/test_google_chat_notification_routing.py`
   - `hrms/tests/test_sheets_receiver_notifications.py`
   - `hrms/hooks.py`
5. Produce the notification family inventory and routing matrix before rewriting any notification copy or cron behavior.

## Execution Authority
This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

## Objective
Make `! Blip Notifications` feel like an AI operations brief instead of a raw event sink. Replace spammy raw event bursts with actionable summaries that explain:

1. what happened,
2. why it matters,
3. who owns the next action,
4. what Blip recommends doing now,
5. what evidence or document link supports the recommendation.

The implementation target is a hybrid model:

- deterministic event collection and risk classification,
- structured action-item generation per family,
- optional AI phrasing/polish after facts are locked,
- non-blocking fallback summaries when AI enrichment is unavailable.

## Evidence Snapshot
The current space behavior is evidenced by a live chat audit, not assumption:

1. `tmp/2026-03-12_blip_notifications_audit/messages.json` shows `442` bot messages in `spaces/AAQABiNmpBg` since `2026-03-10T00:00:00Z`.
2. The largest high-noise families in that window were:
   - `80` store-order approved cards
   - `61` urgent SLA breach messages
   - `61` high SLA breach messages
   - `61` normal SLA breach messages
   - `53` maintenance status updates
   - `22` sheets sync critical alerts
   - `21` new store order notices
   - `20` approval queue notices
   - `13` duplicate store-order approved text notices
3. Current notification producers write directly to chat using raw text from source modules such as:
   - `hrms/api/projects.py::check_sla_violations`
   - `hrms/hr/doctype/bei_maintenance_request/bei_maintenance_request.py::_notify_maintenance_event`
   - `hrms/api/google_chat.py::on_approval_queue_insert`
   - `hrms/api/google_chat.py::on_store_order_update`
   - `hrms/services/sheets_receiver/notifications.py`
   - `hrms/api/discount_abuse.py::_build_critical_notification_message`
4. `hrms/utils/chat_space_lockdown.py` currently reroutes many outbound destinations into `! Blip Notifications`, which means unrelated systems share the same destination even when they serve different audiences.
5. Existing Blip conversational AI remains a separate service and is not the execution venue for Sprint 38 outbound summaries.

## Target Experience Contract
Every in-scope Blip notification must resolve into one of four delivery classes:

1. `critical_immediate`
   - Sent immediately.
   - Used only when a human should act now or a production flow is blocked.
2. `action_digest`
   - Group multiple related events into one operator summary.
   - Used for approval queues, SLA backlogs, repeated row exceptions, and morning operational readiness.
3. `awareness_digest`
   - Informational summary with no immediate human action required.
   - Must say `No action needed` explicitly when that is the correct disposition.
4. `suppressed_or_rerouted`
   - Event is either not worthy of `! Blip Notifications`, or belongs in a dedicated space.

Each delivered message must contain, either in text or card form:

- `Summary`
- `Why this matters`
- `Action now`
- `Owner`
- `Recommended fix`
- `Evidence / source link`
- `Urgency`

## Duplication Audit

| Workstream | Existing Asset | Classification | Plan Decision |
|---|---|---|---|
| Shared Google Chat sender | `hrms/api/google_chat.py::send_message_to_space` | `[EXTEND]` | Keep as final transport; do not let business modules continue composing final raw message text directly |
| Chat routing guard | `hrms/utils/chat_space_lockdown.py` | `[EXTEND]` | Reuse as the last-mile gate, but add a family-aware routing matrix instead of one catch-all sink |
| Sheets sync critical alerts | `hrms/services/sheets_receiver/notifications.py` | `[EXTEND]` | Convert raw sheet alerts into structured action summaries and severity-based routing |
| Maintenance SLA alerts | `hrms/api/projects.py::check_sla_violations` | `[EXTEND]` | Replace hourly per-priority spam with grouped backlog/action digests |
| Maintenance lifecycle alerts | `hrms/hr/doctype/bei_maintenance_request/bei_maintenance_request.py` | `[EXTEND]` | Summarize only action-relevant transitions; suppress noisy status churn |
| Approval queue + store order notifications | `hrms/api/google_chat.py::{on_approval_queue_insert,on_store_order_update}` | `[EXTEND]` | Remove duplicate event styles and replace with action-focused approval summaries |
| Discount digest | `hrms/api/discount_abuse.py::_build_critical_notification_message` | `[EXTEND]` | Preserve deterministic findings, add owner/recommended action layer |
| Frappe app AI dependencies | `pyproject.toml` | `[EXTEND]` | Use existing Frappe runtime dependencies for optional copy polish; do not introduce a second execution venue |
| Existing Blip AI stack | `hrms/services/blip/ai/**` | `[SKIP]` | Keep out of Sprint 38 execution path; use only as tone reference if needed |
| Central notification family inventory + policy registry | none found | `[BUILD]` | Build a canonical policy layer for all in-scope families |
| Deduplication / aggregation / action-item renderer | none found | `[BUILD]` | Build a shared notification intelligence layer before final send |
| Direct raw-event sink in `! Blip Notifications` | current routing behavior | `[SKIP]` | Retire as the default operating model |

## In Scope
- Inventory all current chat-producing families that land in `! Blip Notifications`
- Build a notification family registry with:
  - delivery class
  - target space
  - dedup window
  - severity policy
  - owner mapping
  - required fields
- Introduce a shared structured event envelope before final send
- Build per-family summary adapters for the currently observed high-noise families:
  - sheets sync alerts
  - maintenance SLA breaches
  - maintenance lifecycle updates
  - approval queue alerts
  - store order approval / new-order alerts
  - discount audit alerts
  - morning readiness rollup families tied to inventory / procurement / warehouse sync
- Build the Frappe-local ingestion/sender contract for migrated families:
  - local Python callers use `send_notification_event(event: dict) -> bool`
  - standalone services use `hrms.api.google_chat.ingest_notification_event`
- Add action-item and recommended-fix generation rules per family
- Add routing and suppression controls so `! Blip Notifications` remains high-signal
- Preserve deterministic fact provenance and non-blocking business transactions
- Add tests and certification artifacts for each in-scope family

## Out of Scope
- Rebuilding the conversational Blip assistant end-to-end
- Replacing Google Chat with another channel
- Rewriting the business logic that creates the underlying source events, except where required to attach structured metadata
- Designing a full admin UI unless a minimal operator-facing settings surface is proven necessary
- Removing all digest-style notifications from all other spaces; this sprint is focused on `! Blip Notifications` and its contributing families
- Routing migrated families through the standalone `blip-assistant` service; Sprint 38 uses Frappe as the notification-intelligence execution venue

## Failure Patterns To Prevent
1. `catch_all_sink`: unrelated systems continue posting into one undifferentiated space.
2. `raw_event_dump`: the final message mirrors source text instead of giving an operator brief.
3. `duplicate_signal`: the same event sends both card and text variants or multiple priority variants with no grouping.
4. `hallucinated_fix`: AI invents a cause or recommendation that is not grounded in the structured event data.
5. `hidden_blocker`: digesting delays or suppresses a truly urgent production issue.
6. `transaction_cascade`: a notification formatting failure blocks the source workflow.
7. `owner ambiguity`: a message says something is wrong but does not say who should act.
8. `traceability loss`: the human cannot click or identify the source record, sheet, or queue behind the recommendation.
9. `routing regression`: lockdown still forces everything into `! Blip Notifications` even after policy segmentation is defined.
10. `no_action_noise`: informational messages continue to page users without a clear action or explicit `No action needed`.

## Build Integrity Gates

| Gate | Requirement |
|---|---|
| `gate_family_inventory_locked` | every active in-scope notification family is inventoried with source file, trigger, and intended audience |
| `gate_sender_contract_locked` | migrated families use one explicit sender contract with family id, source ref, dedup key, and fallback text |
| `gate_policy_matrix_defined` | each family has a declared delivery class, routing target, dedup window, and suppression rule |
| `gate_action_contract_defined` | every delivered message shape includes summary, urgency, owner, action, recommendation, and evidence |
| `gate_traceability_defined` | every message links back to or names the source document, queue, or sheet clearly enough for follow-through |
| `gate_dedup_window_defined` | duplicate events from the same family have a deterministic coalescing policy |
| `gate_ai_fallback_defined` | if AI enrichment fails, a deterministic degraded summary still sends when policy requires delivery |
| `gate_non_blocking_delivery_defined` | notification failures never block the underlying source transaction or scheduled job |
| `gate_routing_matrix_defined` | `! Blip Notifications` and any secondary spaces have an explicit policy-backed routing map |
| `gate_runtime_topology_locked` | Frappe vs standalone-service execution venue is fixed and deployable before implementation begins |
| `gate_certified_manifest_locked` | the exact in-scope family manifest and exclusion register are defined before migration starts |
| `gate_vertical_slice_locked` | one named reference family is required to go green before broader family migration proceeds |

## Build Artifact Contract
Execution must produce and keep current:

- `output/agent-runs/S038-blip-notification-intelligence/RUN_STATUS.json`
- `output/agent-runs/S038-blip-notification-intelligence/RUN_SUMMARY.md`
- `output/agent-runs/S038-blip-notification-intelligence/reports/S038_NOTIFICATION_FAMILY_INVENTORY.csv`
- `output/agent-runs/S038-blip-notification-intelligence/reports/S038_CERTIFIED_FAMILY_MANIFEST.csv`
- `output/agent-runs/S038-blip-notification-intelligence/reports/S038_EXCLUSION_REGISTER.csv`
- `output/agent-runs/S038-blip-notification-intelligence/reports/S038_CHAT_ROUTING_MATRIX.csv`
- `output/agent-runs/S038-blip-notification-intelligence/reports/S038_DEPLOY_MATRIX.md`
- `output/agent-runs/S038-blip-notification-intelligence/reports/S038_MESSAGE_POLICY.md`
- `output/agent-runs/S038-blip-notification-intelligence/reports/S038_ACTION_ITEM_CONTRACT.md`
- `output/agent-runs/S038-blip-notification-intelligence/reports/S038_DEDUP_SUPPRESSION_RULES.csv`
- `output/agent-runs/S038-blip-notification-intelligence/reports/S038_TRACEABILITY_MATRIX.md`
- `output/agent-runs/S038-blip-notification-intelligence/reports/S038_PROMPT_AND_TEMPLATE_REGISTRY.md`
- `output/agent-runs/S038-blip-notification-intelligence/defects/S038_DEFECT_REGISTER.csv`
- `output/agent-runs/S038-blip-notification-intelligence/reports/S038_CERTIFICATION_REPORT.md`
- `output/agent-runs/S038-blip-notification-intelligence/reports/S038_SIGNOFF.md`

## Phase 0 Preconditions and Contract Lock

### Notification Policy Lock
1. The chosen architecture for this sprint is `hybrid deterministic facts + optional AI phrasing`.
2. AI is allowed to:
   - rewrite tone,
   - collapse facts into a human brief,
   - propose the next action from a predefined family policy.
3. AI is not allowed to:
   - invent root causes,
   - change counts,
   - hide blocking failures,
   - overwrite deterministic owner mapping,
   - send with no source evidence.
4. The final sender must still be deterministic and auditable.

### Sender Contract Lock (Phase 0A)
1. Sprint 38 introduces one canonical sender contract in Frappe:
   - local Python entrypoint: `send_notification_event(event: dict) -> bool`
   - standalone-service ingest endpoint: `hrms.api.google_chat.ingest_notification_event`
2. Required event fields for every migrated family:
   - `family`
   - `source_system`
   - `source_ref`
   - `severity`
   - `delivery_class`
   - `owner`
   - `dedup_key`
   - `facts`
   - `requested_space`
   - `fallback_text`
3. `send_message_to_space(space_name: str, message: str) -> bool` remains transport only and is not the business-facing API for migrated families.
4. Compatibility rule:
   - unmigrated callers may remain on the legacy raw-string path only if they are either outside the Sprint 38 manifest or listed in the exclusion register
   - a family cannot run mixed legacy and structured senders at the same time
5. Family identification method:
   - routing, dedup, and closeout are keyed by the required `family` field from the certified manifest; no family may infer identity from free-form message text

### AI Runtime Lock (Phase 0B)
1. Sprint 38 runs AI phrasing only inside the Frappe app runtime.
2. Standalone services such as `sheets-receiver` do not call external LLM providers directly in this sprint; they submit structured events to Frappe.
3. The existing standalone `blip-assistant` service is explicitly out of the Sprint 38 execution path.
4. Frappe may use existing app dependencies already present in `pyproject.toml` for optional copy polish, but deterministic summary generation is the primary path and the guaranteed fallback.
5. If the AI phrasing step errors, times out, or lacks credentials, the degraded deterministic summary sends instead when policy requires delivery.

### Certified Family Manifest Lock (Phase 0C)
Sprint 38 closeout is governed by an explicit family manifest, not the phrase "migrated families."

Certified in-scope families for Sprint 38 (`count = 8`):
1. `sheets_sync_critical`
2. `maintenance_sla_backlog`
3. `maintenance_status_update`
4. `approval_queue_new`
5. `store_order_new`
6. `store_order_approved`
7. `discount_critical_digest`
8. `morning_readiness_digest`

Known excluded families for Sprint 38 (must appear in `S038_EXCLUSION_REGISTER.csv` with owner + destination policy):
1. `meta_ads_digest`
2. `attendance_bridge_failure`
3. `biometric_daily_digest`
4. `unclassified_external_or_future_sender`

Closeout rule:
- Sprint 38 cannot be called complete until every in-scope family has a manifest row, routing row, fixture row, and representative live-send proof row.

### Routing Policy Lock
1. `! Blip Notifications` becomes the high-signal ops/exec space, not the default dump for every bot.
2. Families that are informational-only must either:
   - be rerouted to a dedicated space, or
   - be grouped into an awareness digest with an explicit `No action needed`.
3. The routing matrix must replace blanket catch-all behavior for in-scope families.
4. For migrated families emitted by `sheets-receiver`, routing policy lives in Frappe only; the receiver does not own final destination choice beyond delivering the structured event to Frappe.
5. Any fallback routing helper inside `hrms/services/sheets_receiver/notifications.py` remains legacy-only and must be bypassed or removed from the execution path for migrated families once they use `ingest_notification_event`.

### Message Contract Lock
Every in-scope message must expose the following structured fields before final rendering:

- `family`
- `severity`
- `summary`
- `why_it_matters`
- `action_now`
- `owner`
- `recommended_fix`
- `source_ref`
- `event_count`
- `dedup_key`
- `delivery_class`

## Deploy Matrix

| Deploy Order | Runtime | Code Owner | Why it changes in Sprint 38 | Deploy action / rebuild rule | Verification proof |
|---|---|---|---|---|---|
| `1` | `Frappe app` | `Control Cell / hrms repo` | canonical sender contract, ingest endpoint, routing policy, Frappe-native family adapters, optional AI phrasing, tests | normal Frappe deploy; full rebuild when Python code changes | `frappe.ping`, migrated-family fixture tests, one representative live send, log/error scan |
| `2` | `sheets-receiver` | `Control Cell / receiver host service` | `sheets_sync_critical` migrates from raw local alerting to structured event POST into Frappe | rebuild/restart receiver container on host after Frappe endpoint is live | `/health`, one structured ingest dry run, one representative live send through Frappe final sender |
| `3` | `blip-assistant` | `No Sprint 38 change owner required` | no Sprint 38 code changes | none | n/a |

Deploy ordering rule:
- `sheets-receiver` may not ship the migrated `sheets_sync_critical` path before the Frappe `ingest_notification_event` endpoint is deployed and verified.
- `blip-assistant` is not part of Sprint 38 release gating and must not be introduced as a hidden dependency during closeout.

## Vertical Slice First Rule
The mandatory reference slice for Sprint 38 is `sheets_sync_critical`.

It is the first family to go end-to-end because it proves the hardest cross-runtime path:

`sheets-receiver -> Frappe ingest_notification_event -> policy/dedup -> deterministic summary -> optional AI phrasing -> final Google Chat send`

No broader family migration is allowed until this slice is green with:
- one fixture pass,
- one degraded-fallback pass,
- one live-send verification,
- one deploy proof for both Frappe and receiver.

### No-Shell Implementation Rules
1. No visible outbound message may omit the owner and action state.
2. No duplicate card+text pair may exist for the same event unless the policy explicitly requires both and explains why.
3. No hourly spam triplet may remain when one grouped digest can represent the same state.
4. No AI-polished summary may be sent without deterministic facts attached first.
5. No business module may directly compose the final operator-facing text once it is migrated to the shared intelligence layer.

## Execution Workflow
- Test Python changes: `/local-frappe`
- Deploy changes: `/deploy-frappe`
- Full workflow: `/agent-kickoff` or `/execute-plan-bei-erp`
- Chat verification: `/chat`
- Runtime API verification: `/l1-api-check`

## Implementation Phases

### Phase 1 - Family Inventory and Routing Baseline
Goal: lock the actual current universe before code moves.

Tasks:
- Enumerate every active producer that lands in `! Blip Notifications`
- Classify each into `critical_immediate`, `action_digest`, `awareness_digest`, or `suppressed_or_rerouted`
- Identify duplicate families, multi-step families, and families currently rerouted by lockdown policy
- Produce the initial inventory, certified manifest, exclusion register, deploy matrix, and routing artifacts
- Lock `sheets_sync_critical` as the reference vertical slice before broader migration starts

### Phase 2 - Shared Notification Intelligence Layer
Goal: stop letting source modules write final operator text directly.

Tasks:
- Build the Frappe-local `send_notification_event(...)` contract and `ingest_notification_event` endpoint
- Build a shared structured event envelope and render contract
- Add shared dedup, aggregation, and suppression helpers
- Add family policy registry with owner mapping, recommended-fix rules, and routing target
- Preserve raw source metadata for traceability and degraded fallback

### Phase 3 - High-Noise Family Migration
Goal: migrate the worst offenders first.

Priority families:
1. Maintenance SLA backlog
2. Maintenance lifecycle status updates
3. Approval queue / store order workflow alerts
4. Sheets sync critical alerts
5. Discount critical digests

Per-family requirement:
- remove raw spam shape,
- define grouped summary policy,
- define owner and action mapping,
- define `No action needed` cases.

### Phase 4 - AI-Style Summary Rendering
Goal: make the output feel like an assistant without compromising factual integrity.

Tasks:
- Add deterministic summary builder per family
- Add optional Frappe-local AI phrasing layer using existing app dependencies already present in `pyproject.toml`
- Ensure AI only sees the structured fact packet, never raw uncontrolled context
- Add degraded deterministic fallback when AI is unavailable or timing out

### Phase 5 - Routing and Space Hygiene
Goal: ensure the right audience receives the right signal.

Tasks:
- Replace catch-all routing for migrated families with explicit matrix-based routing
- Keep `! Blip Notifications` for critical/actionable ops briefs
- Move informational-only or domain-specific digests to their intended spaces when policy allows
- Ensure the lockdown mechanism respects the new policy instead of flattening everything into one sink

### Phase 6 - Certification and Rollout
Goal: certify that the notification system is more useful, less noisy, and still reliable.

Tasks:
- Fixture-test every migrated family
- Verify no duplicate same-event sends remain
- Verify source workflows still succeed when notification delivery or AI phrasing fails
- Dry-run and live-run representative messages into a safe verification space
- Update canonical artifacts and signoff package

## Task Matrix

| Work Item | Classification | Target Files / Areas |
|---|---|---|
| Notification family inventory + routing matrix | `[BUILD]` | `output/agent-runs/S038-blip-notification-intelligence/reports/**` |
| Certified manifest + exclusion register | `[BUILD]` | `output/agent-runs/S038-blip-notification-intelligence/reports/**` |
| Frappe-local sender contract + ingest endpoint | `[BUILD]` | `hrms/api/google_chat.py` |
| Shared event envelope and renderer contract | `[BUILD]` | `hrms/api/google_chat.py`, `hrms/utils/**` |
| Family-aware routing matrix | `[EXTEND]` | `hrms/utils/chat_space_lockdown.py`, caller modules |
| Sheets sync summary upgrade | `[EXTEND]` | `hrms/services/sheets_receiver/notifications.py` |
| Maintenance SLA digest upgrade | `[EXTEND]` | `hrms/api/projects.py` |
| Maintenance status notification reduction | `[EXTEND]` | `hrms/hr/doctype/bei_maintenance_request/bei_maintenance_request.py` |
| Approval/store-order digest upgrade | `[EXTEND]` | `hrms/api/google_chat.py`, `hrms/api/store.py` |
| Discount digest summary upgrade | `[EXTEND]` | `hrms/api/discount_abuse.py` |
| Frappe-local AI phrasing/polish adapter | `[EXTEND]` | `hrms/api/**`, `hrms/utils/**`, app dependencies in `pyproject.toml` |
| Retain raw dump model | `[SKIP]` | not allowed for migrated families |

## Autonomous Execution Contract
- completion_condition:
  - all defined technical gates green
  - all canonical closeout artifacts updated
  - all 8 certified in-scope families emit structured action summaries instead of raw dumps
  - every excluded family row has an owner and routing disposition
  - final target state recorded as `technical_complete` or `production_live`
- stop_only_for:
  - missing credentials/access
  - destructive approval requiring explicit operator consent
  - genuine business-policy decision on routing ownership or destination spaces
  - direct conflict with unrelated in-flight changes
- continue_without_pause_through:
  - audit
  - execute
  - deploy
  - e2e
  - closeout
- blocker_policy:
  - programmatic -> fix and continue
  - repeated technical failure x3 -> grounded research, then continue
  - business-data/policy -> pause
  - unknown external sender outside repo -> document owner, isolate, continue on in-repo families
- signoff_authority: `single-owner`
- canonical_closeout_artifacts:
  - `output/agent-runs/S038-blip-notification-intelligence/RUN_STATUS.json`
  - `output/agent-runs/S038-blip-notification-intelligence/RUN_SUMMARY.md`
  - `output/agent-runs/S038-blip-notification-intelligence/reports/S038_CERTIFIED_FAMILY_MANIFEST.csv`
  - `output/agent-runs/S038-blip-notification-intelligence/reports/S038_EXCLUSION_REGISTER.csv`
  - `output/agent-runs/S038-blip-notification-intelligence/reports/S038_DEPLOY_MATRIX.md`
  - `output/agent-runs/S038-blip-notification-intelligence/reports/S038_CERTIFICATION_REPORT.md`
  - `output/agent-runs/S038-blip-notification-intelligence/defects/S038_DEFECT_REGISTER.csv`
  - `output/agent-runs/S038-blip-notification-intelligence/reports/S038_SIGNOFF.md`
  - `docs/plans/2026-03-12-sprint-38-blip-notification-intelligence-and-routing.md`
  - `docs/plans/SPRINT_REGISTRY.md`

## Status Reconciliation Contract
Whenever counts, blockers, stage, or certification status changes, update in the same work unit:
1. `RUN_STATUS.json`
2. `RUN_SUMMARY.md`
3. `S038_CERTIFICATION_REPORT.md`
4. `S038_DEFECT_REGISTER.csv`
5. `S038_NOTIFICATION_FAMILY_INVENTORY.csv`
6. `S038_CERTIFIED_FAMILY_MANIFEST.csv`
7. `S038_EXCLUSION_REGISTER.csv`
8. `S038_CHAT_ROUTING_MATRIX.csv`
9. `S038_DEPLOY_MATRIX.md`
10. this plan status line if the sprint state changes
11. `docs/plans/SPRINT_REGISTRY.md` if sprint status changes

## Signoff Model
- mode: `single-owner`
- approver_of_record: `Sam Karazi`
- signoff_artifact: `output/agent-runs/S038-blip-notification-intelligence/reports/S038_SIGNOFF.md`
- note: destination-space policy and acceptable signal/noise threshold are a single-owner operating decision; do not manufacture synthetic departmental approvals

## Certification Coverage Contract
- certified_universe:
  - in_scope_families (`count = 8`):
    - `sheets_sync_critical`
    - `maintenance_sla_backlog`
    - `maintenance_status_update`
    - `approval_queue_new`
    - `store_order_new`
    - `store_order_approved`
    - `discount_critical_digest`
    - `morning_readiness_digest`
  - excluded_families (`count = 4`):
    - `meta_ads_digest`
    - `attendance_bridge_failure`
    - `biometric_daily_digest`
    - `unclassified_external_or_future_sender`
  - runtimes:
    - `Frappe app`
    - `sheets-receiver`
  - degraded_fallback_paths: one per in-scope family
  - representative live sends: one per in-scope family
- closeout_zero_equations:
  - certified_manifest_unmapped = 0
  - certified_families_without_owner = 0
  - certified_families_without_recommended_fix = 0
  - duplicate_same_event_notifiers_in_certified_scope = 0
  - excluded_family_owner_missing = 0
  - cross_runtime_routing_drifts = 0
  - required_fixture_failures = 0
  - required_live_send_failures = 0
- allowed_skips:
  - only explicit policy-backed skips for families proven to be owned outside this repo or outside the migrated scope
- final_readiness_basis:
  - `S038_NOTIFICATION_FAMILY_INVENTORY.csv`
  - `S038_CHAT_ROUTING_MATRIX.csv`
  - `S038_MESSAGE_POLICY.md`
  - `S038_CERTIFICATION_REPORT.md`
  - `S038_SIGNOFF.md`
