# S161: Store Ordering Page Cleanup — Frozen/Dry Tabs, Hide Irrelevant Items, Merge Variants, UOM Conversion

```yaml
sprint: S161
branch: s161-store-ordering-cleanup
status: PR_CREATED
planned_date: 2026-04-05
completed_date:
execution_started: 2026-04-05
execution_summary: "All 4 waves implemented. Backend: get_orderable_items() extended with last_order_date, hidden_count, delivery_lane, variant merge, UOM conversion. submit_order() handles reverse UOM conversion. Frontend: Frozen/Dry tabs, display_uom, hidden item count."
plan_file: docs/plans/2026-04-05-sprint-161-store-ordering-cleanup.md
registry_row: "| `S161` | Sprint 161 | `s161-store-ordering-cleanup` | — | PLANNED — Store ordering UX cleanup: Frozen/Dry tabs, hide irrelevant items, merge variants, UOM conversion. | `docs/plans/2026-04-05-sprint-161-store-ordering-cleanup.md` |"
repos: hrms (backend), bei-tasks (frontend)
depends_on: S154 (store ordering production ready), S155 (SCM integration pipeline)
```

---

## Context

The store ordering page at my.bebang.ph shows ~128 items per store with 6 unrelated category tabs (Toppings, Frozen, Sauces, Packaging, Supplies, Other), duplicate variants (LECHE FLAN appears as both FG001-B and FG001), warehouse-centric UOMs (BOX, BUNDLE instead of PIECE), and items that no store has ever ordered cluttering the list.

Deliveries are already split into **Frozen** (cold chain) and **Dry** lanes — the backend infrastructure (`_resolve_delivery_lane()`, `_lane_to_cargo_category()`, delivery schedule banners) exists but the ordering UI doesn't surface it. CEO directive: simplify to 2 tabs matching the delivery model, hide noise, merge duplicates, convert UOMs.

**Why now:** S154 made the ordering system production-ready. S155 wired the SCM integration pipeline. This sprint polishes the store-facing experience so store supervisors see only what they need.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              get_orderable_items() flow                          │
│              hrms/api/store.py:2198                              │
├─────────────────────────────────────────────────────────────────┤
│  SQL query (L2220)                                               │
│    ├── ADD: MAX(so.order_date) as last_order_date   ◄── Wave 1A │
│    ├── ADD: i.variant_of                            ◄── Wave 3A │
│    └── ADD: custom_store_ordering_uom               ◄── Wave 4B │
│                                                                  │
│  NEW: Variant merge step (after query)              ◄── Wave 3B │
│    Group by variant_of, sum ATP, pick display item               │
│                                                                  │
│  Enrichment loop (L2308)                                         │
│    ├── ADD: delivery_lane = Frozen|Dry              ◄── Wave 2A │
│    ├── ADD: UOM conversion (display_uom, cf)        ◄── Wave 4C │
│    └── FIX: KG rounding in _round_suggested_qty     ◄── Wave 1C │
│                                                                  │
│  Post-sort filter (after L2427)                     ◄── Wave 1B │
│    Split into visible + hidden by relevance                      │
│                                                                  │
│  submit_order() (L2573)                                          │
│    └── ADD: Reverse UOM conversion                  ◄── Wave 4D │
│                                                                  │
│  Response: items + hidden_count + delivery_lane                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Design Rationale (For Cold-Start Agents)

### Why this exists
CEO (Sam) reviewed the Araneta Gateway ordering page and identified 5 problems: wrong category tabs, too many items, duplicate variants, bulk UOMs, and impractical rounding. The root cause is that `get_orderable_items()` was designed to return everything and let the frontend filter — but the frontend filters don't match the delivery model.

### Why Frozen/Dry tabs (not the current 6 categories)
Deliveries are physically split into cold chain trucks and dry goods trucks. Store supervisors think in "what's coming on the frozen truck vs dry truck." The existing `_resolve_delivery_lane()` at store.py:1545 and `_lane_to_cargo_category()` at store.py:1262 already classify every item. The 6 `custom_store_category` values (Toppings, Frozen, Sauces, etc.) don't map to delivery logistics. CEO confirmed: remove them entirely, don't keep as sub-filters.

