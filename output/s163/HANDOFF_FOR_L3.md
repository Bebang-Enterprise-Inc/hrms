# S163 — L3 HANDOFF

**STOP — DO NOT CONTINUE TO L3 IN THIS SESSION.**

This sprint was built in a single monolithic session (Phases 0–9). Per the S099 handoff rule, L3 acceptance testing MUST run in a fresh Claude Code session to avoid corrupt-success drift.

---

## Build state

| Field | Value |
|---|---|
| Sprint | S163 |
| Plan | `docs/plans/2026-04-06-sprint-163-store-ordering-doctypes-product-grouping.md` |
| hrms branch | `s163-store-ordering-doctypes-product-grouping` |
| hrms base SHA | `76cdf2abd77a5c6691965f59e83a4d322acb02f4` |
| bei-tasks branch | `s163-store-ordering-product-grouping` |
| bei-tasks base SHA | `1d79eb5ededab2e9a4d7b032e8e792aec2a0b250` |
| Verification gate | `bash scripts/s163_verify_phases.sh all` — ALL GREEN |
| PRs | _to be filled in by builder before stop_ |

## What was built (Phases 0–9)

1. **Phase 1: 5 new DocTypes**
   - `BEI Store Order Component Recipe` (parent + child item)
   - `BEI Store Order Product Policy`
   - `BEI Store Item Group` (parent + child member)
   - `BEI Store Order Item` extended with `item_group_code`, `group_order_seq`, `group_resolution_status`, `group_qty_requested_total` (all optional — backwards compat)
   - All parent doctypes use `autoname: field:...` (audit fix for idempotency)
2. **Phase 2: Migration script** `scripts/s163_migrate_csv_to_doctypes.py` with per-recipe savepoints, idempotent.
3. **Phase 3: Pipeline switch** in `hrms/utils/store_order_demand_snapshot.py` — `load_component_recipe_catalog` and `load_product_policy_catalog` read DocTypes; CSV fallback dropped (raises RuntimeError without Frappe context).
4. **Phase 4: Group aggregation** in `get_orderable_items` — `_load_store_item_group_index` + `_aggregate_store_item_groups` produce ONE virtual `is_group_row=1` row per group with summed stock + demand.
5. **Phase 5: Multi-row submit** in `submit_order` — group_code → walk members by priority → one BEI Store Order Item row per (member SKU, source warehouse) with shared `group_order_seq`. `item_code` is ALWAYS a real SKU.
6. **Phase 6A: Backend** — new `resolve_group_order_item` whitelist endpoint with optimistic locking via `expected_modified`, member validation, stock reservation check, multi-row swap. `approve_order` invalidates group resolution when qty_approved diverges from group total. `get_orders_for_dispatch` returns group fields + `group_members_with_stock` per-warehouse stock cache.
7. **Phase 6B: Frontend** — new `GroupResolutionModal.tsx` with member-warehouse picker, total validation, save → POST. `order-review/page.tsx` collapses sibling rows back into one display line per group_order_seq, renders GROUP badge + Override button. Proxy `delivery-schedule/route.ts` forwards `resolve_group_order_item`.
8. **Phase 7: Ordering page** — `OrderableItem` interface gains `is_group_row`, `item_group_code`, `member_count`, `member_item_codes`. `OrderItemTable.tsx` and `OrderItemCard.tsx` render `[group]` badge + hide raw GRP- code. `StoreOrderingPage.tsx` submit handler comment confirms group_code passes through.
9. **Phase 8: MR creation** — `_create_mr_for_store_order` wrapped in `savepoint("create_mr_for_store_order")`. HARD BLOCKER: any sibling row with `group_resolution_status=Pending` blocks MR creation. Stock race check: `Bin.actual_qty >= qty` per row at MR time; failure flips siblings back to Pending and throws. Errors NO LONGER swallowed — re-raised for caller visibility. New MR Item custom fields `custom_source_group_code` + `custom_source_order_item` propagated for audit.
10. **Phase 9: Sentry** — new `resolve_group_order_item` calls `set_backend_observability_context(module="store_ordering", action="resolve_group_order_item", mutation_type="update")`.

## What was NOT built (deferred to L3 session)

1. **Migration execution.** `scripts/s163_migrate_csv_to_doctypes.py` is ready but has not been run via SSM yet. Run it AFTER the user merges + deploys the hrms PR.
2. **Frozen Mango vertical slice DocType record.** No `BEI Store Item Group` records exist yet. Create `GRP-FROZEN-MANGO` with members RM010-A (priority 1) and RM030 (priority 2) BEFORE running L3 scenarios.
3. **CSV deletion (Phase 11.1).** Per the plan: "After Phase 10 evidence proves the DocType-backed pipeline works, delete the CSVs in the same commit." This is the post-L3 cleanup commit.
4. **Plan status COMPLETED + registry COMPLETED.** Both are currently `PR_CREATED`. Move to COMPLETED only after L3 evidence + CSV cleanup land.

