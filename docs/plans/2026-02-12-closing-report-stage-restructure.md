# Closing Report Stage Restructure

**Date:** 2026-02-12
**Priority:** HIGH — Do BEFORE bug fixes (changes the same functions)
**Depends on:** None
**Blocks:** `2026-02-12-closing-report-fix-and-ux-redesign.md` (bug fix plan must adapt to new structure)

---

## Problem

The 3-stage closing report has fields in the wrong stages, redundant data collection, and dead code:

| Issue | Impact |
|-------|--------|
| `variance_explanation` in Stage 3 instead of Stage 1 | Crew explains cash variance 2 pages after they see it — they forget why |
| Equipment readings (Stage 2) split from equipment photos (Stage 3) | Crew reads thermometer AND photographs it at the same time — forced to enter in different steps |
| 5 POS files re-collected in Stage 3 | Already collected via separate `BEI POS Upload` endpoint + DocType — double work for crew |
| Old monolithic `submit_closing_report()` still exists | 75 lines of dead code that confuses maintenance |
| Cash reconciliation fields not in any stage | `pos_total_sales`, `actual_cash_count`, `card_payments`, `gcash_total` exist in DocType but no stage collects them |
| Maintenance fields not in any stage | 6 fields exist in DocType but nothing populates them |

---

## Changes

### 1. Move `variance_explanation` from Stage 3 to Stage 1

**File:** `hrms/api/store.py`

**Stage 1** (`submit_closing_stage1_cash`, line 1307): Add `variance_explanation` parameter.

```python
def submit_closing_stage1_cash(report_name, petty_cash_fund=0, delivery_fund=0,
                                change_fund=0, cash_notes=None, pos_down=False,
                                pos_down_estimated_sales=None, pos_down_transaction_count=None,
                                pos_down_notes=None, variance_explanation=None, **kwargs):
    # ... existing code ...
    doc.cash_notes = cash_notes
    doc.variance_explanation = variance_explanation  # ADD — explain variance when you see it
```

**Stage 3** (`submit_closing_stage3_photos`, line 1419): Remove `variance_explanation` parameter.

```python
def submit_closing_stage3_photos(report_name, x_reading_opening_photo, x_reading_closing_photo,
                                  z_reading_photo, store_photos=None,
                                  notes=None):  # REMOVED: pos_files, variance_explanation
```

**Frontend** (`bei-tasks/app/dashboard/store-ops/closing/page.tsx`):
- Move the variance explanation textarea from Stage 3 component to Stage 1 component
- Show it conditionally when `cash_variance` (from API response) exceeds +/- 50 pesos
- Stage 1 API response already returns `total_funds` — add `cash_variance` to response too

**Stage 1 response change:**
```python
return {
    "success": True,
    "name": doc.name,
    "stage_completed": doc.stage_completed,
    "total_funds": doc.total_funds,
    "cash_variance": doc.cash_variance  # ADD — so frontend can show variance explanation prompt
}
```

### 2. Move equipment readings from Stage 2 to Stage 3

**File:** `hrms/api/store.py`

**Stage 2** (`submit_closing_stage2_checklist`, line 1353): Remove `equipment_status` parameter and lines 1396-1399.

```python
def submit_closing_stage2_checklist(report_name, inventory_items, checklist_items=None,
                                     cashier_signoff=False, production_signoff=False,
                                     supervisor_signoff=False):  # REMOVED: equipment_status
    # ... existing code ...
    # REMOVE lines 1374-1375 (isinstance check for equipment_status)
    # REMOVE lines 1396-1399 (freezer_temp, chiller_temp, pos_closed_properly)
```

**Stage 3** (`submit_closing_stage3_photos`, line 1419): Add `equipment_status` parameter.

```python
def submit_closing_stage3_photos(report_name, x_reading_opening_photo, x_reading_closing_photo,
                                  z_reading_photo, store_photos=None,
                                  equipment_status=None, notes=None):
    # ... after photo processing ...

    # Equipment readings (entered alongside equipment photos)
    if equipment_status:
        if isinstance(equipment_status, str):
            equipment_status = json.loads(equipment_status)
        doc.freezer_temp = equipment_status.get("freezer_temp")
        doc.chiller_temp = equipment_status.get("chiller_temp")
        doc.pos_closed_properly = equipment_status.get("pos_closed_properly", 0)
```

