# S137 — Commissary Production Planning Control Room

```yaml
sprint_id: S137
display: Sprint 137
branch: s137-commissary-production-planning
status: PR_CREATED
planned_date: 2026-03-27
completed_date: null
execution_summary: null
depends_on: [S126, S131]
registry_row: "| `S137` | Sprint 137 | `s137-commissary-production-planning` | — | PLANNED |"
total_work_units: 57
```

## Business Problem

The commissary has no production planning visibility. Today's `get_production_suggestions()` uses a **hardcoded target of 100 units** for every product — it doesn't know if stores need 20 or 500. The supervisor produces based on gut feel. The CEO has no way to see whether the commissary is producing what's actually needed or under/over-producing.

**What the CEO wants:** A dashboard showing what the system RECOMMENDS (based on store demand, DTL, orders) vs. what the commissary supervisor TARGETS (their adjusted number) — so manipulation or lazy planning is immediately visible.

**What the supervisor needs:** A single screen with all production data — current stock, days inventory, store demand, RM availability, feasibility — to set realistic daily targets.

## Design Rationale (For Cold-Start Agents)

### Why This Exists
- `get_production_suggestions()` (commissary_requisition.py:471-533) uses `target_stock = 100` for ALL items — a useless placeholder
- Store ordering data exists (Material Requests, DTL calculations, 7-day consumption) but is NOT connected to commissary production planning
- The commissary supervisor currently guesses production quantities — no data-driven targets
- CEO has zero visibility into whether production aligns with actual demand

### Why This Architecture
- **Backend: New `commissary_planning.py`** — keeps planning logic separate from dashboard/requisition modules that are already 1000+ lines each
- **Two new DocTypes** — BEI Production Target (daily plan with child items) + BEI Production Target Log (immutable audit trail). DocTypes give us: Frappe permissions, naming series, audit trail, report builder, and prevent direct DB manipulation. The CEO anti-manipulation requirement demands tamper-proof storage, which JSON flat files cannot guarantee.
- **Demand calculation: DTL-based, not ML** — we already have 7-day consumption averages in `get_days_inventory()` and `get_rm_reorder_alerts()`. Reuse those proven calculations. ML forecasting is S022 scope (future).
- **CEO audit trail: immutable log via DocType** — every time supervisor adjusts a target, a BEI Production Target Log entry is created. Immutability is technically enforced: `on_trash()` throws, `before_save()` blocks edits on existing entries, `allow_rename=0`, `autoname="hash"`. The log is append-only by code, not just convention.

### Key Trade-Off Decisions
1. **DocType vs flat table for targets** → DocType. Reason: CEO anti-manipulation requirement demands tamper-proof storage with audit trail. Frappe DocTypes provide permissions, naming series, report builder. Flat JSON has no access control — any script or admin can modify it silently.
2. **Pull demand from existing endpoints vs new calculation** → Reuse `get_days_inventory()` consumption data + pending Material Requests. No new demand model needed — the data exists, it's just not connected.
3. **Production capacity: simple hours vs detailed resource modeling** → Simple hours (2 shifts × hours × kg/hr). Detailed resource modeling (oven-hours, vat-hours) deferred — commissary has ~10 items and 2 shifts, not a factory with 50 lines.
4. **RM explosion: BOM-based vs manual** → BOM-based. All 22 FG items have BOMs (`check_production_feasibility()` already does this). Extend it to multi-item planning.

### Key Design Additions (Post-Review)
5. **Product-specific target DI, not a flat default** → `PRODUCT_THRESHOLDS` in `commissary.py:1128-1243` already defines per-item `target_di` (e.g., FG001=7 days for 15-day shelf life, FG004=30 days for 180-day shelf life). The recommendation engine MUST use `get_product_threshold(item_code)` instead of a hardcoded default.
6. **Shelf life overproduction cap** → If producing more than `(shelf_life - days_inventory) * avg_daily_consumption` would cause product to expire before it's consumed. Cap `recommended_qty` at this value for short-shelf-life items (shelf_life < 30 days).
7. **Wastage factor** → 7-day wastage rate inflates recommended_qty. Formula: `wastage_factor = 1 + (7d_wastage_qty / 7d_production_qty)`. Example: if 5% of production is wasted, recommend 5% more.
8. **Outsourced items show "Order Qty" not "Target Qty"** → FG001 (Leche Flan, shelf_life=15, 2-week supplier lead time) and FG002 cannot be produced in-house. The planning table differentiates: in-house items get "Produce" action, outsourced items get "Order" action with supplier lead time displayed.
9. **Capacity warning (not hard block)** → Daily capacity ≈ 950 kg/day (AM: 11 staff × 9 hrs × 50 kg/hr ÷ 2 tasks = ~2,475 kg theoretical, ~950 kg practical from MANCOM data). If total targeted > capacity, show amber warning. Don't block — supervisor knows better.

### Known Limitations
- **No Supabase POS demand integration** — `store_order_demand_snapshot.py` exists but is CLI-only. This sprint uses Frappe-native data (Material Requests, SLE consumption). POS demand integration is a future enhancement.
- **Outsourced items (FG001, FG002)** — included in recommendations with differentiated action (Order vs Produce). Supervisor sets order qty; system shows supplier lead time. Auto-PO generation is future scope.
- **No scheduling/sequencing** — this sprint answers "how much" not "in what order." Batch scheduling is future scope.
- **Labor plan integration** — If BEI Weekly Labor Plan shows reduced staffing, capacity warning should reflect it. This sprint uses static capacity estimate; dynamic labor integration is future scope.

