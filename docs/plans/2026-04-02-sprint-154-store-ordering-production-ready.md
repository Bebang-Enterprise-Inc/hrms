---
canonical_sprint_id: S154
display: Sprint 154
status: PR_CREATED
branch: s154-store-ordering-production-ready
lane: single
created_date: 2026-04-02
completed_date:
deployed_at:
backend_pr: 417
frontend_pr: 305
l3_result:
execution_started: 2026-04-02
execution_summary: Phase 1-5 implemented. Backend PR #417 (hrms), Frontend PR #305 (BEI-Tasks). L3 pending in separate session.
depends_on: S136
---

# S154 — Store Ordering Production-Ready

**Goal:** Make the store ordering page usable for real store crews. After this sprint, a crew member opens the page, sees ONLY the ~106 items they actually order (no raw materials), organized by category (Toppings/Frozen/Sauces/Packaging/Supplies/Other), with BOM-based demand projections that account for weather and delivery schedule, and can submit with a visible sticky button.

**Origin:** CEO hands-on review of live ordering page (2026-04-02). 12 defects confirmed via L3 testing. Brainstorm session decisions documented below.

---

## Brainstorm Decisions (2026-04-02 — CEO + Claude)

### BD-1: Item filtering — Category tabs, NOT hiding filters
- **Problem:** 240 items shown, only ~106 are orderable by stores. 100 Raw Materials (commissary ingredients) pollute the list.
- **Decision:** Filter out Raw Materials + Fixed Assets via SQL WHERE clause on `item_group`. Show remaining ~134 items organized in **6 category tabs** with reorder badge counts.
- **Rationale:** CEO raised that store employees are not tech-savvy and currently use Google Sheets. A filter that hides items will cause blame ("I didn't see it, so I didn't order it"). Category tabs show EVERYTHING — nothing is hidden — but organized so crews find items in 3 seconds.
- **Categories:** Toppings & Ingredients, Frozen Products, Sauces & Syrups, Cups & Packaging, Cleaning & Supplies, Other
- **Implementation:** Add `store_category` custom field on Item DocType (6 values). One-time data task to classify ~106 orderable items. UI shows tab bar with badge counts: `[All (106)] [Toppings 🔴12] [Frozen 🔴3] [Sauces 🔴5] [Packaging 🔴8] [Supplies 🔴2]`
- **"Need Reorder" becomes a badge, not a filter.** Red dot on items with 0 stock. Tab headers show count of items needing reorder. Crew sees everything, reorder items highlighted.
- **R&D/SAMPLE/TEST items excluded** from ordering.

### BD-2: Demand engine — BOM-based from day one, NOT issuance-based
- **Problem:** All demand = 1.1/day identical for every item. No sales data connected.
- **Decision:** Build BOM-based demand pipeline using the official BOM file.
- **CEO directive (verbatim):** "I told you we have to start with BOM NOW. You do not decide on my behalf."
- **BOM source of truth:** `data/_CLEANROOM/factcheck_packets/supply_chain_cleanroom_stage_e_2026-03-02_w1_a2/sources/BEBANG STANDARD BOM PER SKU.xlsx`
  - Sheet: `JV` (company-owned stores)
  - **15 POS products:** PRESIDENTIAL, HALUKAY UBE, MANGO GRAHAM CARAMEL, BANANA CINNAMON, BUKO FRUIT SALAD, MELON, BUKO PANDAN, STRAWBERRY PISTACHIO, BLUEBERRY PISTACHIO, MATCHARAP, COOKIE CRUMBLE, SO CORNY, MANGO CLASSIC, SPECIAL, CHOCO BROWNIE
  - **46 ingredients** with grams-per-cup for each product
  - Store Yield column for unit conversion (e.g., 600g pack yield for Leche Flan)
- **Pipeline formula:**
  ```
  1. Query Supabase POS: store sold X units of each product (last 7 days avg)
  2. Explode via BOM: X Presidential × 20g sago = Y grams sago consumed
  3. Sum all products → base_daily_demand per ingredient per store
  4. Weather: fetch 7-day forecast from daily_weather table
     Apply exponential decay weighting (nearer days count more):
       Day 1: weight 1.00, Day 2: 0.85, Day 3: 0.70, Day 4: 0.55,
       Day 5: 0.40, Day 6: 0.25, Day 7: 0.15
     Per-day multiplier: >35°C → 1.15-1.30, rain → 0.85-0.90
     weighted_multiplier = Σ(day_multiplier × day_weight) / Σ(day_weight)
       across the coverage window only (not full 7 days)
  5. Coverage window: days until next delivery (COLD or DRY per item cargo)
  6. Suggested = (base_daily_demand × weighted_weather × coverage_days) + 15% buffer - store_stock
  ```
- **Weather weighting rationale:** Tomorrow's 37°C heatwave should drive more ordering than day 6's 35°C. Without decay weighting, a rain forecast on day 7 would dilute a heatwave signal on day 1 — causing understocking when the store needs product most. Confirmed: CEO approved 2026-04-02.
- **POS → BOM crosswalk:** `bom_fg_to_pos_crosswalk_compact.csv` maps 30+ POS item names to FG names
- **Nightly batch (2 AM):** pre-computes demand snapshots → writes to `BEI Inventory Risk Snapshot` DocType → ordering API reads from local MariaDB (zero latency)
- **Rationale for nightly batch over real-time sync:** Demand doesn't change hour-to-hour. Orders placed once/day before noon. Nightly is perfectly fresh. No Supabase→Frappe sync complexity, no redundant data, no sync failures.

### BD-3: Delivery schedule — SCM-managed per-store, COLD and DRY separate
- **Problem:** Shows "Next delivery: Saturday" for all stores. Hard-coded to "tomorrow." Reality: Market Market gets 27 deliveries/month, SM Sangandaan gets 3. COLD and DRY are delivered separately 42% of the time (SM North EDSA: 28 COLD days but only 16 DRY days).
- **Decision:** Build a **Delivery Schedule Management Page** for SCM team (Ian, Jay, Aldrin) in the SCM module. SCM sets the delivery days per store per week, with separate COLD and DRY checkboxes per day. The ordering page reads this schedule.
- **Data model:** `BEI Delivery Schedule Entry` — one row per store × day × delivery type. 47 stores × 7 days × 4 types (COLD/DRY) = 658 rows per week. Queryable, filterable, auditable. NOT 28 booleans — normalized rows.
- **3 interactive views on one page (tab navigation):**
  - **View 1: Weekly Grid** — their Excel digitized. Matrix: stores (grouped by warehouse 3MD/Pinnacle, collapsible) × 7 days × 4 types. Click cell = toggle delivery on/off. Live column totals. Filters by warehouse/cluster/search. "Copy Previous Week" + "Publish Week" buttons.
  - **View 2: Daily Route View** — select a day, see all deliveries grouped by type then by truck/route. Drag-and-drop stores between routes. Truck capacity bars. "Unassigned" section. Connects to S139 BEI Route.
  - **View 3: Store Card** — click any store → slide-out panel with full 7-day schedule, supervisor info, this-week-vs-last-week diff, inline edit toggles, "View Store Orders" link.