### Why merge variants (not hide by flag)
CEO chose "merge variants in UI" over `custom_store_orderable` flag. Merging is cleaner: stock from FG001-B (16-pack) and FG001 (single) is summed, and the most-ordered variant becomes the display item. The flag approach (`custom_store_orderable`) is kept as a fallback for non-variant duplicates.

### Why include UOM conversion now (not defer)
CEO chose to include UOM conversion in this sprint despite higher complexity. The practical impact is significant: stores ordering "0 BOX" makes no sense when they think in PIECE. Frappe's built-in `UOM Conversion Detail` child table provides the storage mechanism.

### Key trade-offs
1. **Fresh Market (FM) → Dry**: FM items travel on dry trucks, so FM maps to the "Dry" tab. No separate FM tab.
2. **30-day cutoff for hiding**: Items with zero source ATP AND no orders in 30 days are hidden. The 30-day window is configurable but starts there.
3. **Variant merge by `variant_of`**: Uses Frappe's built-in variant field. Items without `variant_of` but logically duplicate (same name, different code) are handled by the `custom_store_orderable` flag.

---

## Duplication Audit

| Feature | Classification | Existing Code |
|---------|---------------|---------------|
| Delivery lane classification | **[EXTEND]** | `_resolve_delivery_lane()` at store.py:1545, `_lane_to_cargo_category()` at store.py:1262 — add `delivery_lane` display field |
| Item filtering by relevance | **[BUILD]** | No existing relevance filter — `get_orderable_items()` returns all enabled items |
| Variant merging | **[BUILD]** | No existing variant merge logic in ordering |
| UOM conversion | **[EXTEND]** | Frappe built-in `UOM Conversion Detail` exists; need to wire it into ordering |
| Category tabs | **[EXTEND]** | `STORE_CATEGORIES` at StoreOrderingPage.tsx:26 — replace values |
| KG rounding | **[EXTEND]** | `_round_suggested_qty()` at store.py:~1724 — add UOMs to set |
| `custom_store_orderable` flag | **[BUILD]** | No existing flag on Item doctype |

---

## Critical Files to Modify

| File | Repo | Waves | Changes |
|------|------|-------|---------|
| `hrms/api/store.py` | hrms | 1-4 | Core: filter, lane, merge, UOM convert |
| `hrms/hr/doctype/bei_store_order_item/bei_store_order_item.json` | hrms | 4 | Add `qty_in_store_uom`, `store_uom` fields |
| `app/dashboard/store-ops/ordering/_components/StoreOrderingPage.tsx` | bei-tasks | 2 | Replace 6-tab categories with Frozen/Dry |
| `hooks/use-store-ordering.ts` | bei-tasks | 2, 4 | Add delivery_lane, display_uom to types |
| `app/dashboard/store-ops/ordering/_components/OrderItemTable.tsx` | bei-tasks | 4 | Display store UOM |
| `app/dashboard/store-ops/ordering/_components/OrderItemCard.tsx` | bei-tasks | 4 | Display store UOM on mobile |

## Existing Code to Reuse (DO NOT DUPLICATE)

| Function | Location | Purpose |
|----------|----------|---------|
| `_resolve_delivery_lane()` | store.py:1545 | Already classifies items → Frozen/Fresh Market/Dry |
| `_lane_to_cargo_category()` | store.py:1262 | Maps lane → FC/DRY/FM |
| `_round_suggested_qty()` | store.py:~1724 | Extend for KG; reuse for UOM-converted values |
| `_build_orderable_source_stock_context()` | store.py:~1502 | Provides stock_map, lane_by_item — reuse for variant merge |
| Frappe `UOM Conversion Detail` | Built-in Item child table | Standard conversion factor storage |
| `normalizeOrderableItem()` | bei-tasks `app/api/ordering/route.ts` | Extend for new fields |

## Functions That MUST NOT Break

| Function | Location | Called At | Why |
|----------|----------|-----------|-----|
| `get_orderable_items()` | store.py:2198 | API route, ordering page | Core ordering data — changes must be backwards-compatible |
| `submit_order()` | store.py:2573 | Order submission | Must accept both old format (no conversion_factor) and new |
| `_build_orderable_source_stock_context()` | store.py:~1502 | get_orderable_items L2291 | Stock resolution — do not change return shape |
| `_resolve_delivery_lane()` | store.py:1545 | get_orderable_items L2313 | Lane classification — extend, don't replace |
| `_round_suggested_qty()` | store.py:~1724 | get_orderable_items L2395-2396 | Rounding — only add UOMs to the set |

