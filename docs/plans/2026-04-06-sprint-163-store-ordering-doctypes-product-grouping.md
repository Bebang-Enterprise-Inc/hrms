# S163: Store Ordering Config Migration to DocTypes + Product Grouping (Mango, Banana Cinnamon, etc.)

> **AUDIT v2 (2026-04-06):** 4 parallel domain audits found 20 CRITICAL, 28 WARNING, 17 INFO. The plan was revised to swap the JSON `resolution_lines` model for a **multi-row child DocType model**, which eliminates 6 of 20 critical findings (pick list breakage, receiving leak, Frappe anti-pattern, Link field violation, qty_dispatched ambiguity, audit trail). 13 other tactical fixes incorporated. See `output/plan-audit/s163-store-ordering-doctypes-product-grouping/CONSOLIDATED_REPORT.md` for details.

```yaml
sprint: S163
branch: s163-store-ordering-doctypes-product-grouping
status: COMPLETED
planned_date: 2026-04-06
execution_started: 2026-04-06
completed_date: 2026-04-07
execution_summary: |
  All 11 phases delivered and verified live on hq.bebang.ph + my.bebang.ph.
  Migration: 25 component recipes + 29 product policies in DocTypes (parity exact match).
  Seed: 6 of 9 BEI Store Item Groups live (3 mixed-UOM groups pending SCM conversion factors — see docs/s163_pending_group_review.md).
  L3: API layer 6/6 groups verified, negative checks 17/17 pass. UI L3 scenarios 1-7 pass after hotfix #467. Scenario 8 (MR auto-creation) confirmed indirectly via cleanup (3 MRs created during testing).
  Bugs found + fixed post-deploy: (1) savepoint sanitization + rollback_to_savepoint missing on MariaDB — PR #462; (2) check_scm_permission kwarg mismatch blocking resolve_group_order_item — hotfix PR #467; (3) is_group_row missing from frontend StoreOrderItem type — hotfix BEI-Tasks #344.
  Test data cleaned up via /frappe-bulk-edits: 8 BEI Store Orders + 3 Material Requests + 13 approval queue entries + 13 ToDo assignments removed.
  CSV fixtures deleted in this commit (Phase 11.1).
prs:
  - hrms#461 — feat(S163): CSV→DocType migration + product grouping (Phases 0-9)
  - hrms#462 — fix(S163): migration savepoint bugs + live evidence
  - hrms#464 — feat(S163): seed 6 BEI Store Item Group records
  - hrms#467 — fix(S163): check_scm_permission kwarg hotfix
  - BEI-Tasks#342 — feat(S163): Product grouping frontend
  - BEI-Tasks#344 — fix(S163): is_group_row type
  - BEI-Tasks#345 — fix(S163/6.5): Show options auto-hide
plan_file: docs/plans/2026-04-06-sprint-163-store-ordering-doctypes-product-grouping.md
registry_row: "| `S163` | Sprint 163 | `s163-store-ordering-doctypes-product-grouping` | — | PLANNED — Migrate component recipes + product policies from CSV to DocTypes. Add Item Group abstraction so stores order by display name (Mango/Banana Cinnamon) and SCM picks/splits actual SKUs at dispatch time. Multi-row model. Audit-revised. | `docs/plans/2026-04-06-sprint-163-store-ordering-doctypes-product-grouping.md` |"
repos: hrms (backend, fixtures), bei-tasks (frontend)
depends_on: S161 (store ordering hotfixes), S159 (BOM data fix)
```

---

## Context

S161 left two structural gaps that this sprint closes:

1. **CSV-as-config debt.** Two critical config files live as flat CSVs in the repo:
   - `hrms/fixtures/store_ordering/store_order_component_recipes.csv` (98 rows)
   - `hrms/fixtures/store_ordering/store_order_product_policies.csv` (31 rows after S161 add-on additions)

   Every change to these files requires: edit → commit → PR → merge → image rebuild → restart (3-15 min). Arnold and Sam can't update them in real time. There's no audit trail, validation, or permission control. The Frappe-native pattern is DocTypes.