- **2 delivery types: COLD and DRY.** Investigated March 2026 actual issuance data (11,343 transactions):
  - COLD: 5,832 transactions (3MD COLD 2,946 + Pinnacle COLD 2,886). 24 items: finished goods (ice milk, jellies, syrups, toppings) + frozen raw materials.
  - DRY: 5,510 transactions (3MD DRY 2,540 + Pinnacle DRY 2,844 + Jentec DRY 126). 78 items: packaging, cleaning, office supplies, shelf-stable ingredients.
  - FM (Fresh Market): **zero transactions** — column exists in Excel but never operationalized. Don't build for it.
  - DR: "Delivery Receipt" document number, not a delivery type. Zero schedule entries.
  - ICE: empty/abandoned column.
- **Grid: 47 × 7 × 2 = 658 cells/week.** Clean, matches reality. If FM becomes real later, add 1 option to the Select field.
- **Initial seed data:** Computed from March 2026 actual delivery data (11,230 issuance rows analyzed — per-store per-type delivery frequency).
- **March data summary (actual):**
  - Almost daily (20+/month): 2 stores (Market Market, SM North EDSA)
  - Frequent (12-19): 13 stores
  - Regular (8-11): 22 stores (Araneta = 10 COLD, 5 DRY)
  - Weekly (4-7): 8 stores
  - Slow (1-3): 2 stores (SM Sangandaan, Estancia)
- **Store ordering reads schedule:** `get_next_delivery(store, cargo_type)` → returns `next_delivery_date` and `days_until` for COLD and DRY separately.
- **Coverage window in suggested qty:** Frozen toppings use `days_to_next_cold_delivery`. Packaging uses `days_to_next_dry_delivery`. Each item's cargo category determines which coverage window applies.

### BD-4: Order window banner — delivery countdown with cutoff
- **Problem:** "Place Order →" link goes to the same page. Banner doesn't show useful delivery info.
- **Decision:** Remove "Place Order →" link entirely. Replace banner with delivery countdown showing COLD and DRY separately:
  ```
  🧊 Next frozen delivery: Wednesday, Apr 4 (1 day 3:42 left to order)
  📦 Next dry delivery: Friday, Apr 6 (3 days 3:42 left to order)
  ```
- **Cutoff rule:** Stores can order anytime EXCEPT after 12:00 noon the day before delivery. Wednesday COLD delivery → cutoff Tuesday 12:00 NN. After cutoff:
  ```
  🧊 Frozen order closed — next window opens Wednesday for Friday delivery
  📦 Next dry delivery: Friday, Apr 6 (3 days 3:42 left to order)
  ```
- **Recommendation nudge:** When delivery is tomorrow and order window is still open, show amber nudge: "Order now — delivery is tomorrow. Orders placed closer to delivery are more accurate."
- **For stores where COLD and DRY always come together** (like Market Market), show single line.

### BD-5: Duplicate/variant items — show item code + UOM prominently
- **Problem:** FROZEN MANGO appears twice (RM030 PACK, RM010-A KG). FROZEN ICE MILK has 4 variants (FG020, FG020-GRIFFITH, FG020-ORIGINAL, R&D). Crew doesn't know which is theirs.
- **Decision:**
  - Show item code prominently (not grey subtext): `FROZEN ICE MILK (GRIFFITH) · FG020-GRIFFITH · KG`
  - Show "Last ordered" indicator if the store has ordered this variant before
  - R&D/SAMPLE items excluded entirely (BD-1)

### BD-6: Review Order button — sticky with summary
- **Problem:** Button uses flex `shrink-0`, gets pushed off-screen on 100+ item pages. Crew can't find submit.
- **Decision:** `position: sticky; bottom: 0; z-index: 20` with backdrop blur and top shadow. Always visible when ≥1 item has quantity. Show item count + estimated cost in the bar:
  ```
  ┌─────────────────────────────────────────────────────┐
  │  🛒 Review Order (9 items · ₱12,450)     [Review →] │
  └─────────────────────────────────────────────────────┘
  ```
- **Confirmed:** Sticky bar with item count + estimated cost. CEO approved 2026-04-02.

### BD-9: Emergency orders — 24hr delivery, triple approval
- **Problem:** What if a store runs out mid-week and next scheduled delivery is 3 days away?
- **Decision:** Add "Emergency Order" button. Delivery within 24 hours. Requires **triple approval chain:**
  1. Area Supervisor approves
  2. Regional Manager (Edlice) approves
  3. SCM approves (they have to arrange the truck)
- **All three must approve.** If any rejects, order is cancelled.
- **UI:** Separate button from regular orders — red/orange, clearly labeled "Emergency — 24hr delivery". Shows warning: "Requires Area Supervisor + Regional Manager + SCM approval."
- **Confirmed:** CEO approved 2026-04-02.

### BD-10: Order editing and SCM quantity override
- **Problem:** BOM suggestions may be wrong early on. Stores need to edit. SCM needs final control.
- **Decision:**
  - Stores can edit order quantities freely until we have confidence in the system.
  - Deviations > 10% from suggested still require Area Supervisor approval (existing rule from S129).
  - **SCM can edit ANY quantity on ANY order** — they have final say on what gets dispatched. The dispatched qty may differ from the ordered qty.
  - SCM edits are tracked: `qty_requested` (store's order) vs `qty_dispatched` (SCM's final number).
- **Confirmed:** CEO approved 2026-04-02.

### BD-11: Open questions (to confirm during execution)
- **Sunday deliveries:** STORE LIST shows 21 Sunday stores but UPDATED DELIVERY SCHEDULE only has Mon-Sat columns. Schedule grid includes Sunday (7 columns). Confirm with SCM if Sunday is active.
- **Missing orders alert (deferred):** Day before a scheduled delivery, SCM should see which stores haven't ordered. Deferred — needs schedule + ordering both live first.
- **Schedule change vs existing orders (deferred):** If SCM moves a delivery after stores ordered, existing orders may be undersized. Manual handling for now.
- **Demand signals on schedule grid (deferred):** Highlight stores running low on the weekly grid. Requires BOM pipeline running first.