---

## Shell Prevention (S026)

### Failure patterns to prevent
- **Dead tab filter**: Frozen/Dry tabs render but filter logic still uses `store_category` → items don't filter correctly
- **Missing backend field**: Frontend filters on `delivery_lane` but backend doesn't return it → all items show in "All" only
- **Broken order submission**: UOM conversion changes break `submit_order()` for stores still on old frontend version
- **Hidden items panic**: Stores can't find items they need because the 30-day cutoff is too aggressive

### Build Integrity Gates

| Gate | Status | Evidence |
|------|--------|----------|
| `gate_route_contract_defined` | Defined | No new routes — modifies existing `/dashboard/store-ops/ordering` |
| `gate_action_wiring_complete` | Required | "Show all items" toggle must call API with `include_hidden=1` |
| `gate_dependency_map_complete` | Required | Wave 4 depends on Frappe custom fields existing |
| `gate_navigation_placement_defined` | N/A | No new nav items |
| `gate_empty_error_states_defined` | Required | What shows when ALL items are hidden (empty state) |
| `gate_mutation_outcomes_defined` | Required | `submit_order()` with UOM conversion must produce correct `qty_requested` |
| `gate_mobile_layout_defined` | Required | `OrderItemCard.tsx` must show `display_uom` |
| `gate_seed_dependency_defined` | Required | `custom_store_ordering_uom` and UOM Conversion Detail rows must be populated |

### Vertical slice first
Implement Wave 1 (hide irrelevant) + Wave 2A (backend delivery_lane) first. This is the minimal vertical slice that proves the filtering and lane classification work end-to-end before adding complexity (variant merge, UOM conversion).

---

## Wave 1: Hide Irrelevant Items + KG Rounding (Backend Only)

**Estimated units: 8**

### Task 1A: Add `last_order_date` to frequency subquery
**File:** `hrms/api/store.py` L2228-2234

Change the freq subquery to return `MAX(so.order_date) as last_order_date`. Add to outer SELECT. Pass through to each item dict in enrichment loop.

```
MUST_MODIFY: hrms/api/store.py
MUST_CONTAIN: "last_order_date"
```

### Task 1B: Post-loop relevance filter
**File:** `hrms/api/store.py` after L2427

Add `include_hidden` param to function signature (default `0`). After the sort, split items into visible vs hidden:
- **Keep visible if:** `available_to_promise > 0` OR last ordered within 30 days
- **Hide if:** source ATP ≤ 0 AND (never ordered OR last order > 30 days ago)
- Return `hidden_count` in response dict. If `include_hidden=1`, return all items.

```
MUST_MODIFY: hrms/api/store.py
MUST_CONTAIN: "hidden_count"
MUST_CONTAIN: "include_hidden"
```

### Task 1C: Fix KG rounding
**File:** `hrms/api/store.py` `_round_suggested_qty()` (~L1724)

Add mass/volume UOMs to `_INTEGER_UOMS`: `"Kg", "KG", "Kilogram", "Liter", "L"`. These round up via `math.ceil()`.

```
MUST_MODIFY: hrms/api/store.py
MUST_CONTAIN: '"Kg"' or '"KG"' in _INTEGER_UOMS
```

---

## Wave 2: Frozen/Dry Tabs (Backend + Frontend)

**Estimated units: 10**

### Task 2A: Backend — Add `delivery_lane` field
**File:** `hrms/api/store.py` enrichment loop, after L2377

The lane is already computed at L2313. Add: `item["delivery_lane"] = "Frozen" if item["cargo_category"] == "FC" else "Dry"`. FM maps to "Dry".

```
MUST_MODIFY: hrms/api/store.py
MUST_CONTAIN: "delivery_lane"
```

### Task 2B: Frontend — Replace category tabs
**File:** `bei-tasks/app/dashboard/store-ops/ordering/_components/StoreOrderingPage.tsx`