**Frontend:**
- Move freezer/chiller temp inputs from Stage 2 to Stage 3, next to the hygrometer and water meter photo capture fields
- Group as "Equipment Readings + Photos" section in Stage 3 UI

### 3. Remove POS files from Stage 3

**File:** `hrms/api/store.py`

**Stage 3** (`submit_closing_stage3_photos`, line 1419): Remove `pos_files` parameter and lines 1449-1456.

```python
def submit_closing_stage3_photos(report_name, x_reading_opening_photo, x_reading_closing_photo,
                                  z_reading_photo, store_photos=None,
                                  equipment_status=None, notes=None):
    # REMOVED: pos_files parameter
    # REMOVED: lines 1449-1456 (pos_files processing)
```

POS files are already handled by the separate `upload_pos_data()` endpoint (line 873) which creates a `BEI POS Upload` record. The closing report links to it via the `pos_upload` Link field.

**Frontend:**
- Remove POS file upload section from Stage 3 component
- If POS Upload is required before closing, show a status badge: "POS Upload: Done" or "POS Upload: Pending"
- Link to the POS Upload page if pending

**DocType fields to keep (no schema change):** `pos_discount_report`, `pos_transaction_report`, `pos_product_mix`, `pos_daily_sales_revenue`, `pos_sales_summary` — these can be populated by a future auto-link from BEI POS Upload, or removed later. Not changing schema now.

### 4. Delete old monolithic endpoint

**File:** `hrms/api/store.py`

Delete `submit_closing_report()` function (lines 643-717). This is the old single-endpoint version that the frontend no longer calls. The 3-stage pipeline (`get_or_create_closing_report` + `submit_closing_stage1_cash` + `submit_closing_stage2_checklist` + `submit_closing_stage3_photos`) replaces it completely.

**Verify before deleting:**
```bash
# Search both repos for any remaining calls
grep -r "submit_closing_report" hrms/ --include="*.py" --include="*.js"
grep -r "submit_closing_report" ../bei-tasks/ --include="*.ts" --include="*.tsx"
```

If only the function definition is found (no callers), safe to delete.

### 5. Add `actual_cash_count` to Stage 1 (conditional)

**File:** `hrms/api/store.py`

The `actual_cash_count` field is the physical cash count the crew does. It's used to compute `cash_variance = actual_cash_count - pos_total_sales - card_payments - gcash_total + ...`. Currently no stage collects it.

Two scenarios:
- **POS Upload done first:** `pos_total_sales`, `card_payments`, `gcash_total` auto-populate from POS extraction. Crew enters `actual_cash_count` in Stage 1 and variance is computed.
- **POS Upload not done:** All POS fields are zero. `actual_cash_count` still captured but variance is meaningless.

**Stage 1** (`submit_closing_stage1_cash`): Add `actual_cash_count` parameter.

```python
def submit_closing_stage1_cash(report_name, petty_cash_fund=0, delivery_fund=0,
                                change_fund=0, cash_notes=None, pos_down=False,
                                pos_down_estimated_sales=None, pos_down_transaction_count=None,
                                pos_down_notes=None, variance_explanation=None,
                                actual_cash_count=0, **kwargs):
    # ... existing code ...
    doc.actual_cash_count = float(actual_cash_count or 0)
```

**Frontend:**
- Add "Actual Cash Count" input to Stage 1 below denomination breakdown
- Show computed `cash_variance` after save (already returned in response)
- If variance > +/- 50: show variance explanation textarea

### 6. Maintenance fields — no stage, keep as-is

The 6 maintenance fields (`has_maintenance_today`, `maintenance_verified`, etc.) are conditional — only relevant when a maintenance tech visited that day. This is better handled as a separate workflow (supervisor fills in after closing) rather than forcing every crew member through a maintenance section every night.

**Decision: Leave as-is.** These fields can be populated via Frappe Desk or a future "Supervisor Review" flow. Not adding them to any stage.

---

## New Stage Structure (After Changes)

