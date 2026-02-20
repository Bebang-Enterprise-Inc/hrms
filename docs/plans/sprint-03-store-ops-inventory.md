# Store Ops + Inventory Sprint Plan
**Date:** 2026-02-19
**Status:** COMPLETE — all tasks implemented, code reviewed, warnings fixed (v3.0)
**Version:** v3.0 (sprint executed, code reviewed + simplified, 2026-02-20)
**Priority:** Dept 3 (third priority in Master Gap Closure Roadmap)
**Parent:** `docs/plans/2026-02-19-master-gap-closure-roadmap.md`

---

## Executive Summary

Store Ops core is **98% live**. The daily cycle (open → midshift → close → POS upload → bank deposit) is fully functional. The two critical gaps are:

1. **G-004/G-120** — POS upload date mismatch goes silently unblocked. Backend already returns `date_mismatch: true` but frontend does NOT block or alert. Stores submitting yesterday's files as today's silently corrupt Supabase P&L data.
2. **G-013** — Store ordering has **no backend API**. 45 stores order from commissary daily via WhatsApp/Google Chat. No audit trail, no demand aggregation, no Area Supervisor controls.

**Key discovery (resolved):** `ordering.py` previously had duplicate implementations. As of v1.2, all 4 duplicate functions (`submit_order`, `get_orderable_items`, `validate_order_schedule`, `approve_order`) in `ordering.py` are deprecated redirects to the canonical `store.py` implementations. Only `get_order_review_queue`, `reject_order`, `generate_dr`, and `_send_order_notification` remain as unique functions in `ordering.py`.

**Total effort estimate:** 2-3 weeks (backend + frontend)

---

## Business Context

| Fact | Value |
|------|-------|
| Stores | 45 (Metro Manila + provinces) |
| Daily cycle | Open → Sell → Close → POS Upload → Bank Deposit |
| Store ops completion | 98% live (daily cycle fully functional) |
| POS data impact | Supabase sales views + monthly P&L + franchise billing |
| Current ordering channel | WhatsApp/Google Chat to commissary (no audit trail) |
| Ordering cutoff | 11:59 AM (configurable via BEI Settings.order_cutoff_hour) |
| Order approval | Area Supervisor must approve before commissary picks |
| Variance records | 200+ accumulating at "Open" with no resolution path |
| Cycle counting | COMPLETE and in production (G-118 resolved) |
| POS date mismatch | Silent data corruption risk — known active bug (G-120) |

**Key people:**
- **Store Staff / Store OIC** — submits daily closing reports, POS uploads, orders
- **Area Supervisor** — approves store orders, approves cycle counts
- **Finance (Alyssa Dimaano)** — reconciles POS data, reviews variance write-offs

---

## Technology Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Backend | Frappe Framework (Python) | All APIs in `hrms/api/` |
| Employee App (my.bebang.ph) | React + Next.js 16 + Shadcn UI + Tailwind v4 | Separate repo: `bei-tasks` |
| Legacy PWA | Ionic 7 + Vue 3 | `frontend/src/views/store_ops/` — has existing ordering pages |
| Database | MariaDB (Docker container) | NOT AWS RDS |
| Notifications | Google Chat via service account | `hrms/api/google_chat.py` |
| Deployment | Docker → AWS EC2 via GitHub Actions | `.github/workflows/build-and-deploy.yml` |

---

## Source Files Map

Every file an implementing agent needs to know about:

### Backend API Files

| File | Lines | Role | Key Functions |
|------|-------|------|---------------|
| `hrms/api/store.py` | ~2100 | Store Ops: POS upload, closing, receiving, ordering | `upload_pos_data` (L1092), `submit_order` (L330), `approve_order` (L433), `complete_receiving` (L556), `submit_closing_stage3_photos` (L1650), `get_order_history` (L406) |
| `hrms/api/ordering.py` | ~525 | Store Ordering workflow (earlier version) | `get_orderable_items` (L70), `validate_order_schedule` (L133), `submit_order` (L169), `approve_order` (L407), `reject_order` (L456), `get_order_review_queue` (L352), `generate_dr` (L267) |
| `hrms/api/inventory.py` | ~1300 | Cycle Count, Variance, Shelf Life | `submit_cycle_count` (L17), `approve_cycle_count` (L176), `get_variances` (L339), `start_variance_investigation` (L1243), `resolve_variance` (L1264), `report_variance` (L285) |
| `hrms/utils/bei_config.py` | — | Central config | `get_company()`, `get_chat_space()`, `SPACE_NOTIFICATIONS` |
| `hrms/api/google_chat.py` | — | Google Chat notifications | `send_message_to_space(space_name, message) -> bool` — never throws |

### DocTypes

| DocType | Directory | Purpose |
|---------|-----------|---------|
| `BEI POS Upload` | `hrms/hr/doctype/bei_pos_upload/` | POS file uploads with date validation |
| `BEI Store Order` | `hrms/hr/doctype/bei_store_order/` | Store ordering |
| `BEI Store Order Item` | `hrms/hr/doctype/bei_store_order_item/` | Child table for order items |
| `BEI Approval Queue` | `hrms/hr/doctype/bei_approval_queue/` | Area Supervisor approval queue |
| `BEI Store Closing Report` | `hrms/hr/doctype/bei_store_closing_report/` | Daily closing — has `pos_upload` link field |
| `BEI Store Receiving` | `hrms/hr/doctype/bei_store_receiving/` | Receiving with 5 quality checks per item |
| `BEI Store Receiving Item` | — | Child: check_condition, check_packaging, check_expiry, check_temperature, check_food_quality |
| `BEI Inventory Variance` | `hrms/hr/doctype/bei_inventory_variance/` | Variance tracking — status: Open/Investigating/Resolved |
| `BEI Cycle Count` | `hrms/hr/doctype/bei_cycle_count/` | Cycle count — status: Submitted/Verified |

### Existing Frontend (Legacy Vue/Ionic PWA — `frontend/`)

Located in `frontend/src/views/store_ops/`:
- `Ordering.vue` — Order list + cutoff warning (EXISTS, calls `get_order_history` and shows orders)
- `OrderForm.vue` — Order creation form (EXISTS, calls `get_orderable_items`)
- `OrderDetail.vue` — Order detail view (EXISTS)
- `Receiving.vue` — Receiving queue (EXISTS)
- `ReceivingForm.vue` — Receiving form with 4 of 5 quality checks (MISSING: `check_food_quality`)
- `FQIList.vue` — FQI list (EXISTS)
- `FQIForm.vue` — FQI form (EXISTS)

**Note:** The legacy Vue/Ionic PWA in `frontend/` is what store staff currently use for store-ops flows. New pages for the Area Supervisor approval UI should go in the `bei-tasks` React/Next.js app (my.bebang.ph).

### RBAC Roles (from code)