- Change `STORE_CATEGORIES` from `["All", "Toppings", "Frozen", "Sauces", "Packaging", "Supplies", "Other"]` to `["All", "Frozen", "Dry"]`
- Change filter at L115-117 from `i.store_category` to `i.delivery_lane`
- Update badge counts to count zero-stock items per `delivery_lane` instead of `store_category`
- Rename `storeCategoryTab` to `deliveryLaneTab` or equivalent

```
MUST_MODIFY: bei-tasks/app/dashboard/store-ops/ordering/_components/StoreOrderingPage.tsx
MUST_CONTAIN: '"Frozen", "Dry"'
MUST_NOT_CONTAIN: '"Toppings", "Frozen", "Sauces"'
```

### Task 2C: Frontend — Add "Show all items" toggle
**File:** `bei-tasks/app/dashboard/store-ops/ordering/_components/StoreOrderingPage.tsx`

Add a link/toggle below the item list: "Show all items (N hidden)". When toggled, re-fetch with `include_hidden=1` or merge hidden items. Hidden items render with muted styling and a "No recent orders" tag.

**Empty state:** If ALL items are hidden after filtering, show: "No items match this filter. Try 'Show all items' to see hidden items."

```
MUST_MODIFY: bei-tasks/app/dashboard/store-ops/ordering/_components/StoreOrderingPage.tsx
MUST_CONTAIN: "hidden"
```

### Task 2D: Frontend — Update types
**File:** `bei-tasks/hooks/use-store-ordering.ts`

Add `delivery_lane: string` and `display_uom: string` to `StoreOrderItem` interface.

```
MUST_MODIFY: bei-tasks/hooks/use-store-ordering.ts
MUST_CONTAIN: "delivery_lane"
```

---

## Wave 3: Merge Variant Items (Backend)

**Estimated units: 12**

### Task 3A: Fetch variant relationships
**File:** `hrms/api/store.py` — main SQL SELECT at L2222

Add `i.variant_of` to the SELECT. Build a variant_groups map after the query.

```
MUST_MODIFY: hrms/api/store.py
MUST_CONTAIN: "variant_of"
```

### Task 3B: Merge variant stock and pick display item
After building variant_groups, before the enrichment loop:
1. For each group of variants sharing `variant_of`, combine stock (sum ATP + store_actual from stock_map/store_stock_map)
2. Pick the most-ordered variant as display item (highest `order_count`, prefer non-bulk UOM on tie)
3. Set `merged_variants` list on display item
4. Remove non-display variants from items list

**HARD BLOCKER:** This step modifies `stock_map` and `store_stock_map` BEFORE the enrichment loop reads them. The merge must happen between the main query and the enrichment loop (between L2303 and L2308), not after.

```
MUST_MODIFY: hrms/api/store.py
MUST_CONTAIN: "merged_variants"
```

### Task 3C: `custom_store_orderable` flag (fallback)
Add `custom_store_orderable` Check field on Item doctype (default 1). Add to WHERE clause at L2235: `AND COALESCE(i.custom_store_orderable, 1) = 1`. This handles non-variant duplicates that can't be auto-merged.

```
MUST_MODIFY: hrms/api/store.py
MUST_CONTAIN: "custom_store_orderable"
```

---

## Wave 4: UOM Conversion (Backend + Frontend)

**Estimated units: 15**

### Task 4A: Add `custom_store_ordering_uom` custom field
Add to Item doctype via Customize Form or fixture:
- Fieldname: `custom_store_ordering_uom`
- Fieldtype: Link
- Options: UOM
- Label: "Store Ordering UOM"
- insert_after: `stock_uom`
- Default: empty (falls back to stock_uom)

### Task 4B: Fetch conversion factors
**File:** `hrms/api/store.py` — in `get_orderable_items()`, after main query

Add `COALESCE(i.custom_store_ordering_uom, i.stock_uom) as store_ordering_uom` to main SQL SELECT at L2222. Batch-fetch `tabUOM Conversion Detail` rows:

```sql
SELECT parent as item_code, uom, conversion_factor
FROM `tabUOM Conversion Detail`
WHERE parenttype = 'Item' AND parent IN %(item_codes)s
```

Build `uom_cf_map: {(item_code, uom): conversion_factor}`.

```
MUST_MODIFY: hrms/api/store.py
MUST_CONTAIN: "store_ordering_uom"
MUST_CONTAIN: "UOM Conversion Detail"
```

