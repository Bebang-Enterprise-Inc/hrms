# S198 — Warehouse Receiving Flow Completion

```yaml
sprint: S198
status: PLANNED
planned_date: 2026-04-16
plan_file: docs/plans/2026-04-16-sprint-198-warehouse-receiving-flow-completion.md
depends_on:
  - S190 Phase 5 deployed (PR #566) — Company-first resolution
  - S192 hrms#583 MERGED — _normalize_store_name_for_route handles S188 children
  - S192 bei-tasks commit 2109e36 on main — OrderCard testid + react-aware Page Object
  - S196 — store-first naming and warehouse migration
completed_date: ""
execution_summary: ""
branch_hrms: s198-warehouse-receiving-flow-completion
branch_bei_tasks: s198-warehouse-receiving-queue-ui
hrms_pr: TBD
bei_tasks_pr: TBD
canonical_unit_total: 53
predecessor_fail_evidence: output/l3/s192/SUMMARY.md (S192 1/7 PASS, FAIL_RETRY_REQUIRED)
audit_version: v2 (2026-04-16 — addresses 15 CRITICAL + 10 WARNING from 8-agent audit pipeline)
audit_report: output/plan-audit/s198-warehouse-receiving-flow-completion/verified_blockers.md
```

> **REGISTRY EVIDENCE** (locked 2026-04-16): registry row added at `docs/plans/SPRINT_REGISTRY.md` with `S198`, branch `s198-warehouse-receiving-flow-completion`, status `PLANNED`. `S197` was already claimed by `s197-pos-sync-5min-interval`; `S198` is the next free ID.

---

## Audit v2 Amendment Summary (2026-04-16)

> **Audit pipeline:** 8 domain agents → code verifier (20 CONFIRMED, 5 STALE, 8 NEW GAPS) → adversarial fact-checker (24 SUPPORTED, 1 PARTIAL). Full report: `output/plan-audit/s198-warehouse-receiving-flow-completion/verified_blockers.md`
>
> All 15 CRITICAL blockers verified against source code. The plan body below is the **amended authoritative version** — do not reference the pre-audit v1 text.

### Fixes applied (CRIT → amendment)

| CRIT | Finding | Fix applied |
|---|---|---|
| 1 | `complete_warehouse_receiving` does NOT build SI; `store.complete_receiving` (store.py:4024) does | **Two Accept paths:** store crew's queue calls `/api/store?action=complete_receiving` (produces SI). Warehouse staff's queue calls `/api/warehouse?action=complete_internal_receipt` (stamps WR only). Phases 2 + 4A rewritten. |
| 2 | "Draft" status doesn't exist; real: `Pending Warehouse Receive` | D-2 rewritten to "Pending Warehouse Receive" |
| 3 | bei-tasks has zero Notification Log consumer | **Phase 3 descoped** from 6 → 3 units. Drop Notification Log; use Google Chat (reuse existing `_notify_warehouse_handoff` pattern in commissary.py). Slack/in-app deferred to a future sprint after a notification framework exists. |
| 4 | `create_warehouse_receiving` hard-throws on non-BKI source | **P1-T1 scope guard:** `if resolve_warehouse_company(se.from_warehouse) != _get_commissary_company(): return None` — non-BKI dispatches skip WR auto-create. Explicit scope statement added. |
| 5 | `source_type` locked to "Commissary Finished Goods" | Scope statement: S198 covers BKI→store dispatches only. Non-BKI internal transfers remain out of scope. |
| 6 | `User.default_store` doesn't exist; `custom_area_supervisor` is on Warehouse (inverted) | **P3-T1 rewritten:** recipient resolution queries `Warehouse.custom_area_supervisor WHERE name = target_warehouse` + `Employee WHERE branch = target_warehouse`. Frontend filter uses `useUserStore().stores` (existing hook, NOT a User field). |
| 7 | API signature is `get_pending_warehouse_receivings(target_warehouse=None)` — no `for_store`/`for_warehouse` | **P2-T4 rewritten:** frontend resolves user's store warehouse via `useUserStore().defaultStore`, passes as `target_warehouse` param. No new API kwarg. |
| 8 | New MODULES keys break TypeScript `Record<Module, Role[]>` exhaustiveness | **MODULES.RECEIVING already exists** (roles.ts:103). Reuse it everywhere — no new module keys. CRIT-8 + WARN-2 resolved. |
| 9 | Detail page RoleGuard uses `MODULES.WAREHOUSE` — blocks store crew | **Phase 2 adds task:** change detail page RoleGuard from `MODULES.WAREHOUSE` to `MODULES.RECEIVING` (which includes STORE_STAFF + STORE_SUPERVISOR). |
| 10 | `ROUTES.WAREHOUSE_RECEIVE` = procurement GR page — wrong redirect | **Phase 2 adds task:** role-based redirect after accept. Store crew → `/dashboard/store-ops/receiving`. Warehouse staff → `/dashboard/warehouse/internal-receiving`. |
| 11 | `CleanupLedger.reverse()` returns in-memory only — no fs.writeFile | **Phase 4A adds task:** after `reverse()`, persist result to `EVIDENCE.cleanupReport` file path. |
| 12 | 2.5% JV markup hardcoded — actual BEI Settings default is 2.75% | **L3 S2 assertion rewritten:** read `bki_markup_jv_percent` from live BEI Settings, don't hardcode. |
| 13 | The Grid - Rockwell has `active_with_billing_hold` — S3 SI guaranteed FAIL | **S3 rewritten as negative-path:** order + approve + dispatch succeed but SI is held (expected). Test asserts billing-hold log entry exists. |
| 14 | S197 registry row missing | **Phase 0 adds task P0-T0:** backfill S197 row in SPRINT_REGISTRY.md. |
| 15 | `stock_entry` field is read_only — ORM set fails silently | **P1-T1 rewritten:** use `frappe.db.set_value("BEI Warehouse Receiving", wr_name, "stock_entry", se.name)` instead of ORM assignment. |

### WARNING fixes applied

| WARN | Fix |
|---|---|
| 1 (double notification) | Resolved by Phase 3 descope — GChat only, no Notification Log. |
| 2 (MODULES.RECEIVING exists) | Reuse existing module. No new RECEIVING_STORE / RECEIVING_WAREHOUSE. |
| 5 (DispatchPage.ts already exists) | Plan says "rewrite" with explicit `MUST_MODIFY` — overwrite is intentional. |
| 6 (relative URL in notification) | Moot — Notification Log dropped. GChat uses absolute URL. |
| 9 (CleanupLedger missing wr-create kind) | Phase 4A adds `wr-create` to CleanupKind type + reverseOne handler. |
| 10 (usePendingInternalReceipts exists) | **Phase 2 rewritten:** store queue page uses `usePendingInternalReceipts(defaultStore)` (DRY). No parallel SWR call. Warehouse queue page uses same hook with `targetWarehouse=null` (shows all). |

### Phase Budget update

| Phase | v1 units | v2 units | Change |
|---|---|---|---|
| 0 | 4 | 5 | +1 (S197 registry backfill) |
| 1 | 10 | 10 | unchanged (scope guard replaces blind try/except) |
| 2 | 12 | 12 | unchanged (tasks reshuffled — detail page RoleGuard + redirect fix, reuse existing hook) |
| 3 | 6 | 3 | -3 (Notification Log dropped → GChat only) |
| 4A | 8 | 8 | unchanged (CleanupLedger persist + wr-create kind added) |
| 4B | 12 | 12 | unchanged (S3 now negative-path; S2 reads Settings) |
| 5 | 4 | 3 | -1 (no LIBRARY_IMPROVEMENTS if <3 fixes) |
| **Total** | **56** | **53** | **-3** |

---

## Purpose

The S190 Company-first billing chain (Store Order → Warehouse Dispatch → Goods Receipt → Sales Invoice) is **operationally incomplete in production today**. The S192 L3 retry surfaced the gap:

1. `hrms.api.warehouse.create_stock_transfer` submits a Stock Entry but **does not create the BEI Warehouse Receiving doc** the store crew needs to acknowledge delivery.
2. `bei-tasks` has **no list page** for pending receivings — only the per-receiving detail page at `/dashboard/warehouse/internal-receiving/[receiving_name]`.
3. Without (1) and (2), `hrms.api.warehouse.complete_warehouse_receiving` (the trigger that builds the S190 Sales Invoice) is unreachable through any browser path. The S190 chain only completes today via Python/SSM scripts — an HB-4 violation that means the production store crew cannot actually use the feature.

This sprint closes the gap with a real, sustainable solution that operators will use daily — not a test-only patch.

**Net deliverable:** a store crew member opens `/dashboard/store-ops/receiving`, sees their pending deliveries, taps one, accepts it, and the Sales Invoice is built automatically.

---

## Design Rationale (For Cold-Start Agents)

### Why this exists
- **Origin:** S192 L3 retry (2026-04-15) failed 6 of 7 scenarios because the dispatch → GR → SI chain has no browser path. Prior session (S192 first run 2026-04-14) faked S1 by calling `complete_warehouse_receiving` directly via Python/SSM — that proved the *backend* works but did not prove a real human store crew member can complete the workflow.
- **Business consequence:** today, dispatched deliveries have no acknowledgment audit trail and no SI lands until someone runs Python in production. Store-side billing for ₱X00K+ daily is at risk the moment the seed scripts go away.
- **Sources:** `output/l3/s192/SUMMARY.md` (FAIL verdict), `output/l3/s192/blocking_defects.json` (BUG-S192-F01..F04 history).

### Why this architecture (Option 3 from the design conversation)
We chose a **backend hook + frontend queue + notification** combination over the alternatives:

| Option considered | Rejected because |
|---|---|
| Auto-create WR in backend only | Operator still has no UI to find the WR docname; flow only works for tests |
| Add UI button only | "Create Receiving" is awkward UX — receiving is a physical event triggered by truck arrival, not a ledger creation step |
| Both backend + frontend (chosen) | Closes the audit gap (every SE has a WR) and the discoverability gap (queue) so the flow mirrors how operators actually work |

### Key trade-off decisions
1. **WR creation happens at SE submit time, not at "truck arrived" time.** Trade-off: store crew sees a "pending receipt" the moment dispatch packs the truck, before the truck physically arrives. Acceptable because: (a) dispatch already represents intent to ship, (b) BIR audit needs the doc the moment stock leaves the source, (c) the UX explains "Dispatched — awaiting receipt" so crew know why it's not yet on their counter.
2. **Receiving queue is per-store for store crew, per-target-warehouse for warehouse staff.** Crew see only their own store's incoming; warehouse staff (test.scm role) see internal transfers between BKI warehouses. Avoids overwhelming the store crew with cross-store noise.
3. **Notification is in-app first, Slack optional.** In-app guarantees delivery to anyone logged in. Slack is a follow-on once the in-app flow is proven stable in production.
4. **WR docname is the existing `BEI-WHR-YYYY-NNNNN` series.** No new naming scheme. The detail page at `/dashboard/warehouse/internal-receiving/[receiving_name]` already exists and works.

### Known limitations and their mitigations
- **Limitation:** `BEI Warehouse Receiving` DocType has no `material_request` direct field — only `stock_entry` (link to SE). Mitigation: queries that need MR-to-WR lookup go through `Stock Entry.material_request → SE name → BEI Warehouse Receiving.stock_entry`. The S198 helper `find_warehouse_receiving_for_mr(mr_name)` encapsulates this two-hop.
- **Limitation:** `hrms.api.warehouse.create_warehouse_receiving` requires `source_warehouse`, `target_warehouse`, `items` parameters. The auto-create hook must derive these from the just-submitted SE. Mitigation: read `se.from_warehouse`, the resolved `target_warehouse` from create_stock_transfer's contract, and `se.items[].item_code/qty/uom`.
- **Limitation:** `BEI Warehouse Receiving` validation rejects items if quantities don't match the SE. Mitigation: the auto-create hook copies SE item quantities exactly.
- **Limitation:** `complete_warehouse_receiving` triggers `build_bki_store_sale_invoice` which depends on `bei_legal_entity` and `bei_store_label` custom fields being populated correctly (per S192 BUG-F02/F03). Both fields' fixes are MERGED in production — don't re-apply.

### Source references
- `hrms/api/warehouse.py:547` — `create_warehouse_receiving` definition
- `hrms/api/warehouse.py:1156` — `create_stock_transfer` (where the hook goes)
- `hrms/api/warehouse.py:1093` — `get_ready_for_dispatch` (queue API for warehouse staff)
- `hrms/api/warehouse.py:341` (in bei-tasks `app/api/warehouse/route.ts`) — `get_pending_warehouse_receivings` (the queue API the new list pages consume)
- `bei-tasks/app/dashboard/warehouse/internal-receiving/[receiving_name]/page.tsx` — existing detail page
- `bei-tasks/app/api/warehouse/route.ts:864` — `create_warehouse_receiving` proxy route
- `bei-tasks/app/api/warehouse/route.ts:891` — `complete_warehouse_receiving` proxy route (SI trigger)
- `bei-tasks/lib/roles.ts` — RBAC source of truth
- `output/l3/s192/diag_dispatch_queue.json` — proves dispatch queue API returns empty without seeded MRs
- `output/l3/s192/diag_megamall.json` — proves S188 child stores work post-F04 fix
- Memory file `memory/feedback_correct_over_fast.md` — "fix the feature, don't remove it"

### Design Decisions Locked
| # | Decision | Why |
|---|---|---|
| D-1 | WR auto-creates on SE submit inside `create_stock_transfer`, **scoped to BKI-source dispatches only** | Single transactional boundary. Non-BKI dispatches return None (their WR flow is out of S198 scope — `create_warehouse_receiving` hard-validates source_company == BKI at warehouse.py:569-573). |
| D-2 | WR initial status = `Pending Warehouse Receive` | This is the only valid initial status per `bei_warehouse_receiving.json:72`. No "Draft" option exists. Controller resets to this on validate. Queue filter hardcodes `{"status": "Pending Warehouse Receive"}`. |
| D-3 | ~~Notification Log~~ **Google Chat** notification on dispatch | bei-tasks has **zero Notification Log consumer** — no bell icon, no useNotifications hook. GChat notification reuses existing `_notify_warehouse_handoff` pattern in commissary.py. In-app notification deferred to a future sprint when a notification framework ships for bei-tasks. |
| D-4 | Store crew identification: query `Warehouse.custom_area_supervisor WHERE name = target_warehouse` (warehouse.py custom field) + `Employee WHERE branch = <target_warehouse_name>` (standard HR link). Frontend filter uses `useUserStore().defaultStore` (existing hook at `bei-tasks/hooks/use-user-store.ts:42`). **`User.default_store` does NOT exist as a User-doctype field.** |
| D-5 | List pages use existing `usePendingInternalReceipts(targetWarehouse)` hook (hooks/use-warehouse.ts:264-280) which wraps `get_pending_warehouse_receivings`. **Store page passes `targetWarehouse=defaultStore`, warehouse page passes `null` (all).** Hook already has SWR config; add `revalidateOnFocus: true` if missing. |
| D-6 | `data-testid` on every list row = `delivery-row-${receiving_name}` | Matches existing `TEST_IDS.deliveryRow` constant in `bei-tasks/tests/e2e/support/selectors.ts`. |
| D-7 | **Two Accept endpoints by role:** Store crew queue calls `store.complete_receiving` (store.py:3933→4024 — this is the endpoint that submits the SI via `_submit_store_sale_invoice`). Warehouse staff queue calls `warehouse.complete_internal_receipt` (warehouse.py — stamps WR only, no SI). **This is the CRIT-1 fix: the SI is built by the STORE endpoint, not the WAREHOUSE endpoint.** |
| D-8 | **RoleGuard:** both queue list pages AND the existing detail page at `[receiving_name]/page.tsx:334` use `MODULES.RECEIVING` (already exists at roles.ts:103 — includes STORE_STAFF + STORE_SUPERVISOR + WAREHOUSE_USER + AREA_SUPERVISOR). No new module keys. |
| D-9 | **Post-accept redirect:** detail page redirects based on originating route: store crew (came from `/dashboard/store-ops/receiving`) → back to store queue. Warehouse staff (came from `/dashboard/warehouse/internal-receiving`) → back to warehouse queue. Uses `searchParams.get("returnTo")` or `document.referrer` fallback. **Fixes CRIT-10:** current redirect goes to `/dashboard/procurement/goods-receipts` (wrong). |
| D-10 | Sentry observability on every new `@frappe.whitelist()` and every new `route.ts` action. Per `.claude/rules/sentry-observability.md` (DM-7) — not optional. |
| D-11 | `stock_entry` field on BEI Warehouse Receiving is `read_only: 1` (bei_warehouse_receiving.json:118). **Use `frappe.db.set_value()` (direct DB write) to stamp it, not ORM assignment.** Fixes CRIT-15. |

