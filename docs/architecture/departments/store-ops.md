---
**Last Scanned:** 2026-02-23 | **Previous Scan:** 2026-02-17
**Commit:** 7b998877f | **Health Score:** 87% LIVE
---

# Department Feature Matrix: Store Operations

## Summary

- Frontend pages: 13 (store-ops: 10, receiving: 3)
- Backend endpoints: 30 LIVE across store.py + dispatch.py + ordering.py
- DocTypes: 16 (bei_store_order, bei_store_order_item, bei_store_opening_report, bei_opening_checklist_item, bei_store_closing_report, bei_closing_checklist_item, bei_mid_shift_handover, bei_midshift_checklist, bei_pos_upload, bei_bank_deposit, bei_bank_deposit_entry, bei_bank_deposit_photo, bei_store_receiving, bei_store_receiving_item, bei_temperature_reading, bei_store_type)
- Health Score: 87% LIVE (3 deprecated ordering.py proxies excluded)

## Feature Matrix

| Feature | Frontend Page | FE Status | Backend API | BE Status | Notes |
|---------|--------------|-----------|-------------|-----------|-------|
| Opening Report | `/dashboard/store-ops/opening` | LIVE | `store.submit_opening_report` | LIVE | 22-item checklist + 5 required watermarked photos |
| Closing Report (3-stage) | `/dashboard/store-ops/closing` | LIVE | `store.get_or_create_closing_report`, `submit_closing_stage1_cash`, `submit_closing_stage2_checklist`, `submit_closing_stage3_photos` | LIVE | Cash Count → Checklist/Inventory → Photos/Z-reading |
| Mid-Shift Check | `/dashboard/store-ops/midshift` | LIVE | `store.submit_midshift_check` | LIVE | 3–4 PM gate frontend-only; backend has no time gate |
| Cashier Handover | `/dashboard/store-ops/handover` | LIVE | `store.submit_mid_shift_handover`, `get_mid_shift_handovers` | LIVE | Signature capture + X-reading photo |
| Maintenance Request | `/dashboard/store-ops/maintenance` | LIVE | `store.submit_maintenance_request` | LIVE | Multi-photo, 8 categories. **No GChat to Projects on creation (GAP-032)** |
| POS Upload | `/dashboard/store-ops/pos` | LIVE | `store.upload_pos_data` | LIVE | **gross_sales/net_sales NOT populated (GAP-022)** |
| Bank Deposit | `/dashboard/store-ops/deposit` | LIVE | `store.submit_bank_deposit` | LIVE | Bank Deposit + Fund Transfer modes |
| Store Ordering | `/dashboard/store-ops/ordering` | LIVE | `ordering.submit_order` → `store.submit_order` | LIVE (deprecated proxy) | Cutoff 11:59 AM, emergency bypass, cargo category required |
| Order Catalog | `/dashboard/store-ops/ordering` | LIVE | `ordering.get_orderable_items` → `store.get_orderable_items` | LIVE (deprecated proxy) | Last order qty batched in 1 query |
| Order Approval | `/dashboard/store-ops/order-approvals` | LIVE | `ordering.approve_order`, `ordering.reject_order` | LIVE | GChat on approval; triggers Material Request |
| Store Receiving | `/dashboard/receiving` | LIVE | `store.get_expected_deliveries`, `store.complete_receiving` | LIVE | Item checklist: condition/packaging/expiry/temp/quality |
| FQI Report | `/dashboard/receiving/fqi` | LIVE | `store.create_fqi_report`, `store.get_fqi_reports` | LIVE | **severity field dropped by backend (GAP-063)** |
| Dispatch Tracker | `/dashboard/receiving/dispatch` | LIVE | `dispatch.get_trips`, `dispatch.confirm_delivery`, `dispatch.get_route_progress` | LIVE | 20 min/stop ETA |
| Trip Creation | — | NOT BUILT | `dispatch.create_trip`, `dispatch.confirm_departure` | LIVE | **GAP-061: no frontend page** |
| Store Returns (from receiving) | — | NOT BUILT | `store.create_store_return` | LIVE | **GAP-062: no FE entry point from receiving** |

## DocType Relationships

| DocType | Link Fields (→ target) | Child Tables | Submittable? |
|---------|----------------------|-------------|--------------|
| bei_store_order | store→Warehouse, submitted_by→User, approved_by→User, trip→BEI Distribution Trip | bei_store_order_item | No (status-driven) |
| bei_store_opening_report | store→Warehouse, submitted_by→User | bei_opening_checklist_item | No |
| bei_store_closing_report | store→Warehouse, submitted_by→User, pos_upload→BEI POS Upload | bei_closing_checklist_item, bei_inventory_spot_check_item | No |
| bei_mid_shift_handover | store→Warehouse, outgoing_cashier→User, incoming_cashier→User | bei_midshift_checklist | No |
| bei_pos_upload | store→Warehouse, uploaded_by→User | — | No |
| bei_bank_deposit | store→Warehouse, submitted_by→User | bei_bank_deposit_entry, bei_bank_deposit_photo | No |
| bei_store_receiving | store→Warehouse, trip→BEI Distribution Trip, receiver_1→User | bei_store_receiving_item | No |
| bei_fqi_report | store→Warehouse, receiving→BEI Store Receiving, item_code→Item | — | No |

## Gaps Found

| ID | Feature | Blocker Type | Severity | Notes |
|----|---------|-------------|----------|-------|
| GAP-003 | `preview_trip_stops` missing from dispatch.py | Bug | Critical | Trip Wizard Step 3 always broken |
| GAP-020 | Approval Queue not created if resolve_warehouse fails | Bug | High | Order sits in limbo |
| GAP-022 | POS Upload: gross_sales/net_sales never populated | Bug | High | Dashboard analytics inaccurate |
| GAP-032 | Maintenance Request: no GChat notification to Projects | Bug | High | Urgent requests unnoticed for hours |
| GAP-061 | Trip creation/departure: no frontend | Frontend | High | Frappe Desk required |
| GAP-062 | Store returns from receiving: no FE entry point | Frontend | Medium | Store staff cannot return damaged goods from receiving page |
| GAP-063 | FQI severity field mismatch — data silently dropped | Data Loss | Medium | All FQIs appear equal priority |
| GAP-081 | Opening/closing checklists hardcoded in page.tsx | Design | Low | Ops team cannot update without code deploy |
| GAP-093 | ordering.py deprecated proxies still in use | Tech Debt | Low | Log pollution |

## Improvements

| Feature | Current State | Suggested Improvement | Priority |
|---------|--------------|----------------------|----------|
| Opening/closing checklists | Hardcoded in page.tsx arrays | Load from DocType or BEI Settings child table | HIGH |
| ETA calculation | 20 min/stop hardcoded fallback | Populate from historical trip data | MEDIUM |
| ordering.py deprecated proxies | 3 deprecated wrappers still called by FE | Update use-ordering.ts to call store.py directly | MEDIUM |
| FQI item_code enforcement | FE allows free-text item name | Enforce item_code selection from Item master | MEDIUM |