### BD-8: Item sort order — urgency default, alphabetical option
- **Problem:** With "Need Reorder" filter gone, crew needs to quickly see what's critical within each category tab.
- **Decision:** Default sort by urgency within each tab:
  1. 🔴 Out of stock (store has 0) — top, red left border
  2. 🟡 Low stock (store has stock but < suggested qty) — amber left border
  3. 🟢 Sufficient (store has enough until next delivery) — green left border, slightly greyed
- **Sort toggle:** Allow user to switch to alphabetical sort (A-Z button in the controls bar). Preference persisted in localStorage.
- **Confirmed:** CEO approved 2026-04-02.

### BD-7: SKU priority scoring + "Source OOS" alert — NOT visible labels
- **Problem:** 161/240 items show "OOS" but most aren't stocked at the source warehouse. High-demand items OOS at source (like Melted Ube) need escalation, not hiding.
- **Decision:** Invisible priority score drives sort order. Crew never sees the score — only the status they understand:
  - 🔴 **Out of stock** — store has 0 (red left border)
  - 🟡 **Low — order by [day]** — store has less than coverage window of stock (amber)
  - ⚠️ **Source OOS badge** — ONLY on high-demand items (top 50% by BOM consumption) where source warehouse has 0. Orange badge: "Source OOS". Crew still orders, order hits SCM queue with escalation flag.
  - 🟢 **Sufficient** — stock covers until next delivery (green, slightly muted)
  - Items not carried by source warehouse sort to bottom of each category tab, separated by divider "── Not carried by {warehouse} ──"
- **Priority score formula (invisible):**
  - Demand (BOM-based): 0-40 pts
  - Order frequency (how many stores order this): 0-20 pts
  - Store stock urgency (0 stock=30, low=20, below 2 days=10, sufficient=0): 0-30 pts
  - Source alert (source OOS on high-demand item): +10 pts
- **No visible number or "HIGH PRIORITY" label.** CEO concern: visible priority labels would confuse crew and drive over-ordering on items they already have. The score only drives sort order.
- **Source OOS alert triggers SCM action:** Order with Source OOS flag goes to Area Supervisor / SCM queue → they find alternative source or alert commissary.
- **"Not stocked" (no Bin record):** Shows "—" in Source column, grey. KPI excludes these from "OOS at Source" count.
- **Confirmed:** CEO approved 2026-04-02.

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

S129 built the ordering UI. S136 fixed routing/picker. But the page shows 240 items (100 are commissary ingredients), all demand = 1.1, delivery schedule is wrong, and crew can't find the submit button. CEO tested live on 2026-04-02 and couldn't place an order.

### Why BOM-based demand (not issuance-based)

Issuance data (what the warehouse shipped) is backward-looking. BOM-based demand (POS sales × recipe) is forward-looking and accounts for weather. It's peak season — heat drives sales up 15-30% on hot days. The weather API can project demand; warehouse shipping logs cannot.

The official BOM file exists in the cleanroom with complete recipes for all 15 POS products. The POS→BOM crosswalk exists. Supabase has daily POS sales per store. All ingredients are mapped.

### Why category tabs (not filters)

Store crews are not tech-savvy and currently use Google Sheets. A filter that hides items causes blame. Category tabs organize without hiding — the crew sees everything, finds items in 3 seconds, and nobody can say "the system hid it from me."

### Source references

- Official BOM: `data/_CLEANROOM/factcheck_packets/supply_chain_cleanroom_stage_e_2026-03-02_w1_a2/sources/BEBANG STANDARD BOM PER SKU.xlsx` (JV sheet, 15 products × 46 ingredients)
- POS crosswalk: `data/_CLEANROOM/agent_runs/2026-03-10_s032-dual-repo-safe-clean-start/checkpoints/phase1_snapshots/BEI-ERP/root_untracked_archive/hrms/fixtures/store_ordering/bom_fg_to_pos_crosswalk_compact.csv`
- Delivery schedule: `data/_CLEANROOM/central_warehouse_2026_03/delivery_schedule.csv`
- Central Warehouse routing: `_CENTRAL_WAREHOUSE_ROUTE_MAP` in `hrms/api/store.py`
- Supabase POS schema: `memory/supabase-schema.md`
- Weather signals: `_compose_signal_modifiers()` in `hrms/api/store.py`
- Ordering page: `bei-tasks/app/dashboard/store-ops/ordering/_components/StoreOrderingPage.tsx`
- OrderWindowBanner: `bei-tasks/app/dashboard/store-ops/inventory/_components/OrderWindowBanner.tsx`
- Demand DocType: `hrms/hr/doctype/bei_inventory_risk_snapshot/bei_inventory_risk_snapshot.json`

---

## Scope (122 units)

### Phase 1: Backend — Item Filtering + Priority Score + Source Status (18 units)

| Task | Type | Repo | File | Description | Units |
|------|------|------|------|-------------|-------|
| B1 | FIX | bei-erp | `hrms/api/store.py` | **[FIX] Filter out commissary-only items (BD-1).** Add WHERE clause: `AND i.item_group IN ('Finished Goods', 'Consumables', 'Packaging Materials', 'Packaging', 'Products')`. Also exclude `item_name LIKE '%SAMPLE%' OR item_name LIKE '%R&D%' OR item_name LIKE '%TEST%' OR item_name LIKE '%E2E%'`. ~106 items remain. **HARD BLOCKER:** Use `item_group` field. | 2 |
| B2 | BUILD | bei-erp | Frappe | **[BUILD] Add `store_category` custom field on Item (BD-1).** Select field, values: Toppings, Frozen, Sauces, Packaging, Supplies, Other. Include in `get_orderable_items` response. | 2 |
| B3 | FIX | bei-erp | `hrms/api/store.py` | **[FIX] "Not stocked" vs "OOS" (BD-7).** Track which item_codes have Bin records at source warehouse. No Bin → `available_to_promise = -1`. Bin qty=0 → `available_to_promise = 0`. Add `source_item_exists` flag. | 3 |
| B4 | BUILD | bei-erp | `hrms/api/store.py` | **[BUILD] SKU priority score (BD-7).** Invisible score per item: Demand (0-40) + Frequency (0-20) + Store urgency (0-30) + Source alert (+10 for high-demand + source OOS). Return `priority_score` and `source_oos_alert` (boolean, only when top 50% demand + source qty=0) in API response. Score drives sort order only — never shown to crew. | 4 |
| B5 | FIX | bei-erp | `hrms/api/store.py` | **[FIX] Heuristic returns 0 when no data (BD-2).** When `last_order_qty=0 AND order_count=0`, return `(0, 0)` instead of `baseline=max(1.0, ...)`. | 1 |
| B6 | FIX | bei-erp | `hrms/api/store.py` | **[FIX] validate_order_schedule reads BEI Delivery Schedule (BD-3).** Query the published schedule for the store. Return `next_cold_delivery`, `next_dry_delivery`, `days_to_cold`, `days_to_dry` separately. Cutoff: 12:00 NN day before delivery. | 4 |
| B7 | FIX | bei-erp | `hrms/api/store.py` | **[FIX] Sentry observability on all modified endpoints.** | 1 |
| B8 | FIX | bei-erp | `hrms/api/store.py` | **[FIX] Coverage window per cargo type in suggested qty (BD-3).** Frozen/chilled items use `days_to_cold`. Dry/packaging items use `days_to_dry`. Formula: `suggested = (daily_demand × weather × days_to_delivery) + 15% buffer - store_stock`. | 1 |

