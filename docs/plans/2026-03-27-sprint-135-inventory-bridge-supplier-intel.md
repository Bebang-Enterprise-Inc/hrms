# Sprint S135 — Inventory Bridge + Supplier Intelligence

```yaml
sprint_id: S135
display: Sprint 135
slug: inventory-bridge-supplier-intel
branch: s135-inventory-bridge-supplier-intel
status: PR_CREATED
planned_date: 2026-03-27
execution_started: 2026-03-27
completed_date: null
depends_on: [S128, S134, S121]
total_units: 22-24
backend_pr: 375
frontend_pr: 270
l3_result: null
execution_summary: null
```

**Goal:** Connect inventory data to procurement decisions. Luwi sees what's running low and the system suggests reorders. Supplier document expiry alerts prevent compliance gaps.

**Depends on:** S128 (shipped), S134 (Quick Receive must be done so GR flow works), S121 (store inventory sync — COMPLETED)

**Impact:**
- Luwi: Sees low-stock items on dashboard, creates PRs with one click
- Luwi: Supplier doc expiry alerts 30 days before expiry
- Ian: Sees expected deliveries this week on dashboard

**Roadmap:** `docs/plans/2026-03-25-procurement-ops-efficiency-roadmap-sprints.md` (was labeled S130 in the roadmap; renumbered to S135 for registry compliance)

---

## Autonomous Execution Contract

```yaml
completion_condition: |
  - All 4 phases implemented and deployed
  - Plan YAML status updated to COMPLETED
  - SPRINT_REGISTRY.md updated with final status
  - L3 evidence committed to branch
stop_only_for:
  - missing_access: credentials/session not available
  - destructive_approval: deleting production data
  - business_policy: unclear business rule (e.g., reorder thresholds)
  - direct_overwrite: conflicting active work on same files
signoff_authority: single-owner (Sam)
deploy_handoff: PR creation → share PR# → STOP (user merges)
governor_feedback_loop: |
  REJECT: read PR comment, fix, push
  NEEDS_FIX: apply fix, push
  Merge Conflict: rebase against production, resolve, force-push
  Deploy Failure: check logs, fix if code issue
release_manager_gate: |
  git add -f output/l3/S135/ && git push after L3
confidence_threshold: reviews with confidence < 0.80 pause auto-merge
```

---

## Ownership Matrix

| File/Surface | Owner | Protected? |
|---|---|---|
| `hrms/api/procurement.py` (new endpoints only) | S135 | Shared — additive only |
| `hrms/api/warehouse.py` (new endpoints only) | S135 | Shared — additive only |
| `hrms/hr/doctype/bei_supplier/bei_supplier.json` | S135 | No — adding fields |
| `bei-tasks/app/dashboard/procurement/dashboard/*` | S135 | No — new widgets |
| `bei-tasks/app/dashboard/procurement/suppliers/*` | S135 | No — extending |

**Protected surfaces (DO NOT TOUCH):**
- CEO approval flow (S132)
- Batch approve / duplicate (S128)
- Quick Receive / Auto-Invoice (S134)
- Store ordering (S129 registry)
- PO list/detail pages (S128/S132)

---

## Phase A: Inventory → PR Bridge (8 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| A1 | BUILD | Backend: `get_low_stock_items(threshold_days=7)` — queries warehouse inventory, calculates days-of-stock-remaining based on consumption rate, returns items below threshold. | 4 |
| A2 | IMPROVE | Backend: Use existing `create_purchase_requisition()` with pre-filled data for stock alerts. No new function needed — the PR creation API already handles this. | 0.5 |
| A3 | BUILD | Frontend: "Stock Alerts" widget on procurement dashboard — items below reorder threshold with color coding (red <3 days, yellow <7 days). Each row: item, current stock, daily consumption, days remaining, [Create PR] button. | 3 |
| A4 | VERIFY | L3: Dashboard shows low-stock items → click Create PR → PR created with correct items and suggested quantities. | 0.5 |

