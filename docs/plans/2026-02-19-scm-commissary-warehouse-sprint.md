# SCM Sprint Plan: Commissary + Warehouse
**Date:** 2026-02-19
**Status:** COMPLETE (except G-046 blocker) — All 4 phases done + deployed
**Version:** v1.6 (Phase 4 deployed 2026-02-19)
**Priority:** Dept 1 (highest priority in Master Gap Closure Roadmap)
**Parent:** `docs/plans/2026-02-19-master-gap-closure-roadmap.md`

---

## OPEN BLOCKERS (resolve before plan is complete)

| # | Gap | Blocker | Status | Owner |
|---|-----|---------|--------|-------|
| 1 | G-046 | **BKI inter-company tax treatment** — Finance must confirm: (1) VAT invoices on hub transfers? (2) Transfer pricing method? (3) SI/PI or JE? (4) EWT ATC code? (5) BKI as separate Frappe company? | WAITING ON FINANCE | Sam → Finance team |

**G-046 cannot be implemented until Finance responds.** All other Phase 1 gaps are complete.

---

## Execution Progress

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 0 (P0-1 to P0-12) | COMPLETE | 12 pre-sprint fixes, commissary.py split, RBAC centralization, N+1 fix |
| Phase 1 Backend | COMPLETE (except G-046) | G-001, G-002, G-003, G-047, G-051, G-067, G-069, G-070, G-100, G-101, G-102 all done |
| Phase 2 Frontend | COMPLETE | trips/page.tsx (881L), my-delivery/page.tsx (575L), dispatch API proxy routes, hooks added. Existing pages already built. |
| Phase 3 Frontend | COMPLETE | Commissary pages already existed. Added `approveRequisition` + `checkFeasibility` hooks + API proxy actions. |
| Code Review | COMPLETE | 3 parallel reviewers (backend, frontend, API contracts). 18 fixes applied (7 P0, 8 P1, 3 P2). |
| Phase 4 SHOULD-HAVE | COMPLETE | G-050 wastage trends, G-012 route CRUD, G-122 3PL billing + EWT |

### Deployment Log

| Date | Repo | Commit | What |
|------|------|--------|------|
| 2026-02-19 | BEI-ERP | `0bcd260` | Phase 0-3 backend: commissary split, RBAC, credit notes, 9 review fixes |
| 2026-02-19 | bei-tasks | `6461ed7` | Phase 2-3 frontend: trips, my-delivery pages, API proxies, 9 review fixes |
| 2026-02-19 | BEI-ERP | `5329529` | Phase 4 backend: wastage trends endpoint, 3PL EWT fields + DM-1 compliant JEs |
| 2026-02-19 | bei-tasks | `42e159f` | Phase 4 frontend: wastage trends page, route CRUD, 3PL billing reconciliation UI |

### Code Review Findings (Resolved)

3 parallel review agents audited all changes. Full reports at:
- `scratchpad/code-review/backend_review.md` — 22 findings (3 P0, 4 P1, 6 P2, 3 P3)
- `scratchpad/code-review/frontend_review.md` — 41 findings (7 CRITICAL, 18 WARNING, 16 INFO)
- `scratchpad/code-review/api_contract_review.md` — 33 MATCH, 4 MISMATCH (fixed), 3 param gaps

Key P0 fixes applied:
1. Double FG row in BOM production path (commissary_dashboard.py)
2. Pro-rata ratio: value-based instead of qty/PHP (store.py)
3. RBAC on process_store_return, approve/reject_material_request
4. Trip response shape unwrapping (.trips/.trip keys)
5. 2MB photo size guard on exception reports
6. Blank signature rejection (length < 3000)
7. Trip detail response shape fix

---

## Executive Summary

Commissary + Warehouse is the **most critical department** to fix. Commissary produces all food (P14.1M/month COGS). Warehouse dispatches to 45 stores. Both have critically low frontend coverage:
- **Warehouse:** 12% live (36 APIs, ZERO frontend pages)
- **Commissary:** 45% live (10 frontend pages exist, 4 API stubs)

This plan covers **6 MUST-HAVE gaps** that block daily operations, followed by **11 SHOULD-HAVE gaps** for the same sprint.

**Total scope:** 4 phases (backend done, frontend next, then enhancements)

---

## Business Context

| Fact | Value |
|------|-------|
| Monthly COGS | P14.1M |
| Commissary entity | Bebang Kitchen Inc. (Shaw Blvd, Mandaluyong) |
| Commissary headcount | 31.5 |
| Commissary net income | P12K/month (barely breaks even) |
| Monthly logistics cost | P4.5M (3PL: 3MD, Orca, Suzuyo, Four Coolitz, WGD) |
| Cold storage cost | P814K/month (RCS Taytay) |
| Foul trip fee | P5,875–12,575 per failed delivery |
| Stores served | 45 (Metro Manila + provinces) |
| Store types | JV, Managed Franchise, Full Franchise |
| Franchise billing markup | Royalty 7%, Management 2.5%, Marketing 5%, Ecommerce 4% |

**Key people:**
- **Aldrin** — Warehouse/Dispatch Supervisor
- **Jay** — Logistics Coordinator (has ETT spreadsheet for all stores)
- **Jeson Porras** — SCM Manager (started Feb 16)
- **Commissary Supervisor** — daily production/QC operations

---

## Technology Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Backend | Frappe Framework (Python) | All APIs in `hrms/api/` |
| Employee App (my.bebang.ph) | React + Next.js 16 + Shadcn UI + Tailwind v4 | Separate repo: `bei-tasks` |
| Legacy PWA | Ionic 7 + Vue 3 | `frontend/` directory — has some dispatch pages |
| Database | MariaDB (Docker container) | NOT AWS RDS |
| Notifications | Google Chat via service account | `hrms/api/google_chat.py` |
| Deployment | Docker → AWS EC2 via GitHub Actions | `.github/workflows/build-and-deploy.yml` |

---

## Source Files Map

Every file an implementing agent needs to know about:

### Backend API Files

| File | Lines | Role | Key Functions |
|------|-------|------|---------------|
| `hrms/api/commissary.py` | ~3600 | Commissary Supervisor APIs | `get_commissary_dashboard`, `submit_production_output`, `get_fqi_summary` (STUB), `get_returns_pending`, `create_rm_requisition`, `get_my_requisitions`, `create_bom`, `update_bom`, `get_bom_detail`, `check_production_feasibility`, BOM/WO/wastage/QC/hub |
| `hrms/api/warehouse.py` | ~606 | Warehouse Supervisor APIs | `get_pending_purchase_orders`, `create_purchase_receipt`, `approve_material_request`, `create_stock_transfer`, `get_warehouse_dashboard` |
| `hrms/api/dispatch.py` | ~1200 | Trip Tracking, Routes, Drivers, Notifications | `get_trips`, `confirm_departure`, `confirm_delivery`, `_send_delivery_notification` (MOCK→needs fix), `create_trip_from_route`, routes CRUD, driver assignment |
| `hrms/api/store.py` | ~2100 | Store Ops (FQI, Returns, Receiving) | `create_fqi_report` (LIVE), `get_fqi_reports` (LIVE), `get_returns_pending` (LIVE — queries `has_issue=1`), `create_store_return`, `process_store_return` |
| `hrms/api/billing.py` | ~1000 | Billing, 3PL, Delivery Rates | `generate_monthly_billing`, `get_3pl_rates`, `generate_3pl_reconciliation` |
| `hrms/api/ordering.py` | ~520 | Store Ordering workflow | `get_orderable_items`, `submit_order`, `approve_order`, `reject_order` |
| `hrms/api/picking.py` | ~280 | Warehouse Pick List | `generate_pick_list`, `complete_picking`, `confirm_loaded` |
| `hrms/api/inventory.py` | ~1300 | Cycle Count, Variance, Shelf Life | `submit_cycle_count`, `approve_cycle_count`, `report_variance`, `resolve_variance` |
| `hrms/api/google_chat.py` | — | Google Chat notifications | `send_message_to_space(space_name, message) -> bool` — never throws |
| `hrms/utils/bei_config.py` | — | Central config | `get_company()`, `get_chat_space()`, `SPACE_NOTIFICATIONS` |

### DocTypes (Custom BEI)

| DocType | Directory | Purpose |
|---------|-----------|---------|
| `BEI Distribution Trip` | `hrms/hr/doctype/bei_distribution_trip/` | Trip tracking with stops |
| `BEI Trip Stop` | `hrms/hr/doctype/bei_trip_stop/` | Child table for trip stops |
| `BEI Route` | `hrms/hr/doctype/bei_route/` | Route master |
| `BEI Route Stop` | `hrms/hr/doctype/bei_route_stop/` | Child: has `estimated_minutes` field |
| `BEI Vehicle` | `hrms/hr/doctype/bei_vehicle/` | Vehicle master |
| `BEI Store Order` | `hrms/hr/doctype/bei_store_order/` | Store ordering with items |
| `BEI Store Order Item` | `hrms/hr/doctype/bei_store_order_item/` | Child table |
| `BEI Store Type` | `hrms/hr/doctype/bei_store_type/` | JV / Managed Franchise / Full Franchise |
| `BEI Goods Receipt` | `hrms/hr/doctype/bei_goods_receipt/` | GR DocType |
| `BEI Store Receiving` | `hrms/hr/doctype/bei_store_receiving/` | Store receiving with items |
| `BEI FQI Report` | `hrms/hr/doctype/bei_fqi_report/` | Food Quality Index — **EXISTS AND WORKS** |
| `BEI QC Form` | `hrms/hr/doctype/bei_qc_form/` | QC form master |
| `BEI Pick List` | `hrms/hr/doctype/bei_pick_list/` | Picking list with items |
| `BEI Billing Schedule` | `hrms/hr/doctype/bei_billing_schedule/` | Franchise billing |
| `BEI Delivery Rate` | `hrms/hr/doctype/bei_delivery_rate/` | Rate per store+cargo_type |
| `BEI 3PL Rate` | `hrms/hr/doctype/bei_3pl_rate/` | 3PL rates per partner |
| `BEI Warehouse Department Mapping` | `hrms/hr/doctype/bei_warehouse_department_mapping/` | Warehouse→Department→Store Type chain |
| `BEI Cycle Count` | `hrms/hr/doctype/bei_cycle_count/` | Cycle count |
| `BEI Inventory Variance` | `hrms/hr/doctype/bei_inventory_variance/` | Variance tracking |
| `BEI Production` | `hrms/hr/doctype/bei_production/` | Production DocType |
| `BEI External Hub` | `hrms/hr/doctype/bei_external_hub/` | Distribution hubs |
| `BEI Purchase Requisition` | `hrms/hr/doctype/bei_purchase_requisition/` | Purchase requisition |

