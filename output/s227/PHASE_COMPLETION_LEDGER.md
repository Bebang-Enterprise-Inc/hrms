# S227 Phase Completion Ledger

## Phase 0 — Library audit + test discipline

| Task | Status | Evidence | Skipped? | If skipped, why? |
|------|--------|----------|----------|------------------|
| 0.1 | DONE | `output/s227/library/AUDIT.md` (Page Object table) | NO | — |
| 0.2 | DONE | `output/s227/library/AUDIT.md` (Fixtures + Assertions tables) | NO | — |
| 0.3 | DONE | `output/s227/library/CONTRIBUTIONS.md` | NO | — |
| 0.4 | DONE | `AUDIT.md` §"data-testid coverage" — 6 testids identified, deferred to Phase 4 task 4.7 | NO | — |
| 0.5 | DONE | `output/s227/library/FAILURE_RESPONSE.md` + `output/s227/verify_phase_completion.py` | NO | — |

**Phase 0 gate:** 4/4 verifier assertions PASSED.

## Phase 1 — Backend role + scope resolver

| Task | Status | Evidence | Skipped? | If skipped, why? |
|------|--------|----------|----------|------------------|
| 1.1 | DONE | `hrms/on_demand/seed_store_partner_role.py` (idempotent role seed) | NO | — |
| 1.2 | DONE | `hrms/api/sales_dashboard.py` (ROLE_STORE_PARTNER constant + ALLOWED_ROLES membership) | NO | — |
| 1.3 | DONE | `_resolve_allowed_store_scope` partner branch placed AFTER stakeholder, falls through to filter | NO | — |
| 1.4 | DONE | `_should_strip_fleet_context` helper (uses `ALLOWED_ROLES - {ROLE_STORE_PARTNER}`, NOT ALL_STORE_ROLES) | NO | — |
| 1.5 | PARTIAL | Sentry extras added on 4 existing calls (overview, summary, store_rankings, product_mix). 3 wrappers + access_context covered in Phase 2 task 2.5/2.6 (per plan). | NO | — |
| 1.6 | DONE | `hrms/api/test_sales_dashboard_partner.py` — 11 Phase 1 tests + 10 Phase 2 tests (helpers loaded lazily) | NO | — |

**Phase 1 gate:** 8/8 verifier assertions PASSED. AST parse OK (4062 lines).

## Phase 2 — Backend response stripping + cache fix

| Task | Status | Evidence | Skipped? | If skipped, why? |
|------|--------|----------|----------|------------------|
| 2.1 | DONE | `_strip_fleet_context_from_overview` — 12-key docstring (FILTER stores, STRIP discount_rankings, FILTER ranking_state.visible, FILTER analysis.effects baseline-derived keys) | NO | — |
| 2.2 | DONE | `_strip_fleet_context_from_product_mix` — strips fleet_rank/fleet_total_stores/per_store_breakdown/assortment_gap_count/assortment_gap_products, rewrites store_coverage to "<scope>/<scope>" (B13) | NO | — |
| 2.3 | DONE | `copy.deepcopy(result)` + strip applied as LAST step in 4 endpoints (overview, summary, store_rankings, product_mix). 6 deepcopy occurrences (4 endpoints + 2 helpers). | NO | — |
| 2.4 | DONE | `export_sales_dashboard_detail` carries `fleet-safe by schema` comment — no stripping required | NO | — |
| 2.5 | DONE | `get_sales_dashboard_access_context` sets `is_partner_view=True` and `can_group_by_area=False` for partners; `_build_access_context` docstring explicitly retains `company` field (GAP-A CEO directive 2026-04-27) | NO | — |
| 2.6 | DONE | 3 wrapper endpoints (`daily_series`, `channel_mix`, `weather_context`) get NEW `set_backend_observability_context` calls with `is_partner_view` extras | NO | — |
| 2.7 | DONE | `test_sales_dashboard_partner.py` Phase 2 tests verified via standalone Python (helpers extracted, all 12 assertions pass) | NO | — |

**Phase 2 gate:** 5/5 verifier assertions PASSED. AST parse OK. Pure-function unit tests PASSED.

## Phase 3 — Frontend role + RBAC

| Task | Status | Evidence | Skipped? | If skipped, why? |
|------|--------|----------|----------|------------------|
| 3.1 | DONE | `lib/roles.ts` — `STORE_PARTNER: "Store Partner"` added to ROLES | NO | — |
| 3.2 | DONE | `lib/roles.ts` — `[ROLES.STORE_PARTNER]: "Store Partner"` added to ROLE_LABELS | NO | — |
| 3.3 | DONE | `lib/roles.ts` — fuchsia color added to ROLE_COLORS | NO | — |
| 3.4 | DONE | `lib/roles.ts` — STORE_PARTNER added to MODULES.ANALYTICS, ANALYTICS_ROADMAP (v3 reversal), SALES_DASHBOARD allowlists. Exclusion-by-omission from every other module remains the privacy guarantee. | NO | — |
| 3.5 | DONE | `lib/navigation-personas.ts` — STORE_PARTNER persona block (primary: Dashboard/Analytics/SalesDashboard, secondary: Profile, hidden: 80+ modules); inline `[ROLES.STORE_PARTNER, "STORE_PARTNER"]` mapping added AFTER STORE_STAFF, BEFORE EMPLOYEE; NO new ROLE_PERSONA_MAP export | NO | — |
| 3.6 | DONE | `npx tsc --noEmit` baseline = 78 errors (pre-existing, unrelated test files); after S227 changes = 78 errors. NET ZERO new TS errors. `npm run build` ✓ Compiled successfully in 12.9s. | NO | — |
| 3.7 | DONE | `tests/unit/navigation/navigation-personas.test.ts` — 4 tests PASSED (admin priority, HQ_SCM_OVERSIGHT, STORE_PARTNER routing, partner+AS precedence) | NO | — |