---

## Requirements Regression Checklist (verify before writing code)

- [ ] Have you read `output/l3/s192/SUMMARY.md` end-to-end so you understand why the predecessor failed?
- [ ] Will the WR auto-create live INSIDE `create_stock_transfer` (single transaction), not as a hook on `Stock Entry.on_submit`? (D-1)
- [ ] Are you using existing `BEI Warehouse Receiving` doctype, not creating a new one? (Existing path: `hrms/hr/doctype/bei_warehouse_receiving/`)
- [ ] Are you using Google Chat notification via `_notify_warehouse_handoff` pattern, not Notification Log? (D-3)
- [ ] Does every new `@frappe.whitelist()` call `set_backend_observability_context()` as its first line? (DM-7)
- [ ] Are the two new list pages using `usePendingInternalReceipts` (wraps SWR) with `revalidateOnFocus: true`? (D-5)
- [ ] Are list rows tagged `data-testid={`delivery-row-${receiving_name}`}`? (D-6)
- [ ] Does the L3 retry use ONLY browser clicks for workflow steps (no `page.request.*` for approve/dispatch/receive)?
- [ ] Did you cleanup all test data via `CleanupLedger`?
- [ ] Did you re-run the S192 spec, verify all 7 scenarios PASS, and produce real SI docnames for S1/S2/S3/S4?
- [ ] Did you flip plan + registry to COMPLETED only after 7/7 PASS?

---

## Library Audit (Phase 0)

> **Per the QA discipline gate:** every test task must reference an existing Page Object / fixture / builder / assertion or include a task to extract one.

### Existing library that this sprint REUSES (do not re-create)
| Asset | Path | Used by |
|---|---|---|
| `LoginPage`, `StoreOrderingPage`, `OrderApprovalPage` | `bei-tasks/tests/e2e/pages/` | Phase 4 L3 |
| `loggedInAreaSupervisor`, `loggedInSCM`, `loggedInStoreSupervisor` fixtures | `bei-tasks/tests/e2e/fixtures/auth.ts` | Phase 4 L3 |
| `OrderBuilder` | `bei-tasks/tests/e2e/builders/OrderBuilder.ts` | Phase 4 L3 |
| `assertCompanyChainCorrect`, `assertOrderCompany`, `assertMRCreatedForOrder` | `bei-tasks/tests/e2e/assertions/billingAssertions.ts` + `orderAssertions.ts` | Phase 4 L3 |
| `CleanupLedger` | `bei-tasks/tests/e2e/fixtures/cleanup.ts` | Phase 4 L3 |
| `TEST_IDS.deliveryRow`, `TEST_IDS.acceptDeliveryButton` | `bei-tasks/tests/e2e/support/selectors.ts` | Phase 2 (UI) + Phase 4 (L3) |
| `submitOrderAtSuggested` helper | `bei-tasks/tests/e2e/pages/StoreOrderingPage.ts` | Phase 4 L3 |

### Library gaps this sprint FILLS (becomes part of the canonical library)
| Asset to add | Path | Replaces text-fallback in |
|---|---|---|
| `ReceivingQueuePage` Page Object — list page navigation + per-row click + accept | `bei-tasks/tests/e2e/pages/ReceivingQueuePage.ts` | inline navigation in S192 retry spec |
| `DispatchPage` rewrite — uses `dispatch-button-${mrName}` testid + dialog flow | `bei-tasks/tests/e2e/pages/DispatchPage.ts` | inline dispatch logic in S192 retry spec |
| `WarehouseApprovalPage` Page Object — `/dashboard/warehouse/approve` | `bei-tasks/tests/e2e/pages/WarehouseApprovalPage.ts` | inline MR-approve logic in S192 retry spec |
| `assertWRCreatedForSE(seName)` assertion | `bei-tasks/tests/e2e/assertions/billingAssertions.ts` | (new) |
| `assertNotificationDeliveredTo(user, recordType, recordName)` assertion | `bei-tasks/tests/e2e/assertions/notificationAssertions.ts` | (new) |
| `findReceivingForOrder(orderName)` support helper | `bei-tasks/tests/e2e/support/frappeReadback.ts` | inline two-hop query in S192 retry spec |

### Library ownership statement
> Library code under `bei-tasks/tests/e2e/{pages,fixtures,builders,assertions,support}` is **owned by S198 once extracted**; future sprints are consumers and extenders. New tests must reuse, not duplicate.

---

## Phase Budget

| Phase | Description | Units | Notes |
|---|---|---|---|
| 0 | Preflight: env probe, library audit, branch + coordination + S197 registry backfill | 5 | |
| 1 | Backend: auto-create WR in `create_stock_transfer` + BKI scope guard + Sentry instrumentation + 4 unit tests | 10 | hrms PR |
| 2 | Frontend: 2 receiving queue list pages + existing hook reuse + testids + RBAC verification + detail page RoleGuard + redirect fix | 12 | bei-tasks PR |
| 3 | Notification: Google Chat notification on dispatch + recipient resolution + GChat surface check | 3 | hrms — same PR as Phase 1 |
| 4A | L3 library extraction: 3 new Page Objects + 2 new assertions + 1 new support helper | 8 | bei-tasks — same PR as Phase 2 |
| 4B | L3 retry: full S190 chain browser-only, all 7 S192 scenarios, real SI evidence | 12 | bei-tasks — separate L3 evidence commit |
| 5 | Closeout: plan + registry to COMPLETED, evidence files, PR comments, S192 status flip | 3 | |

**Total: 53 units** (within the 80-unit ceiling). No phase exceeds 12 units.

---

## Anti-Rewind / Concurrent-Run Protection Contract

This sprint touches files that the S196 agent is also actively modifying. **Coordinate via the ownership matrix below.**

### Surface ownership matrix
| File / surface | S198 owner | Concurrent risk |
|---|---|---|
| `hrms/api/warehouse.py` | S198 (exclusive — additive only) | None known. S196 touches `store.py` + `company_master.py`. |
| `hrms/api/warehouse.py::create_stock_transfer` | S198 (modify return path) | None known |
| `hrms/api/warehouse.py::create_warehouse_receiving` | S198 (call from new hook only — do not modify signature) | None known |
| `hrms/hr/doctype/bei_warehouse_receiving/*` | S198 (no schema change; pure consumer) | None |
| `bei-tasks/app/dashboard/store-ops/receiving/page.tsx` (NEW) | S198 (exclusive) | None |
| `bei-tasks/app/dashboard/warehouse/internal-receiving/page.tsx` (NEW list page; existing `[receiving_name]/` stays) | S198 (exclusive) | None |
| `bei-tasks/lib/roles.ts` | S198 (additive only — verify new routes are visible to right roles) | Multiple sprints touch this; coordinate |
| `bei-tasks/lib/constants.ts` (ROUTES) | S198 (additive only) | Multiple sprints touch this |
| `bei-tasks/tests/e2e/pages/{Dispatch,Receiving,WarehouseApproval}Page.ts` | S198 (rewrite/new) | S192 retry pages reverted multiple times last session — do NOT chase reverts; commit early and let S198 own these going forward |

