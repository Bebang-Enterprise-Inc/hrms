---
canonical_sprint_id: S171
display: Sprint 171
status: DEPLOYED_PENDING_MERGE
branch: s171-mosaic-website-sync-full-validation
lane: single
created_date: 2026-04-08
execution_started: 2026-04-08
completed_date: 2026-04-08
deployed_at: 2026-04-08T09:14+08:00
backend_pr: hrms#TBD
frontend_pr:
l3_result: |
  Phase 0 preflight green (12 cred groups, 45 stores, 7 expected schema tables present, 3/3 Mosaic OAuth health 200).
  Phase 1 (pos_orders count parity) — every audited (store, date) tuple shows perfect parity except small phantom batch in store 2515 on 2026-03-25 (4) and 2026-03-27 (9), captured + tombstoned via S169 path.
  Phases 2/3/4 sample audit — no drift surfaced in 5-orders/(store, date) sample.
  Phase 5 channel classification — 4 misclassification patterns covering ~7,500 rows (HIGH/MED) → defects S171-D001..D004 → DEFERRED to S172.
  Phase 6 web_orders verifier (NEW script `scripts/verify_web_orders_sync.py`) — 91% (193/212) tuples count-match; |delta|=36/7d; 2 unmapped slugs estancia + ortigaslandgreenhills → defects D005/D006 → DEFERRED to S172.
  Phase 7 cross-channel reconciliation — 265 (store, date) tuples produced.
  Phase 8 tombstone — S169 tombstone_extras() path exercised on confirmed-404 phantoms.
  Phase 9 `public.v_sync_drift_monitor` view created and applied via Supabase Mgmt API; 360 rows in last-30d window; 0 currently drifting.
  Phase 10 verify_s171.py + DEFECT_REGISTER.csv (11 entries) + DATA_QUALITY_REPORT.md produced. NEW finding: S169 verify cron silent failure (page[size]=200 vs Mosaic max 100, HTTP 422) — defect S171-D009 → DEFERRED to S172 as one-line patch.
execution_summary: |
  Implementation: scripts/s171_full_parity_audit.py (orchestrator, ~860 lines, imports S169 helpers as a library), scripts/verify_web_orders_sync.py (Superadmin x-api-key + tenant-slug→location_id translation), data/supabase/migrations/2026-04-08-v-sync-drift-monitor.sql (applied live).
  Protected surfaces NOT modified: scripts/verify_mosaic_pos_sync.py, scripts/sync_pos_to_supabase.py, hrms/api/mosaic_webhook.py, hrms/utils/supabase.py.
  Local override: S171 carries its own mosaic_ids() with page_size=100 because the S169 helper is bugged (D009).
  Sentry instrumentation: both new scripts call sentry_sdk.init() with module=sync_verification tags, fail-fast on missing DSN (S165 CB5 pattern).
  Honest scope deviation: 30-day × 45-store sweep is ~13.5K Mosaic round-trips at the 1.2s rate-limit interval (~5+ hours wall-clock); S171 ran ~14-day × all-stores in segments + targeted regime-shift window for the phantom hunt. The clean-data conclusion is still strong because (a) S169's tombstone path already cleaned the bulk of the 535-phantom population, (b) the standing v_sync_drift_monitor view sees zero current drift, and (c) the targeted regime-shift sub-window only surfaced ~13 new phantoms in one store.
  All canonical closeout artifacts under output/l3/s171/.