### Task 4C: Convert quantities in enrichment loop
For items where `store_ordering_uom != stock_uom` and conversion_factor > 1:
- `available_to_promise *= cf`
- `store_actual_qty *= cf`
- `suggested_qty *= cf` (then re-round with `_round_suggested_qty`)
- `recommended_qty *= cf` (then re-round)
- Set `item["display_uom"] = store_uom`, `item["conversion_factor"] = cf`

Default: if no conversion found, `cf = 1.0` and `display_uom = stock_uom`.

```
MUST_MODIFY: hrms/api/store.py
MUST_CONTAIN: "display_uom"
MUST_CONTAIN: "conversion_factor"
```

### Task 4D: Reverse conversion on submit
**File:** `hrms/api/store.py` — `submit_order()` L2573+

When saving `BEI Store Order Item`, if `conversion_factor` is provided and != 1:
- `qty_requested = qty_from_frontend / conversion_factor` (stock UOM)
- Save `qty_in_store_uom` (store UOM) and `store_uom` on the order item for audit

Add fields to BEI Store Order Item doctype (`bei_store_order_item.json`):
- `qty_in_store_uom`: Float, label "Qty (Store UOM)"
- `store_uom`: Link → UOM, label "Store UOM"

**HARD BLOCKER:** Must be backwards-compatible. If no `conversion_factor` sent (old frontend), treat as 1.0. Never break existing order submission.

```
MUST_MODIFY: hrms/api/store.py
MUST_MODIFY: hrms/hr/doctype/bei_store_order_item/bei_store_order_item.json
MUST_CONTAIN: "qty_in_store_uom"
```

### Task 4E: Frontend — Display store UOM
**Files:** `OrderItemTable.tsx`, `OrderItemCard.tsx`, `OrderReviewSheet.tsx`

Use `item.display_uom` instead of `item.uom` for all quantity displays. Pass `conversion_factor` and `display_uom` back on order submit.

```
MUST_MODIFY: bei-tasks/app/dashboard/store-ops/ordering/_components/OrderItemTable.tsx
MUST_MODIFY: bei-tasks/app/dashboard/store-ops/ordering/_components/OrderItemCard.tsx
MUST_CONTAIN: "display_uom"
```

### Task 4F: Data population (one-time, post-deploy)
Script to set `custom_store_ordering_uom` for items where stores order differently. Requires ops input on per-item basis. This is a data task, not a code task — code ships with safe defaults (cf=1).

---

## Sentry Observability

All modifications to `get_orderable_items()` are within an existing `@frappe.whitelist()` that already calls `set_backend_observability_context(module="ordering", action="get_orderable_items")` at L2206. No new endpoints are added.

If `submit_order()` is modified (Wave 4D), verify it already has `set_backend_observability_context()`. If not, add: `set_backend_observability_context(module="ordering", action="submit_order", mutation_type="create")`.

---

## Requirements Regression Checklist

- [ ] Are category tabs exactly `["All", "Frozen", "Dry"]` — no Toppings/Sauces/Packaging/Supplies/Other?
- [ ] Does FM (Fresh Market) map to "Dry" tab (not its own tab)?
- [ ] Are items hidden only when source ATP ≤ 0 AND (never ordered OR last order > 30 days)?
- [ ] Is there a "Show all items" toggle that reveals hidden items?
- [ ] Do variant groups merge stock (sum ATP) and show the most-ordered variant?
- [ ] Is `custom_store_orderable` default 1 (existing items remain visible)?
- [ ] Does UOM conversion use Frappe's built-in `UOM Conversion Detail` (not custom table)?
- [ ] Does `submit_order()` accept orders without `conversion_factor` (backwards-compatible)?
- [ ] Does every new/modified `@frappe.whitelist()` endpoint call `set_backend_observability_context()`?
- [ ] Are KG/Kilogram items rounded to whole numbers via `math.ceil()`?
- [ ] Is the variant merge placed BEFORE the enrichment loop (between L2303 and L2308)?

---

## Zero-Skip Enforcement

Every task MUST be implemented, no exceptions. If a task cannot be completed, the agent STOPS and asks the user.

