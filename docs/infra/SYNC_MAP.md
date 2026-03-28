# BEI ERP Sync Path Map

**Last Updated:** 2026-03-28
**Total active sync paths:** 13

---

## Sync Dependency Order

```
COA → Banks → Suppliers → AP Opening → PRs → POs → GRs → Inventory → AR → Shadow Sync → Demand Snapshot
```

COA must be synced before anything that creates GL entries. Suppliers must exist before AP/PO records reference them.

---

## Active Sync Paths

### 1. Store Inventory Shadow Sync (46 stores)

| Field | Value |
|-------|-------|
| **Source** | Per-store Google Sheets (tab: `3. INVENTORY`) |
| **Trigger** | Daily 7 AM PHT cron → `enqueue_scheduled_store_inventory_shadow_sync()` |
| **Code** | `erp_sync.py` → `store_inventory_shadow_sync.py` → `_sync_inventory_rows()` |
| **Destination** | Stock Reconciliation → Bin (tabBin), SLE, GL |
| **Registry** | `hrms/utils/store_inventory_shadow_sync_registry.csv` |
| **Watchdog** | Every 10 min: `watch_store_inventory_shadow_sync_health()` |
| **Duration** | ~15 min sequential (target: <5 min with parallel batches) |
| **If it breaks** | Stores show 0 stock in ordering page. Re-run with `force=True`. |

### 2. Warehouse Inventory Sync (Ian's sheet)

