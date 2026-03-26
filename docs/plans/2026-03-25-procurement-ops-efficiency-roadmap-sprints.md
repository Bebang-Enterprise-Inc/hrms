# Procurement Operations Efficiency — Sprint Roadmap (v3 — Post-Execution Audit)

**Purpose:** Master plan splitting procurement improvements into executable sprints. This is the routing document — individual sprint plans are written separately.

**Last updated:** 2026-03-27 (v4 — renumbered S129→S134, S130→S135 for registry compliance)

**Context:**
- **Team:** Cayla (solo PO processor, 70 POs/month), Luwi (sourcing/planning), Ian (warehouse/PRs/deliveries), Mae (CPO approver), Sam (CEO approver for new vendors)
- **Data:** 80% of POs are exact duplicates (same supplier + same items). 561 POs over 7 months. P213M total spend.
- **Source:** AppSheet Procurement Compliance Database (`1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q`)

---

## Feature Audit Summary

| # | Feature | Classification | Status | Sprint |
|---|---------|---------------|--------|--------|
| 1 | PO Duplicate (was Templates) | **[BUILD]** | SHIPPED (S128) — "Duplicate PO" button on PO detail | S128 |
| 2 | PO Review Step (Luwi) | **[CANCELLED]** | Process not validated with users, adds bottleneck | — |
| 3 | Batch Approval (Mae) | **[BUILD]** | SHIPPED (S128) — checkboxes, modal, per-PO results | S128 |
| 4 | Quick Receive | **[EXTEND]** | PLANNED | S134 |
| 5 | Auto-Invoice from GR | **[EXTEND]** | PLANNED (backend DONE — `create_invoice` accepts `goods_receipt`) | S134 |
| 6 | RFP Approval Flow | **[EXISTS]** | SKIP — 4-level chain in BEI Payment Request | — |
| 7 | Inventory→PR Bridge | **[EXTEND]** | PLANNED | S135 |
| 8 | Supplier Price Alerts | **[EXISTS]** | SKIP — `check_price_variance()` @ line 3456 | — |
| 9 | PO-to-GR Matching | **[EXISTS]** | SKIP — `get_pending_gr_for_po()` @ line 1731 | — |
| 10 | Auto PR-to-PO | **[EXTEND]** | PLANNED | S135 |
| 11 | Spend Analytics | **[EXISTS]** | SKIP — `get_monthly_spend_report()` full | — |
| 12 | Supplier Doc Expiry | **[BUILD]** | PLANNED — no expiry fields on DocType | S135 |
| 13 | GR Variance Report | **[EXISTS]** | SKIP — 3-way match report | — |
| — | CEO Approval (new vendors) | **[FIX]** | SHIPPED (S132) — 5 broken layers fixed | S132 |
| — | PO Price Edit + Autocomplete | **[BUILD]** | SHIPPED (S120) — inline edit with reason, item search | S120 |
| — | Frappe PO Sync Non-Blocking | **[FIX]** | SHIPPED (S132) — approval no longer blocked by sync failure | S132 |
| — | PO Warehouse Default | **[FIX]** | PLANNED — POs created without `ship_to` | S134 |
| — | Stale Test PO Cleanup | **[DATA]** | PLANNED — PO-2026-00069/73 blocking Mae's tab | S134 |

**6 features SKIP** (already exist). **1 CANCELLED** (PO Review Step). **5 SHIPPED** (S120, S128, S132). **4 features remain** across 2 sprints (S134, S135).

---

## Completed Sprints

### S120 — Item Master Price Sync (COMPLETED 2026-03-26)
- Item autocomplete (`ItemSearchCombobox`), inline price edit with mandatory reason
- Price variance gate (10% threshold), PR form dropdown enforcement
- ₱0 price blocked, contracted price chain: BEI Contracted → Item Price → standard_rate

### S128 — PO Batch Approve + Duplicate (COMPLETED 2026-03-26)
- **Batch Approve:** Checkboxes on PO list, "Approve Selected (N)" button, summary modal with amounts, per-PO success/failure results, RBAC enforced (only mae@bebang.ph)
- **Duplicate PO:** One-click duplicate with items+prices preserved, redirect to new Draft PO
- PRs: hrms #366, BEI-Tasks #254
- L3: 5/5 PASS (batch approve, results modal, duplicate items+prices, Draft PO adversarial, RBAC adversarial)

### S132 — CEO Approval + Collateral Fixes (COMPLETED 2026-03-26)
- Fixed 5 broken layers: DocType status, API endpoint, reject guard, approval gate, CEO notification
- Added `approve_po_ceo()` with Sentry, `notify_ceo()` sends Google Chat to sam@bebang.ph
- Fixed `has_required_procurement_approvals()` — CEO sign-off now enforced (was advisory)
- Fixed `create_frappe_purchase_order()` — non-blocking on failure (was rolling back approval)
- Added Sentry to 4 existing endpoints (submit, approve_mae, approve_butch, reject)
- PRs: hrms #369, #371, BEI-Tasks #267
- L3: 4/4 PASS (batch approve, new vendor → CEO pending, CEO approve, CEO reject)