### Phase 2: BOM-Based Demand Pipeline (20 units)

| Task | Type | Repo | File | Description | Units |
|------|------|------|------|-------------|-------|
| P1 | BUILD | bei-erp | `scripts/build_demand_snapshots.py` | **[BUILD] Extract official BOM to structured data (BD-2).** Parse `BEBANG STANDARD BOM PER SKU.xlsx` JV sheet: 15 products × 46 ingredients. Output: `data/_CLEANROOM/bom/store_consumption_bom.csv` with columns: `pos_product, ingredient_item_code, grams_per_cup, store_yield_grams, uom`. Convert grams-per-cup to fractional units using Store Yield. | 4 |
| P2 | BUILD | bei-erp | `scripts/build_demand_snapshots.py` | **[BUILD] POS → BOM crosswalk (BD-2).** Map Supabase POS item names to the 15 BOM product names. Use existing crosswalk + fuzzy match. Output: verified mapping table. | 3 |
| P3 | BUILD | bei-erp | `scripts/build_demand_snapshots.py` | **[BUILD] Supabase POS query (BD-2).** Query per-store per-product daily sales for last 7 days. Use Doppler for Supabase credentials. **HARD BLOCKER:** Do NOT hardcode credentials. | 3 |
| P4 | BUILD | bei-erp | `scripts/build_demand_snapshots.py` | **[BUILD] BOM explosion + weather + coverage (BD-2).** Per store: POS sales × BOM → ingredient demand/day. Apply weather multiplier (heat index). Apply cargo-specific coverage window (days to next COLD or DRY delivery). Compute `suggested = (daily × weather × coverage) + 15% buffer - store_stock`. | 5 |
| P5 | BUILD | bei-erp | `scripts/build_demand_snapshots.py` | **[BUILD] Write to Frappe.** Write `BEI Inventory Risk Snapshot` records via Frappe API. Fields: `snapshot_date`, `item_code`, `warehouse`, `avg_daily_demand`, `source_reference` (JSON with BOM breakdown). | 3 |
| P6 | VERIFY | bei-erp | — | **[VERIFY] Run pipeline for Araneta Gateway.** Execute for 1 store. Verify snapshots. Check ordering API returns differentiated demand. | 2 |

### Phase 3: Data Setup (8 units)

| Task | Type | Repo | File | Description | Units |
|------|------|------|------|-------------|-------|
| D1 | DATA | bei-erp | Frappe | **[DATA] Classify ~106 orderable items into 6 store_category values (BD-1).** Toppings (~35), Frozen (~15), Sauces (~12), Packaging (~25), Supplies (~15), Other (~4). Script via API. Source: item names + Central Warehouse SUMMARY `CATEGORY 2` column. | 4 |
| D2 | DATA | bei-erp | Frappe | **[DATA] Load store-consumption BOMs into Frappe (BD-2).** 15 POS products with ingredient component lists. Separate from the 17 existing commissary production BOMs. | 4 |

### Phase 4: Delivery Schedule Management Page — 3 Interactive Views (26 units)

**Data model:** `BEI Delivery Schedule Entry` — one row per store × day × delivery type. 47 stores × 7 days × 4 types (COLD/DRY) = 658 rows per week. Queryable, filterable, auditable.

| Task | Type | Repo | File | Description | Units |
|------|------|------|------|-------------|-------|
| S1 | BUILD | bei-erp | Frappe DocType | **[BUILD] Two DocTypes: `BEI Delivery Schedule Week` (parent) + `BEI Delivery Schedule Entry` (child).** Parent: `week_start` (Date, Monday), `published` (Check), `published_by` (Link→User), `published_at` (Datetime), `unpublish_reason` (Small Text). Child: `store` (Link→Warehouse), `day_of_week` (Select: Mon-Sun), `delivery_type` (Select: COLD/DRY), `route_name` (Link→BEI Route, optional). One parent per week, ~987 child entries. SCM can unpublish with reason (audit logged). Also add `custom_territory_cluster` field on Warehouse (Select: CLUSTER 3-9). | 3 |
| S2 | BUILD | bei-erp | `hrms/api/store.py` | **[BUILD] API: CRUD + publish + copy week + totals.** `get_weekly_schedule(week_start, warehouse_filter, cluster_filter)` returns full grid grouped by warehouse/cluster. `toggle_delivery(store, week_start, day, type)` toggles one cell. `copy_week(source_week, target_week)` clones all entries. `publish_week(week_start)` locks schedule + makes it visible to stores. `unpublish_week(week_start, reason)` unlocks with audit reason + notifies affected stores. `get_day_summary(date)` returns totals per type per warehouse. `get_store_schedule(store)` returns one store's full week for store card. **Fallback:** If no published schedule for the requested week, fall back to the last published week (most weeks are identical). Ordering page shows subtle note: "Using last week's schedule." | 4 |
| S3 | BUILD | bei-tasks | `/dashboard/scm/delivery-schedule` | **[BUILD] View 1: Weekly Grid (interactive).** Matrix: rows = stores grouped by warehouse (3MD North / Pinnacle South, collapsible). Cols = Mon-Sun × 4 sub-cols (COLD/DRY). Click cell = toggle 🔴 on/off. Live column totals at bottom ("28 FC, 12 DRY, 5 FM on Monday"). Filters: warehouse, cluster, search. "Copy Previous Week" button. "Publish Week" button (locks, shows who published + when). Week navigator (◄ ►). Store metadata on hover: area supervisor, contact, cluster. | 10 |
| S4 | BUILD | bei-tasks | `/dashboard/scm/delivery-schedule` | **[BUILD] View 2: Daily Route View (interactive).** Select a day → see all deliveries grouped by delivery type (COLD/DRY), then by truck/route. Drag-and-drop stores between routes to rebalance. Show truck capacity utilization bar. "Unassigned" section for stores not yet on a route. Add/remove truck buttons. Connects to BEI Route DocType (S139 data). If no routes assigned yet, show flat list with "Assign Route" dropdown. | 4 |
| S5 | BUILD | bei-tasks | `/dashboard/scm/delivery-schedule` | **[BUILD] View 3: Store Card View (interactive).** Click any store → slide-out panel with: full weekly schedule (7-day row with COLD/DRY toggles), area supervisor + contact + cluster + warehouse, this week vs last week comparison (deliveries added/removed), edit delivery types directly from card (same toggle as grid). "View Store Orders" link to ordering page for that store. | 3 |
| S6 | DATA | bei-erp | Frappe | **[DATA] Seed initial schedule from March actual data + Excel screenshot.** Parse 11,230 March issuance rows for per-store per-type per-weekday delivery patterns. Also incorporate the Excel screenshot data (COLD/DRY columns per day). Create first 2 weeks of schedule entries. | 2 |

