---
canonical_id: S226
sprint_name: Sprint 226
plan_filename: 2026-04-27-sprint-226-fix-orphan-approval-queue-rows.md
slug: fix-orphan-approval-queue-rows

branches:
  hrms: s226-fix-orphan-approval-queue-rows

worktrees:
  hrms: F:/Dropbox/Projects/BEI-ERP-s226-fix-orphan-approval-queue-rows

status: GO
created_date: 2026-04-27
completed_date: null
execution_summary: null
work_units: 8
phase_count: 1

canonical_scope: none
canonical_scope_rationale: |
  This sprint changes get_order_review_queue's visibility filter and adds
  on_cancel/on_trash hooks to BEI Store Order. It does NOT touch tabCompany,
  tabWarehouse, tabCustomer, or any canonical resolver. The data fix is on
  tabBEI Approval Queue (a workflow doctype, not master data).

evidence_committed:
  - output/s226/SUMMARY.md
  - output/s226/cleanup_orphan_queue_rows_dry_run.json
  - output/s226/cleanup_orphan_queue_rows_applied.json

evidence_transient:
  - tmp/s226/*.log

depends_on:
  - S225 Phase 1 sweep diagnosis (output/s225/verification/queue_rows_probe.json + timeline_one_order.json)

execution_authority: Sam (CEO) — single-owner. Diagnosed during S225 Phase 1 BLOCKED state; fix carved out as separate sprint per "every new fix = new branch" rule.
---

# S226 — Fix Orphan BEI Approval Queue Rows Hiding Orders from Approvers

## Bottom line

**Three-part fix to a queue-visibility defect that blocked S225 Phase 1's targeted L3 sweep:**

1. **Backend visibility fix** — `get_order_review_queue` SQL: replace the
   "first Pending row's assignee = current user" check with an `EXISTS` that
   matches if ANY Pending row is assigned to the current user. Also tweak the
   GROUP_CONCAT ordering so the displayed `current_approver` prefers the
   current user's row when present.

2. **Backend cascade fix** — add `on_cancel` and `on_trash` hooks to
   BEI Store Order that mark all still-Pending BEI Approval Queue rows
   referencing the cancelled/deleted order as `Rejected` (matches the
   convention already used by `store.reject_order`). Stops the orphan
   accumulation at the source.

3. **One-time data cleanup** — script `s226_cleanup_orphan_queue_rows.py`
   marks the 135 existing orphan Pending rows (whose referenced order is
   deleted or already Fully Approved) as Rejected. Already executed against
   production: 144 Pending → 9 Pending (only legitimate in-flight rows remain).

## Why this exists

S225 Phase 1's targeted 6-store L3 sweep returned 2/6 PASS (4 failures, 2
flaky). Investigation showed the failures were NOT Pattern B/C (the S224
fixes proved working via direct REST probe + container code grep). They were
all "OrderApprovalPage.approve: order BEI-ORD-2026-XXXX did not appear in
the approval queue after 6 navigation attempts" — the test created a fresh
order, but the order was invisible to `test.area@bebang.ph` in the SCM
review queue.

Root cause (proven via `output/s225/verification/queue_rows_probe.json` +
`timeline_one_order.json`):

- The cleanup pattern across S213-S225 was "cancel the order via
  `frappe.cancel`" but never cascaded the cancel to BEI Approval Queue rows
  referencing the order.
- Result: 144 Pending BEI Approval Queue rows accumulated. 135 of them
  reference orders that are either deleted (`docstatus=2` or removed
  entirely) or already Fully Approved. Only 9 are legitimate.
- `get_order_review_queue` SQL uses `LEFT JOIN (... GROUP BY reference_name
  ... SUBSTRING_INDEX(GROUP_CONCAT(... ORDER BY creation ASC), ',', 1) AS
  assigned_approver)` to derive the per-order assignee. This picks the
  OLDEST Pending row's assignee.
- For a fresh order with multiple Pending rows accumulated from prior runs
  (alternating area-supervisor / warehouse-manager assignees because each
  run creates 1-2 entries), the OLDEST Pending row's assignee is often
  `ian@bebang.ph` (Warehouse Manager). The visibility filter
  `pending_queue.assigned_approver = current_user` then excludes the order
  from `test.area@bebang.ph`'s view.

The S225 sweep test failures are a real product-behaviour issue (an operator
who is assigned a Pending row for an order with older orphan Pending rows
would also lose visibility), not just a test infrastructure quirk.

## Scope

**Files modified:**

- `hrms/api/ordering.py` — `get_order_review_queue` SQL (visibility filter +
  GROUP_CONCAT ordering)
- `hrms/hr/doctype/bei_store_order/bei_store_order.py` — adds `on_cancel`,
  `on_trash`, and `_close_pending_approval_queue_rows` helper
- `scripts/s226_cleanup_orphan_queue_rows.py` (NEW) — one-time data fix

**Forbidden:**

- No changes to `bei-tasks` (frontend) — CEO directive 2026-04-25 is
  permanent.
- No changes to BEI Approval Queue doctype schema (using existing
  `Rejected` status option, not adding `Cancelled`).
- No changes to canonical master data (this is workflow data, not store/
  company master data — `canonical_scope: none`).

## Phase 1 — Implementation, Cleanup, PR (8 units)

### Tasks (all DONE in this sprint's single phase)

1. **Diagnose** the S225 Phase 1 sweep failures. Build
   `scripts/s226_diagnose_order_queue_gap.py` and
   `scripts/s226_probe_queue_rows.py`. Confirm 144 Pending rows, 135 orphans,
   alternating ian/test.area assignee pattern. Evidence:
   `output/s225/verification/queue_rows_probe.json` + `timeline_one_order.json`
   (in S225 worktree).

2. **Backend fix #1** — `get_order_review_queue` visibility filter. Add
   `EXISTS (SELECT 1 FROM tabBEI Approval Queue qx WHERE ... AND
   qx.assigned_approver = %(current_user)s)` to the WHERE clause so any
   matching Pending row makes the order visible.

3. **Backend fix #2** — `BEI Store Order.on_cancel` + `on_trash` hooks call
   `_close_pending_approval_queue_rows(self.name)` which marks every Pending
   queue row for this order as `Rejected` with rejection_reason
   "Order cancelled/deleted".

4. **Data fix** — write `scripts/s226_cleanup_orphan_queue_rows.py`. Two
   paths: doctype `.save()` for ORDER_FULLY_APPROVED orphans (validation
   passes), direct SQL UPDATE for ORDER_DELETED orphans (validation fails
   because reference_name is missing — safe to bypass since the order doesn't
   exist and the queue row has no GL/SLE dependency). Apply with `--commit`.

5. **PR + handoff** — push branch, create PR to production, hand off to Sam
   for merge + deploy.

### Verification (DONE)

- Cleanup result: 144 Pending → 9 Pending (verified via
  `output/s226/cleanup_orphan_queue_rows_applied.json`).
- Code change diff: `git diff --name-only origin/production` returns exactly:
  - `hrms/api/ordering.py`
  - `hrms/hr/doctype/bei_store_order/bei_store_order.py`
  - `scripts/s226_cleanup_orphan_queue_rows.py` (NEW)
  - `docs/plans/2026-04-27-sprint-226-fix-orphan-approval-queue-rows.md` (NEW)
  - `docs/plans/SPRINT_REGISTRY.md` (S226 row added)
  - `output/s226/*` (cleanup evidence)

### Sentry instrumentation

The `get_order_review_queue` function already has
`set_backend_observability_context(module="ordering",
action="get_order_review_queue", mutation_type="read")` — preserved
unchanged. No new whitelisted endpoints added.

## Failure response

If the deployed fix doesn't unblock the S225 sweep, possible follow-ups
(not in this sprint):

- The 9 remaining "legitimate" Pending rows might themselves have a wrong
  assignee for the current state of their order. A second-pass cleanup that
  reads the ToDo allocation as the source-of-truth could be added.
- The S209 cleanup script could also call the cascade helper directly so
  cleanup-side cancellations cascade properly even if the doctype hook is
  bypassed (e.g., when frappe.delete_doc with force=1 is used and on_trash
  is skipped).

## After this PR merges + deploys

Resume S225 Phase 1: re-run the targeted 6-store sweep. Expectation: 6/6
PASS, allowing S225 to proceed to Phase 2 (canonical warehouse audit).

## Files

- `hrms/api/ordering.py` (modified — visibility EXISTS subquery + GROUP_CONCAT ORDER BY tweak)
- `hrms/hr/doctype/bei_store_order/bei_store_order.py` (modified — on_cancel + on_trash + helper)
- `scripts/s226_cleanup_orphan_queue_rows.py` (NEW)
- `output/s226/cleanup_orphan_queue_rows_applied.json` (evidence — applied)
- `output/s226/cleanup_orphan_queue_rows_dry_run.json` (evidence — dry run)
- `docs/plans/2026-04-27-sprint-226-fix-orphan-approval-queue-rows.md` (this file)
- `docs/plans/SPRINT_REGISTRY.md` (S226 row)