---

## Remaining Planned Sprints

### Sprint S134 — Ian + Cayla Bridge (Quick Receive + Auto-Invoice + PO Data Fixes)

**Goal:** Speed up the delivery → invoice chain. Ian records GR in one click, invoice auto-drafts. Also fix PO warehouse defaults and clean up stale test data from S132 findings.

**Depends on:** S128 (shipped), S132 (shipped)

**Impact:**
- Ian: GR creation from 5 min → 30 seconds for matching deliveries
- Cayla: Invoice creation eliminated for deliveries where GR matches PO
- Mae: Stale test POs cleaned from Pending tab

#### Scope (~14 units)

**Phase A: Quick Receive (5 units)**

| Task | Type | Description | Units |
|------|------|-------------|-------|
| A1 | EXTEND | Frontend: On GR new page, after selecting PO + items load, add prominent button: "Received All as Ordered". Clicking it auto-fills all received_qty = ordered_qty and submits. | 3 |
| A2 | IMPROVE | Backend: Chain existing `create_goods_receipt()` + `load_gr_from_po()` + `submit_goods_receipt()`. No new endpoint needed — frontend calls the existing sequence. Sentry on any new/modified endpoint. | 1 |
| A3 | VERIFY | L3: Select PO → click "Received All as Ordered" → GR created with correct quantities. | 1 |

**Phase B: Auto-Invoice from GR (3 units)**

| Task | Type | Description | Units |
|------|------|-------------|-------|
| B1 | BUILD | Frontend: After GR creation success, show prompt: "Create invoice?" with invoice # and date fields pre-filled. Navigate to invoice form with `?goods_receipt=GR-XXXX&purchase_order=PO-XXXX` query params. Backend `create_invoice()` already accepts `goods_receipt` param (line 1906) — no backend work needed. | 2 |
| B2 | VERIFY | L3: Create GR → invoice prompt → fill invoice # → invoice created with correct amounts. | 1 |

**Phase C: PO Data Fixes (3 units)** *(carried from S132 L3 findings)*

| Task | Type | Description | Units |
|------|------|-------------|-------|
| C1 | FIX | Set default `ship_to` warehouse on BEI PO creation. If supplier has a preferred warehouse, use it; otherwise default to "Stores - BEI". Ensures `create_frappe_purchase_order()` sync doesn't fail on missing warehouse. | 1.5 |
| C2 | DATA | Clean up stale test POs (PO-2026-00069, PO-2026-00073) via `bench console`. Set `price_variance_override` or cancel them. Execute via SSM with preview-before-mutate protocol. | 0.5 |
| C3 | VERIFY | Verify batch approve works end-to-end with warehouse set — PO approved AND Frappe PO created without orange warning. | 1 |

**Phase D: Deploy + L3 + Closeout (3 units)**

---

### Sprint S135 — Luwi Strategic Tools (Inventory Bridge + Supplier Intelligence)

**Goal:** Connect inventory data to procurement decisions. Luwi sees what's running low and the system suggests reorders.

**Depends on:** S128 (shipped), S134 (Quick Receive must be done so GR flow works), S121 (store inventory sync — COMPLETED)

#### Scope (~22-24 units)

**Phase A: Inventory → PR Bridge (8 units)**

| Task | Type | Description | Units |
|------|------|-------------|-------|
| A1 | BUILD | Backend: `get_low_stock_items(threshold_days=7)` — queries warehouse inventory, calculates days-of-stock-remaining based on consumption rate, returns items below threshold. | 4 |
| A2 | IMPROVE | Backend: Use existing `create_purchase_requisition()` with pre-filled data for stock alerts. No new function needed — the PR creation API already handles this. | 0.5 |
| A3 | BUILD | Frontend: "Stock Alerts" widget on procurement dashboard — items below reorder threshold with color coding (red <3 days, yellow <7 days). Each row: item, current stock, daily consumption, days remaining, [Create PR] button. | 3 |
| A4 | VERIFY | L3: Dashboard shows low-stock items → click Create PR → PR created with correct items and suggested quantities. | 0.5 |

**Phase B: Auto PR-to-PO + Supplier Enhancements (8 units)**

