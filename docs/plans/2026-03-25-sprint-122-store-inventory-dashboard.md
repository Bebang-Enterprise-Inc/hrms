---
canonical_sprint_id: S122
display: Sprint 122
status: GO
branch: s122-store-inventory-dashboard
lane: single
created_date: 2026-03-25
completed_date:
deployed_at:
backend_pr:
frontend_pr:
l3_result:
execution_summary:
depends_on:
---

# S122 — Store Inventory Dashboard: Birds-Eye Stock Visibility for Store Teams

**Goal:** Give store managers a single page on my.bebang.ph that shows everything they have, what's running low, what's overstocked, and what they should order next — all at a glance, mobile-first, designed for 100+ SKUs.

**Origin:** S121 fixed the inventory sync but revealed that store managers have zero inventory visibility on my.bebang.ph. The ordering page only works during the order window. Outside that window, store teams are blind.

**Key constraint from Sam:** When BEI fully migrates to ERPNext, the Google Sheets sync stops entirely. Do NOT build features around sync freshness or ENCODE adoption. Focus on what tabBin and ERPNext data already provide: stock levels, demand, and order history.

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

Store managers manage 80-150 SKUs across DRY, COLD, FROZEN, and CHILLED categories. Today they have:
- **Ordering page** (`/dashboard/store-ops/ordering`) — only works when the order window is open (schedule-gated)
- **No stock visibility page** — they cannot see what Frappe thinks their store has
- **No demand view** — they cannot see projected demand or days-of-stock outside the ordering flow

The warehouse team has `/dashboard/warehouse/inventory` (a matrix view with status badges, days-of-stock, and demand columns). Store teams need something similar but scoped to a **single store** and optimized for **mobile phones** (store managers are rarely at a desk).

### Why this architecture

**Reuse existing APIs, build new frontend only.** The backend already has everything:
- `useWarehouseStock(warehouse)` — returns items with `actual_qty`, `is_low_stock` for any warehouse
- `useInventoryMatrix({ facilityMode: "stores", facilityIds: [storeWarehouse] })` — returns the full matrix for a store
- `useOrderableItems(store)` — returns items with `available_stock`, `forecast_demand`, `suggested_qty`, `risk_rank`, `is_oos`
- `useOrderSchedule(store)` — returns whether the ordering window is open

No new backend API is needed. The sprint is 100% frontend (bei-tasks repo).

### Key trade-offs

1. **Responsive dual layout:** Stores use both phones and laptops. The page renders as a **grouped card list** on mobile (<768px) with sticky category headers and big touch targets, and a **dense sortable table** on desktop (>=768px) similar to the warehouse inventory matrix — with columns for item, category, qty, status, days-of-stock, demand, and suggested order qty. Both layouts share the same data hooks and filters. Use Tailwind `md:` breakpoint to switch. The card layout is the default (mobile-first).

2. **Single-store vs multi-store:** Store staff see only their store. Area Supervisors see a store picker at the top. This matches the existing pattern in ordering and store-ops pages.

3. **Always-available vs schedule-gated:** Unlike ordering, this page is always available. It shows current stock even when the order window is closed. When the window IS open, a banner links to the ordering page.

4. **No sync freshness features:** Per Sam's directive, we do NOT show sync timestamps, ENCODE adoption, or historical_end_skipped counts. When ERPNext goes live, the sync layer disappears. The dashboard reads tabBin directly — the source of truth regardless of how data gets there.

### How the data flows

```
tabBin (Frappe) → /api/inventory?action=warehouse_stock&warehouse=<store> → useWarehouseStock hook
                → /api/inventory?action=inventory_matrix&facility_mode=stores → useInventoryMatrix hook
Order data      → /api/ordering?action=orderable_items&store=<store> → useOrderableItems hook
Store scope     → useUserStore hook → resolves current user's store warehouse
```

### Existing patterns to follow

- **Store scoping:** `useUserStore()` hook resolves the logged-in user's store. Used by ordering, opening, closing pages.
- **Role guard:** `<RoleGuard module={MODULES.STORE_OPS}>` — same as all store-ops pages.
- **Mobile card pattern:** Warehouse daily stock page (`/warehouse/inventory/daily`) uses card-based rows with big touch targets. Follow this pattern.
- **Category grouping:** Ordering page groups by `cargo_category` (FC/DRY/FM). Use the same grouping.
- **Status badges:** Warehouse matrix uses Critical (red) / Low (amber) / Healthy (green). Reuse `getStatusClasses()`.

---

## Scope