### Protected surfaces (do NOT touch)
- `hrms/api/store.py` — S196 owns
- `hrms/api/company_master.py` — S196 owns
- `hrms/api/commissary.py::build_bki_store_sale_invoice` — S192 fix MERGED, frozen
- `hrms/api/store.py::_normalize_store_name_for_route` — S192 hrms#583 MERGED, frozen
- `bei-tasks/app/dashboard/store-ops/order-approvals/page.tsx` — S192 testid commit on main, frozen

### Remote-truth baseline (record before Phase 1)
Required artifact (write at start of execution): `output/s198/state/REMOTE_TRUTH_BASELINE.json`
```json
{
  "hrms": {
    "release_branch": "production",
    "release_head_sha": "<git rev-parse origin/production at start>",
    "live_evidence_basis": "output/l3/s192/SUMMARY.md S192 1/7"
  },
  "bei_tasks": {
    "release_branch": "main",
    "release_head_sha": "<git rev-parse origin/main at start>",
    "live_evidence_basis": "Vercel deploy of 2109e36"
  }
}
```

### Coordination
- Before pushing to either branch, `git fetch` and rebase onto current `origin/production` (hrms) / `origin/main` (bei-tasks). Verify no shared file conflicts.
- If a rebase touches `hrms/api/store.py`, STOP — that's S196's lane.
- If a rebase touches `bei-tasks/app/dashboard/store-ops/order-approvals/page.tsx`, STOP — that's S192-frozen.

---

## Ground-Truth Lock

### Evidence sources
| File | What it proves |
|---|---|
| `output/l3/s192/SUMMARY.md` | S192 FAIL verdict (1/7 scenarios), retry required |
| `output/l3/s192/blocking_defects.json` | F01-F04 history; F02 + F03 already MERGED so SI build path works |
| `output/l3/s192/state_verification.json` | Per-scenario pass/fail granularity |
| `output/l3/s192/diag_dispatch_queue.json` | `ready_for_dispatch` API returns `[]` without seeded MRs in `Ordered` status |
| `output/l3/s192/diag_megamall.json` | After F04 fix, SM Megamall returns 56 items sourced from `3MD Logistics - Camangyanan - BKI` |
| `hrms/api/warehouse.py` lines 547, 1093, 1156 | The three functions S198 touches (auto-create call, queue API, SE creator) |
| `bei-tasks/app/dashboard/warehouse/internal-receiving/[receiving_name]/page.tsx` | Existing detail page that the new list pages link to |

### Count method
- "L3 scenario pass count" = count of scenarios in `state_verification.json` whose `verdict === "PASS"`. Method: load JSON, filter, count.
- "Real SI docname" = a string matching `^ACC-SINV-\d{4}-\d{5}$` returned by `assertCompanyChainCorrect()`.

### Authoritative sections
- The "L3 Workflow Scenarios" table below (Phase 4B) is the execution source of truth for the L3 retry.
- This plan body supersedes any conflicting language in `output/l3/s192/HANDOVER_PROMPT.md`.

### Unresolved-value policy
- Any operator-facing copy (e.g., notification text, page header) that has not been confirmed by Sam: write `[UNVERIFIED — requires Sam confirmation]` and stop on it.

---

## Phase 0 — Preflight + Library Audit (5 units)

### P0-T1 — Branch + remote-truth baseline (1 unit)
**Action:**
```bash
cd F:/Dropbox/Projects/BEI-ERP
git fetch origin production
git checkout -b s198-warehouse-receiving-flow-completion origin/production

cd ../bei-tasks
git fetch origin main
git checkout -b s198-warehouse-receiving-queue-ui origin/main
```

**MUST_MODIFY:** none (this is setup)

**Evidence:** Write `output/s198/state/REMOTE_TRUTH_BASELINE.json` with both repos' head SHAs.

### P0-T2 — Library audit confirmation (1 unit)
**Action:** Re-run the Library Audit table above against current `bei-tasks/tests/e2e/`. Confirm every "REUSE" asset still exists at the listed path. If any have moved, update the table — do not skip.

**MUST_MODIFY:** none

**Evidence:** `output/s198/state/LIBRARY_AUDIT.md` — confirms which assets exist + which gaps remain.

### P0-T3 — Test users + stock seed verification (1 unit)
**Action:** Verify the S192 test users still exist and have the right roles:
- `test.area@bebang.ph` — Area Supervisor; multi-store supervisor on SM Tanza, SM Megamall, The Grid - Rockwell, Ayala Evo, Araneta Gateway. Password: `BeiTest2026!`
- `test.scm@bebang.ph` — Supply Chain Manager + Warehouse Manager + Regional Manager. Password: `BeiTest2026!`
- `test.supervisor@bebang.ph` — Store Supervisor + Warehouse User + Warehouse Manager. Password: `BeiTest2026!`

Verify Pinnacle stock from S192 seed run still has FG001/FG002/FG010/FG023/PM002/PM003/PM007 ≥ 5000 units. If depleted, re-run `scripts/s192_seed_pinnacle_stock.py` (deploy password gate `# 2289454`).

**MUST_MODIFY:** none

**Evidence:** `output/s198/state/PRE_RUN_USER_AND_STOCK.json`

### P0-T4 — Cleanup any S192 stranded orders (1 unit)
**Action:** Run `python scripts/s192_cleanup_strays.py` to delete any Draft orders left from prior sessions. Append `# 2289454` to the bash command.

**MUST_MODIFY:** none

**Evidence:** stdout of the cleanup script captured into `output/s198/state/PRE_RUN_CLEANUP.json`

---

## Phase 1 — Backend: Auto-create WR + Sentry + Tests (10 units)

> **Branch:** `s198-warehouse-receiving-flow-completion` in hrms repo.

### P1-T1 — Add `_create_warehouse_receiving_for_se(se, contract)` private helper (3 units)
**File:** `hrms/api/warehouse.py`

**MUST_MODIFY:** `hrms/api/warehouse.py`
**MUST_CONTAIN:** `def _create_warehouse_receiving_for_se(`
**MUST_CONTAIN:** `# S198: auto-create BEI Warehouse Receiving`
**MUST_CONTAIN:** `_get_commissary_company`
**MUST_CONTAIN:** `frappe.db.set_value`

**Logic:**
1. **BKI scope guard (CRIT-4):** Before doing anything, check `if resolve_warehouse_company(se.from_warehouse) != _get_commissary_company(): return None`. Non-BKI dispatches skip WR auto-create entirely — their WR flow is out of S198 scope.
2. Build the items payload from `se.items` (item_code, qty, uom).
3. Call `create_warehouse_receiving(source_warehouse=se.from_warehouse, target_warehouse=contract['destination_warehouse'], items=json.dumps(items), remarks=f"Auto-created from {se.name}")`.
4. Stamp the new WR's `stock_entry` field using direct DB write (CRIT-15 — field is `read_only: 1`, ORM set fails silently): `frappe.db.set_value("BEI Warehouse Receiving", wr_name, "stock_entry", se.name)`. Idempotent — if WR already exists for this SE, return its name.
5. Catch and `frappe.log_error` any exception so a WR failure does not roll back the SE submit. WR can be retried by a follow-up.

**HARD BLOCKER:** the helper MUST NOT raise. If the WR creation fails, the SE is already submitted; throwing here would be a half-state. (DM-2 logic — atomicity inside the helper, observability via Sentry on failure.)

### P1-T2 — Wire helper into `create_stock_transfer` (2 units)
**File:** `hrms/api/warehouse.py`

**MUST_MODIFY:** `hrms/api/warehouse.py`
**MUST_CONTAIN:** `_create_warehouse_receiving_for_se(se, contract)`

**Insertion point:** immediately after the existing `with _run_as_system_user("Administrator"): se.submit()` block, before the `return {...}` statement.

```python
# S198: auto-create BEI Warehouse Receiving so the destination store's
# crew has an acknowledgment doc the moment dispatch packs the truck.
wr_name = _create_warehouse_receiving_for_se(se, contract)
if wr_name:
    extras_for_return = {"warehouse_receiving": wr_name}
else:
    extras_for_return = {"warehouse_receiving": None}
```

Then add `**extras_for_return` to the returned `data` dict.

**MUST_CONTAIN:** `"warehouse_receiving":`