**Phase 3 gate:** 6/6 verifier assertions PASSED. Build OK. 4/4 nav tests pass.

## Phase 4a — Frontend conditional rendering (parent pages)

| Task | Status | Evidence | Skipped? | If skipped, why? |
|------|--------|----------|----------|------------------|
| 4.1 | DONE | `sales/page.tsx`: leaderboard Card has `data-testid="analytics-sales-leaderboard"` and S227 comment marking server pre-filter (defense-in-depth) | NO | — |
| 4.2 | DONE | `sales/page.tsx`: Open Full Leaderboard CTA gated on `!access?.is_partner_view` with `data-testid="analytics-sales-open-full-leaderboard-cta"` | NO | — |
| 4.3 | DONE | `product/page.tsx`: Fleet Rank header gated on `sortedProducts.some(p => p.fleet_rank != null)`; Fleet Rank cell gated on `product.fleet_rank != null`. Both have data-testids. | NO | — |
| 4.4 | DONE | `product/page.tsx`: Assortment Gap KPI structural rewrite — independent guard `data.meta.assortment_gap_count != null`; inner cell uses raw value (no `?? 0` fallback — verified absent via grep) | NO | — |
| 4.5 | DONE | `product/page.tsx`: drilldown row uses `drilldownEnabled = isSingleStore && per_store_breakdown?.length > 0` for BOTH onClick AND cursor-pointer styling | NO | — |
| 4.6 | DONE | `product/page.tsx`: Assortment Gap Table gated on `assortment_gap_products?.length && length > 0` | NO | — |
| 4.7 | DONE | 5 testids added (analytics-sales-leaderboard, analytics-sales-open-full-leaderboard-cta, analytics-product-fleet-rank-header, analytics-product-fleet-rank-cell, analytics-product-assortment-gap-card). Phase 4b adds discount card + CSV testids. | PARTIAL | 4.7 split across 4a + 4b |
| 4.8 | DONE | `npm run build` ✓ Compiled successfully in 13.2s | NO | — |

**Phase 4a gate:** 4/4 P4 verifier assertions PASSED. Build OK.

## Phase 4b — Frontend rendering (CSV + child routes + dialog)

| Task | Status | Evidence | Skipped? | If skipped, why? |
|------|--------|----------|----------|------------------|
| 4.9 | DONE | `product/page.tsx`: `downloadCsv` accepts new `isPartnerView` arg; strips `fleet_rank`/`fleet_stores` headers AND row values when partner. `isPartnerView` plumbed via `setIsPartnerView` in access-context fetch. | NO | — |
| 4.10 | DONE | `sales/stores/page.tsx` + `sales/stores/[locationId]/page.tsx`: comment-block audits attached. Both routes are safe-by-default — no fleet-shape fields rendered (rank/position_change shown are within-scope, server-side filtered). | NO | — |
| 4.11 | DONE | `sales/page.tsx`: Highest Discount Stores Card outer guard `(ranking_state.visible || discount_rankings?.length > 0)`. Card hidden entirely when partner (server strips array). Includes `data-testid="analytics-sales-discount-rankings-card"`. | NO | — |
| 4.12 | DONE | `store-detail-dialog.tsx`: comment block classifies all overview field accesses (KEEP/FILTER/STRIPPED). New explicit `(discount_rankings?.length ?? 0) > 0` guard added on the discount callout for defense-in-depth. | NO | — |
| 4.13 | DONE | `npm run build` ✓ Compiled successfully in 12.3s after Phase 4b changes. | NO | — |

**Phase 4b gate:** Build OK after CSV + dialog + child route + discount card changes.

### Phase 4 totals
- 5 sales/page.tsx changes (leaderboard testid, CTA hide, discount card guard, S227 comments)
- 7 product/page.tsx changes (Gap card structural rewrite, Fleet Rank header+cell guards, drilldown enable, downloadCsv, partner-view state)
- 1 store-detail-dialog.tsx field audit + new guard
- 2 child-route audit comment blocks
- 6 data-testids added


- `lib/sales-dashboard.ts` extended with optional `is_partner_view?: boolean` on `SalesDashboardAccessContextResponse` so frontend pages can key conditional renders.

- `_should_strip_fleet_context` count: 13
- `_strip_fleet_context_from_*` count: 6 (2 helpers + 4 endpoint call sites)
- `copy.deepcopy` count: 6 (overview/summary/rankings/product_mix endpoints + 2 helpers)
- `is_partner_view` count: 11 (4 P1 + 3 P2 wrappers + access_context + 3 internal helper checks)


