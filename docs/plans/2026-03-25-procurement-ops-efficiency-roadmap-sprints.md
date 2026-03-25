# Procurement Operations Efficiency — Sprint Roadmap

**Purpose:** Master plan splitting 13 procurement improvements into executable sprints. This is the routing document — individual sprint plans are written separately.

**Context:**
- **Team:** Cayla (solo PO processor, 70 POs/month), Luwi (sourcing/planning), Ian (warehouse/PRs/deliveries), Mae (CPO approver)
- **Data:** 80% of POs are exact duplicates (same supplier + same items). 561 POs over 7 months. P213M total spend.
- **Source:** AppSheet Procurement Compliance Database (`1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q`)

---

## Feature Audit Summary

| # | Feature | Classification | Exists Where | Sprint |
|---|---------|---------------|-------------|--------|
| 1 | PO Templates / Reorder | **[BUILD]** | — | S122 |
| 2 | PO Review Step (Luwi) | **[EXTEND]** | Payment Request only, not POs | S123 |
| 3 | Batch Approval (Mae) | **[BUILD]** | — | S122 |
| 4 | Quick Receive | **[EXTEND]** | `load_gr_from_po()` exists | S123 |
| 5 | Auto-Invoice from GR | **[BUILD]** | — | S123 |
| 6 | RFP Approval Flow | **[EXISTS]** | 4-level chain in bei_payment_request | SKIP |
| 7 | Inventory→PR Bridge | **[EXTEND]** | `convert_pr_to_po()` exists | S124 |
| 8 | Supplier Price Alerts | **[EXISTS]** | `check_price_variance()` @ line 3391 | SKIP (enhance in S124) |
| 9 | PO-to-GR Matching | **[EXISTS]** | `get_pending_gr_for_po()` @ line 1666 | SKIP (surface in S124 dashboard) |
| 10 | Auto PR-to-PO | **[EXISTS]** | `convert_pr_to_po()` manual | S124 (make auto) |
| 11 | Spend Analytics | **[EXISTS]** | `get_monthly_spend_report()` full | SKIP |
| 12 | Supplier Doc Expiry | **[BUILD]** | No expiry fields | S124 |
| 13 | GR Variance Report | **[EXISTS]** | 3-way match report | SKIP |

**6 features SKIP** (already exist). **7 features need work** across 3 sprints.

---

## Sprint S122 — Cayla + Mae Speed (PO Templates + Batch Approve)

**Goal:** Eliminate 80% of Cayla's repetitive PO creation and unblock Mae's approval bottleneck.

**Impact:**
- Cayla: 56 duplicate POs/month → one-click reorders (~4 hours/month saved)
- Mae: 70 POs/month approved one-at-a-time → batch approve in minutes

### Scope (~28 units)

**Phase A: PO Templates / Reorder (12 units)**

| Task | Type | Description | Units |
|------|------|-------------|-------|
| A1 | BUILD | Backend: New DocType `BEI PO Template` — fields: template_name, supplier, items (child table), last_used_date, use_count. API: `save_po_as_template()`, `get_templates()`, `create_po_from_template()`. | 4 |
| A2 | BUILD | Backend: `create_po_from_template(template_name, qty_overrides)` — creates a draft PO pre-filled from template. Cayla adjusts qty, clicks Create. | 2 |
| A3 | BUILD | Frontend: "Reorder Center" tab on PO list page — shows saved templates sorted by last_used. Each row: template name, supplier, item count, last used date, [Reorder Now] button. | 4 |
| A4 | BUILD | Frontend: "Save as Template" button on PO detail page (for existing POs). Dialog: enter template name → saves. | 2 |

**Phase B: Batch Approval for Mae (10 units)**

| Task | Type | Description | Units |
|------|------|-------------|-------|
| B1 | BUILD | Frontend: Add checkboxes to PO list rows. Floating action bar when 1+ selected: `[Approve Selected (N)] [Reject Selected]`. | 4 |
| B2 | BUILD | Frontend: Batch approval summary modal — table showing selected POs with: PO#, Supplier, Items (count), Total Amount, Delivery Date. Mae reviews the table, clicks "Approve All N". | 3 |
| B3 | BUILD | Backend: `batch_approve_pos(names, level, comment)` — loops through POs, approves each, returns success/failure per PO. Sentry instrumented. | 2 |
| B4 | VERIFY | L3: Save a PO as template → reorder from template → batch approve 3 POs. | 1 |