### Source References
- Days inventory logic: `hrms/api/commissary.py:1247-1382` (`get_days_inventory()`)
- Production suggestions: `hrms/api/commissary_requisition.py:471-533` (`get_production_suggestions()`)
- RM reorder/consumption: `hrms/api/commissary_requisition.py:96-196` (`get_rm_reorder_alerts()`)
- BOM feasibility: `hrms/api/commissary_bom.py:270-359` (`check_production_feasibility()`)
- Pending store orders: `hrms/api/commissary_dashboard.py:473-577` (`get_pending_store_orders()`)
- Production items: `hrms/api/commissary_dashboard.py:320-403` (`get_production_items()`)

---

## Phase 0: Backend — Production Planning Engine (14 units)

New file: `hrms/api/commissary_planning.py`

### P0-1: `get_production_recommendations()` endpoint (7 units)
**[BUILD]** — New demand-driven recommendation engine replacing hardcoded target=100.

**Algorithm:**
```
For each active FG item (queried dynamically from Frappe — same SQL as get_days_inventory()):
  1. current_stock = Bin.actual_qty (Shaw BLVD - BKI)
  2. avg_daily_consumption = 7-day rolling from SLE (reuse get_days_inventory logic)
  3. pending_demand = SUM(Material Request items where item_code=X, docstatus=1, status in [Pending, Partially Ordered])
  4. days_inventory = current_stock / avg_daily_consumption (or ∞ if no consumption)

  # ── GAP FIX #1: Product-specific target DI from PRODUCT_THRESHOLDS ──
  # NOTE: PRODUCT_THRESHOLDS (commissary.py:1129) has explicit entries for ~10 items.
  # Items without entries (FG002, FG008, FG010, FG011, FG013, FG015-FG022) use
  # defaults: target_di=14, shelf_life=90. Verify defaults are acceptable.
  5. threshold = get_product_threshold(item_code)  # from commissary.py:1129
     target_di = threshold.target_di              # e.g., FG001=7, FG004=30, default=14
     shelf_life = threshold.shelf_life_days       # e.g., FG001=15, FG004=180, default=90

  6. target_stock = avg_daily_consumption * target_di
  7. raw_recommended = MAX(0, target_stock - current_stock + pending_demand)

  # ── GAP FIX #2: Shelf life overproduction cap (short-life items only) ──
  8. IF shelf_life <= 30 days AND avg_daily_consumption > 0:
       max_before_expiry = (shelf_life - days_inventory) * avg_daily_consumption
       recommended_qty = MIN(raw_recommended, MAX(0, max_before_expiry))
     ELIF avg_daily_consumption == 0:
       recommended_qty = 0  # No consumption = don't produce (prevents /0)
     ELSE:
       recommended_qty = raw_recommended

  # ── GAP FIX #3: Wastage factor inflation ──
  9. wastage_7d = SUM(Material Issue SLE qty for this item, last 7 days)
     production_7d = SUM(Manufacture SLE qty for this item, last 7 days)
     wastage_factor = 1 + (wastage_7d / production_7d) if production_7d > 0 else 1
     recommended_qty = recommended_qty * wastage_factor

  10. priority = "critical" if DI < 1, "high" if DI < target_di * 0.5, "normal" otherwise

  # ── GAP FIX #4: Outsourced item detection ──
  11. is_outsourced = resolve_outsourced_item_flag(item)  # from commissary.py:143
      # Uses: explicit flag → supplier present → code prefix (OUT-, OS-, 3P-)
```

**Returns per item:**
```json
{
  "item_code": "FG004",
  "item_name": "GULAMAN PANDAN",
  "current_stock": 15.0,
  "uom": "KG",
  "avg_daily_consumption": 8.5,
  "days_inventory": 1.8,
  "target_di": 30,
  "shelf_life_days": 180,
  "target_stock": 255.0,
  "pending_demand": 12.0,
  "recommended_qty": 22.5,
  "wastage_factor": 1.03,
  "shelf_life_cap_applied": false,
  "priority": "high",
  "is_outsourced": false,
  "action": "produce",
  "has_bom": true,
  "bom_name": "BOM-FG004-001",
  "max_producible": 45.0,
  "bottleneck_rm": "RM-015 Crystal Gulaman Pandan",
  "last_produced": "2026-03-26",
  "last_produced_qty": 30.0
}
```

**Outsourced item example (FG001 Leche Flan):**
```json
{
  "item_code": "FG001",
  "item_name": "LECHE FLAN",
  "current_stock": 20.0,
  "avg_daily_consumption": 5.0,
  "days_inventory": 4.0,
  "target_di": 7,
  "shelf_life_days": 15,
  "recommended_qty": 15.0,
  "shelf_life_cap_applied": true,
  "is_outsourced": true,
  "action": "order",
  "supplier_lead_time_days": 14,
  "default_supplier": "SUPPLIER-XXX",
  "has_bom": false,
  "max_producible": null,
  "bottleneck_rm": null
}
```

**HARD BLOCKER:** `recommended_qty` MUST be computed server-side and returned as-is. Frontend NEVER calculates this. (Source: CEO anti-manipulation requirement)

### P0-2: `set_production_targets()` endpoint (3 units)
**[BUILD]** — Supervisor sets daily targets per item, logged immutably.

**Input:**
```json
{
  "production_date": "2026-03-27",
  "targets": [
    {"item_code": "FG004", "target_qty": 30, "reason": "extra demand from Shaw"},
    {"item_code": "FG006", "target_qty": 0, "reason": "no coconut supply today"}
  ]
}
```