### P1-T3 — Sentry observability on the new helper (1 unit)
**File:** `hrms/api/warehouse.py`

The helper is private (underscore prefix) so per `.claude/rules/sentry-observability.md` it does NOT need `set_backend_observability_context()`. But add an `extras={"se_name": se.name, "wr_name": wr_name}` to the existing `set_backend_observability_context` call inside `create_stock_transfer` so the parent span carries the WR result.

**MUST_CONTAIN:** `"warehouse_receiving":` (extras key)

### P1-T4 — Idempotency safeguard (1 unit)
**File:** `hrms/api/warehouse.py`

In `_create_warehouse_receiving_for_se`, check first if a WR already exists for this SE:
```python
existing = frappe.db.get_value("BEI Warehouse Receiving", {"stock_entry": se.name, "status": ("!=", "Cancelled")}, "name")
if existing:
    return existing
```
This makes a retry of `create_stock_transfer` on the same MR safe.

**MUST_CONTAIN:** `frappe.db.get_value("BEI Warehouse Receiving"`

### P1-T5 — Unit tests (3 units)
**File:** `hrms/tests/test_s198_warehouse_receiving_auto_create.py` (new)

**MUST_MODIFY:** `hrms/tests/test_s198_warehouse_receiving_auto_create.py`
**MUST_CONTAIN:** `def test_dispatch_creates_wr_alongside_se`
**MUST_CONTAIN:** `def test_idempotent_redispatch_returns_same_wr`
**MUST_CONTAIN:** `def test_wr_failure_does_not_rollback_se`
**MUST_CONTAIN:** `def test_wr_status_starts_pending_warehouse_receive`

Each test seeds an MR + calls `create_stock_transfer` + asserts WR existence/state. Use `frappe.db.savepoint("s198_test")` + `frappe.db.rollback(save_point="s198_test")` for cleanup.

---

## Phase 2 — Frontend: Receiving Queue List Pages (12 units)

> **Branch:** `s198-warehouse-receiving-queue-ui` in bei-tasks repo.

### P2-T1 — Store-side queue page (4 units)
**File (new):** `bei-tasks/app/dashboard/store-ops/receiving/page.tsx`

**MUST_MODIFY:** `bei-tasks/app/dashboard/store-ops/receiving/page.tsx`
**MUST_CONTAIN:** `data-testid={`delivery-row-`}`
**MUST_CONTAIN:** `usePendingInternalReceipts`
**MUST_CONTAIN:** `revalidateOnFocus: true`
**MUST_CONTAIN:** `RoleGuard`
**MUST_CONTAIN:** `MODULES.RECEIVING`

**Behavior:**
- Gets `defaultStore` from `useUserStore()` hook (`hooks/use-user-store.ts:42`).
- Fetches pending receivings via `usePendingInternalReceipts(defaultStore)` from existing `hooks/use-warehouse.ts:264` (DRY — no parallel SWR call). This hook wraps `get_pending_warehouse_receivings` with `target_warehouse` param.
- Lists each WR as a Card containing: source warehouse, dispatch date, items count, source-MR link, "Receive" button.
- Card has `data-testid={`delivery-row-${receiving.name}`}` AND `onClick={() => router.push(`/dashboard/warehouse/internal-receiving/${receiving.name}`)}`.
- Uses `RoleGuard` from `@/components/layout/role-guard` with `MODULES.RECEIVING` (already exists at roles.ts:103 — includes STORE_STAFF + STORE_SUPERVISOR + WAREHOUSE_USER + AREA_SUPERVISOR).
- Empty state: "No pending deliveries" with refresh button bound to SWR `mutate`.
- Header includes a manual Refresh button (`mutate()`) for operators.

### P2-T2 — Warehouse-side queue page (3 units)
**File (new):** `bei-tasks/app/dashboard/warehouse/internal-receiving/page.tsx`

**MUST_MODIFY:** `bei-tasks/app/dashboard/warehouse/internal-receiving/page.tsx`
**MUST_CONTAIN:** `data-testid={`delivery-row-`}`
**MUST_CONTAIN:** `usePendingInternalReceipts`
**MUST_CONTAIN:** `revalidateOnFocus: true`

**Behavior:**
- Fetches pending receivings via `usePendingInternalReceipts(null)` from existing `hooks/use-warehouse.ts:264` — passing `null` shows all warehouses (warehouse staff see everything; no per-user warehouse filter).
- Card → `/dashboard/warehouse/internal-receiving/${name}` (existing detail page).
- RBAC: `MODULES.RECEIVING` (already exists at roles.ts:103 — includes WAREHOUSE_USER + AREA_SUPERVISOR). No new module keys.

### P2-T3 — RBAC + ROUTES wiring (2 units)
**Files:**
- `bei-tasks/lib/roles.ts` — Verify `MODULES.RECEIVING` (roles.ts:103) already grants access to STORE_STAFF, STORE_SUPERVISOR, WAREHOUSE_USER, AREA_SUPERVISOR. No new module keys needed. Do NOT create `RECEIVING_STORE` or `RECEIVING_WAREHOUSE`.
- `bei-tasks/lib/constants.ts` — add `STORE_RECEIVING_QUEUE: "/dashboard/store-ops/receiving"` and confirm `WAREHOUSE_INTERNAL_RECEIVING` already maps to the new list path.
- Sidebar profile (`bei-tasks/lib/sidebar-role-profiles.ts`) — add the two new routes to the relevant role profiles so operators can navigate to them.
- **Detail page RoleGuard fix (CRIT-9):** Change the RoleGuard on the existing detail page at `bei-tasks/app/dashboard/warehouse/internal-receiving/[receiving_name]/page.tsx:334` from `MODULES.WAREHOUSE` to `MODULES.RECEIVING` (so store crew are not blocked).
- **Post-accept redirect fix (CRIT-10):** On the detail page, fix post-accept redirect from `ROUTES.WAREHOUSE_RECEIVE` (which points to the procurement GR page — wrong) to a role-based redirect using `searchParams.get("returnTo")` or `document.referrer` fallback. Store crew (came from `/dashboard/store-ops/receiving`) redirect back to store queue. Warehouse staff (came from `/dashboard/warehouse/internal-receiving`) redirect back to warehouse queue.

**MUST_CONTAIN (roles.ts):** `MODULES.RECEIVING`
**MUST_CONTAIN (constants.ts):** `STORE_RECEIVING_QUEUE`
**MUST_CONTAIN ([receiving_name]/page.tsx):** `MODULES.RECEIVING`
**MUST_CONTAIN ([receiving_name]/page.tsx):** `returnTo`

### P2-T4 — Confirm `get_pending_warehouse_receivings` accepts `target_warehouse` (2 units)
**File:** `bei-tasks/app/api/warehouse/route.ts`

Confirm `get_pending_warehouse_receivings(target_warehouse=None)` at warehouse.py:651 returns WRs filtered by `target_warehouse`. The frontend passes `defaultStore` (from `useUserStore()` hook at `hooks/use-user-store.ts:42`) as the `target_warehouse` param via the existing `usePendingInternalReceipts` hook. No new API kwargs needed — the API already accepts `target_warehouse` as its only filter.

**MUST_CONTAIN (route.ts):** `target_warehouse`

### P2-T5 — Visual + Sentry (1 unit)
- Add Sentry breadcrumbs via `captureExceptionWithContext` on any caught error in the new pages.
- Card design: use the same `<Card>` shadcn component used by `OrderCard` in `bei-tasks/app/dashboard/store-ops/order-approvals/page.tsx`. Match spacing and badge style.

---

## Phase 3 — Notification on Dispatch (3 units)

> **Same branch as Phase 1** (hrms `s198-warehouse-receiving-flow-completion`).

### P3-T1 — Recipient resolution helper (1 unit)
**File:** `hrms/api/warehouse.py`