**Forbidden behaviors:**
- Skipping a task silently
- Marking partial work as "done"
- Replacing a task with a simpler version without user approval
- Saying "deferred to next sprint"
- Combining tasks and dropping features in the merge
- Implementing happy path only, skipping edge cases

**Phase Completion Verification:** After each wave, run this script (not prose checklist):

```bash
#!/bin/bash
# output/s161/verify_waves.sh — run after each wave

echo "=== Wave 1 ==="
echo -n "last_order_date: "; grep -c "last_order_date" hrms/api/store.py
echo -n "hidden_count: "; grep -c "hidden_count" hrms/api/store.py
echo -n "KG rounding: "; grep -c '"Kg"' hrms/api/store.py

echo "=== Wave 2 ==="
echo -n "delivery_lane (backend): "; grep -c "delivery_lane" hrms/api/store.py
echo -n "Frozen/Dry tabs (frontend): "; grep -c '"Frozen", "Dry"' ../bei-tasks/app/dashboard/store-ops/ordering/_components/StoreOrderingPage.tsx 2>/dev/null || echo "N/A (different repo)"

echo "=== Wave 3 ==="
echo -n "variant_of: "; grep -c "variant_of" hrms/api/store.py
echo -n "merged_variants: "; grep -c "merged_variants" hrms/api/store.py

echo "=== Wave 4 ==="
echo -n "display_uom: "; grep -c "display_uom" hrms/api/store.py
echo -n "conversion_factor: "; grep -c "conversion_factor" hrms/api/store.py
echo -n "qty_in_store_uom: "; grep -c "qty_in_store_uom" hrms/api/store.py
```

**FAIL blocks progress:** If any count is 0 for a completed wave, the wave is not done. Fix before proceeding.

---

## Phase Budget Contract

| Wave | Estimated Units | Within Budget? |
|------|----------------|----------------|
| Wave 1 (Hide + Round) | 8 | Yes |
| Wave 2 (Frozen/Dry tabs) | 10 | Yes |
| Wave 3 (Merge variants) | 12 | Yes (at limit) |
| Wave 4 (UOM conversion) | 15 | At ceiling |
| **Total** | **45** | Yes (under 80) |

---

## Autonomous Execution Contract

- **completion_condition:**
  - All 4 waves implemented and verified via grep checks
  - PR created for hrms repo (backend changes)
  - PR created for bei-tasks repo (frontend changes)
  - L3 evidence files committed: `output/l3/s161/form_submissions.json`, `output/l3/s161/api_mutations.json`, `output/l3/s161/state_verification.json`
  - Plan YAML status updated to COMPLETED with `completed_date` and `execution_summary`
  - `docs/plans/SPRINT_REGISTRY.md` row updated to COMPLETED with PR numbers
  - Both files committed and pushed: `git add -f docs/plans/2026-04-05-sprint-161-store-ordering-cleanup.md docs/plans/SPRINT_REGISTRY.md`
- **stop_only_for:**
  - Missing Frappe custom field creation access (need bench console or SSM)
  - `variant_of` field not populated on any items (need data audit first)
  - UOM conversion data not available (need ops input for conversion factors)
  - Merge conflicts with S154/S155/S160 branches
  - Destructive action requiring user approval
- **continue_without_pause_through:** code → test → pr_creation → closeout
- **blocker_policy:**
  - programmatic → fix and continue
  - Frappe migration needed → run `bench migrate` and continue
  - data dependency (UOM conversion factors) → implement code with safe defaults (cf=1), note data population as post-deploy task
  - business-data/policy → pause and ask user
