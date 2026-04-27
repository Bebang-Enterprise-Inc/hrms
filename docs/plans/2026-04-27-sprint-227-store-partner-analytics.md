---
sprint: S227
title: Store Partner role — scoped Sales + Product analytics for non-employee equity partners
branch: s227-store-partner-analytics
status: BUILD_COMPLETE_AWAITING_L3_AND_REVIEW
version: v3 (post-re-audit, 2026-04-27)
plan_date: 2026-04-27
build_completed_date: 2026-04-27
plan_author: Sam Karazi (CEO) + Claude Opus 4.7
audit_evidence: output/plan-audit/sprint-227-store-partner-analytics/verified_blockers.md
phase5_handoff_required: true
phase5_handoff_reason: |
  Per plan §"Phase Budget Summary" v3 mandate: Phase 5 L3 testing MUST run
  in a fresh agent session — context exhaustion at the tail of a 76-unit
  run is the #1 cause of L3 shortcuts per S092 lesson.
build_phases_completed:
  - P0_library_audit
  - P1_backend_role_scope_resolver
  - P2_backend_strippers_cache_fix
  - P3_frontend_role_rbac
  - P4a_parent_pages_conditional_render
  - P4b_csv_child_routes_dialog
  - P6_closeout
canonical_scope: none
canonical_scope_rationale: |
  Pure RBAC + API response shaping. Adds one new Frappe Role (`Store Partner`),
  reuses the existing `BEI Sales Dashboard Store Access` DocType to map partner
  Users to Warehouses, adds a response-stripping helper in
  `hrms/api/sales_dashboard.py` (read-only analytics surface — NOT in the
  canonical-touching API list), and adjusts frontend conditional rendering.
  Zero mutations on `tabCompany` / `tabWarehouse` / `tabCustomer` / `tabSupplier`.
  Zero GL / Sales Invoice / PO / MR / Stock Entry / Journal / Payment Entry
  creation. No COA changes. No `resolve_store_buyer_entity` extension. No
  `commissary.py` / `warehouse.py` / `store.py` / `billing.py` / `procurement.py`
  edits. The plan only READS Warehouse names and `BEI Sales Dashboard Store
  Access` rows — both already-existing canonical surfaces.