**Behavior:**
1. Validate user has "Commissary User" or "Commissary Manager" role
2. **Re-fetch `recommended_qty` server-side** at this moment (call `get_production_recommendations()` internally) — do NOT accept recommended_qty from frontend input. This prevents the supervisor from manipulating the snapshot.
3. Wrap entire operation in `frappe.db.savepoint("set_targets")` (DM-2 compliance):
   ```python
   try:
       frappe.db.savepoint("set_targets")
       # Create/update BEI Production Target doc
       # Create BEI Production Target Log entries (one per item)
       frappe.db.release_savepoint("set_targets")
   except Exception:
       frappe.db.rollback_to_savepoint("set_targets")
       frappe.throw("Could not save targets. No changes were made.")
   ```
4. For each item, create an immutable log entry (BEI Production Target Log)
5. **On partial failure:** return `{success: false, saved: [...], failed: [...], error: "..."}`. Frontend shows warning toast listing failed items with retry button.
6. Return confirmation with deviation flags

**HARD BLOCKER:** The `recommended_qty` at the time of target-setting is snapshotted into the log by re-fetching server-side. If the supervisor sets target=30 but system recommended=22.5, the CEO sees both. The log is append-only — never overwrite previous entries. (Source: CEO anti-manipulation requirement)

### P0-3: `get_production_targets()` endpoint (2 units)
**[BUILD]** — Returns current targets for a date, with recommended vs target comparison.

**Returns:**
```json
{
  "production_date": "2026-03-27",
  "items": [
    {
      "item_code": "FG004",
      "recommended_qty": 22.5,
      "target_qty": 30.0,
      "deviation_pct": 33.3,
      "actual_produced": 28.0,
      "completion_pct": 93.3,
      "set_by": "commissary.team@bebang.ph",
      "set_at": "2026-03-27 06:15:00",
      "reason": "extra demand from Shaw"
    }
  ],
  "summary": {
    "total_recommended": 180.5,
    "total_targeted": 210.0,
    "total_produced": 155.0,
    "overall_deviation_pct": 16.3,
    "overall_completion_pct": 73.8
  }
}
```

### P0-4: `get_rm_requirements_for_plan()` endpoint (2 units)
**[EXTEND]** — Given target quantities, explode BOMs to show total RM needed.

**Extends:** `check_production_feasibility()` from `commissary_bom.py` — currently handles single item. New endpoint handles multi-item BOM explosion.

**Input:** `{"targets": [{"item_code": "FG004", "qty": 30}, {"item_code": "FG006", "qty": 20}]}`

**Returns:**
```json
{
  "rm_requirements": [
    {
      "rm_code": "RM-015",
      "rm_name": "Crystal Gulaman Pandan",
      "total_required": 45.0,
      "current_stock": 60.0,
      "surplus_deficit": 15.0,
      "status": "sufficient",
      "consumed_by": [
        {"item_code": "FG004", "qty_needed": 45.0}
      ]
    },
    {
      "rm_code": "RM-022",
      "rm_name": "Coconut Meat",
      "total_required": 40.0,
      "current_stock": 25.0,
      "surplus_deficit": -15.0,
      "status": "deficit",
      "consumed_by": [
        {"item_code": "FG006", "qty_needed": 20.0},
        {"item_code": "FG009", "qty_needed": 20.0}
      ]
    }
  ],
  "feasibility": {
    "all_feasible": false,
    "bottlenecks": ["RM-022 Coconut Meat: need 40, have 25"],
    "items_blocked": ["FG006", "FG009"]
  }
}
```

---

## Phase 1: DocType — BEI Production Target (7 units)

### P1-1: Create BEI Production Target DocType (3 units)
**[BUILD]** — Stores daily production targets with full audit trail.

**Schema:**
- `autoname`: `"BPT-.YYYY.-.#####"` (e.g., BPT-2026-00001)
- `is_submittable`: `0` (no submit workflow — targets are set and updated, not submitted)
- **Deployment note:** New DocType requires full Docker build: `skip_build=false, no_cache=true`

**Fields:**
| Field | Type | Notes |
|-------|------|-------|
| `production_date` | Date | Required. Unique per date (one target doc per day). |
| `status` | Select | Draft / Set / In Progress / Completed |
| `set_by` | Link (User) | Auto-set from session |
| `set_at` | Datetime | Auto-set |
| `total_recommended` | Float | Computed in `validate()` — not stored from frontend (DM-5) |
| `total_targeted` | Float | Computed in `validate()` — not stored from frontend (DM-5) |
| `total_produced` | Float | Updated via hook when production SEs are created |
| `items` | Table (child) | BEI Production Target Item |

**Child Table — BEI Production Target Item:**
| Field | Type | Notes |
|-------|------|-------|
| `item_code` | Link (Item) | FG item |
| `recommended_qty` | Float | Snapshotted from algorithm at set time |
| `target_qty` | Float | Supervisor's adjusted quantity |
| `deviation_pct` | Float | Computed in `validate()`: `(target - rec) / rec * 100` if rec > 0, else 0 |
| `reason` | Small Text | Why supervisor deviated |
| `actual_produced` | Float | Updated as production SEs are created |
| `completion_pct` | Float | Computed in `validate()`: `actual / target * 100` if target > 0, else 100 |

**Division-by-zero guards (Blocker 7):**
- `deviation_pct`: `0` when `recommended_qty == 0`
- `completion_pct`: `100` when `target_qty == 0` (nothing to do = complete)

**Permissions:**
| Role | Read | Write | Create | Delete |
|------|------|-------|--------|--------|
| Commissary User | Yes | Yes | Yes | No |
| Commissary Manager | Yes | Yes | Yes | No |
| CEO / Executive | Yes | No | No | No |
| HR Manager | Yes | No | No | No |
| System Manager | Yes | Yes | Yes | No |