| Field | Value |
|-------|-------|
| **Source** | Google Sheet `SUMMARY 2026` (Ian's warehouse inventory) |
| **Trigger** | Sheets-receiver webhook (on Google Drive change notification) |
| **Code** | sheets-receiver → `erp_sync.sync_inventory()` → `_sync_inventory_rows()` |
| **Destination** | Stock Reconciliation → Bin, SLE, GL |
| **If it breaks** | Warehouse stock stale. Check sheets-receiver logs. |

### 3. Procurement Suppliers

| Field | Value |
|-------|-------|
| **Source** | Google Sheet `Procurement DB` → tab `Suppliers` |
| **Trigger** | Sheets-receiver webhook + daily 7 AM baseline |
| **Code** | sheets-receiver → `erp_sync.sync_procurement_suppliers()` |
| **Destination** | BEI Supplier DocType |
| **If it breaks** | New suppliers not available for PO creation. |

### 4. Purchase Requisitions

| Field | Value |
|-------|-------|
| **Source** | Google Sheet `Procurement DB` → tab `Purchase Requisitions` |
| **Trigger** | Sheets-receiver webhook + daily baseline |
| **Code** | sheets-receiver → `erp_sync.sync_procurement_requisitions()` |
| **Destination** | BEI Purchase Requisition DocType |

### 5. Purchase Orders

| Field | Value |
|-------|-------|
| **Source** | Google Sheet `Procurement DB` → tab `Purchase Order` |
| **Trigger** | Sheets-receiver webhook + daily baseline |
| **Code** | sheets-receiver → `erp_sync.sync_procurement_purchase_orders()` |
| **Destination** | BEI Purchase Order DocType |

### 6. Goods Receipts

| Field | Value |
|-------|-------|
| **Source** | Google Sheet `Procurement DB` → tab `Goods Receipts` |
| **Trigger** | Sheets-receiver webhook + daily baseline |
| **Code** | sheets-receiver → `erp_sync.sync_procurement_goods_receipts()` |
| **Destination** | BEI Goods Receipt DocType |

### 7. AP Opening Balance (Supplier SOA)

| Field | Value |
|-------|-------|
| **Source** | Google Sheet `AP Opening Balance` → tab `SUPPLIERS SOA` |
| **Trigger** | Sheets-receiver webhook + daily baseline |
| **Code** | sheets-receiver → `erp_sync.sync_ap_opening()` |
| **Destination** | Purchase Invoice (Opening Entry) |
| **If it breaks** | Supplier balances wrong. Check for duplicate invoices. |

### 8. Chart of Accounts

| Field | Value |
|-------|-------|
| **Source** | Google Sheet `Chart of Accounts` → tab `01 - Chart of Accounts (217)` |
| **Trigger** | Sheets-receiver webhook + daily baseline |
| **Code** | sheets-receiver → `erp_sync.sync_coa()` |
| **Destination** | Account DocType |
| **If it breaks** | Missing GL accounts. Must sync before any financial transaction. |

### 9. Bank Directory

| Field | Value |
|-------|-------|
| **Source** | Google Sheet `Bank Directory` → tab `02 - Bank Directory (53)` |
| **Trigger** | Sheets-receiver webhook + daily baseline |
| **Code** | sheets-receiver → `erp_sync.sync_bank_accounts()` |
| **Destination** | Bank Account DocType |

### 10. AR Aging

| Field | Value |
|-------|-------|
| **Source** | Google Sheet `AR Aging` → tab `AR` |
| **Trigger** | Sheets-receiver webhook |
| **Code** | sheets-receiver → `erp_sync.sync_ar_aging()` |
| **Destination** | Sales Invoice records |

### 11. Store Demand Snapshot

| Field | Value |
|-------|-------|
| **Source** | Computed from Supabase POS sales + Frappe BOM data |
| **Trigger** | Daily 7 AM PHT cron → `enqueue_scheduled_store_demand_snapshot_sync()` |
| **Code** | `erp_sync.py` → `store_order_demand_snapshot.py` |
| **Destination** | Demand snapshot records (powers store ordering suggestions) |
| **If it breaks** | Store ordering shows no suggested quantities. Separate from inventory sync. |

### 12. POS Daily Files (XLSX)

| Field | Value |
|-------|-------|
| **Source** | Store POS XLSX exports uploaded to Google Drive |
| **Trigger** | Sheets-receiver scans every 30 min, processes every 2 min |
| **Code** | sheets-receiver POS processor → Supabase |
| **Destination** | Supabase `pos_sales` / `pos_daily_summary` (NOT Frappe) |
| **If it breaks** | Sales dashboard shows gaps. Check sheets-receiver POS queue. |

### 13. Mosaic POS API

| Field | Value |
|-------|-------|
| **Source** | Mosaic POS REST API (45 stores) |
| **Trigger** | GHA cron 12:30 AM PHT daily |
| **Code** | `scripts/mosaic_daily_sync.py` (GitHub Actions) |
| **Destination** | Supabase `mosaic_transactions` |
| **If it breaks** | Re-run the GHA workflow manually. |

---

## Non-Sync Scheduled Jobs (by category)

### Biometrics / Attendance
- ADMS checkin sync (GHA every 5 min)
- Auto-attendance (hourly_long)
- Auto-punch-out (hourly)
- Biometric status refresh (4×/day)
- Biometric daily digest (7 AM PHT)
- Missing punch report (midnight PHT)

### HR / Leave
- Leave allocation expiry (daily_long)
- Earned leave allocation (daily_long)
- Leave encashment (daily_long)
- Birthday/anniversary reminders (daily)

### Procurement
- Overdue PO check (daily)
- Overdue invoice check (daily)
- Pending approval escalation (daily)
- Supplier document expiry (daily)

### Finance
- Monthly billing (1st of month)
- PCF auto-submit (hourly + month-end)

### Monitoring
- Weather collection (5×/day)
- Morning sync health report (8:15 AM)
- Discount audit (3 jobs at midnight)
- Low stock alert (daily)
- Inventory risk snapshots (daily)

---

## What Breaks If a Sync Fails

| Sync | Impact | Recovery |
|------|--------|----------|
| Store Inventory | Ordering page shows 0 stock | Re-run with `force=True` |
| Warehouse Inventory | Warehouse stock stale | Trigger sheets-receiver re-sync |
| COA | All financial transactions fail | Must fix before any GL entry |
| Suppliers | Cannot create new POs | Re-sync from sheets-receiver |
| AP Opening | Supplier balances wrong | Re-sync, check for duplicates |
| POS Files | Sales dashboard gaps | Check sheets-receiver queue |
| Demand Snapshot | No ordering suggestions | Re-run demand sync |
