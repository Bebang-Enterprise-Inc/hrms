---
sprint_id: S232
title: POS Ingest Hardening + Cup Counting Correction
filename: 2026-05-02-sprint-232-pos-ingest-hardening-cup-counting.md
date: 2026-05-02
status: PLANNED
completed_date: null
execution_summary: null

branch: s232-pos-ingest-hardening-cup-counting
secondary_branch: s232-pos-ingest-hardening-cup-counting   # bei-tasks lane
pr: TBD
canonical_scope: none
canonical_scope_rationale: |
  This plan modifies Mosaic POS webhook ingestion + Supabase analytics queries +
  Frappe dashboard frontend. It does NOT touch tabCompany, tabWarehouse, tabCustomer,
  tabSupplier; does NOT create or modify Sales Invoice, Purchase Order, Material
  Request, Stock Entry, Journal Entry, Payment Entry, or GL Entry; does NOT call
  resolve_store_buyer_entity or resolve_warehouse_company. Pure data-ingestion +
  analytics layer.

owner: sam@bebang.ph
signoff_authority: single-owner
estimated_units: 58
phase_count: 7

evidence_committed:
  - output/s232/SUMMARY.md
  - output/s232/DEFECTS.md
  - output/s232/verification/state_before.json
  - output/s232/verification/state_after.json
  - output/s232/verification/dedup_collisions_before.csv
  - output/s232/verification/dedup_collisions_after.csv
  - output/s232/verification/cups_recount_before_after.csv
  - output/s232/l3/form_submissions.json
  - output/s232/l3/api_mutations.json
  - output/s232/l3/state_verification.json
  - output/s232/l3/teardown_ledger.json
  - output/s232/l3/teardown_complete.json

evidence_transient:
  - tmp/s232/sweep_run_*.log
  - tmp/s232/probe_*.json
  - tmp/s232/traceback_*.txt
  - tmp/s232/playwright_trace_*.zip
  - tmp/s232/webhook_replay_*.json
---

# Sprint 232 — POS Ingest Hardening + Cup Counting Correction

## AUDIT v2 STATUS — 13 BLOCKERS RESOLVED INLINE (added 2026-05-02 evening)

This plan was audited 2026-05-02 by 5 parallel domain agents (deployment-qa, frappe-backend, system-arch, cold-start, frontend/design/team) plus an adversarial fact-checker. **13 distinct blockers** identified across 4 clusters. Audit evidence: `output/plan-audit/sprint-232-pos-ingest-hardening-cup-counting/`. Adversarial fact-check verdict: 5/5 highest-stakes blockers SUPPORTED with literal file evidence, 0 hallucinations.

The amendments below are inlined into Phase tables. Cross-reference key:

| ID | Cluster | Resolution location |
|----|---------|---------------------|
| A1 | dedup-broken | Phase 0 task 0.6 (NEW) — backfill BEFORE Phase 1 index creation |
| A2 | dedup-broken | Phase 1 task 1.5 — explicit 409 handling spec |
| A3 | dedup-broken | Phase 1 task 1.5b — webhook REST insert path call sites |
| A4 | dedup-broken | Migration files renumbered 001-007 monotonic (see below) |
| A5 | dedup-broken | Phase 2.2 — `item_name` → `name` (verified column from sync_pos_to_supabase.py:448) |
| B1 | analytics-drift | Phase 5 task 5.5 (NEW) — direct-query patches in discount_abuse + marketing_giveaways |
| B2 | analytics-drift | Phase 5 task 5.0 (NEW) — exhaustive view audit before any view migration ships |
| B3 | analytics-drift | Phase 0 task 0.7 (NEW) — pos_orders_raw scope decision |
| B4 | analytics-drift | Phase 5 task 5.6 (NEW) — pos_order_items + pos_order_payments cascade |
| C1 | verification | Phase 0 task 0.8 (NEW) — `scripts/s232_verify_phase_template.py` shared verifier framework |
| C2 | verification | L3 scenario 8 (NEW) — assert cup recount == 2,941 |
| C3 | verification | L3 scenario 9 (NEW) — cancellation tombstone survives duplicate retry |
| C4 | verification | L3 scenario 10 (NEW) — backfill row-count delta verification |

**Renumbered migration plan (final):**
- `001_bill_number_unique_index.sql` (Phase 1.1)
- `002_webhook_duplicates_table.sql` (Phase 1.2; renamed from `webhook_duplicates` → `pos_duplicates` per H4)
- `003_pos_orders_dedup_fields.sql` (Phase 1.3)
- `004_short_order_id.sql` (Phase 1.5c)
- `005_pos_products.sql` (Phase 2.1)
- `006_pos_order_payments_inferred.sql` (Phase 4.2)
- `007_views_filter_dupes.sql` (Phase 5.2)

**Phase budget after amendments:** Phase 0 grows from 3→9 units (B3, C1, A1 setup). Phase 5 grows from 8→13 units (B1, B2, B4 cascades). Total 58 → 71 units (still under 80 ceiling).

**High-priority items deferred to execution:**
- H5 (multi-terminal `bill_number` scope) → Phase 7.4a — empirical probe at SM Megamall before unique index ships
- H7 (kept-row tie-breaker) → Phase 5.1 clarification: `kept_order_id = MIN(id)` per natural-key tuple
- H8 (`webhook_received_at` NULL backfill) → Phase 5.1 sub-step
- H10 (`/frappe-bulk-edits` mistargeting) → Phase 0.4 — replace with `psql` for Supabase test data

---

## Architecture Correction (added 2026-05-02 after live Supabase probe)

**The original audit interpreted the duplicates as a webhook bug. They are not. The real production architecture is:**

| Path | Status | Volume (last 14 days) |
|------|--------|----------------------:|
| **API poll every 10 minutes** (`scripts/sync_pos_to_supabase.py`) — primary ingestion | ✅ ACTIVE | **138,156 rows** (99.95%) |
| **Webhook for `order.cancelled`** (S169) — tombstones only, doesn't create rows | ✅ ACTIVE | 76 rows (0.05%) tombstone updates |
| **Webhook for `order.completed`** (S189 attempted) | ❌ NOT REGISTERED with Mosaic | 0 rows currently |

Evidence: live Supabase probe `.claude/rlm_state/pos_audit/probe_supabase_dupes.py` (run 2026-05-02). 138,154 of 138,232 rows came via `ingestion_source = 'poll'`. The webhook receiver code at `hrms/api/mosaic_webhook.py:192` exists but isn't wired up at the vendor end — `data/POS_Extraction/MOSAIC_WEBHOOK_REGISTRATIONS.csv` shows all 12 registrations are `order.cancelled` only.

**The duplicates are still real, and they're produced by the API poll.** Live probe found 945 duplicate rows across 137,209 unique `(location_id, business_date, bill_number)` tuples in the last 14 days (0.7% inflation). All of them tagged `ingestion_source = 'poll'`. Sample duplicate cluster at Araneta Gateway 2026-04-23:
```
bill_number 23547 → 6 Mosaic order IDs:
  [51481228, 51481233, 51481234, 51481241, 51481247, 51499274]
  ALL ingestion_source = "poll"
```

**Mechanism:** within a single API pull the response IS deterministic (probe `probe_api_dupes.py` confirmed: 2 pulls 30s apart returned identical 250 IDs at Araneta). But across DIFFERENT pull runs over time, Mosaic re-issues new top-level `id` values for the same physical `bill_number`. Notice the ID gap in the cluster above: 51481247 → 51499274 is ~18,000 IDs apart, ingested hours later. Likely triggers: aggregator re-sync (FoodPanda push), order edit/void/re-ring, or Mosaic-internal reconciliation.

The poll script upserts on `id` (Mosaic Order ID) via `on_conflict=id`. Each new ID becomes a separate row. **The dedup fix needs to live in the poll script's upsert path, NOT the webhook handler.**

**FoodPanda payment_methods coverage (live, 14 days):**
| Channel | Total | With payment row | Missing |
|---------|------:|-----------------:|--------:|
| GrabFood (1) | 21,273 | 20,768 | 505 (2.4%) |
| FoodPanda (2) | 20,465 | 20,100 | 365 (1.8%) |

**98% coverage**, not 1.5%. The audit's 98.5%-missing finding was from a webhook capture (which truly does drop payment_methods). Production poll-based pipeline does NOT have this problem at scale — only ~2% gap which we'll handle as a safety-net inference rather than the primary fix.

## Plan workstream re-targeting (consequence of the architecture correction)

| Workstream | Original direction | Re-targeted direction |
|------------|---------------------|------------------------|
| Phase 1 — Dedup | Modify `hrms/api/mosaic_webhook.py` | **Modify `scripts/sync_pos_to_supabase.py`** + add unique partial index on `pos_orders` (Supabase enforces dedup at write time, regardless of ingestion source). The webhook handler also gets the same dedup helper for the (unused but code-complete) order.completed path, so if S189 ever gets re-registered the bug doesn't return. |
| Phase 2 — Cup classification | unchanged | unchanged |
| Phase 3 — Timestamp standardization | unchanged | unchanged but downgraded — confirm poll script writes PHT-aligned `business_date` correctly (`scripts/sync_pos_to_supabase.py:_map_order_row` is the source of truth) |
| Phase 4 — FoodPanda/Grab payment inference | "Fix 98.5% NULL rate" | **Downgrade to ~2% safety-net.** Inference helper still added (insurance), but not a main blocker. |
| Phase 5 — Historical backfill | unchanged | unchanged — 945 dupes in 14d means several thousand to clean across all history |
| Phase 7 — Vendor outreach | "Two webhook bugs" | **"API ID-instability bug + webhook serializer bug."** API issue is the bigger one for us. |

The total work is similar; the FILE TARGETS shift.

## Pre-Implementation Finding (added 2026-05-02 after live API probe)

**Live Mosaic API probe at Araneta Gateway, SM Megamall, SM North EDSA on 2026-05-01 — actual response, not docs.** Probe scripts: `.claude/rlm_state/pos_audit/probe_mosaic_api.py` and `probe_grab_channels.py`. Full dump: `.claude/rlm_state/pos_audit/mosaic_api_dump_aranetagateway_2026-05-01.json`.

### What Mosaic API IS sending today

**Per-order top-level fields (all 250 Araneta Gateway orders, 2026-05-01):**