### Phase A: "My Stock" Page (13 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| A1 | BUILD | `bei-tasks/app/dashboard/store-ops/inventory/page.tsx` | **[BUILD]** Create the store inventory page with **responsive dual layout**: (1) **Mobile (<768px):** grouped card list with sticky category headers (DRY/COLD/FROZEN/CHILLED), each card showing item name, item code, current qty (large font), stock status badge (Critical/Low/Healthy), UOM. Big touch targets. (2) **Desktop (>=768px):** dense sortable table with columns: Item, Category, Qty, Status, Days Left, Demand, Suggested Order, UOM. Pinned status column on right (same pattern as warehouse matrix). Shared across both: search bar, category filter chips, sort options (risk-first default, qty high-low, alpha). Switch via Tailwind `hidden md:block` / `md:hidden`. Uses `useWarehouseStock(storeWarehouse)`. | 5 |
| A2 | BUILD | `bei-tasks/app/dashboard/store-ops/inventory/page.tsx` | **[BUILD]** Add demand + days-of-stock columns to each card. Pull from `useOrderableItems` to merge `forecast_demand`, `available_to_promise`, and `risk_rank` onto each stock card. Show "~X days left" in amber/red when low. Show "Next order: Y units suggested" when available. | 3 |
| A3 | BUILD | `bei-tasks/app/dashboard/store-ops/inventory/page.tsx` | **[BUILD]** Add summary strip at top: 4 cards showing Total SKUs, Critical Items (count, red if >0), Low Stock Items (count), Overstock Items (qty > 2x suggested). This gives the birds-eye view at a glance. | 2 |
| A4 | BUILD | `bei-tasks/lib/constants.ts` + `bei-tasks/components/layout/nav-main.tsx` | **[EXTEND]** Add route `STORE_OPS_INVENTORY: "/dashboard/store-ops/inventory"` to constants. Add sidebar entry with Package icon between "Ordering" and "Order Approvals" in the store-ops nav group. | 1 |
| A5 | BUILD | `bei-tasks/app/dashboard/store-ops/inventory/page.tsx` | **[BUILD]** Add order window banner: when `useOrderSchedule` returns `allowed: true`, show a top banner "Order window open until {cutoff_time} — [Place Order]" linking to the ordering page. When closed, show "Next delivery: {next_delivery_day}". | 1 |
| A6 | BUILD | `bei-tasks/app/dashboard/store-ops/inventory/page.tsx` | **[BUILD]** Add CSV export button. Export all items with: item_code, item_name, category, qty, status, days_of_stock, forecast_demand, suggested_order_qty. Uses the same `csvEscape` pattern from warehouse inventory. | 1 |

### Phase B: Area Supervisor Multi-Store View (6 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| B1 | BUILD | `bei-tasks/app/dashboard/store-ops/inventory/page.tsx` | **[BUILD]** For Area Supervisor role: add a store picker dropdown at top (same pattern as order-approvals page). Default to "All My Stores" aggregate view. Selecting a specific store shows that store's card list. | 2 |
| B2 | BUILD | `bei-tasks/app/dashboard/store-ops/inventory/page.tsx` | **[BUILD]** "All My Stores" view: show a compact table (not cards) with one row per store: store name, total SKUs, critical count, low count, last order date. Tapping a row navigates to that store's card view. | 2 |
| B3 | BUILD | `bei-tasks/app/dashboard/store-ops/inventory/page.tsx` | **[BUILD]** Add "Stockout Alert" tab/filter: across all supervised stores, show items where `is_oos: true` or `risk_rank >= 8`. Grouped by item (showing which stores are affected). This is the Area Sup's daily priority list. | 2 |

### Phase C: Polish + Sentry + Closeout (4 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| C1 | FIX | Empty/error/loading states: skeleton loader while fetching, "No items found" empty state with illustration, error boundary with retry button. Mobile responsive: test at 375px width. | 1 |
| C2 | FIX | **DM-7 Sentry:** If any new `@frappe.whitelist()` endpoints are added to the backend, add `set_backend_observability_context()`. If backend is unchanged (API reuse only), this is N/A. Confirm in closeout. | 1 |
| C3 | BUILD | Commit, create PR to bei-tasks `main`, deploy to Vercel. | 1 |
| C4 | BUILD | Closeout: update plan YAML to COMPLETED, update SPRINT_REGISTRY.md, `git add -f docs/plans/ output/l3/S122/`, push. | 1 |

**Total: 23 units.**

---

## Rollback Plan

This is a frontend-only sprint in bei-tasks (Vercel auto-deploy). Rollback = revert the PR on `main`. No backend changes, no data mutations, no risk to production Frappe data.