### Phase 5: Frontend UX Redesign + Emergency Orders + SCM Override (28 units)

| Task | Type | Repo | File | Description | Units |
|------|------|------|------|-------------|-------|
| F1 | BUILD | bei-tasks | `StoreOrderingPage.tsx` | **[BUILD] Category tab bar (BD-1).** 7 tabs: `[All (106)] [Toppings 🔴12] [Frozen 🔴3] [Sauces 🔴5] [Packaging 🔴8] [Supplies 🔴2] [Other]`. Badge = items with 0 stock per category. "All" default. | 4 |
| F2 | BUILD | bei-tasks | `StoreOrderingPage.tsx` | **[BUILD] Urgency sort + alphabetical toggle (BD-8).** Default: sort by invisible priority_score (highest first). 🔴 Out of stock → 🟡 Low → 🟢 Sufficient. "Not carried" items after divider at bottom. A-Z toggle button persists to localStorage. | 3 |
| F3 | BUILD | bei-tasks | `StoreOrderingPage.tsx` | **[BUILD] Sticky Review bar with summary (BD-6).** `position: sticky; bottom: 0; z-index: 20; backdrop-blur`. Shows: `🛒 Review Order (9 items · ₱12,450) [Review →]`. Visible when ≥1 item has qty. | 3 |
| F4 | BUILD | bei-tasks | `OrderWindowBanner.tsx` | **[BUILD] Delivery countdown banner (BD-4).** Replace "Place Order →" with dual delivery countdown: `🧊 Next COLD: Wed Apr 4 (1d 3:42 left)` / `📦 Next DRY: Fri Apr 6 (3d 3:42 left)`. Single line when COLD+DRY same day. Cutoff state: "COLD order closed — next window Wed for Fri". Amber nudge when delivery is tomorrow. | 4 |
| F5 | FIX | bei-tasks | `OrderItemTable.tsx` | **[FIX] Item code + UOM prominent (BD-5).** Format: `FROZEN ICE MILK (GRIFFITH) · FG020-GRIFFITH · KG`. Not grey subtext. | 2 |
| F6 | FIX | bei-tasks | `OrderItemTable.tsx` + `OrderItemCard.tsx` | **[FIX] Source OOS alert badge + Not stocked (BD-7).** `source_oos_alert=true` → orange ⚠️ badge "Source OOS". ATP < 0 → "—" grey. ATP = 0 without alert → "OOS" red. "Not carried" items after `── Not carried by {warehouse} ──` divider. | 3 |
| F7 | FIX | bei-tasks | `OrderSummaryStrip.tsx` | **[FIX] KPI updates.** "OOS at Source" excludes not-stocked items. Badge counts per category tab. | 1 |
| F8 | FIX | bei-tasks | `OrderCriticalStrip.tsx` | **[FIX] Critical strip: only truly OOS items with source_oos_alert.** Not "not stocked" items. | 1 |
| F9 | FIX | bei-tasks | `OrderItemCard.tsx` | **[FIX] Mobile card: same sort, categories, source alert, item code.** | 1 |
| F10 | BUILD | bei-erp + bei-tasks | `StoreOrderingPage.tsx` + `hrms/api/store.py` | **[BUILD] Emergency Order button (BD-9).** Red/orange button "Emergency — 24hr delivery" on ordering page. Creates order with `is_emergency=true`. Requires triple approval chain: Area Supervisor → Regional Manager (Edlice) → SCM. All three must approve. Backend: new approval chain logic on `submit_order` when `is_emergency=true`. Frontend: warning dialog explaining the 3-step approval. | 4 |
| F11 | BUILD | bei-erp | `hrms/api/store.py` + BEI Store Order Item | **[BUILD] SCM quantity override (BD-10).** Add `qty_dispatched` field on `BEI Store Order Item` (separate from `qty_requested`). SCM can edit ANY quantity on any approved order via API. Track both: `qty_requested` (what store asked for) vs `qty_dispatched` (what SCM decides to send). Frontend: SCM order review page shows both columns with edit on dispatched. | 2 |

### Phase 6: L3 Testing (10 units)

| Task | Type | Repo | Description | Units |
|------|------|------|-------------|-------|
| T1 | L3 | both | **[L3] Data quality.** (a) search "CINNAMON" → 0 results, (b) category tabs with badge counts, (c) demand differs between items (BOM-based), (d) SAGO suggested non-zero, (e) item code + UOM visible, (f) "Not carried" items at bottom with divider. | 4 |
| T2 | L3 | both | **[L3] Delivery + UX.** (a) banner shows correct COLD + DRY delivery dates per store, (b) cutoff logic works, (c) sticky Review bar with count + cost, (d) urgency sort default, (e) A-Z toggle works. | 3 |
| T3 | L3 | both | **[L3] Submit + SCM.** (a) enter qty → Review → Confirm & Submit → order created, (b) Source OOS alert item: order goes through with flag, (c) SCM schedule page: set schedule, publish, ordering page reflects it. | 3 |

### Phase 7: Closeout (2 units)

| Task | Type | Repo | Description | Units |
|------|------|------|-------------|-------|
| C1 | DOC | bei-erp | Update plan YAML + SPRINT_REGISTRY.md. Push. | 1 |
| C2 | DOC | bei-erp | Update S136 plan status to COMPLETED. | 1 |

**Total: 122 units** (18 backend + 20 pipeline + 8 data + 26 schedule page + 28 frontend/emergency/SCM + 10 L3 + 2 closeout)

---

## Execution Model

122 units split into **1 builder session + 1 L3 session**:
- **Builder session:** Phase 1-5 + Phase 7 closeout = **112 units**. One agent owns all code. No cold-start context conflicts. Stops at PR_CREATED.
- **L3 session (separate):** Phase 6 = **10 units**. Fresh session, read-only (Playwright tests only, no code changes). Builder outputs L3 handoff prompt. Sam pastes into fresh session.