| Field | Coverage | Notes |
|-------|---------:|-------|
| `id` | 250/250 | Mosaic Order ID — DIFFERENT on retries (the bug) |
| `bill_number` | 250/250 | Cashier-facing receipt number — STABLE on retries (our natural key) |
| `receipt_number` | 250/250 | Tax receipt number (BIR OR No) |
| `short_order_id` | 43/250 | **Aggregator platform code: `FP-XXXX` for FoodPanda, `GF-XXXX` for GrabFood. NULL for in-store.** |
| `service_channel_id` | 43/250 | `1`=GrabFood, `2`=FoodPanda, `16`=other-aggregator (3 orders), NULL=in-store |
| `service_type_id` | 250/250 | `3` for delivery (aggregator), other for dine-in/takeout |
| `reference_id` | 0/250 | Always NULL — not used here |
| `cancellation_reason` | 0/250 | Tombstone path (S169) |
| `terminal_id` | **0/250 — NOT PRESENT** | Confirmed missing from API response — our outreach must request this |
| `cashier_id` / `device_id` / `external_reference` / etc. | 0/250 — NOT PRESENT | None of these alternative ID fields exist |

**`payment_methods` array on FoodPanda orders (full sample saved to `mosaic_api_sample_channel_service_channel_id_2_2026-05-01.json`):**
```json
"payment_methods": [
  { "payment_type": "FOODPANDA ONLINE", "paid_amount": 714, "returned_amount": 0 }
]
```
**API ALWAYS returns payment_methods (250/250 non-null). The audit found 270 of 274 webhook payloads have NULL payment_methods. This proves the webhook serializer is dropping the field — it is NOT an API-level bug. Their `GET /api/v1/orders/{id}` returns the data correctly.**

**Cross-store probe (SM Megamall, SM North EDSA, 2026-05-01):**

| service_channel_id | Channel | Sample short_order_id | Sample payment_type | Coverage |
|-------------------:|---------|-----------------------|---------------------|----------|
| 1 | **GrabFood** | `GF-521F`, `GF-...` | `GRAB ONLINE` (309/317) | 317 orders observed |
| 2 | **FoodPanda** | `FP-2502`, `FP-2415` | `FOODPANDA ONLINE` (75/75) | 75 orders observed |
| 16 | Other aggregator | none | `Cash` | 3 orders only — likely manual order entry |
| NULL | In-store walk-in | NULL | varies (Cash / MosaicPay QRPH / etc.) | majority |

### What this changes in our plan

1. **Aggregator dedup got even safer.** For aggregator orders we now have TWO independent natural keys: `bill_number` (Mosaic-side) AND `short_order_id` (platform-side, e.g. `FP-2502`). Either one alone is sufficient; matching both is redundant. This is bulletproof.

2. **GrabFood inference is now in scope.** Phase 4 was originally only FoodPanda; expand to also cover `service_channel_id=1 + NULL payment_methods → 'GRAB ONLINE'`. Same code path, two service-channel IDs.

3. **`terminal_id` confirmed missing — outreach justified.** No field in the API response distinguishes which physical POS terminal made the order. For multi-terminal stores this matters if `bill_number` is per-terminal rather than per-store. Outreach must ask Mosaic to confirm scope of bill_number AND add terminal_id to webhook payload.

4. **Webhook bug 2 sharpened.** The vendor message can now say "your webhook serializer drops payment_methods on aggregator orders, but your `GET /api/v1/orders/{id}` returns them correctly — same orders, two endpoints, different payloads." That's a precise, irrefutable bug report.

### Original API doc cross-reference

- `docs/api/MOSAIC_API_OPENAPI_2026-04-14.json` lines 328-329, 387-388, 605-609, 1002-1006 (documents `bill_number`, `receipt_number`)
- Live ingester at `hrms/api/mosaic_webhook.py:405-406` already extracts `bill_number` and `receipt_number`
- Live poll-sync at `scripts/sync_pos_to_supabase.py:386-387` already extracts them
- Supabase `pos_orders` table has both columns; consumed by `hrms/api/discount_abuse.py:1167, 1254-1255`
- **`short_order_id` is NOT yet captured by our ingester** — Phase 1 task adds it

**Implication for the dedup strategy:** the natural key `(location_id, business_date, bill_number)` is deterministic and bulletproof. Each real cashier ring-up gets exactly one `bill_number` from the POS terminal, and a webhook retry of that same transaction carries the SAME `bill_number` even though Mosaic assigns a new top-level `id` (Order ID) on each retry. This eliminates the 1.16% false-positive risk of the cluster-window heuristic and removes the need for a human review queue.

**Revised dedup approach (replaces the original two-tier rule):**
1. **Primary:** unique constraint on `(location_id, business_date, bill_number)` — first writer wins, retries hit a unique-violation and are diverted to `webhook_duplicates`
2. **Fallback:** for the rare order where Mosaic sends NULL `bill_number` (likely test orders, voided pre-bill, or aggregator-only orders), fall back to the cluster-window rule (same `(location_id, business_date, billed_at, original_gross_sales, items_signature)` AND Webhook Timestamp within 60s of an existing twin)

This keeps the sprint scope intact but makes Phase 1 simpler and eliminates the review queue (kept as a safety net for the NULL `bill_number` fallback path only).

**The Mosaic-vendor outreach is still required** — see "Mosaic Vendor Outreach Reminder" at the end of this plan — but the message is no longer "please add OR No to webhook payload" (already there). It is "please stop firing duplicate webhooks with new top-level Order IDs during retries; please stop dropping Payment Methods on FoodPanda payloads."

## Source Audit

This plan executes the fixes identified by the 2026-05-02 forensic audit:
- Audit report: `docs/audits/2026-05-02_pos_vs_analytics_forensic_audit.md`
- Audit workbook: `F:\Downloads\POS_Analytics_Forensic_Audit_2026-05-02.xlsx`
- Source data: `F:\Downloads\POS Sales Checking (Apr 28).xlsx` (BEBANG ARANETA GATEWAY, 2026-04-20 to 2026-04-26, 1,545 Mosaic backend rows vs 1,579 webhook rows)
- Working CSVs: `.claude/rlm_state/pos_audit/{pos_mosaic.csv, webhook.csv, matched_pairs.csv, webhook_duplicates.csv, webhook_items_parsed.csv}`

The audit measured a +17,052 PHP gross sales overage in Frappe DA vs the Mosaic backend report at Araneta Gateway alone. Of that, +15,086 PHP (88%) is from 18 webhook duplicate clusters where Mosaic re-fired the same transaction with new Order IDs during sync-retry bursts. The remaining ~PHP 2K is timing-window residual (Mosaic and webhook captured different moments in the day). Three secondary issues were also confirmed: cup count is bloated by addon/packaging line items, FoodPanda payment method is dropped on 98.5% of webhook payloads, and dashboards may be reading UTC `Billed At` instead of PHT `business_date`.

## Design Rationale (For Cold-Start Agents)

**Why this exists.** On 2026-05-02 the operations team (Edlice, Andrew, Avis) reported that Frappe Data Analytics gross sales for Araneta Gateway did not match the Mosaic POS backend report. Forensic audit found the webhook stream is the source of truth for analytics (`hrms/api/mosaic_webhook.py` writes to Supabase `pos_orders` + `pos_order_items`), but it carries duplicate transactions when the in-store POS retries failed sends. The duplicates have DIFFERENT Mosaic Order IDs (each retry gets a fresh ID at the API level), so the existing PK-on-`id` upsert cannot catch them.

**Why two-tier dedup, not naive key matching.** A naive `(business_date, billed_at, original_gross_sales, items_signature)` collision check has a 1.16% false-positive rate in real data — at multi-terminal stores two real customers can theoretically order identical items at the same second. The discriminator that's bulletproof is the Webhook Timestamp clustering signature: when 5 webhooks arrive within 4 seconds of each other for the same key, they cannot all be different real transactions (the upstream POS cannot fire 5 distinct sales in 4 seconds). The two-tier rule auto-rejects when timestamps cluster tightly, and routes edge cases (timestamps far apart) to a human review queue.

**Why we are NOT doing the Mosaic vendor change.** The deterministic long-term fix is asking the Mosaic vendor to add `OR No` / `Bill No` + `Terminal Id` to the webhook payload — then dedup is just a UNIQUE INDEX. We will request this from the vendor (Phase 7 outreach task) but not block this sprint on it.

**Why `is_cup_drink` flag, not price-based heuristic.** The forensic audit classified items by price >= 150 PHP as cups. That works for current Bebang menu but breaks if future SKUs are added in the 100-150 range or if package deals are introduced. A persistent `is_cup_drink` flag on a Mosaic product lookup table is the durable answer. The classification list is small (~30 unique SKUs across all stores) and changes infrequently.

**Why dashboards must use `business_date`, not `Billed At`.** The Mosaic webhook payload contains both `billed_at` (UTC) and a derived `business_date` (PHT date used for daily reporting). The audit confirmed `business_date` and PHT-aligned timestamps are correct in Supabase `pos_orders`. The risk is in any dashboard that ad-hoc queries the raw webhook fields instead of the canonical `business_date` — those would show transactions on the wrong day during the 8-hour-overlap window. Phase 3 sweeps for those queries.

**Source references for cold-start verification:**
- Webhook ingester: `hrms/api/mosaic_webhook.py:62` (`receive`), `:192` (`_handle_order_completed`), `:457` (`_upsert_completed_order`)
- POS poll fallback: `scripts/sync_pos_to_supabase.py:495` (orders upsert), `:539` (order rows upsert), `:541` (items upsert)
- Sales dashboard: `hrms/api/sales_dashboard.py` (entry: ~line 1; cup query: `grep -n cups_sold hrms/api/sales_dashboard.py`)
- Discount abuse uses pos_original_gross_sales: `hrms/api/discount_abuse.py:2213, 2462, 2531`
- Supabase tables in scope: `pos_orders`, `pos_order_items`, `pos_order_payments`, `pos_orders_raw`
- Frappe DA cron schedule: `.github/workflows/pos-sync-5min.yml` (S197) — runs `*/5 2-16 * * *` UTC
- Webhook URL: `https://hq.bebang.ph/api/method/hrms.api.mosaic_webhook.receive`

## Requirements Regression Checklist

Before declaring any phase done, the executing agent verifies each item against its own work:

- [ ] Did I add a SECONDARY natural-key dedup check in `_upsert_completed_order` (not just rely on PK on `id`)?
- [ ] Is the dedup PRIMARY key `(location_id, business_date, bill_number)` (deterministic, zero false-positive)? **(HARD BLOCKER: don't fall back to the 1.16%-collision cluster-window rule unless `bill_number` is NULL — Mosaic API confirmed sends bill_number on every order per `docs/api/MOSAIC_API_OPENAPI_2026-04-14.json`.)**
- [ ] Did I add the unique partial index `pos_orders_bill_number_natural_key` with `WHERE bill_number IS NOT NULL`?
- [ ] Did I add a `webhook_duplicates` table to capture rejected payloads for audit?
- [ ] Did I keep the cluster-window rule as the FALLBACK path for NULL-bill_number orders only?
- [ ] Did I create or extend a `pos_products` mapping table with `is_cup_drink` flag?
- [ ] Did I rewire `cups_sold` analytics to use the `is_cup_drink` flag, NOT raw `Item Count` and NOT `sum(qty)`?
- [ ] Did I confirm dashboards consume `pos_orders.business_date` (PHT) not raw webhook `billed_at` (UTC)?
- [ ] Did I add the FoodPanda payment inference rule (`Service Channel ID = 2 + NULL Payment Methods` → `FOODPANDA ONLINE`)?
- [ ] Did I run the historical backfill to mark existing duplicates without deleting (`is_duplicate=true` flag)?
- [ ] Did I run the historical cup recount and write before/after to `output/s232/verification/cups_recount_before_after.csv`?
- [ ] Did every new/modified `@frappe.whitelist()` endpoint call `set_backend_observability_context()`?
- [ ] Are `module="pos_ingest"` and `action=<function_name>` correct for the `bei-hrms` Sentry project?
- [ ] Did I create the Vendor Outreach task for the Mosaic OR No / Bill No request?
- [ ] Are all test scenarios in `## L3 Workflow Scenarios` covered by `output/s232/l3/` evidence files?
- [ ] Did I run `cleanupLedger.pendingEntries === 0` assertion in afterEach for every spec?
- [ ] Did I tear down all seeded test data and write `teardown_complete.json`?

## Codebase Context (Cold-Start Reading List)

| File | Lines | Why |
|------|------:|-----|
| `hrms/api/mosaic_webhook.py` | 533 | Receive endpoint, `_handle_order_completed`, `_upsert_completed_order`. PRIMARY MUTATION TARGET. |
| `scripts/sync_pos_to_supabase.py` | 869 | Backfill / poll-based ingestion (REST API pull). Same upsert pattern; secondary dedup target. |
| `hrms/api/sales_dashboard.py` | (entry) | Cup count query, business_date filtering. PRIMARY ANALYTICS TARGET. |
| `hrms/api/discount_abuse.py` | various | Reads `pos_original_gross_sales` — verify it still aggregates correctly post-dedup. |
| `hrms/api/marketing_giveaways.py` | various | Same — verify aggregation. |
| `data/POS_Extraction/MOSAIC_POS_API_KEYS.csv` | 45+ rows | Credentials per credential group; needed to identify FoodPanda Service Channel mapping. |
| `data/POS_Extraction/MOSAIC_WEBHOOK_REGISTRATIONS.csv` | (rows) | Existing webhook registrations, including order.completed (S189) and order.cancelled (S169). |

Already-shipped guardrails this sprint MUST NOT regress:
- S169 `order.cancelled` tombstone path on `pos_orders.cancelled_at` (no UPDATE that overwrites cancellation).
- S171 `public.v_sync_drift_monitor` view (still operational; new `is_duplicate` flag must not break the drift query).
- S189 webhook + S197 5-min poll cadence (do not change crontab or `cancel-in-progress`).
- S200 analytics auto-store-discovery (do not break the 30s TTL cache or store table sync).

## Worktree & Branch

- Repo: hrms (BEI-ERP)
- Branch: `s232-pos-ingest-hardening-cup-counting` (off `origin/production`)
- Worktree: `F:/Dropbox/Projects/BEI-ERP-s232-pos-ingest-hardening-cup-counting`
- Secondary repo: bei-tasks (only if dashboard frontend changes are required after Phase 6 audit)
- Secondary worktree (if used): `F:/Dropbox/Projects/bei-tasks-s232-pos-ingest-hardening-cup-counting`

## Phase Budget Contract (post-audit-v2)

| Phase | Title | Units (v1) | Units (v2 post-audit) | Cap |
|-------|-------|----------:|----------------------:|----:|
| 0 | Worktree + cold-start reads + pre-index setup | 3 | **9** (+6 for A1, A5, B3, C1, H7, H8, H10) | 15 |
| 1 | Bill-number dedup in poll + webhook | 12 | **15** (+3 for A2 409 handling, A3 webhook bypass fix; H1 budget arithmetic correction) | 15 |
| 2 | Cup-vs-addon classification | 12 | 12 | 15 |
| 3 | Timestamp standardization sweep | 5 | 5 | 15 |
| 4 | FoodPanda + GrabFood payment inference | 4 | 4 | 15 |
| 5 | Historical backfill + analytics drift cleanup | 8 | **13** (+5 for B1 direct-queries, B2 view audit, B4 child-table cascade) | 15 |
| 6 | Frontend dashboard reconciliation | 6 | 6 | 15 |
| 7 | L3 + verifier + closeout (incl. multi-terminal probe) | 8 | **9** (+1 for H5 multi-terminal probe) | 15 |
| **Total** | | **58** | **73** | **80** |

Still under the 80-unit ceiling. Hard limit raised from 12 to 15 per phase to absorb the audit amendments without splitting phases (Phases 0, 1, 5 all hit 15). If any phase grows beyond 15 during execution, split it.

## Ground-Truth Lock

**Authoritative sections of this plan:** Phase tables, file paths, the L3 Workflow Scenarios table, the Test Data Seeding Contract, and the Verification Script template. Audit/amendment history (if added later) is traceability only.

**Evidence sources:**
| Source | Proves |
|--------|--------|
| `docs/audits/2026-05-02_pos_vs_analytics_forensic_audit.md` | The 18 duplicate clusters, the 1.16% naive-key collision rate, the 113 non-cup line items |
| `.claude/rlm_state/pos_audit/webhook_duplicates.csv` | Exact list of duplicate clusters with Order IDs |
| `.claude/rlm_state/pos_audit/webhook_items_parsed.csv` | Exact item-level breakdown including cup vs addon vs packaging |
| `hrms/api/mosaic_webhook.py:457` | Current `_upsert_completed_order` shape — what we're extending |
| `git log --oneline scripts/sync_pos_to_supabase.py` | Existing upsert call sites and on_conflict semantics |

**Count method:**
- Metric: webhook duplicate count
- Basis: cluster count (groups of webhook rows sharing `(business_date, billed_at, original_gross_sales, items_signature)`)
- Method: `python scripts/s232_count_dupes.py --window-days 7` (script created in Phase 5)

**Unresolved value policy:** any value the agent cannot ground in a source file is `[UNVERIFIED — requires resolution]`. No best-guess.

## Test Data Seeding Contract

**Required preconditions for L3:**

| Doctype / Table | Key fields | Records needed | Source |
|-----------------|-----------|----------------|--------|
| Supabase `pos_products` (new lookup table) | product_id (PK), name, is_cup_drink, category | ~30 known SKUs from audit + 5 synthetic test SKUs | Seed via `scripts/s232_seed_pos_products.py` |
| Supabase `pos_orders` | location_id, business_date, billed_at, original_gross_sales | 5 synthetic orders with controlled timestamps | Seed via `/frappe-bulk-edits` SUPABASE_INSERT |
| Test webhook payloads | full Mosaic payload JSON | 6 payloads (1 normal, 3 burst-retry copies, 2 review-queue edge cases) | Generated by `scripts/s232_replay_webhook.py` |

**Seeding step (Phase 0 task 0.5):**
```bash
python scripts/s232_seed_pos_products.py --apply
python scripts/s232_seed_test_orders.py --location 9999 --apply  # 9999 = synthetic test store
```

**Teardown step (Phase 7 closeout task):**
```bash
python scripts/s232_teardown.py --apply
# Reads output/s232/l3/teardown_ledger.json (written during seeding)
# Deletes synthetic pos_orders, pos_order_items, pos_order_payments
# Writes output/s232/l3/teardown_complete.json with delete proof
```

Teardown is mandatory whether the L3 passed or failed. Closeout is non-compliant with seeded data left in production.

**HARD BLOCKER:** The synthetic test store ID `9999` MUST NOT collide with any real Mosaic location_id. Phase 0 verifies via `SELECT 1 FROM pos_orders WHERE location_id = 9999` — if it returns rows, pick a different ID and update the plan inline. (Source: S225 test data seeding rule)

## Phase 0 — Worktree + Cold-Start Reads + Pre-Index Setup (9 units)

| # | Task | MUST_MODIFY / MUST_CONTAIN | Units |
|--:|------|----------------------------|------:|
| 0.1 | **Spawn worktree.** Run `cd F:/Dropbox/Projects/BEI-ERP && git fetch origin --prune && git worktree add F:/Dropbox/Projects/BEI-ERP-s232-pos-ingest-hardening-cup-counting -B s232-pos-ingest-hardening-cup-counting origin/production && cd F:/Dropbox/Projects/BEI-ERP-s232-pos-ingest-hardening-cup-counting`. | n/a (env setup) | 1 |
| 0.2 | **Read the audit.** Open `docs/audits/2026-05-02_pos_vs_analytics_forensic_audit.md` end-to-end and `.claude/rlm_state/pos_audit/webhook_duplicates.csv`. | n/a (read-only) | — |
| 0.3 | **Read the ingester.** Open `hrms/api/mosaic_webhook.py` end-to-end. Note: `_upsert_completed_order` at line 457, `_map_order_row` at line 397, `_map_order_items` at line 431. | n/a (read-only) | — |
| 0.3b | **VERIFIED 2026-05-02 (execution):** `pos_order_items` DB column is `product_name` (line 448: `"product_name": item.get("name") or item.get("product_name")`); price column is `unit_price` (line 450). The audit fact-check conflated the Mosaic source field `name` with the actual DB column `product_name`. Phase 2.2 SQL fixed inline below. (Resolves audit blocker A5.) | n/a (verified, complete) | — |
| 0.4 | **Verify synthetic store ID 9999 is free, using `psql` not `/frappe-bulk-edits`.** This is Supabase data, not Frappe. Run `psql "$SUPABASE_PG_URL" -c "SELECT count(*) FROM pos_orders WHERE location_id = 9999"`. Expect 0. If non-zero, pick alternate ID, edit this plan inline before proceeding. (Resolves audit H10.) | output/s232/verification/state_before.json contains `synthetic_store_check: PASS` | 1 |
| 0.5 | **Confirm baseline.** Generate `output/s232/verification/state_before.json` with: row count of `pos_orders`, sum of `original_gross_sales` for last 7 days, count of `pos_order_items` last 7 days, count of NULL `Payment Methods` in last 7 days, current schema of `pos_orders`. | MUST_CONTAIN: `pos_orders_count`, `gross_7d_sum`, `null_payment_count` | 1 |
| 0.6 | **🟥 BACKFILL EXISTING DUPES BEFORE INDEX CREATION (resolves audit blocker A1).** The audit confirmed Phase 1's unique partial index will fail with PG error 23505 because 945 existing duplicates already violate `(location_id, business_date, bill_number)`. Run `scripts/s232_backfill_dupes.py --dry-run` first; capture the dupe count to `output/s232/verification/dedup_collisions_before.csv`. Then run `--apply` to set `is_duplicate=true` and `kept_order_id=MIN(id)` on all duplicate clusters (kept-row tie-breaker = lowest Mosaic id). Phase 1.1's index uses `WHERE bill_number IS NOT NULL AND is_duplicate = false` so post-backfill rows can be uniquely indexed. **This task MUST complete before Phase 1.1 ships.** Resolves H7 (tie-breaker rule), H8 (webhook_received_at NULL backfill — also set `webhook_received_at = paid_at` for historical rows in this pass). | MUST_MODIFY: scripts/s232_backfill_dupes.py, output/s232/verification/dedup_collisions_before.csv; MUST_CONTAIN: `kept_order_id`, `MIN(id)`, `is_duplicate = true`, `webhook_received_at = paid_at` | 4 |
| 0.7 | **🟥 DECIDE pos_orders_raw SCOPE (resolves audit blocker B3).** The poll script writes both `pos_orders_raw` (raw dump, on_conflict=id at line 495) AND `pos_orders` (cleaned). Determine if `pos_orders_raw` is consumed by any analytics or kept for forensics only. Grep `hrms/`, `bei-tasks/`, `scripts/`, Supabase views for `pos_orders_raw` references. Write findings to `output/s232/verification/pos_orders_raw_scope.md`. Decision: (a) extend dedup to `pos_orders_raw` (add unique index + backfill), or (b) document that `pos_orders_raw` is intentionally raw (no dedup, kept for vendor forensics only) and verify zero downstream consumers. Update Phase 1 inline based on decision. | MUST_MODIFY: output/s232/verification/pos_orders_raw_scope.md; MUST_CONTAIN: `pos_orders_raw consumers:` | 1 |
| 0.8 | **🟥 CREATE SHARED VERIFIER TEMPLATE (resolves audit blocker C1).** Phases 2-6 originally lacked verifier code templates — only Phase 1 had one. Create `scripts/s232_verify_phase_template.py` exporting `verify_phase(phase_num, required_files: list[str], required_strings: list[tuple[str,str]], extra_checks: list[Callable]=None)`. Each Phase N's verifier becomes a thin wrapper. Refuse to proceed to Phase N+1 unless Phase N's verifier exits 0. | MUST_MODIFY: scripts/s232_verify_phase_template.py; MUST_CONTAIN: `def verify_phase`, `subprocess.check_output`, `git diff --name-only`, `sys.exit(1)` | 2 |

**Phase 0 verifier (Phase 7 will run all phase verifiers in sequence):**
```python
# scripts/s232_verify_phase0.py
import subprocess, json, sys
required_files = ["output/s232/verification/state_before.json"]
for f in required_files:
    open(f).read()  # raises if missing
state = json.loads(open("output/s232/verification/state_before.json").read())
assert state["synthetic_store_check"] == "PASS", "synthetic store ID collision"
print("PHASE 0 VERIFIER: PASS")
```

## Phase 1 — Bill-Number Dedup in API Poll Script + Webhook Handler (15 units, post-audit)

**Goal:** Add a Supabase-level unique partial index on `(location_id, business_date, bill_number)` so duplicates are rejected at write time regardless of ingestion source. Modify `scripts/sync_pos_to_supabase.py` (the active poll path producing 99.95% of rows) to handle the unique-violation gracefully — record the rejected row to `webhook_duplicates` (table name kept for continuity even though the source is poll) so we keep an audit trail of which IDs were dropped. Also wire the same logic into `hrms/api/mosaic_webhook.py:_upsert_completed_order` so the (currently-unregistered) order.completed webhook is hardened in advance — if S189 webhooks ever get re-registered, the bug doesn't return.

| # | Task | MUST_MODIFY / MUST_CONTAIN | Units |
|--:|------|----------------------------|------:|
| 1.1 | **Add unique partial index on `pos_orders`.** Supabase migration: `CREATE UNIQUE INDEX pos_orders_bill_number_natural_key ON pos_orders (location_id, business_date, bill_number) WHERE bill_number IS NOT NULL AND is_duplicate = false`. **The `AND is_duplicate = false` clause is critical** — it allows the index to ship even after Phase 0.6 backfill has marked existing dupes (which still have their bill_numbers but won't violate the unique constraint because they're flagged). HARD BLOCKER: Phase 0.6 MUST run first; verify by checking `output/s232/verification/dedup_collisions_before.csv` exists and has rows. | MUST_MODIFY: scripts/s232_supabase_migrations/001_bill_number_unique_index.sql; MUST_CONTAIN: `pos_orders_bill_number_natural_key`, `WHERE bill_number IS NOT NULL`, `is_duplicate = false` | 1 |
| 1.2 | **Create `pos_duplicates` table** (renamed from `webhook_duplicates` per audit H4 — 99.95% of dedups are poll-source, not webhook). Captures rejected payloads for audit. Columns: `order_id BIGINT PK, kept_order_id BIGINT, location_id BIGINT, business_date DATE, bill_number INT, source TEXT (poll|webhook), payload JSONB, rejected_at TIMESTAMPTZ, reason TEXT`. | MUST_MODIFY: scripts/s232_supabase_migrations/002_pos_duplicates_table.sql; MUST_CONTAIN: `pos_duplicates`, `kept_order_id`, `source TEXT` | 1 |
| 1.3 | **Add `is_duplicate` column to `pos_orders`.** `is_duplicate BOOLEAN DEFAULT false`. Note: `webhook_received_at` is added/backfilled in Phase 0.6 already (combined with the dedup backfill). | MUST_MODIFY: scripts/s232_supabase_migrations/003_pos_orders_dedup_fields.sql; MUST_CONTAIN: `is_duplicate BOOLEAN DEFAULT false` | 1 |
| 1.4 | **Create dedup helper.** New file `hrms/utils/pos_dedup.py` exposes two functions: (a) `find_bill_number_twin(supabase_client, location_id, business_date, bill_number) -> Optional[int]` returns existing `pos_orders.id` matching the natural key, else None. (b) `find_cluster_twin(supabase_client, location_id, business_date, billed_at, original_gross_sales, items_signature, webhook_received_at, window_seconds=60) -> Optional[int]` for the NULL-bill fallback — same key + Webhook Timestamp within window. Items signature = SHA256 hex of `sorted([(product_id, qty, price) for item in items])`. | MUST_MODIFY: hrms/utils/pos_dedup.py; MUST_CONTAIN: `def find_bill_number_twin`, `def find_cluster_twin`, `sha256`, `window_seconds` | 3 |
| 1.5 | **Wire dedup into `scripts/sync_pos_to_supabase.py` (PRIMARY TARGET — produces 99.95% of rows).** Before the `pos_orders` upsert at `:539`, call `find_bill_number_twin` for each row. Split the batch: rows with no twin → main upsert; rows with twin → `pos_duplicates` table batch insert. **Resolves audit blocker A2 (PostgREST 409 handling):** also wrap the main upsert call in a try/except — if PostgREST returns HTTP 409 (race against the unique index), catch it, parse the error response to extract the conflicting `id`, route the row to `pos_duplicates` with `reason='race_409'`, and continue with the rest of the batch. Do NOT re-raise. The existing `supabase_upsert` helper retries up to MAX_RETRIES on 5xx — extend it to NOT retry on 409 (the conflict won't resolve itself). | MUST_MODIFY: scripts/sync_pos_to_supabase.py; MUST_CONTAIN: `find_bill_number_twin`, `pos_duplicates`, `bill_number`, `409`, `race_409` | 3 |
| 1.5b | **Wire same dedup into `_upsert_completed_order` REST insert path (resolves audit blocker A3).** The webhook handler does NOT use `supabase_upsert` — it has its own direct REST POST at `hrms/api/mosaic_webhook.py:476-490`. Before that POST: call `find_bill_number_twin`. If a twin exists, POST to `pos_duplicates` instead of `pos_orders`. If the POST returns 409 (race), catch and route to `pos_duplicates` with `reason='race_409'`. The order.completed webhook is currently NOT registered with Mosaic vendor (per `MOSAIC_WEBHOOK_REGISTRATIONS.csv`) but if S189 gets re-registered later, the bug must not return. | MUST_MODIFY: hrms/api/mosaic_webhook.py; MUST_CONTAIN: `find_bill_number_twin`, `find_cluster_twin`, `pos_duplicates`, `bill_number is not None`, `bill_number is None`, `status_code == 409` | 2 |
| 1.5c | **Capture `short_order_id` in pos_orders (both paths).** Add column `short_order_id TEXT` to `pos_orders`. Extend `_map_order_row` in `hrms/api/mosaic_webhook.py:397` AND `map_order_row` in `scripts/sync_pos_to_supabase.py` to write `order.get("short_order_id")`. Add a NON-unique B-tree index on `(location_id, short_order_id) WHERE short_order_id IS NOT NULL`. NOT used as a dedup key — captured for traceability and future aggregator reconciliation. | MUST_MODIFY: scripts/s232_supabase_migrations/004_short_order_id.sql, hrms/api/mosaic_webhook.py, scripts/sync_pos_to_supabase.py; MUST_CONTAIN: `short_order_id` | 1 |
| 1.6 | **Sentry instrumentation.** `_handle_order_completed` already runs through `receive()`; add `set_backend_observability_context(module="pos_ingest", action="handle_order_completed", mutation_type="create", extras={"order_id": order_id, "bill_number": bill_number})` at the start of `_handle_order_completed`. | MUST_MODIFY: hrms/api/mosaic_webhook.py; MUST_CONTAIN: `set_backend_observability_context`, `module="pos_ingest"` | 1 |
| 1.7 | **Phase 1 verifier.** `scripts/s232_verify_phase1.py` greps for the strings, parses git diff for files changed, verifies all MUST_CONTAINs are present, AND queries Supabase to confirm the unique index exists. | MUST_MODIFY: scripts/s232_verify_phase1.py; MUST_CONTAIN: `pos_orders_bill_number_natural_key` | 2 |

**Phase 1 verifier template (mandatory):**
```python
# scripts/s232_verify_phase1.py
import subprocess, sys
diff_files = subprocess.check_output(["git","diff","--name-only","origin/production"]).decode().splitlines()
required_files = [
    "scripts/sync_pos_to_supabase.py",  # PRIMARY target - 99.95% of rows
    "hrms/api/mosaic_webhook.py",  # SECONDARY target - future-proofing
    "hrms/utils/pos_dedup.py",
    "scripts/s232_supabase_migrations/001_bill_number_unique_index.sql",
    "scripts/s232_supabase_migrations/002_webhook_duplicates.sql",
    "scripts/s232_supabase_migrations/003_pos_orders_dedup_fields.sql",
]
for f in required_files:
    assert f in diff_files, f"FAIL: {f} not modified"
required_strings = [
    ("hrms/utils/pos_dedup.py", "def find_bill_number_twin"),
    ("hrms/utils/pos_dedup.py", "def find_cluster_twin"),
    ("hrms/utils/pos_dedup.py", "sha256"),
    ("scripts/sync_pos_to_supabase.py", "find_bill_number_twin"),
    ("scripts/sync_pos_to_supabase.py", "webhook_duplicates"),
    ("hrms/api/mosaic_webhook.py", "find_bill_number_twin"),
    ("hrms/api/mosaic_webhook.py", "find_cluster_twin"),
    ("hrms/api/mosaic_webhook.py", "webhook_duplicates"),
    ("hrms/api/mosaic_webhook.py", 'module="pos_ingest"'),
    ("scripts/s232_supabase_migrations/001_bill_number_unique_index.sql", "pos_orders_bill_number_natural_key"),
]
for f, s in required_strings:
    if s not in open(f).read():
        print(f"FAIL: {s!r} not found in {f}")
        sys.exit(1)
print("PHASE 1 VERIFIER: PASS")
```

If verifier fails, do NOT proceed to Phase 2. Fix and re-run.

## Phase 2 — Cup-vs-Addon Classification (12 units)

**Goal:** Add an `is_cup_drink` flag on a Mosaic product lookup table. Rewire `cups_sold` analytics to count only cup drinks. Do NOT trust `Item Count` (under-counts), do NOT trust `sum(qty)` (over-counts by 113 line items in 7-day audit window).

| # | Task | MUST_MODIFY / MUST_CONTAIN | Units |
|--:|------|----------------------------|------:|
| 2.1 | **Create `pos_products` table.** Supabase migration (renumbered to 005 per audit A4): columns `(product_id BIGINT PK, name TEXT, default_price NUMERIC, is_cup_drink BOOLEAN DEFAULT false, category TEXT, first_seen_at TIMESTAMP, last_seen_at TIMESTAMP)`. | MUST_MODIFY: scripts/s232_supabase_migrations/005_pos_products.sql; MUST_CONTAIN: `is_cup_drink`, `category` | 1 |
| 2.2 | **Seed `pos_products` from existing `pos_order_items`.** Script `scripts/s232_seed_pos_products.py` queries `SELECT product_id, product_name, AVG(unit_price) AS default_price FROM pos_order_items WHERE product_id IS NOT NULL GROUP BY product_id, product_name` (Phase 0.3b verified: DB column is `product_name`, not `name` or `item_name`; price column is `unit_price`, not `price`). Initial `is_cup_drink` value: heuristic `default_price >= 150 AND product_name NOT IN (packaging_list)`. After seed, write `output/s232/verification/pos_products_seeded.csv` showing every product with proposed flag. | MUST_MODIFY: scripts/s232_seed_pos_products.py; MUST_CONTAIN: `SELECT product_id, product_name, AVG(unit_price)`, `FROM pos_order_items`, `is_cup_drink`, `packaging_list = (` | 3 |
| 2.3 | **Manual classification override file.** Create `data/POS_Extraction/POS_PRODUCT_CLASSIFICATION.csv` with columns `(product_id, name, is_cup_drink, override_reason)`. Pre-populate from audit findings: confirm Cup 16 oz=0, Bottled Water=0, Insulated Bag=0, Spoon=0, Strawberry Fruit=0, Leche Flan=0, Ube Halaya=0, Macapuno=0, Nata=0, Mais=0, Brown Sugar Ball=0, Mango (topping)=0, Rice Crispies=0, Red Sago=0, Mini Mallows=0, Langka=0. Confirm Presidential=1, Special=1, Buko Bliss=1, So Corny=1, Mango Supreme=1, Melon-ial=1, Uberload=1, Bananarific=1, Brownie Overload=1, Mango Delight=1, Iskrambol=1, Matcharap=1, Fun-dan=1, Berry Good (Strawberry)=1, Berry Good (Blueberry)=1. | MUST_MODIFY: data/POS_Extraction/POS_PRODUCT_CLASSIFICATION.csv; MUST_CONTAIN: `Cup 16 oz,0`, `Insulated Bag,0`, `Bottled Water,0`, `Presidential,1` | 2 |
| 2.4 | **Apply classification overrides.** `scripts/s232_apply_product_classification.py` reads the CSV and UPDATEs `pos_products.is_cup_drink` accordingly. | MUST_MODIFY: scripts/s232_apply_product_classification.py | 1 |
| 2.5 | **Rewire `cups_sold` query.** Find every place in `hrms/api/sales_dashboard.py` that computes cups: replace `SUM(item_count)` or `COUNT(*)` patterns with `SUM(qty) WHERE is_cup_drink = true` via JOIN to `pos_products`. Add a SQL view `v_pos_cups_sold` so other consumers can reuse the canonical metric. | MUST_MODIFY: hrms/api/sales_dashboard.py; MUST_CONTAIN: `is_cup_drink`, `v_pos_cups_sold` | 3 |
| 2.6 | **Sentry instrumentation.** Every modified `@frappe.whitelist()` endpoint in `sales_dashboard.py` calls `set_backend_observability_context(module="sales_dashboard", action="<fn>")`. | MUST_MODIFY: hrms/api/sales_dashboard.py; MUST_CONTAIN: `module="sales_dashboard"` | 1 |
| 2.7 | **Phase 2 verifier.** Same template; verify the cup classification CSV has at minimum 16 rows with `0` and 15 rows with `1`. Confirm `v_pos_cups_sold` view exists in Supabase via probe. | MUST_MODIFY: scripts/s232_verify_phase2.py | 1 |

## Phase 3 — Timestamp Standardization Sweep (5 units)

**Goal:** Confirm every analytics query reads `pos_orders.business_date` (PHT date) and `pos_orders.billed_at` (already converted to PHT during ingest in `_map_order_row`), NEVER raw webhook UTC fields. Ban any new code paths that consume the UTC payload directly.

| # | Task | MUST_MODIFY / MUST_CONTAIN | Units |
|--:|------|----------------------------|------:|
| 3.1 | **Audit all dashboard queries.** Grep `hrms/api/{sales_dashboard.py,discount_abuse.py,marketing_giveaways.py}` for `billed_at`, `paid_at`, `business_date`. Catalogue every read site. Write `output/s232/verification/timestamp_usage_audit.md` listing each call site and whether it reads PHT or UTC. | MUST_MODIFY: output/s232/verification/timestamp_usage_audit.md | 1 |
| 3.2 | **Document `_map_order_row` PHT contract.** Add a docstring comment in `hrms/api/mosaic_webhook.py:_map_order_row` stating: *"All timestamp columns written here are PHT-aligned. Webhook payload `billed_at` (UTC) is converted to PHT via Asia/Manila offset. Downstream readers MUST use these columns and NEVER reach back to the raw payload for time."* | MUST_MODIFY: hrms/api/mosaic_webhook.py; MUST_CONTAIN: `PHT-aligned`, `Asia/Manila` | 1 |
| 3.3 | **Add a PHT timezone test.** New test ensures that for an order with `billed_at = 2026-04-20T03:07:05Z` (UTC), the row written to `pos_orders` has `business_date = 2026-04-20` (PHT date) and `billed_at = 2026-04-20T11:07:05+08:00` (PHT). | MUST_MODIFY: tests/api/test_mosaic_webhook_timestamps.py; MUST_CONTAIN: `2026-04-20T11:07:05` | 2 |
| 3.4 | **Phase 3 verifier.** Confirm audit document exists with at least 3 call site entries; confirm new test exists. | MUST_MODIFY: scripts/s232_verify_phase3.py | 1 |

## Phase 4 — Aggregator Payment Inference (FoodPanda + GrabFood) (4 units)

**Goal:** When the webhook arrives with an aggregator `service_channel_id` AND `payment_methods` is NULL, synthesize the platform-correct `payment_type`. Live API probe (2026-05-01, SM Megamall + Araneta Gateway) confirms `service_channel_id=1` is GrabFood (97.5% have `GRAB ONLINE`) and `service_channel_id=2` is FoodPanda (100% have `FOODPANDA ONLINE`). Audit found webhook serializer drops payment_methods 98.5% of the time even though API returns it correctly.

| # | Task | MUST_MODIFY / MUST_CONTAIN | Units |
|--:|------|----------------------------|------:|
| 4.1 | **Implement inference in payment mapping.** Centralize the rule in a small helper: `infer_payment_type(service_channel_id) -> Optional[str]` returning `"FOODPANDA ONLINE"` for 2, `"GRAB ONLINE"` for 1, else None. When mapping payments: if `payment_methods` array is empty AND `infer_payment_type` returns a value, synthesize a single payment `{payment_type: <inferred>, line_number: 0, amount: original_gross_sales, inferred: true}`. | MUST_MODIFY: hrms/api/mosaic_webhook.py; MUST_CONTAIN: `infer_payment_type`, `service_channel_id == 1`, `service_channel_id == 2`, `FOODPANDA ONLINE`, `GRAB ONLINE`, `inferred` | 2 |
| 4.2 | **Add `inferred` column to `pos_order_payments`.** Supabase migration (renumbered to 006 per audit A4). Backfill: every existing row gets `inferred = false`. | MUST_MODIFY: scripts/s232_supabase_migrations/006_pos_order_payments_inferred.sql; MUST_CONTAIN: `inferred` | 1 |
| 4.3 | **Phase 4 verifier.** Replay synthetic FoodPanda AND GrabFood webhooks with empty payments. Confirm rows appear in `pos_order_payments` with correct `payment_type` and `inferred=true`. | MUST_MODIFY: scripts/s232_verify_phase4.py; MUST_CONTAIN: `FOODPANDA ONLINE`, `GRAB ONLINE` | 1 |

## Phase 5 — Historical Backfill + Analytics-Drift Cleanup (13 units)

**Goal:** Mark existing duplicates in `pos_orders` (do NOT delete — preserve audit trail), cascade the dedup flag to child tables (audit B4), exhaustively cover all views (audit B2), patch direct-query reads (audit B1), and recompute cups_sold metrics. **Note:** the "mark duplicates" sub-task moved to Phase 0.6 (per audit A1) so it runs BEFORE the unique index ships. Phase 5 here covers the cascade work + analytics cleanup.

| # | Task | MUST_MODIFY / MUST_CONTAIN | Units |
|--:|------|----------------------------|------:|
| 5.0 | **🟥 EXHAUSTIVE VIEW AUDIT (resolves audit blocker B2).** Before writing any view-filter migration, identify every Supabase view that reads `pos_orders` directly (not through another view). Run `psql "$SUPABASE_PG_URL" -c "SELECT viewname, definition FROM pg_views WHERE definition LIKE '%pos_orders%'"`, plus grep `hrms/`, `bei-tasks/`, `scripts/` for any code-side view CREATE statements. Write findings to `output/s232/verification/views_using_pos_orders.md`. The migration in 5.2 must cover EVERY view found here. | MUST_MODIFY: output/s232/verification/views_using_pos_orders.md; MUST_CONTAIN: `pg_views`, `viewname` | 2 |
| 5.1 | **Verify Phase 0.6 backfill outcome** (the actual marking ran in Phase 0.6 per audit A1 reorder). Read `output/s232/verification/dedup_collisions_before.csv`, query Supabase to confirm `is_duplicate=true` count matches the expected ~945 rows. Write `output/s232/verification/dedup_collisions_after.csv`. If counts don't match, STOP — the backfill was incomplete and Phase 1.1's index ship will fail. | MUST_MODIFY: output/s232/verification/dedup_collisions_after.csv; MUST_CONTAIN: `is_duplicate_count`, `match` | 1 |
| 5.2 | **🟥 Update ALL analytics views with `WHERE is_duplicate IS NOT TRUE` filter (resolves audit B2).** Migration `007_views_filter_dupes.sql` (renumbered per audit A4). Must cover every view from Phase 5.0's exhaustive audit, not just `v_sync_drift_monitor`. Confirm gross sales total drops by ~PHP 15K for Araneta Gateway 2026-04-20 to 2026-04-26. | MUST_MODIFY: scripts/s232_supabase_migrations/007_views_filter_dupes.sql; MUST_CONTAIN: `is_duplicate IS NOT TRUE`, every view name from views_using_pos_orders.md | 2 |
| 5.3 | **Cup count recount.** `scripts/s232_recount_cups.py` recomputes total cups for last 90 days using the new `is_cup_drink` filter AND `is_duplicate IS NOT TRUE`. Writes `output/s232/verification/cups_recount_before_after.csv` with columns `(business_date, location_id, cups_old_method, cups_new_method, delta)`. | MUST_MODIFY: scripts/s232_recount_cups.py; MUST_CONTAIN: `cups_old_method`, `cups_new_method`, `is_cup_drink`, `is_duplicate IS NOT TRUE` | 2 |
| 5.5 | **🟥 PATCH DIRECT-QUERY ANALYTICS (resolves audit blocker B1).** Two HRMS modules read `pos_orders` directly via PostgREST, bypassing views. They will silently double-count duplicate-flagged rows after dedup ships unless patched: (a) `hrms/api/discount_abuse.py:1175` calls `_supabase_get_all("pos_orders", params)` — modify the params construction (~line 1167) to append `&is_duplicate=is.false`. (b) `hrms/api/marketing_giveaways.py:1009-1015` calls `_supabase_get("pos_orders", params)` — same fix. Verify by re-running the audit's gross-sales query post-patch and confirming the +PHP 15K overage is gone. | MUST_MODIFY: hrms/api/discount_abuse.py, hrms/api/marketing_giveaways.py; MUST_CONTAIN: `is_duplicate=is.false`, `is_duplicate%3Dis.false` (URL-encoded variant if needed) | 2 |
| 5.6 | **🟥 CASCADE DEDUP TO CHILD TABLES (resolves audit blocker B4).** When 6 duplicate parents land in `pos_orders`, their items+payments insert into `pos_order_items` (945 cluster × ~3 items avg = ~2,800 orphan item rows) and `pos_order_payments`. Mark them `is_duplicate=true` too: (a) Add `is_duplicate BOOLEAN DEFAULT false` to both child tables. (b) `UPDATE pos_order_items SET is_duplicate=true WHERE order_id IN (SELECT id FROM pos_orders WHERE is_duplicate=true)`. (c) Same for `pos_order_payments`. (d) Update views in 5.2 to also filter child tables. **Do NOT delete** — preserve audit trail. | MUST_MODIFY: scripts/s232_supabase_migrations/008_cascade_is_duplicate_to_children.sql; MUST_CONTAIN: `pos_order_items`, `pos_order_payments`, `is_duplicate BOOLEAN DEFAULT false`, `WHERE order_id IN (SELECT id FROM pos_orders WHERE is_duplicate=true)` | 3 |
| 5.7 | **Phase 5 verifier.** Confirm: (a) all verification CSVs exist + non-empty; (b) `views_using_pos_orders.md` lists ≥3 views; (c) Phase 5.5's grep of `is_duplicate=is.false` in discount_abuse.py and marketing_giveaways.py returns hits; (d) Phase 5.6's child-table updates are in the migration. | MUST_MODIFY: scripts/s232_verify_phase5.py; MUST_CONTAIN: `is_duplicate=is.false`, `pos_order_items`, `pos_order_payments` | 1 |

**HARD BLOCKER:** This phase NEVER deletes rows from `pos_orders` or `pos_order_items`. The `is_duplicate=true` flag is the ONLY mutation. (Source: 2026-04-21 evidence-preservation rule + S087 anti-rewind protection.)

## Phase 6 — Frontend Dashboard Reconciliation (6 units)

**Goal:** If any bei-tasks dashboard query is reading raw cups (Item Count or sum of qty), update it to use the new `v_pos_cups_sold` view OR call the new backend endpoint. Drop in a `[updated]` badge so users know the metric changed.

| # | Task | MUST_MODIFY / MUST_CONTAIN | Units |
|--:|------|----------------------------|------:|
| 6.1 | **Audit bei-tasks queries.** From the bei-tasks worktree, grep for `cups_sold`, `item_count`, `cups`. Write `output/s232/verification/bei_tasks_cup_query_audit.md`. | MUST_MODIFY: output/s232/verification/bei_tasks_cup_query_audit.md | 1 |
| 6.2 | **Update queries.** If audit finds direct Supabase queries reading raw cups: route them through the backend endpoint or `v_pos_cups_sold` view. If audit finds zero direct queries (all already go through `hrms/api/sales_dashboard.py`): mark this task as N/A with explanation in PR description. | MUST_MODIFY: (TBD per audit — e.g. `bei-tasks/lib/queries/cups.ts`) — IF audit flags any | 3 |
| 6.3 | **Add metric-change badge.** On the Sales Dashboard "Cups Sold" tile, render a small "Methodology updated 2026-05-02" tooltip. | MUST_MODIFY: bei-tasks dashboard component (TBD per audit); MUST_CONTAIN: `Methodology updated 2026-05-02` | 1 |
| 6.4 | **Phase 6 verifier.** | MUST_MODIFY: scripts/s232_verify_phase6.py | 1 |

If Phase 6.1 audit shows zero direct queries (everything routes through HRMS API), the bei-tasks lane is unnecessary; mark Phase 6 as N/A and update the secondary_branch reservation in registry to "not used".

## Phase 7 — L3 + Verifier + Closeout + Multi-Terminal Probe (9 units, post-audit)

| # | Task | MUST_MODIFY / MUST_CONTAIN | Units |
|--:|------|----------------------------|------:|
| 7.1 | **Run all phase verifiers.** `python scripts/s232_verify_all_phases.py` runs Phase 0-6 verifiers in order. Any FAIL halts here. | MUST_MODIFY: scripts/s232_verify_all_phases.py | 1 |
| 7.2 | **L3 scenarios.** Execute every row in `## L3 Workflow Scenarios` below. For each, capture form_submissions / api_mutations / state_verification entries. | MUST_MODIFY: output/s232/l3/{form_submissions.json, api_mutations.json, state_verification.json} | 3 |
| 7.3 | **Teardown seeded data.** `python scripts/s232_teardown.py --apply`. Writes `output/s232/l3/teardown_complete.json`. | MUST_MODIFY: output/s232/l3/teardown_complete.json | 1 |
| 7.4 | **Vendor outreach task.** Email Mosaic vendor support with the OR No / Bill No / Terminal Id webhook payload request. Save email draft + sent confirmation under `output/s232/vendor_outreach/`. (Doesn't block sprint closeout — just creates the artifact for follow-up.) | MUST_MODIFY: output/s232/vendor_outreach/2026-05-02_OR_No_Request.md | 1 |
| 7.4a | **🟥 MULTI-TERMINAL `bill_number` SCOPE PROBE (resolves audit H5).** Pick a known multi-terminal store (SM Megamall, Mosaic Location ID 2338). Pull `GET /api/v1/orders` for one full business day. Group by `(business_date, bill_number)` — count any duplicates. If `bill_number` is per-terminal-per-store, multi-terminal stores will show duplicate bill_numbers in a single day. If found, **HARD STOP and revisit Phase 1.1 — the unique index would over-deduplicate at multi-terminal stores**. If zero collisions found at SM Megamall on a real business day, the unique index is safe to ship as-is. | MUST_MODIFY: output/s232/verification/multi_terminal_bill_number_probe.json; MUST_CONTAIN: `multi_terminal_collision_count` | 1 |
| 7.5 | **Closeout artifacts.** Update plan YAML `status: COMPLETED`, `completed_date: <today>`, `execution_summary`. Update SPRINT_REGISTRY.md row to COMPLETED with PR link. Commit + push (`git add -f docs/plans/...`). | MUST_MODIFY: docs/plans/2026-05-02-sprint-232-pos-ingest-hardening-cup-counting.md, docs/plans/SPRINT_REGISTRY.md | 1 |
| 7.6 | **Worktree closeout.** `cd F:/Dropbox/Projects/BEI-ERP && git worktree remove F:/Dropbox/Projects/BEI-ERP-s232-pos-ingest-hardening-cup-counting`. | n/a (env teardown) | 1 |

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| n/a (script) | `scripts/s232_replay_webhook.py --scenario normal` posts a single fresh order to `https://hq.bebang.ph/api/method/hrms.api.mosaic_webhook.receive` | New row in `pos_orders` with `is_duplicate IS NOT TRUE`; matching items in `pos_order_items` | Webhook ingestion regressed |
| n/a (script) | `scripts/s232_replay_poll.py --scenario id-drift` simulates 6 successive poll runs that return the SAME `bill_number=99001` with different top-level Mosaic IDs (matches the live Araneta 2026-04-23 cluster pattern). | First poll-run → `pos_orders` accepted. Poll runs 2-6 → `webhook_duplicates` table with `kept_order_id=<run 1's id>`; NO new rows in `pos_orders`. The unique partial index on `(location_id, business_date, bill_number)` is what enforces this at the DB level. | Bill-number dedup not catching the actual production bug |
| n/a (script) | `scripts/s232_replay_poll.py --scenario null-bill` simulates a poll-run where 3 orders have `bill_number=NULL` (aggregator case observed in some service_channel_id=16 orders) | All 3 accepted (partial unique index excludes NULLs). Cluster-window fallback in helper still flags them if their (billed_at, gross, items) match within 60s — for traceability. | Fallback path broken |
| n/a (script) | `scripts/s232_replay_poll.py --scenario two-real-customers` simulates a poll-run with 2 orders, DIFFERENT `bill_number` (99003 and 99004) but same items + same gross + same second | BOTH accepted. NEITHER goes to `webhook_duplicates`. False-positive test — bill_number-based dedup must not over-match. | Dedup is over-aggressive — would have dropped a real customer |
| n/a (script) | `scripts/s232_replay_webhook.py --scenario burst-retry` posts 5 webhooks with same `bill_number=99005` (future-proofing path — webhook is currently NOT registered for order.completed, but if S189 gets re-registered the bug must not return) | Same as poll path: first accepted, rest go to `pos_duplicates`. | Webhook handler dedup not future-proofed |
| n/a (script) | **🟥 SCENARIO 8 (resolves audit C2): cup-recount-2941.** `scripts/s232_replay_poll.py --scenario cup-recount-2941` runs the recount on Araneta Gateway 2026-04-20 to 2026-04-26 window post-Phase-2 + post-Phase-5. Asserts `total_cup_drinks == 2941` (the audit's true count). | Exact match 2,941 cups. Test FAILS the sprint if drift. | Cup classification or dedup is wrong |
| n/a (script) | **🟥 SCENARIO 9 (resolves audit C3): cancellation tombstone survives duplicate retry.** Insert a `pos_orders` row with `cancelled_at` set via S169 path, then replay a poll/webhook with the same `(location_id, business_date, bill_number)` and a new `id`. | New payload routed to `pos_duplicates` (not `pos_orders`), `cancelled_at` on the original row is unchanged, the cancellation timestamp survives. Analytics show order as cancelled. | Tombstone interaction with dedup is broken |
| n/a (script) | **🟥 SCENARIO 10 (resolves audit C4): backfill row-count delta verification.** Run `SELECT COUNT(*) FROM pos_orders WHERE is_duplicate=true GROUP BY business_date` after Phase 0.6 backfill. Compare to expected counts from `output/s232/verification/dedup_collisions_before.csv`. | Per-day counts match within ±0 tolerance (deterministic; this is just a "did the backfill run" check). | Phase 0.6 backfill incomplete or off |
| sam@bebang.ph | Open Sales Dashboard → Araneta Gateway → 2026-04-20 to 2026-04-26 (after Phase 5 ships) | Gross sales total = pre-dedup PHP 665,910 minus PHP 15,086 dedup correction = **~PHP 650,824**. Cups display shows 2,941. | Phase 5 view filter or direct-query patch (5.5) is broken — drift persists |
| n/a (script) | `scripts/s232_replay_webhook.py --scenario foodpanda-no-payment` posts a `service_channel_id=2` webhook with empty payments array, `short_order_id="FP-9999"` | `pos_order_payments` row appears with `payment_type='FOODPANDA ONLINE'` and `inferred=true`. `pos_orders.short_order_id` = "FP-9999". | FoodPanda inference broken |
| n/a (script) | `scripts/s232_replay_webhook.py --scenario grabfood-no-payment` posts a `service_channel_id=1` webhook with empty payments array, `short_order_id="GF-AAAA"` | `pos_order_payments` row appears with `payment_type='GRAB ONLINE'` and `inferred=true`. `pos_orders.short_order_id` = "GF-AAAA". | GrabFood inference broken (this scenario didn't exist before live probe found GF channel) |
| n/a (script) | `scripts/s232_replay_webhook.py --scenario mixed-cart` posts an order with 1 Presidential + 1 Leche Flan + 1 Cup 16 oz | `pos_order_items` shows 3 line items. Query of `v_pos_cups_sold` returns 1 cup (only Presidential), NOT 3 | Cup classification not honored |
| sam@bebang.ph | Open Sales Dashboard → Araneta Gateway → 2026-04-20 to 2026-04-26 | Gross sales display reflects post-dedup total (~PHP 633K, NOT the pre-dedup PHP 665K). Cups display shows ~2,941 (NOT 3,054 or 2,334) | Dashboard not consuming new view |
| sam@bebang.ph | Open Sales Dashboard → Araneta Gateway → hover the "Cups Sold" tile | Tooltip says "Methodology updated 2026-05-02" | Phase 6.3 not applied |

## Failure Response

This is not a typical UI test plan — most scenarios are scripted webhook replays — but the same three-mode discipline applies:

- **Mode A (app bug):** L3 scenario fails because the ingester behaves wrong (e.g. burst-retry copies are still being inserted). File `[BUG]` and fix the ingester. Do NOT change the test scenario thresholds to make the test pass.
- **Mode B (test bug):** L3 scenario fails because the replay script generated bad payload. Fix the script.
- **Mode C (flakiness):** Webhook arrived but `pos_orders` row not yet visible to verifier (Supabase replication lag). Add an explicit `wait_for_row_visible(order_id, timeout=10s)` helper to the L3 verifier. Do NOT add `time.sleep()`.

If 3+ library fixes happen during execution → emit `output/s232/LIBRARY_IMPROVEMENTS.md`.

## Anti-Rewind / Concurrent-Run Protection

| Surface | Owner | Notes |
|---------|-------|-------|
| `hrms/api/mosaic_webhook.py` | S232 | Sole owner this sprint. S169/S189 already shipped — preserve their handlers. |
| `hrms/api/sales_dashboard.py` | S232 | Cup count rewire only. Do NOT touch S227 store-partner response stripping or S176 IA. |
| Supabase `pos_orders`, `pos_order_items`, `pos_order_payments` | S232 (additive only) | New columns OK; do NOT drop S189/S171/S169 columns. |
| `pos_products` (new table) | S232 | New surface. |
| `webhook_duplicates`, `webhook_review_queue` (new tables) | S232 | New surfaces. |

Protected surfaces (must remain untouched unless explicitly in scope):
- S169 cancellation tombstone path (`hrms/api/mosaic_webhook.py:_handle_order_cancelled`) — Phase 5 cascade MUST preserve `cancelled_at` on duplicates (verified by L3 scenario 9)
- S171 `v_sync_drift_monitor` view (S232 may add `WHERE is_duplicate IS NOT TRUE` filter, must NOT change drift semantics)
- S189 webhook URL (currently registered for `order.cancelled` only; future-proofed in Phase 1.5b for `order.completed` if re-registered)
- **S197 actual poll cadence:** `*/10 2-16 * * *` (10-minute interval — file is named `pos-sync-5min.yml` but the cron is */10; do NOT change either) — H2 audit correction
- S200 store auto-discovery 30s TTL cache (independent of dedup)
- S227 store-partner response shaping in `sales_dashboard.py` — Phase 2.5 cup-query rewire MUST preserve the `copy.deepcopy()` response-stripping for Store Partner role

**Removed from previous version (audit H3):** `webhook_review_queue` was listed as a new surface in v1 but no phase actually creates it. The two-tier dedup approach was simplified per the bill_number-based natural-key design (no review queue needed since bill_number match is deterministic). Removed.

Remote truth baseline: `output/s232/SXXX_REMOTE_TRUTH_BASELINE.json` captures `origin/production` HEAD of hrms + bei-tasks at Phase 0 start. Phase 7 closeout re-fetches and verifies no protected files moved upstream during execution.

## Autonomous Execution Contract

- **completion_condition:** all 7 phases green; all phase verifiers PASS; all L3 evidence files non-empty; `teardown_complete.json` shows zero seeded data remaining; plan + registry pushed; PR created and shared with Sam.
- **stop_only_for:**
  - Mosaic vendor support requires CEO sign-off on outreach email content
  - destructive backfill that would touch >10K rows (escalate before applying)
  - synthetic store ID 9999 collision discovered in Phase 0.4
  - 3 consecutive technical failures of the same kind on the same Phase 1 dedup test
- **continue_without_pause_through:** audit → execute → PR creation → L3 → closeout
- **blocker_policy:**
  - programmatic → fix and continue
  - Supabase migration error → re-read schema + retry; if still failing after 2 attempts → debug
  - business decision → pause
- **signoff_authority:** single-owner (Sam)
- **canonical_closeout_artifacts:** all under `output/s232/` per `evidence_committed`

## Status Reconciliation Contract

When status, counts, or blockers change, update in the same work unit:
1. `output/s232/SUMMARY.md`
2. `output/s232/DEFECTS.md`
3. plan YAML status line
4. `docs/plans/SPRINT_REGISTRY.md` row

## Signoff Model

- mode: single-owner
- approver_of_record: Sam Karazi (CEO)
- signoff_artifact: PR description + plan YAML `status: COMPLETED`

## Scope Size Warning

This plan is 58 units (under the 80 ceiling) but spans both backend and frontend lanes. Phase 6 (frontend) may turn out to be N/A after Phase 6.1 audit — in that case, the effective work is 52 units and easily fits a single agent session. If Phase 6 is needed AND any of Phases 1, 2, 5 expand beyond budget during execution: split into S232a (backend) and S232b (frontend) per the splitting rule.

## Zero-Skip Enforcement

- Every task above MUST be implemented. No silent skipping.
- If a task cannot be completed, the agent STOPS and asks Sam.
- After each phase, write the verifier output to `output/s232/verification/phase_<N>_verifier.txt`.
- Forbidden: marking partial work as DONE; replacing a task with a simpler version; deferring to a future sprint without Sam approval; combining tasks and dropping features in the merge; implementing happy path only; commenting out failing assertions to make tests pass.

## Execution Workflow

- Test Python changes locally: `/local-frappe`
- Deploy to production: `/deploy-frappe` (after PR review + merge)
- Full workflow shorthand: `/agent-kickoff`
- E2E: `/e2e-test` or `/test-full-cycle`

PR-handoff: this sprint creates the PR and stops. Sam handles merge + deploy.

## Agent Boot Sequence

1. Read this plan in full.
2. Spawn worktree (Phase 0.1) — never work in the main checkout.
3. Read `docs/audits/2026-05-02_pos_vs_analytics_forensic_audit.md` and `.claude/rlm_state/pos_audit/webhook_duplicates.csv` end-to-end.
4. Read `hrms/api/mosaic_webhook.py` end-to-end.
5. Confirm synthetic store ID 9999 is free (Phase 0.4).
6. Begin Phase 1 (no preliminary "exploration" phase — the audit already did the exploration).

## Execution Authority

This sprint is intended for autonomous end-to-end execution. The agent does not stop for progress-only updates. The agent stops only for items in the Autonomous Execution Contract `stop_only_for` list.

---

## ⚠️ MOSAIC VENDOR OUTREACH REMINDER (Sam — DO THIS) ⚠️

**Status: pending — must be sent by Sam after this sprint ships.**

Our forensic audit (2026-05-02, Araneta Gateway, 7-day window) and Mosaic's own OpenAPI spec (`docs/api/MOSAIC_API_OPENAPI_2026-04-14.json`) prove that the bugs below are on **Mosaic's side**, not ours. We are paying them and they are shipping us garbage data. Phase 1-7 of this sprint is the workaround we have to build because their API misbehaves. Send the message below to escalate so the workaround eventually becomes obsolete.

### What to ask Mosaic to fix

| # | Bug we observed | Evidence | Why it's their bug |
|---|-----------------|----------|---------------------|
| 1 | **Mosaic API re-issues new top-level `id` values for the same physical `bill_number` across time.** Live Supabase probe 2026-05-02: 945 duplicate rows across 137,209 unique (location_id, business_date, bill_number) tuples in last 14 days (0.7% inflation rate, all from the API `GET /api/v1/orders` poll). Worst case: bill_number 23547 at Araneta Gateway 2026-04-23 has 6 distinct Mosaic IDs spanning ID range 51481228 to 51499274 (~18,000 IDs apart, ingested across hours). Verified within-pull determinism: 2 consecutive pulls 30s apart returned identical 250 IDs (no race condition in our poll). The drift only happens BETWEEN poll runs — Mosaic regenerates IDs for the same physical bill across time. | `.claude/rlm_state/pos_audit/probe_supabase_dupes.py` output; `.claude/rlm_state/pos_audit/api_dupe_probe.json` (within-pull determinism proof); audit `webhook_duplicates.csv` (originally interpreted as a webhook-retry issue but actually shows poll-side ID drift) | Either: (a) `id` should be stable per physical transaction — your API should not mint a fresh ID for the same bill_number on subsequent edits/voids/re-rings — OR (b) you treat `id` as ephemeral-by-design and clients should use `bill_number` as the stable key, in which case please document this clearly so we don't have to reverse-engineer it. Also possibly related: aggregator (FoodPanda/Grab) re-syncs may be triggering ID regeneration on your side. |
| 2 | **`order.completed` webhook DROPS `payment_methods` for aggregator orders, even though `GET /api/v1/orders/{id}` returns it correctly.** Live probe 2026-05-01 at Araneta Gateway: `GET /api/v1/orders` returned `payment_methods` 250/250 (including all 43 FoodPanda orders with `[{payment_type: "FOODPANDA ONLINE", ...}]`). Forensic audit found webhook stream had `payment_methods` populated for only 4 of 274 FoodPanda webhook payloads (1.5%). Same orders, two endpoints, different payloads. | Live API dump: `.claude/rlm_state/pos_audit/mosaic_api_sample_channel_service_channel_id_2_2026-05-01.json`. Audit: 270/274 FP webhook payloads have NULL Payment Methods. | Webhook serializer is incomplete for aggregator orders. Their own list/get endpoints return the field correctly — only the webhook drops it. Easy fix on their side, just align the webhook serializer with the GET serializer. |
| 3 | **No `terminal_id` in any API or webhook response.** Live probe 2026-05-01: 0 of 250 orders had a terminal_id field. Multi-terminal stores (e.g. SM Megamall) cannot disambiguate which physical POS terminal a transaction came from. | Live API dump fields list shows: id, location_id, business_date, bill_number, receipt_number, short_order_id, service_channel_id, service_type_id, pax_count, billed_at, paid_at, items, taxes, payment_methods, price_breakdown — no terminal/cashier/device field. | If `bill_number` is sequenced per-terminal rather than per-store, our `(location_id, business_date, bill_number)` natural key would over-deduplicate at multi-terminal stores. Need confirmation of bill_number scope AND addition of terminal_id field. |

### Suggested message to send

Copy the block below into the Mosaic vendor portal / email to Mosaic Support. Address: support@mosaic-pos.com (or whoever the account manager is — check `data/POS_Extraction/MOSAIC_POS_API_KEYS.csv` for the contact).

```
Subject: [BEBANG-ENTERPRISE] Mosaic API issue — `id` field drifts across time for the
         same `bill_number`, producing 0.7% duplicate rows in our analytics; also a
         secondary webhook serializer issue dropping aggregator payment_methods

Hi Mosaic team,

We consume orders from your platform via two paths:
  (1) GET /api/v1/orders polled every 10 minutes (PRIMARY — 99.95% of our data)
  (2) order.cancelled webhook for tombstoning (working fine, ~12 registrations)

A live audit on 2026-05-02 surfaced one major API issue and one secondary
webhook serializer issue. Details below.

Issue 1 — `id` is not stable per physical transaction
=====================================================

Live Supabase probe across our last 14 days of polled data (138,154 rows
across 49 stores) found 945 duplicate rows where multiple distinct top-level
`id` values share the same (location_id, business_date, bill_number) tuple.
That is a 0.7% inflation rate in our analytics, scaling proportionally with
volume.

Worst observed cluster:
  Store: BEBANG ARANETA GATEWAY (location_id=2557)
  Date:  2026-04-23
  bill_number: 23547
  Six distinct Mosaic order IDs: 51481228, 51481233, 51481234, 51481241,
                                 51481247, 51499274
  ID range spans ~18,000 — ingested by our poll script across multiple hours.

Within-pull behavior IS deterministic. We re-pulled the same business_date
twice, 30 seconds apart, and got identical 250 IDs both times. So the
drift only occurs ACROSS POLL RUNS — between calls, your API regenerates
or re-issues `id` for the same bill_number. Likely triggers we suspect:
aggregator re-sync push (FoodPanda/Grab), order edit/void/re-ring on
the operator side, or your internal reconciliation.

Two questions:
  Q1: Is `id` intended to be stable per physical transaction? If yes,
      this is a bug — same bill_number should map to the same id forever.
  Q2: Or is `id` ephemeral by design? If so, clients should use
      `bill_number` as the stable PK. Please confirm so we can build
      against it correctly.

Our workaround: we are adding a UNIQUE INDEX on (location_id, business_date,
bill_number) on our side and rejecting the second arrival, keeping the
earliest `id`. This is a band-aid; the right fix is your side ensuring
`id` stability OR documenting that `bill_number` is the canonical key.

Issue 2 — payment_methods dropped on the order.completed webhook (lower
priority for us today, but flagging in case you re-fix)
========================================================================

For our purposes this is no longer urgent because we use the API poll —
which returns payment_methods correctly (98%+ coverage in our data lake
for service_channel_id 1 and 2). However, we noted during testing that
the order.completed webhook payload (registered at one point in early
April per S189) was dropping payment_methods on aggregator orders —
98.5% of FoodPanda webhook payloads had empty/null payment_methods even
though GET /api/v1/orders/{id} for the same orders returns them
correctly.

If anyone is still using the order.completed webhook, the serializer
needs to be aligned with the GET serializer. Not urgent for us; flagging
for completeness.

Issue 3 — No terminal_id in API or webhook payloads
====================================================

Live API probe across three stores on 2026-05-01 confirms there is NO
terminal_id, cashier_id, device_id, or operator field anywhere in the
order response. For multi-terminal stores like SM Megamall, this means
we cannot tell which physical POS terminal a transaction came from.

Two questions for your team:
  Q1: Is the `bill_number` field scoped per-store or per-terminal-per-store?
  Q2: If per-terminal, can you add a `terminal_id` field to the order
      response (and webhook payload) so multi-terminal stores can
      reconcile correctly?

Without Q1's answer we cannot guarantee our dedup logic is correct at
multi-terminal stores.

Reference data
==============

We can share with your engineering team:
  - POS_Analytics_Forensic_Audit_2026-05-02.xlsx (the duplicate cluster list)
  - mosaic_api_dump_aranetagateway_2026-05-01.json (full API response dump
    for one day, 250 orders, showing what your GET endpoint sends)
  - Specific bill_numbers and Order ID groupings for the 18 duplicate clusters

Thanks for looking into this.

Sam Karazi
CEO, Bebang Enterprise Inc.
sam@bebang.ph
```

### When to send

Send AFTER S232 is merged and deployed. Reasons:
- Once our workaround is in place, we have stable analytics regardless of how long Mosaic takes
- Their fix may take weeks/months and we can't wait
- We're sending from a position of "we already have a fix; this is for YOUR own benefit and other clients" rather than "we're broken, fix us"

### Closeout artifact

After Sam sends, save the email + any vendor reply to:
`output/s232/vendor_outreach/mosaic_bug_report_2026-05-02.md`

Update this section with: `Status: SENT <date>` and any vendor ETA / ticket reference.

### Related ask (long-term, not blocker)

Already covered as Issue 3 in the email above. Tracking here for the closeout artifact:

- **Confirm `bill_number` scope** (per-store or per-terminal-per-store)
- **Add `terminal_id` to API and webhook payloads** (zero/250 orders had it on the live probe)

If Mosaic confirms `bill_number` is per-store, no further changes needed on our side. If per-terminal, our unique index will need to include `terminal_id` once Mosaic adds it — and we'll need to handle the transition (rows ingested before the field was added will have NULL terminal_id, partial index handles that).