---

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| test.crew@bebang.ph | Navigate to Store Ops > Inventory via sidebar | Page loads, shows stock cards grouped by category for user's store | Route/nav broken |
| test.crew@bebang.ph | Search for "LECHE" in search bar | FG001-A (LECHE FLAN x 12) card appears | Search broken |
| test.crew@bebang.ph | Tap "Critical" filter chip | Only Critical-status items shown | Filter broken |
| test.crew@bebang.ph | View summary strip | Shows Total SKUs, Critical count, Low count, Overstock count | Summary calc broken |
| test.crew@bebang.ph | Check a low-stock item card | Shows "~X days left" + "Suggested: Y units" | Demand data not merged |
| test.areasup@bebang.ph | Navigate to Store Ops > Inventory | Shows store picker + "All My Stores" aggregate view | RBAC/multi-store broken |
| test.areasup@bebang.ph | Tap a specific store row | Drills into that store's card list view | Navigation broken |
| test.areasup@bebang.ph | Switch to "Stockout Alerts" tab | Shows cross-store OOS/high-risk items grouped by item | Alert aggregation broken |
| test.crew@bebang.ph | Click "Export CSV" | Downloads CSV with all items + stock + demand columns | Export broken |
| test.crew@bebang.ph | View page when order window is open | Banner shows "Order window open — Place Order" link | Banner/schedule broken |

Evidence files required before closeout:
```
output/l3/S122/form_submissions.json
output/l3/S122/api_mutations.json
output/l3/S122/state_verification.json
```

---

## Requirements Regression Checklist

- [ ] Does the page use `useUserStore()` for store scoping (not hardcoded)?
- [ ] Does the page use `<RoleGuard module={MODULES.STORE_OPS}>` for access control?
- [ ] Does mobile (<768px) show card layout with sticky category headers?
- [ ] Does desktop (>=768px) show dense sortable table with pinned status column?
- [ ] Does responsive switch use Tailwind `md:` breakpoint (not JS resize)?
- [ ] Are items grouped by cargo category (DRY/COLD/FROZEN/CHILLED)?
- [ ] Does the summary strip show Critical/Low/Overstock counts?
- [ ] Does each card show days-of-stock from demand data?
- [ ] Does the order window banner use `useOrderSchedule` (not hardcoded times)?
- [ ] Does Area Supervisor see multi-store view with store picker?
- [ ] Does the Stockout Alert tab aggregate across supervised stores?
- [ ] Is no sync-freshness feature built (no ENCODE tracking, no sync timestamps)?
- [ ] Are existing `useWarehouseStock` and `useOrderableItems` hooks reused (no new backend APIs)?
- [ ] Does every new/modified `@frappe.whitelist()` endpoint call `set_backend_observability_context()`? (N/A if backend unchanged)

---

## Autonomous Execution Contract

- **completion_condition:**
  - Store inventory page renders at `/dashboard/store-ops/inventory`
  - Sidebar entry visible for Store Staff, Store Supervisor, Area Supervisor roles
  - Card list shows stock with demand data merged
  - Summary strip shows correct counts
  - Area Supervisor sees multi-store view
  - Stockout Alert tab works
  - Order window banner links to ordering page
  - CSV export works
  - Page works at 375px mobile width
  - Plan YAML status = COMPLETED, pushed
  - SPRINT_REGISTRY.md updated

- **stop_only_for:**
  - `useWarehouseStock` or `useOrderableItems` APIs return unexpected data structure
  - bei-tasks repo access issues
  - Business-data decision needed (e.g., what threshold = "overstock"?)

- **continue_without_pause_through:**
  - code → PR → Vercel deploy → L3 → closeout

- **blocker_policy:**
  - programmatic → fix and continue
  - Vercel deploy failure → check logs, fix, redeploy
  - business-data → pause

- **signoff_authority:** single-owner (Sam Karazi, CEO)

---

## Remote-Truth Baseline

| Repo | Branch | HEAD SHA |
|------|--------|---------|
| bei-tasks | main | *(fill at execution start)* |

---

## Agent Boot Sequence

1. Read this plan fully — including the Requirements Regression Checklist.
2. **Create sprint branch:** `cd ../bei-tasks && git fetch origin main && git checkout -b s122-store-inventory-dashboard origin/main`
3. Read `hooks/use-inventory.ts` — the `useWarehouseStock` and `useInventoryMatrix` hooks.
4. Read `hooks/use-ordering.ts` — the `useOrderableItems` and `useOrderSchedule` hooks.
5. Read `app/dashboard/warehouse/inventory/daily/page.tsx` — the mobile card pattern to follow.
6. Read `app/dashboard/store-ops/ordering/page.tsx` — the store-scoped ordering workspace (thin wrapper).
7. Read `lib/constants.ts` lines 48-58 — existing STORE_OPS routes.
8. Read `components/layout/nav-main.tsx` — sidebar navigation structure.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

## Execution Workflow
- Develop in bei-tasks repo on branch `s122-store-inventory-dashboard`
- Test locally: `cd ../bei-tasks && npm run dev`
- Deploy: create PR to `main` → Vercel auto-deploys preview → merge → production auto-deploy
- Validate: L3 scenarios on https://my.bebang.ph after deploy