total_work_units: 76
phase_count: 7
depends_on: []
evidence_committed:
  - output/s227/SUMMARY.md
  - output/s227/DEFECTS.md
  - output/s227/verification/state_after.json
  - output/s227/verification/api_response_shape_partner.json
  - output/s227/verification/api_response_shape_admin.json
  - output/s227/verification/role_seeded.json
  - output/s227/verification/access_rows_seeded.json
  - output/s227/L3/form_submissions.json
  - output/s227/L3/api_mutations.json
  - output/s227/L3/state_verification.json
  - output/s227/L3/screenshots/*.png
evidence_transient:
  - tmp/s227/probe_*.json
  - tmp/s227/sweep_run_*.log
  - tmp/s227/playwright_trace_*.zip
  - tmp/s227/traceback_*.txt
  - tmp/s227/dev_server_*.log
sentry_projects:
  - bei-hrms (backend whitelisted endpoints in hrms/api/sales_dashboard.py)
  - bei-tasks (frontend route handler app/api/analytics/sales/[endpoint]/route.ts — auto-instrumented)
---

# Sprint 227 — Store Partner Analytics

> **PR-Handoff:** This plan ends at PR creation. The agent does NOT merge or
> deploy. Sam reviews the PR comments, runs the release manager gate, and
> handles merge + deploy himself. The agent stops after Phase 6 (closeout)
> with the PR number recorded in the registry.

## Goal

Give ~12 non-employee equity partners (each holding 1–12 BEI stores) **read-only
access to the Sales and Product analytics pages on my.bebang.ph**, scoped to
their own store(s). Partners see absolute performance numbers — sales totals,
channel mix, daily trend, top products, velocity, discounts, weather — for
their store(s) only. Partners DO NOT see any rank, any other store's name, or
any cross-store comparison. The dashboard is for transparency, not operational
benchmarking.

## Non-Goals

- Not redesigning the Sales or Product pages.
- Not building a separate partner subdomain or portal.
- Not changing the analytics shown to BEI internal team (Area Supervisor,
  Store Supervisor, HQ, Admin) — their existing experience is unchanged.
- Not adding payout/distribution calculations or partner statements (different
  feature, separate sprint).
- Not building partner-management screens (provisioning is manual via Frappe
  Desk, ~3 minutes per partner; only ~12 users).
- Not building audit-log / access-log of partner data views (flagged as future
  work).

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

BEI has ~12 equity partners — non-employees who hold equity in 1–12 specific
BEI-operated stores each. Partners want **transparency about their store's
performance** (so they trust BEI is running the store well and so they can see
the numbers behind their distributions). They are **passive equity holders** —
BEI's ops team runs the stores, makes ordering/staffing/promo decisions.

### Why we do NOT show ranks or fleet comparisons

CEO directive (this brainstorm, 2026-04-27): "partners do not need to act on
anything, we run their stores. Showing them their stores ranking means they
will question our team not doing enough for the store especially for under
performing locations."

Translation: the moment a partner sees their store ranked against any other
store (named or unnamed, fleet or own-stores), they will use that rank as
leverage to pressure the ops team. Even rank-within-their-own-stores creates
the same pressure — "why is my SM Aura store underperforming SM Sta. Rosa?".
The dashboard's job for partners is to deliver clean absolute numbers, not
comparisons. This is fundamentally different from the dashboard's job for the
ops team (who DO need ranks to allocate attention).

### Why reuse `BEI Sales Dashboard Store Access` (not a new DocType)

The existing DocType already maps `User -> Warehouse` rows for the
`Sales Stakeholder` role. Each partner gets one row per store they hold. ~12
partners × 1–12 stores ≈ 30–80 rows total. Trivial scale. Adding a new
DocType for "partners" would duplicate this without gain, and would require a
new admin UI for adding rows. Reuse is correct.

### Why a new role (`Store Partner`) and not extension of `Sales Stakeholder`

`Sales Stakeholder` is an internal BEI role (e.g., a regional manager who
isn't on the ops team but sees sales). Partners are **external** to BEI — they
have no employment, no @bebang.ph email, no internal trust posture. Auditing
needs to distinguish "internal stakeholder access" from "external partner
access." A new role makes that distinction structural and visible in every
log line.

### Why response-stripping (server-side) is the right enforcement layer

The frontend pages (`sales/page.tsx`, `product/page.tsx`) already render most
fleet UI conditionally on the presence of fields like `fleet_rank` and
`assortment_gap_count`. If the server simply omits these fields from the JSON
response when role is `Store Partner`, the frontend "naturally" renders the
partner-correct view with minimal frontend changes. Frontend-only gating
(role checks in JSX) is fragile — every new feature would need a check, easy
to miss. Server-side stripping is one chokepoint.

### Why `canonical_scope: none`

This plan touches `hrms/api/sales_dashboard.py` (read-only analytics) and
frontend RBAC plumbing. It does NOT touch `tabCompany` / `tabWarehouse` /
`tabCustomer` / `tabSupplier` (creates/updates/deletes) or any canonical
surface listed in the canonical gate's "in" criteria. It reads `tabWarehouse`
names but doesn't mutate. It reuses an existing DocType (no schema change).
The canonical scope rule explicitly lists "frontend polish on bei-tasks (CSS,
typography, component refactor, route rename with no backend API changes)"
and "Documentation-only sprints" as `none` examples; this plan is closer to
"frontend polish + read-only API response shaping" than to anything in the
"in" list.

### Trade-offs considered and rejected

1. **Anonymized fleet rank ("top 22%") instead of no rank** — rejected: still
   creates the same accountability pressure once a partner sees they're below
   the fleet average. The CEO's actual concern was the comparative framing
   itself, not the named-store leak.

2. **Dynamic-scope ranking (rank within partner's own stores)** — rejected:
   degenerates to "1 of 1" for single-store partners, AND still creates
   pressure on multi-store partners ("why is my SM Aura store ranked last of
   my 3 stores?").

3. **Separate `partners.bebang.ph` subdomain** — rejected: significant
   overhead (separate auth, separate routing, deployment duplication, design
   upkeep), and would feel like a stripped-down report tool. Partners are
   getting the SAME page our team uses, just with comparative fields stripped.

4. **Extend `Sales Stakeholder` role** — rejected: muddles internal vs
   external user classes; future audits/reports become harder to write
   ("which Sales Stakeholders are partners and which are internal?").

### Known limitations and their mitigations

- **CSV export** is enabled — partners can download their own data. This is a
  real exfiltration vector (a partner could share their store's data publicly).
  ACCEPTED: partners own this data and are bound by NDA. The reverse decision
  (block export) would be hostile and inconsistent with our trust posture.
- **No access-log on partner views** — out of scope. Future sprint should add
  audit logging on `Store Partner` API calls.
- **Partner who is also a BEI employee** — corner case (e.g., a senior officer
  with equity). Behavior: if their User has BOTH `Store Partner` AND any
  `ALL_STORE_ROLES` role, the all-store role wins (they see everything,
  including comparisons). This matches existing `_resolve_allowed_store_scope`
  precedence and is documented in the role resolver.
- **Single-store partner edge case** — solved by stripping comparison fields
  entirely. There's no "1 of 1" rank because rank is hidden, not displayed
  with degenerate denominator.

### Source references

- `hrms/api/sales_dashboard.py:535` — `_resolve_allowed_store_scope()`,
  the existing role-to-scope resolver this plan extends.
- `hrms/api/sales_dashboard.py:571` — the `ROLE_SALES_STAKEHOLDER` branch
  that mirrors the `BEI Sales Dashboard Store Access` lookup pattern that
  partners will reuse.
- `hrms/api/sales_dashboard.py:1644` — `_build_access_context()`, the
  structure that needs to NOT include fleet meta when partner.
- `hrms/api/sales_dashboard.py:3676` — `get_product_mix_analytics()`, the
  endpoint that builds `fleet_rank` / `assortment_gap_*` and needs stripping.
- `hrms/hr/doctype/bei_sales_dashboard_store_access/bei_sales_dashboard_store_access.json`
  — existing DocType schema (3 fields: user, warehouse, notes).
- `bei-tasks/lib/roles.ts:16-71` — ROLES const where `STORE_PARTNER` is added.
- `bei-tasks/lib/roles.ts:1168-1242` — `ROLE_LABELS` and `ROLE_COLORS` maps
  that MUST also include `STORE_PARTNER` (TS exhaustiveness — see MEMORY
  lesson `feedback_role_records_exhaustiveness.md`).
- `bei-tasks/lib/navigation-personas.ts` — persona definition for
  `STORE_PARTNER` controlling sidebar visibility.
- `bei-tasks/app/dashboard/analytics/sales/page.tsx` — fleet leaderboard UI.
- `bei-tasks/app/dashboard/analytics/product/page.tsx` — fleet rank +
  assortment gap UI.
- MEMORY `feedback_correct_over_fast.md` — never strip features to make
  errors disappear; here we strip fleet fields by design, NOT by accident.
- MEMORY `feedback_dont_invent_policy_preconditions.md` — partners are NOT
  store supervisors with extra rules; they're a distinct user class.

---

## Requirements Regression Checklist

Before code is committed, the executing agent verifies each is true. Each
maps to a locked design decision from the brainstorm:

- [ ] **R1** — A new Frappe Role named exactly `Store Partner` is created in
  `hrms/hr/role/store_partner/store_partner.json` (or via `seed_store_partner_role.py`),
  with `desk_access=0` and `disabled=0`. (Source: brainstorm decision —
  external read-only role.)
- [ ] **R2** — `ROLE_STORE_PARTNER = "Store Partner"` is added to
  `hrms/api/sales_dashboard.py` and included in `ALLOWED_ROLES`.
  (Source: backend access gate.)
- [ ] **R3** — `_resolve_allowed_store_scope()` adds a `Store Partner` branch
  that mirrors the `Sales Stakeholder` branch (looks up
  `BEI Sales Dashboard Store Access` rows for the user, maps to warehouses).
  (Source: reuse decision.)
- [ ] **R4** — A new helper `_should_strip_fleet_context(roles: set[str]) -> bool`
  returns `True` iff `Store Partner` ∈ roles AND `roles.intersection(ALLOWED_ROLES - {ROLE_STORE_PARTNER}) == set()`.
  **NOT just ALL_STORE_ROLES** — the broader check ensures Area Supervisor,
  Store Supervisor, and Sales Stakeholder also win precedence over Partner.
  (CEO directive 2026-04-27 — executives who are also equity partners see the
  AS/HQ view, not the partner-restricted view.)
- [ ] **R5** — When `_should_strip_fleet_context()` is true, the response of
  `get_sales_dashboard_overview` / `get_sales_dashboard_summary` /
  `get_sales_dashboard_store_rankings` / `get_product_mix_analytics` /
  `get_sales_dashboard_access_context` OMITS these keys (or filters values):
  `fleet_rank`, `fleet_total_stores`, `assortment_gap_count`,
  `assortment_gap_products`, `per_store_breakdown` (the entire array, not
  just rows), `wow_delta_pct` if computed against the fleet (keep only when
  it's vs the SAME store's prior period), and `stores` (the leaderboard) is
  filtered to only the partner's own stores (so even if BEI sends rank=1
  for SM Aura, no other store appears in the leaderboard list).
  (Source: brainstorm — no rank, no comparison.)
- [ ] **R6** — `bei-tasks/lib/roles.ts` adds `STORE_PARTNER: "Store Partner"`
  to `ROLES`, adds an entry in `ROLE_LABELS`, adds an entry in `ROLE_COLORS`
  (TS Record<Role,…> exhaustiveness — MEMORY `feedback_role_records_exhaustiveness.md`),
  adds `ROLES.STORE_PARTNER` to the allowlists for **`MODULES.ANALYTICS`,
  `MODULES.ANALYTICS_ROADMAP`, AND `MODULES.SALES_DASHBOARD`** — all three
  required because the Product page's RoleGuard uses ANALYTICS_ROADMAP
  (v3 reversal of v2 B8). (Source: RBAC gate + audit v2 C1.)
- [ ] **R7** — `bei-tasks/lib/navigation-personas.ts` adds a
  `STORE_PARTNER` persona with primary = `[DASHBOARD, ANALYTICS, SALES_DASHBOARD]`,
  secondary = `[PROFILE]`, collapsed = `[]`, hidden = everything else.
  **There is NO `ROLE_PERSONA_MAP` exported constant** — the role-to-persona
  mapping is the inline `roleToPersona: [Role, string][]` array INSIDE the
  `getPersonaForRoles()` function (lines 700-724). Insert
  `[ROLES.STORE_PARTNER, "STORE_PARTNER"]` into that array AFTER STORE_STAFF
  and BEFORE EMPLOYEE. Do NOT create a new ROLE_PERSONA_MAP export.
  (Source: audit B2 — sidebar limit.)
- [ ] **R8** — `bei-tasks/app/dashboard/analytics/sales/page.tsx` renders the
  Stores Leaderboard table only when `data.stores.length > 0` AND every store
  in the response is in the user's allowed scope (which is already true when
  partner — but we add an explicit guard so a future regression cannot leak
  fleet stores). (Source: defense in depth.)
- [ ] **R9** — `bei-tasks/app/dashboard/analytics/product/page.tsx` conditionally
  renders the `Fleet Rank` column, the `Assortment Gap` KPI card, the
  Assortment Gap table, and the per-product drilldown (per-store breakdown)
  ONLY when the corresponding fields are PRESENT in the response. When the
  fields are absent, those JSX blocks return `null`. (Source: stripped-shape
  drives UI.)
- [ ] **R10** — Sentry observability calls (`set_backend_observability_context`)
  on the modified `@frappe.whitelist()` endpoints include `module="sales"`
  and `extras={"is_partner_view": True}` when partner role is detected.
  (Source: rule `sentry-observability.md` — DM-7 attribution.)
- [ ] **R11** — `_selected_scope()` (line 601) rejects with PermissionError if
  a partner requests `?stores=<warehouse-not-in-their-access>`. (Existing
  behavior — verify, don't break.)
- [ ] **R12** — Discount metrics (SC %, PWD %, other %) ARE present in the
  partner response. (Source: brainstorm confirmation — partners SEE
  discounts.)
- [ ] **R13** — Weather + business-impact context IS present in the partner
  response. (Source: brainstorm confirmation — partners SEE weather.)
- [ ] **R14** (v2 audit) — Cache safety: the strip pass operates on a
  `copy.deepcopy()` of the cached payload. **Never** mutate a cached object
  in-place. The 4 endpoints in Phase 2 task 2.3 each include
  `result = copy.deepcopy(result)` before strip. (Source: audit B1 —
  cache poisoning across role classes.)
- [ ] **R15** (v2 audit) — `company` field (legal entity) IS visible to
  partners in the access-context store rows. CEO directive 2026-04-27 —
  partners see their entity. Do NOT strip the `company` field. (Source:
  audit GAP-A.)
- [ ] **R16** (v3 reversal) — `MODULES.ANALYTICS_ROADMAP` DOES include
  `Store Partner` in its role allowlist. The Product page's RoleGuard at
  `bei-tasks/app/dashboard/analytics/product/page.tsx:380` uses
  ANALYTICS_ROADMAP — partners need it to reach the page. v2 dropped it
  based on a faulty "future-features placeholder" assumption; v3 reverses.
  (Source: audit v2 C1.)
- [ ] **R17** (v2 audit) — The frontend `downloadCsv()` function in
  `product/page.tsx` produces a CSV with NO `fleet_rank` or `fleet_stores`
  column headers when the user is a partner. (Source: audit B3.)
- [ ] **R18** (v2 audit) — The "Open Full Leaderboard" CTA on the Sales page
  is hidden when `is_partner_view`. The child routes
  `/sales/stores/page.tsx` and `/sales/stores/[locationId]/page.tsx` are
  audited and any fleet-shape fields are guarded. (Source: audit B4.)
- [ ] **R19** (v2 audit) — The `_should_strip_fleet_context` helper checks
  `roles.intersection(ALLOWED_ROLES - {ROLE_STORE_PARTNER}) == set()`, NOT
  just ALL_STORE_ROLES. Tested with all 5 single-role and 4 multi-role
  combinations in the unit tests. (Source: audit B5 + CEO directive
  2026-04-27 — AS view wins.)
- [ ] **R20** (v2 audit) — No Custom DocPerm rows are created on the
  `Store Partner` role. Phase 1 task 1.6 includes a unit test asserting
  `frappe.get_all("Custom DocPerm", filters={"role": "Store Partner"}) == []`.
  (Source: audit B15 — defense in depth.)

**HARD BLOCKER** items:
1. Never silently allow a partner request to escape `_resolve_allowed_store_scope`
   bounds — every `?stores=` value MUST be validated against the scope.
2. Never re-introduce `fleet_rank` / `per_store_breakdown` / `assortment_gap`
   fields into the partner response, even if a future code path mutates the
   response dict — the stripping pass MUST be the LAST step before
   serialization, AND must operate on a deepcopy to avoid cache poisoning.
3. If the executing agent finds that an existing test (`Sales Stakeholder`,
   `Area Supervisor`) breaks because the existing code already lacks scope
   filtering on `stores`, STOP and surface — do NOT silently change the
   non-partner code paths. The plan's scope is `Store Partner` only.
4. Never create a `ROLE_PERSONA_MAP` constant in `navigation-personas.ts` —
   that's dead code. The mapping lives inside `getPersonaForRoles()`.
5. Never create `hrms/hr/role/store_partner/store_partner.json` — that
   directory doesn't exist and Frappe won't auto-load it. Use the imperative
   seed script at `hrms/on_demand/seed_store_partner_role.py`.

---

## Agent Boot Sequence

The executing agent runs these in order, and stops on any failure:

1. **Read this plan fully**, including the Design Rationale and Requirements
   Regression Checklist.
2. **Spawn the worktree** (per `.claude/rules/worktree-isolation.md`):
   ```bash
   BR=s227-store-partner-analytics
   WT=F:/Dropbox/Projects/BEI-ERP-${BR##*/}
   cd F:/Dropbox/Projects/BEI-ERP && git fetch origin --prune
   git worktree add "$WT" -B "$BR" origin/production
   cd "$WT"
   ```
   Also spawn the bei-tasks worktree:
   ```bash
   BT_WT=F:/Dropbox/Projects/bei-tasks-${BR##*/}
   cd F:/Dropbox/Projects/bei-tasks && git fetch origin --prune
   git worktree add "$BT_WT" -B "$BR" origin/main
   ```
   All subsequent code edits happen in `$WT` or `$BT_WT` — NEVER in
   `F:/Dropbox/Projects/BEI-ERP` or `F:/Dropbox/Projects/bei-tasks`.
3. **Verify branch state** — `git status --short` in both worktrees must be
   clean.
4. **Read `docs/plans/SPRINT_REGISTRY.md`** to confirm S227 is the assigned
   ID and that the row references this plan.
5. **Cross-check no concurrent S227 work exists** — `git branch -a | grep s227`
   in both repos. There must be exactly one match (the branch we just
   created).
6. **Verify the existing files this plan reads from**:
   - `hrms/api/sales_dashboard.py` exists and contains
     `_resolve_allowed_store_scope`, `_build_access_context`,
     `get_product_mix_analytics`.
   - `hrms/hr/doctype/bei_sales_dashboard_store_access/bei_sales_dashboard_store_access.json`
     exists with fields `user`, `warehouse`, `notes`.
   - `bei-tasks/lib/roles.ts` contains `ROLES`, `ROLE_LABELS`, `ROLE_COLORS`,
     `MODULE_ACCESS`.
   - `bei-tasks/lib/navigation-personas.ts` exists and exports
     `NAVIGATION_PERSONAS`.
7. **Begin Phase 0**.

## Execution Authority

This sprint is intended for **autonomous end-to-end execution through PR
creation**. The agent does NOT stop for progress-only updates and does NOT
merge or deploy. Stop conditions: see the Autonomous Execution Contract below.

---

## Phase 0 — Library Audit + Test Discipline (5 work units)

Per `.claude/docs/qa-test-library-discipline.md`, every test plan starts
with a library audit. Outputs:

| # | Task | MUST_MODIFY / MUST_CONTAIN | Units |
|---|---|---|---|
| 0.1 | List existing Page Objects that cover Analytics pages. Look in `bei-tasks/tests/e2e/pages/` for `AnalyticsSalesPage`, `AnalyticsProductPage`, `LoginPage`. Catalog what exists. | MUST_CREATE: `output/s227/library/AUDIT.md` containing a table of `(Page Object | exists? | covers what | gap)`. | 1 |
| 0.2 | List existing fixtures relevant to: logging in as a partner-like user (`loggedInAs*` fixtures), seeding `BEI Sales Dashboard Store Access` rows (likely missing), and asserting absence of fleet fields in API responses. | MUST_CONTAIN in AUDIT.md: explicit list of fixtures named, each marked `[REUSE]` / `[EXTEND]` / `[NEW]`. | 1 |
| 0.3 | Define library contributions this sprint will add (declare up front so they're owned by this sprint, not implicit drive-bys). | MUST_CREATE: `output/s227/library/CONTRIBUTIONS.md` listing: (a) `loggedInAsStorePartner` fixture, (b) `seedSalesDashboardStoreAccess` fixture + `cleanupLedger` reverse handler, (c) `assertNoFleetLeak` assertion helper, (d) `AnalyticsSalesPage.assertPartnerView()` method, (e) `AnalyticsProductPage.assertPartnerView()` method. | 1 |
| 0.4 | Verify `data-testid` coverage on the components partners will see. Existing test IDs needed: `analytics-sales-leaderboard`, `analytics-product-fleet-rank-cell`, `analytics-product-assortment-gap-card`. | If any test ID is missing, MUST add a sub-task to the relevant frontend phase (Phase 4) to add the test ID before the L3 phase begins. | 1 |
| 0.5 | Document the failure-response model for L3 (Mode A / B / C from discipline doc §"Failure Discipline"). | MUST_CREATE: `output/s227/library/FAILURE_RESPONSE.md` mapping each potential failure path to the right response. | 1 |

**Phase 0 gate:** AUDIT.md + CONTRIBUTIONS.md + FAILURE_RESPONSE.md present
in `output/s227/library/` and committed. Verification script (Phase 6) checks
all three files exist with non-trivial content (>100 bytes each).

---

## Phase 1 — Backend role + scope resolver (10 work units)

| # | Task | MUST_MODIFY / MUST_CONTAIN | Units |
|---|---|---|---|
| 1.1 | Add Frappe Role via imperative seed script. **DO NOT** create `hrms/hr/role/store_partner/store_partner.json` — that directory does not exist and Frappe will not auto-load it (audit V4). **DO NOT** reference `hrms/seed_bd_roles.py` — that file does not exist either. Pattern to follow: `hrms/patches/v16_0/ensure_sales_dashboard_access.py` (an imperative role/perm setup script). Place the new script at `hrms/on_demand/seed_store_partner_role.py` — consistent with the `s206_seed_intercompany_accounts.py` precedent. The script idempotently creates the Frappe Role: `role_name="Store Partner"`, `desk_access=0`, `disabled=0`. | MUST_CREATE: `hrms/on_demand/seed_store_partner_role.py`. MUST_CONTAIN: `frappe.db.exists("Role", "Store Partner")` check + `frappe.get_doc({"doctype": "Role", "role_name": "Store Partner", "desk_access": 0}).insert(ignore_permissions=True)`. **MUST NOT exist** (negative assertion): `hrms/hr/role/store_partner/store_partner.json` — Phase 6 verification script must `assert not Path("hrms/hr/role/store_partner/store_partner.json").exists()`. | 2 |
| 1.2 | Add `ROLE_STORE_PARTNER = "Store Partner"` constant in `hrms/api/sales_dashboard.py` near the existing `ROLE_*` constants (~line 37). Add it to `ALLOWED_ROLES` (~line 53). | MUST_MODIFY: `hrms/api/sales_dashboard.py`. MUST_CONTAIN: `ROLE_STORE_PARTNER = "Store Partner"`. MUST_CONTAIN: `ROLE_STORE_PARTNER` in the `ALLOWED_ROLES` set literal. | 1 |
| 1.3 | Extend `_resolve_allowed_store_scope()` (~line 535) with a `Store Partner` branch. The branch mirrors the existing `ROLE_SALES_STAKEHOLDER` branch (~line 571–584): look up `BEI Sales Dashboard Store Access` rows where `user == current_user`, fetch the linked warehouses, return them as `scope.stores`. Place the new branch **LAST in the if/elif chain** — after the `ROLE_SALES_STAKEHOLDER` branch — so any other analytics-granting role (Admin, HQ family, AS, SS, Stakeholder) wins precedence over Partner. **CEO directive 2026-04-27:** executives who are also equity partners must see the AS/HQ view, not the partner-restricted view. The Partner branch is the LOWEST scope tier. **MIRROR PATTERN:** copy the Sales Stakeholder fall-through pattern (set `warehouse_rows`, fall through to `_filter_sales_warehouses` at line 587). **DO NOT** copy the Store Supervisor early-return pattern at line 565 — that's a divergent shape. After your branch, the existing line-586 guard `if role_label != ROLE_STORE_SUPERVISOR` continues to work since Partner ≠ Store Supervisor. | MUST_MODIFY: `hrms/api/sales_dashboard.py`. MUST_CONTAIN: `elif ROLE_STORE_PARTNER in roles:` branch with `frappe.get_all("BEI Sales Dashboard Store Access", filters={"user": user}, fields=["warehouse"])`. **MUST NOT CONTAIN** in the Partner branch: `return {` (no early return — fall through to filter). | 3 |
| 1.4 | Add `_should_strip_fleet_context(roles: set[str]) -> bool` helper. Returns `True` iff `ROLE_STORE_PARTNER` ∈ roles AND `roles.intersection(ALLOWED_ROLES - {ROLE_STORE_PARTNER}) == set()`. **NOT just ALL_STORE_ROLES** — the broader check ensures Area Supervisor / Store Supervisor / Sales Stakeholder also win precedence over Partner (CEO directive 2026-04-27). Place near `_resolve_allowed_store_scope()`. Docstring must state: "Strip fleet context iff the user holds Store Partner AND no other analytics-granting role. Executives-who-are-partners (e.g., partner+AS) see the AS view." | MUST_MODIFY: `hrms/api/sales_dashboard.py`. MUST_CONTAIN: `def _should_strip_fleet_context(roles: set[str]) -> bool:`. MUST_CONTAIN: `ALLOWED_ROLES - {ROLE_STORE_PARTNER}` (or equivalent set-difference logic, NOT `ALL_STORE_ROLES`). | 2 |
| 1.5 | Update Sentry observability tagging on the affected endpoints. For each `@frappe.whitelist()` function listed in §"Affected Endpoints" below, add `extras={"is_partner_view": is_partner}` to the `set_backend_observability_context()` call where `is_partner = _should_strip_fleet_context(_get_roles())`. (DM-7 attribution per `sentry-observability.md`.) | MUST_MODIFY: `hrms/api/sales_dashboard.py`. MUST_CONTAIN: `is_partner_view` literal string in 9 places (one per affected endpoint). | 1 |
| 1.6 | Add unit-style backend assertions to `hrms/api/test_sales_dashboard_partner.py` (new file). Tests required: (a) partner with 1 access row → `_resolve_allowed_store_scope()` returns exactly that warehouse; (b) partner + HQ User → returns all warehouses (HQ precedence); (c) **partner + Area Supervisor → returns AS warehouses + `_should_strip_fleet_context()` returns False** (CEO directive: AS view wins); (d) **partner + Sales Stakeholder → returns Stakeholder warehouses + strip returns False**; (e) `_should_strip_fleet_context()` helper truth table covering all 5 single-role and 4 multi-role combinations; (f) **DocPerm safety assertion: `frappe.get_all("Custom DocPerm", filters={"role": "Store Partner"})` returns `[]`** (B15 defense-in-depth — partner role must not inherit any DocPerm rows on other DocTypes). | MUST_CREATE: `hrms/api/test_sales_dashboard_partner.py`. MUST_CONTAIN: 6 test functions covering scope resolution, stripping helper truth table, and DocPerm safety. | 2 |

**Phase 1 gate:** `git diff --name-only` includes `hrms/api/sales_dashboard.py`,
`hrms/on_demand/seed_store_partner_role.py`, `hrms/api/test_sales_dashboard_partner.py`.
`grep -c 'ROLE_STORE_PARTNER' hrms/api/sales_dashboard.py >= 4`. Backend
unit tests pass locally (`pytest hrms/api/test_sales_dashboard_partner.py`).

### Affected Endpoints (referenced by Phase 1 task 1.5 and Phase 2)

All in `hrms/api/sales_dashboard.py`:

| Endpoint | Line | Stripping required |
|---|---|---|
| `get_sales_dashboard_access_context` | 3415 | drop `can_group_by_area`, mark `is_partner_view=True` |
| `get_sales_dashboard_overview` | 3421 | strip from inner payload (see Phase 2) |
| `get_sales_dashboard_summary` | 3449 | inherits from overview — verify no leak |
| `get_sales_dashboard_daily_series` | 3477 | inherits from overview — verify no leak |
| `get_sales_dashboard_channel_mix` | 3502 | inherits from overview — verify no leak |
| `get_sales_dashboard_store_rankings` | 3527 | drop fleet-comparison `stores` rows outside scope (already scoped — verify), drop `comparison_meta` if comparison-vs-fleet (keep if comparison-vs-own-prior-period) |
| `get_sales_dashboard_weather_context` | 3587 | NO STRIPPING — partners see weather (R13) |
| `export_sales_dashboard_detail` | 3612 | strip in CSV export — drop columns that compare to fleet |
| `get_product_mix_analytics` | 3677 | drop `fleet_rank`, `fleet_total_stores`, `per_store_breakdown`, `assortment_gap_count`, `assortment_gap_products`, `wow_delta_pct` if vs-fleet |

---

## Phase 2 — Backend response stripping + cache fix (15 work units)

**CRITICAL ARCHITECTURAL FIX (audit V1 / B1):** The existing `_cache_get_or_set` in `sales_dashboard.py:384-393` caches the unstripped payload under a key built by `_sales_dashboard_cache_key()` (line 400-423). That key has NO role/user/partner field. So an admin's full-fleet payload would get cached and served to a Store Partner with the same `(location_ids, dates, channel)` tuple. The strip MUST run on a deepcopy AFTER cache-fetch, OR the cache key must include `is_partner_view` as a binning token.

This sprint uses the **deepcopy-after-cache-fetch** pattern — simpler, no cache invalidation flush required, and the strip cost is microseconds vs the Supabase query cost.

| # | Task | MUST_MODIFY / MUST_CONTAIN | Units |
|---|---|---|---|
| 2.1 | Implement `_strip_fleet_context_from_overview(payload: dict, scope: dict) -> dict` that operates on a **deepcopy** (caller's responsibility) and removes/filters: `stores` rows where warehouse not in scope (defense-in-depth — already scoped server-side); the entire `discount_rankings` array (B12 — partners don't see it); `ranking_state.visible = False` so frontend hides discount card; `comparison_meta` if rank-delta-vs-fleet; **`analysis.effects` subkeys** (`channel_mix_shift_vs_baseline.pickup_share_delta_pct_points`, `delivery_share_delta_pct_points`, `expected_net_sales_without_vat`, `actual_vs_expected_*`) since those are fleet-baseline derived (B6 — weather wrapper inherits via `analysis`). Enumerate every top-level overview key in a docstring: `scope`/`date_window`/`mode_state`/`summary`/`freshness`/`comparisons`/`daily`/`analysis`/`stores`/`ranking_state`/`discount_rankings`/`channels` — mark each as STRIP / KEEP / FILTER. | MUST_MODIFY: `hrms/api/sales_dashboard.py`. MUST_CONTAIN: `def _strip_fleet_context_from_overview(`. MUST_CONTAIN docstring listing all 12 overview top-level keys with strip/keep/filter classification. | 3 |
| 2.2 | Implement `_strip_fleet_context_from_product_mix(payload: dict, scope: dict) -> dict` (operates on deepcopy). Removes from `payload["meta"]`: `assortment_gap_count`, `assortment_gap_products`. Removes from each product in `payload["products"]`: `fleet_rank`, `fleet_total_stores`, `per_store_breakdown`. Conditionally drops `wow_delta_pct` (the variant vs fleet) — keep the variant vs same-store prior period (verify in implementation by reading the existing `wow_delta_pct` calculation). **B13 fix:** also strip or rewrite `store_coverage` field on each product to `"X/X"` (using only partner's scope size) so the literal `44` fleet count never appears. | MUST_MODIFY: `hrms/api/sales_dashboard.py`. MUST_CONTAIN: `def _strip_fleet_context_from_product_mix(`. MUST_CONTAIN: deletion of all 6 listed keys (5 originals + `store_coverage` rewrite). | 3 |
| 2.3 | Apply the strippers as the LAST step before return in `get_sales_dashboard_overview`, `get_sales_dashboard_summary`, `get_sales_dashboard_store_rankings`, `get_product_mix_analytics`. **Pattern (deepcopy after cache to avoid cache poisoning per V1):** ```python\nresult = ...build_payload...   # may return cached object\nif _should_strip_fleet_context(_get_roles()):\n    result = copy.deepcopy(result)\n    _strip_fleet_context_from_overview(result, scope)\nreturn result\n```. The `copy.deepcopy` is mandatory — without it, the strip mutates the cached object and contaminates other users hitting the same cache key. | MUST_MODIFY: `hrms/api/sales_dashboard.py`. MUST_CONTAIN: `import copy` (or `from copy import deepcopy`). MUST_CONTAIN: `copy.deepcopy(result)` (or `deepcopy(result)`) in 4 endpoints. MUST_CONTAIN: `_should_strip_fleet_context(_get_roles())` invocation in 4 places. | 2 |
| 2.4 | **NO-OP for backend CSV** — audit V6 confirmed `export_sales_dashboard_detail` (line 3635-3659) has no fleet columns; its schema is per-day-per-store rows scoped via `_selected_scope`. Just add a docstring comment in the function noting "fleet-safe by schema; partner view does not require additional stripping." The frontend `downloadCsv` leak is real — handled in Phase 4 task 4.9. | MUST_MODIFY: `hrms/api/sales_dashboard.py:3635-3659` (comment only). MUST_CONTAIN: comment string `fleet-safe by schema`. | 1 |
| 2.5 | Strip the `access-context` response: when partner, set `can_group_by_area: False` and add `is_partner_view: True` for frontend keying. **CEO directive 2026-04-27 (GAP-A):** keep the per-store `company` field (legal entity) visible. Partners SEE their entity name in the store picker — it's their entity. Document this in the `_build_access_context` docstring. | MUST_MODIFY: `hrms/api/sales_dashboard.py:1644-1660`. MUST_CONTAIN: `is_partner_view`. MUST_CONTAIN docstring text: `company field intentionally retained for partners`. | 1 |
| 2.6 | Apply the deepcopy-after-cache pattern to wrapper endpoints `get_sales_dashboard_daily_series`, `get_sales_dashboard_channel_mix`, `get_sales_dashboard_weather_context` (lines 3477-3498, 3502-3523, 3587-3609). Each wrapper calls `get_sales_dashboard_overview()` then re-packs a subset (`overview["daily"]`, `overview["channels"]`, `overview["analysis"]`). Since the overview wrapper now strips for partners, the wrapper inherits — but only if the strip helper enumerates `analysis` and `channels` (per task 2.1 docstring). Add an explicit assertion test in 2.7 that each wrapper output contains no `effects.expected_net_sales_without_vat`, no `effects.channel_mix_shift_vs_baseline`, no `discount_rankings` for partner sessions. **Also add Sentry tagging** to the 3 wrapper endpoints (currently they don't have `set_backend_observability_context()` calls — `daily_series`, `channel_mix`, `weather_context` are exceptions to the otherwise-instrumented pattern). | MUST_MODIFY: `hrms/api/sales_dashboard.py:3477-3609`. MUST_CONTAIN: 3 new `set_backend_observability_context()` calls in the wrappers. | 2 |
| 2.7 | Backend tests for stripping. Add 5 tests to `hrms/api/test_sales_dashboard_partner.py`: (a) overview payload strip → assert removed keys; (b) product-mix payload strip → assert all 6 keys removed including `store_coverage` rewrite; (c) `get_product_mix_analytics` end-to-end as mocked partner → response has no leaks; (d) **cache-poisoning prevention test** — call same endpoint as admin then partner with same `(location_ids, dates, channel)` and assert partner's response has no fleet keys (proves deepcopy works); (e) **wrapper inheritance test** — call `weather_context` as partner and assert no `analysis.effects.channel_mix_shift_vs_baseline` in response. | MUST_MODIFY: `hrms/api/test_sales_dashboard_partner.py`. MUST_CONTAIN: 5 new test functions. | 3 |

**Phase 2 gate:** `pytest hrms/api/test_sales_dashboard_partner.py` passes
all 6 tests. `grep -c '_should_strip_fleet_context' hrms/api/sales_dashboard.py >= 5`.
`grep -c '_strip_fleet_context_from_' hrms/api/sales_dashboard.py >= 2` (helper
definitions).

---

## Phase 3 — Frontend role + RBAC (8 work units)

| # | Task | MUST_MODIFY / MUST_CONTAIN | Units |
|---|---|---|---|
| 3.1 | Add `STORE_PARTNER: "Store Partner"` to `ROLES` const in `bei-tasks/lib/roles.ts` (~line 16-71). | MUST_MODIFY: `bei-tasks/lib/roles.ts`. MUST_CONTAIN: `STORE_PARTNER: "Store Partner"`. | 1 |
| 3.2 | Add `[ROLES.STORE_PARTNER]: "Store Partner"` entry in `ROLE_LABELS` (~line 1168). **TS exhaustiveness — required by `Record<Role, string>`.** | MUST_MODIFY: `bei-tasks/lib/roles.ts`. MUST_CONTAIN: `[ROLES.STORE_PARTNER]: "Store Partner"`. | 1 |
| 3.3 | Add `[ROLES.STORE_PARTNER]: { bg: "...", text: "..." }` entry in `ROLE_COLORS` (~line 1208). Choose a distinct color (suggested: `bg-fuchsia-500/10`, `text-fuchsia-600`) — visually different from existing analytics-viewer roles. **TS exhaustiveness required.** | MUST_MODIFY: `bei-tasks/lib/roles.ts`. MUST_CONTAIN: `[ROLES.STORE_PARTNER]:` in ROLE_COLORS. | 1 |
| 3.4 | Add `ROLES.STORE_PARTNER` to role allowlists for **`MODULES.ANALYTICS` (~line 474), `MODULES.ANALYTICS_ROADMAP` (~line 490), AND `MODULES.SALES_DASHBOARD` (~line 514)**. **REVERSAL OF v2 B8 AMENDMENT (audit v2 C1 2026-04-27):** v2 dropped ANALYTICS_ROADMAP based on a faulty assumption that it was a "future-features placeholder." It is NOT. The actual `bei-tasks/app/dashboard/analytics/product/page.tsx:380` uses `<RoleGuard module={MODULES.ANALYTICS_ROADMAP}>` as its page-level access gate (per the file's S176 comment: "umbrella gate for Product/Manpower/Finance/Operations analytics shells"). Without ANALYTICS_ROADMAP in the partner allowlist, partners get a 403 / RoleGuard rejection on the Product page and the entire sprint promise breaks (L3 scenario 4 fails). **Therefore: partners need 3 modules, not 2.** Exclusion-by-omission from every other module remains the privacy guarantee. | MUST_MODIFY: `bei-tasks/lib/roles.ts`. MUST_CONTAIN: `ROLES.STORE_PARTNER` appears EXACTLY 3 times in MODULE_ACCESS object literal (ANALYTICS, ANALYTICS_ROADMAP, SALES_DASHBOARD). | 1 |
| 3.5 | Add `STORE_PARTNER` persona to `bei-tasks/lib/navigation-personas.ts`: primary = `[MODULES.DASHBOARD, MODULES.ANALYTICS, MODULES.SALES_DASHBOARD]`, secondary = `[MODULES.PROFILE]`, collapsed = `[]`, hidden = ALL OTHER MODULES. **CRITICAL: there is NO `ROLE_PERSONA_MAP` exported constant in this file** (audit V8 / B2). The role-to-persona mapping is an inline `const roleToPersona: [Role, string][]` array INSIDE the `getPersonaForRoles()` function (lines 700-724), and order matters (first-match wins). **Do NOT create a new ROLE_PERSONA_MAP constant** — it would be dead code. Instead: insert `[ROLES.STORE_PARTNER, "STORE_PARTNER"]` into the `roleToPersona` array AFTER `[ROLES.STORE_STAFF, "STORE_STAFF"]` and BEFORE `[ROLES.EMPLOYEE, "DEFAULT"]`. **Precedence note:** if a future user holds Store Partner + AS, the AS branch in `getPersonaForRoles` matches earlier in the iteration order — they get the AS persona, consistent with B5 backend precedence. | MUST_MODIFY: `bei-tasks/lib/navigation-personas.ts`. MUST_CONTAIN: `STORE_PARTNER:` persona block in `NAVIGATION_PERSONAS`. MUST_CONTAIN: `[ROLES.STORE_PARTNER, "STORE_PARTNER"]` inside the `getPersonaForRoles()` function body (NOT as a top-level export). **MUST NOT CONTAIN**: any new `ROLE_PERSONA_MAP` export — Phase 6 verification: `grep -c 'export.*ROLE_PERSONA_MAP' bei-tasks/lib/navigation-personas.ts == 0`. | 2 |
| 3.6 | Run `tsc --noEmit` on bei-tasks. Any TS error here is the exhaustiveness check catching a missed `Record<Role, ...>` entry — this is a hard blocker because production deploys would fail at build time. | Verification only — no file change. MUST_RUN: `cd bei-tasks && npx tsc --noEmit` exits with code 0. | 1 |
| 3.7 | Add `getPersonaForRoles()` smoke test in `bei-tasks/tests/lib/navigation-personas.test.ts` that asserts a user with role `Store Partner` resolves to the `STORE_PARTNER` persona and that `MODULES.PROCUREMENT` is in `hidden`, not `primary`/`secondary`/`collapsed`. | MUST_CREATE OR MODIFY: `bei-tasks/tests/lib/navigation-personas.test.ts`. MUST_CONTAIN: `STORE_PARTNER` test name. | 1 |

**Phase 3 gate:** `cd bei-tasks && npx tsc --noEmit` passes. `grep -c
'STORE_PARTNER' bei-tasks/lib/roles.ts >= 5` (constant, label, color, 3
module allowlists). `grep -c 'STORE_PARTNER' bei-tasks/lib/navigation-personas.ts >= 2`
(persona + map). Smoke test passes.

---

## Phase 4 — Frontend conditional rendering (18 work units)

This phase grew from 12 → 18 work units in v2 to absorb 5 frontend defects the audit caught: B3 (downloadCsv leak), B4 (unprotected child routes), B9 (Gap card ternary structure), B10 (Fleet Rank header), B11 (drilldown onClick), B12 (discount card UX), B14 (store-detail-dialog field audit). At 18 units this exceeds the preferred-split threshold of 12 — split into Phase 4a (parent pages) and Phase 4b (child routes + CSV + dialog) at execution time if context pressure builds.

| # | Task | MUST_MODIFY / MUST_CONTAIN | Units |
|---|---|---|---|
| 4.1 | `app/dashboard/analytics/sales/page.tsx`: where the Stores Leaderboard table is rendered, ensure rendering is gated on `data.stores?.length > 0`. The `data.stores` array is already filtered server-side — this is a defense-in-depth render guard, NOT new logic. Add a comment `// S227: server pre-filters; this guard prevents accidental fleet leak if response shape changes`. | MUST_MODIFY: `bei-tasks/app/dashboard/analytics/sales/page.tsx`. MUST_CONTAIN: `// S227:` comment near the leaderboard JSX block. | 1 |
| 4.2 | Same file: hide the **"Open Full Leaderboard" CTA at sales/page.tsx:1518-1525** when partner. The link goes to `/dashboard/analytics/sales/stores` (B4 — child route reachable post-RBAC change). Frontend-side hide is the simpler defense; the route itself is also protected at the page level by 4.10. Use `{!data.is_partner_view && <OpenFullLeaderboardCTA />}` style guard. Read `data.is_partner_view` from the access-context response (Phase 2 task 2.5 adds this field). | MUST_MODIFY: `bei-tasks/app/dashboard/analytics/sales/page.tsx:~1518`. MUST_CONTAIN: `is_partner_view` guard near the "Open Full Leaderboard" link. | 1 |
| 4.3 | `app/dashboard/analytics/product/page.tsx`: **Fleet Rank column — gate BOTH the cell AND the header** (audit V12 / B10 — plan v1 only gated the cell). Cell at lines 795-796: `{product.fleet_rank != null && <FleetRankBadge rank={product.fleet_rank} ...>}`. Header at line 744: `{isSingleStore && sortedProducts.some(p => p.fleet_rank != null) && <TableHead>Fleet Rank</TableHead>}`. Without the header guard, partner sees an empty "Fleet Rank" column header with all "—" cells. | MUST_MODIFY: `bei-tasks/app/dashboard/analytics/product/page.tsx:741-750, 795-796`. MUST_CONTAIN: `product.fleet_rank != null` guard around the cell. MUST_CONTAIN: `sortedProducts.some(p => p.fleet_rank != null)` (or equivalent presence-check) around the `<TableHead>Fleet Rank</TableHead>`. | 2 |
| 4.4 | **Assortment Gap KPI card structural rewrite** (audit V11 / B9 + v2 audit C3). The current code at lines 541-600 is a single ternary: `{isSingleStore && signalSummary ? (<><SignalCard /><GapCard count={data.meta.assortment_gap_count ?? 0}/></>) : (<><TopProductCard /><HighestMixCard /></>)}`. The `?? 0` fallback renders "0 products not sold here" when the field is stripped — wrong for partners. **Two-part rewrite:** (a) split the ternary so each card is independent — add `{isSingleStore && signalSummary && data.meta.assortment_gap_count != null && <GapCard ... />}`. (b) **inside the GapCard body at line 572**, change `<div className="text-2xl font-bold">{data.meta.assortment_gap_count ?? 0}</div>` to `<div className="text-2xl font-bold">{data.meta.assortment_gap_count}</div>` — the inner `?? 0` becomes dead code once the outer guard ensures non-null, and the Phase 6 grep `assortment_gap_count ?? 0 == 0` would otherwise fail. | MUST_MODIFY: `bei-tasks/app/dashboard/analytics/product/page.tsx:541-600`. MUST_CONTAIN: `data.meta.assortment_gap_count != null` in the outer guard. MUST NOT CONTAIN: `assortment_gap_count ?? 0` ANYWHERE in the file (Phase 6 verification: `grep -c 'assortment_gap_count ?? 0' product/page.tsx == 0` — applies to BOTH the outer guard AND the inner cell). | 3 |
| 4.5 | **Drilldown row — gate BOTH onClick AND expansion** (audit V18 / B11 — plan v1 only gated expansion). At line 761, change `onClick={isSingleStore ? () => setExpandedProduct(...) : undefined}` to `onClick={isSingleStore && product.per_store_breakdown && product.per_store_breakdown.length > 0 ? () => setExpandedProduct(...) : undefined}`. Also remove `cursor-pointer` styling when same condition is false. Expansion at line 821 already has the truthiness guard — verify it stays. | MUST_MODIFY: `bei-tasks/app/dashboard/analytics/product/page.tsx:756-767`. MUST_CONTAIN: `product.per_store_breakdown && product.per_store_breakdown.length > 0` in the onClick predicate (NOT just in the expansion render). | 2 |
| 4.6 | Same file: gate the Assortment Gap Table (the dedicated card that opens when `showGapProducts` is true) on `data.meta.assortment_gap_products?.length > 0`. When absent, the toggle button does nothing AND the table is not rendered. | MUST_MODIFY: `bei-tasks/app/dashboard/analytics/product/page.tsx`. MUST_CONTAIN: `data.meta.assortment_gap_products?.length > 0` guard. | 1 |
| 4.7 | Add `data-testid` attributes for L3 assertions: `data-testid="analytics-product-fleet-rank-cell"` on each fleet-rank cell, `data-testid="analytics-product-fleet-rank-header"` on the header, `data-testid="analytics-product-assortment-gap-card"` on the Gap KPI card, `data-testid="analytics-sales-leaderboard"` on the leaderboard table, `data-testid="analytics-sales-discount-rankings-card"` on the discount rankings card, `data-testid="analytics-sales-open-full-leaderboard-cta"` on the CTA from task 4.2. | MUST_MODIFY: 2 frontend page files. MUST_CONTAIN: 6 distinct `data-testid` strings. | 1 |
| 4.8 | Run `cd bei-tasks && npm run build` to verify the build succeeds with the new conditional rendering. | Verification only. MUST_RUN: `npm run build` exits 0. | 1 |
| 4.9 | **NEW (B3): Frontend `downloadCsv` strip headers when partner.** In `bei-tasks/app/dashboard/analytics/product/page.tsx:182-225`, the function `downloadCsv()` unconditionally appends `["velocity", "contribution_pct", "wow_delta_pct", "fleet_rank", "fleet_stores", "trend_slope", "signal", "daily_series"]` as `storeHeaders` when `isSingleStore=true`. For partners (`is_partner_view=true`), strip `fleet_rank` and `fleet_stores` from the header list AND skip the corresponding `base.push(...)` calls in the row builder. Pattern: `const fleetSafeHeaders = storeHeaders.filter(h => isPartnerView ? !["fleet_rank", "fleet_stores"].includes(h) : true);` and analogously in the row push. | MUST_MODIFY: `bei-tasks/app/dashboard/analytics/product/page.tsx:182-225`. MUST_CONTAIN: `isPartnerView` (or equivalent) check inside `downloadCsv` function. **MUST NOT CONTAIN** in CSV output for partner: literal strings `"fleet_rank"` or `"fleet_stores"` as header tokens. Phase 6 verification: write a CSV from a partner-mock, parse first line, assert no fleet_rank header. | 2 |
| 4.10 | **NEW (B4): Address child routes `/sales/stores/page.tsx` and `/sales/stores/[locationId]/page.tsx`.** Both pages already use `<RoleGuard module={MODULES.SALES_DASHBOARD}>` (verified at sales/stores/page.tsx:407-419). When partners are added to that module's allowlist, both child routes become reachable. Two-fold fix: (a) Audit `bei-tasks/app/dashboard/analytics/sales/stores/page.tsx` for fleet-rank, per-store-breakdown, assortment-gap rendering — apply the same conditional-on-presence guards as the parent (likely fewer such fields since this page is store-list-focused). (b) Audit `stores/[locationId]/page.tsx` similarly. (c) Verify the data-fetch path in both routes goes through the same `fetchSalesOverview` / `/api/analytics/sales/access-context` endpoints — those are server-stripped, so the data IS partner-safe; the fix is to confirm rendering doesn't render undefined fields as defaults. | MUST_MODIFY: `bei-tasks/app/dashboard/analytics/sales/stores/page.tsx` AND `bei-tasks/app/dashboard/analytics/sales/stores/[locationId]/page.tsx`. MUST_CONTAIN: at least one new conditional render guard tied to a stripped field, OR a code comment confirming "no fleet-shape fields rendered" if audit confirms safe-by-default. | 2 |
| 4.11 | **NEW (B12): Hide / strip "Highest Discount Stores" card for partners.** At `bei-tasks/app/dashboard/analytics/sales/page.tsx:1452-1505`, the card renders unconditionally and shows "Select a broader store scope to compare discount burden" when `RANKING_MIN_SCOPE_STORES=5` threshold isn't met (1-4 store partners). This is misleading UX since partners can't broaden scope. Backend Phase 2 task 2.1 already strips `discount_rankings` to `[]`. Frontend: gate the entire card on `bundle.rankings.discount_rankings?.length > 0` so when stripped (empty array) the card doesn't render at all. | MUST_MODIFY: `bei-tasks/app/dashboard/analytics/sales/page.tsx:1452-1505`. MUST_CONTAIN: `bundle.rankings.discount_rankings?.length > 0` (or equivalent) guard around the entire `<Card>` block. | 1 |
| 4.12 | **NEW (B14): Field-by-field audit of `store-detail-dialog.tsx` partner safety.** When a partner picks a store and clicks for detail, the dialog independently calls `fetchSalesOverview([store.warehouse], ...)`. Backend Phase 2 strips for partners — but the dialog's JSX may still try to render fields that assume fleet context. Read the entire `store-detail-dialog.tsx`, list every `data.X.Y.Z` access, classify each as: SAFE (partner-rendered), STRIPPED (must guard with `!= null` or `?.length > 0`), or REPLACE-WITH-FALLBACK (e.g., `comparison.net_delta_pct` becomes "vs prior period" instead of "vs fleet baseline"). Add the field-audit checklist as a code comment block at the top of `store-detail-dialog.tsx`. | MUST_MODIFY: `bei-tasks/app/dashboard/analytics/sales/store-detail-dialog.tsx`. MUST_CONTAIN: a comment block listing classified fields. MUST_CONTAIN: at least one new conditional render guard if any STRIPPED fields are found. | 2 |
| 4.13 | **NEW (v2 audit C2): Second `npm run build` gate at end of Phase 4b.** Tasks 4.9-4.12 modify additional frontend files (`product/page.tsx` for downloadCsv, `sales/page.tsx` for discount card, `store-detail-dialog.tsx` for field audit, `stores/page.tsx` and `stores/[locationId]/page.tsx` for child route audits). The 4a-end build at task 4.8 only verifies the 4a state. Without a 4b-end build, TS errors from `is_partner_view` propagation through `downloadCsv` could escape to PR review. Run `cd bei-tasks && npx tsc --noEmit && npm run build` at end of 4b. | Verification only. MUST_RUN: `npm run build` exits 0 after 4b tasks complete. | 1 |

**Phase 4 gate:** `npm run build` passes. `grep -c 'S227' bei-tasks/app/dashboard/analytics/sales/page.tsx >= 1`. `grep -c
'fleet_rank != null' bei-tasks/app/dashboard/analytics/product/page.tsx >= 1`.
`grep -c 'assortment_gap_count != null' bei-tasks/app/dashboard/analytics/product/page.tsx >= 1`.

---

## Phase 5 — L3 testing (10 work units)

The L3 phase verifies real-browser behavior end-to-end as a partner user.
Per QA library discipline: no `page.request.*`, no `fetch()`, no `curl` for
workflow ops. Real browser only. SSM is allowed for environmental setup
(creating the test partner User + access rows) and verification (reading the
response JSON to assert shape).

### Test Account Provisioning (one-time, via SSM before L3 tests run)

```python
# tmp/s227/provision_test_partner.py
import frappe

def provision():
    test_email = "test.partner.s227@bebang.ph"
    if not frappe.db.exists("User", test_email):
        user = frappe.get_doc({
            "doctype": "User",
            "email": test_email,
            "first_name": "Test",
            "last_name": "Partner",
            "send_welcome_email": 0,
            "enabled": 1,
            "roles": [{"role": "Store Partner"}],
        })
        user.insert(ignore_permissions=True)
        user.new_password = "BeiTest2026!"
        user.save(ignore_permissions=True)

    # Assign 2 stores so we test multi-store partner behavior
    test_stores = ["SM AURA - BEBANG MEGA INC.", "SM STA. ROSA - SWEET HARMONY FOOD CORP."]
    for warehouse in test_stores:
        if not frappe.db.exists("BEI Sales Dashboard Store Access",
                                {"user": test_email, "warehouse": warehouse}):
            frappe.get_doc({
                "doctype": "BEI Sales Dashboard Store Access",
                "user": test_email,
                "warehouse": warehouse,
                "notes": "S227 L3 test fixture — DELETE after sprint closeout",
            }).insert(ignore_permissions=True)
    frappe.db.commit()
```

The cleanup ledger reverses both the access rows and (optionally) the User
record at L3 closeout.

### L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| `test.partner.s227@bebang.ph` | Login → navigate to my.bebang.ph | Redirected to `/dashboard`. Sidebar shows ONLY: Dashboard, Analytics → Sales, Analytics → Product, Profile. NO sidebar entries for Tasks, HR, Procurement, Warehouse, Commissary, Finance, Settings. | R7 (persona) is broken or misapplied. |
| `test.partner.s227@bebang.ph` | Click sidebar "Analytics → Sales" | `/dashboard/analytics/sales` renders. Store picker shows 2 stores (SM Aura + SM Sta. Rosa). Default = "All Stores" = 2 stores. KPI tiles render. Daily trend chart renders. Channel mix renders. Discount metrics render (R12). Weather context renders (R13). | Backend scope resolver (R3) is broken. |
| `test.partner.s227@bebang.ph` | Inspect Stores Leaderboard table on Sales page | The leaderboard table EITHER does not render OR shows ONLY the partner's 2 stores. NO third-party store name (e.g. "BGC", "ORTIGAS GREENHILLS") appears anywhere on the page. | R8 (defense-in-depth) is broken or backend `stores` array leaked fleet rows. |
| `test.partner.s227@bebang.ph` | Click sidebar "Analytics → Product" | `/dashboard/analytics/product` renders. KPI tiles show Total Products + Total Cups + Top Product + Highest-Mix Channel — but NOT Signal Summary, NOT Assortment Gap card. Default view is "All Stores" (= 2 stores). | R4 (`_should_strip_fleet_context`) or R9 (frontend conditional render) is broken. |
| `test.partner.s227@bebang.ph` | Pick a single store from picker (SM Aura) | Page reloads with single-store view. Velocity / WoW / Contribution / Trend / Signal columns render (these are per-store, not comparative — keep). Fleet Rank column does NOT render. Assortment Gap card does NOT render. Per-product drilldown is NOT clickable. | R9 is broken. |
| `test.partner.s227@bebang.ph` | Click on a product row in single-store view | Row does NOT expand. No per-store breakdown table appears. (Drilldown disabled because per_store_breakdown is absent from response.) | R9 sub-task 4.5 is broken. |
| `test.partner.s227@bebang.ph` | Open browser DevTools Network tab → reload Product page → inspect `/api/analytics/sales/product-mix` response JSON | Response JSON has products array. Each product has `total_quantity`, `total_gross_sales`, `velocity`, `contribution_pct`, `trend_label`. Each product DOES NOT have `fleet_rank`, `fleet_total_stores`, `per_store_breakdown`. Response meta DOES NOT have `assortment_gap_count` / `assortment_gap_products`. | R5 (response stripping) is broken. |
| `test.partner.s227@bebang.ph` | Open DevTools → reload Sales page → inspect `/api/analytics/sales/access-context` response | Response has `allowed_stores` with exactly 2 stores. Response has `is_partner_view: true`. Response has `can_group_by_area: false`. | R2 / R5 broken. |
| `test.partner.s227@bebang.ph` | Try to manually navigate to `/dashboard/procurement` | Server-side `RoleGuard` rejects → renders 403 / "no access" page OR redirects to `/dashboard`. | R6 (allowlist exclusion) is broken. |
| `test.partner.s227@bebang.ph` | Try to call `/api/analytics/sales/product-mix?stores=BGC` (a store NOT in the partner's scope) via browser fetch from the page | API returns 403 with body `{"error": "Store selection 'BGC' is outside your allowed scope."}`. (Existing behavior of `_selected_scope`, R11.) | R11 / `_selected_scope` is broken — partners could escape scope. |
| `test.partner.s227@bebang.ph` | Click "Export CSV" on Product page | CSV downloads. Open the CSV — columns include product_name, channel, avg_unit_price, total_quantity, total_gross_sales, velocity, contribution_pct, wow_delta_pct (vs own prior period), trend_label, daily_series. NO columns for fleet_rank, fleet_stores, assortment_gap, or any other store name. | R5 / Phase 2 task 2.4 broken. |
| `test.partner.s227@bebang.ph` | Logout. Login as `test.area.supervisor@bebang.ph` (existing internal role). Visit `/dashboard/analytics/product`. Inspect Network response. | Internal role's response DOES include `fleet_rank`, `assortment_gap_*`, `per_store_breakdown`. **No regression** — this confirms stripping is partner-only. | Phase 2 stripping is incorrectly applied to non-partners. |

### L3 Tasks

| # | Task | Output | Units |
|---|---|---|---|
| 5.1 | Provision the test partner user + 2 access rows via the SSM script above. Capture before-state. | `output/s227/L3/provision_log.json`. | 1 |
| 5.2 | Build `bei-tasks/tests/e2e/fixtures/loggedInAsStorePartner.ts` fixture per the library contributions plan. Builds on the existing `loggedInAs*` pattern. | `bei-tasks/tests/e2e/fixtures/loggedInAsStorePartner.ts` exists. | 1 |
| 5.3 | Build `assertNoFleetLeak(page)` helper that asserts the rendered DOM contains no `data-testid="analytics-product-fleet-rank-cell"`, no `data-testid="analytics-product-assortment-gap-card"`, and no third-party store name from a known fleet list. | `bei-tasks/tests/e2e/assertions/assertNoFleetLeak.ts` exists. | 1 |
| 5.4 | Write `bei-tasks/tests/e2e/specs/s227-store-partner-analytics.spec.ts` covering the 12 scenarios above. Each scenario uses the new fixture + assertion + Page Object methods. | Spec file exists. Each scenario has at least one `await expect(...)` assertion. | 3 |
| 5.5 | Execute the spec via Playwright real-browser run (NOT `--reporter=line --grep` shortcuts). Record traces. | `output/s227/L3/playwright_report/`. | 1 |
| 5.6 | Verify response shapes via SSM probe: log in as the test partner via API (cookie-based session), call all 9 affected endpoints, save response JSON, run a structural diff against expected-no-fleet-keys list. | `output/s227/L3/api_response_shape_partner.json` + `api_mutations.json` + `state_verification.json`. | 1 |
| 5.7 | Repeat the response-shape probe as `test.area.supervisor@bebang.ph` and assert fleet keys ARE present (regression check). | `output/s227/L3/api_response_shape_admin.json`. | 1 |
| 5.8 | If any L3 scenario fails, classify per Failure Response: Mode A (app bug — file [BUG], don't touch test/library, push fix); Mode B (test bug — fix the test, promote pattern if generic); Mode C (brittleness — fix the LIBRARY, never paper over with `waitForTimeout`). Emit `output/s227/library/LIBRARY_IMPROVEMENTS.md` if ≥3 library fixes. | Per Failure Response section below. | 1 |

**Phase 5 gate:** All 12 L3 scenarios pass. `output/s227/L3/form_submissions.json`,
`api_mutations.json`, `state_verification.json` all exist and contain real
assertions (not empty stubs). `cleanupLedger.pendingEntries === 0` after
`afterEach`. No `page.request.` / `fetch(` calls in workflow steps (only
in setup/verification probes).

---

## Phase 6 — Closeout (5 work units)

| # | Task | MUST_MODIFY / MUST_CONTAIN | Units |
|---|---|---|---|
| 6.1 | Write `output/s227/SUMMARY.md` with: outcome (PASS/FAIL), counts (12/12 L3 scenarios), 3 affected endpoint groups, role + access rows seeded, evidence file paths, and the PR number. | MUST_CREATE: `output/s227/SUMMARY.md`. | 1 |
| 6.2 | Write `output/s227/DEFECTS.md` listing any defects discovered during L3 + their disposition (FIXED-IN-S227 / DEFERRED-TO-S228 / WONTFIX). If no defects, the file says "No defects identified." | MUST_CREATE: `output/s227/DEFECTS.md`. | 1 |
| 6.3 | Run the verification script `output/s227/verify_phase_completion.py` (created in Phase 0 task 0.5). Script does git-diff + grep over the assertions in this plan and exits non-zero on any miss. | Script exit code 0. | 1 |
| 6.4 | Update plan YAML metadata: `status: GO` → `status: COMPLETED`, add `completed_date: 2026-04-NN`, add `execution_summary: "..."`. Update `docs/plans/SPRINT_REGISTRY.md` row for S227 with COMPLETED status + PR number(s). Commit + push both files using `git add -f` (docs may be gitignored). | MUST_MODIFY: this plan file + SPRINT_REGISTRY.md. | 1 |
| 6.5 | Create the PR via `GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms ...` (one PR for hrms, one for bei-tasks). PR description includes the task-by-task checklist (Zero-Skip Enforcement) and links back to this plan. **Then STOP** — do NOT merge, do NOT deploy. Report PR numbers to user. | hrms PR + bei-tasks PR exist. PR descriptions list every task with status. | 1 |

**Phase 6 gate:** `output/s227/SUMMARY.md` exists, registry shows COMPLETED,
2 PRs open. Worktree status is clean. Closeout sequence:

```bash
# In each worktree:
git status --short    # must be clean (or explicitly committed)
cd F:/Dropbox/Projects/BEI-ERP
git worktree remove F:/Dropbox/Projects/BEI-ERP-s227-store-partner-analytics
cd F:/Dropbox/Projects/bei-tasks
git worktree remove F:/Dropbox/Projects/bei-tasks-s227-store-partner-analytics
```

If a worktree has uncommitted files at this stage, the agent commits them
to a follow-up branch (NEVER pushes more commits to `s227-store-partner-analytics`
after the PR is created — see MEMORY `feedback_check_registry_against_branches.md`).

---

## Zero-Skip Enforcement

Every task in Phases 0–6 MUST be implemented. No exceptions. The agent MUST
notify Sam before proceeding past any phase if any task in that phase is
skipped or partial.

### Phase Completion Checklist (per phase)

After each phase, the agent appends to `output/s227/PHASE_COMPLETION_LEDGER.md`:

```
## Phase N — <name>
| Task | Status | Evidence | Skipped? | If skipped, why? |
|------|--------|----------|----------|------------------|
| N.1  | DONE   | <git SHA + filename> | NO | — |
| N.2  | DONE   | <git SHA + filename> | NO | — |
...
```

### Verification Script (filesystem-grounded, NOT self-report)

`output/s227/verify_phase_completion.py` (created in Phase 0 and run at
each phase gate):

```python
#!/usr/bin/env python3
"""S227 phase completion verifier — filesystem-grounded.

Runs after each phase. Exits non-zero on any miss. Self-assessment is not
trustworthy (see S154 incident); evidence comes from git diff and grep.
"""
import subprocess
import sys
from pathlib import Path

REPO_HRMS = Path("F:/Dropbox/Projects/BEI-ERP-s227-store-partner-analytics")
REPO_BT = Path("F:/Dropbox/Projects/bei-tasks-s227-store-partner-analytics")

failures = []

def must_modify(repo: Path, files: list[str], phase: str):
    diff = subprocess.run(["git", "-C", str(repo), "diff", "--name-only", "origin/HEAD"],
                          capture_output=True, text=True).stdout
    for f in files:
        if f not in diff:
            failures.append(f"[{phase}] MUST_MODIFY missed: {f}")

def must_contain(repo: Path, file: str, pattern: str, count: int, phase: str):
    p = repo / file
    if not p.exists():
        failures.append(f"[{phase}] MUST_CONTAIN file missing: {file}")
        return
    found = sum(1 for line in p.read_text().splitlines() if pattern in line)
    if found < count:
        failures.append(f"[{phase}] MUST_CONTAIN '{pattern}' in {file}: expected >= {count}, found {found}")

# Phase 1
must_modify(REPO_HRMS, ["hrms/api/sales_dashboard.py", "hrms/api/test_sales_dashboard_partner.py",
                        "hrms/on_demand/seed_store_partner_role.py"], "P1")
must_contain(REPO_HRMS, "hrms/api/sales_dashboard.py", "ROLE_STORE_PARTNER", 4, "P1")

# Phase 2
must_contain(REPO_HRMS, "hrms/api/sales_dashboard.py", "_should_strip_fleet_context", 5, "P2")
must_contain(REPO_HRMS, "hrms/api/sales_dashboard.py", "_strip_fleet_context_from_", 2, "P2")

# Phase 3
must_modify(REPO_BT, ["lib/roles.ts", "lib/navigation-personas.ts"], "P3")
must_contain(REPO_BT, "lib/roles.ts", "STORE_PARTNER", 5, "P3")
must_contain(REPO_BT, "lib/navigation-personas.ts", "STORE_PARTNER", 2, "P3")

# Phase 4
must_contain(REPO_BT, "app/dashboard/analytics/product/page.tsx", "fleet_rank != null", 1, "P4")
must_contain(REPO_BT, "app/dashboard/analytics/product/page.tsx", "assortment_gap_count != null", 1, "P4")
must_contain(REPO_BT, "app/dashboard/analytics/sales/page.tsx", "S227", 1, "P4")

# Phase 5
for f in ["form_submissions.json", "api_mutations.json", "state_verification.json",
          "api_response_shape_partner.json", "api_response_shape_admin.json"]:
    if not (Path("output/s227/L3") / f).exists():
        failures.append(f"[P5] L3 evidence missing: output/s227/L3/{f}")

# Phase 6
for f in ["output/s227/SUMMARY.md", "output/s227/DEFECTS.md",
          "output/s227/verification/state_after.json"]:
    if not Path(f).exists():
        failures.append(f"[P6] closeout evidence missing: {f}")

if failures:
    print("VERIFICATION FAILED:\n" + "\n".join(failures))
    sys.exit(1)
print("All phase completion assertions passed.")
```

### Forbidden agent behaviors

- Skipping a task silently
- Marking partial work as "done"
- Replacing a task with a simpler version without user approval
- Saying "deferred to next sprint" without explicit user OK
- Combining tasks and dropping features in the merge
- Implementing happy path only, skipping the negative scenarios in §"L3 Workflow Scenarios"
- Pushing a new commit to `s227-store-partner-analytics` after the PR is
  merged (per MEMORY `feedback_check_registry_against_branches.md` —
  every fix-after-PR-merge gets its OWN branch)

---

## Library Contributions

This sprint contributes the following to `bei-tasks/tests/e2e/`:

| Artifact | Path | Purpose |
|---|---|---|
| Fixture | `tests/e2e/fixtures/loggedInAsStorePartner.ts` | Reusable login-as-partner fixture for any future spec testing partner-scoped surfaces. |
| Fixture | `tests/e2e/fixtures/seedSalesDashboardStoreAccess.ts` | Seeds + tears down `BEI Sales Dashboard Store Access` rows via cleanup ledger. |
| Assertion | `tests/e2e/assertions/assertNoFleetLeak.ts` | Asserts a rendered page has no fleet rank, no assortment gap, no third-party store names. Reusable for any partner-scoped page audits. |
| Page Object method | `tests/e2e/pages/AnalyticsSalesPage.ts::assertPartnerView()` | Encapsulates the partner-shape assertions for the Sales page. |
| Page Object method | `tests/e2e/pages/AnalyticsProductPage.ts::assertPartnerView()` | Same for the Product page. |
| Helper | `tests/e2e/support/buildPartnerWithStores.ts` | Builder: creates a User + N access rows in one call, returns a cleanup token. |

Owner: this sprint. Future sprints are consumers + extenders.

---

## Failure Response (Mode A / B / C)

Per `.claude/docs/qa-test-library-discipline.md` §"Failure Discipline":

- **Mode A (app bug)** — the feature under test is broken. Action: file
  `[BUG]` against the relevant phase task, do NOT modify test code or
  library, push a fix to the in-flight branch (since the PR is not yet
  created), re-run the L3 spec.
- **Mode B (test bug)** — the test is wrong. Action: fix the test. If the
  fix involves a pattern useful elsewhere (e.g., a flaky modal interaction),
  promote the fix to a Page Object method or a fixture and reference it from
  the spec.
- **Mode C (brittleness/flakiness)** — the spec is flaky due to timing or
  selector instability. Action: fix the LIBRARY. NEVER `waitForTimeout`,
  NEVER `retry(3)` masking. Identify the root cause (network race, missing
  test ID, server-side timing), fix at the root.

If ≥3 library fixes happen during execution, emit
`output/s227/library/LIBRARY_IMPROVEMENTS.md` listing each Mode C fix with
its root cause and resolution.

---

## Anti-Rewind / Concurrent-Run Protection

Lighter version since this plan is purely additive (new constants, new
helper functions, new conditional render guards) — no replacement of
existing logic.

| Concern | Mitigation |
|---|---|
| `hrms/api/sales_dashboard.py` is touched by many sprints (S176, S179, S182, S183, S185, etc.) | Only ADD lines. Phase 1+2 are pure additions: new constant, new branch in resolver, new helper, new strip functions, modifications to add `_should_strip_fleet_context()` invocation as the LAST step of 4 endpoint return paths. No existing logic is replaced. |
| `bei-tasks/lib/roles.ts` is high-risk (S181 lesson — TS exhaustiveness) | Phase 3.6 hard-blocker: `tsc --noEmit` MUST pass. ROLE_LABELS + ROLE_COLORS exhaustiveness verified by tooling. |
| `bei-tasks/app/dashboard/analytics/{sales,product}/page.tsx` are large files (29k+ tokens) | Add conditional `&& product.fleet_rank != null` guards INSIDE existing JSX blocks — do not refactor or "simplify" surrounding code. Run `git diff --stat` after each phase: line count change should be small (~+50 lines), not large (~-500 lines). If line count drops by >20%, STOP and review (MEMORY `feedback_correct_over_fast.md` and CLAUDE.md "Line Count Awareness"). |
| Existing scope precedence (admin > HQ > Area > Store > Stakeholder) | Partner branch placed AFTER stakeholder, so it doesn't interfere with admin/HQ/area/store users. |
| Concurrent runs (e.g. S225 also in flight) | Different file domains: S225 = Stock Reconciliation / canonical scripts. S227 = sales_dashboard + frontend RBAC. Zero overlap. |

**Remote-truth baseline (recorded at Phase 0):**
- `hrms` release-head: `git rev-parse origin/production` (record in
  `output/s227/verification/remote_truth_baseline.json`).
- `bei-tasks` release-head: `git -C F:/Dropbox/Projects/bei-tasks rev-parse origin/main`.

**Pre-touch backup contract:** before mutating any of the 5 protected files
(`sales_dashboard.py`, `roles.ts`, `navigation-personas.ts`, `sales/page.tsx`,
`product/page.tsx`), the agent runs `git diff origin/production --
<file> > tmp/s227/pretouch/<file>.diff` to capture the pre-touch state.

---

## Status Reconciliation Contract

When any of {phase status, defect count, scenario pass count, PR number,
sprint status} changes, the agent updates ALL of the following in the same
work unit:

1. `output/s227/SUMMARY.md`
2. `output/s227/PHASE_COMPLETION_LEDGER.md`
3. `output/s227/DEFECTS.md`
4. `docs/plans/2026-04-27-sprint-227-store-partner-analytics.md` (this plan's
   YAML status field + any inline counts)
5. `docs/plans/SPRINT_REGISTRY.md` (S227 row)

If any of these has stale counts at PR creation time, that's a closeout
defect.

---

## Signoff Model

- **Mode:** single-owner.
- **Approver of record:** Sam Karazi (CEO).
- **Signoff artifact:** PR review approval comment from Sam on both the
  hrms PR and the bei-tasks PR.
- **Note:** No synthetic department-approval rows. There is no Finance / HR /
  Legal sign-off on this sprint — it's a frontend RBAC + read-only analytics
  feature with zero financial or compliance impact.

---

## Autonomous Execution Contract

```yaml
completion_condition:
  - all 7 phase gates green (verify via output/s227/verify_phase_completion.py)
  - all 12 L3 scenarios pass with evidence in output/s227/L3/
  - hrms PR created against Bebang-Enterprise-Inc/hrms with task-by-task checklist in description
  - bei-tasks PR created against Bebang-Enterprise-Inc/BEI-Tasks with task-by-task checklist
  - SPRINT_REGISTRY.md row for S227 updated with both PR numbers + COMPLETED status
  - this plan's YAML metadata flipped to status: COMPLETED
  - both worktrees removed cleanly (`git worktree list` shows neither)
  - final target state: `pr_open_awaiting_review` (NOT merged, NOT deployed — that's Sam's job)
stop_only_for:
  - missing credentials/access (Frappe SSM access, GH token, Vercel access)
  - destructive approval needed (e.g., need to disable existing User account)
  - genuine business-policy decision (e.g., partner asks for a feature not in scope)
  - unresolved [UNVERIFIED] values that affect partner-facing output
  - direct conflict with unrelated in-flight work (e.g., S225 force-pushes over our changes)
continue_without_pause_through:
  - audit (Phase 0 library audit)
  - execute (Phases 1-4)
  - L3 (Phase 5)
  - PR creation (Phase 6 task 6.5)
  - closeout (Phase 6)
blocker_policy:
  programmatic: fix and continue
  evidence mismatch: normalize plan + continue
  repeated technical failure x3: pause, do grounded research, then continue
  business-data/policy: pause
signoff_authority: single-owner
canonical_closeout_artifacts:
  - output/s227/SUMMARY.md
  - output/s227/DEFECTS.md
  - output/s227/PHASE_COMPLETION_LEDGER.md
  - output/s227/verification/state_after.json
  - output/s227/L3/form_submissions.json
  - output/s227/L3/api_mutations.json
  - output/s227/L3/state_verification.json
  - docs/plans/2026-04-27-sprint-227-store-partner-analytics.md
  - docs/plans/SPRINT_REGISTRY.md
```

---

## Sentry Observability (DM-7)

Every modified `@frappe.whitelist()` endpoint in
`hrms/api/sales_dashboard.py` already has a
`set_backend_observability_context()` call (verified at lines 3430, 3458,
3540, 3690). This sprint extends those calls with an `extras={"is_partner_view": <bool>}`
field so Sentry can filter partner traffic separately:

```python
set_backend_observability_context(
    module="sales",
    action="get_product_mix_analytics",
    mutation_type="read",
    extras={"is_partner_view": _should_strip_fleet_context(_get_roles())},
)
```

**Sentry project mapping:**
- Backend: project `bei-hrms` (slug: `bei-hrms`, platform: python)
- Frontend: project `bei-tasks` — `app/api/analytics/sales/[endpoint]/route.ts`
  is a Next.js API route, auto-instrumented by `@sentry/nextjs`. No additional
  code required there.
- Org: `bebang-enterprise-inc`

**Verification:** after deploy, search Sentry for `is_partner_view:true`
and confirm partner traffic is tagged. (This is post-merge work for Sam, not
in this plan's scope.)

---

## Provisioning & Rollout Plan (Sam, post-merge)

Once the PR merges and deploys (Sam's responsibility), Sam provisions the
~12 partners. ~3 minutes per partner:

1. **Frappe Desk → User → New:**
   - Email: partner's personal email (Gmail, Yahoo, etc. — no @bebang.ph
     requirement).
   - First Name / Last Name: partner's real name.
   - Send Welcome Email: ✓ (so they get a password setup link).
   - Roles: add ONLY `Store Partner`. Do NOT add `Employee` or any other
     role.
   - Save.
2. **Frappe Desk → BEI Sales Dashboard Store Access → New:**
   - User: the partner's email.
   - Warehouse: select the warehouse for one of their stores.
   - Notes: e.g., "Partner: <name>, equity: <%>, since: <year>"
   - Save. Repeat per store the partner holds (1–12 rows).
3. **Send the partner:**
   - my.bebang.ph URL.
   - Their welcome email password reset link (auto-sent).
   - A 1-paragraph "what you'll see" note: "You'll see Sales and Product
     analytics for your store(s) only. The data updates daily by ~9 AM
     Manila time."
4. **Verify partner login** — at first login, confirm they see only the
   stores assigned, no fleet leaderboards, no rank columns.

If a partner's stores change (acquires more, divests one), Sam adds/removes
rows in `BEI Sales Dashboard Store Access`. Removal is per-warehouse, not
all-or-nothing.

---

## Execution Workflow (links)

- Test Python changes locally: `/local-frappe`
- Deploy changes (Sam): `/deploy-frappe`
- Full workflow: `/agent-kickoff`
- E2E testing: `/e2e-test`

---

## Phase Budget Summary (v3 post-re-audit)

| Phase | Units (v1) | Units (v2) | Units (v3) | Cumulative |
|---|---|---|---|---|
| Phase 0 — Library audit | 5 | 5 | 5 | 5 |
| Phase 1 — Backend role + scope resolver | 10 | 11 | 11 | 16 |
| Phase 2 — Backend response stripping + cache fix | 10 | 15 | 15 | 31 |
| Phase 3 — Frontend role + RBAC | 8 | 8 | 8 | 39 |
| Phase 4 — Frontend conditional rendering | 12 | 18 | **19** | 58 |
| Phase 5 — L3 testing | 10 | 12 | 12 | 70 |
| Phase 6 — Closeout | 5 | 6 | 6 | 76 |
| **Total** | **60** | **75** | **76** | **76** |

Hard limit per phase: 15 units. Preferred split threshold: 12. Phase 4 (19u)
exceeds both. **Phase 4 split is now MANDATORY (not optional)** — execute in
two sub-phases:
- **Phase 4a** = tasks 4.1–4.8 (parent pages + first build gate at 4.8)
- **Phase 4b** = tasks 4.9–4.13 (CSV + child routes + dialog + second build gate at 4.13)

Both sub-phases end with `npm run build` to catch type-propagation regressions
between 4a and 4b (audit v2 C2). Phase 2 (15u) is at the hard limit but
not over.

Total 76 units ≤ 80-unit ceiling — single-agent-single-session viable, but
tight. **Phase 5 L3 testing MUST run in a fresh agent session** (no longer a
soft recommendation — context exhaustion at the tail of a 76-unit run is
the #1 cause of L3 shortcuts per S092 lesson; mandate replaces the v1/v2
"recommend" wording).

## v3 Amendment Log (re-audit-driven, 2026-04-27 evening)

The v2 plan was re-audited and 4 v2-introduced or v2-uncaught issues surfaced.
v3 fixes them.

| # | Re-audit ID | Severity | Section | Amendment |
|---|---|---|---|---|
| 1 | v2-frontend-C1 | CRITICAL | Task 3.4 + R6 + R16 | **Reverse v2 B8** — restore `MODULES.ANALYTICS_ROADMAP` to the partner allowlist. The Product page's RoleGuard at `bei-tasks/app/dashboard/analytics/product/page.tsx:380` uses ANALYTICS_ROADMAP; v2's "future-features placeholder" assumption was wrong. Without it, partners get 403 on Product page and the entire sprint promise breaks. |
| 2 | v2-frontend-C2 | CRITICAL | NEW task 4.13 | Add second `npm run build` at end of Phase 4b to catch type-propagation regressions from `is_partner_view` plumbed through `downloadCsv` (4.9), discount card (4.11), dialog audit (4.12), and child routes (4.10). |
| 3 | v2-frontend-C3 | CRITICAL | Task 4.4 (precision) | Explicitly require removing the inner `data.meta.assortment_gap_count ?? 0` at line 572. Outer guard makes inner fallback dead code; Phase 6 grep for `?? 0` would otherwise fail. |
| 4 | v2-deployment-blockers | WARNING | Phase Budget section | Phase 4 split now MANDATORY (was "if context pressure builds"). Phase 5 fresh-session also MANDATORY (was "recommend"). |

## v2 Amendment Log (audit-driven, 2026-04-27 morning)

The 16 amendments below were applied after the multi-agent plan audit
(`output/plan-audit/sprint-227-store-partner-analytics/verified_blockers.md`)
caught architectural defects in v1.

| # | Audit ID | Severity | Section | Amendment |
|---|---|---|---|---|
| 1 | B1 | CRITICAL | Phase 2 (NEW task 2.3 pattern) | Strip operates on `copy.deepcopy()` to prevent Redis cache poisoning across role classes |
| 2 | B2 | CRITICAL | Task 3.5 + R7 | Rewrote — `ROLE_PERSONA_MAP` doesn't exist; use inline `roleToPersona` array inside `getPersonaForRoles()` |
| 3 | B3 | CRITICAL | NEW task 4.9 | Frontend `downloadCsv` strips fleet column headers for partners |
| 4 | B4 | CRITICAL | NEW task 4.2 + 4.10 | "Open Full Leaderboard" CTA hidden for partners; child routes `/sales/stores` and `/sales/stores/[locationId]` audited |
| 5 | B5 | CRITICAL | Task 1.3, 1.4, R4, R19 | `_should_strip_fleet_context` checks `ALLOWED_ROLES - {ROLE_STORE_PARTNER}`, not just ALL_STORE_ROLES. CEO directive: AS view wins for executives-who-are-partners |
| 6 | B6 | CRITICAL | Task 2.1, 2.6 | Strip helper docstring enumerates all 12 overview keys; 3 wrapper endpoints (`daily_series`, `channel_mix`, `weather_context`) get Sentry tagging + verified to inherit strip via overview |
| 7 | B7 | CRITICAL | Task 1.1 | Removed dead references to `seed_bd_roles.py` and `hrms/hr/role/`; pattern is `hrms/patches/v16_0/ensure_sales_dashboard_access.py`; script path is `hrms/on_demand/seed_store_partner_role.py` |
| 8 | B8 | WARNING | Task 3.4 + R6, R16 | Dropped `MODULES.ANALYTICS_ROADMAP` from STORE_PARTNER allowlist |
| 9 | B9 | CRITICAL | Task 4.4 | Structural rewrite of Signal+Gap ternary — no more `?? 0` fallback for stripped field |
| 10 | B10 | WARNING | Task 4.3 | Fleet Rank `<TableHead>` gets `sortedProducts.some(p => p.fleet_rank != null)` guard |
| 11 | B11 | WARNING | Task 4.5 | `onClick` on drilldown row gates on `per_store_breakdown` presence, not just `isSingleStore` |
| 12 | B12 | WARNING | NEW task 4.11 | Discount Rankings card gated on `discount_rankings?.length > 0`; backend strips array |
| 13 | B13 | WARNING | Task 2.2 | `store_coverage` rewrite to `"X/X"` for partners; literal `44` fleet count never appears |
| 14 | B14 | WARNING | NEW task 4.12 | Field-by-field audit of `store-detail-dialog.tsx` partner safety |
| 15 | B15 | WARNING | Task 1.6 + R20 | Custom DocPerm safety assertion test added |
| 16 | GAP-A | DECISION | Task 2.5 + R15 | CEO directive: keep `company` field (legal entity) visible to partners |
| 17 | GAP-B | INFO | Task 1.3 | Note added: mirror Stakeholder fall-through pattern, NOT Store Supervisor early-return |

---

## Cold-Start Test (Self-Check)

Before this plan is handed off, the agent verifies all of the following:

- [x] Every external dependency resolved with concrete details (DocType:
  `BEI Sales Dashboard Store Access` with fields `user`, `warehouse`,
  `notes`).
- [x] Every file path complete and verified (sales_dashboard.py at exact
  line numbers; roles.ts and navigation-personas.ts at exact line numbers).
- [x] Every API has endpoint + auth + sample response (9 endpoints listed
  with line numbers; auth is Frappe session cookie via Next.js proxy).
- [x] Every function-not-to-break is listed: `_resolve_allowed_store_scope`
  (don't change existing branches), `_selected_scope` (don't change
  PermissionError behavior), `set_backend_observability_context` (already
  imported at top of file).
- [x] Every frontend route has path + RBAC roles + pattern: `/dashboard/analytics/sales`
  and `/dashboard/analytics/product` are existing routes; pattern is
  `RoleGuard module={MODULES.ANALYTICS_ROADMAP}`.
- [x] Branch state documented: `production` is dirty with pre-existing
  modifications (registry, procurement.py, etc.) — these are NOT this
  plan's concern; the worktree spawns from `origin/production` clean.
- [x] MUST_MODIFY assertions on every "modify FILE" task.
- [x] MUST_CONTAIN assertions on every UI feature task.
- [x] Verification script (Python) defined in Phase 6.
- [x] Script checks filesystem (git diff + grep) — not agent self-report.

---

## Closeout: Final Sprint State

After Phase 6 completes:

```yaml
status: COMPLETED
completed_date: 2026-04-NN
execution_summary: |
  Added Store Partner Frappe role + persona; ~12 partners can now log into
  my.bebang.ph and see Sales + Product analytics scoped to their store(s)
  only — no rank, no fleet leak, no other store names. Discount metrics +
  weather context preserved per CEO directive.
prs:
  - hrms#NNN
  - bei-tasks#NNN
test_evidence: output/s227/L3/
worktrees_removed: yes
follow_ups:
  - audit-log on partner API access (future sprint, lightly recommended)
```

---

*End of plan.*