## Pre-L3 setup (run BEFORE L3 scenarios)

1. User merges hrms PR (will be filled in below) and triggers deploy.
2. SSM: run migration script — `python scripts/s163_migrate_csv_to_doctypes.py` against `hq.bebang.ph`. Verify `output/s163/migration_evidence.json` shows 25 recipes created, 29 policies created, 0 errors.
3. SSM: create `GRP-FROZEN-MANGO` BEI Store Item Group with members RM010-A (priority 1, conversion_to_display=1.0) and RM030 (priority 2, conversion_to_display=1.0), display_uom=KG, delivery_lane=Frozen.
4. User merges bei-tasks PR (will be filled in below) and Vercel auto-deploys.
5. Verify the ordering page for Araneta Gateway shows ONE "Frozen Mango" row.

## L3 scenarios (8 total — from plan section "L3 Workflow Scenarios")

| # | User | Action | Expected | Failure means |
|---|------|--------|----------|---------------|
| 1 | test.storesup@bebang.ph | Open ordering page for Araneta Gateway | "Frozen Mango" appears as ONE row, stock = 12.5 KG (sum), demand > 0 | Phase 4 group aggregation broken |
| 2 | test.storesup@bebang.ph | Search "Mango" in ordering | One result: "Frozen Mango (group)" | Phase 7 frontend display broken |
| 3 | test.storesup@bebang.ph | Enter qty=5 KG → submit | BEI Store Order Item has `is_group_order=1`, `item_group_code=GRP-FROZEN-MANGO` | Phase 5 broken |
| 4 | test.area@bebang.ph | Open order approvals | Grouped order shows "Frozen Mango — 5 KG" with no SKU detail. Approve. | approval display broken |
| 5 | test.scm@bebang.ph | Open SCM order review | Approved order shows `[GROUP] Frozen Mango — 5 KG → Auto: RM010-A 5 KG @ 3MD` | Phase 6.3 broken |
| 6 | test.scm@bebang.ph | Click Override | Modal opens with members RM010-A and RM030, each with stock counts | Phase 6.4 broken |
| 7 | test.scm@bebang.ph | Enter 3 KG RM010-A + 2 KG RM030 → Save | Modal closes, line shows "Manual: RM010-A 3 KG, RM030 2 KG"; backend has 2 sibling rows sharing seq | Phase 6.1 broken |
| 8 | test.scm@bebang.ph | Mark Ready for Dispatch → triggers MR | MR has TWO items: RM010-A 3 KG and RM030 2 KG. ZERO `GRP-FROZEN-MANGO` rows. | Phase 8.1 broken |

Test accounts: see `memory/testing-accounts.md`. All passwords `BeiTest2026!`.

## Evidence files required at `output/l3/s163/`

- `form_submissions.json` — every form/button click with payload + response
- `api_mutations.json` — every POST/PUT/PATCH with payload + status
- `state_verification.json` — before/after state checks per scenario

## Verification script results

`bash scripts/s163_verify_phases.sh all` — **ALL GREEN** at session end:
- Phase 1: DocTypes — OK
- Phase 2: Migration — OK
- Phase 3: Pipeline — OK
- Phase 4: Group aggregation — OK
- Phase 5: Submit order — OK
- Phase 6: SCM resolution — OK
- Phase 7: Frontend ordering — OK
- Phase 8: MR expansion — OK
- Phase 9: Sentry — OK
- AUDIT-FIX: No GRP-* leaks into picking.py — OK

## How to run L3 in a fresh session

Open a new Claude Code session and paste:

```
Run /l3-v2-bei-erp for sprint S163.

Plan: docs/plans/2026-04-06-sprint-163-store-ordering-doctypes-product-grouping.md
Branch: s163-store-ordering-doctypes-product-grouping
PRs: <fill in>

L3 scenarios are in the plan under "## L3 Workflow Scenarios" — 8 scenarios.

Pre-test setup:
1. Confirm migration executed (recipes + policies in DocTypes)
2. Confirm GRP-FROZEN-MANGO group exists with RM010-A + RM030
3. Confirm hrms+bei-tasks PRs are merged and deployed

Evidence files to produce:
- output/l3/s163/form_submissions.json
- output/l3/s163/api_mutations.json
- output/l3/s163/state_verification.json

After all scenarios pass:
1. Commit evidence (git add -f output/l3/s163/)
2. Phase 11.1: delete the two CSV fixtures
3. Update plan status to COMPLETED + completed_date
4. Update SPRINT_REGISTRY.md S163 row to COMPLETED
5. git add -f and push
```

---

**STOP. The build agent ends here.**
