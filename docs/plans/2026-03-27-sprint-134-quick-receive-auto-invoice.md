# Sprint S134 — Quick Receive + Auto-Invoice + PO Data Fixes

```yaml
sprint_id: S134
display: Sprint 134
slug: quick-receive-auto-invoice
branch: s134-quick-receive-auto-invoice
status: PLANNED
planned_date: 2026-03-27
completed_date: null
depends_on: [S128, S132]
total_units: 14
backend_pr: null
frontend_pr: null
l3_result: null
execution_summary: null
```

**Goal:** Speed up the delivery-to-invoice chain. Ian records GR in one click, invoice auto-drafts. Also fix PO warehouse defaults and clean up stale test data from S132 findings.

**Depends on:** S128 (shipped), S132 (shipped)

**Impact:**
- Ian: GR creation from 5 min to 30 seconds for matching deliveries
- Cayla: Invoice creation eliminated for deliveries where GR matches PO
- Mae: Stale test POs cleaned from Pending tab

**Roadmap:** `docs/plans/2026-03-25-procurement-ops-efficiency-roadmap-sprints.md` (was labeled S129 in the roadmap; renumbered to S134 for registry compliance)

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
  - business_policy: unclear business rule
  - direct_overwrite: conflicting active work on same files
signoff_authority: single-owner (Sam)
deploy_handoff: PR creation → share PR# → STOP (user merges)
governor_feedback_loop: |
  REJECT: read PR comment, fix, push
  NEEDS_FIX: apply fix, push
  Merge Conflict: rebase against production, resolve, force-push
  Deploy Failure: check logs, fix if code issue
release_manager_gate: |
  git add -f output/l3/S134/ && git push after L3
confidence_threshold: reviews with confidence < 0.80 pause auto-merge
```

---

## Ownership Matrix

| File/Surface | Owner | Protected? |
|---|---|---|
| `hrms/api/procurement.py` | S134 | No — extending |
| `bei-tasks/app/dashboard/procurement/goods-receipts/*` | S134 | No — new/extending |
| `bei-tasks/app/dashboard/procurement/invoices/*` | S134 | No — extending |
| `hrms/hr/doctype/bei_purchase_order/bei_purchase_order.py` | S134 (ship_to fix only) | Shared — minimal touch |

**Protected surfaces (DO NOT TOUCH):**
- CEO approval flow (S132)
- Batch approve / duplicate (S128)
- Store ordering (S129 registry)
- PO list page layout

---

## Phase A: Quick Receive (5 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| A1 | EXTEND | Frontend: On GR new page, after selecting PO + items load, add prominent button: "Received All as Ordered". Clicking it auto-fills all received_qty = ordered_qty and submits. | 3 |
| A2 | IMPROVE | Backend: Chain existing `create_goods_receipt()` + `load_gr_from_po()` + `submit_goods_receipt()`. No new endpoint needed — frontend calls the existing sequence. Sentry on any new/modified endpoint. | 1 |
| A3 | VERIFY | L3: Select PO → click "Received All as Ordered" → GR created with correct quantities. | 1 |

## Phase B: Auto-Invoice from GR (3 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| B1 | BUILD | Frontend: After GR creation success, show prompt: "Create invoice?" with invoice # and date fields pre-filled. Navigate to invoice form with `?goods_receipt=GR-XXXX&purchase_order=PO-XXXX` query params. Backend `create_invoice()` already accepts `goods_receipt` param (line 1906) — no backend work needed. | 2 |
| B2 | VERIFY | L3: Create GR → invoice prompt → fill invoice # → invoice created with correct amounts. | 1 |

## Phase C: PO Data Fixes (3 units)

*Carried from S132 L3 findings.*

| Task | Type | Description | Units |
|------|------|-------------|-------|
| C1 | FIX | Set default `ship_to` warehouse on BEI PO creation. If supplier has a preferred warehouse, use it; otherwise default to "Stores - BEI". Ensures `create_frappe_purchase_order()` sync doesn't fail on missing warehouse. **HARD BLOCKER:** Must use existing warehouse names from `docs/erp/WAREHOUSE_TREE_2025-12-31.csv`. | 1.5 |
| C2 | DATA | Clean up stale test POs (PO-2026-00069, PO-2026-00073) via `bench console`. Set `price_variance_override` or cancel them. Execute via SSM with preview-before-mutate protocol. | 0.5 |
| C3 | VERIFY | Verify batch approve works end-to-end with warehouse set — PO approved AND Frappe PO created without orange warning. | 1 |

## Phase D: Deploy + L3 + Closeout (3 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| D1 | DEPLOY | Create PRs for hrms and bei-tasks repos targeting production. Share PR numbers with user. | 1 |
| D2 | L3 | Generate L3 handoff prompt for fresh session testing. | 1 |
| D3 | CLOSEOUT | Update plan YAML status to COMPLETED/PR_CREATED. Update SPRINT_REGISTRY.md. `git add -f` for docs/ and output/l3/S134/. | 1 |

---

## L3 Workflow Scenarios

| # | Type | Scenario | Inputs | Expected |
|---|------|----------|--------|----------|
| L3-1 | happy | Quick Receive — full match | Select approved PO with 3 items → click "Received All as Ordered" | GR created with all 3 items, received_qty = ordered_qty |
| L3-2 | happy | Auto-Invoice prompt | After GR-1 created → click "Create Invoice?" → fill invoice# "INV-TEST-001" | Invoice created linked to GR and PO, amounts match |
| L3-3 | happy | PO with warehouse default | Create new PO without manually setting ship_to → submit → Mae approve | Frappe PO created successfully, no orange warning about missing warehouse |
| L3-4 | adversarial | Partial receive (no quick button) | Select PO → modify received_qty for 1 item to less than ordered | GR created with partial quantities, PO status remains Partially Received |
| L3-5 | adversarial | Stale PO cleanup verified | Check PO-2026-00069 and PO-2026-00073 | Both POs cancelled or have price_variance_override set |

---

## Design Rationale (For Cold-Start Agents)

1. **Quick Receive is a frontend shortcut, not a new API.** The backend already has `create_goods_receipt()`, `load_gr_from_po()`, and `submit_goods_receipt()`. The feature is a single button that chains these existing calls.
2. **Auto-Invoice uses existing `create_invoice(goods_receipt=...)`.** Line 1906 of `procurement.py` already accepts this parameter. No new backend endpoint needed — just a frontend prompt after GR success.
3. **Warehouse default prevents Frappe PO sync failures.** S132 L3 found that POs created without `ship_to` cause `create_frappe_purchase_order()` to fail with "Warehouse is mandatory for stock Item". The fix is setting a default at PO creation time.
4. **Stale test POs block Mae's workflow.** PO-2026-00069 and PO-2026-00073 were created during S132 testing and sit in Mae's Pending tab with price variance issues.

---

## Requirements Regression Checklist

- [ ] Quick Receive button calls existing GR APIs (no new endpoint)
- [ ] Auto-Invoice uses existing `create_invoice(goods_receipt=...)` parameter
- [ ] Warehouse default is "Stores - BEI" (matches warehouse tree)
- [ ] Stale POs cleaned via SSM preview-before-mutate
- [ ] Sentry on any new/modified `@frappe.whitelist()` endpoint
- [ ] No changes to CEO approval flow (S132 protected)
- [ ] No changes to batch approve/duplicate (S128 protected)

---

## Revision History

- **v1 (2026-03-27):** Initial plan. Scope from procurement roadmap v3 (was labeled S129, renumbered to S134 for registry compliance). 14 units across 4 phases.