### Existing Frontend (Legacy Vue/Ionic PWA)

Located in `frontend/src/views/dispatch/`:
- `Dashboard.vue`, `DeliveryStop.vue`, `DepartureForm.vue`, `TripDetail.vue`
- `FQIForm.vue`, `FQIList.vue` — FQI reporting exists in legacy PWA
- `OrderDetail.vue`, `OrderForm.vue`, `Ordering.vue`
- `Receiving.vue`, `ReceivingForm.vue`

**No dedicated warehouse/ or commissary/ frontend directories exist.**

### RBAC Roles (from code)

**AUDIT FIX (BLOCKER 7):** The backend role names below do NOT all exist in `bei-tasks/lib/roles.ts`. The frontend RBAC layer defines: `Store Staff`, `Store Supervisor`, `Area Supervisor`, `HR User`, `HR Manager`, `Warehouse User`, `Driver`, `Projects User`, `Procurement User`, `Procurement Manager`, `HQ User`, `System Manager`, `Administrator`, `Employee`.

**Missing roles that must be added to BOTH Frappe AND `lib/roles.ts` before frontend work:**
- `Warehouse Manager` → either add new, or map to existing `Warehouse User`
- `Logistics Coordinator` → either add new, or map to existing `Warehouse User`
- `Supply Chain Manager` → either add new, or map to existing `Procurement Manager`
- `Commissary Supervisor` → add new (no existing equivalent)
- `Accounts Manager` → map to existing `HQ User` or add new
- `Driver` role exists in `lib/roles.ts` but has NO pages assigned — must be added to trips page

**Backend role sets (current code):**
```python
# dispatch.py
SCM_ADMIN_ROLES = {"HR Manager", "Warehouse Manager", "System Manager"}
SCM_DISPATCH_ROLES = {"HR Manager", "Warehouse Manager", "Logistics Coordinator", "System Manager"}
SCM_STORE_ROLES = {"Store Staff", "Store Supervisor", "Area Supervisor", "Warehouse User", "System Manager"}

# billing.py
RATE_MANAGEMENT_ROLES = {"Accounts Manager", "Supply Chain Manager", "System Manager"}

# picking.py
SCM_PICKING_ROLES = {"Warehouse Manager", "Warehouse Staff", "Logistics Coordinator", "System Manager"}
```

**Phase 0 Task P0-RBAC: Align backend + frontend role names** (2 hours)
- Decision: map existing roles or create new ones (get sign-off from Jeson/Sam)
- Update `lib/roles.ts` with new constants: `SCM_DISPATCH_ROLES`, `SCM_ADMIN_ROLES`, `SCM_STORE_ROLES`
- Add sidebar navigation entries for `Driver` role (trips page access)
- Add `Commissary Supervisor` role to Frappe + `lib/roles.ts`
- Provision `test.driver@bebang.ph` test account with `Driver` role

---

## MUST-HAVE Gaps (6 items)

### Gap G-001: FQI Report Disabled (Daily Errors)

**Problem:** The `BEI FQI Report` DocType **exists and works** — `store.py:605` (`create_fqi_report`) and `store.py:657` (`get_fqi_reports`) are fully live. However, `commissary.py` has two stale stubs:
1. Lines 92-102: Dashboard FQI count hardcoded to `0` with a stale TODO comment saying "DocType not yet created" (it IS created)
2. Lines 644-650: `get_fqi_summary()` returns `{"success": True, "data": [], "message": "FQI tracking not yet configured"}`

Additionally, `bei_fqi_report.py:28-30` has a TODO stub:
```python
def notify_stakeholders(self):
    # TODO: Send notifications to QA, SCM, AS, RM
    pass
```

**Fix (3 tasks):**

**Task 1A: Uncomment FQI dashboard count** (30 min)
- File: `hrms/api/commissary.py`
- Lines 92-102: Remove the `fqi_issues = 0` stub. Replace with actual query.
- **AUDIT FIX:** Before writing the query, read `bei_fqi_report.json` to get the canonical `status` Select field options. The plan originally assumed `["Open", "In Progress"]` but the code uses `"Open"` on creation and `"Failed"` in commented-out code. Use the actual DocType values:
  ```python
  # Step 1: Read bei_fqi_report.json → get status options (e.g., Open, In Progress, Resolved, Closed)
  # Step 2: Use the "open/active" statuses in the filter:
  fqi_issues = frappe.db.count("BEI FQI Report", {
      "status": ["in", ACTIVE_FQI_STATUSES],  # from DocType definition
      "creation": [">=", add_days(today(), -7)]
  })
  ```

**Task 1B: Implement `get_fqi_summary()`** (1 hour)
- File: `hrms/api/commissary.py`
- Lines 644-650: Replace stub with real query aggregating FQI reports by `issue_type`, `status`, and `store` for the last N days
- Query pattern: `frappe.get_all("BEI FQI Report", filters={"creation": [">=", add_days(today(), -days)]}, fields=["issue_type", "status", "store", "item_code", "name", "creation"])`

**Task 1C: Implement FQI stakeholder notifications** (1 hour)
- File: `hrms/hr/doctype/bei_fqi_report/bei_fqi_report.py`
- Lines 28-30: Wire `notify_stakeholders()` to send Google Chat message using:
  ```python
  from hrms.api.google_chat import send_message_to_space
  from hrms.utils.bei_config import get_chat_space, SPACE_NOTIFICATIONS
  ```
- Notification format: "FQI Report #{name} — {issue_type} at {store} for {item_code}. Status: {status}"
- **Must wrap in try/except** — notification failure must NEVER block FQI creation (same pattern as dispatch.py line 211)

**Effort:** 1 day total
**Test:** Create an FQI report via API, verify dashboard count updates, verify Chat notification fires

---

### Gap G-002: Store Returns Has No Logic

**Problem:** Two different `get_returns_pending()` functions exist:
1. `store.py:683` — **CORRECT implementation**: Queries `BEI Store Receiving Item` where `has_issue=1` AND no linked return Stock Entry exists
2. `commissary.py:654` — **Simplified version**: Queries `Stock Entry` with `remarks LIKE '%return%'`

The store.py implementation is the correct one. But the full returns workflow needs verification:
- `create_store_return` (store.py:734) — Creates Material Transfer Stock Entry from store → commissary
- `process_store_return` (store.py:815) — Processes the return (needs verification of credit note generation)

**Fix (4 tasks):**

**Task 2A: Verify existing returns flow end-to-end** (2 hours)
- Read `store.py:683-860` completely
- Verify `create_store_return` creates correct Stock Entry (Material Transfer, source=store warehouse, target=commissary warehouse)
- Verify `process_store_return` handles: status update, inventory reconciliation, and credit note (if implemented)
- Check if credit note generation exists or is missing

**Task 2B: Implement credit note generation if missing** (1.5 days)
- When a return is processed, create a credit note against the original billing.
- **AUDIT FIX (BLOCKER 5+8):** The original plan only created an internal billing document. The fix requires BOTH a billing record AND a GL Journal Entry:

  **Step 1: Schema fix** — Add `Credit Note` to `BEI Billing Schedule.billing_type` Select field options in `bei_billing_schedule.json` (currently only has `Monthly Fees` and `Delivery`). Run `bench migrate`.

  **Step 2: Create billing record** — `BEI Billing Schedule` with `billing_type = "Credit Note"`, negative amounts, linked to original billing via `remarks` or `reference_billing` field.

  **Step 3: Post GL Journal Entry (DM-1 compliant):**

  **v1.3 FIX:** `party_type`/`party` go ONLY on the AR row (1103101), NOT on revenue/income rows. Putting party on revenue rows creates 5x AR aging entries. All 4 fee accounts must be reversed pro-rata.

  **Pro-rata formula:** `reversal_amount = (return_qty / billed_qty) × fee_amount` for each fee account.

  ```python
  # Calculate pro-rata reversal for each fee
  ratio = return_qty / billed_qty
  royalty_rev   = round(original_royalty * ratio, 2)    # 7%
  mgmt_rev      = round(original_mgmt * ratio, 2)      # 2.5%
  marketing_rev = round(original_marketing * ratio, 2)  # 5%
  ecomm_rev     = round(original_ecomm * ratio, 2)      # 4%
  total_credit  = royalty_rev + mgmt_rev + marketing_rev + ecomm_rev

  jv = frappe.get_doc({
      "doctype": "Journal Entry",
      "voucher_type": "Credit Note",
      "posting_date": today(),
      "company": get_company(),
      "user_remark": f"Credit Note for Store Return {return_name} | {store} | {reason}",
      "accounts": [
          {
              "account": "4000301 - ROYALTY FEE INCOME - BEI",
              "debit_in_account_currency": royalty_rev,
              "cost_center": store_cost_center,
              # NO party_type/party — this is a revenue account, not AR/AP
          },
          {
              "account": "4000302 - MANAGEMENT FEE INCOME - BEI",
              "debit_in_account_currency": mgmt_rev,
              "cost_center": store_cost_center,
          },
          {
              "account": "4000303 - MARKETING FEE INCOME - BEI",
              "debit_in_account_currency": marketing_rev,
              "cost_center": store_cost_center,
          },
          {
              "account": "4000304 - ECOMMERCE FEE INCOME - BEI",
              "debit_in_account_currency": ecomm_rev,
              "cost_center": store_cost_center,
          },
          {
              "account": "1103101 - ACCOUNTS RECEIVABLE - TRADE - BEI",
              "credit_in_account_currency": total_credit,
              "party_type": "Customer",    # DM-1: party ONLY on AR row
              "party": store_customer_name, # DM-1: MANDATORY on AR
          }
      ]
  })
  jv.insert()
  jv.submit()
  ```
  - If original billing included output VAT, add a 6th row: debit `2102205` (Output VAT Payable) and increase the AR credit by the VAT amount.
  - **DM-1 rule:** `party_type`/`party` go ONLY on receivable (1103xxx) and payable (2101xxx) rows — NEVER on income, expense, or tax liability accounts.

  **Step 4: Atomicity (DM-2):**
  ```python
  frappe.db.savepoint("store_return_credit")
  try:
      # Insert BEI Billing Schedule (credit note)
      # Insert + submit Journal Entry
      frappe.db.release_savepoint("store_return_credit")
  except Exception:
      frappe.db.rollback(save_point="store_return_credit")
      raise
  # Notification OUTSIDE savepoint — failure must NOT roll back the credit note
  try:
      send_message_to_space(space, f"Credit note issued for return from {store}")
  except Exception:
      frappe.log_error("Credit note notification failed")
  ```