Add `_get_store_crew_recipients(target_warehouse)`:
- Resolve the area supervisor by querying `Warehouse.custom_area_supervisor WHERE name = target_warehouse` (custom field defined at `custom_field.json:75-80`).
- Resolve store crew emails by querying `Employee WHERE branch = <target_warehouse_name>` (standard HR link — `branch` holds the store/warehouse name).
- Combine area supervisor email + crew emails. Cap at 20 users to avoid blast radius.
- Return empty list if no matches (don't error).

**MUST_CONTAIN:** `def _get_store_crew_recipients(`
**MUST_CONTAIN:** `Warehouse.custom_area_supervisor`

### P3-T2 — Google Chat notification on dispatch (1 unit)
**File:** `hrms/api/warehouse.py`

Inside `_create_warehouse_receiving_for_se` (Phase 1 helper), after WR is created successfully, send a Google Chat notification reusing the existing `_notify_warehouse_handoff` pattern from `commissary.py`. Use absolute URL `https://my.bebang.ph/dashboard/warehouse/internal-receiving/{wr_name}` for the link.

```python
recipients = _get_store_crew_recipients(target_warehouse)
_notify_warehouse_handoff(
    recipients=recipients,
    subject=f"Delivery {wr_name} dispatched to your store",
    link=f"https://my.bebang.ph/dashboard/warehouse/internal-receiving/{wr_name}",
    wr_name=wr_name,
)
```
Wrap in try/except — notification failures must not roll back the SE/WR.

**MUST_CONTAIN:** `_notify_warehouse_handoff` or `google_chat`

### P3-T3 — Confirm GChat message delivered to target store's Chat space (1 unit)
**File:** read-only verification.

After triggering a test dispatch, confirm the Google Chat message is delivered to the target store's Chat space (the same space used by `_notify_warehouse_handoff` for commissary handoffs). Verify the message body contains the WR name and the absolute URL to the receiving detail page. Also confirm the SWR `revalidateOnFocus: true` (D-5) on the queue page covers the operator's mental model: "I focus the tab, my queue refreshes."

**Evidence:** `output/s198/state/GCHAT_NOTIFICATION_CHECK.md` — note which Chat space received the message and confirm link format.
**MUST_CONTAIN:** `gchat` or `google_chat`

### P3-T4 — Unit test (1 unit)
**File:** `hrms/tests/test_s198_dispatch_notification.py` (new)

**MUST_CONTAIN:** `def test_dispatch_sends_gchat_notification`
**MUST_CONTAIN:** `def test_gchat_failure_does_not_rollback_dispatch`

---

## Phase 4A — L3 Library Extraction (8 units)

> **Branch:** `s198-warehouse-receiving-queue-ui` (same as Phase 2).

### P4A-T1 — `WarehouseApprovalPage` Page Object (2 units)
**File (new):** `bei-tasks/tests/e2e/pages/WarehouseApprovalPage.ts`

**MUST_MODIFY:** `bei-tasks/tests/e2e/pages/WarehouseApprovalPage.ts`
**MUST_CONTAIN:** `class WarehouseApprovalPage`
**MUST_CONTAIN:** `aria-label="Approve `

Method: `approve(mrName: string)` navigates to `/dashboard/warehouse/approve`, polls for the MR by `aria-label="Approve ${mrName}"`, clicks via DOM-level `.evaluate(el => el.click())`, waits for queue to refresh.

### P4A-T2 — Rewrite `DispatchPage` (2 units)
**File:** `bei-tasks/tests/e2e/pages/DispatchPage.ts`

**MUST_MODIFY:** `bei-tasks/tests/e2e/pages/DispatchPage.ts`
**MUST_CONTAIN:** `dispatch-button-`
**MUST_CONTAIN:** `Create Transfer`

Method: `dispatch(mrName, opts?)` clicks the per-MR `dispatch-button-${mrName}`, fills the dialog Source Warehouse + Remarks, clicks the "Create Transfer" submit button, waits for toast.

### P4A-T3 — Rewrite `ReceivingPage` to use `ReceivingQueuePage` (2 units)
**Files:**
- `bei-tasks/tests/e2e/pages/ReceivingQueuePage.ts` (new) — list page navigation, click `delivery-row-${name}`.
- `bei-tasks/tests/e2e/pages/ReceivingPage.ts` (rewrite) — navigates from MR → queue page → row → existing detail page → accept-delivery-button.

**MUST_CONTAIN (ReceivingQueuePage.ts):** `delivery-row-`
**MUST_CONTAIN (ReceivingPage.ts):** `accept-delivery-button`

### P4A-T4 — `assertWRCreatedForSE` + `assertNotificationDeliveredTo` (1 unit)
**Files:**
- `bei-tasks/tests/e2e/assertions/billingAssertions.ts` — add `assertWRCreatedForSE(seName)` returning the WR docname.
- `bei-tasks/tests/e2e/assertions/notificationAssertions.ts` (new) — add `assertNotificationDeliveredTo(user, recordType, recordName)`.

### P4A-T5 — `findWarehouseReceivingForOrder` support helper (1 unit)
**File:** `bei-tasks/tests/e2e/support/frappeReadback.ts`

Two-hop query: order → MR → SE → WR. Returns WR docname or null.

**MUST_CONTAIN:** `export async function findWarehouseReceivingForOrder`

---

## Phase 4B — L3 Retry: Full S190 Chain Browser-Only (12 units)

> **Same branch as Phase 4A.** Evidence under `output/l3/s198/`.

### P4B-T1 — Update existing spec to use library (2 units)
**File:** `bei-tasks/tests/e2e/specs/s190-store-company-integration.spec.ts`

**MUST_MODIFY:** `bei-tasks/tests/e2e/specs/s190-store-company-integration.spec.ts`
**MUST_CONTAIN:** `WarehouseApprovalPage`
**MUST_CONTAIN:** `DispatchPage`
**MUST_CONTAIN:** `ReceivingQueuePage`

Replace inline navigation with the new Page Objects. Each scenario calls them in sequence: order submit → order approval → MR approval (warehouse/approve) → dispatch → receiving queue → accept → assert SI chain.

### P4B-T2 — Run the spec, all 7 scenarios PASS (8 units)
**Command:**
```bash
cd F:/Dropbox/Projects/bei-tasks
FRAPPE_API_KEY=$(doppler secrets get FRAPPE_API_KEY --plain --project bei-erp --config dev) \
FRAPPE_API_SECRET=$(doppler secrets get FRAPPE_API_SECRET --plain --project bei-erp --config dev) \
S192_EVIDENCE_ROOT="F:/Dropbox/Projects/BEI-ERP/output/l3/s198" \
npx playwright test tests/e2e/specs/s190-store-company-integration.spec.ts --reporter=list --timeout=900000
```

**HARD BLOCKER:** ALL 7 SCENARIOS MUST PASS. No partial. No "deferred." Per Sam's 2026-04-16 rule: corner cutting = whole test fails = repeat from scratch.

If a scenario fails, classify per Failure Response below. If Mode A (app bug), file the defect, fix the code, re-run from scratch. If Mode B (test bug), fix the test in the library so future sprints inherit the fix.

### P4B-T3 — Evidence + cleanup (2 units)
**Files (must exist, populated, valid):**
- `output/l3/s198/SUMMARY.md` — scenario × assertion pass/fail matrix; honest, no spin
- `output/l3/s198/state_verification.json` — per-scenario verdict (PASS / FAIL only — no PARTIAL)
- `output/l3/s198/form_submissions.json` — every POST to `/api/ordering` and `/api/warehouse` with body + response
- `output/l3/s198/api_mutations.json` — every Frappe doc created/modified with before/after
- `output/l3/s198/cleanup_ledger.json` — running ledger
- `output/l3/s198/cleanup_report.json` — reverser output (every mutation reversed)
- `output/l3/s198/screenshots/` — per-step browser captures
- `output/l3/s198/blocking_defects.json` — any defect surfaced this run
- `output/l3/s198/deferred_defects.json` — non-blocking observations

Cleanup: every order, MR, SE, WR, SI created during the run is cancelled/deleted via `CleanupLedger.reverse()`. `cleanup_report.json` shows zero failed reversals.

---

## Phase 5 — Closeout (3 units)

### P5-T1 — Verify all evidence + all PASS (1 unit)
Re-read `output/l3/s198/state_verification.json`. Confirm `score.pass === 7 && score.fail === 0`. If not, return to Phase 4B.

### P5-T2 — Update plan + registry to COMPLETED (1 unit)
**Files:**
- `docs/plans/2026-04-16-sprint-198-warehouse-receiving-flow-completion.md` — set `status: COMPLETED`, `completed_date`, `execution_summary`.
- `docs/plans/SPRINT_REGISTRY.md` — flip S198 row to COMPLETED with PR refs.
- `docs/plans/SPRINT_REGISTRY.md` — flip S192 row from `FAIL_RETRY_REQUIRED` to `RETRIED_BY_S198_PASSED` with link to S198 evidence.

`git add -f` both files (docs/ may be gitignored).

### P5-T3 — Push and create PRs (1 unit)
**Two PRs:**
- hrms PR (branch `s198-warehouse-receiving-flow-completion`): Phase 1 + Phase 3 (backend auto-create WR + notification).
- bei-tasks PR (branch `s198-warehouse-receiving-queue-ui`): Phase 2 + Phase 4A + Phase 4B (UI list pages + library + L3 evidence).

PR descriptions include Phase × Task completion table (Zero-Skip Enforcement). Stop. Do not merge. Sam handles merge per PR-Handoff workflow.

### P5-T4 — Library improvements changelog (1 unit)
If Phase 4B caused 3+ library fixes, write `output/l3/s198/LIBRARY_IMPROVEMENTS.md` per the QA discipline rule.

---

## L3 Workflow Scenarios (Phase 4B execution table)

Every row must pass browser-only. Real SI docnames captured.

| # | User | Action sequence | Expected SI / outcome | Failure means |
|---|---|---|---|---|
| S1 | test.area → test.area → test.scm → test.scm → test.supervisor | Submit order on SM Tanza → Single/Dual approval → MR approve at /warehouse/approve → Dispatch at /warehouse/dispatch → Open `/dashboard/store-ops/receiving` → tap delivery → click Accept | Real `ACC-SINV-YYYY-NNNNN` with customer = BEBANG MEGA INC., TIN = 010-885-436-00000, 12% VAT (exact ratio), 8% markup, GL has Customer party row | Backend auto-create WR broken OR queue page doesn't show |
| S2 | same chain | Same on SM Megamall | Real SI with customer = `SM Megamall - Bebang Enterprise Inc.` (S196 STORE-FIRST naming), JV markup = value from BEI Settings.bki_markup_jv_percent (default 2.75% per bei_settings.json:360-365 — do NOT hardcode), 12% VAT | S188 child resolution / S196 rename broken |
| S3 | same chain | Same on The Grid - Rockwell | **NEGATIVE PATH:** order + approve + dispatch SUCCEED, but SI is NOT built because The Grid - Rockwell has `active_with_billing_hold` status (commissary.py:1033 `buyer_entity_requires_billing_hold` returns True). Test asserts: (a) order.company = TASTECARTEL CORP., (b) MR approved + SE created, (c) WR auto-created, (d) `complete_receiving` returns billing-hold response, (e) no ACC-SINV created. This validates the billing-hold guard works. | Billing hold guard broken (SI created when it shouldn't be) |
| S4 | same chain (single FG item at suggested qty) | Same on Ayala Evo | Real SI; SI customer doc IDENTICAL to S1's SI customer doc (multi-store same-entity dedupe) | S190 same-entity Customer dedupe broken |
| F1 | test.area | Open `/dashboard/store-ops/ordering`, set no qty, attempt submit | Review/Submit controls hidden; no order created | S0 deviation gate or empty-order guard broken |
| F2 | Administrator (setup) + test.area (run) | Create test warehouse with `company=NULL`; test.area attempts submit on it | Inline ValidationError "Store warehouse … has no Company set"; no order created | S190 Company-first guard broken |
| F3 | test.scm (rename) | After S1 SI lands, rename Customer "BEBANG MEGA INC." to a new name; observe billing-hold log entry on next dispatch attempt | Billing-hold log entry written; new dispatch refuses to bill until customer reverted | S190 rename guard broken |

Score requirement: **7 PASS, 0 FAIL.** No partial.

---

## Failure Response (Mode A / B / C)

| Mode | When | Action |
|---|---|---|
| **A — App bug** | A scenario fails because the production code has a defect | File `output/l3/s198/blocking_defects.json` entry. **Do not modify the test.** Fix the app code, rebase the relevant PR, re-run the affected scenarios from scratch. |
| **B — Test bug** | A scenario fails because the test is wrong (selector, timing, fixture) | Fix the test. If the fix would help future tests, **promote the fix to the Page Object / fixture / assertion** in the same commit. Re-run from scratch. |
| **C — Brittleness / flake** | A scenario fails intermittently OR needs `waitForTimeout` to pass | Fix the LIBRARY, not the spec. **Forbidden:** `test.retry(3)`, `page.waitForTimeout(N)` masking a missing wait condition. Replace with explicit wait-for-element or wait-for-network-response. |

If ≥3 library fixes happen during execution, write `output/l3/s198/LIBRARY_IMPROVEMENTS.md` as a closeout artifact.

---

## Zero-Skip Enforcement

> Sam's rule (2026-04-16): "Partial tests = Fail as well. Every single time you cut corners the whole test will fail and you will repeat from scratch until the whole flow is tested in a browser."

### Forbidden agent behaviors
- Skipping a task silently
- Marking partial work as "done"
- Replacing a task with a simpler version without explicit Sam approval
- Saying "deferred to next sprint" for any in-scope task
- Combining tasks and dropping features
- Implementing happy path only, skipping edge cases (F1/F2/F3)
- Calling `page.request.*` / `fetch()` / `curl` for any workflow step (approve/dispatch/receive/SI)
- Using `waitForTimeout` to mask a missing wait condition
- Calling the L3 retry "passed" without producing real `ACC-SINV-YYYY-NNNNN` docnames in `state_verification.json` for S1/S2/S4 (S3 is negative-path — must have `si_name: null`)

### Per-phase verification scripts (FAIL blocks progress)

After each phase, the agent runs a verification script. If any assertion fails, the phase is incomplete and the agent must fix before proceeding.

`output/s198/verify_phase1.py` — checks:
1. `git diff --name-only origin/production..HEAD` includes `hrms/api/warehouse.py` and `hrms/tests/test_s198_warehouse_receiving_auto_create.py`
2. `grep -c "_create_warehouse_receiving_for_se" hrms/api/warehouse.py >= 2` (definition + call)
3. `grep -c "_notify_warehouse_handoff\|google_chat" hrms/api/warehouse.py >= 1`
4. `grep -c "def test_" hrms/tests/test_s198_warehouse_receiving_auto_create.py >= 4`

`output/s198/verify_phase2.py` — checks:
1. `git diff --name-only origin/main..HEAD` includes the two new `page.tsx` files and `lib/roles.ts`
2. `grep -c "data-testid={`delivery-row-" bei-tasks/app/dashboard/store-ops/receiving/page.tsx >= 1`
3. `grep -c "data-testid={`delivery-row-" bei-tasks/app/dashboard/warehouse/internal-receiving/page.tsx >= 1`
4. `grep -c "MODULES.RECEIVING\|usePendingInternalReceipts" bei-tasks/app/dashboard/store-ops/receiving/page.tsx >= 2`

`output/s198/verify_phase4b.py` — checks:
1. `output/l3/s198/state_verification.json` has `score.pass === 7 && score.fail === 0`
2. Every S1/S2/S4 entry has a non-null `si_name` matching `^ACC-SINV-\d{4}-\d{5}$`; S3 entry has `si_name === null` (negative-path: billing-hold blocks SI)
3. `output/l3/s198/cleanup_report.json` has `failed === []`

**HARD BLOCKER:** If any verification script FAILs, do not proceed to the next phase. Fix the failure first.

---

## Autonomous Execution Contract

```yaml
completion_condition:
  - all 5 phases verified by their verification scripts (FAIL == 0 in each)
  - L3 retry: 7 PASS / 0 FAIL with real SI docnames captured
  - all evidence files exist and are populated (SUMMARY.md, state_verification.json, form_submissions.json, api_mutations.json, cleanup_report.json, screenshots/)
  - cleanup_report.json shows zero failed reversals
  - both PRs created (hrms + bei-tasks) with PR descriptions including the per-phase task completion table
  - plan YAML status: COMPLETED, completed_date set, execution_summary written
  - SPRINT_REGISTRY.md S198 row flipped to COMPLETED
  - SPRINT_REGISTRY.md S192 row flipped to RETRIED_BY_S198_PASSED

stop_only_for:
  - missing credentials (FRAPPE_API_KEY/SECRET — fetch via Doppler `bei-erp/dev`)
  - test users not found (test.area / test.scm / test.supervisor) — escalate to Sam
  - destructive approval needed (e.g., dropping a Customer mid-run) — Sam must approve
  - genuine business-policy decision (e.g., notification copy `[UNVERIFIED — requires Sam confirmation]`)
  - 3 consecutive failed attempts on the same scenario after Failure Response Mode A/B/C analysis — STOP and present blocker to Sam
  - rebase conflict on hrms/api/store.py or commissary.py (S196/S192 frozen surfaces)

continue_without_pause_through:
  - Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4A → Phase 4B → Phase 5
  - PR creation
  - Evidence assembly
  - Status reconciliation

blocker_policy:
  - programmatic (linter, type error, missing import) → fix and continue
  - test mode A (app bug) → fix code, file defect, re-run scenario, continue
  - test mode B (test bug) → fix library, re-run, continue
  - test mode C (brittleness) → fix library, re-run, continue
  - business-data/policy → pause for Sam
  - 3 consecutive failures on same scenario → STOP

signoff_authority: single-owner (Sam — CEO)

canonical_closeout_artifacts:
  - output/l3/s198/SUMMARY.md
  - output/l3/s198/state_verification.json
  - output/l3/s198/form_submissions.json
  - output/l3/s198/api_mutations.json
  - output/l3/s198/cleanup_report.json
  - output/l3/s198/cleanup_ledger.json
  - output/l3/s198/blocking_defects.json
  - output/l3/s198/deferred_defects.json
  - output/l3/s198/LIBRARY_IMPROVEMENTS.md (if 3+ library fixes)
  - docs/plans/2026-04-16-sprint-198-warehouse-receiving-flow-completion.md (status flipped)
  - docs/plans/SPRINT_REGISTRY.md (S198 + S192 rows updated)
```

---

## Status Reconciliation Contract

When any of {phase status, scenario score, blocker count, defect count, PR state} changes, the agent updates these in the SAME work unit:
1. `output/l3/s198/state_verification.json`
2. `output/l3/s198/SUMMARY.md`
3. `output/l3/s198/blocking_defects.json` / `deferred_defects.json` (if defect count changed)
4. `docs/plans/2026-04-16-sprint-198-warehouse-receiving-flow-completion.md` (status YAML)
5. `docs/plans/SPRINT_REGISTRY.md` (S198 row, S192 row at closeout)
6. PR description on hrms PR + bei-tasks PR

No partial updates.

---

## Agent Boot Sequence (cold-start ready)

When a fresh agent picks up this plan, it must execute in order:

1. **Read this plan fully** — including Design Rationale, Requirements Regression Checklist, Phase tables, Failure Response, Autonomous Execution Contract.
2. **Read the predecessor evidence:** `output/l3/s192/SUMMARY.md` end-to-end. Understand why S192 failed.
3. **Verify prerequisites:**
   - `git -C F:/Dropbox/Projects/BEI-ERP log origin/production --oneline | grep "fix(S192): normalize S188"` returns the F04 commit
   - `curl -s 'https://hq.bebang.ph/api/method/frappe.client.get_count?doctype=Warehouse' -H "Authorization: token <KEY>:<SECRET>"` returns 200
4. **Create branches** (P0-T1):
   ```bash
   cd F:/Dropbox/Projects/BEI-ERP
   git fetch origin production
   git checkout -b s198-warehouse-receiving-flow-completion origin/production

   cd ../bei-tasks
   git fetch origin main
   git checkout -b s198-warehouse-receiving-queue-ui origin/main
   ```
5. **Fetch credentials:**
   ```bash
   FRAPPE_API_KEY=$(doppler secrets get FRAPPE_API_KEY --plain --project bei-erp --config dev)
   FRAPPE_API_SECRET=$(doppler secrets get FRAPPE_API_SECRET --plain --project bei-erp --config dev)
   ```
6. **Read concurrent agent state:**
   - `git -C F:/Dropbox/Projects/BEI-ERP branch -a | grep -E 's19[5-9]'`
   - If S196/S197 branches show recent activity, expect concurrent edits to `hrms/api/store.py` + `hrms/api/company_master.py` — DO NOT TOUCH those files.
7. **Begin Phase 0 → Phase 5** without pausing for progress-only updates.

---

## Execution Workflow

- Test Python changes locally before deploying: `/local-frappe`
- Deploy Frappe changes (Phase 1+3 backend): builder creates PR, Sam merges, Sam triggers deploy
- Frontend changes (Phase 2+4A+4B): builder creates PR, Sam merges, Vercel auto-deploys main
- L3 testing (Phase 4B): runs against production after both PRs are deployed
- PR-handoff workflow: builder creates PR + STOPS. Sam reviews, merges, deploys. Builder polls PR state for re-work feedback.

---

## Anti-Rewind Checklist

Before pushing each PR:
- [ ] `git -C F:/Dropbox/Projects/BEI-ERP fetch origin production && git rebase origin/production` — clean rebase, no conflicts on protected surfaces
- [ ] `git -C F:/Dropbox/Projects/bei-tasks fetch origin main && git rebase origin/main` — same
- [ ] `git diff --name-only origin/production..HEAD` (hrms) shows ONLY: `hrms/api/warehouse.py`, `hrms/tests/test_s198_*.py`
- [ ] `git diff --name-only origin/main..HEAD` (bei-tasks) shows the two new `page.tsx`, `lib/roles.ts`, `lib/constants.ts`, `lib/sidebar-role-profiles.ts`, the test library files, and the spec
- [ ] No diff hits `hrms/api/store.py`, `hrms/api/company_master.py`, `hrms/api/commissary.py`, or `bei-tasks/app/dashboard/store-ops/order-approvals/page.tsx` (S192/S196 frozen)

---

## Closeout Verification (final gate)

Before declaring COMPLETED:

```bash
# 1. L3 PASS count
python -c "import json; d=json.load(open('output/l3/s198/state_verification.json')); assert d['score']['pass']==7 and d['score']['fail']==0, d['score']"

# 2. Real SI docnames present
python -c "import json,re; d=json.load(open('output/l3/s198/state_verification.json')); [print(s['scenario'], s.get('si_name')) for s in d['scenarios']]; assert all(re.match(r'^ACC-SINV-\d{4}-\d{5}$', s.get('si_name','')) for s in d['scenarios'] if s['scenario'] in ('S1','S2','S4')); s3=[s for s in d['scenarios'] if s['scenario']=='S3'][0]; assert s3.get('si_name') is None, f'S3 should have no SI (billing-hold), got {s3.get(\"si_name\")}'"

# 3. Cleanup ledger reversed
python -c "import json; d=json.load(open('output/l3/s198/cleanup_report.json')); assert d['failed']==[]"

# 4. No HB-4 violations in workflow specs
rg 'page\.request|fetch\(|curl ' bei-tasks/tests/e2e/specs/s190-store-company-integration.spec.ts | grep -v "// HB-4 read-only" && exit 1 || echo "HB-4 OK"

# 5. Plan + registry updated
grep "status: COMPLETED" docs/plans/2026-04-16-sprint-198-warehouse-receiving-flow-completion.md
grep "S198.*COMPLETED" docs/plans/SPRINT_REGISTRY.md
grep "S192.*RETRIED_BY_S198_PASSED" docs/plans/SPRINT_REGISTRY.md
```

If any of these fail, the sprint is NOT COMPLETED. Return to the failing phase.

---

## End of Plan

This plan is self-contained. A cold-start agent should be able to read this document and execute Phase 0 → Phase 5 without consulting any conversation history except the cited evidence files in `output/l3/s192/`.