2. **No Product Grouping.** S161 audit found 9 groups of duplicate SKUs (RAG, Banana Cinnamon, Frozen Mango, etc.). Stores see 3 different "Banana Cinnamon" rows for the same physical product. The fast-food industry pattern (McDonald's, Starbucks, Restaurant365) is: stores order by **display name** (one entry per ingredient), and the warehouse picks the actual SKU at dispatch time based on availability and FIFO. We need that abstraction layer.

The CEO directive (2026-04-06): "do them in the same sprint." Both changes touch the same data model and the same get_orderable_items pipeline, so bundling avoids two rounds of pipeline rework.

---

## Design Rationale (For Cold-Start Agents)

### Why CSV → DocType migration

**The CSVs were built quickly during S155** when the demand pipeline was first wired. They were a one-time extract from Arnold's BOM workbook. No DocType was created because the team was racing to get demand signals working at all. Now the data is stable enough to need proper governance:
- Arnold needs to update portions when recipes change (currently impossible without engineering)
- Audit trail is required (compliance asks "who changed Banana Cinnamon's portion?")
- Validation prevents typos (CSV `RM010-A` vs `RM010A` silently breaks the recipe)
- Permission control: only commissary/SCM should edit recipes

**Why not use Frappe's built-in BOM doctype?** Frappe's `BOM` is designed for manufacturing with cost rollup, operations, work orders, etc. Our store ordering recipes are simpler (just `recipe_key → [item, qty]` pairs). Using BOM would force us into the manufacturing module's overhead and submission workflow, which is overkill.

### Why a custom Item Group DocType (not Frappe Item Variants)

**Frappe has built-in `variant_of`/`Item Variant` support**, but it's designed for products that differ only in attributes (size, color) and share a common BOM/template. Our case is different:
- Different UOMs per member (KG vs PACK)
- Different physical formats (bulk vs vacuum-pack)
- Different suppliers with different cost
- Items already exist as standalone SKUs with stock, history, and audit trail

**Audit confirmed `variant_of` is NULL for all 152 store items.** Forcing migration to Frappe Item Variants would require:
- Recreating every item as a variant with attribute fields
- Migrating all stock records
- Migrating order history
- Massive risk of data loss

**Custom `BEI Store Item Group` DocType** keeps existing items untouched. The group is a thin display/dispatch abstraction layer.

### Why allow SKU split (not single-SKU per order line)

User decision (2026-04-06): if a store orders 5 KG of Frozen Mango and the source warehouse has 3 KG of RM010-A and 2 KG of RM030, SCM should be able to split the dispatch across both SKUs. Single-SKU-only would force the store to short by 2 KG even though total stock exists.

### Why member priority field (not bin creation date / true FIFO)

User decision (2026-04-06): Stock Ledger Entry data is unreliable in BEI today (S138 reset, ongoing inventory sync issues). Member priority is configured by SCM in Frappe Desk and is predictable. Future enhancement (separate sprint) can layer real FIFO from SLE dates on top.

### Why store sees group name only

User decision (2026-04-06): The whole point of grouping is to hide SKU complexity from stores. Showing actual SKUs on the receiving page would defeat the purpose. Internal audit trail still records the dispatched SKUs in BEI Store Order Item.

### Key trade-off decisions

1. **Breaking the existing CSV vs gradual migration:** Migrate to DocType in one cutover. Read the CSV once during migration, write to DocType, switch the loader, delete the CSVs. No "read from both" hybrid mode (proven anti-pattern).

2. **Inline group resolution at order submit vs lazy at SCM review:** Resolve at SCM review time. The store ordering page just sends the group code; the order item stores the group code and a `is_group_order=1` flag. Resolution happens in the SCM Order Review UI before MR creation. Reason: ATP at order time may not match ATP at dispatch time (orders accumulate in the queue).

3. **One MR row per group vs one MR row per resolved SKU:** One MR row per resolved SKU. The MR is the warehouse's contract with picking — it must contain real item codes the warehouse can find in bins. The group code is preserved on the parent BEI Store Order Item for audit.

4. **Group is opt-in:** Items not in any group behave exactly as before. The migration creates groups only for the 9 candidates from S161 audit; everything else stays as individual items.

### Sources for cold-start agents

- S161 audit results: 9 consolidation groups, 25 SKUs, 152 active items → `output/l3/s161/`
- S161 add-on BOM PR #460: 13 new ADDON-* recipes (must be in CSV before migration runs)
- BEBANG STANDARD BOM cleanroom file: `data/_CLEANROOM/factcheck_packets/supply_chain_cleanroom_stage_e_2026-03-02_w1_a2/sources/BEBANG STANDARD BOM PER SKU.xlsx`
- Existing CSV files: `hrms/fixtures/store_ordering/store_order_component_recipes.csv` (line counts: ~98 + 13 added by PR #460), `store_order_product_policies.csv` (~31 rows)
- Existing CSV loaders: `hrms/utils/store_order_demand_snapshot.py` lines 17-21 (paths), 342-369 (`load_product_policy_catalog`), 372-395 (`load_component_recipe_catalog`), 421-504 (`resolve_product_mapping`), 331-339 (`load_bom_catalog`)
- Existing parent+child DocType template: `hrms/hr/doctype/bei_store_order/bei_store_order.json` + `hrms/hr/doctype/bei_store_order_item/bei_store_order_item.json`
- get_orderable_items: `hrms/api/store.py:2197+`
- submit_order: `hrms/api/store.py:2708+`
- approve_order + _create_mr_for_store_order: `hrms/api/store.py:3020+, 3212+`
- get_orders_for_dispatch + update_qty_dispatched: `hrms/api/store.py:6643+, 6703+`
- Pick list generation: `hrms/api/picking.py:44+, 257+`
- SCM Order Review page: `bei-tasks/app/dashboard/scm/order-review/page.tsx`
- Frontend ordering page: `bei-tasks/app/dashboard/store-ops/ordering/_components/StoreOrderingPage.tsx`

---

## End-to-End SCM Workflow (When Store Orders a Grouped Product)

This is the answer to "how the SCM team will issue the correct SKU." Walking through with Frozen Mango as the example:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 1: STORE ORDERING PAGE (my.bebang.ph)                                 │
│                                                                             │
│  Store sees ONE row: "Frozen Mango — 12.5 KG on hand, 0.9 days left"        │
│  (Stock and demand are SUMS across RM010-A + RM030 at this store)           │
│                                                                             │
│  Store enters: 5 KG → Submit                                                │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 2: BACKEND submit_order()                                             │
│                                                                             │
│  Receives: { item_code: "GRP-FROZEN-MANGO", qty_requested: 5, is_group: 1 } │
│                                                                             │
│  Creates BEI Store Order Item:                                              │
│    item_group_code = "GRP-FROZEN-MANGO"  (NEW field)                        │
│    item_code = "GRP-FROZEN-MANGO" (group code as placeholder)               │
│    is_group_order = 1  (NEW field)                                          │
│    group_resolution_status = "Pending" (NEW field)                          │
│    qty_requested = 5                                                        │
│    proposed_resolution = JSON: [                                            │
│      {member: "RM010-A", qty: 5, source_wh: "3MD Camangyanan", priority: 1} │
│    ]  (auto-computed from member priority + ATP at submit time)             │
│                                                                             │
│  Order moves to Pending Approval                                            │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 3: AREA SUPERVISOR APPROVAL (existing flow)                           │
│                                                                             │
│  Approver sees: "Frozen Mango — 5 KG"                                       │
│  Can adjust qty_approved (existing behavior)                                │
│  Approval does NOT resolve the group → that's SCM's job                     │
│                                                                             │
│  approve_order() → status = "Approved"                                      │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 4: SCM ORDER REVIEW PAGE (NEW group-resolution UI)                    │
│                                                                             │
│  /dashboard/scm/order-review                                                │
│                                                                             │
│  Order line displays:                                                       │
│    [GROUP] Frozen Mango ── 5 KG ── Auto-resolved: RM010-A (5 KG @ 3MD)      │
│                                                              [Override...]  │
│                                                                             │
│  SCM clicks "Override" → modal opens:                                       │
│                                                                             │
│    ┌─────────────────────────────────────────────────────────────────┐      │
│    │ Resolve: Frozen Mango — 5 KG                                    │      │
│    ├─────────────────────────────────────────────────────────────────┤      │
│    │  Member SKU      | Source         | Stock | Pick Qty           │      │
│    │  RM010-A         | 3MD Camangyanan| 500 KG| [3.0]              │      │
│    │  RM010-A         | Pinnacle       | 500 KG| [0.0]              │      │
│    │  RM030 (PACK)    | 3MD Camangyanan| 200 PK| [2.0]              │      │
│    │  RM030 (PACK)    | Pinnacle       | 200 PK| [0.0]              │      │
│    │                                                                 │      │
│    │  Total: 5.0 KG (matches qty_requested) ✓                        │      │
│    │                                              [Cancel] [Save]    │      │
│    └─────────────────────────────────────────────────────────────────┘      │
│                                                                             │
│  POST /api/method/hrms.api.store.resolve_group_order_item                   │
│    Backend updates BEI Store Order Item:                                    │
│      group_resolution_status = "Manual"                                     │
│      resolution_lines = JSON [                                              │
│        {member_item: "RM010-A", source_wh: "3MD...", qty: 3.0},             │
│        {member_item: "RM030",   source_wh: "3MD...", qty: 2.0}              │
│      ]                                                                      │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 5: MR CREATION (existing _create_mr_for_store_order, EXTENDED)        │
│                                                                             │
│  When the order is marked Ready for Dispatch:                               │
│                                                                             │
│  For each BEI Store Order Item:                                             │
│    if is_group_order:                                                       │
│      For each line in resolution_lines:                                     │
│        Create Material Request Item with:                                   │
│          item_code = line.member_item   (REAL SKU, not group)               │
│          qty = line.qty                                                     │
│          warehouse = line.source_wh                                         │
│          custom_source_group_code = "GRP-FROZEN-MANGO"  (audit)             │
│          custom_source_order_item = order_item.name  (audit)                │
│    else:                                                                    │
│      Existing flow: one MR row per order item                               │
│                                                                             │
│  MR submitted with REAL SKUs only                                           │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 6: PICK LIST + WAREHOUSE PICKING (existing flow, unchanged)           │
│                                                                             │
│  Pick list reads MR Items → already has real SKUs                           │
│  Warehouse picks RM010-A (3 KG) and RM030 (2 PACK)                          │
│  No knowledge of groups at the picking layer                                │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 7: STOCK ENTRY + DELIVERY (existing flow, unchanged)                  │
│                                                                             │
│  Stock Entry posts the actual SKUs                                          │
│  Trip stop delivers physical items                                          │
│  Store receives 3 KG RM010-A + 2 KG RM030                                   │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 8: STORE RECEIVING PAGE (group-aware view)                            │
│                                                                             │
│  Store sees: "Frozen Mango — 5 KG received ✓"                               │
│  (Hides the SKU detail; clicking the row could expand it for audit)         │
│                                                                             │
│  Store stock updates per SKU (RM010-A +3, RM030 +2) — accurate Bin records  │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key invariants:**
- The store NEVER sees the SKU split. They see "Frozen Mango — 5 KG."
- Material Request, Pick List, Stock Entry all contain REAL item codes — no group abstraction in those layers.
- The audit trail on `BEI Store Order Item` records both the group code and the resolved SKU(s).
- If a group has only ONE member with stock, auto-resolution sets `group_resolution_status = "Auto"` and SCM doesn't need to touch it (no extra clicks for the common case).
- If SCM never opens the override modal, the auto-resolution proceeds to MR creation as-is.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  NEW DOCTYPES (Frappe Desk editable)                                 │
│                                                                      │
│  BEI Store Order Component Recipe (parent)                           │
│   ├── recipe_key (Data, unique)                                      │
│   ├── description (Small Text)                                       │
│   ├── disabled (Check)                                               │
│   └── components (Table → BEI Store Order Component Recipe Item)     │
│                                                                      │
│  BEI Store Order Component Recipe Item (child, istable=1)            │
│   ├── item_code (Link → Item, reqd)                                  │
│   ├── item_name (fetch from item_code)                               │
│   ├── qty_per_unit (Float, precision=6, reqd)                        │
│   ├── portion_g (Float)                                              │
│   ├── container_yield_g (Float)                                      │
│   └── note (Small Text)                                              │
│                                                                      │
│  BEI Store Order Product Policy (parent)                             │
│   ├── product_name (Data, reqd)                                      │
│   ├── product_code (Data) — POS SKU                                  │
│   ├── policy_type (Select: component_recipe / fg_recipe / exclude)   │
│   ├── target_recipe (Link → BEI Store Order Component Recipe)        │
│   ├── exclude_reason (Small Text)                                    │
│   ├── disabled (Check)                                               │
│   └── note (Small Text)                                              │
│                                                                      │
│  BEI Store Item Group (parent)                                       │
│   ├── group_code (Data, unique) — e.g., "GRP-FROZEN-MANGO"           │
│   ├── display_name (Data) — e.g., "Frozen Mango"                     │
│   ├── display_uom (Link → UOM)                                       │
│   ├── delivery_lane (Select: Frozen / Dry)                           │
│   ├── disabled (Check)                                               │
│   ├── members (Table → BEI Store Item Group Member)                  │
│   └── note (Small Text)                                              │
│                                                                      │
│  BEI Store Item Group Member (child, istable=1)                      │
│   ├── item_code (Link → Item, reqd)                                  │
│   ├── item_name (fetch from item_code)                               │
│   ├── stock_uom (fetch from item_code)                               │
│   ├── conversion_to_display (Float, default 1.0)                     │
│   ├── priority (Int, reqd) — lower = picked first                    │
│   └── note (Small Text)                                              │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  EXTENDED DOCTYPE: BEI Store Order Item (4 new fields)               │
│  AUDIT-FIX (2026-04-06): Multi-row model — see decision below.       │
│                                                                      │
│   ├── item_code (Link → Item)  ←── NEVER "GRP-*", always real SKU    │
│   │   For grouped orders, this is the resolved member SKU.           │
│   │   The auto-resolution at submit_order picks the first member.    │
│   │                                                                  │
│   ├── item_group_code (Link → BEI Store Item Group, optional)        │
│   │   Audit backref to the group this row was resolved from.         │
│   │                                                                  │
│   ├── group_order_seq (Int, optional)                                │
│   │   Sibling-row identifier. All rows from the same store ordering  │
│   │   line share the same seq number, so the frontend can group them │
│   │   back into one display line.                                    │
│   │                                                                  │
│   ├── group_resolution_status (Select: Pending/Auto/Manual)          │
│   │   On the row representing the canonical line.                    │
│   │                                                                  │
│   └── group_qty_requested_total (Float, optional)                    │
│       Total qty the store ordered for this group line — used to      │
│       validate sum of sibling rows in resolve_group_order_item.      │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  MULTI-ROW MODEL — Why we changed from JSON resolution_lines         │
│                                                                      │
│  AUDIT FOUND: storing resolution as Long Text JSON breaks pick list, │
│  receiving page, Stock Entry, audit trail, and Frappe relational     │
│  semantics. The original plan used `item_code = "GRP-*"` placeholder │
│  which leaked into 4 downstream surfaces (pick list, receiving,      │
│  billing, FQI) — the Stock Entry rejects GRP-* because it's not a    │
│  valid Item.                                                         │
│                                                                      │
│  FIXED: When a store submits a grouped order line for "Frozen Mango  │
│  5 KG", submit_order creates ONE OR MORE BEI Store Order Item rows,  │
│  one per resolved (member SKU, source warehouse) tuple. Each row has │
│  a real item_code that downstream code can use as-is.                │
│                                                                      │
│  Example: store orders "Frozen Mango 5 KG", auto-resolution picks    │
│  RM010-A from 3MD. submit_order creates ONE row:                     │
│    item_code = "RM010-A", qty = 5, item_group_code = "GRP-FROZEN-",  │
│    group_order_seq = 1, group_resolution_status = "Auto"             │
│                                                                      │
│  When SCM overrides via the modal to split 3 KG RM010-A + 2 KG RM030 │
│  resolve_group_order_item DELETES the existing sibling rows and      │
│  CREATES new rows:                                                   │
│    Row A: item_code = "RM010-A", qty = 3, group_order_seq = 1, ...   │
│    Row B: item_code = "RM030",   qty = 2, group_order_seq = 1, ...   │
│  Both rows share group_order_seq=1, so the frontend groups them.     │
│                                                                      │
│  Benefits:                                                           │
│   ✓ Pick list works unchanged (already iterates BEI Store Order Item)│
│   ✓ Receiving page works unchanged                                   │
│   ✓ Stock Entry works unchanged                                      │
│   ✓ Frappe relational queries work (Link validation, joins, search)  │
│   ✓ Audit trail per row (track_changes records each qty edit)        │
│   ✓ No JSON parsing in the hot path                                  │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  PIPELINE READS                                                      │
│                                                                      │
│  store_order_demand_snapshot.py                                      │
│    load_component_recipe_catalog() ──→ now reads from DocType         │
│    load_product_policy_catalog()   ──→ now reads from DocType         │
│    (CSV files DELETED post-migration)                                 │
│                                                                      │
│  store.py get_orderable_items()                                       │
│    1. Query all active BEI Store Item Group + members                 │
│    2. For each group: SUM stock + SUM demand across members           │
│    3. Replace member rows with one virtual group row in response      │
│    4. Non-grouped items unchanged                                     │
│                                                                      │
│  store.py submit_order()                                              │
│    For each item:                                                     │
│      if item_code starts with "GRP-": resolve via BEI Store Item Group│
│        compute proposed_resolution (priority * ATP)                   │
│        store group_code + resolution JSON on order item               │
│      else: existing flow                                              │
│                                                                      │
│  NEW: store.py resolve_group_order_item()                             │
│    SCM endpoint to override the auto-resolution                       │
│                                                                      │
│  store.py _create_mr_for_store_order() (EXTENDED)                     │
│    For grouped items: expand resolution_lines into individual MR rows │
│    Non-grouped items: existing flow                                   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Decisions Made (User-Confirmed 2026-04-06)

| Decision | Choice | Why |
|----------|--------|-----|
| Plan size | One sprint (S163) covering both DocType migration and Product Grouping | User directive — they're tightly coupled (both touch get_orderable_items) |
| SKU split | SCM can split one order line across multiple SKUs and source warehouses | Handles partial stock; matches real warehouse behavior |
| FIFO logic | Member `priority` field configured in Frappe Desk | SLE data unreliable in BEI; can layer true FIFO later |
| Store receiving view | Group name only | Hides SKU complexity from stores; full audit trail preserved on order item |
| Migration cutover | One-shot (CSV → DocType, then delete CSVs) | No hybrid read mode; proven anti-pattern |
| Group opt-in | Yes — items not in any group behave unchanged | Avoids touching 130+ working items |

---

## Duplication Audit

| Feature | Classification | Existing Code |
|---------|---------------|---------------|
| Component recipe storage | **[EXTEND]** | CSV at `hrms/fixtures/store_ordering/store_order_component_recipes.csv` (loaded by `load_component_recipe_catalog` at `store_order_demand_snapshot.py:372`) — replace with DocType-backed loader |
| Product policy mapping | **[EXTEND]** | CSV at `hrms/fixtures/store_ordering/store_order_product_policies.csv` (loaded by `load_product_policy_catalog` at `store_order_demand_snapshot.py:342`) — replace with DocType-backed loader |
| Item grouping | **[BUILD]** | No existing code. `variant_of` is NULL for all 152 store items per S161 audit. No "alternate SKU" or "substitute" fields exist anywhere |
| SCM order review page | **[EXTEND]** | `bei-tasks/app/dashboard/scm/order-review/page.tsx` exists with qty_dispatched override — add group resolution modal to same page |
| Order submit pipeline | **[EXTEND]** | `submit_order()` at `store.py:2708+` — add group detection branch |
| MR creation | **[EXTEND]** | `_create_mr_for_store_order()` at `store.py:3212+` — add resolution_lines expansion for grouped items |
| Pick list / Stock Entry | **[SKIP]** | Already operates on real item codes; no changes needed downstream of MR |
| Frappe Item Variants | **[SKIP]** | Built-in `variant_of` does not fit (different UOMs, suppliers, formats); custom DocType is the right approach |

---

## Critical Files to Modify

| File | Repo | Phase | Change |
|------|------|-------|--------|
| `hrms/hr/doctype/bei_store_order_component_recipe/bei_store_order_component_recipe.json` | hrms | 1 | NEW DocType |
| `hrms/hr/doctype/bei_store_order_component_recipe_item/bei_store_order_component_recipe_item.json` | hrms | 1 | NEW child DocType |
| `hrms/hr/doctype/bei_store_order_product_policy/bei_store_order_product_policy.json` | hrms | 1 | NEW DocType |
| `hrms/hr/doctype/bei_store_item_group/bei_store_item_group.json` | hrms | 1 | NEW DocType |
| `hrms/hr/doctype/bei_store_item_group_member/bei_store_item_group_member.json` | hrms | 1 | NEW child DocType |
| `hrms/hr/doctype/bei_store_order_item/bei_store_order_item.json` | hrms | 1 | EXTEND with 4 new fields (item_group_code, is_group_order, group_resolution_status, resolution_lines) |
| `scripts/s163_migrate_csv_to_doctypes.py` | hrms | 2 | NEW migration script (SSM-deployed) |
| `hrms/utils/store_order_demand_snapshot.py` | hrms | 3 | Replace CSV loaders at lines 342, 372 with DocType queries |
| `hrms/api/store.py` (`get_orderable_items`) | hrms | 4 | Add group expansion: query BEI Store Item Group, SUM stock+demand, replace member rows with virtual group rows |
| `hrms/api/store.py` (`submit_order`) | hrms | 5 | Detect group codes, compute auto-resolution, store on order item |
| `hrms/api/store.py` (NEW `resolve_group_order_item`) | hrms | 6 | NEW endpoint for SCM to override auto-resolution |
| `hrms/api/store.py` (`_create_mr_for_store_order`) | hrms | 8 | Expand resolution_lines into individual MR rows |
| `hrms/api/store.py` (`get_orders_for_dispatch`) | hrms | 6 | Include group fields in response |
| `bei-tasks/app/dashboard/store-ops/ordering/_components/StoreOrderingPage.tsx` | bei-tasks | 7 | Render grouped items with group badge |
| `bei-tasks/app/dashboard/store-ops/ordering/_components/OrderItemTable.tsx` | bei-tasks | 7 | Show group name instead of SKU when item is group |
| `bei-tasks/app/dashboard/scm/order-review/page.tsx` | bei-tasks | 6 | Add Override button + modal for grouped items |
| `bei-tasks/app/dashboard/scm/order-review/_components/GroupResolutionModal.tsx` | bei-tasks | 6 | NEW component |
| `bei-tasks/hooks/use-ordering.ts` | bei-tasks | 7 | Add group fields to OrderableItem interface |
| `hrms/fixtures/store_ordering/store_order_component_recipes.csv` | hrms | 11 | DELETE post-migration |
| `hrms/fixtures/store_ordering/store_order_product_policies.csv` | hrms | 11 | DELETE post-migration |

---

## Existing Code to Reuse (DO NOT DUPLICATE)

| Function / Component | Location | Purpose |
|---|---|---|
| `BEI Store Order` parent+child template | `hrms/hr/doctype/bei_store_order/*` | Pattern for new parent+child DocTypes |
| `load_component_recipe_catalog()` | `store_order_demand_snapshot.py:372-395` | Function signature stays the same — replace internal CSV read with `frappe.get_all` |
| `load_product_policy_catalog()` | `store_order_demand_snapshot.py:342-369` | Same as above |
| `resolve_product_mapping()` | `store_order_demand_snapshot.py:421-504` | Unchanged — calls the loaders above; will work transparently after migration |
| `_build_orderable_source_stock_context()` | `store.py:1502+` | Reuse for group stock aggregation |
| `_resolve_delivery_lane()` | `store.py:1545+` | Reuse — group inherits lane from members |
| `_lane_to_cargo_category()` | `store.py:1262+` | Reuse |
| `update_qty_dispatched()` | `store.py:6703+` | Existing pattern for SCM order modifications — model the new `resolve_group_order_item` after this |
| `frappe-bulk-edits` skill | `.claude/skills/frappe-bulk-edits/` | For SSM execution of migration script |

---

## Functions That MUST NOT Break

| Function | Location | Why |
|---|---|---|
| `get_orderable_items()` | `store.py:2197+` | Core ordering API — changes must keep non-grouped items working identically |
| `submit_order()` | `store.py:2708+` | Order submission — must accept BOTH old format (item_code = real SKU) AND new format (item_code = GRP-*) |
| `approve_order()` | `store.py:3020+` | Approval flow unchanged — group resolution is post-approval, pre-MR |
| `_create_mr_for_store_order()` | `store.py:3212+` | MR creation — non-grouped items unchanged; grouped items expand to multiple MR rows |
| `_load_store_item_demand_snapshots()` | `store.py:1778+` | Demand snapshot reader — keys unchanged |
| `load_bom_catalog()` | `store_order_demand_snapshot.py:331+` | Tries Frappe BOM first, falls back to CSV — leave alone |
| `generate_pick_list()` | `picking.py:44+` | Reads MR items (real SKUs) — unchanged |
| `confirm_loaded()` | `picking.py:257+` | Creates Stock Entries from pick list — unchanged |

---

## Shell Prevention (S026)

### Failure patterns to prevent
- **Dead group resolution UI**: Override modal renders but Save button doesn't actually persist resolution_lines → MR is created with the group code instead of real SKUs → pick list fails
- **Silent CSV fallback**: Migration completes but the new loader still falls back to CSV when DocType returns empty → stale data masks the bug for days
- **Group code leaks into MR**: Forgetting to expand resolution_lines in `_create_mr_for_store_order` → Material Request submission fails because GRP-* is not a valid Item
- **Backwards compat break**: Changing the order item schema in a way that breaks existing pending orders during the deploy window

### Build Integrity Gates

| Gate | Status | Evidence |
|------|--------|----------|
| `gate_route_contract_defined` | Required | New endpoint `resolve_group_order_item` registered with `@frappe.whitelist()` and Sentry context |
| `gate_action_wiring_complete` | Required | Override button → modal → Save → POST → DB update → re-render — full chain wired |
| `gate_dependency_map_complete` | Required | Migration script depends on PR #460 (add-on recipes) being merged first |
| `gate_navigation_placement_defined` | N/A | No new routes — extends existing pages |
| `gate_empty_error_states_defined` | Required | What shows when a group has no members with stock anywhere; what shows when SCM tries to save split that exceeds qty_requested |
| `gate_mutation_outcomes_defined` | Required | resolve_group_order_item must return updated order item with new resolution_lines for the frontend to re-render |
| `gate_mobile_layout_defined` | Required | OrderItemCard.tsx mobile view must render group name correctly |
| `gate_seed_dependency_defined` | Required | The 9 BEI Store Item Group records must exist before the new ordering page goes live |

### Vertical slice first
Implement Phase 1 (DocTypes), Phase 2 (Migration), Phase 3 (Pipeline switch), then for grouping, do **Frozen Mango as the single vertical slice** through all phases (Phase 4-8) before adding the other 8 groups. This proves end-to-end correctness on one item before scaling.

---

## Phase 0: Reservation + Boot Sequence

**Estimated units: 3**

### Task 0.1: Reserve sprint and create branch

```
MUST_MODIFY: docs/plans/SPRINT_REGISTRY.md
MUST_CONTAIN: "S163"
MUST_CONTAIN: "s163-store-ordering-doctypes-product-grouping"
```

1. Read this plan fully.
2. Read `docs/plans/SPRINT_REGISTRY.md` and verify S163 row exists; if not, add it.
3. **Create branch:** `git fetch origin production && git checkout -b s163-store-ordering-doctypes-product-grouping origin/production`. Verify with `git branch --show-current`. NEVER write code on production.
4. Confirm PR #460 is merged (add-on recipes must be in production CSV before migration).
5. Read `docs/plans/SPRINT_REGISTRY.md` for cross-sprint context.

### Task 0.2: Pre-migration data audit

```
MUST_CREATE: output/s163/pre_migration_audit.json
```

Run a read-only Frappe script via SSM that captures:
- Current row count of `store_order_component_recipes.csv`
- Current row count of `store_order_product_policies.csv`
- Current count of items in each item_group
- Current `variant_of` distribution (should be NULL for all)
- List of any in-flight orders that would be affected by the schema change

This is the ground-truth baseline for verification at closeout.

---

## Phase 1: Create New DocTypes

**Estimated units: 8**

### Task 1.1: BEI Store Order Component Recipe (parent + child)

Create both DocType JSONs following the BEI Store Order template at `hrms/hr/doctype/bei_store_order/bei_store_order.json` + `bei_store_order_item.json`.

**AUDIT-FIX:** Parent JSON MUST include `"autoname": "field:recipe_key"`. Without this, Frappe assigns hash names and the migration's `frappe.db.exists("BEI Store Order Component Recipe", "FULL-BANANA-CINNAMON")` returns None, breaking idempotency. Same fix needed for `BEI Store Order Product Policy` (`field:product_name`) and `BEI Store Item Group` (`field:group_code`).

**Parent fields:**
- `recipe_key` (Data, reqd, unique, in_list_view)
- `description` (Small Text)
- `disabled` (Check, default 0)
- `components` (Table → BEI Store Order Component Recipe Item)
- `autoname` (DocType meta): `"field:recipe_key"`

**Child fields (`istable: 1`):**
- `item_code` (Link → Item, reqd)
- `item_name` (Data, fetch_from item_code.item_name, read_only, in_list_view)
- `qty_per_unit` (Float, reqd, precision 6, in_list_view)
- `portion_g` (Float)
- `container_yield_g` (Float)
- `note` (Small Text)

```
MUST_MODIFY: hrms/hr/doctype/bei_store_order_component_recipe/bei_store_order_component_recipe.json
MUST_MODIFY: hrms/hr/doctype/bei_store_order_component_recipe_item/bei_store_order_component_recipe_item.json
MUST_CONTAIN: "BEI Store Order Component Recipe Item"
MUST_CONTAIN: "istable"
```

### Task 1.2: BEI Store Order Product Policy

```
MUST_MODIFY: hrms/hr/doctype/bei_store_order_product_policy/bei_store_order_product_policy.json
MUST_CONTAIN: "policy_type"
MUST_CONTAIN: "target_recipe"
```

**Fields:**
- `product_name` (Data, reqd)
- `product_code` (Data) — POS SKU
- `policy_type` (Select: `component_recipe\nfg_recipe\nexclude`, reqd)
- `target_recipe` (Link → BEI Store Order Component Recipe, depends_on `policy_type == "component_recipe"`)
- `target_fg_name` (Data, depends_on `policy_type == "fg_recipe"`)
- `exclude_reason` (Small Text, depends_on `policy_type == "exclude"`)
- `disabled` (Check, default 0)
- `note` (Small Text)
- **`autoname` (DocType meta): `"field:product_name"`** (AUDIT-FIX)

### Task 1.3: BEI Store Item Group (parent + child)

```
MUST_MODIFY: hrms/hr/doctype/bei_store_item_group/bei_store_item_group.json
MUST_MODIFY: hrms/hr/doctype/bei_store_item_group_member/bei_store_item_group_member.json
MUST_CONTAIN: "group_code"
MUST_CONTAIN: "priority"
MUST_CONTAIN: "conversion_to_display"
```

**Parent fields:**
- `group_code` (Data, reqd, unique) — e.g., `GRP-FROZEN-MANGO`
- `display_name` (Data, reqd, in_list_view) — e.g., `Frozen Mango`
- `display_uom` (Link → UOM, reqd)
- `delivery_lane` (Select: `Frozen\nDry`, reqd)
- `disabled` (Check, default 0)
- `members` (Table → BEI Store Item Group Member)
- `note` (Small Text)
- **`autoname` (DocType meta): `"field:group_code"`** (AUDIT-FIX)

**Child fields (`istable: 1`):**
- `item_code` (Link → Item, reqd)
- `item_name` (Data, fetch_from item_code.item_name, read_only)
- `stock_uom` (Data, fetch_from item_code.stock_uom, read_only)
- `conversion_to_display` (Float, reqd, default 1.0) — multiply member qty by this to express in display UOM
- `priority` (Int, reqd, default 100) — lower = picked first
- `note` (Small Text)

### Task 1.4: Extend BEI Store Order Item (MULTI-ROW MODEL — AUDIT REVISED)

Add 4 new fields to existing `bei_store_order_item.json`. **DO NOT add a `resolution_lines` JSON field** — the audit found this was a Frappe anti-pattern. Instead, the multi-row model creates one row per (member SKU, source warehouse), and sibling rows from the same store ordering line share a `group_order_seq`.

```
MUST_MODIFY: hrms/hr/doctype/bei_store_order_item/bei_store_order_item.json
MUST_CONTAIN: "item_group_code"
MUST_CONTAIN: "group_order_seq"
MUST_CONTAIN: "group_resolution_status"
MUST_CONTAIN: "group_qty_requested_total"
```

- `item_group_code` (Link → BEI Store Item Group, optional) — audit backref to the group
- `group_order_seq` (Int, optional) — sibling-row identifier; rows from the same store ordering line share this
- `group_resolution_status` (Select: `\nPending\nAuto\nManual`, default empty) — set on the canonical row of each seq
- `group_qty_requested_total` (Float, optional) — total qty the store ordered; sum of sibling rows must equal this

**HARD BLOCKER #1:** Backwards compatibility. Existing pending orders MUST continue to work — when these fields are null, the item behaves exactly like a non-grouped item. No `reqd: 1` on any of the new fields.

**HARD BLOCKER #2:** `item_code` is and remains a `Link → Item, reqd: 1`. NEVER write a `GRP-*` value to `item_code`. If the agent is tempted to do this, STOP — it breaks downstream pick list, receiving, Stock Entry, and Frappe Link validation. Always store the resolved member SKU in `item_code` and the group code in `item_group_code`.

### Task 1.5: Run bench migrate

After all JSONs are committed, run `bench --site hq.bebang.ph migrate` via SSM to create the tables and apply the schema changes. Verify with a SQL count of new tables.

---

## Phase 2: Migration Script (CSV → DocType)

**Estimated units: 5**

### Task 2.1: Write migration script

```
MUST_CREATE: scripts/s163_migrate_csv_to_doctypes.py
MUST_CONTAIN: "BEI Store Order Component Recipe"
MUST_CONTAIN: "BEI Store Order Product Policy"
```

The script reads both CSVs (which already have PR #460 add-on recipes added) and inserts DocType records via SSM. Idempotent — re-running it does nothing if records already exist.

Pseudo-code (AUDIT-FIX: per-recipe savepoint to prevent half-baked records on partial failure):
```python
import csv, frappe
# Read store_order_component_recipes.csv
with open(...) as f:
    rows = list(csv.DictReader(f))

# Group by recipe_key
recipes = defaultdict(list)
for row in rows:
    recipes[row['recipe_key']].append(row)

# Insert parent + child for each recipe — PER-RECIPE SAVEPOINT
errors = []
for recipe_key, items in recipes.items():
    savepoint_name = f"migrate_{recipe_key.replace('-', '_')}"
    try:
        frappe.db.savepoint(savepoint_name)

        existing = frappe.db.exists("BEI Store Order Component Recipe", recipe_key)
        if existing:
            # AUDIT-FIX: don't blindly skip — verify the parent has all expected children.
            # If child count mismatches, log and skip with WARNING (don't auto-repair).
            existing_count = frappe.db.count(
                "BEI Store Order Component Recipe Item",
                filters={"parent": recipe_key},
            )
            if existing_count != len(items):
                errors.append(f"{recipe_key}: existing has {existing_count} children, CSV has {len(items)} — manual review")
            frappe.db.release_savepoint(savepoint_name)
            continue

        doc = frappe.new_doc("BEI Store Order Component Recipe")
        doc.recipe_key = recipe_key
        doc.description = items[0].get('note', '')
        for item in items:
            doc.append("components", {
                "item_code": item['item_code'],
                "qty_per_unit": flt(item['qty_per_unit']),
                "note": item.get('note', ''),
            })
        doc.insert(ignore_permissions=True)
        frappe.db.release_savepoint(savepoint_name)
    except Exception as e:
        frappe.db.rollback_to_savepoint(savepoint_name)
        errors.append(f"{recipe_key}: {e}")

# Same pattern for store_order_product_policies.csv → BEI Store Order Product Policy
# Final report: errors[] must be empty in evidence file
```

**HARD BLOCKER (audit fix DM-2):** Per-recipe savepoint is mandatory. Without it, a single bad row (typo, missing item_code, encoding issue) leaves a half-baked parent that re-runs cannot detect.

### Task 2.2: Execute migration via SSM

Use the `frappe-bulk-edits` skill pattern (boilerplate at top, base64 encode, docker exec). Capture before/after counts:

```
MUST_CREATE: output/s163/migration_evidence.json
```

Evidence must include:
- CSV row count read
- DocType records created
- Records skipped (idempotent)
- Errors (must be 0)

### Task 2.3: Manual verification

Open Frappe Desk → "BEI Store Order Component Recipe" list → confirm 12+ recipes (FULL-BANANA-CINNAMON, TIKIM-PRESIDENTIAL, ADDON-* including the 13 from PR #460, etc.). Open one record, verify the components child table has the right item codes.

---

## Phase 3: Switch Demand Pipeline to DocType Reads

**Estimated units: 6**

### Task 3.1: Replace `load_component_recipe_catalog` — DROP CSV FALLBACK (AUDIT FIX)

```
MUST_MODIFY: hrms/utils/store_order_demand_snapshot.py
MUST_CONTAIN: "BEI Store Order Component Recipe"
MUST_NOT_CONTAIN: "open(COMPONENT_RECIPE_PATH"
MUST_CONTAIN: "RuntimeError"
```

Replace the CSV-reading body of `load_component_recipe_catalog` (lines 372-395) with `frappe.get_all("BEI Store Order Component Recipe Item", filters={"parent": recipe_key}, ...)`. Function signature and return type stay identical so callers don't change.

**AUDIT-FIX:** Drop the CSV fallback entirely. The original plan said "fall back to CSV when no Frappe context — copy `load_bom_catalog` pattern" but Phase 11 deletes the CSVs. After Phase 11 the fallback would silently return empty dicts → corrupted demand snapshots in any standalone script. Replace the dual-mode pattern with:

```python
def load_component_recipe_catalog() -> dict[str, list[dict[str, Any]]]:
    try:
        import frappe
        if not frappe.db:
            raise RuntimeError(
                "load_component_recipe_catalog requires a Frappe context after S163. "
                "Initialize frappe via: frappe.init(site='hq.bebang.ph'); frappe.connect()"
            )
    except (ImportError, RuntimeError):
        raise RuntimeError(
            "load_component_recipe_catalog requires a Frappe context after S163. "
            "CSV fallback was removed because the source CSVs are deleted at Phase 11. "
            "Standalone scripts must boot a Frappe context."
        )
    # ... query DocType
```

This is intentional: any standalone script that imports these loaders MUST boot Frappe explicitly. The error message tells future developers exactly what to do.

Same pattern for `load_product_policy_catalog`.

### Task 3.2: Replace `load_product_policy_catalog`

Same pattern for the policy catalog (lines 342-369) → reads from BEI Store Order Product Policy.

### Task 3.3: Local test

Run `python scripts/s161_check_rm_store_orders.py` (or similar local pipeline test) and verify the demand snapshots still generate identically. Compare a sample of computed `qty_per_fg` values from before/after.

```
MUST_CREATE: output/s163/pipeline_parity_check.json
```

---

## Phase 4: Group Aggregation in get_orderable_items

**Estimated units: 10**

### Task 4.1: Query active groups

In `get_orderable_items()`, after the main item query, fetch all active `BEI Store Item Group` records with their members. Build:
- `groups_by_member_code: {item_code → group_record}`
- `groups: {group_code → {display_name, members, display_uom, delivery_lane}}`

```
MUST_MODIFY: hrms/api/store.py
MUST_CONTAIN: "BEI Store Item Group"
```

### Task 4.2: Aggregate stock and demand per group

For each group:
- `aggregated_store_actual = SUM(member.store_actual_qty * member.conversion_to_display) for each member`
- `aggregated_source_atp = SUM(member.available_to_promise * member.conversion_to_display) for each member`
- `aggregated_avg_daily_demand = SUM(demand_snapshot[member_code] * conversion) for each member`
- `aggregated_last_order_qty = MAX(last_qty_map[member_code])`

### Task 4.3: Replace member rows with virtual group rows

After enrichment, build the response:
- For items NOT in any group: pass through unchanged
- For each group: add ONE virtual row with the group_code as `item_code`, aggregated stock/demand/suggested
- Members are NOT returned (the store doesn't see them)

Recompute `recommended_qty` and `is_low_stock` from aggregated values using existing `_build_recommendation_contract` logic.

```
MUST_CONTAIN: "is_group_row"
```

### Task 4.4: Frozen Mango vertical slice test

Create one BEI Store Item Group: `GRP-FROZEN-MANGO` with members RM010-A (priority 1) and RM030 (priority 2). Hit the API and verify Araneta Gateway sees ONE "Frozen Mango" row with summed stock + summed demand.

```
MUST_CREATE: output/s163/vertical_slice_frozen_mango.json
```

---

## Phase 5: Order Submission with Group Codes

**Estimated units: 8**

### Task 5.1: Detect group codes in submit_order — MULTI-ROW EXPANSION

```
MUST_MODIFY: hrms/api/store.py
MUST_CONTAIN: "item_group_code"
MUST_CONTAIN: "group_order_seq"
```

In `submit_order()`, check each incoming item:
- If `item_code` matches an active `BEI Store Item Group` → it's a group order
- Compute proposed_resolution: walk members in priority order, allocate `qty_requested` against each member's source ATP until satisfied
- **Generate a fresh `group_order_seq` integer** (increment per grouped line in this order)
- **Create ONE BEI Store Order Item row per resolved (member SKU, source_warehouse) tuple**:
  ```
  for line in proposed_resolution:
      order.append("items", {
          "item_code": line.member_item,    # REAL SKU, never GRP-*
          "qty_requested": line.qty,
          "uom": member.stock_uom,
          "item_group_code": group.group_code,
          "group_order_seq": seq,
          "group_qty_requested_total": qty_requested_in_display_uom,
          "group_resolution_status": "Auto" if fully_resolved else "Pending",
      })
  ```
- For groups where ATP cannot fully satisfy the request, still create rows for whatever members have stock; mark the seq as `Pending` so SCM resolves the gap.

For non-group items, existing flow unchanged: ONE row, no group fields populated.

**Result:** A 5 KG Frozen Mango order auto-resolved to RM010-A becomes ONE BEI Store Order Item with `item_code=RM010-A, qty=5, item_group_code=GRP-FROZEN-MANGO, group_order_seq=1`. If split across two members, it becomes TWO rows sharing `group_order_seq=1`.

### Task 5.2: Validation

If a group order's qty_requested exceeds total available stock across all members, allow it (mark as Pending, SCM will deal with it). Don't reject the order at submit time — give SCM the chance to adjust.

### Task 5.3: Submit-side test

Submit a test order via L3 with one grouped item and one regular item. Verify the BEI Store Order Item record has the right fields populated.

---

## Phase 6: SCM Order Review Group Resolution UI

**Estimated units: 12**

### Task 6.1: Backend — `resolve_group_order_item` endpoint (MULTI-ROW + OPTIMISTIC LOCKING)

```
MUST_MODIFY: hrms/api/store.py
MUST_CONTAIN: "def resolve_group_order_item"
MUST_CONTAIN: "set_backend_observability_context"
MUST_CONTAIN: "expected_modified"
MUST_CONTAIN: "group_order_seq"
```

New `@frappe.whitelist()` endpoint with optimistic locking and multi-row updates:

```python
@frappe.whitelist()
def resolve_group_order_item(order_name: str, group_order_seq: int, resolution: list, expected_modified: str) -> dict:
    set_backend_observability_context(
        module="store_ordering",
        action="resolve_group_order_item",
        mutation_type="update",
    )
    # OPTIMISTIC LOCKING (audit fix #4): reject if order was modified by another user
    current_modified = frappe.db.get_value("BEI Store Order", order_name, "modified")
    if str(current_modified) != str(expected_modified):
        frappe.throw(_("Order was modified by another user. Please refresh."), exc=frappe.exceptions.ConflictError)

    order = frappe.get_doc("BEI Store Order", order_name)
    # Find all sibling rows by group_order_seq
    sibling_rows = [r for r in order.items if r.group_order_seq == group_order_seq]
    if not sibling_rows:
        frappe.throw(_("No grouped order line found for seq {0}").format(group_order_seq))

    group_code = sibling_rows[0].item_group_code
    qty_requested_total = flt(sibling_rows[0].group_qty_requested_total)

    # Validate qty_approved divergence (audit fix #7)
    qty_target = flt(sibling_rows[0].qty_approved or qty_requested_total)

    # Validate input
    total = sum(flt(line["qty"]) for line in resolution)
    if abs(total - qty_target) > 0.001:
        frappe.throw(_("Total {0} does not match required {1}").format(total, qty_target))
    for line in resolution:
        if flt(line["qty"]) < 0:
            frappe.throw(_("Negative qty not allowed for {0}").format(line["member_item"]))
        # Validate member is actually in the group
        # Validate source warehouse has stock (against current Bin.actual_qty — stock reservation check)

    # DELETE old sibling rows, CREATE new ones (multi-row swap)
    order.items = [r for r in order.items if r.group_order_seq != group_order_seq]
    for line in resolution:
        order.append("items", {
            "item_code": line["member_item"],
            "qty_requested": flt(line["qty"]),
            "qty_approved": flt(line["qty"]),  # match qty_target
            "uom": frappe.db.get_value("Item", line["member_item"], "stock_uom"),
            "item_group_code": group_code,
            "group_order_seq": group_order_seq,
            "group_qty_requested_total": qty_requested_total,
            "group_resolution_status": "Manual",
        })
    order.save(ignore_permissions=True)
    return {"order_item_seq": group_order_seq, "modified": str(order.modified)}
```

**Validation rules (machine-checked):**
1. `expected_modified` matches current — else 409 conflict
2. SUM of `resolution[].qty` equals `qty_approved or group_qty_requested_total`
3. Every `resolution[].member_item` is in the group's members table
4. Every `resolution[].qty >= 0`
5. Every `resolution[].source_warehouse` has at least `resolution[].qty` in `Bin.actual_qty` AT THIS MOMENT (stock reservation check; reject if depleted)

### Task 6.1b: Update Next.js proxy route — AUDIT FIX

```
MUST_MODIFY: bei-tasks/app/api/delivery-schedule/route.ts
MUST_CONTAIN: "resolve_group_order_item"
```

The frontend talks to `/api/delivery-schedule?action=...` (Next.js proxy), NOT directly to `hrms.api.store`. The proxy must be updated to:
1. Pass through the new group fields in the GET response shape
2. Add a POST action `resolve_group_order_item` that forwards to the Frappe endpoint with the user's session cookie

Verify the actual proxy file path during execution (it may be at `bei-tasks/app/api/scm/order-review/route.ts` or similar). Search for "get_orders_for_dispatch" to find the right file.

### Task 6.1c: Extend approve_order to invalidate stale group resolutions — AUDIT FIX

```
MUST_MODIFY: hrms/api/store.py
```

In `approve_order()` after `qty_approved` is set: for each grouped order item where `qty_approved != group_qty_requested_total`, set `group_resolution_status = "Pending"` and clear all but the first sibling row, forcing SCM to re-resolve. Without this, SCM can dispatch 5 KG against a 3 KG approval.

### Task 6.2: Backend — Extend `get_orders_for_dispatch`

```
MUST_MODIFY: hrms/api/store.py
```

The dispatch view must return the new fields (`item_group_code`, `is_group_order`, `group_resolution_status`, `resolution_lines`) plus a computed `group_members_with_stock` array showing each member's available stock at each source warehouse — so the modal can populate the picker without a second roundtrip.

### Task 6.3: Frontend — Override button on order line

```
MUST_MODIFY: bei-tasks/app/dashboard/scm/order-review/page.tsx
MUST_CONTAIN: "is_group_order"
```

When `is_group_order` is true, render:
- A "GROUP" badge next to the item name
- Display the current resolution as a small inline summary (e.g., "5 KG → RM010-A 3 KG @ 3MD, RM030 2 KG @ 3MD")
- An "Override" button that opens the modal

### Task 6.4: Frontend — GroupResolutionModal component

```
MUST_CREATE: bei-tasks/app/dashboard/scm/order-review/_components/GroupResolutionModal.tsx
MUST_CONTAIN: "qty_requested"
MUST_CONTAIN: "resolution_lines"
```

Modal with:
- Header: group display_name + qty_requested
- Table of members: item_code, source_warehouse, available_qty, pick_qty (input)
- Live total at the bottom: must equal qty_requested for Save to enable
- Save button → POST to `resolve_group_order_item` → close modal → refetch order list

### Task 6.5: Frontend — Default auto-resolution display

For groups with `group_resolution_status = "Auto"` (no SCM intervention needed), don't show the Override button by default. Add a "Show options" link that reveals it. Reduces visual noise for the common case.

### Task 6.6: SCM endpoint test

Create a grouped order, hit `resolve_group_order_item` with a split, verify the order item updates correctly.

```
MUST_CREATE: output/s163/scm_resolution_test.json
```

---

## Phase 7: Frontend Ordering Page (Group Display)

**Estimated units: 8**

### Task 7.1: Update OrderableItem type

```
MUST_MODIFY: bei-tasks/hooks/use-ordering.ts
MUST_CONTAIN: "is_group_row"
MUST_CONTAIN: "item_group_code"
```

Add: `is_group_row?: boolean`, `item_group_code?: string`, `member_count?: number`.

### Task 7.2: Group badge in OrderItemTable

```
MUST_MODIFY: bei-tasks/app/dashboard/store-ops/ordering/_components/OrderItemTable.tsx
MUST_CONTAIN: "is_group_row"
```

When `is_group_row`, render the row normally but:
- Show display_name as the item name
- Show display_uom (not stock_uom)
- Add a small "[group]" badge (subtle, gray)
- The item_code column shows the group_code (e.g., GRP-FROZEN-MANGO)

### Task 7.3: Group badge in OrderItemCard (mobile)

```
MUST_MODIFY: bei-tasks/app/dashboard/store-ops/ordering/_components/OrderItemCard.tsx
MUST_CONTAIN: "is_group_row"
```

Same treatment for the mobile card view: render `display_name`, `display_uom`, and a small `[group]` pill when `is_group_row` is true. Hide the raw `item_code` (do NOT display `GRP-FROZEN-MANGO` to stores).

### Task 7.4: Submit payload — verify group_code is sent

```
MUST_MODIFY: bei-tasks/app/dashboard/store-ops/ordering/_components/StoreOrderingPage.tsx
MUST_CONTAIN: "is_group_row"
```

The submit handler at `StoreOrderingPage.tsx` already sends `item_code` from the OrderableItem. When `is_group_row=true`, the `item_code` IS the group_code (e.g., `GRP-FROZEN-MANGO`). The backend submit_order endpoint detects this and expands into multi-row BEI Store Order Item records.

**MUST_CONTAIN check** verifies the submit handler at least references `is_group_row` (e.g., to log it or branch on it). If the agent decides truly no change is needed, drop Task 7.4 from the Critical Files list — but the gate must be unambiguous.

---

## Phase 8: MR Creation + Savepoints + Pick List/Receiving Verification

**Estimated units: 10**

### Task 8.1: Extend `_create_mr_for_store_order` — MULTI-ROW MODEL MAKES THIS TRIVIAL

```
MUST_MODIFY: hrms/api/store.py
MUST_CONTAIN: "frappe.db.savepoint"
MUST_CONTAIN: "item_group_code"
```

**Because of the multi-row model:** the existing MR creation loop ALREADY creates one MR Item row per BEI Store Order Item. There's no JSON expansion needed. Just propagate the audit fields:

In the MR item creation loop (lines ~3267-3283):
- For each BEI Store Order Item (whether grouped or not), create one MR Item row with `item_code = order_item.item_code` (real SKU in both cases)
- For grouped order items (where `item_group_code` is set), also set custom fields on the MR Item: `custom_source_group_code = order_item.item_group_code`, `custom_source_order_item = order_item.name`

**SAVEPOINT (audit fix DM-2):** Wrap the body of `_create_mr_for_store_order` in `frappe.db.savepoint("create_mr_for_store_order")` and `release_savepoint`/`rollback_to_savepoint`. The function mutates the order, creates MR, inserts MR items, submits — all of which must roll back together.

**REMOVE BLANKET TRY/EXCEPT (audit fix):** The existing function at `store.py:3212-3297` has `try: ... except Exception as e: frappe.log_error(...); return None` which hides the real error. Replace with `frappe.log_error(...); raise` so callers see `ItemNotFound: ...` etc instead of generic "Failed to create".

**HARD BLOCKER:** If any BEI Store Order Item has `group_resolution_status = "Pending"` at MR creation time, throw a clear error listing offending rows. The order should not move to MR until SCM has resolved every grouped line.

### Task 8.2: Custom fields on Material Request Item

Use Frappe Custom Fields (loaded via fixtures) to add `custom_source_group_code` and `custom_source_order_item` to Material Request Item. These are audit-only fields, not used in any business logic.

```
MUST_MODIFY: hrms/fixtures/custom_field.json
MUST_CONTAIN: "custom_source_group_code"
```

### Task 8.3: Pick list and Receiving page — VERIFY no changes needed

**The multi-row model makes pick list and receiving page work unchanged.** The pick list at `picking.py:60-96` reads BEI Store Order Item rows directly via `frappe.get_all` with `fields=["parent","item_code","item_name","qty_requested","uom"]`. Since `item_code` is now a real SKU on every row (never `GRP-*`), pick list generation works without modification.

Same applies to `get_pending_deliveries_with_manifest` at `store.py:3349-3364` (store receiving page).

**MUST_CONTAIN check:** Run `grep -c "GRP-" hrms/api/picking.py` — should return 0. If anything in picking.py references `GRP-*`, the multi-row model wasn't followed correctly.

```
MUST_NOT_CONTAIN_GREP: grep -r "GRP-" hrms/api/picking.py
MUST_NOT_CONTAIN_GREP: grep -r "GRP-" hrms/api/store.py | grep -v "def resolve_group_order_item\|item_group_code"
```

L3 must verify: pick list contains zero rows where `item_code LIKE 'GRP-%'`. Stock Entry posts succeed.

### Task 8.4: Stock reservation race — MR-time validation (AUDIT FIX)

Add to `_create_mr_for_store_order`: before creating each MR row, validate that `Bin.actual_qty(item_code, source_warehouse) >= qty`. If a parallel order has consumed the stock since SCM resolved, REJECT with "Stock decreased between resolution and dispatch — SCM must re-resolve order line {seq}". Set the affected sibling rows back to `group_resolution_status = "Pending"`.

This is a minimal fix for the race condition. Full stock reservation (BEI Stock Reservation ledger) is deferred to a future sprint.

### Task 8.2: Custom fields on Material Request Item

Use Frappe Custom Fields (loaded via fixtures) to add `custom_source_group_code` and `custom_source_order_item` to Material Request Item. These are audit-only fields, not used in any business logic.

```
MUST_MODIFY: hrms/fixtures/custom_field.json
MUST_CONTAIN: "custom_source_group_code"
```

### Task 8.3: Pick list and Stock Entry validation

Pick list (`picking.py:44+`) reads MR items by `item_code`. Since MR items now contain real SKUs (not group codes), the existing pick list code works unchanged. Verify by submitting a test grouped order through the full pipeline.

---

## Phase 9: Sentry Observability

**Estimated units: 3**

Every new `@frappe.whitelist()` endpoint must call `set_backend_observability_context()`:

```
MUST_CONTAIN: "set_backend_observability_context"
```

Endpoints to instrument:
- `resolve_group_order_item` (module="store_ordering", action="resolve_group_order_item", mutation_type="update")

Existing endpoints (`submit_order`, `get_orders_for_dispatch`, `_create_mr_for_store_order`) are already instrumented per S097 closeout gate; verify they still are after edits.

---

## Phase 10: L3 Testing (Vertical Slice + 9 Groups) — HARD HANDOFF

**Estimated units: 6**

Run L3 in a fresh agent session per S099 handoff rule. Plan **MANDATES** a separate session because S163 has 82 work units total, which crosses the 40-tool-call threshold.

### Task 10.0: Generate L3 handoff artifact (AUDIT FIX)

Before stopping for the L3 session, the build agent MUST produce:

```
MUST_CREATE: output/s163/HANDOFF_FOR_L3.md
```

This file contains:
- Branch name and current SHA
- Deployed image tag (after the user merges and deploys)
- PR numbers (hrms + bei-tasks)
- All 8 L3 scenarios with expected inputs
- Test account credentials reference (`memory/testing-accounts.md`)
- Frozen Mango group setup confirmation: `GRP-FROZEN-MANGO` exists with members RM010-A and RM030
- Verification script results: `output/s163/verify_phase_*.json`
- A clear "STOP — DO NOT CONTINUE TO L3 IN THIS SESSION" instruction

**HARD STOP:** After the build agent creates this file, it must STOP and tell the user the build is complete and ready for L3. Do NOT begin L3 in the same session — context exhaustion at the tail of an 80+ unit session is the #1 cause of L3 corruption per S154.

### Task 10.1: Run L3 in a fresh session

In a NEW Claude Code session (after the user starts it), run `/l3-v2-bei-erp` and execute the 8 scenarios from the L3 Workflow Scenarios table.

Evidence files required at `output/l3/s163/`:
- `form_submissions.json` — every form/button click with payload + response
- `api_mutations.json` — every POST/PUT/PATCH with payload + status
- `state_verification.json` — before/after state checks per scenario

(See L3 Workflow Scenarios section below.)

---

## Phase 11: Closeout

**Estimated units: 3**

### Task 11.1: Delete CSV files

```
MUST_DELETE: hrms/fixtures/store_ordering/store_order_component_recipes.csv
MUST_DELETE: hrms/fixtures/store_ordering/store_order_product_policies.csv
```

After Phase 10 evidence proves the DocType-backed pipeline works, delete the CSVs in the same commit. This is the cutover.

### Task 11.2: Update plan + registry

- Set `status: COMPLETED` and `completed_date` in this plan's YAML metadata
- Update `docs/plans/SPRINT_REGISTRY.md` S163 row to COMPLETED with PR numbers
- `git add -f docs/plans/2026-04-06-sprint-163-store-ordering-doctypes-product-grouping.md docs/plans/SPRINT_REGISTRY.md`
- Commit and push

---

## Sentry Observability

All new and modified `@frappe.whitelist()` endpoints in `hrms/api/store.py` MUST call `set_backend_observability_context(module="store_ordering", action="<function_name>", mutation_type="<type>")`.

Sentry projects: backend → `bei-hrms` (python), frontend → `bei-tasks` (javascript-nextjs). Org: `bebang-enterprise-inc`.

---

## Requirements Regression Checklist

Before writing ANY code, the executing agent must verify each item against its planned implementation. Each item must answer YES or STOP.

**Existing checks:**
- [ ] Are 5 new DocType JSONs being created (Recipe + Recipe Item, Policy, Item Group + Group Member)? *(Phase 1)*
- [ ] Are the 4 new fields on `BEI Store Order Item` all optional (no `reqd: 1`)? *(Phase 1.4 — backwards compat HARD BLOCKER #1)*
- [ ] Does the migration script read the LATEST CSV (which includes PR #460 add-on recipes)? *(Phase 2 — depends on PR #460 being merged first)*
- [ ] Is the migration script idempotent (re-running it doesn't duplicate records)? *(Phase 2.1)*
- [ ] Does `load_component_recipe_catalog()` keep its original signature and return type? *(Phase 3.1 — caller compatibility)*
- [ ] Does `get_orderable_items` return ONE virtual row per group (members hidden)? *(Phase 4)*
- [ ] Are aggregated values computed per group (stock, demand, suggested)? *(Phase 4.2)*
- [ ] Do non-grouped items pass through `get_orderable_items` unchanged? *(Phase 4.3)*
- [ ] Does `submit_order` accept BOTH old format (real SKU) and new format (group code)? *(Phase 5.1 — backwards compat)*
- [ ] Does the auto-resolution allocate by member priority then ATP? *(Phase 5.1)*
- [ ] Does the modal display ALL members with their stock at each source warehouse? *(Phase 6.4)*
- [ ] Does MR Item record `custom_source_group_code` for audit? *(Phase 8.2)*
- [ ] Are the CSV files deleted only AFTER L3 evidence proves the DocType-backed pipeline works? *(Phase 11.1)*
- [ ] Does every new `@frappe.whitelist()` endpoint call `set_backend_observability_context()`? *(Phase 9)*
- [ ] Does the closeout phase update both the plan YAML and `SPRINT_REGISTRY.md` and push them? *(Phase 11.2)*

**AUDIT-FIX checks (added 2026-04-06):**
- [ ] Is `item_code` on BEI Store Order Item ALWAYS a real SKU (never `GRP-*`)? *(HARD BLOCKER #2 — pick list, receiving, Stock Entry depend on this)*
- [ ] Does the multi-row model store sibling rows with shared `group_order_seq`? *(Phase 5.1 — replaces JSON resolution_lines)*
- [ ] Does each new parent DocType JSON include `"autoname": "field:..."`? *(Phase 1 — without this, idempotency check fails)*
- [ ] Does the migration script wrap each recipe insertion in `frappe.db.savepoint()`? *(Phase 2.1 — DM-2)*
- [ ] Does `_create_mr_for_store_order` use `frappe.db.savepoint()` and NOT swallow errors? *(Phase 8.1 — DM-2)*
- [ ] Does `resolve_group_order_item` accept and validate `expected_modified` for optimistic locking? *(Phase 6.1 — concurrency)*
- [ ] Does `resolve_group_order_item` validate against `qty_approved or group_qty_requested_total`, not just `qty_requested`? *(Phase 6.1 — qty_approved divergence)*
- [ ] Does `approve_order` invalidate group resolutions when `qty_approved != qty_requested`? *(Phase 6.1c — added by audit)*
- [ ] Does the Next.js proxy at `bei-tasks/app/api/...` forward `resolve_group_order_item`? *(Phase 6.1b — added by audit)*
- [ ] Does `_create_mr_for_store_order` validate stock at MR-creation time (race protection)? *(Phase 8.4 — added by audit)*
- [ ] Does the modal Save handler call `mutate()` from parent SWR to refresh order list? *(Phase 6.4 — CTA wiring)*
- [ ] Does the modal block negative qty, over-allocation per source, and zero-stock allocation? *(Phase 6.4 — validation rules)*
- [ ] Is `pick_list.py` UNCHANGED (no GRP-* references) because the multi-row model makes expansion unnecessary? *(Phase 8.3 — verification)*
- [ ] Is the CSV fallback DROPPED in Phase 3 (loaders raise RuntimeError without Frappe context)? *(Phase 3.1 — audit decision Option A)*
- [ ] Is the verification script saved to `scripts/s163_verify_phases.sh` (not just inside the markdown)? *(Zero-skip — Windows compat)*
- [ ] Does Phase 10 produce `output/s163/HANDOFF_FOR_L3.md` and STOP before running L3? *(Phase 10 — context exhaustion mitigation)*
- [ ] Does Phase 7 Tasks 7.3, 7.4 include MUST_CONTAIN gates for `is_group_row`? *(Cold-start — verifiability)*
- [ ] Does the vertical slice JSON contain `"GRP-FROZEN-MANGO"` so `grep -q` proves it? *(Phase 4.4 — schema check)*

---

## Zero-Skip Enforcement

Every task MUST be implemented. No exceptions. If a task cannot be completed, the agent STOPS and asks the user.

**Forbidden behaviors:**
- Skipping a task silently
- Marking partial work as "done"
- Replacing a task with a simpler version without user approval
- Saying "deferred to next sprint"
- Combining tasks and dropping features
- Implementing happy path only, skipping edge cases (especially: what happens when a group has zero stock anywhere, or when SCM tries to save a split with mismatched total)

### Phase verification script — SAVED TO scripts/s163_verify_phases.sh (AUDIT FIX)

```
MUST_CREATE: scripts/s163_verify_phases.sh
```

After each phase, the agent runs `bash scripts/s163_verify_phases.sh <phase_number>` from the BEI-ERP working directory and writes the output to `output/s163/verify_phase_<N>.json`. This script must be a real file (not just markdown), saved in Phase 0 as a `MUST_CREATE` artifact. Agents using PowerShell on Windows invoke it via Git Bash: `& "C:\Program Files\Git\bin\bash.exe" scripts/s163_verify_phases.sh 1`.

```bash
#!/bin/bash
echo "=== Phase 1: DocTypes ==="
ls hrms/hr/doctype/bei_store_order_component_recipe/*.json
ls hrms/hr/doctype/bei_store_order_product_policy/*.json
ls hrms/hr/doctype/bei_store_item_group/*.json
grep -c "is_group_order" hrms/hr/doctype/bei_store_order_item/bei_store_order_item.json

echo "=== Phase 2: Migration ==="
test -f scripts/s163_migrate_csv_to_doctypes.py
test -f output/s163/migration_evidence.json

echo "=== Phase 3: Pipeline ==="
grep -c "BEI Store Order Component Recipe" hrms/utils/store_order_demand_snapshot.py
! grep -q "open(COMPONENT_RECIPE_PATH" hrms/utils/store_order_demand_snapshot.py

echo "=== Phase 4: Group aggregation ==="
grep -c "BEI Store Item Group" hrms/api/store.py
grep -c "is_group_row" hrms/api/store.py

echo "=== Phase 5: Submit order ==="
grep -c "is_group_order" hrms/api/store.py
grep -c "group_resolution_status" hrms/api/store.py

echo "=== Phase 6: SCM resolution ==="
grep -c "def resolve_group_order_item" hrms/api/store.py
test -f ../bei-tasks/app/dashboard/scm/order-review/_components/GroupResolutionModal.tsx

echo "=== Phase 7: Frontend ordering ==="
grep -c "is_group_row" ../bei-tasks/hooks/use-ordering.ts

echo "=== Phase 8: MR expansion ==="
grep -c "resolution_lines" hrms/api/store.py
grep -c "custom_source_group_code" hrms/fixtures/custom_field.json

echo "=== Phase 11: Cleanup ==="
! test -f hrms/fixtures/store_ordering/store_order_component_recipes.csv
! test -f hrms/fixtures/store_ordering/store_order_product_policies.csv

echo "=== AUDIT-FIX: No GRP-* leaks into pick list or downstream code ==="
! grep -q "GRP-" hrms/api/picking.py
# Allow GRP- only in resolve_group_order_item and item_group_code references in store.py
GRP_LEAKS=$(grep -n "GRP-" hrms/api/store.py | grep -v "def resolve_group_order_item\|item_group_code\|# AUDIT" | wc -l)
test "$GRP_LEAKS" -eq 0

echo "=== AUDIT-FIX: autoname declared on all 3 new parent DocTypes ==="
grep -q "field:recipe_key" hrms/hr/doctype/bei_store_order_component_recipe/bei_store_order_component_recipe.json
grep -q "field:group_code" hrms/hr/doctype/bei_store_item_group/bei_store_item_group.json

echo "=== AUDIT-FIX: optimistic locking parameter present ==="
grep -q "expected_modified" hrms/api/store.py

echo "=== AUDIT-FIX: savepoint in _create_mr_for_store_order ==="
grep -A 30 "def _create_mr_for_store_order" hrms/api/store.py | grep -q "savepoint"

echo "=== AUDIT-FIX: proxy route updated for resolve_group_order_item ==="
grep -rq "resolve_group_order_item" ../bei-tasks/app/api/

echo "=== AUDIT-FIX: vertical slice JSON has real evidence ==="
grep -q "GRP-FROZEN-MANGO" output/s163/vertical_slice_frozen_mango.json
```

**FAIL blocks progress.** If any check returns 0 or the file/condition is wrong, the phase is incomplete.

---

## Phase Budget Contract

| Phase | Estimated Units | Within Budget? | Notes |
|------|----------------|----------------|---|
| Phase 0 (Reservation + Audit) | 3 | Yes | |
| Phase 1 (DocTypes + autoname) | 9 | Yes | +1 for autoname declarations |
| Phase 2 (Migration script + savepoints) | 6 | Yes | +1 for per-recipe savepoints |
| Phase 3 (Pipeline switch — drop CSV fallback) | 6 | Yes | |
| Phase 4 (Group aggregation) | 10 | Yes | |
| Phase 5 (Submit order — multi-row expansion) | 8 | Yes | Multi-row instead of JSON, similar effort |
| Phase 6 (SCM UI + proxy + approve_order + locking) | 16 | **Above 12-unit ceiling — split required** | +4 for proxy update, approve_order invalidation, optimistic locking |
| Phase 7 (Frontend ordering + tighter gates) | 8 | Yes | |
| Phase 8 (MR + savepoints + stock race + pick list verify) | 12 | At ceiling | +2 for savepoint, stock race check, pick list grep verification |
| Phase 9 (Sentry) | 3 | Yes | |
| Phase 10 (L3 + handoff artifact) | 7 | Yes | +1 for HANDOFF_FOR_L3.md |
| Phase 11 (Closeout) | 3 | Yes | |
| **Total** | **91** | **Above 80 ceiling — see mitigation** | +9 from audit fixes |

**Phase 6 split (audit fix S029):**
- Phase 6A: backend (resolve endpoint, optimistic locking, proxy, approve_order extension) — 8 units
- Phase 6B: frontend (modal, override button, validation) — 8 units

**Scope size warning:** Original plan was 82 units; audit-driven fixes added 9 units (now 91). The user explicitly requested both DocType migration AND Product Grouping in one sprint because they share the get_orderable_items pipeline (touching it twice would double the L3 burden). The recommended split (S163 = DocType, S163 = Grouping) is rejected by the user.

**Mitigation:**
1. Phase 6 is split into 6A (backend) and 6B (frontend), each at 8 units, well under the 12-unit per-phase ceiling.
2. L3 MUST run in a separate fresh agent session per S099 handoff rule. Phase 10.0 produces a hard handoff artifact and the build agent STOPS.
3. Phases 1-3 (DocType migration, ~21 units) can be the first PR, Phases 4-11 (Product Grouping, ~70 units) can be the second PR. Both go under the same S163 branch but the agent can checkpoint at the end of Phase 3 with a Frappe `bench migrate` and a separate "DocType migration complete, no behavior change" commit.

---

## Autonomous Execution Contract

- **completion_condition:**
  - All 11 phases implemented and verified
  - Phase verification script returns all green
  - PRs created for hrms (DocTypes + backend) and bei-tasks (frontend)
  - L3 evidence files at `output/l3/s163/` cover all 8 scenarios below
  - CSV files deleted from `hrms/fixtures/store_ordering/`
  - Plan YAML status updated to COMPLETED with `completed_date` and `execution_summary`
  - `docs/plans/SPRINT_REGISTRY.md` row updated to COMPLETED with PR numbers
  - Both files committed and pushed to production

- **stop_only_for:**
  - PR #460 not yet merged (migration depends on the add-on recipes being in CSV)
  - Frappe `bench migrate` fails on the new DocTypes (DocType JSON syntax error — fix and retry)
  - SCM rejects the UX of the resolution modal (requires user feedback)
  - Destructive action requiring user approval

- **continue_without_pause_through:** code → test → pr_creation → closeout

- **blocker_policy:**
  - Programmatic → fix and continue
  - Migration data mismatch → halt, capture diff, present to user
  - Frappe DocType validation error → research Frappe docs, fix JSON, retry
  - L3 failure → fix bug, redeploy, rerun L3 from invalidated level

- **signoff_authority:** single-owner (Sam)

- **canonical_closeout_artifacts:**
  - `output/s163/pre_migration_audit.json`
  - `output/s163/migration_evidence.json`
  - `output/s163/pipeline_parity_check.json`
  - `output/s163/vertical_slice_frozen_mango.json`
  - `output/s163/scm_resolution_test.json`
  - `output/s163/verify_phase_<N>.json` × 11 phases
  - `output/l3/s163/form_submissions.json`
  - `output/l3/s163/api_mutations.json`
  - `output/l3/s163/state_verification.json`
  - `docs/plans/2026-04-06-sprint-163-store-ordering-doctypes-product-grouping.md` (status → COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (row updated)

---

## Signoff Model

- **mode:** single-owner
- **approver_of_record:** Sam (CEO)
- **note:** No department approval required.

---

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branch:** `git fetch origin production && git checkout -b s163-store-ordering-doctypes-product-grouping origin/production`. NEVER write code on production.
3. Verify PR #460 is merged before starting Phase 2 (migration depends on the add-on recipes).
4. Read `docs/plans/SPRINT_REGISTRY.md` for cross-sprint context.
5. Read `hrms/utils/store_order_demand_snapshot.py` lines 17-21, 342-395 (CSV loaders).
6. Read `hrms/api/store.py` lines 2197+ (`get_orderable_items`), 2708+ (`submit_order`), 3020+ (`approve_order`), 3212+ (`_create_mr_for_store_order`), 6643+ (`get_orders_for_dispatch`).
7. Read `hrms/hr/doctype/bei_store_order/bei_store_order.json` and `bei_store_order_item.json` as the parent+child template.
8. Read `bei-tasks/app/dashboard/scm/order-review/page.tsx` for the existing SCM dispatch UI.
9. Implement phases 0-11 in order. The Frozen Mango vertical slice (Phase 4.4) must work end-to-end before adding the other 8 groups.
10. Run L3 in a fresh agent session — do NOT execute L3 in the same session as the build.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

---

## Execution Workflow

- Test Python changes: `/local-frappe`
- Deploy changes: `/deploy-frappe`
- Full workflow: `/agent-kickoff`
- Frappe SSM scripts: `/frappe-bulk-edits`
- E2E testing: `/l3-v2-bei-erp` (run in a separate fresh session)

> **Note:** Deployment is user-mediated. Builder sessions create PRs; Sam handles merge, deploy trigger, and L1 smoke.

---

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| test.storesup@bebang.ph | Open ordering page for Araneta Gateway | "Frozen Mango" appears as ONE row (not RM010-A + RM030 separately). Stock = 12.5 KG (sum). Demand > 0. | Phase 4 group aggregation broken |
| test.storesup@bebang.ph | Search "Mango" in ordering | One result: "Frozen Mango (group)" | Phase 7 frontend display broken |
| test.storesup@bebang.ph | Enter qty=5 KG for Frozen Mango → submit order | Order submitted. Backend BEI Store Order Item has `is_group_order=1`, `item_group_code="GRP-FROZEN-MANGO"`, `resolution_lines` JSON populated | Phase 5 submit_order group detection broken |
| test.area@bebang.ph | Open order approvals | The grouped order shows "Frozen Mango — 5 KG" with no SKU detail. Approve. | Group display in approval flow broken |
| test.scm@bebang.ph | Open SCM order review | Approved order shows "[GROUP] Frozen Mango — 5 KG → Auto: RM010-A 5 KG @ 3MD" | Phase 6.3 group badge broken |
| test.scm@bebang.ph | Click Override on Frozen Mango row | Modal opens with members RM010-A and RM030, each at 3MD and Pinnacle, with stock counts | Phase 6.4 modal broken |
| test.scm@bebang.ph | Enter 3 KG for RM010-A @ 3MD + 2 KG for RM030 @ 3MD → Save | Modal closes, order line shows "Manual: RM010-A 3 KG, RM030 2 KG". Backend `resolution_lines` = JSON with 2 entries. | Phase 6.1 resolve endpoint broken |
| test.scm@bebang.ph | Mark order as Ready for Dispatch → triggers MR creation | Material Request created with TWO items: RM010-A 3 KG and RM030 2 KG. NO row with `GRP-FROZEN-MANGO`. | Phase 8.1 MR expansion broken |

### L3 Evidence Files (Required Before Closeout)

```
output/l3/s163/form_submissions.json
output/l3/s163/api_mutations.json
output/l3/s163/state_verification.json
```

**Recommendation:** Run L3 in a fresh agent session because the build session will exceed 40 tool calls.

---

## Closeout Phase (Mandatory)

After all phases are implemented and L3 evidence is collected:

1. Update plan YAML: `status: COMPLETED`, fill `completed_date` and `execution_summary`
2. Update `docs/plans/SPRINT_REGISTRY.md` S163 row with COMPLETED status and PR numbers
3. Delete the two CSV files: `hrms/fixtures/store_ordering/store_order_component_recipes.csv` and `store_order_product_policies.csv`
4. Commit and push everything: `git add -f docs/plans/2026-04-06-sprint-163-*.md docs/plans/SPRINT_REGISTRY.md && git commit -m "docs: S163 closeout — update plan and registry, remove CSV fixtures"`

---

## Verification Summary

1. **Phase 1-3 (DocType migration):** All 12 component recipes (including 13 add-on recipes from PR #460) and 31 product policies appear as DocType records in Frappe Desk. The demand pipeline produces identical snapshots before and after the cutover (parity check).
2. **Phase 4 (Group aggregation):** `get_orderable_items` for Araneta Gateway returns "Frozen Mango" as one row with summed stock (12.5 KG) and summed demand. Member SKUs (RM010-A, RM030) are NOT in the response.
3. **Phase 5 (Submit order):** Submitting a group order creates a BEI Store Order Item with the group fields populated and a valid auto-resolution.
4. **Phase 6 (SCM resolution):** SCM can override the resolution via the modal, splitting across SKUs and source warehouses. The resolution persists.
5. **Phase 8 (MR expansion):** Approving a grouped order creates a Material Request with multiple item rows (real SKUs), one per resolution line.
6. **Phase 11 (Cleanup):** Both CSV files are deleted. The pipeline still works because it reads from DocTypes.

**End-to-end test:** Submit a grouped order from a test store → approve → resolve via SCM → trigger MR → verify pick list contains real SKUs → confirm stock entry posts correctly.