**Why not multiple builder sessions:** Cold-start agents on the same feature step on each other's code (proven failure in this conversation — branch confusion, wrong commits, patches-on-patches).
**Why separate L3:** Agents skip L3 no matter the sprint size. The builder physically cannot declare PASS — L3 is not its job.

---

## Requirements Regression Checklist

- [ ] Does `get_orderable_items` exclude Raw Material, Fixed Asset, R&D/SAMPLE/TEST/E2E items? (B1)
- [ ] Does the API return `store_category` per item? (B2)
- [ ] Does the API return `available_to_promise = -1` for not-stocked, `= 0` for real OOS? (B3)
- [ ] Does the API return `priority_score` (invisible) and `source_oos_alert` (boolean) per item? (B4)
- [ ] Does `source_oos_alert` only fire on top 50% demand items where source qty = 0? (B4)
- [ ] Does the heuristic return (0, 0) for zero-history zero-count items? (B5)
- [ ] Does `validate_order_schedule` return separate `next_cold_delivery` and `next_dry_delivery`? (B6)
- [ ] Is cutoff 12:00 NN on the day BEFORE delivery? (B6)
- [ ] Does suggested qty use cargo-specific coverage window (COLD vs DRY)? (B8)
- [ ] Is the BOM extracted from `BEBANG STANDARD BOM PER SKU.xlsx` JV sheet (15 products × 46 ingredients)? (P1)
- [ ] Does the pipeline use Supabase POS sales × BOM → ingredient demand? (P4)
- [ ] Does the pipeline apply weather multiplier AND cargo-specific coverage window? (P4)
- [ ] Does the pipeline write to `BEI Inventory Risk Snapshot`? (P5)
- [ ] Does the pipeline use Doppler for Supabase credentials? (P3)
- [ ] Are all ~106 orderable items classified into 6 store_category values? (D1)
- [ ] Does `BEI Delivery Schedule` DocType exist with 14 boolean fields + published flag? (S1)
- [ ] Does the SCM schedule page support click-to-toggle, copy week, apply template, publish? (S3)
- [ ] Is initial schedule seeded from March actual delivery data? (S4)
- [ ] Does the frontend show 7 category tabs with reorder badge counts? (F1)
- [ ] Is default sort by priority_score (urgency), with A-Z toggle? (F2)
- [ ] Is Review bar sticky with item count + estimated cost? (F3)
- [ ] Does banner show dual COLD/DRY delivery countdown + cutoff state + amber nudge? (F4)
- [ ] Is item code + UOM shown prominently (not grey subtext)? (F5)
- [ ] Does Source OOS alert show ⚠️ badge only on high-demand items? (F6)
- [ ] Are "Not carried" items at bottom of each tab with divider? (F6)
- [ ] Does emergency order require triple approval: Area Supervisor → Regional Manager → SCM? (F10)
- [ ] Does `BEI Store Order Item` have `qty_dispatched` field separate from `qty_requested`? (F11)
- [ ] Can SCM edit `qty_dispatched` on any approved order? (F11)
- [ ] Does the schedule DocType use parent/child (Week + Entry), not flat rows? (S1)
- [ ] Does unpublish require a reason and log audit trail? (S2)
- [ ] Does the weekly grid have 2 sub-columns per day (COLD/DRY), not 4? (S3)
- [ ] Does every modified `@frappe.whitelist()` call `set_backend_observability_context()`? (B7)

---

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| sam@bebang.ph | Search "CINNAMON" | 0 results — raw materials filtered | B1 broken |
| sam@bebang.ph | Search "R&D" or "SAMPLE" | 0 results — test items filtered | B1 broken |
| sam@bebang.ph | Check tab bar | 7 tabs with badge counts. "All" selected by default | F1 broken |
| sam@bebang.ph | Tap "Toppings" tab | Shows ~35 topping items, sorted by urgency (🔴 first) | F1 or D1 broken |
| sam@bebang.ph | Toggle A-Z sort | Items re-sort alphabetically | F2 broken |
| sam@bebang.ph | Check BALLPEN entry | Shows `BALLPEN BLACK 0.7 · OS001 · PIECE` (code + UOM prominent) | F5 broken |
| sam@bebang.ph | Check Demand/Day for SAGO | Non-zero, differs from other items (BOM-based) | P4 pipeline broken |
| sam@bebang.ph | Check delivery banner | Shows separate 🧊 COLD and 📦 DRY delivery dates with countdown | B6/F4 broken |
| sam@bebang.ph | Check Suggested Qty for SAGO | Non-zero: `(daily × weather × days_to_cold) + buffer - stock` | P4 or B8 broken |
| sam@bebang.ph | Scroll to bottom of Toppings tab | "Not carried by 3MD" divider, then low-priority items | F6 broken |
| sam@bebang.ph | Find high-demand item OOS at source | ⚠️ Source OOS orange badge visible | B4/F6 broken |
| sam@bebang.ph | Scroll with qty entered | Sticky bar visible: `🛒 Review Order (N items · ₱X)` | F3 broken |
| sam@bebang.ph | Tap Review → Confirm & Submit | Order BEI-ORD-xxxx created | Submit regression |
| sam@bebang.ph | Open SCM schedule page | 3 view tabs: Weekly Grid, Daily Route, Store Card. Grid shows 47 stores × 7 days × 4 types | S3 broken |
| sam@bebang.ph | Click FC cell for Araneta Wednesday | Cell toggles 🔴 on. Column total increments. | S3 toggle broken |
| sam@bebang.ph | Click "Copy Previous Week" | All entries cloned to next week. Grid populates. | S2 copy broken |
| sam@bebang.ph | Switch to Daily Route view, select Wednesday | See all Wednesday deliveries grouped by COLD/DRY, truck assignments | S4 broken |
| sam@bebang.ph | Drag store between routes | Store moves, truck capacity bars update | S4 drag broken |
| sam@bebang.ph | Click store name → Store Card | Slide-out: full week schedule, supervisor info, edit toggles | S5 broken |
| sam@bebang.ph | Publish week | Schedule locked. Ordering page shows correct next delivery for each store | S2/B6/F4 broken |
| sam@bebang.ph | Click "Emergency Order" on ordering page | Warning dialog shows triple approval requirement. Submit creates emergency order with `is_emergency=true` | F10 broken |
| sam@bebang.ph | Open SCM order view, edit qty_dispatched | Both `qty_requested` and `qty_dispatched` visible. SCM can change dispatched qty. | F11 broken |
| test.crew1@bebang.ph | Open ordering | Category tabs, no raw materials, correct schedule, urgency sort | Regression |

Evidence files:
```
output/l3/S154/form_submissions.json
output/l3/S154/api_mutations.json
output/l3/S154/state_verification.json
```

---

## Zero-Skip Enforcement (MANDATORY — Read Before Every Phase)