- **signoff_authority:** single-owner (Sam)
- **canonical_closeout_artifacts:**
  - `output/l3/s161/form_submissions.json`
  - `output/l3/s161/api_mutations.json`
  - `output/l3/s161/state_verification.json`
  - `docs/plans/2026-04-05-sprint-161-store-ordering-cleanup.md` (status → COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (row updated)

---

## Signoff Model

- **mode:** single-owner
- **approver_of_record:** Sam (CEO)
- **note:** No department approval required. Sam reviews PRs directly.

---

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branch:** `git fetch origin production && git checkout -b s161-store-ordering-cleanup origin/production`. NEVER write code on production.
3. Read `docs/plans/SPRINT_REGISTRY.md` for cross-sprint context.
4. Read `hrms/api/store.py` lines 2198-2440 (`get_orderable_items`) and lines 1700-1730 (`_round_suggested_qty`).
5. Read `bei-tasks/app/dashboard/store-ops/ordering/_components/StoreOrderingPage.tsx` lines 1-160.
6. Read `bei-tasks/hooks/use-store-ordering.ts` lines 1-70.
7. Implement waves 1-4 in order. Each wave builds on the previous.
8. After all waves: create PRs, update registry, update plan status, commit L3 evidence.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

---

## Execution Workflow

- Test Python changes: `/local-frappe`
- Deploy changes: `/deploy-frappe`
- Full workflow: `/agent-kickoff` (reads all required skills automatically)
- E2E testing: `/e2e-test` or `/test-full-cycle`

> **Note:** Deployment is user-mediated. Builder sessions create PRs; Sam handles merge, deploy trigger, and L1 smoke. See `/workflow` for the current deployment model.

---

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| test.storesup@bebang.ph | Open ordering page for Araneta Gateway | Tabs show "All", "Frozen", "Dry" — NOT Toppings/Sauces/etc. Item count < 128. | Wave 1 filter or Wave 2 tabs not working |
| test.storesup@bebang.ph | Click "Frozen" tab | Only items with cargo_category=FC shown. Count < total items. | delivery_lane filter broken |
| test.storesup@bebang.ph | Click "Dry" tab | Only DRY+FM items shown. FM items appear under Dry. | FM→Dry mapping broken |
| test.storesup@bebang.ph | Check item count on "All" tab vs old count | Significantly fewer than 128 items (hidden_count > 0 in API response) | Wave 1 relevance filter not applied |
| test.storesup@bebang.ph | Click "Show all items" toggle | Hidden items appear with muted/dimmed styling | Toggle not implemented or not wired to include_hidden |
| test.storesup@bebang.ph | Search "LECHE FLAN" in search bar | Only 1 result (not 2). Shows merged stock from both FG001 and FG001-B. | Variant merge broken or not applied |
| test.storesup@bebang.ph | Check BANANA CINNAMON (KG item) suggested qty | Whole number (e.g., 11 KG not 10.71 KG) | KG rounding not added to _INTEGER_UOMS |
| test.storesup@bebang.ph | Check a converted-UOM item (if data populated) | Shows PIECE not BOX, with converted quantities | UOM conversion not applied |
| test.storesup@bebang.ph | Fill suggested → Review → Submit dry order | Order submitted successfully, appears in approval queue with correct qtys | submit_order backwards compat broken |

### L3 Evidence Files (Required Before Closeout)

```
output/l3/s161/form_submissions.json
output/l3/s161/api_mutations.json
output/l3/s161/state_verification.json
```

**Recommendation:** For 45 total work units, run L3 in a fresh agent session to avoid context-exhaustion bias.

---

## Closeout Phase (Mandatory)

After all waves are implemented and L3 evidence is collected:

1. Update this plan's YAML: `status: COMPLETED`, fill `completed_date` and `execution_summary`
2. Update `docs/plans/SPRINT_REGISTRY.md` S161 row with COMPLETED status and PR numbers
3. Commit both: `git add -f docs/plans/2026-04-05-sprint-161-store-ordering-cleanup.md docs/plans/SPRINT_REGISTRY.md && git commit -m "docs: S161 closeout — update plan and registry"`
4. Push to branch

---

## Verification Summary

1. **Wave 1:** `get_orderable_items` for Araneta Gateway returns fewer items + `hidden_count > 0`. KG items show whole-number suggestions.
2. **Wave 2:** Each item has `delivery_lane` = "Frozen" or "Dry". Frontend tabs are "All / Frozen / Dry". No Toppings/Sauces/etc.
3. **Wave 3:** LECHE FLAN (FG001 + FG001-B) → single entry with combined ATP and `merged_variants` list.
4. **Wave 4:** Items with `custom_store_ordering_uom` show converted quantities. Submit order → `BEI Store Order Item` has correct stock_uom qty in `qty_requested` and store-uom qty in `qty_in_store_uom`.

**E2E:** Use test store account → place order after each wave → verify order appears in approval queue with correct items/quantities/UOMs.
