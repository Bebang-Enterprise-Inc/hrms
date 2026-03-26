# Sprint S128 — PO Batch Approve + Duplicate

```yaml
sprint: S128
branch: s128-po-batch-approve-duplicate
status: IN_PROGRESS
execution_started: 2026-03-26
plan_file: docs/plans/2026-03-26-sprint-128-po-batch-approve-duplicate.md
roadmap: docs/plans/2026-03-25-procurement-ops-efficiency-roadmap-sprints.md
```

## Goal

Eliminate Mae's one-at-a-time PO approval bottleneck (70 POs/month) and give Cayla one-click PO duplication for repeat orders (80% of POs are duplicates).

## Scope (~15 units)

### Phase A: Backend (5 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| A1 | BUILD | `batch_approve_pos(names, level, comment)` — loops through POs, calls existing `approve_mae()`/`approve_butch()` per PO. Returns per-PO success/failure. Sentry instrumented. | 2 |
| A2 | BUILD | `duplicate_po(source_name)` — reads existing PO, creates new Draft PO with same supplier + items + prices. New PO date = today, new PO number auto-generated. Sentry instrumented. | 2 |
| A3 | BUILD | Add route mappings in API proxy for batch approve and duplicate endpoints. | 1 |

### Phase B: Frontend (8 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| B1 | BUILD | PO list page: Add checkboxes to "Pending Approval" tab rows. Floating action bar when 1+ selected showing "[Approve Selected (N)]" and "[Reject Selected]". | 3 |
| B2 | BUILD | Batch approval summary modal: Table showing selected POs with PO#, Supplier, Items count, Total Amount. "Approve All N" button. Comment field. Per-PO success/failure results. | 3 |
| B3 | BUILD | PO detail page: "Duplicate PO" button (visible for Approved/Sent/Received POs). Creates draft PO and redirects to it. | 2 |

### Phase C: Hooks + Deploy (2 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| C1 | BUILD | `useBatchApprovePOs()` and `useDuplicatePO()` hooks in use-procurement.ts. | 1 |
| C2 | BUILD | Create PRs for hrms and bei-tasks. | 1 |

## L3 Workflow Scenarios

| # | Scenario | Steps | Expected |
|---|----------|-------|----------|
| L3-1 | Batch approve 2+ POs | Log in as mae@bebang.ph → PO list → Pending Approval tab → check 2+ POs → click "Approve Selected" → review summary modal → click "Approve All" | All selected POs move to Approved status. Toast shows success count. |
| L3-2 | Batch approve with >500K PO | Same flow but include a >500K PO | >500K PO should NOT be batch-approvable by Mae (requires Butch). Error shown for that PO, others succeed. |
| L3-3 | Duplicate a PO | Log in as procurement user → PO detail of an Approved PO → click "Duplicate PO" | New Draft PO created with same supplier, items, prices. Redirected to new PO. |

## Autonomous Execution Contract

- **Completion condition:** PRs created for hrms and bei-tasks, L3 handoff prompt generated
- **Stop-only-for:** Missing credentials, business-policy decision
- **Branch:** `s128-po-batch-approve-duplicate`
- **Signoff:** Single-owner (Sam)

## Files Touched

**hrms repo:**
- `hrms/api/procurement.py` — add `batch_approve_pos()`, `duplicate_po()`

**bei-tasks repo:**
- `hooks/use-procurement.ts` — add `useBatchApprovePOs()`, `useDuplicatePO()`
- `app/api/procurement/[...slug]/route.ts` — add route mappings
- `app/dashboard/procurement/purchase-orders/page.tsx` — batch approve UI
- `app/dashboard/procurement/purchase-orders/[id]/page.tsx` — duplicate button