### Stage 1: Cash Count & Reconciliation
| Field | Type | Notes |
|-------|------|-------|
| petty_cash_fund | Currency | |
| delivery_fund | Currency | |
| change_fund | Currency | |
| Denomination breakdowns (3x7) | Currency/Int | PCF, Delivery, Change Fund |
| Voucher amounts (2) | Currency | PCF, Delivery |
| actual_cash_count | Currency | **NEW** — physical cash count |
| POS Down mode (4 fields) | Mixed | Conditional |
| cash_notes | Text | |
| variance_explanation | Text | **MOVED from Stage 3** — conditional on variance > 50 |

**Saved data:** 30+ fields. Heavy data entry but all numerical — fast on mobile with number pads.

### Stage 2: Checklist & Inventory
| Field | Type | Notes |
|-------|------|-------|
| inventory_spot_check | Child Table | 12 items with expected/actual counts |
| checklist_items | Child Table | End-of-day tasks |
| cashier_signoff | Check | |
| production_signoff | Check | |
| supervisor_signoff | Check | |

**Removed from Stage 2:** `equipment_status` (freezer_temp, chiller_temp, pos_closed_properly) — moved to Stage 3.

**Saved data:** 2 child tables + 3 checkboxes. Checkbox-heavy — fast to complete.

### Stage 3: Photos & Equipment
| Field | Type | Notes |
|-------|------|-------|
| X-reading opening photo | Attach Image | Document scan |
| X-reading closing photo | Attach Image | Document scan |
| Z-reading photo | Attach Image | Document scan |
| 10 store area photos | Attach Image | Standard camera |
| Equipment readings | Mixed | **MOVED from Stage 2** — freezer_temp, chiller_temp, pos_closed_properly |
| notes | Text | General notes |

**Removed from Stage 3:** `pos_files` (5 fields) — handled by separate POS Upload. `variance_explanation` — moved to Stage 1.

**Saved data:** 13 photos + 3 equipment fields + notes. Photo-heavy — slowest stage due to camera captures.

---

## Files Modified

| File | Changes |
|------|---------|
| `hrms/api/store.py` | Move variance_explanation to stage1, move equipment to stage3, remove pos_files from stage3, add actual_cash_count to stage1, delete old submit_closing_report() |
| `bei-tasks/app/dashboard/store-ops/closing/page.tsx` | Move variance explanation UI to Stage 1, move equipment inputs to Stage 3, remove POS file upload from Stage 3, add actual_cash_count input |

No DocType schema changes needed — all fields already exist, we're just changing which API endpoint writes to them.

---

## Execution Order

1. **Backend changes** (hrms/api/store.py) — all in one commit
2. **Frontend changes** (bei-tasks closing page) — separate commit after backend deploys
3. **Delete dead code** (old submit_closing_report) — only after verifying no callers remain

This restructure should be done BEFORE the bug fix plan (`2026-02-12-closing-report-fix-and-ux-redesign.md`) since it changes the same functions. The bug fixes (save_base64_image, key mismatch, etc.) apply to the restructured code.

---

## Verification

After restructure, verify:

1. **Stage 1 saves variance_explanation** — submit with variance > 50, check explanation saved
2. **Stage 2 no longer accepts equipment_status** — confirm parameter is ignored/removed
3. **Stage 3 accepts equipment_status** — submit with freezer_temp=5, verify saved
4. **Stage 3 no longer accepts pos_files** — confirm parameter is ignored/removed
5. **Stage 1 saves actual_cash_count** — submit with count, verify cash_variance computed
6. **Old endpoint deleted** — `POST submit_closing_report` returns 404/AttributeError
7. **Full 3-stage flow** — complete all 3 stages, verify all fields populated correctly

---

## Related Plans

| Plan | Relationship |
|------|-------------|
| `2026-02-12-closing-report-fix-and-ux-redesign.md` | Bug fixes (save_base64_image, key mismatch, permissions) — apply AFTER this restructure |
| `2026-02-12-ops-bug-tracker.md` | Tracks all 22 ops bugs from feedback — BUG-002 is the closing report |
| `2026-02-12-ops-5-bugs-fix-plan.md` | Original simpler bug fix plan — superseded by the comprehensive plan |