```python
# store.py line 82-85
STORE_OPS_ALLOWED_ROLES = [
    "Store Staff", "Store Supervisor", "Area Supervisor",
    "System Manager", "Administrator"
]

# ordering.py line 15-17
ORDERING_STORE_ROLES = {"Store Staff", "Store Supervisor", "Store OIC", "System Manager"}
ORDERING_WAREHOUSE_ROLES = {"HR Manager", "Warehouse User", "System Manager"}
ORDERING_APPROVAL_ROLES = {"Area Supervisor", "HR Manager", "Warehouse User", "System Manager"}
```

---

## MUST-HAVE Gaps (2 items)

### Gap G-004/G-120: POS Upload Date Mismatch Not Shown to User

**Problem:** `upload_pos_data()` in `hrms/api/store.py:1092` already detects date mismatches:

```python
# store.py:1139-1181
if file_date and str(file_date) != str(pos_date):
    date_mismatch_warning = _(
        "Warning: POS file date ({0}) does not match claimed date ({1}). "
        "Please verify the correct date before submitting."
    ).format(file_date, pos_date)
    frappe.log_error(...)

# ...on return:
if date_mismatch_warning:
    result["warning"] = date_mismatch_warning
    result["date_mismatch"] = True
return result
```

The backend logs the mismatch AND returns `{"date_mismatch": True, "warning": "..."}` in the response. However, the frontend POS upload page does **NOT** inspect `result.date_mismatch` before completing. The upload proceeds silently even when there is a date mismatch.

**Impact:** Wrong date POS data → wrong Supabase sync → wrong P&L → wrong franchise billing. At 45 stores × 30 days = 1,350 uploads/month. Even a 1% error rate = 13 corrupted records/month that Finance must fix manually.

**Fix (2 tasks):**

**Task A-1: Add 'Cancel Upload' button to existing POS date mismatch modal** (1-2 hours)

Add a "Cancel Upload" button to the existing POS date mismatch modal in `bei-tasks/app/dashboard/store-ops/pos/page.tsx`. The modal already shows the warning — add a cancel path that either deletes the already-inserted doc or uses a `dry_run` param. Also need backend `cancel_pos_upload` endpoint or `dry_run` support.

**File to modify:** `bei-tasks/app/dashboard/store-ops/pos/page.tsx` — the modal component already exists. Do NOT rebuild from scratch.

**Alternative if delete is complex:** Change backend to accept a two-phase flow:
- Phase 1: `upload_pos_data(..., dry_run=True)` — validates and parses but does NOT insert. Returns `date_mismatch` warning.
- Phase 2: User confirms → `upload_pos_data(..., dry_run=False)` — actually inserts.

The two-phase approach is cleaner but requires backend change. The cancel button addition is simpler and unblocks immediately.

**Task A-2: Backend hardening — add `skip_date_validation` gate** (1 hour)

Current: `upload_pos_data` at `store.py:1121` accepts `skip_date_validation=False`. When `True`, it bypasses validation entirely.

Change: When `date_mismatch=True` and `skip_date_validation=False`, set `doc.has_date_mismatch = 1` (if field exists on DocType) so Finance can filter/flag in their reconciliation view.

```python
# After insert, before returning result:
if date_mismatch_warning:
    result["warning"] = date_mismatch_warning
    result["date_mismatch"] = True
    # Tag the document for Finance reconciliation
    frappe.db.set_value("BEI POS Upload", doc.name, "has_date_mismatch", 1)
```

**Verify first:** Check if `has_date_mismatch` field exists on `BEI POS Upload` DocType JSON. If not, add it via Frappe Customize Form (select field, default 0).

**Effort:** 1 day (frontend modal + backend tagging)
**Test:**
- Submit POS upload with yesterday's files for today's date
- Verify `result.date_mismatch = true` in API response
- Verify frontend shows blocking confirmation modal
- Verify "Cancel" stops upload
- Verify "Confirm" completes upload and `has_date_mismatch = 1` on the saved doc

---

### Gap G-013: Store Ordering Has No Backend API

**Problem:** The research notes say "frontend page exists, no backend API." However, the actual code shows the ordering backend IS partially implemented across two files:

- `hrms/api/store.py:330` — `submit_order()` — **EXISTS and works**. Creates `BEI Store Order`, sets `status = "Pending Approval"`, creates `BEI Approval Queue` entry for area supervisor. This is the canonical implementation.
- `hrms/api/store.py:433` — `approve_order()` — **EXISTS**. Area Supervisor approves, creates Material Request via `_create_mr_for_store_order()`.
- `hrms/api/ordering.py:169` — `submit_order()` — **DUPLICATE/OLDER VERSION**. Creates `BEI Store Order` differently (with `cargo_category`, `is_bulk_order`, etc.). Less robust than `store.py` version.
- `hrms/api/ordering.py:407` — `approve_order()` — **DUPLICATE**. Different from `store.py:433`.

**Root cause:** The `frontend/src/views/store_ops/OrderForm.vue` calls `get_orderable_items` from `store.py:215`, but the **submit call** may be pointed at the wrong endpoint or not wired at all. The `Ordering.vue` only calls `get_order_history` — it does not show or submit to the approval queue.