### The Rule

**Every task in this plan MUST be implemented. No exceptions. No "deferred." No "out of scope." No "will do later."**

If a task cannot be completed, the agent MUST:
1. **STOP immediately**
2. **State the task ID** (e.g., "BLOCKED on F10")
3. **Explain WHY** it cannot be completed (specific error, missing dependency, technical impossibility)
4. **Ask the user** for guidance before proceeding to any other task

**The agent is FORBIDDEN from:**
- Skipping a task silently
- Marking a task as "done" when it's partial
- Replacing a task with a simpler version without explicit user approval
- Saying "deferred to next sprint" — there is no next sprint for these items
- Combining multiple tasks into one and dropping features in the merge
- Implementing the happy path only and skipping edge cases described in the task

### Task Completion Checklist (MANDATORY after each phase)

After completing EACH phase, the agent MUST write a checklist to `output/s154/phase_completion.md`:

```markdown
## Phase N Completion — [timestamp PHT]

| Task | Status | Evidence | Skipped? | If skipped, why? |
|------|--------|----------|----------|------------------|
| B1   | DONE   | SQL WHERE clause added, line XXX | No | — |
| B2   | DONE   | Custom field in fixtures, line XXX | No | — |
| ...  | ...    | ... | ... | ... |

Skipped count: 0
Partial count: 0
Agent self-declaration: I confirm all tasks in Phase N are fully implemented as described.
```

**If `Skipped count > 0` or `Partial count > 0`, the agent MUST immediately notify the user BEFORE starting the next phase.**

### PR Description Gate

The PR description MUST include:
1. A task-by-task checklist with checkmarks
2. Any task NOT checked must have an explanation
3. The user will reject any PR missing tasks without explanation

### L3 Handoff Gate

The L3 handoff prompt MUST list every task from every phase with its implementation status. The L3 agent uses this to verify — if a task says "DONE" but L3 can't find the feature, it's a builder lie and gets reported.

---

## Autonomous Execution Contract

- **completion_condition:**
  - No Raw Material / R&D / TEST items in ordering page
  - 7 category tabs with urgency sort + A-Z toggle + reorder badge counts
  - BOM-based demand (15 products × 46 ingredients) with weather + cargo-specific coverage
  - SCM delivery schedule page live — weekly grid, click-to-toggle, publish
  - Ordering banner shows separate COLD/DRY delivery dates with countdown + cutoff
  - Sticky Review bar with item count + estimated cost
  - SKU priority score driving sort (invisible) + Source OOS alert badge
  - "Not carried" items at bottom of each tab with divider
  - Emergency order button with triple approval chain (Area Sup → Regional Mgr → SCM)
  - SCM qty override: `qty_dispatched` editable on any approved order
  - All L3 scenarios pass (including emergency + SCM override scenarios)
  - Phase completion checklists written for all phases in `output/s154/phase_completion.md`
  - PR descriptions include task-by-task checklist
  - Plan + registry updated
  - **ZERO tasks skipped. If any task is skipped, agent MUST notify user BEFORE proceeding.**