| Task | Type | Description | Units |
|------|------|-------------|-------|
| B1 | EXTEND | Backend: `auto_convert_pr_to_po(pr_name)` — thin wrapper over existing `convert_pr_to_po()` + `get_contracted_price()` from S104. If PR has single-source supplier with contracted price, auto-create PO draft. | 1 |
| B2 | BUILD | Backend: Add `bir_expiry_date`, `sec_expiry_date`, `permit_expiry_date` fields to BEI Supplier DocType. Cron job: `check_supplier_document_expiry()` — alerts 30 days before expiry via Google Chat. | 4 |
| B3 | BUILD | Frontend: Supplier detail page — show document expiry status (green/yellow/red badges). Supplier list — show "N documents expiring" filter. | 2 |
| B4 | VERIFY | L3: PR with single-source supplier → auto PO draft created. Supplier with expiring doc → alert sent. | 1 |

**Phase C: Today's Deliveries Widget (3 units)**

| Task | Type | Description | Units |
|------|------|-------------|-------|
| C1 | BUILD | Frontend: Dashboard widget — "Deliveries Expected This Week" from POs where delivery_date is this week and status is Approved/Sent. Shows: supplier, PO#, items, date. Color: green=on-time, red=overdue. | 2 |
| C2 | VERIFY | L3: Dashboard shows expected deliveries matching PO delivery dates. | 1 |

**Phase D: Deploy + L3 + Closeout (3-5 units)**

---

## Sprint Dependency Map (Current)

```
S121 (Inventory Sync Fix — COMPLETED)
S120 (Item Master Price Sync — COMPLETED)
        ↓
S128 (Batch Approve + Duplicate — COMPLETED)
S132 (CEO Approval Fix — COMPLETED)
        ↓
S134 (Quick Receive + Auto-Invoice + PO Data Fixes — PLANNED)
        ↓
S135 (Inventory Bridge + Supplier Intelligence — PLANNED)
```

S134 and S135 run sequentially. S135 depends on S134 (GR flow must work before connecting inventory to procurement).

---

## Features That Already Exist (No Sprint Needed)

| # | Feature | Why Skip |
|---|---------|----------|
| 6 | RFP Approval Flow | Already 4-level chain in BEI Payment Request DocType |
| 8 | Supplier Price Alerts | `check_price_variance()` with 5%/10% thresholds exists |
| 9 | PO-to-GR Matching | `get_pending_gr_for_po()` exists, surfaced in reports |
| 11 | Spend Analytics | `get_monthly_spend_report()` full dashboard exists |
| 13 | GR Variance Report | 3-way match report with variance calculations exists |

---

## Total Effort

| Sprint | Units | Status |
|--------|-------|--------|
| S120 (item master price sync) | 38 | COMPLETED |
| S121 (inventory sync fix) | 18 | COMPLETED |
| S128 (batch approve + duplicate) | 15 | COMPLETED |
| S132 (CEO approval + collateral) | 15 | COMPLETED |
| S134 (quick receive + auto-invoice + data fixes) | 14 | PLANNED |
| S135 (inventory bridge + supplier intel) | 22-24 | PLANNED |
| **Total delivered** | **86** | |
| **Total remaining** | **36-38** | |

---

## Revision History

- **v1 (2026-03-25):** Original roadmap — 101 units across S122/S123/S124 (placeholder numbers)
- **v2 (2026-03-26):** Audit — renumbered to S128/S129/S130, cancelled PO Review Step, consolidated PO Templates → Duplicate, identified auto-invoice backend as done. Reduced to 47-53 units.
- **v3 (2026-03-26):** Post-execution — S128 and S132 completed. Added S120/S132 to completed sprints. S129 updated with PO data fixes from S132 L3. S130 scope reduced (auto-convert wrapper is trivial, stock alert PR creation uses existing API). Feature audit table updated to reflect current reality. Dependency map updated.
- **v4 (2026-03-27):** Registry compliance — renumbered roadmap S129→S134 and S130→S135 (S129 was already consumed by Store Ordering Redesign in the canonical sprint registry). Created standalone plan files: `2026-03-27-sprint-134-quick-receive-auto-invoice.md` and `2026-03-27-sprint-135-inventory-bridge-supplier-intel.md`.

## Data Sources

| Source | ID | What It Contains |
|--------|------|-----------------|
| Procurement AppSheet | `1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q` | 561 POs, 489 PRs, 958 GRs, 91 suppliers, approval matrix |
| Ian's WHSE Inventory | `1piMVW6nH7l_8lsXFqJ-LBZUbbXhyXgzvJPpLjo3LUNA` | 11,510 March transactions, 247 items, 5 warehouses |
| Days Inventory Monitoring | `1nH9LtfGbQcX6l8CVMnnaOxyyShDj4bJD0EzahGJ2nk0` | 16 critical frozen/chilled items, days-of-stock tracking |
| Procurement audit | `tmp/procurement-sprint-audit.md` | Code-level feature audit |
| Process alignment | `tmp/procurement-process-alignment.md` | Actual process vs system gaps |