**Phase C: Deploy + L3 + Closeout (6 units)**

| Task | Type | Description | Units |
|------|------|-------------|-------|
| C1 | BUILD | Create PRs, merge, deploy both repos. | 2 |
| C2 | VERIFY | L3: Full reorder flow + batch approval test. | 3 |
| C3 | BUILD | Closeout. | 1 |

---

## Sprint S123 — Ian + Cayla Bridge (Quick Receive + Auto-Invoice)

**Goal:** Speed up the delivery → invoice chain. Ian records GR in one click, invoice auto-drafts.

**Depends on:** S122 (not blocking, can run in parallel)

**Impact:**
- Ian: GR creation from 5 min → 30 seconds for matching deliveries
- Cayla: Invoice creation eliminated for deliveries where GR matches PO

### Scope (~25 units)

**Phase A: PO Review Step for Luwi (8 units)**

| Task | Type | Description | Units |
|------|------|-------------|-------|
| A1 | EXTEND | Backend: Add `review_status`, `reviewed_by`, `review_date`, `review_comment` fields to BEI Purchase Order DocType (mirror the pattern from BEI Payment Request). | 2 |
| A2 | EXTEND | Backend: `review_po(name, comment)` and `batch_review_pos(names, comment)` endpoints. Sentry instrumented. PO flow becomes: Draft → Pending Review (Luwi) → Pending Mae Approval → Approved. | 2 |
| A3 | BUILD | Frontend: "Pending Review" tab on PO list. Luwi sees POs she needs to review. Batch review with checkboxes (same pattern as Mae's batch approve). | 3 |
| A4 | VERIFY | Update PO detail page to show Luwi's review status alongside Mae/Butch approval status. | 1 |

**Phase B: Quick Receive (6 units)**

| Task | Type | Description | Units |
|------|------|-------------|-------|
| B1 | EXTEND | Frontend: On GR new page, after selecting PO + items load, add prominent button: "Received All as Ordered". Clicking it auto-fills all received_qty = ordered_qty and submits. | 3 |
| B2 | EXTEND | Backend: `quick_receive_gr(purchase_order)` — creates GR with all items matching PO qty. Returns GR name. Sentry instrumented. | 2 |
| B3 | VERIFY | L3: Select PO → click "Received All as Ordered" → GR created with correct quantities. | 1 |

**Phase C: Auto-Invoice from GR (5 units)**

| Task | Type | Description | Units |
|------|------|-------------|-------|
| C1 | BUILD | Frontend: After GR creation success, show prompt: "Create invoice? Invoice #: [___] Date: [___] Attach: [Upload]". Clicking "Create" calls create_invoice with PO+GR data pre-filled. | 3 |
| C2 | BUILD | Backend: Ensure `create_invoice` accepts `goods_receipt` parameter to pre-fill items/amounts from GR (partially exists — verify and extend). | 1 |
| C3 | VERIFY | L3: Create GR → invoice prompt appears → fill invoice # → invoice created with correct amounts. | 1 |

**Phase D: Deploy + L3 + Closeout (6 units)**

---

## Sprint S124 — Luwi Strategic Tools (Inventory Bridge + Supplier Intelligence)

**Goal:** Connect inventory data to procurement decisions. Luwi sees what's running low and the system suggests reorders.

**Depends on:** S122 (templates exist so auto-reorder can use them), S123 (review step exists so Luwi's workflow is formalized), S121 (store inventory sync fixed so tabBin data is reliable)

### Scope (~30 units)

**Phase A: Inventory → PR Bridge (12 units)**

| Task | Type | Description | Units |
|------|------|-------------|-------|
| A1 | BUILD | Backend: `get_low_stock_items(threshold_days=7)` — queries warehouse inventory (from Ian's data or Frappe stock), calculates days-of-stock-remaining based on consumption rate, returns items below threshold. | 4 |
| A2 | BUILD | Backend: `create_pr_from_stock_alert(items)` — auto-creates PR for low-stock items with suggested qty (based on historical consumption × lead time). | 3 |
| A3 | BUILD | Frontend: "Stock Alerts" widget on procurement dashboard — shows items below reorder threshold with color coding (red <3 days, yellow <7 days). Each row: item, current stock, daily consumption, days remaining, [Create PR] button. | 4 |
| A4 | VERIFY | L3: Dashboard shows low-stock items → click Create PR → PR created with correct items and suggested quantities. | 1 |

**Phase B: Auto PR-to-PO + Supplier Enhancements (10 units)**

| Task | Type | Description | Units |
|------|------|-------------|-------|
| B1 | EXTEND | Backend: `auto_convert_pr_to_po(pr_name)` — if PR has single-source supplier with contracted price, auto-create PO draft (uses existing `convert_pr_to_po` + contracted price lookup from S104). | 3 |
| B2 | BUILD | Backend: Add `expiry_date` fields to BEI Supplier for BIR 2307, SEC, Business Permit. Cron job: `check_supplier_document_expiry()` — alerts 30 days before expiry via Google Chat. | 4 |
| B3 | BUILD | Frontend: Supplier detail page — show document expiry status (green/yellow/red badges). Supplier list — show "N documents expiring" filter. | 2 |
| B4 | VERIFY | L3: PR with single-source supplier → auto PO draft created. Supplier with expiring doc → alert sent. | 1 |

**Phase C: Today's Deliveries Widget (3 units)**

| Task | Type | Description | Units |
|------|------|-------------|-------|
| C1 | BUILD | Frontend: Dashboard widget — "Deliveries Expected This Week" from POs where delivery_date is this week and status is Approved/Sent. Shows: supplier, PO#, items, date. Color: green=on-time, red=overdue. | 2 |
| C2 | VERIFY | L3: Dashboard shows expected deliveries matching PO delivery dates. | 1 |

**Phase D: Deploy + L3 + Closeout (5 units)**

---

## Sprint Dependency Map

```
S121 (Inventory Sync Fix — ALREADY PLANNED)
        ↓ (tabBin data must be reliable first)
S122 (Cayla+Mae Speed)          S123 (Ian+Cayla Bridge)
  PO Templates                    PO Review Step (Luwi)
  Batch Approve                   Quick Receive
                                  Auto-Invoice from GR
        ↓                               ↓
              S124 (Luwi Strategic)
                Inventory→PR Bridge
                Auto PR-to-PO
                Supplier Doc Expiry
                Deliveries Widget
```

S121 must complete first (fixes inventory data that S124 depends on).
S122 and S123 can run in **parallel** (different files, different surfaces).
S124 depends on all three.

---

## Features That Already Exist (No Sprint Needed)

| # | Feature | Why Skip |
|---|---------|----------|
| 6 | RFP Approval Flow | Already 4-level chain in BEI Payment Request DocType |
| 8 | Supplier Price Alerts | `check_price_variance()` with 5%/10% thresholds exists |
| 9 | PO-to-GR Matching | `get_pending_gr_for_po()` exists, surfaced in reports |
| 11 | Spend Analytics | `get_monthly_spend_report()` full dashboard exists |
| 13 | GR Variance Report | 3-way match report with variance calculations exists |

These features exist in the backend. If they're not visible enough in the UI, that's a UX task — not a feature build.

---

## Total Effort

| Sprint | Units | Duration | Parallel? |
|--------|-------|----------|-----------|
| S121 (inventory sync fix) | 18 | ~0.5 day | First (prerequisite) |
| S122 (PO templates + batch approve) | 28 | ~1 day | Yes (with S123) |
| S123 (quick receive + auto-invoice) | 25 | ~1 day | Yes (with S122) |
| S124 (inventory→PR bridge) | 30 | ~1 day | After S121+S122+S123 |
| **Total** | **101** | **~3-4 days** | |

---

## Data Sources

| Source | ID | What It Contains |
|--------|------|-----------------|
| Procurement AppSheet | `1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q` | 561 POs, 489 PRs, 958 GRs, 91 suppliers, approval matrix |
| Ian's WHSE Inventory | `1piMVW6nH7l_8lsXFqJ-LBZUbbXhyXgzvJPpLjo3LUNA` | 11,510 March transactions, 247 items, 5 warehouses |
| Days Inventory Monitoring | `1nH9LtfGbQcX6l8CVMnnaOxyyShDj4bJD0EzahGJ2nk0` | 16 critical frozen/chilled items, days-of-stock tracking |
| Extracted data | `tmp/procurement_appsheet_data.md` | Full analysis |
| Best practices research | `tmp/procurement_best_practices.md` | Industry benchmarks |