### P1-2: Create BEI Production Target Log DocType (2 units)
**[BUILD]** — Immutable audit log. Every time a target is set or changed, a log entry is created.

**Schema:**
- `autoname`: `"hash"` (content-addressable, prevents rename)
- `allow_rename`: `0`
- `is_submittable`: `0` (no workflow — created once, never modified)

**Fields:**
| Field | Type | Notes |
|-------|------|-------|
| `production_date` | Date | |
| `item_code` | Link (Item) | |
| `action` | Select | set / adjusted / reset |
| `recommended_qty` | Float | System recommendation at that moment |
| `previous_target` | Float | Before this change |
| `new_target` | Float | After this change |
| `reason` | Small Text | |
| `changed_by` | Link (User) | |
| `changed_at` | Datetime | |

**Immutability Enforcement (HARD BLOCKER — CEO anti-manipulation):**
```python
class BEIProductionTargetLog(Document):
    def before_save(self):
        if not self.is_new():
            frappe.throw("Production Target Log entries are immutable and cannot be modified.")

    def on_trash(self):
        frappe.throw("Production Target Log entries cannot be deleted.")
```

**Permissions:**
| Role | Read | Write | Create | Delete |
|------|------|-------|--------|--------|
| Commissary User | Yes | No | No | No |
| Commissary Manager | Yes | No | No | No |
| CEO / Executive | Yes | No | No | No |
| System Manager | Yes | No | No | No |

Only system creates entries via `set_production_targets()`. No role has write/delete permission.

### P1-3: Hook production SE to update actuals (2 units)
**[EXTEND]** — After a Manufacture Stock Entry is submitted OR cancelled, update the matching BEI Production Target's `actual_produced` for that date+item.

**On submit:** call `_update_production_target_actuals(item_code, qty, posting_date)` — increments `actual_produced`.
**On cancel:** call `_update_production_target_actuals(item_code, -qty, posting_date)` — decrements `actual_produced`.

Wire into `submit_production_output()` in `commissary_dashboard.py` after successful SE creation. Also register in `hooks.py`:
```python
doc_events = {
    "Stock Entry": {
        "on_submit": "hrms.api.commissary_planning.on_stock_entry_submit",
        "on_cancel": "hrms.api.commissary_planning.on_stock_entry_cancel"
    }
}
```

**Idempotency guard:** Check if `actual_produced` was already updated for this SE name (store `last_se_name` on target item row or use a set). Prevent double-counting on retry.

---

## Phase 2: Frontend — Production Planning Dashboard (13 units)

New route: `/dashboard/commissary/planning`

### P2-1: Planning page layout + data hook (2 units)
**[BUILD]** — New page at `app/dashboard/commissary/planning/page.tsx`

