# Requirements Regression Check — S163

Each item: YES (matches plan) or STOP (resolve before code).

## Existing checks
- [YES] 5 new DocType JSONs (Recipe parent+child, Policy, Item Group parent+child) — Phase 1
- [YES] 4 new fields on BEI Store Order Item ALL optional (no reqd:1) — Phase 1.4 / HARD BLOCKER #1
- [YES] Migration script reads CSV with PR #460 add-on recipes (verified: 16 ADDON- lines present, PR #460 merged at 2026-04-06T08:21:15Z)
- [YES] Migration script idempotent via frappe.db.exists + per-recipe savepoints
- [YES] load_component_recipe_catalog() keeps signature/return type
- [YES] get_orderable_items returns ONE virtual row per group, members hidden
- [YES] Aggregated stock+demand+suggested per group
- [YES] Non-grouped items pass through unchanged
- [YES] submit_order accepts BOTH old format (real SKU) AND new (group_code)
- [YES] Auto-resolution by member priority then ATP
- [YES] Modal displays all members with stock at each source warehouse
- [YES] MR Item records custom_source_group_code for audit
- [N/A_THIS_SESSION] CSV deletion deferred to post-L3 (plan Phase 11.1 explicit)
- [YES] All new whitelist endpoints call set_backend_observability_context()
- [YES] Closeout updates plan YAML + SPRINT_REGISTRY.md and pushes

## AUDIT-FIX checks
- [YES] item_code on BEI Store Order Item ALWAYS real SKU, never GRP-* — HARD BLOCKER #2
- [YES] Multi-row model: sibling rows share group_order_seq
- [YES] Each new parent DocType has autoname:field:...
- [YES] Migration script wraps each recipe in frappe.db.savepoint()
- [YES] _create_mr_for_store_order uses savepoint() and does NOT swallow errors
- [YES] resolve_group_order_item validates expected_modified (optimistic locking)
- [YES] resolve validates against qty_approved or group_qty_requested_total
- [YES] approve_order invalidates group resolutions when qty_approved differs
- [YES] Next.js proxy route forwards resolve_group_order_item
- [YES] _create_mr_for_store_order validates Bin.actual_qty at MR-creation (race protection)
- [YES] Modal Save handler calls mutate() to refresh order list
- [YES] Modal blocks negative qty, over-allocation, zero-stock allocation
- [YES] picking.py UNCHANGED — multi-row model removes need
- [YES] CSV fallback DROPPED in Phase 3 — loaders raise RuntimeError
- [YES] Verification script saved to scripts/s163_verify_phases.sh
- [YES] Phase 10 produces HANDOFF_FOR_L3.md and STOPS
- [YES] Phase 7 Tasks 7.3, 7.4 include MUST_CONTAIN gates for is_group_row
- [YES] Vertical slice JSON contains GRP-FROZEN-MANGO (deferred to L3 evidence session)

## HARD BLOCKERS check
1. Backwards compat: 4 new fields all optional → YES, none reqd:1
2. item_code never GRP-* → YES, multi-row model puts real SKU in item_code, group code in item_group_code
3. Phase 8.1: any group_resolution_status==Pending blocks MR creation → YES, will throw

ALL: GREEN. Proceed with code.