## Phase B: Auto PR-to-PO + Supplier Enhancements (8 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| B1 | EXTEND | Backend: `auto_convert_pr_to_po(pr_name)` — thin wrapper over existing `convert_pr_to_po()` + `get_contracted_price()` from S104. If PR has single-source supplier with contracted price, auto-create PO draft. | 1 |
| B2 | BUILD | Backend: Add `bir_expiry_date`, `sec_expiry_date`, `permit_expiry_date` fields to BEI Supplier DocType. Cron job: `check_supplier_document_expiry()` — alerts 30 days before expiry via Google Chat. | 4 |
| B3 | BUILD | Frontend: Supplier detail page — show document expiry status (green/yellow/red badges). Supplier list — show "N documents expiring" filter. | 2 |
| B4 | VERIFY | L3: PR with single-source supplier → auto PO draft created. Supplier with expiring doc → alert sent. | 1 |

## Phase C: Today's Deliveries Widget (3 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| C1 | BUILD | Frontend: Dashboard widget — "Deliveries Expected This Week" from POs where delivery_date is this week and status is Approved/Sent. Shows: supplier, PO#, items, date. Color: green=on-time, red=overdue. | 2 |
| C2 | VERIFY | L3: Dashboard shows expected deliveries matching PO delivery dates. | 1 |

## Phase D: Deploy + L3 + Closeout (3-5 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| D1 | DEPLOY | Create PRs for hrms and bei-tasks repos targeting production. Share PR numbers with user. | 1 |
| D2 | L3 | Generate L3 handoff prompt for fresh session testing. | 1 |
| D3 | CLOSEOUT | Update plan YAML status. Update SPRINT_REGISTRY.md. `git add -f` for docs/ and output/l3/S135/. | 1-3 |

---

## L3 Workflow Scenarios

| # | Type | Scenario | Inputs | Expected |
|---|------|----------|--------|----------|
| L3-1 | happy | Stock Alerts widget loads | Navigate to procurement dashboard | Stock Alerts widget shows items with <7 days of stock, color-coded |
| L3-2 | happy | Create PR from stock alert | Click [Create PR] on a low-stock item | PR created with item, suggested quantity, and supplier pre-filled |
| L3-3 | happy | Auto PR-to-PO conversion | Create PR for single-source supplier with contracted price → approve PR | PO draft auto-created with correct prices from contracted price master |
| L3-4 | happy | Supplier doc expiry badges | Navigate to supplier detail page for supplier with expiry dates set | Green/yellow/red badges showing document expiry status |
| L3-5 | happy | Deliveries widget | Navigate to procurement dashboard | "Deliveries Expected This Week" shows approved POs with delivery_date this week |
| L3-6 | adversarial | Multi-source supplier blocks auto-convert | Create PR for item with 2+ suppliers | Auto-convert does NOT trigger — PR stays as PR for manual PO creation |
| L3-7 | adversarial | No stock data available | View Stock Alerts widget when warehouse has no consumption history | Widget shows empty state: "No consumption data available" |

---

## Design Rationale (For Cold-Start Agents)

1. **Low stock calculation uses consumption rate.** `get_low_stock_items()` divides current stock by average daily consumption (from GR/Stock Entry history) to get days-of-stock-remaining. Threshold is configurable (default 7 days).
2. **PR creation reuses existing API.** `create_purchase_requisition()` already exists and handles all validation. The stock alert widget just pre-fills the form data.
3. **Auto PR-to-PO is a thin wrapper.** `convert_pr_to_po()` and `get_contracted_price()` from S104 already exist. The new function just checks single-source + contracted price conditions before calling them.
4. **Supplier doc expiry uses Google Chat.** BEI uses Google Chat for notifications (not email). The cron job calls the existing `send_google_chat_notification()` helper.
5. **Deliveries widget queries PO delivery_date.** Simple query: POs where `delivery_date` is this week AND status in (Approved, Sent to Supplier). No new data model needed.

---

## Requirements Regression Checklist

- [ ] `get_low_stock_items()` uses consumption rate, not just current stock
- [ ] Stock alert threshold is configurable (default 7 days)
- [ ] PR creation uses existing `create_purchase_requisition()` API
- [ ] Auto PR-to-PO only triggers for single-source + contracted price
- [ ] Supplier expiry fields added to BEI Supplier DocType (BIR, SEC, permit)
- [ ] Expiry cron uses Google Chat notification (not email)
- [ ] Deliveries widget queries existing PO delivery_date field
- [ ] Sentry on all new `@frappe.whitelist()` endpoints
- [ ] No changes to S128/S132/S134 protected surfaces

---

## Revision History

- **v1 (2026-03-27):** Initial plan. Scope from procurement roadmap v3 (was labeled S130, renumbered to S135 for registry compliance). 22-24 units across 4 phases.