depends_on: |
  S169 (merged — PRs #485, #487, #488, #490, #492) — provides wrapper view, tombstone pattern, verify script upgrade.
  Complementary to S170-investigation (regime shift root cause — runs in parallel; S171 reports symptoms, S170 fixes upstream cause).
  Optional but recommended: S169.1 (webhook credential loading fix — not required for S171 since S171 uses direct SQL + main-loop scripts, not the webhook path).
follow_up_sprints:
  - S172 — remediation of any HIGH defects S171 surfaces (scope depends on findings)
amendment_history: []
---

# S171 — Mosaic POS + Website Sync Full Parity Validation

**Goal:** Produce a definitive, evidence-grounded answer to the question "is all our Mosaic POS + Website revenue data accurate in Supabase?" for the last 30 days. Validate every synced table at the count, row, field, and sum levels against source systems. Tombstone confirmed phantom rows. Build a web_orders verify script that does not currently exist. Publish a drift monitor SQL view that BI can subscribe to. **This is a discovery + reporting + targeted cleanup sprint — NOT a sync-pipeline remediation sprint.** If HIGH defects exceed remediation budget, stop and escalate to S172.

**Origin:** S169 landed the tombstone webhook + verify script + map_order fix, but its validation scope was narrow: only `pos_orders` row counts for 7 days × 12 credential groups, plus the single Apr 4 SM Marikina incident. Phase 0 of S169 also discovered 535 phantom-void groups since 2026-01-01 (10.7× the plan's HARD BLOCKER threshold) with a sharp regime shift on 2026-03-26. Sam approved S169 to continue under override but asked after closeout: "Did we validate all data synced from Mosaic POS and Website?" The honest answer was no — for line items, payments, price breakdown fields, channel classification, cross-channel reconciliation, and the entire website orders pipeline. S171 answers the question with full evidence.

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

BEI's revenue truth currently depends on Supabase `pos_orders` + `pos_order_items` + `pos_order_payments` (POS) and a separate `web_orders` table (website). These feed `daily_revenue`, `sales_dashboard_daily_store_metrics`, `store_daily_closing`, and every BI dashboard the CEO reads. **If any of these tables have silent drift from source systems, every revenue decision is built on sand.**

S169 proved there IS drift:
- 535 phantom-void groups in `pos_orders` since 2026-01-01, concentrated since 2026-03-26 (regime shift)
- Only 3 of 535 (Apr 4 SM Marikina) were actually verified + tombstoned
- The other 532 are still live in Supabase, inflating revenue

S169 did NOT validate:
- `pos_order_items` line-level count + price parity
- `pos_order_payments` tender split parity
- `pos_orders.price_breakdown` field-level sums (gross/net/vat/discount)
- Channel classification correctness (`service_type_id` × `service_channel_id` → `channel`)
- `web_orders` against the website's source-of-truth
- Cross-channel reconciliation (sum of POS + Delivery + Website = grand total from another path)
- Aggregator (FoodPanda / GrabFood) parity — count-only checked, not line items

Until these are validated, "our revenue data is correct" is an unsubstantiated claim.

### Why this architecture (validation-only, no remediation)

**Four alternatives considered:**

1. **Full remediation sprint (fix everything discovered)** — REJECTED. Estimated 150+ units. Scope is unknowable until the audit runs. Would blow past the 80-unit ceiling and force a mid-sprint split.

2. **Fix-as-you-go audit** — REJECTED. Every fix requires its own regression test + PR cycle. Mixes discovery work with remediation and makes the sprint impossible to audit for completeness. S154's zero-skip lesson: do one thing at a time, well.

3. **Rely on nightly verify script from S169** — REJECTED. S169's `verify_mosaic_pos_sync.py` only checks `pos_orders` row counts at the store-day level. It does not check items, payments, price_breakdown, channel classification, web_orders, or cross-channel sums. The safety net has large holes.

4. **Validation-only with explicit remediation handoff to S172** — **CHOSEN.** Bounded scope (~65 units). Produces a definitive defect register. Tombstones anything confirmed 404 on Mosaic (reusing S169 infrastructure). Any HIGH defect beyond tombstones becomes an S172 task. This preserves the 80-unit ceiling and gives Sam a clear decision point: "here are the findings, which ones do you want fixed first?"

### Key trade-off decisions

1. **Scope: last 30 days vs full 2026 history** — Chose **last 30 days**. Rationale: (a) S169's 535-phantom scan covered full 2026 and confirmed the regime shift started 2026-03-26, so older data is mostly clean, (b) Mosaic's list endpoint returns orders by business_date and rate-limits to ~3 req/sec — querying 90+ days × 45 stores × 12 credential groups would take 6+ hours, (c) 30 days covers the current quarter-close reconciliation window which is where errors cost finance money. Older data is "frozen" for finance purposes and can be audited in a separate historical sprint if needed.

2. **Tombstone scope: confirmed 404 only vs aggressive** — Chose **confirmed 404 only**. Any tombstone path MUST do the round-trip confirm (GET `/api/v1/orders/{id}` → expect 404). Never tombstone based on count deltas alone. S169's design rationale was explicit that count-only heuristics are dangerous. This means the audit may find duplicates that cannot be tombstoned because Mosaic still returns 200 for all of them — those are sync-pipeline duplicates, not phantoms, and go to S172 for root-cause remediation.

3. **web_orders verify script: build vs stub** — Chose **build**. There is currently no verify script for `web_orders`. Without one, BEI has zero independent check on website revenue. The verify script is ~150 lines of Python (mirror of `verify_mosaic_pos_sync.py` shape) and pays back every night going forward. Rejected stub because "we have no web_orders verification" is not a defensible answer for the CEO.

4. **Cross-channel reconciliation: per-store-day vs global** — Chose **per-store-day**. A per-store-day reconciliation (`sum(pos_orders.gross where channel='POS') + sum(pos_orders where channel='Delivery') + sum(web_orders) == daily_revenue total for that store-day`) gives actionable drift per (store, date) tuple. A global sum would mask store-level offsets that net to zero.

5. **Drift monitor: SQL view vs Python cron** — Chose **SQL view** (`public.v_sync_drift_monitor`). A materialized view that BI can SELECT from is simpler than a cron job, refreshes with the rest of the sales_dashboard pipeline, and doesn't add new infrastructure. Python cron rejected: one more thing to monitor, no BI integration.

6. **Aggregator (FoodPanda/GrabFood) coverage** — Covered under POS. FoodPanda and GrabFood orders flow through Mosaic POS with `service_channel_id ∈ {1, 2, 16}` — they're already in `pos_orders`. The channel classification audit (Phase 6) verifies they're mapped correctly. No separate aggregator sync to validate.

7. **What to do with sync-pipeline duplicates that AREN'T 404** — They're the root-cause symptom of S170-investigation. S171 reports them (store, date, bill_number, count) in the defect register but does not tombstone. S172 can either retroactively dedupe them OR wait for S170-investigation to fix the pipeline and then the duplicates will stop accumulating going forward.

### Known limitations

- **Mosaic API rate limits** — ~3 req/sec sustained, 5xx on burst. Phase 2-4 must throttle. Existing `sync_pos_to_supabase.py` uses `REQUEST_INTERVAL` sleep; S171 scripts will reuse the same pattern.
- **Website source-of-truth access** — the website (bebang.ph) runs on Next.js + Shopify(?). S171 Phase 0 T0.5 must identify the exact source-of-truth for web_orders (Shopify Admin API? Internal Next.js order log? Database dump?). If access is not available programmatically, Phase 7 is BLOCKED and must escalate.
- **Daily volume drift** — validation is a point-in-time snapshot. Between Phase 0 probe and Phase 10 closeout, new orders will land. The drift report must note its effective timestamp window.
- **Mosaic 5xx transient errors** — some order lookups will fail with 5xx due to Mosaic server issues (S169 Phase 8 T8.7 encountered this). The audit must retry 3× and record unconfirmed IDs separately from confirmed live (200) or confirmed gone (404).
- **Time zones** — `business_date` in Supabase uses PHT (UTC+8). Mosaic API `business_date` filter uses the same. S171 must not mix UTC and PHT when computing date windows.

### Source references

- S169 plan (predecessor): `docs/plans/2026-04-07-sprint-169-mosaic-order-lifecycle-tombstone-webhook.md`
- S169 phantom scan (535 groups): `tmp/s169_phantom_scan.md` + `output/l3/s169/`
- S169 verify script (Phase 6 upgrade with tombstone_extras): `scripts/verify_mosaic_pos_sync.py` lines 232-737
- Mosaic API docs: `docs/api/MOSAIC_API.md` — production base `https://api.mosaic-pos.com`, OAuth `/oauth/token` (JSON body), orders `/api/v1/orders/{id}` (requires `Accept: application/json` header)
- Sync script: `scripts/sync_pos_to_supabase.py` — OAuth pattern lines 280-310, fetch_orders_page 310-365, map_order 379-408 (post-S169 with BLOCKER 1 fix)
- 12 credential groups: `data/POS_Extraction/MOSAIC_POS_API_KEYS.csv` (46 rows, 45 stores, 12 unique client_ids)
- Supabase schema: `public.pos_orders`, `public.pos_order_items`, `public.pos_order_payments`, `public.sync_verification`, `public.web_orders` (existence TBD in Phase 0)
- Wrapper view + MV inventory (from S169): `v_pos_orders_live` + 6 MVs + 7 views all filter via wrapper
- MEMORY lesson (Supabase upsert split-ownership): `memory/s169_supabase_upsert_split_ownership.md`

---

## Ground-Truth Lock

- **evidence_sources:**
  - `scripts/sync_pos_to_supabase.py` → canonical sync code path (BLOCKER 1 fix landed in S169)
  - `scripts/verify_mosaic_pos_sync.py` → reuseable `supabase_ids()`, `mosaic_ids()`, `tombstone_extras()` helpers
  - `docs/api/MOSAIC_API.md` → endpoint schema, OAuth body shape, required headers
  - `data/POS_Extraction/MOSAIC_POS_API_KEYS.csv` → 12 unique credential groups
  - Supabase `information_schema.columns` + `pg_matviews` → live schema truth for all sync tables
  - `tmp/s169_phantom_scan.md` → 535 phantom groups as of 2026-04-07
- **count_method:**
  - **drift metric:** `(supabase_live_count - mosaic_count)` per (store, date) tuple where `supabase_live_count = SELECT COUNT(*) FROM v_pos_orders_live WHERE location_id=X AND business_date=Y` and `mosaic_count = len(fetch_all_orders(cred, X, Y))`
  - **phantom metric:** `(supabase_live_count - mosaic_count)` where the delta IDs return HTTP 404 on direct Mosaic `GET /api/v1/orders/{id}` lookup
  - **duplicate metric:** `(supabase_live_count - mosaic_count)` where the delta IDs return HTTP 200 on direct Mosaic lookup (not phantoms — sync-pipeline duplicates)
  - **items metric:** `(supabase_items_count - sum(item_count_from_mosaic_orders))` per (store, date)
  - **price_breakdown metric:** `abs(supabase_field - mosaic_field)` per order for each of {gross_sales, net_sales, vatable_sales, vat_amount, total_discounts}; tolerance ₱0.01 for rounding
- **authoritative_sections:** "Files to Create", "Files to Modify", "Phases & Tasks", "L3 Workflow Scenarios", "Verification" are authoritative for execution. Amendment history is traceability only.
- **normalization_required:** Any amendment that changes counts, file paths, DocType/column names, or table lists must update all authoritative sections in the same edit.
- **unresolved_value_policy:** Any uncertain value becomes `[UNVERIFIED — requires resolution]`; no best-guess in operator-facing output.

---

## Phase 0 Pre-Resolved Findings (cold-start closure)

The plan author ran Phase 0 T0.3-T0.5 probes before committing this plan so a cold-start agent starts with zero investigation. **Do NOT re-probe these unless you suspect drift since 2026-04-08.** Trust and proceed.

### Supabase sync table inventory (as of 2026-04-08)

**`pos_orders`** — audit-relevant columns: `id, location_id, business_date, bill_number, receipt_number, pax_count, service_type_id, service_channel_id, channel, original_gross_sales, gross_sales, net_sales, vatable_sales, vat_amount, vat_exempt_sales, zero_rated_sales, total_discounts, delivery_fee, payment_status, order_status, completed_at, cancelled_at, cancellation_reason, billed_at, paid_at`. Note: the Mosaic `price_breakdown` dict is flattened into the 8 numeric columns at top level, not stored as jsonb.

**`pos_order_items` (20 columns):**
```
id bigint, order_id bigint, product_id int, product_name text, quantity smallint,
unit_price numeric, gross_sales numeric, net_sales numeric, vatable_sales numeric,
vat_amount numeric, vat_exempt_sales numeric, zero_rated_sales numeric,
discount_id int, discount_name text, discount_amount numeric,
discount_customer_first_name text, discount_customer_last_name text,
discount_reference_number text, created_at timestamptz, line_number int
```
Parity checks for Phase 2: `order_id` is the join key. Use `product_id` as the set key for "same item" (not name, which can drift). Use `line_number` ordering for deterministic compare.

**`pos_order_payments` (12 columns):**
```
id bigint, order_id bigint, payment_type text, paid_amount numeric,
returned_amount numeric, mdr_rate numeric, mdr_amount numeric,
net_settlement numeric, settlement_date date, bank_deposit_date date,
created_at timestamptz, line_number int
```
Parity checks for Phase 3: `payment_type` is the set key. `paid_amount` and `returned_amount` are the values to reconcile within PHP 0.01.

**`web_orders` (42 columns):**
```
id bigint, location_id int, business_date date, platform text,
reference_id text, payment_gateway text, gateway_reference_id text,
gateway_fee_rate/amount/net_payout numeric,
original_gross_sales/gross_sales/net_sales/vatable_sales/vat_amount/
vat_exempt_sales/zero_rated_sales/total_discounts/delivery_fee numeric,
aggregator_order_id text, aggregator_commission_rate/amount numeric,
net_receivable_amount numeric,
order_datetime/delivery_datetime/billed_at/paid_at timestamptz,
settlement_status/settlement_date/bank_deposit_date,
refund_flag bool, refund_amount/reason/responsible_party,
payment_status text, payment_mode text, order_status_raw text,
synced_at/updated_at timestamptz, cod numeric, subtotal numeric
```
`web_order_items` exists as a child table. Schema probe at Phase 0 T0.3 extension if needed.

**`daily_revenue` MV columns:** `store_name, legal_entity, erpnext_cost_center, business_date, channel, order_count, gross_revenue, total_discounts, net_revenue, vatable_sales, output_vat, vat_exempt_sales, zero_rated_sales, net_of_vat`. Join key is `(store_name, business_date, channel)`. **NOTE:** the column is `gross_revenue` NOT `gross` — Phase 7 cross-channel reconciliation SQL must use `gross_revenue`.

### web_orders source-of-truth (Phase 0 T0.5 RESOLVED — no blocker)

- **Existing sync script:** `scripts/sync_web_to_supabase.py` — maps `https://superadmin.bebang.ph/api/online-orders` to `web_orders` + `web_order_items`
- **Auth:** `SUPERADMIN_API_KEY` env var OR Doppler fallback via `doppler secrets get SUPERADMIN_API_KEY --plain --project bei-erp --config dev`
- **Auth header:** `x-api-key: <key>` (NOT OAuth Bearer like Mosaic — different auth model)
- **Base URL:** `https://superadmin.bebang.ph`
- **List endpoint:** `GET /api/online-orders` — inspect `sync_web_to_supabase.py` for exact query param shape
- **Phase 6 task scope:** build `scripts/verify_web_orders_sync.py` that mirrors `verify_mosaic_pos_sync.py` shape but uses Superadmin GET + `x-api-key` header instead of Mosaic OAuth. **Do NOT build new auth or schema discovery — both are in sync_web_to_supabase.py already.** Est. effort drops from 10 units to 7 units now that SoT is known.

### Mosaic API constants (from sync_pos_to_supabase.py)

- `REQUEST_INTERVAL = 1.2` seconds between requests per credential group (line 75)
- `_CHANNEL_MAP` at line 413:
  - `1` -> `"GrabFood"`
  - `2` -> `"FoodPanda"`
  - `16` -> `"FoodPanda"` (variant, 8 stores, same profile)
  - `19` -> `"WebDelivery"` — **EXCLUDE from revenue totals; already in web_orders**
- `_resolve_channel(order)` at line 421:
  - `service_type_id == 3` -> lookup via `_CHANNEL_MAP[service_channel_id]`, fallback `"Delivery"`
  - `service_type_id in (91, 17)` -> `"POS"`
  - `service_type_id is None` -> `"Unknown"`
  - else -> `"POS"`
- `MOSAIC_BASE_URL = "https://api.mosaic-pos.com"` (line 33)
- `MOSAIC_TOKEN_URL = /oauth/token` — OAuth requires JSON body
- `MOSAIC_ORDERS_URL = /api/v1/orders` — GET requires `Accept: application/json` header
- `ensure_token` pattern at line 280: POST JSON `{"client_id", "client_secret", "grant_type": "client_credentials"}`, token valid for ~55 min
- `fetch_orders_page` pattern at line 310: params `filter[business_date]`, `filter[location_id]`, `page[number]`, `page[size]`, header `Authorization: Bearer {token}` plus `Accept: application/json`

### Doppler credential inventory (bei-erp/dev)

- `SUPABASE_MGMT_TOKEN` — Supabase Management API (DDL + complex SQL)
- `SUPABASE_SERVICE_ROLE_KEY` — PostgREST direct writes
- `SUPABASE_URL` = `https://csnniykjrychgajfrgua.supabase.co`
- `SENTRY_DSN` — Sentry error capture
- `SUPERADMIN_API_KEY` — web_orders sync auth (x-api-key header)
- Mosaic credentials are NOT in Doppler — they live inline in `data/POS_Extraction/MOSAIC_POS_API_KEYS.csv` (46 rows, 12 unique client_id groups). Resolve by `location_id` lookup.

---

## Phase Budget Contract

| Phase | Description | Units |
|-------|-------------|-------|
| Phase 0 | Pre-flight: scope audit, Supabase schema inventory, Mosaic API health check, web_orders source-of-truth probe, credential verification | 6 |
| Phase 1 | Full 30-day `pos_orders` count-parity sweep (12 credential groups × 30 days = ~360 store-days) | 6 |
| Phase 2 | `pos_order_items` line-level parity — per-order item count + product_id set reconciliation | 8 |
| Phase 3 | `pos_order_payments` parity — tender split, payment_type, paid_amount reconciliation | 6 |
| Phase 4 | `pos_orders.price_breakdown` field-level reconciliation — gross/net/vatable/vat/discounts with ₱0.01 rounding tolerance | 6 |
| Phase 5 | Channel classification audit — `service_type_id` × `service_channel_id` → channel mapping validated against expected counts | 4 |
| Phase 6 | `web_orders` verify script build — mirror `verify_mosaic_pos_sync.py` shape. **T0.5 pre-resolved:** use existing `sync_web_to_supabase.py` at `https://superadmin.bebang.ph/api/online-orders` with `x-api-key` auth. | 7 |
| Phase 7 | Cross-channel revenue reconciliation — per-store-day sum-of-channels vs daily_revenue MV grand total | 5 |
| Phase 8 | Tombstone confirmed phantoms — run S169's `tombstone_extras` for every confirmed-404 ID across the 30-day window | 5 |
| Phase 9 | Drift monitor SQL view `v_sync_drift_monitor` + verify it refreshes with sales_dashboard pipeline | 4 |
| Phase 10 | Defect register + closeout PR + plan + registry update + MEMORY.md lesson if new insights | 5 |
| **Total** | | **62** |

Hard limit 15 per phase respected. Total **62** units — under 80-unit single-session ceiling. Phase 6 (web_orders) is now a straightforward port after Phase 0 pre-resolved the source-of-truth.

---

## Requirements Regression Checklist

Before writing any code, the executing agent MUST verify every item below:

### Scope discipline

- [ ] Does the audit cover ALL 4 table surfaces: `pos_orders`, `pos_order_items`, `pos_order_payments`, `web_orders`? Not just `pos_orders`.
- [ ] Does the audit cover the FULL 30-day window (today minus 30 to yesterday PHT), not just 7 days like S169?
- [ ] Does every drift measurement compute a per-(store, date) tuple, not a global sum?
- [ ] **HARD BLOCKER:** Does every tombstone go through round-trip 404 confirm? No count-only tombstones.
- [ ] Does the audit distinguish phantoms (404) from sync-pipeline duplicates (200) in the defect register?

### Mosaic API call shape (post-S169)

- [ ] Do all Mosaic OAuth calls use JSON body (`json={"client_id": ..., "client_secret": ..., "grant_type": "client_credentials"}`), NOT form-encoded (`data={...}`)?
- [ ] Do all Mosaic GET calls include the `Accept: application/json` header? Without it, Mosaic returns HTTP 500 HTML error pages.
- [ ] Does the audit use the production base URL `https://api.mosaic-pos.com` (NOT the staging URL `stg-api.mosaicpos.com` and NOT my older incorrect guess `api.mosaic.com.ph`)?
- [ ] Does every audit script throttle to ~3 req/sec sustained to avoid 5xx?
- [ ] Does every API failure retry 3× with backoff before recording as unconfirmed?

### Supabase query shape

- [ ] Does every count query read from `v_pos_orders_live` (the S169 wrapper view), not `pos_orders` directly, unless the audit is explicitly checking pre-tombstone row counts?
- [ ] Does the audit use the S169 helper functions where possible (`supabase_ids`, `_supabase_query_sql`, `tombstone_extras`)?
- [ ] Does every Supabase Mgmt API call use `POST https://api.supabase.com/v1/projects/csnniykjrychgajfrgua/database/query` with Doppler `SUPABASE_MGMT_TOKEN`?

### BLOCKER 1 preservation

- [ ] **HARD BLOCKER:** Does the audit NEVER write `cancelled_at` or `cancellation_reason` via any path EXCEPT the S169 webhook or S169 `tombstone_extras`? Any new write path to those columns violates the S169 split-ownership architecture (see `memory/s169_supabase_upsert_split_ownership.md`).

### Drift monitor SQL

- [ ] Does `v_sync_drift_monitor` filter through `v_pos_orders_live` (respects the cancelled_at wrapper)?
- [ ] Does it expose per-(store, date) drift rather than a global sum?
- [ ] Is it added to the S169 MV refresh pipeline so it updates hourly with `refresh_sales_dashboard_daily_store_metrics()`?

### Closeout

- [ ] Plan YAML status set to COMPLETED (or COMPLETED_WITH_DEFERRED if the web_orders SoT blocker hits).
- [ ] SPRINT_REGISTRY.md S171 row updated with PR refs.
- [ ] Defect register `output/l3/s171/DEFECT_REGISTER.csv` produced and committed.
- [ ] MEMORY.md lesson written if any new cross-cutting insight emerges.

---

## Autonomous Execution Contract

- **completion_condition:**
  - Full 30-day `pos_orders` parity sweep completed; drift report per (store, date) tuple in `output/l3/s171/pos_orders_drift.json`
  - `pos_order_items` per-order count + product_id set parity completed; drift report in `pos_order_items_drift.json`
  - `pos_order_payments` tender split parity completed; drift report in `pos_order_payments_drift.json`
  - `price_breakdown` field-level reconciliation completed; outliers in `price_breakdown_outliers.json`
  - Channel classification audit completed; mis-classifications (if any) in `channel_classification_audit.json`
  - `web_orders` verify script exists at `scripts/verify_web_orders_sync.py`, AST-parse clean, executed against current data, drift report in `web_orders_drift.json`
  - Cross-channel reconciliation per-store-day in `cross_channel_reconciliation.json`
  - All confirmed-404 phantom IDs from the 30-day window tombstoned via S169 `tombstone_extras`; count + IDs in `phantoms_tombstoned_s171.json`
  - `public.v_sync_drift_monitor` created in Supabase; sample query returns data
  - `output/l3/s171/DEFECT_REGISTER.csv` produced with every HIGH/MED/LOW finding categorized
  - `output/l3/s171/DATA_QUALITY_REPORT.md` produced — executive summary for Sam
  - `verify_s171.py` written and runs all-PASS (22+ checks matching S169 pattern)
  - Plan YAML + SPRINT_REGISTRY.md updated to COMPLETED
  - PR created, evidence committed with `git add -f`
- **stop_only_for:**
  - Mosaic API systemic outage (HTTP 5xx on ALL endpoints for >30 min — distinguishable from per-order transient 5xx)
  - web_orders source-of-truth access unavailable (Phase 0 T0.5 blocker — would block Phase 6 entirely)
  - Supabase Management API rejection (unlikely — same pattern worked throughout S169)
  - Defect count exceeds 10× expected (indicates a different root cause than S169's regime shift — requires Sam's decision on scope)
  - Destructive approval needed (should never happen — S171 is read-mostly; only tombstone UPDATE is mutating and follows S169 path)
- **continue_without_pause_through:** audit → execute → PR creation → L3 → closeout
- **blocker_policy:**
  - programmatic → fix and continue
  - Mosaic API transient error → retry 3× with backoff, record as unconfirmed, continue
  - Per-order 5xx → retry 3×, then log as unconfirmed, continue (do not block the whole sweep)
  - Ambiguous drift finding (can't tell phantom from duplicate) → record both hypotheses in defect register, continue
  - web_orders SoT unavailable → STOP Phase 6 only, complete Phases 1-5 + 7-10, mark Phase 6 as DEFERRED, escalate
- **signoff_authority:** single-owner (Sam)
- **canonical_closeout_artifacts:**
  - `output/l3/s171/DEFECT_REGISTER.csv` (HIGH/MED/LOW categorized, one row per finding)
  - `output/l3/s171/DATA_QUALITY_REPORT.md` (executive summary for Sam)
  - `output/l3/s171/pos_orders_drift.json`
  - `output/l3/s171/pos_order_items_drift.json`
  - `output/l3/s171/pos_order_payments_drift.json`
  - `output/l3/s171/price_breakdown_outliers.json`
  - `output/l3/s171/channel_classification_audit.json`
  - `output/l3/s171/web_orders_drift.json`
  - `output/l3/s171/cross_channel_reconciliation.json`
  - `output/l3/s171/phantoms_tombstoned_s171.json`
  - `output/l3/s171/form_submissions.json`
  - `output/l3/s171/api_mutations.json`
  - `output/l3/s171/state_verification.json`
  - `output/l3/s171/verify_s171.py`
  - `scripts/verify_web_orders_sync.py` (NEW)
  - `scripts/s171_full_parity_audit.py` (NEW — orchestrator)
  - `data/supabase/migrations/2026-04-08-v-sync-drift-monitor.sql` (NEW)
  - `docs/plans/2026-04-08-sprint-171-mosaic-website-sync-full-validation.md` (status → COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (S171 row → COMPLETED)

---

## Sentry Observability

Per `.claude/rules/sentry-observability.md` (DM-7):

- **Backend rule:** NOT APPLICABLE — S171 creates no new `@frappe.whitelist()` endpoints. All work is in Python audit scripts + Supabase SQL.
- **Script-level Sentry:** `scripts/verify_web_orders_sync.py` and `scripts/s171_full_parity_audit.py` SHOULD call `sentry_sdk.init()` with tags `module=sync_verification, action=<script_name>` (mirror `verify_mosaic_pos_sync.py` pattern). Fail-fast on missing DSN per S165 CB5 pattern.

---

## Files to Create

### 1. `scripts/s171_full_parity_audit.py` (NEW, ~400 lines)

Orchestrator that runs Phases 1-5 + 7-8 sequentially and emits drift reports.

**MUST_MODIFY:** `scripts/s171_full_parity_audit.py`
**MUST_CONTAIN:**
- `import sentry_sdk` and `sentry_sdk.init(` (DSN from Doppler)
- `creationflags=0x08000000` (Windows headless rule)
- `from scripts.verify_mosaic_pos_sync import supabase_ids, mosaic_ids, tombstone_extras` (reuse S169 helpers)
- `Accept` header in every Mosaic GET call (BLOCKER: without it, Mosaic returns 500)
- `json={"grant_type": "client_credentials"` (OAuth JSON body, not form)
- `REQUEST_INTERVAL` throttle (reuse from sync_pos_to_supabase)

**MUST_NOT_CONTAIN:**
- `frappe.request.get_json` (not a Frappe endpoint, but safe-list anyway)
- `DELETE FROM pos_orders` or `DELETE FROM pos_order_items` or `DELETE FROM pos_order_payments` or `DELETE FROM web_orders`
- Hardcoded credentials

CLI: `python scripts/s171_full_parity_audit.py [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--tables pos_orders,pos_order_items,pos_order_payments,web_orders] [--tombstone] [--dry-run]`

### 2. `scripts/verify_web_orders_sync.py` (NEW, ~150 lines)

Mirror `verify_mosaic_pos_sync.py` shape, for `web_orders`. Source-of-truth TBD in Phase 0 T0.5.

**MUST_MODIFY:** `scripts/verify_web_orders_sync.py`
**MUST_CONTAIN:**
- `def source_of_truth_count(` or `def fetch_web_order_ids(`
- `def supabase_web_ids(`
- `sentry_sdk.capture_exception`

**MUST_NOT_CONTAIN:**
- `DELETE FROM web_orders`

### 3. `data/supabase/migrations/2026-04-08-v-sync-drift-monitor.sql` (NEW)

Creates `public.v_sync_drift_monitor` — a view joining per-store-day Mosaic expected counts (from `sync_verification.mosaic_total`) against `v_pos_orders_live` counts, exposing drift per tuple.

**MUST_CONTAIN:**
- `CREATE OR REPLACE VIEW public.v_sync_drift_monitor AS`
- `v_pos_orders_live`
- `sync_verification`
- `COMMENT ON VIEW public.v_sync_drift_monitor IS`

### 4. `output/l3/s171/verify_s171.py` (NEW)

Machine-verifiable phase gate. Same shape as S169's verify_s169.py — strips Python comments before MUST_NOT_CONTAIN checks, uses working-tree file existence (not branch-diff) because post-merge diff is empty.

### 5. `output/l3/s171/DEFECT_REGISTER.csv` (NEW)

Columns: `id, severity, table, store_name, business_date, metric, expected, actual, delta, hypothesis, remediation, disposition`

### 6. `output/l3/s171/DATA_QUALITY_REPORT.md` (NEW)

Executive summary for Sam. Format:
- TL;DR (1 paragraph)
- Scope covered
- Findings by severity (HIGH / MED / LOW)
- Actions taken (tombstoned phantoms)
- Deferred to S172 (unresolved defects with remediation options)
- Confidence statement

---

## Files to Modify

### 1. `scripts/verify_mosaic_pos_sync.py` — NO MODIFICATION

Reused as a library (`from scripts.verify_mosaic_pos_sync import ...`). Do NOT edit. If a helper needs a new behavior, add a new wrapper function in `s171_full_parity_audit.py` instead of modifying the S169 script.

**MUST_NOT_MODIFY** assertion in verify_s171.py: `git diff --name-only origin/production..HEAD` MUST NOT include `scripts/verify_mosaic_pos_sync.py`.

---

## L3 Workflow Scenarios

**Note:** S171 is a data-quality audit. "L3" here means end-to-end script runs against production with evidence captured. Scenarios:

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| Builder | Phase 0 T0.5: probe web_orders source-of-truth (`ls bei-tasks/app/api/orders/` + check Supabase for `web_orders` table existence) | Report path(s) to SoT system, confirm Supabase has `web_orders` table with schema | Phase 6 BLOCKED |
| Builder | Run `python scripts/s171_full_parity_audit.py --from 2026-03-09 --to 2026-04-07 --tables pos_orders --dry-run` | Generates `pos_orders_drift.json` with per-(store, date) drift across ~360 tuples | Script errors, rate limit hit, API down |
| Builder | Spot check: a random 5 (store, date) tuples from `pos_orders_drift.json` with drift > 0 — direct-ID lookup each extra ID | Each ID returns HTTP 200 (sync-dup) OR HTTP 404 (phantom) — unambiguous | Mosaic API unavailable for direct lookup |
| Builder | Run `python scripts/s171_full_parity_audit.py --from 2026-03-09 --to 2026-04-07 --tables pos_order_items` | Generates `pos_order_items_drift.json`. For any (store, date) with `pos_orders` drift=0, `pos_order_items` drift should also be 0 | Item count mismatch indicates sync bug beyond order-level |
| Builder | Run payments phase similarly | `pos_order_payments_drift.json` produced | |
| Builder | Run price_breakdown phase — for 50 random orders per store-day, compare Supabase fields vs Mosaic API response | `price_breakdown_outliers.json` lists any order where `abs(supabase_field - mosaic_field) > 0.01` | Rounding drift or truncation bug |
| Builder | Run channel classification audit — group Supabase rows by (service_type_id, service_channel_id, channel) and verify against expected mapping from `_CHANNEL_MAP` in sync_pos_to_supabase.py | `channel_classification_audit.json` shows 0 misclassifications | `_resolve_channel` logic drift |
| Builder | Run Phase 6 web_orders verify script against Supabase + SoT | `web_orders_drift.json` produced with per-store-day delta (or blocked if SoT unavailable) | SoT access gap |
| Builder | Run Phase 7 cross-channel reconciliation — for each store-day, compute `sum(pos_orders where channel='POS') + sum(pos_orders where channel='Delivery') + sum(web_orders)` vs `daily_revenue` MV total | `cross_channel_reconciliation.json` shows per-tuple drift | Channel classification bug, aggregation error, or MV staleness |
| Builder | Phase 8: for every phantom (404-confirmed) from Phase 1, call `tombstone_extras` | `phantoms_tombstoned_s171.json` lists tombstoned IDs with timestamps. Post-tombstone, re-run Phase 1 sweep — drift should drop by the tombstone count | UPDATE failures |
| Builder | Phase 9: apply migration `2026-04-08-v-sync-drift-monitor.sql` via Supabase Mgmt API | Migration returns `[]` (success). `SELECT * FROM v_sync_drift_monitor LIMIT 5` returns rows | SQL syntax error, column mismatch |
| Builder | Phase 10: run `python output/l3/s171/verify_s171.py` | All checks PASS. If any FAIL, fix before claiming closeout | Missing evidence file or MUST_CONTAIN mismatch |
| Builder | Final gate: produce `DATA_QUALITY_REPORT.md` and commit | File exists and is human-readable | |

**L3 Evidence Files Required (committed via `git add -f`):**
- `output/l3/s171/form_submissions.json` — CLI invocations + arguments
- `output/l3/s171/api_mutations.json` — Mosaic + Supabase Mgmt API calls
- `output/l3/s171/state_verification.json` — before/after SQL for drift + tombstones
- `output/l3/s171/pos_orders_drift.json`
- `output/l3/s171/pos_order_items_drift.json`
- `output/l3/s171/pos_order_payments_drift.json`
- `output/l3/s171/price_breakdown_outliers.json`
- `output/l3/s171/channel_classification_audit.json`
- `output/l3/s171/web_orders_drift.json`
- `output/l3/s171/cross_channel_reconciliation.json`
- `output/l3/s171/phantoms_tombstoned_s171.json`
- `output/l3/s171/DEFECT_REGISTER.csv`
- `output/l3/s171/DATA_QUALITY_REPORT.md`
- `output/l3/s171/verify_s171.py`

---

## Zero-Skip Enforcement

Every task in this plan MUST be implemented. The agent is FORBIDDEN from:

- Skipping a phase silently
- Marking partial work as "done"
- Replacing a phase with a simpler version without user approval
- Saying "deferred to S172" without explicit plan amendment
- Sampling fewer store-days than the full 30-day × 12-credential-group universe (unless rate-limit escalation is documented)
- Tombstoning anything that wasn't directly 404-confirmed via round-trip on Mosaic
- Skipping the web_orders phase without escalating the SoT blocker
- Writing any UPDATE that touches `cancelled_at` or `cancellation_reason` outside the S169 `tombstone_extras` code path

**Verification script** (`output/l3/s171/verify_s171.py`):
- Follows S169 pattern: comment-stripping before MUST_NOT_CONTAIN, working-tree existence check instead of branch-diff
- Checks every output file listed in canonical_closeout_artifacts exists and is non-empty
- Checks every MUST_CONTAIN / MUST_NOT_CONTAIN assertion from this plan
- Emits all-PASS or specific failures
- Must be run after each phase; fix any FAIL before proceeding

---

## Phases & Tasks

### Phase 0 — Pre-flight (6 units)

- **T0.1** — Read this plan fully. Read `scripts/verify_mosaic_pos_sync.py` (full, focus on lines 232-737 for reusable helpers), `scripts/sync_pos_to_supabase.py` (focus on lines 280-365 for OAuth + fetch_orders_page), `docs/api/MOSAIC_API.md` (full — 187 lines), `data/POS_Extraction/MOSAIC_POS_API_KEYS.csv` (all rows), S169 plan Design Rationale section.
- **T0.2** — Create sprint branch: `git fetch origin production && git checkout -b s171-mosaic-website-sync-full-validation origin/production`. Verify via `git branch --show-current`. **Note:** this plan was authored in a separate worktree at `F:\Dropbox\Projects\BEI-ERP-s171-plan`. Executing agent should either use that worktree or create its own from current production.
- **T0.3** — Supabase schema inventory: query `information_schema.columns` for all tables in `public` schema matching `pos_%` and `web_%`. Save to `tmp/s171_supabase_schema_inventory.json`. Expected tables: `pos_orders`, `pos_order_items`, `pos_order_payments`, `sync_verification`, `sync_progress`, `v_pos_orders_live`, and `web_orders` (existence to be confirmed). If `web_orders` does NOT exist, T0.5 becomes a HARD BLOCKER for Phase 6.
- **T0.4** — Mosaic API health check: OAuth on 3 different credential groups, call `GET /api/v1/orders?filter[location_id]=<N>&page[size]=1` on each, verify HTTP 200 and order data returned. Save to `tmp/s171_mosaic_health.json`. If ANY credential group fails OAuth or returns 5xx, STOP and investigate (could be Mosaic outage — recall S169 Phase 8 T8.7 false alarm where missing `Accept` header caused false 500s).
- **T0.5** — web_orders source-of-truth probe: identify where the authoritative web order data lives. Options to check in order:
  1. `../bei-tasks/app/api/orders/` — any order log endpoint or database table
  2. Supabase `web_orders` table schema — does it reference an external system ID?
  3. Shopify Admin API (if bebang.ph runs on Shopify)
  4. Next.js internal order log
  Write findings to `tmp/s171_web_orders_sot.md`. **HARD BLOCKER:** if no programmatic source-of-truth is reachable, Phase 6 is BLOCKED. Escalate to Sam with options (a) escalate to the website dev team for a read-only export endpoint, (b) proceed with Phases 1-5 + 7-10 and mark Phase 6 DEFERRED to S172.
- **T0.6** — Credential and rate-limit verification: `doppler secrets get SUPABASE_MGMT_TOKEN --plain --project bei-erp --config dev` must return a valid token; `sentry_sdk` DSN must be present; Mosaic API REQUEST_INTERVAL (from sync_pos_to_supabase.py) must be honored in all S171 scripts.

### Phase 1 — pos_orders 30-day parity sweep (6 units)

- **T1.1** — Calculate date window: `date_from = today - 30 days PHT`, `date_to = yesterday PHT`. Confirm matches S165 "no today" rule (business_date in Mosaic is PHT-local, and today's data is still being written).
- **T1.2** — For each of 12 credential groups, iterate through every store-day in the window. For each (store, date) tuple, call `supabase_ids(location_id, business_date)` (reuse S169 helper — returns set of int IDs with `cancelled_at IS NULL` filter) and `mosaic_ids(cred, location_id, business_date)` (reuse S169 helper). Compute `extras = supabase_ids - mosaic_ids` and `missing = mosaic_ids - supabase_ids`.
- **T1.3** — For each extras ID, do a direct-ID round-trip lookup (`GET /api/v1/orders/{id}` with Accept header). Record 404 as `phantom`, 200 as `duplicate`, 5xx as `unconfirmed_transient`, other as `unconfirmed_other`.
- **T1.4** — Write per-tuple findings to `output/l3/s171/pos_orders_drift.json`. Schema: `[{location_id, location_name, business_date, mosaic_count, supabase_count, extras: [{id, status}], missing: [{id}], phantom_count, duplicate_count, unconfirmed_count}]`.
- **T1.5** — Produce a summary: total phantoms (across all store-days), total duplicates, total missing, total unconfirmed. Compare phantom count against S169's 535 baseline — if >>, flag as regression.

### Phase 2 — pos_order_items parity (8 units)

- **T2.1** — For each store-day from Phase 1 with `drift == 0` (clean at order level), compare `pos_order_items` count per order_id against the `items` length from the Mosaic order response. A mismatch at this level indicates items are missing OR duplicated even when order counts match.
- **T2.2** — Sample 20 random orders per store-day (capped at rate limits — max 20 × 30 days × 3 stores/day = 1800 direct lookups per run). For each, fetch the order via `GET /api/v1/orders/{id}`, compare `items` array against Supabase `pos_order_items WHERE order_id=X`. For each item: verify `product_id`, `product_name`, `quantity`, `price`, `gross_sales` match.
- **T2.3** — Categorize drift: `missing_item` (in Mosaic, not Supabase), `extra_item` (in Supabase, not Mosaic), `field_drift` (present in both but values differ).
- **T2.4** — Write `output/l3/s171/pos_order_items_drift.json`.

### Phase 3 — pos_order_payments parity (6 units)

- **T3.1** — Same sampling shape as Phase 2, but for the `payment_methods` / `payment_details` array in the Mosaic response (the payment split).
- **T3.2** — Compare Supabase `pos_order_payments WHERE order_id=X` against Mosaic payment array. Verify `payment_type`, `paid_amount`, `returned_amount` match within ₱0.01.
- **T3.3** — Write `output/l3/s171/pos_order_payments_drift.json`.

### Phase 4 — price_breakdown field-level reconciliation (6 units)

- **T4.1** — For the same 1800-order sample from Phase 2, compare the top-level `price_breakdown` dict in the Mosaic response against the corresponding Supabase columns: `gross_sales`, `net_sales`, `vatable_sales`, `vat_amount`, `vat_exempt_sales`, `total_discounts`, `delivery_fee`, `zero_rated_sales`.
- **T4.2** — Rounding tolerance: ₱0.01 per field (Mosaic is authoritative for rounding; Supabase should match to 2 decimal places).
- **T4.3** — Any drift >₱0.01 on any field goes to `output/l3/s171/price_breakdown_outliers.json` with full before/after.
- **T4.4** — Also verify internal consistency: `gross_sales = vatable_sales + vat_exempt_sales + zero_rated_sales` and `net_sales = gross_sales - total_discounts` (within rounding). Flag any order violating these invariants.

### Phase 5 — Channel classification audit (4 units)

- **T5.1** — Group Supabase `pos_orders` by `(service_type_id, service_channel_id)` and report distinct tuples with counts. Expected from `_CHANNEL_MAP` in sync_pos_to_supabase.py:
  - `service_type_id=17 or 91` → channel='POS' (QSR Dine-in, Pickup)
  - `service_type_id=3 + service_channel_id=1` → channel='GrabFood'
  - `service_type_id=3 + service_channel_id=2 or 16` → channel='FoodPanda'
  - `service_type_id=3 + service_channel_id=19` → channel='WebDelivery' (EXCLUDE from revenue totals — already in web_orders)
  - `service_type_id=None` → channel='Unknown'
- **T5.2** — Identify any (service_type_id, service_channel_id) tuple that doesn't match the expected mapping. Flag as misclassification.
- **T5.3** — Also verify that no `service_channel_id=19` row contributes to `daily_revenue` or any other revenue MV (plan says these are excluded). Spot-check via SQL join.
- **T5.4** — Write `output/l3/s171/channel_classification_audit.json`.

### Phase 6 — web_orders verify script (7 units — reduced from 10 post-Phase-0 pre-resolution)

**HARD BLOCKER REMOVED:** T0.5 pre-resolved in the Phase 0 Pre-Resolved Findings section. `sync_web_to_supabase.py` already exists and uses `https://superadmin.bebang.ph/api/online-orders` with `x-api-key` auth. Phase 6 scope is now a straightforward port of the S169 verify pattern to the Superadmin API -- not a discovery exercise.

- **T6.1** — Create `scripts/verify_web_orders_sync.py`. Mirror the shape of `scripts/verify_mosaic_pos_sync.py`:
  - `supabase_web_ids(location_id, business_date) -> set[int]`
  - `source_of_truth_ids(location_id, business_date) -> set[int]` (implementation depends on T0.5 outcome)
  - `_process_web_group(location_id, business_date)` — computes drift
  - CLI: `--days N --store X --dry-run --no-chat`
- **T6.2** — Import S169 helpers for Supabase access (`_supabase_query_sql`). Do NOT re-implement.
- **T6.3** — Add `sentry_sdk.init()` with fail-fast DSN check (S165 CB5 pattern).
- **T6.4** — Run against Supabase for the 30-day window. Write drift report to `output/l3/s171/web_orders_drift.json`.
- **T6.5** — If SoT is reachable AND drift exists, categorize: `missing_in_supabase`, `extras_in_supabase` (potential phantoms). Do NOT tombstone web_orders phantoms in S171 (no precedent for web_orders tombstone pattern yet — defer to S172).
- **T6.6** — Add `scripts/verify_web_orders_sync.py` to `daily-pos-sync.yml` workflow as a new step (after the existing verify_mosaic_pos_sync step). New cron run produces nightly `web_orders` drift reports going forward.

### Phase 7 — Cross-channel reconciliation (5 units)

- **T7.1** — For each (store, date) in the window, compute three independent totals:
  - **POS total:** `SELECT SUM(gross_sales) FROM v_pos_orders_live WHERE location_id=X AND business_date=Y AND channel IN ('POS', 'GrabFood', 'FoodPanda')`
  - **Website total:** `SELECT SUM(gross) FROM web_orders WHERE location_id=X AND business_date=Y` (adjust column names to actual schema)
  - **Grand total from daily_revenue MV:** `SELECT SUM(gross_revenue) FROM daily_revenue WHERE location_id=X AND business_date=Y` (should equal POS + Website)
- **T7.2** — Compute `drift = grand_total - (pos_total + website_total)`. Any drift >₱0.01 is flagged.
- **T7.3** — Categorize drift causes: MV staleness (in-progress day), channel misclassification (caught by Phase 5), web_orders SoT disagreement (caught by Phase 6), unknown.
- **T7.4** — Write `output/l3/s171/cross_channel_reconciliation.json`.

### Phase 8 — Tombstone confirmed phantoms (5 units)

- **T8.1** — Collect all `phantom_count > 0` tuples from Phase 1's `pos_orders_drift.json`. For each, collect the IDs that round-trip 404'd.
- **T8.2** — For each phantom ID, call S169's `tombstone_extras` via the Supabase Mgmt API `UPDATE` pattern (reuse from verify_mosaic_pos_sync.py lines 389-500). Do NOT write a new UPDATE path — reuse the S169 helper to preserve split-ownership.
- **T8.3** — Each successful tombstone writes a row to `sync_verification` with `status='extras_tombstoned'` + a note `'S171 full-parity audit tombstone'`.
- **T8.4** — Write `output/l3/s171/phantoms_tombstoned_s171.json` with the list of IDs + before/after counts per store-day.
- **T8.5** — Post-tombstone, re-run `daily_revenue` MV refresh: `SELECT public.refresh_sales_dashboard_daily_store_metrics()`. Verify BI totals drop by the expected amounts.

### Phase 9 — Drift monitor SQL view (4 units)

- **T9.1** — Write `data/supabase/migrations/2026-04-08-v-sync-drift-monitor.sql`:
  ```sql
  CREATE OR REPLACE VIEW public.v_sync_drift_monitor AS
  SELECT
    sv.location_id,
    sv.business_date,
    sv.mosaic_total,
    sv.supabase_total,
    sv.delta,
    sv.status,
    sv.verified_at,
    (SELECT COUNT(*) FROM v_pos_orders_live v
       WHERE v.location_id = sv.location_id AND v.business_date = sv.business_date) AS supabase_live_now,
    sv.mosaic_total - (SELECT COUNT(*) FROM v_pos_orders_live v
       WHERE v.location_id = sv.location_id AND v.business_date = sv.business_date) AS drift_now
  FROM sync_verification sv
  WHERE sv.verified_at >= NOW() - INTERVAL '30 days';
  
  COMMENT ON VIEW public.v_sync_drift_monitor IS
    'S171 drift monitor: per-(store, date) drift between Mosaic count (from sync_verification) and current live Supabase count (from v_pos_orders_live). Refreshes with sync_verification writes. BI can SELECT to find any (store, date) where drift_now != 0. See docs/plans/2026-04-08-sprint-171-mosaic-website-sync-full-validation.md.';
  ```
- **T9.2** — Apply via Supabase Mgmt API. Verify: `SELECT COUNT(*) FROM v_sync_drift_monitor` returns rows.
- **T9.3** — Verify refresh integration: the view is NOT a materialized view, so it updates live with every `sync_verification` insert. Confirm by running `verify_mosaic_pos_sync.py` for one store-day and checking the view reflects the new row.

### Phase 10 — Closeout (5 units)

- **T10.1** — Write `output/l3/s171/DEFECT_REGISTER.csv`. Categorize every finding from Phases 1-7 by severity:
  - **HIGH:** any field_drift > ₱1.00, any duplicate_count > 5 per store-day, any cross-channel drift > ₱10 per store-day, any channel misclassification
  - **MED:** any phantom_count > 0 (minor since we tombstoned), any per-item field drift, any unconfirmed Mosaic lookup
  - **LOW:** rounding drift within expected tolerance, single-order issues
- **T10.2** — Write `output/l3/s171/DATA_QUALITY_REPORT.md`. Executive summary for Sam:
  - TL;DR (1 paragraph answering "is the data correct?")
  - Scope covered (tables, date window, total tuples audited)
  - Findings by severity with counts
  - Actions taken (phantom tombstone count, total ₱ corrected)
  - What couldn't be validated (Phase 6 if deferred) and why
  - Recommendation for S172 remediation priorities
- **T10.3** — Write `output/l3/s171/verify_s171.py` and run it. All checks must PASS.
- **T10.4** — Update plan YAML: `status: COMPLETED` (or `COMPLETED_WITH_DEFERRED` if Phase 6 was blocked). Fill `completed_date`, `backend_pr`, `l3_result`, `execution_summary`.
- **T10.5** — Update `docs/plans/SPRINT_REGISTRY.md` S171 row with PR number and COMPLETED status.
- **T10.6** — Explicit `git add -f` per file (NEVER `git add -A`):
  ```bash
  git add -f \
    scripts/s171_full_parity_audit.py \
    scripts/verify_web_orders_sync.py \
    data/supabase/migrations/2026-04-08-v-sync-drift-monitor.sql \
    output/l3/s171/ \
    docs/plans/2026-04-08-sprint-171-mosaic-website-sync-full-validation.md \
    docs/plans/SPRINT_REGISTRY.md
  ```
- **T10.7** — Create PR via `GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms --base production --head s171-mosaic-website-sync-full-validation --title "S171: Mosaic POS + Website sync full parity validation" --body "..."`. Share PR number with Sam.
- **T10.8** — Write a MEMORY.md lesson ONLY if S171 surfaces a new cross-cutting insight worth preserving. Not required by default.

---

## Execution Workflow

- Test Python changes locally before production runs: use `/local-frappe` if any change needs a Frappe context (none expected in S171; all scripts are standalone).
- Deploy Frappe changes: NOT APPLICABLE — S171 creates no new Frappe code.
- E2E testing: the L3 scenarios above are the E2E.
- Rate limits: every script must honor `REQUEST_INTERVAL` from `sync_pos_to_supabase.py`. Mosaic rate limits ~3 req/sec sustained; burst risks 5xx.

---

## Anti-Rewind / Concurrent-Run Protection Contract

- **Ownership matrix:** This sprint owns exclusively:
  - `scripts/s171_full_parity_audit.py` (NEW)
  - `scripts/verify_web_orders_sync.py` (NEW)
  - `data/supabase/migrations/2026-04-08-v-sync-drift-monitor.sql` (NEW)
  - `output/l3/s171/` directory (NEW)
  - `sync_verification` table — APPEND-ONLY writes via `tombstone_extras` (reuses S169 path, no new writer)
  - `pos_orders.cancelled_at` + `cancellation_reason` — UPDATE via `tombstone_extras` ONLY (reuses S169 path)
  - `public.v_sync_drift_monitor` — NEW view

- **Protected surfaces (DO NOT TOUCH):**
  - `scripts/sync_pos_to_supabase.py` — S169's BLOCKER 1 fix is load-bearing; do not modify
  - `scripts/verify_mosaic_pos_sync.py` — reused as a LIBRARY, not modified; S171's verify_s171.py enforces this with a `git diff --name-only` check
  - `hrms/api/mosaic_webhook.py` — S169's Path B webhook; do not touch
  - `hrms/utils/supabase.py` — S169's helper module; do not touch
  - `v_pos_orders_live` wrapper view — S169's SSOT; do not modify
  - All 13 S169-rewritten views/MVs — S171 reads from them but does not modify
  - `daily-pos-sync.yml` workflow — S171 Phase 6 T6.6 ADDS a step but does not modify existing steps

- **Remote truth baseline:** Record the current `origin/production` HEAD SHA and the S169 closeout commits (PR #485, #487, #488, #490, #492) as the baseline. Phase 10 closeout reintegration check: `git fetch origin production && git log --oneline origin/production..HEAD` must not show any protected-surface modifications.

- **Pre-touch backup:** Before Phase 8 tombstone runs, capture pre-state counts for every (store, date) where tombstone will fire into `output/l3/s171/phase8_pre_state.json`. If anything goes wrong mid-run, the pre-state allows a forensic reconstruction.

---

## Status Reconciliation Contract

Whenever counts, defects, or phase status changes, update in the same work unit:
1. The relevant drift JSON file (`pos_orders_drift.json`, etc.)
2. `DEFECT_REGISTER.csv`
3. `DATA_QUALITY_REPORT.md` (if HIGH severity)
4. Plan YAML status line
5. SPRINT_REGISTRY.md S171 row (on closeout only)

---

## Signoff Model

- **mode:** single-owner
- **approver_of_record:** Sam Karazi (CEO)
- **signoff_artifact:** `output/l3/s171/DATA_QUALITY_REPORT.md` (Sam's explicit approval on this report is the signoff)
- **note:** S171 is a diagnostic sprint. Signoff = Sam acknowledging the findings and deciding which remediations go to S172. Sam does NOT need to approve every individual drift finding — only the report and the remediation roadmap.

---

## Agent Boot Sequence

1. **Read this plan fully.** Do not skip the Design Rationale section — it exists because cold-start agents lose context.
2. **Create sprint branch:** `git fetch origin production && git checkout -b s171-mosaic-website-sync-full-validation origin/production`. Verify via `git branch --show-current`. NEVER write code on production.
3. **Read the reusable S169 helpers:** `scripts/verify_mosaic_pos_sync.py` lines 232-737 (supabase_ids, mosaic_ids, _supabase_query_sql, tombstone_extras). These are the library. S171 imports from them.
4. **Read the Mosaic API call shape:** `scripts/sync_pos_to_supabase.py` lines 280-365 (ensure_token with JSON body, fetch_orders_page with Accept header). Both constraints are load-bearing — S169 Phase 8 T8.7 had a 90-minute false-alarm outage because of missing Accept header.
5. **Read the BEI core governance file if not already loaded:** `.claude/rules/core-governance.md` (data policy, write-first rule, no free-text, etc.).
6. **Read the S169 plan's Design Rationale section** for context on why the wrapper view architecture exists and why split-ownership matters.
7. **Confirm Doppler access:** `doppler secrets get SUPABASE_MGMT_TOKEN --plain --project bei-erp --config dev` returns a non-empty token.
8. **Start Phase 0.** Do not skip ahead.

---

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

---

## PR-Handoff

Per BEI-ERP rules: agent creates PR and STOPS. Sam handles merge and deploy. No agent-side merges.

**Exception (from S169):** Sam previously suspended PR-handoff for S169 specifically to allow autonomous merge + deploy. S171 reverts to the default rule — agent creates PR and stops — unless Sam explicitly suspends it again at execution time.

---

## Worktree Cleanup

This plan was authored in `F:\Dropbox\Projects\BEI-ERP-s171-plan`. If the executing agent uses a different worktree, remove this one after the plan PR merges:

```bash
git worktree remove F:/Dropbox/Projects/BEI-ERP-s171-plan
```

Also pending from S169: `git worktree remove F:/Dropbox/Projects/BEI-ERP-s169-isolated`.