Layout (single bird's-eye view):
```
┌────────────────────────────────────────────────────────────┐
│ Production Planning — [Date Picker: today]                 │
│                                                            │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────┐│
│ │Total Rec│ │Total Tgt│ │Total Act│ │Compltn %│ │Cap % ││
│ │  180 kg │ │  210 kg │ │  155 kg │ │   73.8% │ │ 22%  ││
│ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └──────┘│
│                                                            │
│ [Tab: Production Plan] [Tab: RM Requirements]              │
│ [Tab: Store Demand]                                        │
│                                                            │
│ ┌──────────────────────────────────────────────────────┐   │
│ │ Production Plan Table                                │   │
│ │ FG001 │ Order │ 20  │ 5/d │ 4.0d │ ... │ 15  │ ... │   │
│ │ FG004 │ Prod  │ 15  │ 8/d │ 1.8d │ ... │ 22  │ ... │   │
│ │ FG006 │ Prod  │ 100 │ 3/d │ 33d  │ ... │ 0   │ ... │   │
│ └──────────────────────────────────────────────────────┘   │
│                                                            │
│ [Save Targets]  [Reset to Recommended]                     │
└────────────────────────────────────────────────────────────┘
```

**Hook:** `useProductionPlan(date)` — calls `get_production_recommendations()` + `get_production_targets()` for the selected date.

### P2-2: Production Plan table (4 units)
**[BUILD]** — Interactive table where supervisor sets targets.

**Columns:**
| Column | Source | Editable | Notes |
|--------|--------|----------|-------|
| Item | recommendations | No | Item code + name + shelf life badge for short-life items |
| Action | recommendations | No | Badge: **Produce** (green) or **Order** (blue, outsourced) |
| Current Stock | recommendations | No | With DI badge (critical/low/ok) |
| Avg Daily | recommendations | No | 7-day avg consumption |
| Days Inv. | recommendations | No | Color-coded per product threshold |
| Pending Orders | recommendations | No | Store demand qty |
| Recommended | recommendations | No | **System-calculated, read-only** — includes wastage factor & shelf life cap |
| Target | targets | **Yes** | Editable input, defaults to recommended |
| Deviation | computed | No | `(target - rec) / rec * 100%`, red if > ±25% |
| Reason | targets | **Yes** | Required if deviation > 10% |
| Feasible | recommendations | No | Green check / red X based on RM stock (N/A for outsourced) |
| Bottleneck | recommendations | No | RM name if not feasible, or supplier lead time for outsourced |
| Actual | targets | No | Updated live as production happens |
| Status | computed | No | Badge: not started / in progress / done / over |

**Outsourced Item Row Differentiation:**
- Action column shows blue "Order" badge instead of green "Produce"
- Feasible column shows "N/A" (no BOM to check)
- Bottleneck column shows "Lead: 14 days" (supplier lead time)
- Shelf life warning icon if `days_inventory > shelf_life * 0.5`

**Shelf Life Cap Indicator:**
- If `shelf_life_cap_applied = true`, show info icon next to Recommended value
- Tooltip: "Capped to prevent expiry — shelf life {N} days, current DI {M} days"

**Interaction:**
- Supervisor edits Target column → deviation auto-computes
- If deviation > 25%, row highlights yellow with warning
- If deviation > 50%, row highlights red — reason becomes mandatory
- "Save Targets" calls `set_production_targets()` with all edited rows
- "Reset to Recommended" resets all target values to recommended values

**HARD BLOCKER:** The "Recommended" column is ALWAYS server-calculated and read-only on the frontend. Frontend NEVER computes recommendations. (Source: CEO anti-manipulation requirement)

### P2-3: RM Requirements tab (3 units)
**[BUILD]** — Shows RM needed to fulfill the current targets.

**Layout:**
```
┌──────────────────────────────────────────────────┐
│ Raw Material Requirements for [Date]             │
│                                                  │
│ [All Sufficient ✓] [3 Deficits ✗]               │
│                                                  │
│ RM Code | RM Name    | Required | Stock | Status │
│ RM-015  | Gulaman P. | 45 kg    | 60 kg | ✓     │
│ RM-022  | Coconut    | 40 kg    | 25 kg | ✗-15  │
│ ...                                              │
│                                                  │
│ Blocked Items: FG006, FG009 (Coconut shortage)   │
└──────────────────────────────────────────────────┘
```

Calls `get_rm_requirements_for_plan()` with current target values.

Auto-refreshes when targets are changed (debounced 1s).

### P2-4: Summary stat cards + capacity warning (2 units)
**[BUILD]** — Five stat cards at the top:
1. **Total Recommended** — sum of all recommended_qty (in-house items only)
2. **Total Targeted** — sum of all target_qty (in-house items only)
3. **Total Produced** — sum of actual_produced (live from SEs)
4. **Completion %** — total_produced / total_targeted * 100
5. **Capacity** — total_targeted_kg / daily_capacity * 100% (from MANCOM data: ~950 kg/day practical)

Color coding for Completion: <50% = red, 50-80% = yellow, >80% = green
Color coding for Capacity: <80% = green, 80-100% = yellow, >100% = red with warning "Exceeds estimated daily capacity"

**Capacity calculation:** `daily_capacity = 950` kg (derived from MANCOM productivity data: ~50 kg/hr × ~19 productive manhours/day). This is a static estimate. If BEI Weekly Labor Plan is available for the date, use actual scheduled manhours × 50 kg/hr instead.

### P2-5: Navigation entry + RBAC (2 units)
**[EXTEND]** — Add "Production Planning" to commissary sidebar in bei-tasks.

**RBAC (bei-tasks/lib/roles.ts):**
- Commissary User: full access (read + write targets)
- Commissary Manager: full access
- CEO / Executive: read-only (cannot edit targets)
- All others: hidden

---

## Phase 3: CEO Audit View (8 units)

### P3-1: `get_production_audit_trail()` endpoint (2 units)
**[BUILD]** — Returns all target changes with recommended vs target comparison.

**Input:** `date_from`, `date_to`, `item_code?`

**Returns:**
```json
{
  "entries": [
    {
      "production_date": "2026-03-27",
      "item_code": "FG004",
      "item_name": "GULAMAN PANDAN",
      "recommended_qty": 22.5,
      "final_target_qty": 30.0,
      "actual_produced": 28.0,
      "deviation_pct": 33.3,
      "completion_pct": 93.3,
      "adjustments": [
        {
          "action": "set",
          "previous": 0,
          "new": 30,
          "reason": "extra demand from Shaw",
          "by": "commissary.team@bebang.ph",
          "at": "2026-03-27 06:15:00"
        }
      ]
    }
  ],
  "summary": {
    "avg_deviation_pct": 18.2,
    "items_over_target": 3,
    "items_under_target": 5,
    "items_on_target": 12,
    "overall_completion_pct": 85.4
  }
}
```

### P3-2: `get_production_performance_summary()` endpoint (2 units)
**[BUILD]** — Weekly/monthly rollup for CEO reporting.

**Input:** `period` (week/month), `date?`

**Returns:**
```json
{
  "period": "2026-W13",
  "daily_breakdown": [
    {
      "date": "2026-03-24",
      "total_recommended": 180,
      "total_targeted": 195,
      "total_produced": 170,
      "deviation_pct": 8.3,
      "completion_pct": 87.2
    }
  ],
  "item_breakdown": [
    {
      "item_code": "FG004",
      "total_recommended": 150,
      "total_targeted": 180,
      "total_produced": 165,
      "avg_deviation_pct": 20.0,
      "avg_completion_pct": 91.7,
      "trend": "increasing"
    }
  ],
  "alerts": [
    "FG006: Target consistently 40%+ above recommended (possible manipulation)",
    "FG009: Chronic under-production (completion < 50% for 3 days)"
  ]
}
```

### P3-3: CEO Production Overview page (4 units)
**[BUILD]** — New route: `/dashboard/commissary/production-overview`

**Layout:**
```
┌──────────────────────────────────────────────────────┐
│ Production Overview (CEO View)                       │
│ [This Week ▾] [This Month ▾]                         │
│                                                      │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐    │
│ │Avg Dev %│ │Compltn %│ │Over-Prod│ │Under-Pr │    │
│ │  18.2%  │ │  85.4%  │ │ 3 items │ │ 5 items │    │
│ └─────────┘ └─────────┘ └─────────┘ └─────────┘    │
│                                                      │
│ ┌────────────────────────────────────────────────┐   │
│ │ Daily Trend Chart (Recommended vs Target vs    │   │
│ │ Actual — 3 lines, 7/30 day view)               │   │
│ └────────────────────────────────────────────────┘   │
│                                                      │
│ ┌────────────────────────────────────────────────┐   │
│ │ Item Comparison Table                          │   │
│ │ Item | Rec | Target | Actual | Dev% | Alerts   │   │
│ │ FG004| 150 | 180    | 165    | +20% | ⚠ high  │   │
│ │ FG009|  80 |  40    |  35    | -50% | 🔴 under │   │
│ └────────────────────────────────────────────────┘   │
│                                                      │
│ ┌────────────────────────────────────────────────┐   │
│ │ Adjustment Audit Log                           │   │
│ │ Date | Item | Rec→Target | By | Reason         │   │
│ │ 3/27 | FG004| 22.5→30   | CS | extra demand   │   │
│ └────────────────────────────────────────────────┘   │
│                                                      │
│ [🚩 Alerts]                                          │
│ • FG006: Target 40%+ above recommended (3 days)     │
│ • FG009: Under-production chronic (<50% completion)  │
└──────────────────────────────────────────────────────┘
```

**RBAC:** CEO / Executive role only. Commissary users cannot see this page.

**Alert logic (server-side):**
- **Over-targeting:** `deviation_pct > 30%` for 3+ consecutive days
- **Under-production:** `completion_pct < 50%` for 3+ consecutive days
- **Chronic deviation:** `avg_deviation_pct > 25%` for the period

---

## Phase 4: Connect Store Demand to Commissary (8 units)

### P4-1: `get_store_demand_for_commissary()` endpoint (3 units)
**[BUILD]** — Aggregates store-level demand that the commissary needs to fulfill.

**Data sources:**
1. **Pending Material Requests** — stores that have placed orders
2. **DTL data** — stores where items are below reorder level (from `get_days_inventory()` logic applied per-store)
3. **Historical consumption** — 7-day rolling average per store per item

**Returns:**
```json
{
  "demand_by_item": [
    {
      "item_code": "FG004",
      "item_name": "GULAMAN PANDAN",
      "total_pending_orders": 45.0,
      "total_projected_demand": 62.0,
      "stores_ordering": 8,
      "stores_at_risk": 3,
      "store_breakdown": [
        {"store": "Shaw BLVD", "pending": 10, "di": 1.2, "status": "critical"},
        {"store": "Glorietta", "pending": 8, "di": 2.5, "status": "low"},
        {"store": "SM North", "pending": 0, "di": 0.5, "status": "critical"}
      ]
    }
  ],
  "summary": {
    "total_items_in_demand": 15,
    "total_stores_at_risk": 12,
    "total_pending_order_qty": 320
  }
}
```

### P4-2: Store Demand panel on Planning page (3 units)
**[BUILD]** — New tab on the Planning page: "Store Demand"

Shows per-item which stores need stock, their current DI, and pending orders. Helps supervisor understand WHY the system recommends a certain quantity.

Clicking an item row expands to show store-level breakdown.

### P4-3: Feed store demand into recommendations (2 units)
**[EXTEND]** — Update `get_production_recommendations()` to include store-level demand data:
- `stores_at_risk` count per item
- `highest_priority_store` (store with lowest DI for that item)
- `total_store_demand` (aggregated pending + projected)

This replaces the simple `pending_demand` from Material Requests with a richer signal.

---

## Phase 5: Sentry Instrumentation + Closeout (6 units)

### P5-1: Sentry instrumentation (2 units)
Add `set_backend_observability_context()` to all new endpoints:
- `get_production_recommendations()` — module="commissary", action="get_production_recommendations"
- `set_production_targets()` — module="commissary", action="set_production_targets", mutation_type="create"
- `get_production_targets()` — module="commissary", action="get_production_targets"
- `get_rm_requirements_for_plan()` — module="commissary", action="get_rm_requirements_for_plan"
- `get_production_audit_trail()` — module="commissary", action="get_production_audit_trail"
- `get_production_performance_summary()` — module="commissary", action="get_production_performance_summary"
- `get_store_demand_for_commissary()` — module="commissary", action="get_store_demand_for_commissary"

### P5-2: bei-tasks API routes (1 unit)
Add Next.js API routes in `app/api/commissary/planning/route.ts` for:
- GET: production_recommendations, production_targets, rm_requirements, store_demand
- POST: set_production_targets

### P5-3: Sprint closeout (3 units)
- Update plan YAML: status → COMPLETED, add completed_date, execution_summary
- Update SPRINT_REGISTRY.md with PR numbers and COMPLETED status
- Commit and push both files: `git add -f docs/plans/...`

---

## Rollback Plan

If the new DocTypes or endpoints cause production issues:
1. **Immediate:** Disable all `commissary_planning.py` endpoints by commenting out `@frappe.whitelist()` decorators. Push hotfix.
2. **Frontend:** Hide "Production Planning" and "Production Overview" navigation entries in `bei-tasks/lib/roles.ts` (set module visibility to empty array).
3. **DocType tables remain** in the database but are inert — no data flows to/from them without the API endpoints.
4. **No data loss risk** — these DocTypes are new and contain only planning data. They do not affect existing production, inventory, or ordering workflows.
5. **Full rollback:** Revert the branch merge on production. DocType tables remain as empty artifacts (harmless).

---

## Phase Budget Contract

| Phase | Units | Description |
|-------|-------|-------------|
| Phase 0 | 14 | Backend planning engine — 4 endpoints with product-specific DI, shelf life cap, wastage factor, outsourced detection, savepoint, partial failure handling |
| Phase 1 | 7 | DocTypes (with immutability enforcement, naming, permissions) + production SE hook (submit + cancel + idempotency) + hooks.py registration |
| Phase 2 | 13 | Frontend planning dashboard — with outsourced item differentiation + capacity warning card |
| Phase 3 | 8 | CEO audit view (2 endpoints + page) |
| Phase 4 | 8 | Store demand connection |
| Phase 5 | 7 | Sentry + API routes + closeout |
| **Total** | **57** | |

All phases under 15-unit hard limit. Phase 0 at 14 is acceptable (algorithm complexity, not separate surfaces).

## Scope Size Warning

At 57 units this is within the 80-unit ceiling but on the larger side for a single agent session. User has confirmed single-session execution. If context pressure builds, prioritize Phase 0-2 (core engine + dashboard, 34 units) over Phase 3-4 (CEO view + store demand, 16 units).

---

## Requirements Regression Checklist

- [ ] Is `recommended_qty` computed entirely server-side? (Anti-manipulation requirement)
- [ ] Does the frontend NEVER calculate recommendations? (Anti-manipulation requirement)
- [ ] Is every target adjustment logged immutably with the recommended qty at that moment? (CEO audit trail)
- [ ] Can the CEO see recommended vs target for every item on every day? (CEO visibility)
- [ ] Does the CEO view show alerts for chronic deviation or under-production? (Manipulation detection)
- [ ] Are commissary users blocked from accessing the CEO production overview? (RBAC separation)
- [ ] Does the RM explosion use actual BOM data from Frappe? (Data integrity)
- [ ] Does every new `@frappe.whitelist()` endpoint call `set_backend_observability_context()`? (Sentry DM-7)
- [ ] Are module and action parameters correct for Sentry? (Sentry DM-7)
- [ ] Is the DocType using Link fields (not Data) for item_code and user references? (DM-4)
- [ ] Are outsourced items (no BOM) included but flagged? (Complete item coverage)
- [ ] Does `target_di` use `get_product_threshold(item_code)` instead of a hardcoded default? (Gap Fix #1: product-specific thresholds)
- [ ] Is `recommended_qty` capped at `max_before_expiry` for items with `shelf_life <= 30`? (Gap Fix #2: overproduction prevention)
- [ ] Does the recommendation include `wastage_factor` based on 7-day wastage/production ratio? (Gap Fix #3: wastage-adjusted demand)
- [ ] Do outsourced items show "Order" action with supplier lead time instead of "Produce"? (Gap Fix #4: outsourced differentiation)
- [ ] Does the dashboard show a capacity utilization card with amber warning when > 100%? (Gap Fix #5: capacity awareness)

---

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| test.commissary@bebang.ph | Open `/dashboard/commissary/planning` | Page loads with all 22 FG items, each showing recommended qty based on consumption data. FG001/FG002 show "Order" badge, others show "Produce" badge. | Recommendation engine or outsourced detection broken |
| test.commissary@bebang.ph | Verify FG001 (Leche Flan) row | Shows action="Order", target_di=7, shelf_life=15, feasible=N/A, bottleneck shows lead time. Recommended qty is shelf-life-capped. | Gap Fix #2 or #4 not working |
| test.commissary@bebang.ph | Verify FG004 (Gulaman Pandan) row | Shows action="Produce", target_di=30 (not 3 or 100), shelf_life=180. No shelf life cap. | Gap Fix #1 (product-specific DI) broken |
| test.commissary@bebang.ph | Check capacity card when total target is reasonable | Capacity card shows green (<80%) or yellow (80-100%). Value based on ~950 kg/day. | Gap Fix #5 not working |
| test.commissary@bebang.ph | Edit FG004 target from recommended to +30%, add reason "extra demand from Shaw" → click Save Targets | Success toast, targets saved. Deviation shows +30%, row highlights yellow. | set_production_targets endpoint broken |
| test.commissary@bebang.ph | Edit FG006 target to 50% above recommended WITHOUT adding reason → click Save | Validation error: reason required when deviation > 10% | Deviation validation broken |
| test.commissary@bebang.ph | Click "RM Requirements" tab | Shows all RM needed for current targets, with surplus/deficit per RM, blocked items listed | BOM explosion broken |
| test.commissary@bebang.ph | Change FG006 target to 999 (way above feasible) | RM tab shows deficit, FG006 row shows red "not feasible", capacity card turns red (>100%) | Feasibility or capacity check broken |
| test.commissary@bebang.ph | Click "Reset to Recommended" → Save | All targets reset to recommended values, deviation = 0% for all items | Reset logic broken |
| test.commissary@bebang.ph | Click "Store Demand" tab | Shows per-item store breakdown with pending orders and DI per store | Store demand connection broken |
| CEO (sam@bebang.ph) | Open `/dashboard/commissary/production-overview` | Shows weekly summary with recommended vs target vs actual, deviation %, alerts | CEO view broken |
| CEO (sam@bebang.ph) | Verify adjustment log shows commissary.team's changes | Log shows FG004: rec→target with reason, timestamp, user | Audit trail broken |
| test.commissary@bebang.ph | Try to open `/dashboard/commissary/production-overview` | Access denied or page not visible in navigation | RBAC leaking CEO view to commissary |

---

## Build Integrity Gates

| Gate | Description |
|------|-------------|
| `gate_route_contract_defined` | `/dashboard/commissary/planning` and `/dashboard/commissary/production-overview` routes defined |
| `gate_action_wiring_complete` | Save Targets button → POST set_production_targets → success toast + refresh |
| `gate_dependency_map_complete` | Planning page depends on: get_production_recommendations, get_production_targets, get_rm_requirements_for_plan |
| `gate_navigation_placement_defined` | "Production Planning" in commissary sidebar, "Production Overview" in CEO section |
| `gate_empty_error_states_defined` | Empty state for: no production history (first use), no targets set, no RM data |
| `gate_mutation_outcomes_defined` | set_production_targets: creates DocType + log entries, returns confirmation |
| `gate_mobile_layout_defined` | Planning table responsive: card view on mobile with key columns |
| `gate_seed_dependency_defined` | Requires: FG items with BOMs (22 items, all have BOMs from S126/S131) |

---

## Anti-Rewind / Concurrent-Run Protection

- **Owned files (new):** `hrms/api/commissary_planning.py`, `bei-tasks/app/dashboard/commissary/planning/`, `bei-tasks/app/dashboard/commissary/production-overview/`
- **Protected surfaces (do not touch):** `hrms/api/commissary_dashboard.py` (except P1-3 hook into submit_production_output), `hrms/api/commissary_requisition.py`, `hrms/api/commissary_bom.py`, all existing commissary frontend pages
- **Extend-only:** `bei-tasks/lib/roles.ts` (add planning routes), `bei-tasks/app/api/commissary/` (add planning route)

---

## Autonomous Execution Contract

```yaml
completion_condition:
  - All 7 backend endpoints return correct data
  - Both DocTypes created and functional
  - Planning page loads with recommendations for all 22 FG items
  - CEO overview page shows recommended vs target comparison
  - RBAC enforced (commissary can't see CEO view)
  - Sentry instrumented on all endpoints
  - Plan YAML status updated to COMPLETED
  - SPRINT_REGISTRY.md updated to COMPLETED with PR numbers
stop_only_for:
  - Missing Doppler credentials for Frappe API
  - DocType migration failure requiring manual intervention
  - Frappe version incompatibility with new DocType fields
  - Direct conflict with concurrent S126/S131 changes
continue_without_pause_through:
  - Phase transitions
  - PR creation
  - Deploy monitoring
  - L3 testing
blocker_policy:
  programmatic: fix and continue
  environment: debug and continue
  business_policy: pause and ask
signoff_authority: single-owner (Sam)
canonical_closeout_artifacts:
  - output/l3/S137/form_submissions.json
  - output/l3/S137/api_mutations.json
  - output/l3/S137/state_verification.json
  - docs/plans/2026-03-27-sprint-137-commissary-production-planning.md
  - docs/plans/SPRINT_REGISTRY.md
```

---

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branch:** `git fetch origin production && git checkout -b s137-commissary-production-planning origin/production`. NEVER write code on production.
3. Read `docs/plans/SPRINT_REGISTRY.md` for cross-sprint context.
4. Read `hrms/api/commissary_dashboard.py` — understand existing production endpoints.
5. Read `hrms/api/commissary_requisition.py` — understand suggestion + RM alert logic.
6. Read `hrms/api/commissary_bom.py` — understand feasibility check.
7. Read `hrms/api/commissary.py` lines 1247-1382 — understand `get_days_inventory()`.
8. Read `bei-tasks/lib/roles.ts` — understand current RBAC structure.
9. Confirm all 22 FG items have BOMs before starting.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

## Execution Workflow
- Test Python changes: `/local-frappe`
- Deploy changes: `/deploy-frappe`
- Full workflow: `/agent-kickoff` (reads all required skills automatically)
- E2E testing: `/e2e-test` or `/test-full-cycle`

---

## Audit History

### Audit v1 (2026-03-27) — 5-domain + code verification
**Status:** NO-GO → **GO after amendments applied**
**Agents:** Frappe Backend, Frontend, Deployment QA, System Architecture, Design Review + Code Verifier
**Findings:** 13 CRITICAL, 32 WARNING, 22 INFO, 3 NEW GAPS (code verifier)
**Blockers resolved (10/10):**
1. DocType vs Flat-JSON contradiction → **FIXED** (removed contradictory paragraph, rationale updated)
2. Immutability not enforced → **FIXED** (added `before_save`/`on_trash` overrides, `autoname="hash"`, permission matrix)
3. Multi-doc write without savepoint → **FIXED** (added `frappe.db.savepoint("set_targets")` to P0-2)
4. Stored computed fields without cancel hook → **FIXED** (added `on_cancel` to P1-3, `hooks.py` registration)
5. No Docker full build instruction → **FIXED** (added note to P1-1)
6. DocType schema incomplete → **FIXED** (added autoname, is_submittable, permission matrix to both DocTypes)
7. Division-by-zero in 4 places → **FIXED** (guards added to algorithm + DocType `validate()`)
8. PRODUCT_THRESHOLDS covers ~10 items → **FIXED** (acknowledged in algorithm, defaults documented)
9. No rollback plan → **FIXED** (Rollback Plan section added)
10. Partial failure undefined → **FIXED** (partial success response in P0-2)

**Code verifier NEW GAPs resolved:**
- Line number references corrected (commissary.py:143→146, :1128→1129)
- "FG001-FG022" hardcoded range → changed to "all active FG items (dynamic SQL)"
- PRODUCT_THRESHOLDS coverage gap acknowledged with default values

**Full findings:** `output/plan-audit/s137-commissary-production-planning/`
**Verdict after amendments:** GO