**The real gaps are:**
1. **Frontend `OrderForm.vue` does not call `store.submit_order()`** — needs to be wired
2. **No Area Supervisor approval UI in my.bebang.ph** — `bei_approval_queue` entries created but Area Supervisor has no page to view/approve them
3. **`store.py:approve_order()` creates MR but `MR.items` may be empty** — `store_warehouse` field extraction at line 495 has a bug (reads `order.warehouse` or `order.store_warehouse` which don't exist on `BEI Store Order`; the correct field is `order.store`)

**Fix (5 tasks):**

**Task B-1: Verify `cargo_category` is passed by existing React ordering page to `store.submit_order()`** (1 hour)

Verify the existing React ordering page at `/dashboard/store-ops/ordering/` correctly passes `cargo_category` parameter to `store.submit_order()` after BLOCKER 4 fix. Update `useSubmitOrder()` hook to include `cargo_category` in the payload. Vue `OrderForm.vue` is legacy — no changes needed (it already calls `store.submit_order` at line 170).

**Task B-2: Fix `_create_mr_for_store_order()` warehouse extraction bug** (1 hour)

- File: `hrms/api/store.py`
- Lines 477-524: `_create_mr_for_store_order()` at line 495 reads:
  ```python
  store_warehouse = getattr(order, "warehouse", None) or getattr(order, "store_warehouse", None)
  ```
  Neither `warehouse` nor `store_warehouse` exist on `BEI Store Order`. The correct field is `order.store`.
- Fix:
  ```python
  store_warehouse = order.store  # BEI Store Order.store = the store warehouse
  ```
- Then verify this field is set as `warehouse` on MR items (line 502).

**Task B-3: Build Area Supervisor order approval page in bei-tasks** (2-3 days)

New page: `/dashboard/store-ops/order-approvals`

- **APIs consumed:**
  - `store.get_orderable_items(store)` — view items in an order
  - `ordering.get_order_review_queue(date, status)` at `ordering.py:352` — get orders needing approval
  - `store.approve_order(order_name, approved_quantities)` at `store.py:433` — approve with qty adjustments
  - `ordering.reject_order(order_name, reason)` at `ordering.py:456` — reject with reason
- **UI requirements:**
  - Accessible by Area Supervisor role only (check `is_multi_store: true` from `get_user_store()`)
  - Order queue: list of orders with `status = "Pending Approval"`, grouped by store
  - Order detail: item table with editable `qty_approved` (defaults to `qty_requested`)
  - Approve button: calls `approve_order`, shows Material Request name on success
  - Reject button: requires `reason` text input, calls `reject_order`
  - Filter by date (today default) and store
  - Show `is_emergency` badge for emergency orders
- **RBAC:** `ORDERING_APPROVAL_ROLES` — Area Supervisor, HR Manager, Warehouse User, System Manager

**Task B-4: Add Google Chat notification when order is submitted** (1 hour)

- File: `hrms/api/store.py`
- After `order.insert()` at line 375, add notification to area supervisor:
  ```python
  try:
      from hrms.api.google_chat import send_message_to_space
      from hrms.utils.bei_config import get_chat_space, SPACE_NOTIFICATIONS
      space = get_chat_space(SPACE_NOTIFICATIONS)
      msg = f"New store order {order.name} from {warehouse} — {len(items)} items. Review: my.bebang.ph/dashboard/store-ops/order-approvals"
      send_message_to_space(space, msg)
  except Exception as e:
      frappe.log_error(f"GChat notification failed for order {order.name}: {e}", "Store Ordering")
  ```
- Must be wrapped in try/except — notification failure must never block order creation

**Task B-5: Add Google Chat notification when order is approved or rejected** (1 hour)

- File: `hrms/api/store.py`
- In `approve_order()` at line 433, after `order.save()`:
  ```python
  try:
      _send_order_approval_notification(order, "approved")
  except Exception as e:
      frappe.log_error(f"GChat notification failed for approved order {order.name}: {e}", "Store Ordering")
  ```
- In `ordering.reject_order()` at `ordering.py:456`, the notification to store is already wired via `_send_order_notification`. Verify it fires.

**Effort:** 3-4 days (B-2 is 1 hour; B-1+B-4+B-5 are 1 day; B-3 is 2-3 days)
**Test:**
- Submit an order via `OrderForm.vue` as `test.staff@bebang.ph` → verify `BEI Store Order` created with status "Pending Approval"
- Verify `BEI Approval Queue` entry created with `assigned_approver = test.area@bebang.ph`
- Login as `test.area@bebang.ph` → navigate to `/dashboard/store-ops/order-approvals` → approve order
- Verify Material Request created after approval (not empty items)
- Verify rejection workflow: reject order → store staff sees "Cancelled" status
- Verify GChat notification fires on submit (does not block if GChat fails)

---

## SHOULD-HAVE Gaps (7 items)

### Gap G-009: Area Supervisor Order Approval UI

**Note:** This is covered by Task B-3 above (G-013 fix). They must be built in the same sprint. The approval UI becomes the Area Supervisor page at `/dashboard/store-ops/order-approvals`.

**APIs:**
- `ordering.get_order_review_queue(date, status)` — `ordering.py:352`
- `store.approve_order(order_name, approved_quantities)` — `store.py:433`
- `ordering.reject_order(order_name, reason)` — `ordering.py:456`

**Effort:** Bundled with G-013 Task B-3 (no additional effort)

---

### Gap G-010: Receiving Completion Form Fix

**Problem:** `frontend/src/views/store_ops/ReceivingForm.vue` shows only 4 of 5 quality checks. The `check_food_quality` checkbox is missing from the template (lines 48-61 show: condition, packaging, expiry, temperature — no food quality).

**Fix (2 tasks):**

**Task C-1: Add `check_food_quality` to ReceivingForm.vue** (1 hour)

- File: `frontend/src/views/store_ops/ReceivingForm.vue`
- After the `check_temperature` checkbox block (currently line ~58-61), add:
  ```html
  <ion-checkbox v-model="item.check_food_quality" label-placement="end">
      Food Quality OK
  </ion-checkbox>
  ```
- Verify `complete_receiving()` at `store.py:556` already handles this field: line 589 includes `"check_food_quality": item_data.get("check_food_quality", 0)` — it does. No backend change needed.

**Task C-2: Verify submit button calls `complete_receiving()`** (30 min)

- File: `frontend/src/views/store_ops/ReceivingForm.vue`
- Check the submit handler — verify it calls `hrms.api.store.complete_receiving` with all 5 checks
- If not wired: add the call with `{store, trip, items, receiver_1_signature, receiver_2_signature, driver_signature}`

**Effort:** 1-2 hours total
**Test:** Receive a delivery via the form, verify all 5 quality checks are saved on `BEI Store Receiving Item`

---

### Gap G-090: Closing Report → POS Upload Auto-Link

**Problem:** `BEI Store Closing Report` has a `pos_upload` Link field (visible in `get_closing_report_status()` return at `store.py:1757`). However, Stage 3 submission (`submit_closing_stage3_photos` at `store.py:1650`) does NOT auto-link today's POS upload. Finance must manually match closing reports to POS uploads.

At 45 stores × 30 days = 1,350 records/month, this is real overhead.

**Fix (1 task):**

**Task D-1: Auto-link POS upload in Stage 3 submission** (2-3 hours)

- File: `hrms/api/store.py`
- In `submit_closing_stage3_photos()` at line 1650, before `doc.save()` at line 1732:
  ```python
  # Auto-link today's POS upload if not already set
  if not doc.pos_upload:
      today_upload = frappe.db.get_value(
          "BEI POS Upload",
          {"store": doc.store, "pos_date": doc.report_date},
          "name"
      )
      if today_upload:
          doc.pos_upload = today_upload
  ```
- Verify that `BEI Store Closing Report` has `report_date` field (check DocType JSON)
- If `report_date` field does not exist, use `doc.name` to extract date (closing reports are named with dates, e.g., `BEI-CLR-2026-02-19-STORE`)

**Effort:** 2-3 hours
**Test:** Submit Stage 3 closing, verify `BEI Store Closing Report.pos_upload` is set to today's POS upload

---

### Gap G-038: Variance Investigation Workflow (Open→Investigating→Resolved)

**Problem:** Backend APIs exist:
- `start_variance_investigation(variance_name)` at `inventory.py:1243` — transitions Open→Investigating
- `resolve_variance(variance_name, resolution_type, resolution_notes, adjustment_qty)` at `inventory.py:1264` — transitions to Resolved with optional Stock Entry (Write-Off) or Stock Reconciliation

But the variance list page (if it exists) has no action buttons for these transitions. 200+ variance records are stuck at "Open" with no resolution path.

**Fix (2 tasks):**

**Task E-1: Verify variance list page exists and add action buttons** (1-2 days)

Search `bei-tasks` repo for variance-related pages: `grep -r "variance" ../bei-tasks/src/ --include="*.tsx"`.

If the variance list page EXISTS:
- Add "Start Investigation" button on Open variance rows → calls `inventory.start_variance_investigation(name)`
- Add "Resolve" button on Open/Investigating rows → opens resolution modal

If NO variance page exists:
- Build `/dashboard/inventory/variances` page with:
  - Variance list with filters: store, status (Open/Investigating/Resolved), date range
  - "Start Investigation" action on Open rows
  - "Resolve" action: modal with `resolution_type` select (Write-Off/Recount Corrected/Theft/Damage/System Error), `resolution_notes` textarea, optional `adjustment_qty`
  - Color coding: Open=red, Investigating=yellow, Resolved=green

**Task E-2: Resolve modal — integrate Stock Entry confirmation** (bundled)

When `resolution_type = "Write-Off"`:
- `resolve_variance()` at `inventory.py:1299` creates a `Material Issue` Stock Entry
- Response includes `stock_entry` name
- Frontend shows: "Write-off Stock Entry {name} created. Inventory adjusted."

**Effort:** 2-3 days
**Test:** Report a variance, start investigation, resolve as Write-Off, verify Stock Entry created, verify variance status = Resolved

---

### Gap G-035: Cycle Count Reconciliation API

**Problem:** Cycle counts end at status "Verified" after `approve_cycle_count()` at `inventory.py:176`. There is no `mark_cycle_count_reconciled()` API to transition to a "Reconciled" terminal state that confirms the variance has been written off in GL.

**Fix (1 task):**

**Task F-1: Add `mark_cycle_count_reconciled()` endpoint** (1 day)

- File: `hrms/api/inventory.py`
- Add new endpoint after `approve_cycle_count()`:
  ```python
  @frappe.whitelist()
  def mark_cycle_count_reconciled(count_name, stock_reconciliation_name=None, notes=None):
      """Mark a Verified cycle count as Reconciled.

      Args:
          count_name: BEI Cycle Count name
          stock_reconciliation_name: Optional Stock Reconciliation created for this count
          notes: Optional notes on how variances were reconciled

      Returns:
          dict: {success, name, status}
      """
      allowed_roles = ["Area Supervisor", "Store Supervisor", "System Manager"]
      if not any(r in frappe.get_roles(frappe.session.user) for r in allowed_roles):
          frappe.throw(_("Not authorized to reconcile cycle counts"), frappe.PermissionError)

      doc = frappe.get_doc("BEI Cycle Count", count_name)

      if doc.status != "Verified":
          frappe.throw(_("Only Verified cycle counts can be marked as Reconciled"))

      doc.status = "Reconciled"
      if stock_reconciliation_name:
          doc.stock_reconciliation = stock_reconciliation_name  # Verify field exists
      if notes:
          doc.reconciliation_notes = notes  # Verify field exists
      doc.save(ignore_permissions=True)

      return {"success": True, "name": count_name, "status": "Reconciled"}
  ```
- **Verify first:** Check `BEI Cycle Count` DocType JSON for existing fields. If `stock_reconciliation` or `reconciliation_notes` fields don't exist, add via Frappe Customize Form.
- Add "Mark Reconciled" button to cycle count detail view in frontend (small scope)

**Effort:** 1 day (backend + minimal frontend)
**Test:** Approve a cycle count, click "Mark Reconciled", verify status = "Reconciled"

---

### Gap G-089: Receiving Quality Checks Completeness

**Problem:** `ReceivingForm.vue` shows 4 of 5 quality checks (missing `check_food_quality`). This is the same issue as G-010 Task C-1 above.

**Status:** COVERED by Task C-1. No additional work needed.

---

### Gap G-091: Photo Upload E2E Test

**Problem:** Photo upload pipeline (frontend camera → base64 → `save_base64_image()` → File DocType) is complex and has failure modes. Cycle counting is L3-tested but photo upload is called out as untested in `inventory.md`.

**Fix (1 task):**

**Task G-1: Add E2E photo upload test scenario** (0.5 day)

- File: `docs/testing/TEST_SCENARIOS.md`
- Add scenario: "Variance Report with Photo Evidence"
  - Steps: Login as `test.staff@bebang.ph`, submit variance with 150KB+ real JPEG photo
  - Assert: `result.success = true`, `doc.photo_evidence` is a `/files/` URL (not base64)
  - Assert: File DocType record exists with `attached_to_doctype = "BEI Inventory Variance"`
  - Verify file is publicly accessible (HTTP 200 on the URL)
- Add scenario: "Cycle Count with Photo"
  - Use existing cycle count submission but add `photo_evidence` field
  - Assert: photo saved correctly via `save_base64_image()` in `store.py:18`

**Effort:** 0.5 day (test scenario writing + one run)

---

## Rollback Plan

### Pre-Sprint
- [ ] Tag current Docker image before sprint: `docker tag bei-hrms:latest bei-hrms:pre-sprint-03`
- [ ] Record current `bench version` output for all apps
- [ ] Backup MariaDB: `mysqldump --all-databases > pre_sprint_03_backup.sql`

### Phase 1 Rollback (Backend fixes)
If backend deployment fails after Phase 1:
1. Revert to tagged Docker image: `docker tag bei-hrms:pre-sprint-03 bei-hrms:latest`
2. Redeploy: `docker compose up -d`
3. Run `bench migrate` (reverts to pre-sprint schema)
4. Customize Form field additions (`has_date_mismatch`) can be removed manually via Frappe Desk → Customize Form → BEI POS Upload → delete the field

### Phase 2-4 Rollback (Frontend)
If Vercel deployment fails:
1. Revert via Vercel dashboard → Deployments → select last working deployment → Promote to Production
2. Or: `git revert HEAD && vercel.cmd --prod --force`

### Test Data Cleanup
If sprint is abandoned mid-execution:
- Delete test Stock Entries: `frappe.db.sql("DELETE FROM tabStock Entry WHERE owner LIKE 'test.%' AND creation > '2026-02-20'")`
- Delete test Material Requests: same pattern
- Delete test BEI Store Orders: same pattern
- Do NOT delete BEI Cycle Count or BEI Inventory Variance records (these are operational data)

---

## Sprint Execution Order

### Phase 1: Quick Backend Fixes (Week 1, Days 1-3)

| Day | Gap | Task | Owner | Depends On |
|-----|-----|------|-------|------------|
| 1 | G-004/G-120 | Task A-2: Backend date mismatch tagging | Backend | — |
| 1 | G-013 | Task B-2: Fix `_create_mr_for_store_order()` warehouse bug | Backend | — |
| 1 | G-090 | Task D-1: Auto-link POS upload in Stage 3 | Backend | — |
| 2 | G-035 | Task F-1: Add `mark_cycle_count_reconciled()` endpoint | Backend | — |
| 2 | G-013 | Task B-4: Add GChat notification on order submit | Backend | B-2 |
| 2 | G-013 | Task B-5: Add GChat notification on approve/reject | Backend | — |
| 3 | G-038 | Task E-2: Verify variance resolution creates correct Stock Entry | Backend | — |

**Deploy backend after Phase 1** — Full Docker build + migrate required (new code/endpoints).

### Phase 2: Frontend Quick Wins (Week 1, Days 2-4)

| Day | Gap | Task | Owner | Notes |
|-----|-----|------|-------|-------|
| 2-3 | G-004/G-120 | Task A-1: Date mismatch modal in POS upload | Frontend | bei-tasks repo |
| 3 | G-010 | Task C-1: Add `check_food_quality` to ReceivingForm.vue | Frontend | frontend/ repo |
| 3 | G-010 | Task C-2: Verify submit calls `complete_receiving()` | Frontend | frontend/ repo |
| 4 | G-091 | Task G-1: Add E2E photo upload test scenarios | Testing | TEST_SCENARIOS.md |

### Phase 3: Area Supervisor Approval UI (Week 2, Days 5-9)

| Day | Gap | Task | Owner | Notes |
|-----|-----|------|-------|-------|
| 5-6 | G-013 | Task B-1: Verify `cargo_category` passed by React ordering page to `store.submit_order()` | Frontend | bei-tasks repo |
| 5-9 | G-013/G-009 | Task B-3: Area Supervisor approval page `/dashboard/store-ops/order-approvals` | Frontend | bei-tasks repo |

### Phase 4: Variance Resolution (Week 2-3, Days 8-13)

| Day | Gap | Task | Owner | Notes |
|-----|-----|------|-------|-------|
| 8-10 | G-038 | Task E-1: Build variance list page with action buttons | Full-stack | bei-tasks repo |
| 11-12 | G-035 | Add "Mark Reconciled" button to cycle count detail | Frontend | bei-tasks repo |
| 13 | All | Full integration test | QA | See Verification Checklist |

---

## Verification Checklist

Before marking this sprint as complete, verify ALL of the following:

### Backend Verifications

- [ ] `POST upload_pos_data` with date mismatch → returns `{"date_mismatch": true, "warning": "..."}`
- [ ] `BEI POS Upload` document has `has_date_mismatch = 1` when date mismatch occurs
- [ ] `store.submit_order(store, items)` creates `BEI Store Order` with `status = "Pending Approval"`
- [ ] `store.submit_order()` creates `BEI Approval Queue` entry with `assigned_approver = area_supervisor`
- [ ] `store.approve_order(order_name, approved_quantities)` → Material Request created with correct store warehouse
- [ ] Material Request items are NOT empty after approval (B-2 fix verified)
- [ ] `submit_closing_stage3_photos()` sets `BEI Store Closing Report.pos_upload` to today's POS upload
- [ ] `inventory.start_variance_investigation(name)` transitions status Open→Investigating
- [ ] `inventory.resolve_variance(name, "Write-Off", notes)` creates Material Issue Stock Entry
- [ ] `inventory.mark_cycle_count_reconciled(name)` transitions Verified→Reconciled
- [ ] GChat notification fires when order submitted (no block if GChat fails)
- [ ] GChat notification fires when order approved/rejected

### Frontend Verifications

- [ ] POS upload with date mismatch → blocking modal appears with both dates
- [ ] Modal "Cancel" → upload does NOT complete
- [ ] Modal "Confirm" → upload completes with `has_date_mismatch` flag
- [ ] `ReceivingForm.vue` shows all 5 quality checks including `check_food_quality`
- [ ] Receiving form submit calls `complete_receiving()` and saves all 5 checks
- [ ] `OrderForm.vue` submit calls `store.submit_order()` and shows success/error
- [ ] Area Supervisor order approval page loads at `/dashboard/store-ops/order-approvals`
- [ ] Approval page accessible only to Area Supervisor role (test with `test.area@bebang.ph`)
- [ ] Approve button adjusts quantities and shows Material Request name
- [ ] Reject button requires reason input and shows "Cancelled" status
- [ ] Variance list page shows Open/Investigating/Resolved with correct color coding
- [ ] "Start Investigation" button transitions Open→Investigating
- [ ] "Resolve" modal accepts all 5 resolution types
- [ ] "Write-Off" resolution shows created Stock Entry name
- [ ] Cycle count detail shows "Mark Reconciled" button (Verified counts only)

### Integration Verifications

- [ ] Full flow: Store submits order → GChat notification to area supervisor → Area Supervisor approves → Material Request created → warehouse picks
- [ ] Full flow: Store submits POS upload (wrong date) → modal appears → user confirms → POS upload saved with mismatch flag
- [ ] Full flow: Closing Stage 3 submitted → `pos_upload` field auto-linked
- [ ] Full flow: Variance reported → Start Investigation → Resolve (Write-Off) → Stock Entry created → status = Resolved
- [ ] Full flow: Cycle count submitted → approved → Mark Reconciled → status = Reconciled

---

## Deployment Notes

### Backend Deployment

- **All backend changes require a FULL Docker build** (`skip_build=false`, `no_cache=true`)
- Build takes 5-10 minutes, migrations 1-2 minutes after
- Workflow: `.github/workflows/build-and-deploy.yml`
- Test with real user session before deploying (not API token — see Memory #9)
- Phase 1 backend fixes can be deployed together before frontend work begins

### Frontend Deployment

- **Legacy PWA changes** (`frontend/` repo): ReceivingForm.vue, OrderForm.vue changes → build with `yarn build-pwa` in `frontend/`, deploy as usual
- **my.bebang.ph changes** (`bei-tasks` repo): POS upload modal, Area Supervisor approval page, variance pages → deploy: `vercel.cmd --prod --force --token $TOKEN --scope team_xvK1nhuvsdZp3GNfd4uDJ0DW --yes`
- On Windows: use `vercel.cmd` not `vercel`

### Database Migrations

- Adding `has_date_mismatch` to `BEI POS Upload` — use Frappe Customize Form (no schema migration needed)
- `mark_cycle_count_reconciled()` may need `stock_reconciliation` and `reconciliation_notes` fields on `BEI Cycle Count` — verify first, add via Customize Form if missing
- `BEI Inventory Variance` status enum must include "Investigating" — verify in DocType JSON before deploying `start_variance_investigation()`

### Test Accounts

| Account | Email | Password | Role |
|---------|-------|----------|------|
| Store Staff | test.staff@bebang.ph | BeiTest2026! | Store OIC |
| Store Supervisor | test.supervisor@bebang.ph | BeiTest2026! | Store Supervisor |
| Area Supervisor | test.area@bebang.ph | BeiTest2026! | Area Supervisor |
| HR Officer | test.hr@bebang.ph | BeiTest2026! | HR Officer |

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| `BEI Store Order.store` vs `warehouse` field naming confusion | `_create_mr_for_store_order()` creates empty MR — commissary never sees order | Task B-2 is the critical fix. Verify field name before deploying. |
| Two `submit_order()` implementations in `store.py` and `ordering.py` | Frontend calls wrong endpoint | Standardize: frontend uses `hrms.api.store.submit_order`. Deprecate `ordering.submit_order` after verifying no frontend calls it. |
| `BEI Approval Queue` required fields | Order created but approval queue entry silently fails → Area Supervisor never notified | Code already handles this with try/except at `store.py:391`. Verify `assigned_approver` field name matches DocType. |
| GChat rate limits | Notifications dropped during high-order periods | Already handled — `send_message_to_space` never throws. Log errors only. |
| "Reconciled" status not in `BEI Cycle Count` enum | `mark_cycle_count_reconciled()` fails on save | Verify DocType JSON enum for `status` field before deploying. Add "Reconciled" if missing. |
| POS upload modal: delete-after-mismatch race condition | Upload already inserted, user cancels, doc left orphaned | Prefer two-phase dry_run approach for cleaner UX. Or: delete orphan if user cancels (call delete API). |
| Missing `check_food_quality` data for past receiving records | Historical receiving records are incomplete | Forward-only fix. Add note to receiving history: "Food quality check captured from [date]". |

---

## NICE-TO-HAVE (Deferred — Do Not Build This Sprint)

| Gap | What | Why Defer |
|-----|------|-----------|
| G-032 | Return Reasons DocType | Hardcoded list (damaged/wrong item/expired/overdelivered) is stable. No analytics needed yet. |
| G-033 | Inventory Spot Check Items | Orphaned DocType — superseded by cycle count module. Deprecate quietly. |
| G-034 | Store Audit Items | Orphaned DocType — superseded by Supervisor module store visit. Deprecate quietly. |
| G-036 | COS RECON Export Automation | Manual click (45/month) is acceptable. Add auto-export when Finance reports bottleneck. |
| G-037 | Low Stock Alerts (store level) | QSR uses commissary-push model. Stores don't pull based on stock levels. Build after G-013 stable. |
| G-039 | Expiring Batches (store level) | Shelf Life Extension workflow (LIVE) handles urgent cases reactively. |
| G-087 | Maintenance Verification standalone | Embedded-in-closing design is correct for QSR. No separate page needed. |
| G-088 | Delivery Trip Billing Admin UI | Finance handles billing. Store Ops staff don't need to see billing records. |

---

## Deferred Deprecation Cleanup

Two orphaned DocTypes should be deprecated (no code required — just documentation):

1. **`BEI Inventory Spot Check Item`** — superseded by `BEI Cycle Count`. No parent DocType, no API. Archive quietly.
2. **`BEI Store Audit Item`** — superseded by `BEI Store Visit Report` in Supervisor module. Archive quietly.

Action: Add to `NEXT_SPRINT_CLEANUP.md` for an engineer to `frappe.delete_doc_if_exists` on a migration patch.

---

*This plan is self-contained. An implementing agent should be able to execute it without additional context beyond reading the source files listed above.*

---

## Audit Amendments (v1.1) — 2026-02-20

### Audit Methodology

Six specialized agents audited this plan in parallel, each writing detailed findings to disk. Full reports with code fixes are in the referenced files — this section contains only the consolidated blockers and recommendations.

| Domain | Agent | Findings File | Score |
|--------|-------|---------------|-------|
| Frappe Backend | frappe-backend-auditor | `output/plan-audit/store-ops-inventory/frappe_backend_findings.md` | 5 CRITICAL, 9 WARNING, 7 INFO |
| Frontend | frontend-auditor | `output/plan-audit/store-ops-inventory/frontend_findings.md` | 5/10 quality |
| Deployment/QA | deployment-qa-auditor | `output/plan-audit/store-ops-inventory/deployment_qa_findings.md` | NO-GO verdict |
| System Architecture | system-arch-auditor | `output/plan-audit/store-ops-inventory/system_arch_findings.md` | 2.8/5 architecture |
| Design Review | design-review-auditor | `output/plan-audit/store-ops-inventory/design_review_findings.md` | 3.1/5 design quality |
| PH Finance | ph-finance-auditor | `output/plan-audit/store-ops-inventory/ph_finance_findings.md` | 63/100 compliance |

### Blocker Resolution Status (v1.2 — 2026-02-20)

All 10 audit blockers have been resolved. Code verified against actual source files.

| # | Blocker | Resolution | Verified |
|---|---------|------------|----------|
| 1 | `_create_mr_for_store_order()` warehouse None | `store.py:531` already reads `order.store` with null check | Code verified |
| 2 | `resolve_variance()` never submits Stock Entry | `inventory.py:1352-1354` has `se.submit()`, `release_savepoint()` removed, SR path at 1373-1375 also submits | Code verified |
| 3 | 4 duplicate function pairs | `ordering.py:61-93` — `get_orderable_items`, `validate_order_schedule`, `submit_order`, `approve_order` all deprecated to redirect to `store.py` | Code verified |
| 4 | `cargo_category` missing from `store.submit_order()` | `store.py:331` accepts `cargo_category` param, line 346 validates it as required | Code verified |
| 5 | No role checks on variance functions | `inventory.py:1279` and `1312` have role checks (`Store Supervisor`, `Area Supervisor`, `Warehouse User`, `System Manager`) | Code verified |
| 6 | `has_date_mismatch` field missing | Field exists in `bei_pos_upload.json` at line 282 | Code verified |
| 7 | Tasks A-1/B-1 describe full rebuilds | Plan task descriptions already retargeted to fix existing implementations (add Cancel button, verify cargo_category) | Plan verified |
| 8 | "Warehouse Manager" role mismatch with `lib/roles.ts` | Changed to "Warehouse User" in `inventory.py` (both `start_variance_investigation` and `resolve_variance`) | **Fixed v1.2** |
| 9 | Zero L3 test scenarios | 21 scenarios written in `TEST_SCENARIOS.md` (SORDER-001, POSDATE-001, VAR-001, CCRECON-001, GCHAT-001, etc.) | Code verified |
| 10 | No rollback plan | Rollback section exists in plan (lines 467-491) with Docker tag, Customize Form removal, test data cleanup | Plan verified |

### Additional Recommendations (Non-Blocking)

1. **`except Exception` swallows `frappe.ValidationError`** (`design_review_findings.md` CRIT-2): 6 functions silently absorb validation errors. Let `frappe.ValidationError` and `frappe.PermissionError` propagate; only catch unexpected exceptions.
2. **SQL injection in `get_returns_pending`** (`design_review_findings.md` CRIT-3): f-string SQL interpolation. Use parameterized queries.
3. **`_send_order_notification()` re-raises exceptions** (`frappe_backend_findings.md` W5, `system_arch_findings.md` C4): Change `raise e` to `frappe.log_error()` to match store.py pattern.
4. **N+1 queries in `get_orderable_items()`** (`system_arch_findings.md` C3): 401 queries for 200-item catalog. Rewrite as batch SQL.
5. **Area Supervisor has no permission on BEI Approval Queue** (`frappe_backend_findings.md` I5): Task B-3 UI will get PermissionError.
6. **Variance route conflict** (`frontend_findings.md` C-04): `/dashboard/inventory/variances` already exists as store-staff form. Task E-1 management list needs different route.
7. **`store.py:approve_order()` uses `order.save()` without `ignore_permissions`** (`design_review_findings.md` WARN-5): Area Supervisor will get PermissionError.
8. **"Store OIC" missing from `STORE_OPS_ALLOWED_ROLES`** (`design_review_findings.md` WARN-6): OICs can't call store ops endpoints.
9. **Approval Queue silently skipped when no Area Supervisor configured** (`system_arch_findings.md` W2): Orders stuck in "Pending Approval" forever with no notification.
10. **SWR hooks already exist for Task B-3** (`frontend_findings.md` W-02): `useOrderReviewQueue`, `useApproveOrder`, `useRejectOrder` already implemented — only the page component is missing.
11. **Dual valuation (Moving Average + FIFO) violates PAS 2.25** (`ph_finance_findings.md` W1): Commit to one method for financial reporting.
12. **Stock Entry Write-Off GL accounts unspecified** (`ph_finance_findings.md` W2): Confirm GL mapping with Finance before deploying variance resolution.

### Pre-Flight Checks: Audit Additions

- [x] **AUDIT-1:** `store.py:531` reads `order.store` — already correct (BLOCKER 1)
- [x] **AUDIT-2:** `se.submit()` and `sr.submit()` present in `resolve_variance()`, `release_savepoint()` removed (BLOCKER 2)
- [x] **AUDIT-3:** All 4 duplicate function pairs deprecated in `ordering.py` → redirect to `store.py` (BLOCKER 3)
- [x] **AUDIT-4:** `cargo_category` param exists on `store.py:submit_order()` with validation (BLOCKER 4)
- [x] **AUDIT-5:** Role checks present on `start_variance_investigation()` and `resolve_variance()` (BLOCKER 5)
- [x] **AUDIT-6:** `has_date_mismatch` field exists on `BEI POS Upload` DocType JSON (BLOCKER 6)
- [x] **AUDIT-7:** Tasks A-1 and B-1 retargeted to fix existing implementations (BLOCKER 7)
- [x] **AUDIT-8:** Changed "Warehouse Manager" → "Warehouse User" in `inventory.py` (BLOCKER 8) — **Fixed v1.2**
- [x] **AUDIT-9:** 21 L3 test scenarios written in `TEST_SCENARIOS.md` (BLOCKER 9)
- [x] **AUDIT-10:** Rollback plan documented with Docker image tag and cleanup procedure (BLOCKER 10)

### GO / NO-GO Gate (Updated v2.0)

**6 MUST-FIX blockers identified. Sprint is CONDITIONAL GO — resolve V-05, V-06, V-09, V-10, V-14, NG-01 before execution.**

### Version History

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | 2026-02-19 | Initial draft |
| v1.1 | 2026-02-20 | 6-domain parallel audit: 10 blockers identified, 12 additional recommendations. NO-GO gate added. |
| v1.2 | 2026-02-20 | Blocker resolution: 9/10 already fixed in code, BLOCKER 8 fixed (Warehouse Manager→Warehouse User in inventory.py). Status changed to GO. Remaining work: 8 tasks (D-1, C-1, F-1, A-1, B-3, B-4, B-5, E-1). |
| v1.3 | 2026-02-20 | BLOCKER 11 fixed: Added "Store OIC" to `STORE_OPS_ALLOWED_ROLES` in `store.py:83`. Without this, Store OICs (including test.staff@bebang.ph) were locked out of all store ops endpoints. Clarified dual-path RBAC: `store.py:approve_order()` = Area Supervisor only (store path), `ordering.py` ORDERING_APPROVAL_ROLES = includes HR Manager/Warehouse User (commissary path). Both are by design. |
| v2.0 | 2026-02-20 | Second full audit (v2): 6 domain agents + code verifier. 21 findings verified against source code: 18 confirmed, 2 stale (false positives), 1 new gap. 6 must-fix blockers, 6 sprint-fix items. |
| v2.1 | 2026-02-20 | 4/6 blockers fixed in code: V-05 (cycle count v1 submit), V-06 (approval queue warning), V-14 (N+1 batch query), NG-01 (theft/damage stock entry). 2 remaining are frontend (V-09 POS cancel button, V-10 route conflict) — to fix in bei-tasks repo during sprint. Status: GO. |
| v3.0 | 2026-02-20 | **SPRINT EXECUTED.** All 7 tasks implemented by agent team (5 Wave-1 parallel + 2 Wave-2 parallel). Code review found 2 CRITs + 5 WARNs; all fixed. Code simplifier applied 3 improvements. **Changes:** Backend: store.py (A-2 date tag, D-1 auto-link, B-4/B-5 GChat + _notify_store_ops helper), inventory.py (F-1 mark_cycle_count_reconciled + 4 DocType fields), ordering.py (deprecated log_error→logger.warning). Legacy FE: ReceivingForm.vue (C-1 food quality + C-2 payload fix). React/bei-tasks: POS cancel button with orphan doc delete (CRIT-2), order approvals page with RBAC fix (WARN-4), variance management page at /variance-management (V-10), cycle count reconcile button, approve_order payload dict fix (CRIT-1), useOrderDetail via frappe.client.get (WARN-5). Test scenarios: 2 photo E2E scenarios + 2 regression entries. Status: COMPLETE — ready for deploy. |

---

## Audit Amendments (v2.0) — 2026-02-20

### Audit Methodology (Second Pass)

7 agents (6 domain + 1 code verifier) audited the plan. All domain agents read ACTUAL source code. Code verifier grounded every CRITICAL finding against file:line evidence.

| Domain | Agent | Findings File | Score |
|--------|-------|---------------|-------|
| Frappe Backend | frappe-backend-auditor | `output/plan-audit/store-ops-inventory-v2/frappe_backend_findings.md` | 3 CRITICAL, 4 WARNING, 3 INFO |
| PH Finance | ph-finance-auditor | `output/plan-audit/store-ops-inventory-v2/ph_finance_findings.md` | 57/100 compliance |
| Frontend | frontend-auditor | `output/plan-audit/store-ops-inventory-v2/frontend_findings.md` | 7/10 quality |
| Deployment/QA | deployment-qa-auditor | `output/plan-audit/store-ops-inventory-v2/deployment_qa_findings.md` | NO-GO (2 blockers) |
| System Architecture | system-arch-auditor | `output/plan-audit/store-ops-inventory-v2/system_arch_findings.md` | 2.8/5 (9 critical, 12 major) |
| Design Review | design-review-auditor | `output/plan-audit/store-ops-inventory-v2/design_review_findings.md` | 3/5 (3 critical, 3 warning) |
| **Code Verification** | code-verifier | `output/plan-audit/store-ops-inventory-v2/code_verification.md` | **18 confirmed, 2 stale, 1 new gap** |

### Stale Findings (False Positives — Removed)

| Claim | Actual State |
|-------|-------------|
| "BEI Cycle Count status missing Reconciled" | "Reconciled" IS in `bei_cycle_count.json:91` options string |
| "approve_order missing ignore_permissions" (v1.1 WARN-5) | `ignore_permissions=True` IS at `store.py:501` |

### Top 10 Verified Blockers

#### BLOCKER V-05 (CRITICAL): Parallel v1/v2 cycle count paths — incompatible docstatus
**Source:** `code_verification.md` V-05 | `system_arch_findings.md` CRITICAL-07
**Problem:** `submit_cycle_count` (inventory.py:17) creates `docstatus=0` records. `submit_cycle_count_v2` (inventory.py:705) creates `docstatus=1`. `approve_cycle_count` (inventory.py:193) requires `docstatus=1` — so v1 records can NEVER be approved.
**Fix:** Deprecate `submit_cycle_count` or add `docstatus=1` migration for existing v1 records. Check if any stores still use the v1 endpoint.

#### BLOCKER V-14 (CRITICAL): N+1 + data bug in get_orderable_items
**Source:** `code_verification.md` V-14 | `system_arch_findings.md` CRITICAL-03
**Problem:** `store.py:245-263` — nested `get_all` inside loop = 200+ queries for 100-item store. Also, `limit=1` on inner query returns wrong `last_order_qty` (only checks most recent order, not most recent order containing that item).
**Fix:** Replace loop with single batch query. `ordering.py` already has correct `_get_last_order_qty` implementation to reference.

#### BLOCKER V-06 (MAJOR): Approval Queue silently dropped on failure
**Source:** `code_verification.md` V-06 | `system_arch_findings.md` MAJOR-04
**Problem:** `store.py:411-431` — bare `except Exception` swallows queue creation failures. Order stays in "Pending Approval" with no supervisor routing. No warning returned to frontend.
**Fix:** At minimum, add `result["warning"] = "Order created but approval routing failed"` in the except block. Better: make queue creation non-optional (let it throw).

#### BLOCKER NG-01 (MAJOR): Theft/Damage variance resolution — no stock adjustment
**Source:** `code_verification.md` NG-01 | `ph_finance_findings.md` F-05
**Problem:** `inventory.py:1379-1380` — "Theft", "Damage", "System Error" resolution types only set `doc.status = "Resolved"` with NO Stock Entry. Phantom inventory remains in stock ledger.
**Fix:** Create Material Issue Stock Entry for Theft/Damage (same as Write-Off path). System Error may need Stock Reconciliation instead.

#### BLOCKER V-10 (MAJOR): Frontend route conflict for variance management
**Source:** `code_verification.md` V-10 | `frontend_findings.md` C-02
**Problem:** `/dashboard/inventory/variances` already exists in bei-tasks as a store-staff variance SUBMISSION form. Building Task E-1 management UI at this route would overwrite it.
**Fix:** Use `/dashboard/inventory/variance-management` or `/dashboard/inventory/variances/manage` for the new management list.

#### BLOCKER V-09 (MAJOR): POS Upload Cancel button absent
**Source:** `code_verification.md` V-09 | `frontend_findings.md` C-01
**Problem:** `bei-tasks/app/dashboard/store-ops/pos/page.tsx:159-192` — date mismatch modal has only "I Understand, Continue" button. No `AlertDialogCancel`. Doc is already inserted when modal appears.
**Fix:** This IS Task A-1 in the sprint. Elevate to blocker priority — currently scheduled Day 2-3 but should be Day 1 since data corruption is active.

### Additional Verified Findings (Fix in Sprint)

7. **V-02:** Duplicate status `"Partial"` vs `"Partially Fulfilled"` in `bei_store_order.json:65` — data split risk
8. **V-03:** N+1 in `get_order_history` (`store.py:459-463`) — 21+ queries per page load
9. **V-08:** `except Exception` swallows `ValidationError` in 3 inventory.py functions (lines 76, 338, 411)
10. **V-18:** `resubmit_cycle_count` (`inventory.py:279`) missing `ignore_permissions=True` — store staff can't resubmit rejected counts

### Deferred to Next Sprint

11. **V-15/V-16:** N+1 in `get_mid_shift_handovers` and `get_return_requests`
12. **V-17:** Duplicate `resolve_warehouse` functions (store.py vs inventory.py) with diverging failure modes
13. **V-19:** Missing `ignore_permissions` in `save_cycle_count_draft` and `approve_cycle_count`
14. **V-11:** 5 hardcoded GL accounts in `process_store_return` (`store.py:956-988`)
15. **V-01:** `store.py` God Object (2361 lines, 36 endpoints, 8 domains) — refactor post-sprint

### Pre-Flight Checks: v2.0 Audit Additions

- [x] **AUDIT-V05:** Fixed — added `doc.submit()` to legacy `submit_cycle_count` so it creates `docstatus=1` (matching v2). bei-tasks still calls v1 via `use-inventory.ts:122`.
- [x] **AUDIT-V14:** Fixed — replaced N+1 loop in `get_orderable_items` (`store.py:245`) with single batch SQL query. Also fixed silent data bug (limit=1 returned wrong last_order_qty).
- [x] **AUDIT-V06:** Fixed — approval queue except block now returns `warning` field to frontend instead of silent swallow (`store.py:425`).
- [x] **AUDIT-NG01:** Fixed — Theft/Damage resolution types now create Material Issue Stock Entry to remove phantom inventory (`inventory.py:1383`). System Error remains status-only (no stock adjustment).
- [ ] **AUDIT-V10:** Change Task E-1 route to `/dashboard/inventory/variance-management` (not `/variances`). **Frontend — bei-tasks repo.**
- [ ] **AUDIT-V09:** Elevate Task A-1 (POS Cancel button) to Phase 1 Day 1 priority. **Frontend — bei-tasks repo.**