**Task 2C: Wire commissary.py returns to use store.py implementation** (2 hours)
- **AUDIT FIX:** `commissary.py:654` (`get_returns_pending`) must be **deprecated and removed**. It uses `remarks LIKE '%return%'` (fragile, full table scan). The canonical implementation is `store.py:683` which uses proper `has_issue=1` + NOT EXISTS anti-join.
- Replace `commissary.py:get_returns_pending()` body with: `from hrms.api.store import get_returns_pending as _store_returns; return _store_returns(store=None)` (show all stores for commissary view)
- Or better: delete entirely and have frontend call `store.get_returns_pending()` directly

**Task 2D: Add returns notification** (1 hour)
- When a store creates a return, notify commissary via Google Chat
- Pattern: `send_message_to_space(space, f"Return request from {store}: {items_count} items. Reason: {reason}")`

**Effort:** 2-3 days
**Test:** Create a store return, verify Stock Entry created, verify credit note generated, verify commissary receives notification, verify inventory updated at both warehouses

---

### Gap G-003: Google Chat Delivery Notifications are MOCK

**Problem:** `dispatch.py:571-588` (`_send_delivery_notification`) currently sends to a **global notifications space**, not per-store. The function IS wired and DOES send (it's not a stub — it calls `send_message_to_space`). However:
1. It sends to `SPACE_NOTIFICATIONS` (global), not to the specific store's space
2. The ETA calculation (`_calculate_eta` at line 495) uses hardcoded 20 min/stop
3. No per-store space mapping exists

**Current code (dispatch.py:571):**
```python
def _send_delivery_notification(driver, store, eta_range):
    from hrms.api.google_chat import send_message_to_space
    from hrms.utils.bei_config import get_chat_space, SPACE_NOTIFICATIONS
    space = get_chat_space(SPACE_NOTIFICATIONS)
    message = (f"🚚 *Delivery Update*\nDriver *{driver}* is 1 stop away "
               f"from *{store}*.\nETA: {eta_range}")
    send_message_to_space(space, message)
```

**Fix (3 tasks):**

**Task 3A: Add per-store Google Chat space mapping** (2 hours)
- The `Warehouse` DocType already has a `custom_gchat_space` field (used by `google_chat.py:on_store_order_update`)
- Modify `_send_delivery_notification` to try per-store space first, fall back to global:
  ```python
  store_warehouse = frappe.db.get_value("Warehouse", {"warehouse_name": store}, "custom_gchat_space")
  space = store_warehouse or get_chat_space(SPACE_NOTIFICATIONS)
  ```

**Task 3B: Populate store→space mapping for all 45 stores** (2 hours)
- Script to set `custom_gchat_space` on each store's Warehouse record
- Source: Google Chat API — list all spaces, match by store name pattern
- Or: Manual mapping CSV if Chat spaces don't follow naming convention

**Task 3C: Fix ETA calculation (bundle with G-073)** (4 hours)
- `dispatch.py:495` (`_calculate_eta`): Replace hardcoded 20 min/stop with `BEI Route Stop.estimated_minutes`
- Populate `estimated_minutes` from Jay's ETT spreadsheet data (already extracted in `docs/commissary/COMMISSARY_COST_BASELINE_2026-02-16.md`)
- Known ETTs: Shaw→Megamall=12min, Shaw→SM Bacoor=45min, Shaw→Dasmariñas=55min, Shaw→Lipa=120min
- Fallback to 20 min/stop if `estimated_minutes` is NULL

**Effort:** 1-2 days
**Test:** Trigger `confirm_delivery` on a trip with 3+ stops, verify notification goes to the correct store's Chat space with accurate ETA

---

### Gap G-006: Warehouse Has ZERO Frontend (36 APIs, No UI)

**Problem:** All 36 warehouse APIs are live in `warehouse.py`, `dispatch.py`, `picking.py`, and `ordering.py`. But there is NO React/Next.js frontend for warehouse operations. Staff must use Frappe Desk.

**5 Core Pages Required (MUST-HAVE):**

**Page 1: `/dashboard/warehouse/trips` — Trip Tracking** (3-4 days)
- **Purpose:** Drivers and dispatchers track active trips, confirm departures/deliveries
- **APIs consumed:**
  - `dispatch.get_trips(date, status)` — list trips for today
  - `dispatch.get_trip_detail(trip_name)` — trip detail with stops
  - `dispatch.confirm_departure(trip_name, driver, vehicle, vehicle_plate, temperature, seal_number)` — start trip
  - `dispatch.confirm_delivery(trip_name, stop_idx, signature, signed_by)` — confirm stop delivery
  - `dispatch.report_exception(trip_name, stop_idx, exception_type, reason, photo)` — report issue
  - `dispatch.get_route_progress(trip_name)` — real-time progress
- **UI requirements:**
  - Trip list with status badges (Pending, In Transit, Completed)
  - Trip detail: map of stops with status indicators, departure form, per-stop delivery confirmation
  - Exception reporting with photo capture (camera)
  - Mobile-first (drivers use phones)
- **RBAC:** `SCM_DISPATCH_ROLES` (HR Manager, Warehouse Manager, Logistics Coordinator, System Manager)

**Page 2: `/dashboard/warehouse/approve` — MR Approval** (2-3 days)
- **Purpose:** Warehouse supervisor approves/rejects Material Requests from stores
- **APIs consumed:**
  - `warehouse.get_pending_material_requests()` — list pending MRs
  - `warehouse.get_material_request_items(mr_name)` — MR detail
  - `warehouse.approve_material_request(mr_name, approved_items)` — approve with qty adjustments
  - `warehouse.reject_material_request(mr_name, reason)` — reject
- **UI requirements:**
  - Queue list with store name, item count, urgency badge
  - Detail view: item table with editable approved qty
  - Approve/Reject action buttons
  - Bulk approve capability for routine orders
- **RBAC:** `SCM_ADMIN_ROLES`

**Page 3: `/dashboard/warehouse/receive` — PO Receiving** (2-3 days)
- **Purpose:** Warehouse staff receives supplier deliveries against POs
- **APIs consumed:**
  - `warehouse.get_pending_purchase_orders()` — POs awaiting receipt
  - `warehouse.get_purchase_order_items(po_name)` — PO items
  - `warehouse.create_purchase_receipt(po_name, items, remarks)` — create GR
- **UI requirements:**
  - PO list with supplier, item count, expected date
  - Item table with qty received input
  - Remarks field for exceptions
  - Photo capture for damaged goods
- **RBAC:** `SCM_ADMIN_ROLES`

**Page 4: `/dashboard/warehouse/dispatch` — Stock Transfer/Dispatch** (3-4 days)
- **Purpose:** Dispatch stock from commissary/warehouse to stores
- **APIs consumed:**
  - `warehouse.get_ready_for_dispatch()` — approved MRs ready to dispatch
  - `warehouse.create_stock_transfer(source_warehouse, target_warehouse, items, mr_name, remarks)` — create transfer
  - `dispatch.create_trip_from_route(route_name, trip_date, vehicle, driver, selected_stops)` — Trip Wizard
  - `dispatch.get_routes(cargo_type, active_only)` — available routes
  - `dispatch.get_available_drivers(date)` — available drivers
  - `dispatch.get_vehicles(status)` — available vehicles
  - `picking.generate_pick_list(trip_name)` — generate pick list
  - `picking.complete_picking(pick_list_name)` — mark picking done
  - `picking.confirm_loaded(pick_list_name)` — confirm truck loaded
- **UI requirements:**
  - Dispatch queue: approved MRs grouped by route/store
  - Trip Wizard: select route → auto-populate stops → assign driver/vehicle → create trip
  - Pick list generation and tracking
  - Loading confirmation
- **RBAC:** `SCM_DISPATCH_ROLES`

**Page 5: `/dashboard/warehouse/my-delivery` — Store Staff Delivery View** (2-3 days)
- **Purpose:** Store staff sees incoming deliveries with ETA
- **APIs consumed:**
  - `dispatch.get_my_delivery(date)` — deliveries for my store today
- **UI requirements:**
  - Today's deliveries with driver name, ETA, cargo type
  - Real-time status updates (Pending → Departed → 1 Stop Away → Arrived)
  - Items preview per delivery
  - Receiving confirmation link
- **RBAC:** `SCM_STORE_ROLES`

**Total frontend effort:** 2-3 weeks (5 pages, mobile-first)

**Implementation notes:**
- All frontend goes in the `bei-tasks` repo (React/Next.js), NOT the legacy Vue/Ionic `frontend/` directory
- Use Shadcn UI components (existing pattern in bei-tasks)
- Each page follows the existing dashboard pattern: `/dashboard/warehouse/{page}`
- API calls use the existing Frappe REST client in bei-tasks
- Test accounts: `test.warehouse@bebang.ph` / `BeiTest2026!` (has Warehouse Staff role)

---

### Gap G-014: BOM Management Has No Frontend

**Problem:** 4 BOM APIs exist in `commissary.py` but no frontend:
- `create_bom(item_code, materials, quantity, uom, remarks)` — line 3090
- `update_bom(bom_name, materials, quantity, remarks)` — line 3170 (deactivates old, creates new — Frappe BOMs are immutable)
- `get_bom_detail(item_code)` — line 3256
- `check_production_feasibility(item_code, qty)` — line 3308

**Why critical:** Without BOM, `submit_production_output()` falls back to Material Receipt (no RM deduction). Raw material inventory is NOT decremented when production runs. P14.1M/month COGS impact.

**Fix (2 pages):**

**Page 1: `/dashboard/commissary/bom` — BOM List** (2-3 days)
- List all active BOMs with item code, quantity, materials count
- Search/filter by item group (Finished Goods)
- Create new BOM button
- Status badge (Active/Inactive)

**Page 2: `/dashboard/commissary/bom/[item_code]` — BOM Detail/Edit** (3-4 days)
- Show BOM materials table (item, qty, UOM)
- Edit materials (add/remove/change qty) — calls `update_bom` (creates new version)
- Production feasibility check button — calls `check_production_feasibility(item_code, qty)`
- Show feasibility result: can_produce (bool), shortfall items, max_producible qty
- Version history (BOMs are immutable, so show previous versions via `amended_from` chain)

**RBAC:** Commissary Supervisor role
**Effort:** 1 week
**Test:** Create a BOM for a halo-halo recipe, verify RM appears in materials, run feasibility check, submit production output and verify RM inventory decrements

---

### Gap G-047: RM Requisition Has No Approval Flow

**Problem:** `create_rm_requisition()` (commissary.py:2037) creates a Material Request and **immediately submits it** (`mr.insert()` then `mr.submit()`). There is no Draft→Review→Submit workflow. The commissary supervisor cannot review before it goes to procurement.

**Current code (commissary.py:2037):**
```python
def create_rm_requisition(items=None, required_by_date=None, remarks=None):
    # ... creates MR ...
    mr.insert()
    mr.submit()  # Goes directly to submitted (docstatus=1)
```

However, `get_my_requisitions()` (line 2104) queries `docstatus: ["in", [0, 1]]` — so it already handles Draft MRs.

**Fix (2 tasks):**

**Task 6A: Change to Draft-first workflow** (2 hours)
- File: `hrms/api/commissary.py`
- Line ~2098: Change `mr.submit()` to NOT auto-submit. Keep as Draft (docstatus=0).
- Add new endpoint: `submit_rm_requisition(mr_name)` that validates and submits
- Commissary Supervisor creates → reviews → submits → Procurement sees it

**Task 6B: Add Submit button on requisitions page** (4 hours)
- Existing frontend page: verify if `/dashboard/commissary/raw-materials` exists (commissary.md shows it as LIVE)
- If exists: add Submit action button for Draft requisitions
- If not: build simple requisition list + detail page with Submit/Cancel actions
- The `get_my_requisitions()` API already returns both Draft and Submitted MRs

**Effort:** 2 days
**Test:** Create RM requisition → verify it's Draft → Submit via UI → verify Procurement team can see it

---

## SHOULD-HAVE Gaps (11 items)

### Gap G-073: ETA Calculation Hardcoded at 20 min/stop

**Problem:** `dispatch.py:495` (`_calculate_eta`) assumes 20 minutes per stop regardless of distance.

**Fix:** Replace with `BEI Route Stop.estimated_minutes` field values. Populate from Jay's ETT data. Fallback to 20 min.

**Data source:** `docs/commissary/COMMISSARY_COST_BASELINE_2026-02-16.md` — all store ETTs extracted.

**Effort:** 1 day (bundled with G-003 Task 3C)

---

### Gap G-012: Route Management Frontend

**Problem:** 10 route management APIs exist (`create_route`, `update_route`, `duplicate_route`, `reorder_stops`, etc.) with no frontend.

**Fix:** Build `/dashboard/warehouse/routes` page with route list, create/edit form, stop reordering (drag-drop), and Trip Wizard integration.

**APIs:** `dispatch.get_routes()`, `dispatch.get_route_detail()`, `dispatch.create_route()`, `dispatch.update_route()`, `dispatch.delete_route()`, `dispatch.duplicate_route()`, `dispatch.reorder_stops()`

**Effort:** 3-5 days

---

### Gap G-050: Wastage Trend Analysis

**Problem:** Wastage data is logged (via `log_wastage()` at commissary.py:2751) but no analytics. Commissary barely breaks even (P12K/month net).

**Fix:** Build 1 backend aggregation endpoint + 1 frontend page showing wastage by reason code, item, shift, and time trend.

**Data:** `Stock Entry` to Scrap warehouse, with `batch_no` and reason in `BEI QC Form` or wastage remarks.

**Effort:** 2-3 days

---

### Gap G-051: FEFO Enforcement on Production/Dispatch

**Problem:** FEFO picking list is advisory only (`get_fefo_picking_list()` at commissary.py:2912). Stock Entry doesn't enforce batch selection order.

**Fix:** Add validation warning in `submit_production_output()` and `create_stock_transfer()`: if selected batch is not the oldest available, show warning "Batch {X} expires {date} — older batch {Y} expires {date_earlier} is available".

**Effort:** 1-2 days

---

### Gap G-122: 3PL Billing Validation + EWT Compliance

**Problem:** 3PL logistics costs P4.5M+/month. No validation workflow for matching BEI trip records to 3PL invoices.

**AUDIT FIX (BLOCKER 4 — BIR penalty risk):** The original plan had no EWT (Expanded Withholding Tax) logic. All payments to domestic logistics contractors are subject to EWT.

**v1.3 FIX — ATC code and rate corrected:** The correct ATC for domestic corporate carriers (trucking, freight, logistics) is **WC110 at 1%**, NOT WI100 (which is for professional fees at 10-15%). Per BIR RR 2-98 as amended by RR 11-2018, transportation contractors fall under ATC WC110 "Payments to carriers/trucking companies." Using WI100 would invalidate all Form 2307 certificates. P4.5M/month × 1% = P45K/month.

**Fix (3 tasks):**

**Task 122A: Add EWT fields to 3PL Rate** (2 hours)
- Add `ewt_atc` (Data, default "WC110") and `ewt_rate` (Percent, default 1.0) fields to `BEI 3PL Rate` DocType
- Different 3PL providers may have different rates (WC110=1% for corporate carriers, WI158=15% if individual contractor >P10M gross)
- **v1.3 FIX — EWT rate source precedence:** At runtime, `create_3pl_payment_je()` MUST read `ewt_rate` from the `BEI 3PL Rate` record, NOT from the module-level `EWT_RATE = 0.02` constant in `billing.py:598`. Remove the module constant after Task 122A is deployed.

**Task 122B: Compute EWT in reconciliation** (1 day)
- In `generate_3pl_reconciliation()`, after matching trip records to invoices:
  ```python
  ewt_rate = frappe.db.get_value("BEI 3PL Rate", rate_name, "ewt_rate") or 1.0
  ewt_amount = round(net_payable * (ewt_rate / 100), 2)
  net_payment = net_payable - ewt_amount
  ```
- Create Journal Entry: Debit `2101101` (AP), Credit `2102202` (Withholding Tax - Expanded Payable)
- **v1.3 FIX — DM-1 party placement:** `party_type = "Supplier"` and `party = 3pl_supplier_name` go ONLY on the `2101101` (AP) row, NOT on the `2102202` (EWT Payable) row. EWT Payable is a government obligation, not a supplier balance — putting party on it creates incorrect supplier ledger entries.

**Task 122C: Form 2307 generation** (1 day)
- Generate Form 2307 per 3PL provider per month
- Must issue to each provider by the 10th of following month

**Task 122D: Frontend + Input VAT** (2-3 days)
- Display reconciliation results with EWT deduction column
- On invoice matching, split Input VAT to `1105104` (Input VAT - Services), not goods account
- VAT = invoice_gross / 1.12 × 0.12

**Effort:** 5-6 days (backend EWT + frontend + Form 2307)
**All 5 3PL providers (3MD, Orca, Suzuyo, Four Coolitz, WGD) must be set up as Frappe Suppliers with correct EWT ATC.**

---

### Gap G-046: Hub Transfer Approval

**Problem:** Hub transfers (commissary → distribution hub) create Stock Entry directly without approval.

**AUDIT FIX (BLOCKER 6 — Inter-company tax risk):** Bebang Kitchen Inc. (BKI) is a separate legal entity from BEI. Hub transfers may constitute taxable intercompany sales requiring VAT invoices per BIR RR 2-2013.

**DECISION GATE (must resolve before implementation):**
- [ ] **Q1:** Is BKI on the SAME Frappe instance as BEI? (Check with Alyssa/Denise)
- [ ] **Q2:** If same instance — are they in SEPARATE company books in Frappe?
- **If BKI and BEI are separate Frappe companies:** Hub transfer must use inter-company transaction flow (Purchase Invoice on BEI side, Sales Invoice on BKI side). Material Transfer is NOT legally correct.
- **If BKI is a cost center within BEI (same company):** Material Transfer is fine. Document this policy formally. Add a `transfer_price` field to BOM for proper COGS tracking.

**Fix (after decision gate resolved):**
- Add 1-step approval: Commissary Supervisor initiates → Warehouse Supervisor approves
- Modify `create_hub_transfer()` (commissary.py:1744) to create as Draft, add `approve_hub_transfer()` endpoint
- If inter-company: replace Stock Entry with inter-company invoicing flow

**Effort:** 2 days (same-company path) or 5 days (inter-company path)

---

### Gap G-043: Production Feasibility Check Button

**Problem:** `check_production_feasibility()` API exists (commissary.py:3308) but no UI to trigger it.

**Fix:** Add "Check Feasibility" button on production submission page. Shows: can_produce, shortfall items, max_producible. Block production if critical shortfall.

**Effort:** 2-4 hours (frontend only — backend exists)

---

### Gap G-045: Work Order Detail View

**Problem:** Work Orders list exists (`get_work_orders()` at commissary.py:2595) but no detail page for a single WO.

**Fix:** Build `/dashboard/commissary/work-orders/[name]` detail page showing: items, quantities, RM requirements, status, crew, start/complete actions.

**APIs:** `get_work_orders()`, `start_work_order()`, `complete_work_order()`

**Effort:** 1-2 days

---

### Gap G-067: Billing Auto-Create Feature Flag Documentation

**Problem:** `BEI Settings.billing_auto_create_on_delivery` default is undocumented. If disabled, franchise billing is missed.

**Fix:** Document default value, add to deployment checklist, verify current setting on production.

**Effort:** 1 hour

---

### Gap G-070: Store Order → Material Request Link

**Problem:** No foreign key from Material Request → BEI Store Order. Cannot trace "Why was this MR created?"

**Fix:** Add `store_order` Link field to Material Request (custom field via Frappe). Set in `submit_order()` (ordering.py:169) when creating MR.

**Effort:** 1 day

---

### Gap G-101: Silent Billing Failure Alerts

**Problem:** Billing creation failures (async) only logged to Frappe error log. No notification.

**Fix:** In `_create_delivery_billing()` (dispatch.py:343), add try/except that sends Google Chat alert on failure. Bundle with G-003 Chat work.

**Effort:** 2-4 hours

---

## Sprint Execution Order

### Phase 0: Pre-Sprint Schema & Bug Fixes — COMPLETE

These fix existing broken code discovered by the audit. They are prerequisites for all subsequent phases.

| # | Blocker | Task | File(s) | Effort |
|---|---------|------|---------|--------|
| P0-1 | B1: confirm_loaded inventory loss | Change `stock_entry_type` from `"Material Issue"` to `"Material Transfer"` in `picking.py:confirm_loaded()`. **v1.3 FIX — data model:** Create one Stock Entry PER STOP (not per pick list), because each stop has a different target warehouse. Loop through trip stops, filter pick list items by stop, create SE with `s_warehouse=commissary` and `t_warehouse=stop.warehouse`. This replaces the current single-SE-per-pick-list approach. Pick list items need `stop_order` or `store` field to enable this grouping — add to `BEI Pick List Item` DocType and populate during `generate_pick_list()`. | `hrms/api/picking.py` | 4h |
| P0-2 | B2: Store Order status enum | Add `Ready for Dispatch` and `Partially Fulfilled` to `BEI Store Order.status` Select field in `bei_store_order.json`. OR change `commissary.py:937,939` to use existing `Partial` value. | `bei_store_order.json` or `commissary.py` | 1h |
| P0-3 | B3: approve_material_request no-op | After inserting Comment, add `frappe.db.set_value("Material Request", mr_name, "status", "Ordered")` or use custom status. Currently the function only adds a comment and does nothing. | `hrms/api/warehouse.py:264-298` | 2h |
| P0-4 | B8: billing_type missing Credit Note | Add `Credit Note` (and `Adjustment`) to `BEI Billing Schedule.billing_type` Select options in `bei_billing_schedule.json`. | `bei_billing_schedule.json` | 30m |
| P0-5 | B7: RBAC alignment | Decide role mappings, update `lib/roles.ts`, add `Commissary Supervisor` + `Driver` sidebar entries, provision `test.driver@bebang.ph`. | `bei-tasks/lib/roles.ts` | 2h |
| P0-6 | Audit: BEI Store Order missing `trip` Link field | Add `trip` Link field (options: `BEI Distribution Trip`) to `bei_store_order.json`. Without this, `picking.py:generate_pick_list()` always returns empty. | `bei_store_order.json` | 30m |
| P0-7 | Audit: dispatch_date → trip_date | Change `commissary.py:1537` filter from `"dispatch_date"` to `"trip_date"`. Currently returns empty list every day. | `hrms/api/commissary.py` | 15m |
| P0-8 | Audit: approve_order permission conflict | Add `Area Supervisor` to `ORDERING_WAREHOUSE_ROLES` in `ordering.py`, OR make `approve_order()` call `_generate_dr_internal()` (no permission check). Currently Area Supervisors get PermissionError mid-approval. | `hrms/api/ordering.py` | 1h |
| P0-9 | Audit: Semi-Franchise dead code | Remove `"Semi-Franchise"` branch from `billing.py:299` (not a valid store type), or add to DocType if it's a real store type. | `hrms/api/billing.py` | 30m |

| P0-10 | v1.3: RBAC backend centralization | Create `hrms/utils/scm_roles.py` with `SCM_ADMIN_ROLES`, `SCM_DISPATCH_ROLES`, `SCM_STORE_ROLES`, `SCM_PICKING_ROLES`, `ORDERING_WAREHOUSE_ROLES`, `RATE_MANAGEMENT_ROLES`. Import from this file in `dispatch.py`, `ordering.py`, `picking.py`, `billing.py`. Replace 35 call sites of `_check_scm_permission()` with single shared function. | `hrms/utils/scm_roles.py` + 4 API files | 4h |
| P0-11 | v1.3: Split commissary.py God Object | Split 3,569-line file into 4 modules BEFORE Phase 1 starts (6+ concurrent edits planned): `commissary_dashboard.py` (dashboard + production), `commissary_quality.py` (FQI + QC), `commissary_requisition.py` (RM + hub transfers), `commissary_bom.py` (BOM CRUD). Keep `commissary.py` as a thin re-export layer for backwards compatibility. | `hrms/api/commissary*.py` | 3 days |
| P0-12 | v1.3: Fix N+1 queries | Batch `get_production_items()` Bin + production queries into 2 SQL JOINs (replaces 400+ sequential queries). Batch `get_pending_purchase_orders()` items fetch into single query with GROUP_CONCAT. | `hrms/api/commissary.py`, `hrms/api/warehouse.py` | 4h |

**Deploy Phase 0** — Full Docker build + `bench migrate` required (schema changes).
**Verification:** Run each fixed endpoint once with a test account to confirm it works.
**Note:** P0-11 (commissary.py split) is a 3-day task. Run P0-1 through P0-10 + P0-12 on Day 0, then P0-11 over Days 0-2 while Phase 1 backend work begins on non-commissary files.

---

### Phase 1: Feature Backend Fixes — COMPLETE (except G-046)

| # | Gap | Task | Status |
|---|-----|------|--------|
| 1 | G-001 | Task 1A: FQI dashboard count (real query) | DONE |
| 2 | G-001 | Task 1B: `get_fqi_summary()` implementation | DONE |
| 3 | G-001 | Task 1C: FQI Google Chat notifications | DONE |
| 4 | G-047 | RM requisition Draft-first + `approve_requisition()` endpoint | DONE |
| 5 | G-067 | Billing feature flag (`BEI Settings.enable_delivery_billing`) | DONE |
| 6 | G-101 | Billing failure Chat alerts | DONE |
| 7 | G-003 | Per-store Chat space mapping via `custom_gchat_space` | DONE |
| 8 | G-003 | ETA calculation fix (G-073 bundled) — per-stop `estimated_minutes` | DONE |
| 9 | G-070 | Store order Link field on Material Request | DONE |
| 10 | G-002 | Tasks 2A-2D: Returns flow + credit note + GL JE + Chat notifications | DONE |
| 11 | G-051 | FEFO enforcement warnings | DONE |
| 12 | G-069 | UNIQUE constraint on Distribution Trip (route_name, trip_date) | DONE |
| 13 | G-100 | Idempotency guards (store return, hub transfer, RM requisition) | DONE |
| 14 | G-102 | Transaction isolation (SELECT FOR UPDATE + savepoint fix) | DONE |
| 15 | G-046 | Hub transfer approval workflow | **BLOCKED** — waiting on Finance (BKI inter-company tax decision) |

**Deploy backend after Phase 1** — Full Docker build + migrate required (new code).
**Gate:** All 45 stores must have `custom_gchat_space` mapped before deploy. Assert: `SELECT COUNT(*) FROM tabWarehouse WHERE custom_gchat_space IS NOT NULL AND custom_gchat_space != '' AND is_group = 0` = 45.

### Phase 2: Warehouse Frontend

**Step 0 — Prerequisite (do first):** Create the data-fetching foundation before any page work:
- Hook files: `use-warehouse-trips.ts`, `use-warehouse-approve.ts`, `use-warehouse-receive.ts`, `use-warehouse-dispatch.ts`, `use-commissary-bom.ts`
- Zod schemas: `DepartureSchema`, `DeliveryConfirmationSchema`, `ExceptionReportSchema`, `POReceivingItemSchema`, `MRApprovalSchema`
- API proxy routes: `app/api/dispatch/route.ts`, `app/api/picking/route.ts` (without these, CORS blocks all warehouse API calls)
- Refresh strategy: Trips page `refetchInterval: 30000`, Approve page `refetchOnWindowFocus: true` (manual), Receive page `refetchInterval: 60000`

| # | Gap | Page | Depends On |
|---|-----|------|------------|
| 1 | G-006 | `/dashboard/warehouse/trips` (trip tracking) | Step 0 |
| 2 | G-006 | `/dashboard/warehouse/approve` (MR approval) | Step 0 |
| 3 | G-006 | `/dashboard/warehouse/receive` (PO receiving) | Step 0 |
| 4 | G-006 | `/dashboard/warehouse/dispatch` (dispatch + Trip Wizard) | Step 0 |
| 5 | G-006 | `/dashboard/warehouse/my-delivery` (store view) | Step 0 |

Pages 1-5 can be built in parallel after Step 0 is done.

### Phase 3: Commissary Frontend

| # | Gap | Page | Depends On |
|---|-----|------|------------|
| 1 | G-014 | `/dashboard/commissary/bom` (BOM list + detail) | Step 0 hooks |
| 2 | G-047 | Submit button on requisitions page | Phase 1 #4 |
| 3 | G-043 | Feasibility check button on production page | — |
| 4 | G-045 | Work order detail view | — |

Pages 1-4 can be built in parallel.

### Phase 4: SHOULD-HAVE Enhancements

| # | Gap | What | Depends On |
|---|-----|------|------------|
| 1 | G-050 | Wastage trend analysis page | Phase 2+3 done |
| 2 | G-012 | Route management frontend | Phase 2 #4 |
| 3 | G-122 | 3PL billing reconciliation frontend | Phase 1 deployed |

---

## Verification Checklist — L3/L4 Test Specifications

**AUDIT FIX (BLOCKER 9):** All tests upgraded from L1/L2 to L3/L4 with specific assertions.
**Quality target:** >= 70% of tests at L3+L4 level.
**Test execution:** Use Playwright CLI + Frappe API calls. Each test must assert DB state, not just UI appearance.

### Phase 0 Bug Fix Verifications (L4 — DB verify)

| ID | Test | Level | Assertions |
|----|------|-------|------------|
| P0-T1 | `confirm_loaded()` creates Material Transfer (not Issue) | L4 | DB: `SELECT stock_entry_type FROM tabStock Entry WHERE pick_list=%s` = "Material Transfer". DB: `t_warehouse` is populated on all SE items. DB: Bin qty at target warehouse increased. |
| P0-T2 | Store Order status updates work | L4 | API: Call `_update_store_order_status_after_fulfillment()` → DB: `SELECT status FROM tabBEI Store Order WHERE name=%s` IN valid options. No error in `tabError Log`. |
| P0-T3 | `approve_material_request()` changes MR status | L4 | API: Call with valid MR name → DB: `SELECT status FROM tabMaterial Request WHERE name=%s` != "Pending". DB: Comment also exists. |
| P0-T4 | BEI Billing Schedule accepts Credit Note type | L4 | API: Insert billing with `billing_type="Credit Note"` → no ValidationError. DB: record exists. |
| P0-T5 | `generate_pick_list()` returns results for trip with linked store orders | L4 | DB: Create BEI Store Order with `trip` Link set → API: Call `generate_pick_list(trip_name)` → response `success=True`, items non-empty. |
| P0-T6 | `get_delivery_routes()` returns today's trips | L4 | DB: Create trip with `trip_date=today()` → API call → response includes the trip. |
| P0-T7 | Area Supervisor can approve orders | L3 | API: Login as `test.area@bebang.ph` → call `approve_order(order_name)` → no PermissionError. |

### Backend Feature Verifications (L4 — DB verify)

| ID | Test | Level | Assertions |
|----|------|-------|------------|
| B-T1 | FQI dashboard count is real | L4 | DB: Insert 3 FQI Reports with status "Open" → API: `get_commissary_dashboard()` → `fqi_issues >= 3`. |
| B-T2 | `get_fqi_summary()` returns grouped data | L4 | DB: Insert FQI reports with different issue_types → API: Response has non-empty `data` array with correct grouping. |
| B-T3 | FQI notification fires | L3 | API: Create FQI report → verify `send_message_to_space` was called (mock or check Google Chat API log). Negative: simulate Chat failure → FQI report still created. |
| B-T4 | Store return creates correct Stock Entry | L4 | API: `create_store_return(store, items)` → DB: SE `stock_entry_type="Material Transfer"`, `from_warehouse=store`, `to_warehouse=commissary`. DB: Bin qty decreased at store, increased at commissary. |
| B-T5 | Store return credit note has GL entries | L4 | API: `process_store_return(return_name)` → DB: `BEI Billing Schedule` exists with `billing_type="Credit Note"`. DB: `Journal Entry` exists with `party_type="Customer"` and `party` set ONLY on the AR row (1103101), NOT on revenue rows (4000301-4). DB: GL Entry has 4 debit rows (royalty, mgmt, marketing, ecomm) + 1 credit row (AR). DB: All 4 fee accounts debited pro-rata. |
| B-T6 | `confirm_delivery()` sends to per-store Chat space | L4 | DB: Set `custom_gchat_space` on test store's Warehouse → API: `confirm_delivery()` → verify notification sent to that space (not SPACE_NOTIFICATIONS). Negative: store with no `custom_gchat_space` → falls back to global. |
| B-T7 | ETA uses `estimated_minutes` | L3 | DB: Set `estimated_minutes=45` on a route stop → API: `confirm_delivery()` on previous stop → ETA in notification reflects 45 min, not 20 min. |
| B-T8 | RM requisition is Draft | L4 | API: `create_rm_requisition(items)` → DB: `docstatus=0`. API: `submit_rm_requisition(mr_name)` → DB: `docstatus=1`. Negative: submit already-submitted → error. |
| B-T9 | FEFO warns on non-oldest batch | L3 | DB: Create 2 batches (old expiry, new expiry) → API: Select newer batch → response includes warning with older batch details. |
| B-T10 | Hub transfer creates Draft | L4 | API: `create_hub_transfer()` → DB: Stock Entry `docstatus=0`. API: `approve_hub_transfer()` with Warehouse Supervisor → DB: `docstatus=1`. Negative: non-supervisor → PermissionError. |
| B-T11 | Billing failure alerts | L3 | Simulate billing creation failure → verify Chat notification sent with error details. |
| B-T12 | Material Request has store_order link | L4 | API: `submit_order()` → DB: `SELECT store_order FROM tabMaterial Request WHERE name=%s` = order name. |

### Frontend Verifications (L3 — Browser API with real data)

| ID | Test | Level | Assertions |
|----|------|-------|------------|
| F-T1 | Trips page: departure form submit | L3 | Login as `test.warehouse@bebang.ph` → fill departure form (driver, vehicle, plate, temp, seal) → submit → API returns success. DB: trip status = "In Transit". |
| F-T2 | Trips page: delivery confirmation | L3 | On trip with stops → confirm delivery on stop 1 → API returns success. DB: stop status = "Delivered". Signature field populated. |
| F-T3 | Trips page: exception report with photo | L3 | Report exception with type + reason + photo → API returns success. DB: exception record exists. |
| F-T4 | Approve page: approve MR with qty adjustment | L3 | Login as `test.warehouse@bebang.ph` → adjust qty → approve → DB: MR status changed. |
| F-T5 | Approve page: reject MR | L3 | Reject with reason → DB: MR status = rejected. |
| F-T6 | Receive page: create GR | L3 | Select PO → enter received qty → submit → DB: Purchase Receipt created, `docstatus=1`. |
| F-T7 | Dispatch page: Trip Wizard end-to-end | L3 | Select route → stops → driver → vehicle → create trip → DB: BEI Distribution Trip created. Pick list generated. |
| F-T8 | My-delivery page: store staff sees deliveries | L3 | Login as `test.staff@bebang.ph` → page shows today's deliveries. Verify status badges render. |
| F-T9 | BOM list + create | L3 | Login as `test.commissary@bebang.ph` → create BOM with materials → DB: BOM created with correct items. |
| F-T10 | BOM feasibility check | L3 | On existing BOM → click Check Feasibility → response shows can_produce, shortfall items. |
| F-T11 | RM requisition Submit button | L3 | Draft MR visible → click Submit → DB: `docstatus=1`. |

### RBAC Tests (L3 — Per-role access matrix)

| ID | Test | Level | Assertions |
|----|------|-------|------------|
| R-T1 | Wrong role blocked from trips page | L3 | Login as `test.staff@bebang.ph` (Store OIC) → navigate to `/warehouse/trips` → redirected or 403. |
| R-T2 | Wrong role blocked from approve page | L3 | Login as `test.staff@bebang.ph` → `/warehouse/approve` → redirected or 403. |
| R-T3 | Driver can access trips page | L3 | Login as `test.driver@bebang.ph` → `/warehouse/trips` → page loads. |
| R-T4 | Store staff can access my-delivery | L3 | Login as `test.staff@bebang.ph` → `/warehouse/my-delivery` → page loads. |
| R-T5 | Commissary Supervisor can access BOM | L3 | Login as `test.commissary@bebang.ph` → `/commissary/bom` → page loads. |

### Negative Tests (L3/L4)

| ID | Test | Level | Assertions |
|----|------|-------|------------|
| N-T1 | Return with no stock in source warehouse | L4 | API: `create_store_return` with qty > available → error returned, no SE created. |
| N-T2 | Double-return prevention | L4 | API: Return same receiving item twice → second call returns error. |
| N-T3 | Submit already-submitted MR | L3 | API: `submit_rm_requisition()` on docstatus=1 MR → error. |
| N-T4 | Chat API down during delivery confirmation | L3 | Simulate Chat failure → delivery confirmation still succeeds. No exception propagated. |
| N-T5 | BOM edit on submitted BOM | L3 | API: `update_bom()` on submitted BOM → creates NEW version (not modify in-place). |
| N-T6 | PO receiving qty exceeds ordered qty | L3 | Enter qty_received > ordered → validation error. |

### Integration Flow Tests (L4 — Full pipeline with DB verification at each step)

| ID | Test | Level | Assertions |
|----|------|-------|------------|
| I-T1 | Store Order → MR → Approve → Dispatch → Trip → Delivery → Billing | L4 | At each step: verify DB state (docstatus, status, warehouse bins, GL entries). Final: billing record exists with correct amounts. |
| I-T2 | RM Requisition (Draft) → Submit → Procurement visibility | L4 | Create draft → submit → login as `test.procurement@bebang.ph` (if exists) → MR visible in procurement queue. |
| I-T3 | Production Output with BOM → RM decremented | L4 | DB: Check RM Bin qty before → submit production → DB: RM Bin qty after = before - BOM qty. FG Bin qty increased. |
| I-T4 | Store Return → Credit Note → GL → Inventory | L4 | Full chain: return created → SE exists → billing credit note exists → JV exists with party fields → GL entries balance → inventory adjusted at both warehouses. |

**Test count:** 7 (Phase 0) + 12 (Backend) + 11 (Frontend) + 5 (RBAC) + 6 (Negative) + 4 (Integration) = **45 tests**
**L3+L4 count:** 45/45 = **100%** (exceeds 70% threshold)

---

## Deployment Notes

### AUDIT FIX (BLOCKER 10): Rollback Plan

**Before EVERY deploy:**
1. `git tag pre-scm-sprint-phase-N-$(date +%Y%m%d)` on both `hrms` and `bei-tasks` repos
2. Record current Docker image tag: `docker inspect --format='{{.Image}}' frappe-worker | head -c 12`
3. Database snapshot: `docker exec mariadb mysqldump -u root -p$MYSQL_ROOT_PASSWORD bei_erp > /tmp/bei_erp_pre_deploy_$(date +%Y%m%d).sql`

**Rollback procedure:**
- Backend: `git checkout <pre-deploy-tag> && full Docker build`
- Frontend: `vercel rollback --yes` or redeploy previous commit
- Database: Restore from mysqldump snapshot
- Frappe Customize Form changes: manually revert via Desk (not version-controlled)

### Backend Deployment
- **All backend changes require a FULL Docker build** (`skip_build=false`, `no_cache=true`)
- Build takes 5-10 minutes, migrations 1-2 minutes after
- Workflow: `.github/workflows/build-and-deploy.yml`
- Test with real user session before deploying (not API token)
- **Must test with ALL 5 role-type test accounts** (warehouse, commissary, store staff, supervisor, area)

### Frontend Deployment
- All frontend goes to `bei-tasks` repo (React/Next.js on Vercel)
- **MANDATORY:** Update `lib/cache-bust.ts` (change `CACHE_BUST` string + `CACHE_BUST_NOTE`) before every Vercel deploy
- Deploy: `cd C:/Users/Sam/.cursor/Projects/bei-tasks && vercel.cmd --prod --force --token $TOKEN --scope team_xvK1nhuvsdZp3GNfd4uDJ0DW --yes`
- On Windows: use `vercel.cmd` not `vercel`
- **Post-deploy verify:** Open browser console, confirm new cache-bust string is printed

### Migration Runbook (Numbered — Execute in Order)

**Phase 0 Migrations (schema changes — deploy first):**
1. Verify field existence: `bench --site bei.local get-doc DocType "BEI Store Order" | grep -c "trip"` — if 0, add it
2. Add `trip` Link field to `BEI Store Order` (type: Link, options: BEI Distribution Trip)
3. Add `Ready for Dispatch`, `Partially Fulfilled` to `BEI Store Order.status` Select options
4. Add `Credit Note`, `Adjustment` to `BEI Billing Schedule.billing_type` Select options
5. Add `ewt_atc` (Data) and `ewt_rate` (Percent) to `BEI 3PL Rate`
6. Verify `estimated_minutes` exists on `BEI Route Stop` — if not, add it (Float type)
7. Verify `store_order` custom field on Material Request — if not, add via Customize Form
8. Run `bench migrate` — all schema changes are idempotent (add-if-not-exists)

**Phase 0 Code fixes (deploy after schema):**
9. Fix `picking.py:confirm_loaded()` — Material Issue → Material Transfer
10. Fix `warehouse.py:approve_material_request()` — add status update
11. Fix `commissary.py:1537` — dispatch_date → trip_date
12. Fix `ordering.py` — Area Supervisor permission conflict

**Phase 1 Code (feature work — deploy after Phase 0 verified):**
13. All G-001 through G-122 backend changes
14. `bench migrate` for any additional field additions

### Test Accounts
| Account | Email | Password | Role |
|---------|-------|----------|------|
| Warehouse Staff | test.warehouse@bebang.ph | BeiTest2026! | Warehouse Staff |
| Commissary Supervisor | test.commissary@bebang.ph | BeiTest2026! | Commissary Supervisor |
| Store Staff | test.staff@bebang.ph | BeiTest2026! | Store OIC |
| Store Supervisor | test.supervisor@bebang.ph | BeiTest2026! | Store Supervisor |
| Area Supervisor | test.area@bebang.ph | BeiTest2026! | Area Supervisor |
| Driver | test.driver@bebang.ph | BeiTest2026! | Driver (v1.3 FIX — was missing from table; provisioned in P0-5) |

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Frappe BOM immutability — updates create new versions | Users confused by version chain | Clear UI messaging: "This will create a new BOM version" |
| Google Chat rate limits during bulk notifications | Notifications silently dropped | Retry logic in `send_message_to_space`, queue batch sends |
| Store→Chat space mapping incomplete | Some stores miss notifications | Fallback to global `SPACE_NOTIFICATIONS` if per-store not configured |
| Returns credit note logic missing entirely | Financial reconciliation gaps | Verify in Task 2A before building; may need DocType extension |
| Frappe Employee records: NEVER use ORM for inserts | Cascade validation failures | Direct SQL INSERT only (see Memory #6) — relevant if creating new DocType records |
| 45 stores × daily operations = high API volume | Performance under load | All existing APIs use pagination (`limit` params). Frontend must paginate. |

---

## NICE-TO-HAVE (Deferred — Do Not Build This Sprint)

| Gap | What | Why Defer |
|-----|------|-----------|
| G-040 | Item groups hardcoded | Stable categories, fine as-is |
| G-041 | Wastage reasons hardcoded | 6 codes adequate |
| G-042 | QC templates hardcoded | 8 form types stable |
| G-044 | Batch tracking enable utility | One-time admin, use bench console |
| G-048 | Quality Inspection templates | Standard Frappe adequate |
| G-049 | Production suggestions ML | DI heuristic is appropriate |
| ~~G-069~~ | ~~Duplicate trip race condition~~ | **PROMOTED to Phase 1** — correctness bug, not debt (design review C-2) |
| G-071 | ETA window configurable per cargo | ±15 min default is fine |
| G-072 | Warehouse capacity tracking | Single commissary, not needed |
| G-092 | Cascade delete on visits | Audit records shouldn't be deleted |
| G-099 | Rate limiting | Internal app, not a DoS target |
| ~~G-100~~ | ~~Idempotency~~ | **PROMOTED to Phase 1** — correctness bug, not debt (design review C-2) |
| ~~G-102~~ | ~~Transaction isolation~~ | **PROMOTED to Phase 1** — correctness bug, not debt (design review C-2) |
| G-123 | Pick/pack workflow | Wrong model for production-to-dispatch |

---

*This plan is self-contained. An implementing agent should be able to execute it without additional context beyond reading the source files listed above.*

---

## Audit Amendments (v1.1 → v1.2 → v1.3) — 2026-02-19

### Audit Methodology

6 specialized agents audited this plan in parallel (twice — v1.1 initial, v1.2 re-audit). Full reports with code fixes are in the referenced files.

| Domain | v1.1 Score | v1.2 Re-Audit Score | v1.1 Findings | v1.2 Findings |
|--------|-----------|-------------------|---------------|---------------|
| Frappe Backend | 7 CRITICAL | 3 new CRITICAL (3/7 resolved) | `output/plan-audit/scm-commissary-warehouse/frappe_backend_findings.md` | `output/plan-audit/scm-commissary-warehouse-v2/frappe_backend_findings.md` |
| PH Finance | 31/100 | 54/100 | `output/plan-audit/scm-commissary-warehouse/ph_finance_findings.md` | `output/plan-audit/scm-commissary-warehouse-v2/ph_finance_findings.md` |
| Frontend | 5/10 | 6/10 | `output/plan-audit/scm-commissary-warehouse/frontend_findings.md` | `output/plan-audit/scm-commissary-warehouse-v2/frontend_findings.md` |
| Deployment/QA | NO-GO | GO (conditional) | `output/plan-audit/scm-commissary-warehouse/deployment_qa_findings.md` | `output/plan-audit/scm-commissary-warehouse-v2/deployment_qa_findings.md` |
| System Architecture | 2.8/5 | 3.4/5 | `output/plan-audit/scm-commissary-warehouse/system_arch_findings.md` | `output/plan-audit/scm-commissary-warehouse-v2/system_arch_findings.md` |
| Design Review | 2/5 | 3/5 | `output/plan-audit/scm-commissary-warehouse/design_review_findings.md` | `output/plan-audit/scm-commissary-warehouse-v2/design_review_findings.md` |

### Top 10 Blockers (Must Resolve Before Execution)

#### BLOCKER 1: `confirm_loaded()` Uses Material Issue Instead of Material Transfer — Permanent Inventory Loss
**Source:** `frappe_backend_findings.md` C3 | **Severity:** CRITICAL
**Problem:** `picking.py:confirm_loaded()` creates a Stock Entry with `stock_entry_type = "Material Issue"`, which permanently removes items from inventory with no destination warehouse. For dispatch to stores, the correct type is Material Transfer.
**Fix:** Change to `"Material Transfer"` and populate both `s_warehouse` and `t_warehouse`. See findings file for code details.

#### BLOCKER 2: BEI Store Order Status Enum Missing Values — Fulfillment Silently Fails
**Source:** `frappe_backend_findings.md` C1 | **Severity:** CRITICAL
**Problem:** `commissary.py:_update_store_order_status_after_fulfillment()` sets `"Ready for Dispatch"` and `"Partially Fulfilled"` — neither exists in the DocType's Select field options. Frappe throws a validation error, swallowed by try/except, so fulfillment status updates always silently fail.
**Fix:** Add `Ready for Dispatch` and `Partially Fulfilled` to `bei_store_order.json` status options + `bench migrate`, or change code to use existing values.

#### BLOCKER 3: `approve_material_request()` Is a No-Op — Only Adds Comment
**Source:** `frappe_backend_findings.md` C2 | **Severity:** CRITICAL
**Problem:** `warehouse.py:approve_material_request()` only inserts a Comment. It does not update `mr.status`, does not call `mr.save()`. The entire warehouse approval workflow is broken — approval has zero effect.
**Fix:** Update `mr.status` after approval (e.g., via `frappe.db.set_value`) or redesign using Frappe's Workflow module.

#### BLOCKER 4: EWT on 3PL Payments — P90K+/Month Unwithheld (BIR Penalty Risk)
**Source:** `ph_finance_findings.md` C1 | **Severity:** CRITICAL
**Problem:** P4.5M/month in 3PL logistics payments are subject to EWT. Zero EWT logic exists in `billing.py` or `dispatch.py`. BIR criminal liability under Sec. 251-252 NIRC.
**Fix:** Add `ewt_rate` and `ewt_amount` fields to `BEI 3PL Rate`. Compute EWT in `generate_3pl_reconciliation()`. Issue Form 2307 monthly. **v1.3 correction:** ATC is WC110 (1% for corporate carriers), NOT WI100 (professional fees).

#### BLOCKER 5: Credit Note Has No GL Entry — Revenue Not Actually Reversed
**Source:** `ph_finance_findings.md` C2 + `deployment_qa_findings.md` C-01 | **Severity:** CRITICAL
**Problem:** Task 2B creates `BEI Billing Schedule` with negative amounts but posts NO Journal Entry. Revenue is not reversed in GL. Additionally, credit note path has no DM-1 verification (party/party_type fields). The books won't balance at subsidiary ledger level.
**Fix:** Task 2B must include a GL Journal Entry (Debit revenue accounts 4000301-4000304, Credit AR 1103101) with `party_type = "Customer"` and proper remarks. Wrap in `frappe.db.savepoint()` with notification OUTSIDE the savepoint.

#### BLOCKER 6: Inter-Company BKI ↔ BEI Hub Transfers — Possible Taxable Sales
**Source:** `ph_finance_findings.md` C5 | **Severity:** CRITICAL
**Problem:** Bebang Kitchen Inc. (BKI) is a separate legal entity. Hub transfers modeled as internal Material Transfers may constitute taxable intercompany sales requiring VAT invoices per BIR RR 2-2013. This is a legal/tax decision that must be made BEFORE G-046 (Hub Transfer Approval) can be built.
**Fix:** Decision required: Is BKI on the same Frappe instance as BEI? If separate companies: use inter-company transaction flow. If same company: document formally and add transfer price field.

#### BLOCKER 7: RBAC Role Names Don't Match `lib/roles.ts`
**Source:** `frontend_findings.md` C-05 | **Severity:** CRITICAL
**Problem:** Plan references `SCM_DISPATCH_ROLES` with "Warehouse Manager" and "Logistics Coordinator" — neither exists in `bei-tasks/lib/roles.ts`. The `Driver` role exists but has no pages assigned. Frontend RBAC will fail on day 1.
**Fix:** Align all role names with existing `lib/roles.ts` definitions before any frontend work. Add new roles to both Frappe and bei-tasks if needed.

#### BLOCKER 8: `billing_type = "Credit Note"` Not in DocType Options
**Source:** `frappe_backend_findings.md` C4 | **Severity:** CRITICAL
**Problem:** `BEI Billing Schedule` only has `Monthly Fees` and `Delivery` as billing_type options. Setting `"Credit Note"` will fail Frappe's Select field validation. Task 2B cannot work without a schema change.
**Fix:** Add `Credit Note` to billing_type options in `bei_billing_schedule.json` + `bench migrate`.

#### BLOCKER 9: 0% Test Coverage at L3+L4 Level (vs 70% Minimum)
**Source:** `deployment_qa_findings.md` | **Severity:** CRITICAL
**Problem:** All 28 verification items in the plan are at L1/L2 level (existence checks, manual verification). Zero L3 (browser API) or L4 (API+DB verify) tests specified. Quality score = 0%. Phase 4 has zero test cases at any level.
**Fix:** Write L3/L4 test cases for all 28 verification items. See deployment_qa_findings.md for the complete test gap analysis with specific test IDs and recommended levels.

#### BLOCKER 10: No Rollback Plan + No Migration Runbook
**Source:** `deployment_qa_findings.md` D-04, D-05 | **Severity:** CRITICAL
**Problem:** No git tag before deploy, no previous Docker image reference, no DB snapshot step, no Frappe Customize Form revert procedure. No migration ordering documented. Unverified claims about field existence.
**Fix:** Add: (1) `git tag pre-scm-sprint-<date>`, (2) document previous Docker image tag, (3) numbered migration checklist with field existence verification, (4) Vercel cache-bust step per `.claude/rules/deployment.md`.

### Additional Recommendations (Non-Blocking)

1. ~~**Split commissary.py**~~ → **PROMOTED to P0-11** (v1.3)
2. ~~**Centralize RBAC role sets**~~ → **PROMOTED to P0-10** (v1.3)
3. ~~**Fix N+1 queries**~~ → **PROMOTED to P0-12** (v1.3)
4. ~~**Add TanStack Query hooks + Zod validation schemas**~~ → **PROMOTED to Phase 2 Day 4 prerequisite** (v1.3)
5. ~~**Define dashboard refresh strategy**~~ → **PROMOTED to Phase 2 Day 4 prerequisite** (v1.3)
6. **Add optimistic updates** for driver-facing mutations (`frontend_findings.md` C-03): Mobile connectivity requires immediate UI feedback
7. **Fix `dispatch_date` → `trip_date`** field name (`frappe_backend_findings.md` C7): Route data always returns empty
8. **Fix `approve_order` → `generate_dr` permission conflict** (`frappe_backend_findings.md` C6): Area Supervisors cannot approve orders
9. **Add Google Chat circuit breaker** (`design_review_findings.md` W-3): Prevent Chat outage from cascading into delivery pipeline latency
10. **Promote deferred G-069 (race condition), G-100 (idempotency), G-102 (transaction isolation)** from "debt" to "bugs" (`design_review_findings.md` C-2): These produce corrupted data under concurrent load
11. **Foul trip fee accounting** (P29K-63K/month untracked) — needs EWT + GL treatment (`ph_finance_findings.md` C3)
12. **Franchise royalty computation basis** — must exclude SC/PWD discounts from base (`ph_finance_findings.md` C4)
13. **Cold storage cost capitalization decision** — P814K/month affects COGS (`ph_finance_findings.md` W3)
14. **Driver test account needed** — no Driver role in canonical test accounts (`frontend_findings.md` I-05)
15. **Store→Chat space mapping must be 100% complete** before `confirm_delivery` deploys (`deployment_qa_findings.md` C-06)

### Pre-Flight Checks: Audit Additions

- [ ] **AUDIT-1:** `picking.py:confirm_loaded()` changed from Material Issue to Material Transfer with correct warehouses
- [ ] **AUDIT-2:** BEI Store Order status options include `Ready for Dispatch` and `Partially Fulfilled` (or code updated to use existing values)
- [ ] **AUDIT-3:** `warehouse.py:approve_material_request()` actually updates MR status (not just adds comment)
- [ ] **AUDIT-4:** EWT computation logic added to 3PL reconciliation flow before G-122 goes live
- [ ] **AUDIT-5:** Credit note path includes GL Journal Entry with party fields (DM-1) and savepoint (DM-2)
- [ ] **AUDIT-6:** BKI ↔ BEI inter-company transfer decision documented (same company in Frappe? or intercompany invoicing?)
- [ ] **AUDIT-7:** All RBAC role names aligned with `bei-tasks/lib/roles.ts` — new roles added to both Frappe and bei-tasks
- [ ] **AUDIT-8:** `BEI Billing Schedule.billing_type` includes `Credit Note` option
- [ ] **AUDIT-9:** L3/L4 test cases written for all 28 verification items (quality score >= 70%)
- [ ] **AUDIT-10:** Git tag created pre-deploy, migration runbook documented, rollback procedure specified

### GO / NO-GO Gate (Updated)

**v1.3 STATUS: GO** — All 10 original blockers resolved (v1.2). Re-audit found 7 new issues, all fixed in v1.3:
- v1.3-FIX-1: Credit note JV party fields corrected (party ONLY on AR row, not revenue rows)
- v1.3-FIX-2: Credit note JV expanded to all 4 fee accounts (4000301-4000304) with pro-rata formula
- v1.3-FIX-3: EWT ATC corrected from WI100 (professional fees) to WC110 (corporate carriers, 1%)
- v1.3-FIX-4: EWT JV party fields corrected (party ONLY on AP row, not EWT Payable row)
- v1.3-FIX-5: G-069 changed from SELECT COUNT (race-vulnerable) to UNIQUE constraint + correct function target
- v1.3-FIX-6: G-100/G-102 implementation guidance expanded with specific endpoints and pattern distinction
- v1.3-FIX-7: P0-1 data model resolved (one SE per stop, add store field to Pick List Item)
- v1.3-FIX-8: dispatch.py:422 rollback method fix specified (rollback_to_savepoint → rollback with save_point=)
- v1.3-FIX-9: test.driver@bebang.ph added to Test Accounts table
- v1.3-FIX-10: EWT rate source precedence specified (DocType field wins over module constant)
- v1.3-PROMOTED-1: commissary.py split (P0-11) — merge conflicts prevention
- v1.3-PROMOTED-2: RBAC centralization (P0-10) — backend role set DRY
- v1.3-PROMOTED-3: N+1 query fix (P0-12) — 400+ queries → 2 JOINs
- v1.3-PROMOTED-4: TanStack/Zod/CORS proxy (Phase 2 Day 4 prereq) — frontend foundation
- v1.3-PROMOTED-5: Refresh strategy (Phase 2 Day 4 prereq) — per-page polling config

**Pre-flight checks AUDIT-1 through AUDIT-10 above must still be verified during execution.**

### Version History

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | 2026-02-19 | Initial draft |
| v1.1 | 2026-02-19 | 6-domain audit: 37 CRITICAL, 62 WARNING, 27 INFO findings. 10 blockers identified. NO-GO until resolved. |
| v1.2 | 2026-02-19 | All 10 blockers resolved inline. Phase 0 added (9 pre-sprint bug fixes). Task 2B rewritten with GL JE (DM-1/DM-2). G-122 expanded with EWT/Form 2307. G-046 gated on BKI decision. RBAC alignment task added. Verification checklist upgraded to 45 L3/L4 tests. Rollback plan + migration runbook added. G-069/G-100/G-102 promoted from deferred to Phase 1. Status: APPROVED — GO. |
| v1.3 | 2026-02-19 | Re-audit (6 agents). 10 fixes + 5 promotions from recommendations to tasks. Fixes: (1) Credit note party ONLY on AR row. (2) Credit note expanded to 4 fee accounts with pro-rata formula. (3) EWT ATC WI100→WC110 (1%). (4) EWT JV party ONLY on AP row. (5) G-069 UNIQUE constraint. (6) G-100 endpoints enumerated. (7) G-102 pattern distinction. (8) P0-1 one-SE-per-stop. (9) dispatch.py:422 rollback fix. (10) test.driver added. Promotions: P0-10 (RBAC centralization), P0-11 (commissary.py split), P0-12 (N+1 fix), Phase 2 Day 4 prereq (TanStack/Zod/CORS/refresh). |
