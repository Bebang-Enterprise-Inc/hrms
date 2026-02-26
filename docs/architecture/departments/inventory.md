---
**Last Scanned:** 2026-02-23 | **Previous Scan:** 2026-02-17
**Commit:** 7b998877f | **Health Score:** 89% LIVE
---

# Department Feature Matrix: Store Inventory

## Summary

- Frontend pages: 10 (`/dashboard/inventory` hub + 6 sub-pages + `/inventory/stock-counts` standalone 3-page)
- Backend endpoints: 19 (1 deprecated v1, 17 LIVE)
- DocTypes: 7 (bei_cycle_count, bei_cycle_count_item, bei_inventory_variance, bei_inventory_spot_check_item, bei_shelf_life_extension, bei_external_auditor_store_access, bei_store_audit_item)
- Health Score: 89% LIVE

## Feature Matrix

| Feature | Frontend Page | FE Status | Backend API | BE Status | Notes |
|---------|--------------|-----------|-------------|-----------|-------|
| Inventory Hub | `/dashboard/inventory` | LIVE | — (static nav) | — | Hub stats are hardcoded strings (GAP-082) |
| Store Ordering (Inventory path) | `/dashboard/inventory/ordering` | LIVE | `inventory.submit_order` | LIVE | Simpler UI than store-ops path |
| Cycle Count Submit (v1) | `/dashboard/inventory/counts` | LIVE (calls v1) | `inventory.submit_cycle_count` | **DEPRECATED** | **CRITICAL GAP-004: throws deprecation error immediately** |
| Cycle Count Submit (v2) | `/inventory/stock-counts/new` | LIVE | `inventory.submit_cycle_count_v2` | LIVE | Whole + Loose qty, photo upload, blind count |
| Cycle Count Draft Save | `/inventory/stock-counts/new` | LIVE | `inventory.save_cycle_count_draft` | LIVE | |
| Cycle Count List | `/inventory/stock-counts` | LIVE | `inventory.get_cycle_counts` | LIVE | External Auditor sees own counts only |
| Cycle Count Detail | `/inventory/stock-counts/[id]` | LIVE | `inventory.get_cycle_count` | LIVE | |
| Cycle Count Approve/Reject | `/inventory/stock-counts/[id]` | LIVE | `inventory.approve_cycle_count` | LIVE | Self-approval prevention enforced |
| Cycle Count Resubmit | `/dashboard/inventory/counts` | LIVE | `inventory.resubmit_cycle_count` | LIVE | Ownership check enforced |
| Cycle Count Reconcile | — | NOT BUILT | `inventory.mark_cycle_count_reconciled` | LIVE | **GAP-059: no FE for Finance** |
| COS RECON Export | — | NOT BUILT | `inventory.export_count_to_cos_recon` | LIVE | **GAP-058: Finance cannot download xlsx** |
| Inventory Variance Report | `/dashboard/inventory/variances` | LIVE | `inventory.report_variance` | LIVE | |
| Variance Management | `/dashboard/inventory/variance-management` | LIVE | `inventory.get_variances` | LIVE | Resolution dialog in UI |
| Variance Resolution | `/dashboard/inventory/variance-management` | LIVE | `inventory.resolve_variance` (inferred) | VERIFY | **GAP-060: endpoint name unconfirmed** |
| Shelf Life Extension | `/dashboard/inventory/shelf-life` | LIVE | `inventory.request_shelf_extension` | LIVE | |
| Shelf Life Approve | — | NOT BUILT | `inventory.approve_shelf_extension` | LIVE | **GAP-057: no supervisor frontend** |
| Store Returns | `/dashboard/inventory/returns` | LIVE | `inventory.submit_return_request` | LIVE | Creates Material Issue (no destination warehouse) |
| Warehouse Stock View | `/dashboard/inventory` (warehouse) | PAGE EXISTS | `inventory.get_warehouse_stock` | LIVE | SCM Inventory roles |
| Daily SOH Update | (warehouse module) | PAGE EXISTS | `inventory.daily_stock_update` | LIVE | Creates and submits Stock Reconciliation |

## DocType Relationships

| DocType | Link Fields | Child Tables | Submittable? |
|---------|-------------|-------------|--------------|
| bei_cycle_count | store→Warehouse, counted_by→User, approved_by→User, stock_reconciliation→Stock Reconciliation | bei_cycle_count_item | **Yes** |
| bei_cycle_count_item | item_code→Item | — | — |
| bei_inventory_variance | store→Warehouse, cycle_count→BEI Cycle Count, item_code→Item | — | No |
| bei_shelf_life_extension | store→Warehouse, item_code→Item, requested_by→User, approved_by→User | — | No |
| bei_external_auditor_store_access | user→User, warehouse→Warehouse | — | No |

## Gaps Found

| ID | Feature | Blocker Type | Severity | Notes |
|----|---------|-------------|----------|-------|
| GAP-004 | Cycle count dashboard calls deprecated v1 endpoint | Bug | Critical | `/dashboard/inventory/counts` completely broken for submission |
| GAP-057 | Shelf life extension approval: no frontend | Frontend | Medium | Supervisors must use Frappe Desk |
| GAP-058 | COS RECON export: no frontend | Frontend | Medium | Finance cannot download xlsx from app |
| GAP-059 | Cycle count reconciliation: no frontend | Frontend | Medium | Finance cannot close cycle count workflow |
| GAP-060 | Variance resolution endpoint unconfirmed | Verify | High | FE has modal but API wiring unclear |
| GAP-082 | Inventory hub stats hardcoded | Bug | Medium | Users see stale/fake stats |
| GAP-094 | Returns: Material Issue vs Material Transfer inconsistency | Logic | Medium | GL treatment differs between return paths |

## Improvements

| Feature | Current State | Suggested Improvement | Priority |
|---------|--------------|----------------------|----------|
| Blind count item loading | Loads ALL stock items per call | Add pagination/batch loading by item_group | HIGH |
| Returns recipient warehouse | Material Issue with no destination | Use commissary warehouse as destination | HIGH |
| Variance management | FE dialog exists, resolve endpoint unconfirmed | Verify/create `inventory.resolve_variance()` endpoint | HIGH |
| Cycle count duplicate detection | No index | Add index on (store, count_date, count_type, docstatus) | MEDIUM |