- **stop_only_for:**
  - P3: Supabase POS data doesn't have per-item per-store sales (need to investigate views)
  - P2: POS→BOM crosswalk coverage < 80% (some POS items can't be mapped to BOM products)
  - D2: Store consumption BOMs conflict with existing commissary production BOMs in Frappe
  - Weather API not accessible
  - S1: BEI Delivery Schedule DocType creation fails (permissions/schema conflict)

- **phase_sequencing:**
  - **Builder session:** Phase 1 → 2 → 3 → 4 → 5 → 7 sequentially. Backend PR + frontend PR. Stop at PR_CREATED.
  - **L3 session (separate):** Phase 6 after all deployed + pipeline has run. Sam pastes L3 handoff prompt into fresh session.

- **signoff_authority:** single-owner (Sam Karazi, CEO)

---

## Implementation Details (Gap Closures — Investigated 2026-04-02)

### ID-1: Branch state — Phase 1 B1-B5 already committed
- Branch `s154-store-ordering-production-ready` exists in both repos.
- **bei-erp:** commit `93a9a2ac4` has B1 (item_group filter), B2 (store_category in SQL), B3 (source_item_exists), B4 (priority_score + source_oos_alert), B5 (heuristic returns 0). **Start at B6.**
- **bei-tasks:** branch created but no commits yet. All frontend work is pending.

### ID-2: Supabase POS — exact table and query
- **Table:** `pos_orders` (synced daily via `scripts/sync_pos_to_supabase.py`)
- **Child table:** `pos_order_items` (item_name, qty, price per order)
- **Key columns:** `location_id` (→ Mosaic store), `business_date` (Manila date), `payment_status` (filter 'PAID')
- **Query for per-item per-store daily sales:**
  ```sql
  SELECT location_id, business_date, item_name, SUM(qty) as qty_sold
  FROM pos_orders JOIN pos_order_items ON pos_orders.id = pos_order_items.pos_order_id
  WHERE payment_status = 'PAID' AND business_date >= :since
  GROUP BY location_id, business_date, item_name
  ```
- **Location → Frappe warehouse mapping:** `hrms/fixtures/sales_dashboard_store_mapping.csv`
- **Credentials:** Doppler `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` (project `bei-erp`, config `dev`)

### ID-3: Weather API — Open-Meteo, free, no API key
- **Service:** Open-Meteo (https://api.open-meteo.com/v1/forecast)
- **No API key required.** Free tier is sufficient.
- **Existing code:** `_is_weather_risk(warehouse)` at `hrms/api/store.py:1457-1468`. Queries `BEI Weather Alert` DocType.
- **Weather multiplier:** `_compose_signal_modifiers()` at line 1428: weather_multiplier = 1.06 if risk, else 1.0.
- **Supabase weather data:** `daily_weather` table with `max_temp`, `is_rainy`, `business_impact`. Synced by `scripts/sync_weather_to_supabase.py`.
- **For S154:** Query `daily_weather` for next 3 days forecast. If `max_temp > 35` → multiplier 1.15-1.30. If `is_rainy` → multiplier 0.85-0.90.

### ID-4: BOM Excel column mapping
- **File:** `data/_CLEANROOM/factcheck_packets/.../BEBANG STANDARD BOM PER SKU.xlsx`
- **Sheet:** `JV` (company-owned stores)
- **Structure (matrix):**
  - Row 1: Columns 0-4 = metadata headers. Columns 5,7,9,11,13,15,17,19,21,23,25,27,29,31,33 = **15 product names** (PRESIDENTIAL, HALUKAY UBE, MANGO GRAHAM CARAMEL, BANANA CINNAMON, BUKO FRUIT SALAD, MELON, BUKO PANDAN, STRAWBERRY PISTACHIO, BLUEBERRY PISTACHIO, MATCHARAP, COOKIE CRUMBLE, SO CORNY, MANGO CLASSIC, SPECIAL, CHOCO BROWNIE). Products are at ODD column indices starting at 5.
  - Row 1 col 1: "UNIT PRICE, VAT EX". Col 2: "UOM". Col 3: "Store Yield, grams". Col 4: "Price per gram".
  - Row 2: Sub-headers: "grams per cup" and "price per cup" alternating under each product.
  - Rows 3-48: **46 ingredient rows.** Col 0 = ingredient name. Col 1 = unit price. Col 2 = UOM (e.g., "600g (12s) pack"). Col 3 = Store Yield in grams. Col 4 = price per gram. Product columns (odd) = grams per cup. Product columns (even) = price per cup.
- **Canonical CSV export also available:** `data/_CLEANROOM/migration_runs/.../P05_BOM_UOM/inputs_normalized/BOM_RECIPES_PACKET.csv` (columns: Product, Item Code, Ingredient, BOM Reference, Grams per Cup, SKU Conversion)
- **To extract:** Use the CSV if available; fall back to openpyxl for Excel only if CSV is incomplete.

### ID-5: Store name normalization
- **Function:** `_normalize_store_name_for_route(warehouse_name)` at `hrms/api/store.py:1331-1340`
- **Logic:** uppercase, strip " - BEBANG ENTERPRISE INC.", " - BEI", " - BKI", " - BEBANG KITCHEN INC."
- **Use for:** delivery schedule seeding (match March issuance store names to Frappe warehouse names)
- **Additional alias maps:** `hrms/services/blip/data/weather.py:44-93` (e.g., "megamall" → "sm_megamall")

### ID-6: Custom Field creation in Frappe
- **Pattern:** Add to `hrms/fixtures/custom_field.json`
- **For `store_category`:**
  ```json
  {
    "doctype": "Custom Field",
    "name": "Item-custom_store_category",
    "dt": "Item",
    "fieldname": "custom_store_category",
    "fieldtype": "Select",
    "label": "Store Category",
    "options": "\nToppings\nFrozen\nSauces\nPackaging\nSupplies\nOther",
    "insert_after": "item_group",
    "description": "Category for store ordering page tabs (S154)"
  }
  ```
- **Deploy:** Fixture auto-loads on `bench migrate` (registered in `hrms/hooks.py:568`)
- **ALSO needed for S4:** `BEI Delivery Schedule` DocType — create as a new DocType in `hrms/hr/doctype/bei_delivery_schedule/`

### ID-7: Existing code that must not break
- `_CENTRAL_WAREHOUSE_ROUTE_MAP` (lines 1264-1328): 47 store→warehouse fallback routing. DO NOT modify.
- `_is_orderable_store()` (lines 1604-1615): called at 3 locations (1853, 1944, 1958) for store picker filtering. DO NOT modify.
- `_NON_ORDERABLE_NAME_PATTERNS` (lines 1591-1595): updated by S154 B1 to add "Finished Goods", "Work In Progress" etc. Keep all existing entries.
- `store_actual_qty` (line 2202): must remain in API response. Frontend depends on it.
- `source_warehouse_short` (line 2201): must remain. Frontend reads it for Source Avail. column.
- `_build_recommendation_contract()` (lines 1497-1556): zero-history guard must remain intact.

### ID-8: SCM module in bei-tasks
- **Route:** `/app/dashboard/scm/delivery-schedule`
- **Directory:** `app/dashboard/scm/delivery-schedule/page.tsx` (new)
- **RBAC:** `MODULES.SCM` in `lib/roles.ts:616-623` — includes: PROCUREMENT_USER, PROCUREMENT_MANAGER, SUPPLY_CHAIN_MANAGER, WAREHOUSE_USER, HQ_USER, HQ_FINANCE, SYSTEM_MANAGER, ADMINISTRATOR
- **Route constant:** Add `SCM_DELIVERY_SCHEDULE: "/dashboard/scm/delivery-schedule"` to `lib/constants.ts`
- **Sidebar:** SCM section already exists with 6 sub-pages. Add "Delivery Schedule" after "Route Planner".
- **Pattern to follow:** `app/dashboard/scm/route-planner/page.tsx` (S139 implementation)

---

## Agent Boot Sequence

1. Read this plan fully — especially **Brainstorm Decisions** and **Implementation Details** sections.
2. **Check out existing branch (bei-erp):** `git fetch origin && git checkout s154-store-ordering-production-ready && git pull origin s154-store-ordering-production-ready`. Branch already has B1-B5 committed. **Start at B6.**
3. **Check out existing branch (bei-tasks):** `cd ../bei-tasks && git fetch origin && git checkout s154-store-ordering-production-ready`. No commits yet — all frontend work pending.
4. Read `hrms/api/store.py` lines 2060-2240 (`get_orderable_items`), lines 2410-2480 (`validate_order_schedule`), lines 1679-1684 (`_estimate_projected_sales_and_bom`).
5. Read BOM CSV: `data/_CLEANROOM/migration_runs/2026-03-02_frappe_go_live_zero_hallucination_v1/01_packets/P05_BOM_UOM/inputs_normalized/BOM_RECIPES_PACKET.csv`. If insufficient, parse the Excel JV sheet per ID-4 column mapping.
6. Read POS crosswalk: `data/_CLEANROOM/agent_runs/2026-03-10_s032-dual-repo-safe-clean-start/checkpoints/phase1_snapshots/BEI-ERP/root_untracked_archive/hrms/fixtures/store_ordering/bom_fg_to_pos_crosswalk_compact.csv`.
7. Read delivery schedule: `data/_CLEANROOM/central_warehouse_2026_03/delivery_schedule.csv`.
8. Read `memory/supabase-schema.md` for Supabase query patterns. Credentials via Doppler: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.
9. Read `bei-tasks/app/dashboard/scm/route-planner/page.tsx` for SCM page pattern.
10. Read `bei-tasks/app/dashboard/store-ops/ordering/_components/StoreOrderingPage.tsx` for current ordering UI.
11. Read `hrms/fixtures/custom_field.json` for Custom Field creation pattern.
12. Execute Phase 1 B6-B8, then Phase 2-5 in order. Stop at PR_CREATED. Output L3 handoff prompt.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

**ZERO-SKIP RULE:** After each phase, write the phase completion checklist to `output/s154/phase_completion.md`. If ANY task was skipped or partially done, STOP and notify the user IMMEDIATELY. Do NOT proceed to the next phase with skipped tasks. The user (Sam Karazi, CEO) has explicitly required this — no task is optional, no task can be deferred, no task can be simplified without his approval.
